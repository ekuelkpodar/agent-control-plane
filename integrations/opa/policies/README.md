# OPA bundle: booking approval threshold + destructive-action guardrail.
# See policies/booking.rego (sample). Add tenant bundles as
# integrations/opa/policies/tenants/<tenant_id>.rego and set
# ACP_OPA_URL to the OPA server; the ACP OPA adapter queries
# /v1/data/acp/authz with {"input": {...}}.
