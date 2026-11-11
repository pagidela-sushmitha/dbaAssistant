---
title: Database Data Classification and Masking
doc_type: policy
owner: Security Engineering
last_reviewed: 2026-09-03
status: current
---
# Database Data Classification and Masking

## Classification levels

Northwind Data classifies database information as Restricted, Confidential, or Internal. Restricted includes PII/payment fields such as `customers.email` and `payments.card_last4`. A partial payment identifier remains Restricted even when it cannot independently authorize a payment. Confidential includes nonpublic business records and operational analysis. Internal covers routine material intended only for authorized staff. When a dataset mixes levels, handle it at the highest applicable level until the data owner approves a narrower classification.

## Production copies

Restricted data is never copied to non-prod unmasked. This rule applies to exports, restored backups, query samples, screenshots, and developer fixtures. A read-only role does not grant permission to distribute query results. Production restores remain isolated with restricted access until the intended destination and masking plan have been approved.

Every staging refresh must use the masking tool nw-mask. The refresh owner verifies masking coverage for the current schema, runs the approved transformation, and checks representative records without placing original values in the evidence. New Restricted columns must be added to masking configuration before a refresh can proceed.

## Evidence and ownership

Use aggregate counts or synthetic examples in tickets and chat. For example, `SELECT count(*) FROM customers WHERE email IS NULL;` can verify completeness without publishing addresses. Avoid statements that expose raw values in logs or exported plans. Masking &amp; validation must preserve required relationships without preserving identifying content.

The inventory names each cluster's accountable data owner. Consult that owner and Security Engineering when classification is unclear. Record the source, destination, masking validation, and authorized recipients for each approved refresh; stop distribution and report any unmasked copy immediately.

---
Northwind Data · Confidential · Internal Use Only · Printed copies are uncontrolled
