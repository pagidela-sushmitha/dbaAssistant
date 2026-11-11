---
title: DBA On-Call and Escalation
doc_type: policy
owner: DBA Operations
last_reviewed: 2026-09-08
status: current
---
# DBA On-Call and Escalation

## Rotation and communication

The DBA team uses a weekly rotation with handoff Monday 10:00 ET. PagerDuty DBA-Primary is the production paging service, and Slack #dba-oncall carries incident coordination. Non-urgent questions belong in #dba-help. A chat message does not replace a PagerDuty page when an incident requires a timed response. The outgoing responder remains responsible until the incoming responder confirms handoff.

## Response expectations

Sev1 acknowledgement is due within 5 min, Sev2 within 15 min, and Sev3 by the next business day. Acknowledgement means a named responder accepts ownership and starts assessment; it is not a recovery guarantee. For Sev1, escalate to the secondary after 10 min and to DBA manager Priya Raman after 20 min from the initial page if active incident coverage is still needed. Keep escalation timestamps visible in the incident record.

Declare severity based on customer impact and the applicable runbook. Replication lag lasting >30 min on pg-orders or pg-billing is Sev2. An isolated legacy CRM replication failure is Sev3 under its runbook; reassess if the impact expands. Do not postpone an outage response while debating a label.

## Handoff and closure

At handoff, review open incidents, active changes, backup failures, drained replicas, and unresolved capacity alerts. Confirm Teleport access, PagerDuty routing, and Grafana PG Overview availability. Incoming responders must know any outstanding emergency approvals or expiring access requests.

Maintain an incident timeline with observed symptoms, decisions, owners, and next checkpoints. Close only after recovery is verified and follow-up work has an owner. New hires shadow 2 full rotations before becoming primary on-call.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
