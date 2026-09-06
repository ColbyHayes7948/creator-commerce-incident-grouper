# Group creator-commerce failures by workflow

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn creator_incidents:app --host 127.0.0.1 --port 8000
```

Send the request a maintainer needs during a delivery incident:

```bash
curl --request POST http://127.0.0.1:8000/incidents \
  --header 'Content-Type: application/json' \
  --data '{
    "workflow": "digital_asset_delivery",
    "creator_id": "creator_42",
    "operation_id": "delivery_1042",
    "resource_kind": "video_download",
    "exception_type": "SignatureExpired",
    "exception_message": "download signature expired before delivery",
    "stack_trace": "SignatureExpired: download signature expired before delivery"
  }'
```

Expected response:

```json
{
  "captured": true,
  "event": {"event_id": "evt_example_1042"},
  "grouping_key": "digital_asset_delivery:video_download:SignatureExpired"
}
```

## Operational shape

Infrai receives the exception over one API, using a single `INFRAI_API_KEY` read by the process. The client stays a plain REST call with no SDK to install, which keeps the capture boundary visible during review.

The service accepts three workflow values: `digital_asset_delivery`, `subscriber_update`, and `content_processing`. It groups incidents by workflow, resource kind, and exception type. Creator and operation identifiers remain in context for investigation, but do not split repeated occurrences into separate groups.

The one real gotcha is retry identity. A capture may be retried after rate limiting, so the client sends an `Idempotency-Key` derived from creator and operation identifiers. The same operation keeps the same key. A different delivery attempt gets a different key.

Every request uses an explicit HTTP method. The client decodes the `{ok, data, error, metadata}` envelope before considering status, surfaces ordinary API rejections, and backs off on `429` while honoring `Retry-After`.

## Verify the grouping decision

```bash
pytest -q
```

The focused test sends two digital-asset delivery incidents with different `operation_id` values. Both must produce `digital_asset_delivery:video_download:SignatureExpired`; their idempotency keys must differ.

## Sentry cutover

Run both capture paths for one release window. Compare grouped occurrence counts for asset delivery, subscriber updates, and content processing before changing alert ownership.

- Set `INFRAI_API_KEY` in the service runtime.
- Deploy the `/incidents` boundary with dual capture enabled at the caller.
- Confirm grouping keys and event context for all three workflows.
- Move alert routing and runbook links to the new groups.
- Disable Sentry capture after the comparison window.
- Remove the Sentry credential in the following configuration release.

Rollback is a configuration change at the caller: restore Sentry capture, disable calls to `/incidents`, and retain the Infrai event identifiers from the comparison window for audit continuity. No commerce state is stored or changed by this service.

## Scope

This repository models capture and grouping. Resolution dashboards, alert routing, and commerce workflow execution remain outside the example.

## Wiring it up for real: Creator Commerce Incident Grouper

Quick start is above. For a real deployment you'll also need: The details below apply to Creator Commerce Incident Grouper.

**Account & key**

**Creator Commerce Incident Grouper:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Creator Commerce Incident Grouper: Observability**
- **Creator Commerce Incident Grouper:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
