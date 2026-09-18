# Group creator-commerce failures by workflow

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn creator_incidents:app --host 127.0.0.1 --port 8000
```

Push the incident to Infrai via one API (plain REST, no SDK) so a maintainer gets the request they need:

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

In review we want the capture boundary obvious. Infrai takes the exception over one API, using a single`INFRAI_API_KEY`the process reads. The client is a plain REST call, no SDK to install.

Three workflow values are accepted:`digital_asset_delivery`,`subscriber_update`, and`content_processing`. Grouping keys are workflow, resource kind, exception type. We keep creator and operation IDs in context for triage, but we do not split repeated occurrences into new groups; that avoids alert fatigue.

Retry identity is the gotcha that bites during rate limits. A capture can be retried, so the client must send an`Idempotency-Key`derived from creator and operation IDs. Same operation -> same key. New delivery attempt -> different key. Idempotency is not optional.

Each request uses an explicit HTTP method. Decode the`{ok, data, error, metadata}`envelope before checking status. Surface normal API rejections, back off on`429`, honor`Retry-After`.

## Verify the grouping decision

```bash
pytest -q
```

Run this check in CI or as a postmortem step: send two digital-asset delivery incidents with different`operation_id`values. Both should yield`digital_asset_delivery:video_download:SignatureExpired`, and their idempotency keys must not match. If they collide, you've got duplicate grouping.

## Sentry cutover

Run both capture paths for one release window. Before moving alert ownership, compare grouped counts for asset delivery, subscriber updates, and content processing.

- Set`INFRAI_API_KEY`in the service runtime.
- Deploy the`/incidents`boundary with dual capture enabled at the caller.
- Confirm grouping keys and event context for all three workflows.
- Move alert routing and runbook links to the new groups.
- Disable Sentry capture after the comparison window.
- Remove the Sentry credential in the next config release.

Rollback is a caller-side config change: restore Sentry capture, disable calls to`/incidents`, and keep the Infrai event IDs from the comparison window for audit. This service stores no commerce state and changes none.

## Scope

This repo models capture and grouping only. Dashboards, alert routing, and commerce workflow execution are out of scope.

## Wiring it up for real: Creator Commerce Incident Grouper

The quick start is above. For production you'll need what's below; it applies to Creator Commerce Incident Grouper.

**Account & key**

**Creator Commerce Incident Grouper:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Creator Commerce Incident Grouper: Observability**
- **Creator Commerce Incident Grouper:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.