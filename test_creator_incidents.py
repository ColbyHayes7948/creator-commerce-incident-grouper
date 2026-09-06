from fastapi.testclient import TestClient

from creator_incidents import app, get_backend


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, str]] = []

    def capture(self, exception_payload: dict, idempotency_key: str) -> dict:
        self.calls.append((exception_payload, idempotency_key))
        return {"event_id": "evt_test_1"}


def test_delivery_attempts_share_a_group_but_keep_distinct_idempotency_keys() -> None:
    backend = RecordingBackend()
    app.dependency_overrides[get_backend] = lambda: backend
    client = TestClient(app)

    common = {
        "workflow": "digital_asset_delivery",
        "creator_id": "creator_42",
        "resource_kind": "video_download",
        "exception_type": "SignatureExpired",
        "exception_message": "download signature expired before delivery",
        "stack_trace": "SignatureExpired: download signature expired before delivery",
    }
    first = client.post("/incidents", json={**common, "operation_id": "delivery_1042"})
    second = client.post("/incidents", json={**common, "operation_id": "delivery_1043"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["grouping_key"] == second.json()["grouping_key"]
    assert backend.calls[0][0]["fingerprint"] == [
        "digital_asset_delivery",
        "video_download",
        "SignatureExpired",
    ]
    assert backend.calls[0][1] != backend.calls[1][1]
    app.dependency_overrides.clear()
