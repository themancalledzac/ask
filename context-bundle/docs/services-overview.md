# Services Overview — Aपरture Robotics (internal)

This page is the closest thing we have to a map of what runs where. It is
**not** authoritative and is updated "whenever someone remembers to." If you
find it wrong, fix it (or ping the owner listed in `services.json`).

| Service | What it does | Team |
| --- | --- | --- |
| atlas-api | Core GraphQL/REST API behind the app | Platform |
| beacon | Notification + alerting fan-out | Platform |
| courier | Outbound email/SMS to customers | Growth |
| ledger | Billing, invoices, usage metering | Ops |
| forge | Internal build + deploy pipeline | Platform |
| lookout | Customer-facing status dashboard | Growth |

If you're trying to figure out **who owns a service**, the answer lives in
`services.json`, not here — this table goes stale fast.
