"""HTTP service for grouping failures in creator-commerce workflows."""

from __future__ import annotations

import hashlib
import traceback
from enum import Enum
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from infrai_errors import InfraiError, InfraiErrors


class Workflow(str, Enum):
    DIGITAL_ASSET_DELIVERY = "digital_asset_delivery"
    SUBSCRIBER_UPDATE = "subscriber_update"
    CONTENT_PROCESSING = "content_processing"


class IncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: Workflow
    creator_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    resource_kind: str = Field(min_length=1)
    exception_type: str = Field(min_length=1)
    exception_message: str = Field(min_length=1)
    stack_trace: str = Field(min_length=1)


class IncidentReceipt(BaseModel):
    captured: bool
    event: dict[str, Any]
    grouping_key: str


def grouping_key(incident: IncidentRequest) -> str:
    """Group by workflow, resource kind, and exception class."""
    return ":".join(
        (incident.workflow.value, incident.resource_kind, incident.exception_type)
    )


def exception_payload(incident: IncidentRequest) -> dict[str, Any]:
    key = grouping_key(incident)
    return {
        "title": f"{incident.workflow.value}: {incident.exception_type}",
        "message": incident.exception_message,
        "level": "error",
        "fingerprint": key.split(":"),
        "exception": incident.stack_trace,
        "context": {
            "creator_id": incident.creator_id,
            "operation_id": incident.operation_id,
            "resource_kind": incident.resource_kind,
            "workflow": incident.workflow.value,
        },
    }


def idempotency_key(incident: IncidentRequest) -> str:
    material = f"creator-incident:{incident.creator_id}:{incident.operation_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def get_backend() -> InfraiErrors:
    return InfraiErrors()


app = FastAPI(title="Creator commerce incident capture")


@app.post("/incidents", response_model=IncidentReceipt, status_code=status.HTTP_201_CREATED)
def capture_incident(
    incident: IncidentRequest,
    backend: InfraiErrors = Depends(get_backend),
) -> IncidentReceipt:
    try:
        event = backend.capture(exception_payload(incident), idempotency_key(incident))
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
    return IncidentReceipt(
        captured=True,
        event=event,
        grouping_key=grouping_key(incident),
    )


if __name__ == "__main__":
    sample = IncidentRequest(
        workflow=Workflow.DIGITAL_ASSET_DELIVERY,
        creator_id="creator_42",
        operation_id="delivery_1042",
        resource_kind="video_download",
        exception_type="SignatureExpired",
        exception_message="download signature expired before delivery",
        stack_trace="SignatureExpired: download signature expired before delivery",
    )
    print(exception_payload(sample))
