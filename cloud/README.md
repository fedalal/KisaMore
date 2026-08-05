# KisaMore Cloud API

The central service receives outbound snapshots from the Raspberry Pi and exposes a separate
read-only endpoint for the public website. It does not contain light, watering, configuration,
or shutdown commands.

## Data flow

1. The Pi reads its existing SQLite state and latest saved sensor samples.
2. Every 30 seconds it sends an HTTPS request authenticated by a device ID and a random token.
3. The API stores current rack state and telemetry history in PostgreSQL.
4. The public site reads only `/api/v1/public/farms/{slug}/live`.

The Raspberry Pi does not accept incoming internet connections.

## VPS start with Docker Compose

```bash
cp cloud/.env.example cloud/.env
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Put the generated value in KISAMORE_BOOTSTRAP_DEVICE_TOKEN.

docker compose --env-file cloud/.env -f docker-compose.cloud.yml up -d --build
curl http://127.0.0.1:8080/api/v1/health
```

Publish `127.0.0.1:8080` through Nginx at an HTTPS hostname such as `api.kisamore.com`.
Do not expose PostgreSQL to the internet.

## Raspberry Pi configuration

Install the updated dependencies, then add these variables to the `kisamore.service` systemd
unit (preferably via an `EnvironmentFile` readable only by root):

```dotenv
KISAMORE_CLOUD_URL=https://api.kisamore.com
KISAMORE_DEVICE_ID=greenhouse-pi-01
KISAMORE_DEVICE_TOKEN=the-same-random-token-used-on-the-vps
KISAMORE_CLOUD_INTERVAL_SECONDS=30
KISAMORE_CLOUD_TIMEOUT_SECONDS=10
KISAMORE_SOFTWARE_VERSION=d7caafd-cloud-sync
```

Then run:

```bash
source kisamoreevn/bin/activate
pip install -r requirements.txt
sudo systemctl daemon-reload
sudo systemctl restart kisamore.service
journalctl -u kisamore.service -f
```

Expected log line:

```text
[cloud-sync] snapshot sent: racks=4
```

Without the three required cloud variables, synchronization stays disabled and the existing
local controller continues to operate normally.

## API

- `GET /api/v1/health` — service/database health.
- `POST /api/v1/edge/snapshot` — authenticated device ingestion.
- `GET /api/v1/public/farms/demo-farm/live` — public read-only state.
- `GET /api/docs` — OpenAPI UI.

The bootstrap token is hashed before it is stored. Once a device exists, changing only the
bootstrap token environment variable does not rotate its credentials.
