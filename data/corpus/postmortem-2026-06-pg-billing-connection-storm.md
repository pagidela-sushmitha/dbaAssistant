---
title: June 2026 Billing Connection Storm
doc_type: postmortem
owner: Billing Team
last_reviewed: 2026-09-12
status: current
---
# June 2026 Billing Connection Storm

## Incident summary

On 2026-06-02, pg-billing suffered a Sev2 incident lasting 18 minutes. billing-api v4.2 bypassed pgBouncer and opened direct PostgreSQL connections on port 5432. The resulting connection storm exhausted the cluster's 300 max_connections limit and produced SQLSTATE 53300 errors, including "sorry, too many clients already". Billing requests failed or retried while existing sessions occupied backend capacity.

## Timeline and mitigation

At 15:06 UTC, application errors rose immediately after the v4.2 rollout. The DBA compared session counts by application with `SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name;`. pgBouncer queue statistics did not match the increase in PostgreSQL connections, pointing to a routing bypass rather than ordinary pool saturation.

The Billing responder rolled back billing-api to v4.1. New connections again used pgBouncer on port 6432, and direct sessions drained as the faulty instances stopped. The team did not raise max_connections or restart PostgreSQL. Error rates and a representative billing workflow were healthy by 15:24 UTC, completing the 18-minute incident.

## Cause and corrective actions

A connection configuration change escaped deployment review because tests checked database reachability without checking the endpoint port. Aggressive client retries increased the number of simultaneous attempts.

Billing added CI lint rejecting port 5432 in application production connection settings. DBA Operations added PgConnectionsHigh at 80% utilization. The pool remains 25 per database/user for pg-billing; increasing it was not required for recovery. Follow-up validation exercises deployment configuration checks and confirms pooler routing before rollout. The application owner also reviewed retry bounds so a future connection failure cannot immediately multiply demand.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
