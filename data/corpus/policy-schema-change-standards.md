---
title: Production Schema Change Standards
doc_type: standard
owner: DBA Operations
last_reviewed: 2026-09-09
status: current
---
# Production Schema Change Standards

## Delivery and review

Run schema migrations through Flyway in CI. Add the PR label dba-review and allow a review SLA of 2 business days after the migration, impact details, and validation plan are ready. Application teams may execute their own approved migrations through this pipeline. Review approval does not replace the required ServiceNow change classification, CAB approval for normal changes, or freeze checks.

## Lock and rewrite controls

Set `lock_timeout = '5s'` for migration sessions, for example with `SET lock_timeout = '5s';` before the migration statement. Treat a lock timeout as a reason to investigate blockers and reschedule, rather than retrying in a tight loop. No volatile defaults on >10M-row tables in business hours: a volatile expression can require expensive work across existing rows. Plan phased column additions and backfills with the DBA reviewer.

Every FK needs an index on its referencing columns, using a suitable existing index when possible. PostgreSQL does not automatically create that index for a foreign key. Document the index choice and check write overhead as well as read plans. For large tables, `CREATE INDEX CONCURRENTLY` is a standard change and must run outside a transaction block; configure the Flyway migration accordingly.

## Deployment checks

Include expected table size, lock behavior, application compatibility, and a rollback or forward-repair plan in the PR. Test representative workloads before production. Coordinate deployment order when old and new application versions overlap. Validate constraints, index validity, and application errors afterward, then link the migration version and observed results to the change record. Stop if unexpected blocking threatens service and involve the on-call DBA.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
