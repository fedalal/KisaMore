"""Check return URLs without creating invoices or touching a live payment."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from cloud.app import lava_payments_service as service
from cloud.app import lava_webhook_api as api
from cloud.app.lava_webhook_api import CheckoutRequest, _checkout_return_origin
from cloud.app.security import get_current_user, get_session


def request(host):
    return Request({"type": "http", "method": "POST", "scheme": "https", "path": "/",
                    "query_string": b"", "headers": [(b"host", host.encode())],
                    "server": (host, 443)})


class CheckoutReturnOriginTests(unittest.TestCase):
    def test_only_approved_origins_can_be_selected(self):
        main = CheckoutRequest(kind="topup", kisa=10)
        mirror = CheckoutRequest(kind="topup", kisa=10, return_origin="https://ru.kisamore.farm")
        self.assertEqual(_checkout_return_origin(main, request("kisamore.farm")), "https://kisamore.farm")
        self.assertEqual(_checkout_return_origin(main, request("ru.kisamore.farm")), "https://ru.kisamore.farm")
        self.assertEqual(_checkout_return_origin(main, request("attacker.example")), "https://kisamore.farm")
        # A mirror proxy can forward the main Host; the browser origin wins.
        self.assertEqual(_checkout_return_origin(mirror, request("kisamore.farm")), "https://ru.kisamore.farm")
        with self.assertRaises(ValidationError):
            CheckoutRequest(kind="topup", kisa=10, return_origin="https://attacker.example")

    def test_provider_receives_correct_return_urls_and_language(self):
        captured = []

        class Response:
            status_code = 201
            def json(self):
                return {"id": "a38e22a3-4094-4734-a8d8-d38554c985af", "paymentUrl": "https://app.lava.top/test"}

        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def post(self, url, json, headers):
                captured.append(json)
                return Response()

        async def run():
            with patch.object(service, "_headers", return_value={}), patch.object(service.httpx, "AsyncClient", Client):
                for origin in ("https://kisamore.farm", "https://ru.kisamore.farm", "https://attacker.example"):
                    await service.create_lava_invoice(email="buyer@example.test", offer_id="offer", kind="topup", amount=10, buyer_language="RU", return_base=origin)

        asyncio.run(run())
        for body, host in zip(captured, ("https://kisamore.farm", "https://ru.kisamore.farm", "https://kisamore.farm")):
            self.assertEqual(body["buyerLanguage"], "RU")
            self.assertEqual(body["currency"], "USD")
            self.assertEqual(body["amount"], 10)
            for key, status in (("successful_return_url", "return"), ("failure_return_url", "failed"), ("cancel_return_url", "cancelled")):
                self.assertEqual(body[key], f"{host}/wallet?payment={status}")

    def test_authenticated_checkout_passes_mirror_origin_to_provider(self):
        class Session:
            def add(self, value): self.order = value
            async def commit(self): pass

        app = FastAPI()
        app.include_router(api.router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="buyer-1", email="buyer@example.test")
        app.dependency_overrides[get_session] = lambda: Session()
        create = AsyncMock(return_value=("a38e22a3-4094-4734-a8d8-d38554c985af", "https://app.lava.top/test"))
        with patch.object(api, "enabled", return_value=False), patch.object(api, "test_admin_enabled", return_value=True), patch.object(api, "create_lava_invoice", create):
            with TestClient(app, base_url="https://kisamore.farm") as client:
                response = client.post("/api/v1/payments/checkout", json={
                    "kind": "topup", "kisa": 10, "language": "ru",
                    "return_origin": "https://ru.kisamore.farm",
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(create.await_args.kwargs["return_base"], "https://ru.kisamore.farm")
                self.assertEqual(create.await_args.kwargs["buyer_language"], "RU")
                rejected = client.post("/api/v1/payments/checkout", json={
                    "kind": "topup", "kisa": 10, "return_origin": "https://attacker.example",
                })
                self.assertEqual(rejected.status_code, 422)
                self.assertEqual(create.await_count, 1)


if __name__ == "__main__":
    unittest.main()
