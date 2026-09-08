from cloud.app.mqtt_sync import _mqtt_reason_code_failed


class _ReasonCode:
    def __init__(self, is_failure):
        self.is_failure = is_failure


class _ReasonCodeWithValue:
    value = 0


def test_mqtt_reason_code_accepts_paho_v2_success_object():
    assert _mqtt_reason_code_failed(_ReasonCode(False)) is False


def test_mqtt_reason_code_accepts_paho_v2_failure_object():
    assert _mqtt_reason_code_failed(_ReasonCode(True)) is True


def test_mqtt_reason_code_accepts_numeric_and_value_codes():
    assert _mqtt_reason_code_failed(0) is False
    assert _mqtt_reason_code_failed(5) is True
    assert _mqtt_reason_code_failed(_ReasonCodeWithValue()) is False
