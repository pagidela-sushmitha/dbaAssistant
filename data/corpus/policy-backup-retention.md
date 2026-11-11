---
title: Database Backup Retention and Recovery Access
doc_type: policy
owner: Infrastructure Governance
last_reviewed: 2026-09-07
status: current
---
# Database Backup Retention and Recovery Access

## Retention requirements

Production PostgreSQL backups provide 35 days PITR, with pg-analytics explicitly limited to 14 days. Monthly fulls are retained for 13 months, including analytics. A retained monthly full supports recovery to that backup; it does not promise continuous WAL coverage outside the cluster's PITR window. Owners must distinguish these recovery capabilities when making requests.

pgBackRest writes full backups Sunday 02:00 UTC, differential backups daily, and continuous WAL to S3. Backup storage uses AES-256 with KMS. Restrict storage and KMS permissions to approved service identities and responders. Encryption does not remove the data's classification or authorize wider access to restored records.

## Restore requests

A non-incident restore requires ServiceNow and has an SLA of 1 business day. Include the source cluster, required point in time with timezone, business purpose, data owner, and intended destination. This fulfillment SLA covers coordination and response; transfer and recovery duration depend on volume and WAL replay. The operational estimate is approximately 45 min per 500 GB, followed by validation.

## Handling recovered data

Never restore onto a running primary. Use the isolated restore host `restore-01.db.nw.internal` under the backup-restore runbook. Restored prod data cannot go to non-prod unless masked with nw-mask and validated against the data-classification policy. Restrict access while masking and verification occur.

Record the selected backup, recovery timestamp, validation evidence, authorized recipients, and cleanup disposition. Review backup failures promptly and test recovery through approved changes. Retention is a protection objective, not proof that every restore point is usable; confirm the available backup chain before promising a recovery time.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
