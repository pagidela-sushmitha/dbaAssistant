---
title: pgBouncer Pool Operations
doc_type: runbook
owner: DBA Operations
last_reviewed: 2026-09-23
status: current
---
# pgBouncer Pool Operations

## Service contract

Northwind Data runs pgBouncer 1.23 on port 6432. All applications must connect through it. Default per database/user server pool sizes are 40 for pg-orders, 25 for pg-billing, and 10 for pg-analytics. PostgreSQL max_connections values are respectively 500, 300, and 200; adding databases or users can multiply backend demand, so do not treat one pool size as the cluster total.

## Investigate saturation

Connect to the pgBouncer administrative database through the approved Teleport path and run `SHOW POOLS;`. A pool with `cl_waiting >0` for a minute is saturated. Compare waiting clients, active servers, idle servers, and query duration with PostgreSQL activity. `SHOW STATS;` helps distinguish a brief burst from sustained demand. Check recent application releases and long transactions before proposing more server connections.

## Apply operational controls

`RELOAD;` reloads supported configuration settings and does not drop connections. Validate the intended configuration before reloading, then verify the effective values. A reload does not apply PostgreSQL settings that require a server restart.

Use `PAUSE <database>;` during coordinated maintenance to stop assigning new work and wait for active server work to complete. Long transactions can delay the pause, so monitor its progress and application timeouts. Use `RESUME <database>;` after the maintenance checks pass. Record both commands and their timestamps in the change ticket.

Review queue depth &amp; application errors after resuming traffic. Follow the connection-exhaustion runbook when backend limits are reached, and involve the application owner if retry behavior keeps the pool saturated. Confirm that no database remains paused before closing the maintenance record.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
