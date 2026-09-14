# Simple Agent — Quickstart

The minimal loop: register an agent → create a task → execute it → read the
audit trail. Uses only the public REST contract.

## Prerequisites

```bash
docker compose up -d            # or: make dev
export ACP_API_KEY=<your key>
export ACP_API_URL=http://localhost:8000
export ACP_TENANT_ID=demo
```

## 1. Register an agent

```bash
curl -s -X POST $ACP_API_URL/api/v1/agents \
  -H "Authorization: Bearer $ACP_API_KEY" \
  -H "X-Tenant-ID: $ACP_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello-agent",
    "description": "Minimal demo agent.",
    "capabilities": ["echo"],
    "version": "0.1.0"
  }'
# -> {"id": "<agent-id>", "tenant_id": "demo", "status": "registered", ...}
```

## 2. Create a task

```bash
curl -s -X POST $ACP_API_URL/api/v1/tasks \
  -H "Authorization: Bearer $ACP_API_KEY" \
  -H "X-Tenant-ID: $ACP_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Summarize the attached shipment manifest.",
    "input": {"manifest_ref": "MAN-001"}
  }'
# -> {"id": "<task-id>", "tenant_id": "demo", "goal": "...", "status": "created", ...}
```

## 3. Execute the governed pipeline

```bash
TASK=<task-id from step 2>

curl -s -X POST $ACP_API_URL/api/v1/tasks/$TASK/execute \
  -H "Authorization: Bearer $ACP_API_KEY" \
  -H "X-Tenant-ID: $ACP_TENANT_ID"
```

The task flows through admission → plan → risk → policy → (approval if
required) → execute. Poll until terminal:

```bash
curl -s $ACP_API_URL/api/v1/tasks/$TASK \
  -H "Authorization: Bearer $ACP_API_KEY" \
  -H "X-Tenant-ID: $ACP_TENANT_ID" | python3 -m json.tool
```

If the task lands in `awaiting_approval`, decide it:

```bash
curl -s $ACP_API_URL/api/v1/approvals?status=requested \
  -H "Authorization: Bearer $ACP_API_KEY" \
  -H "X-Tenant-ID: $ACP_TENANT_ID"

curl -s -X POST $ACP_API_URL/api/v1/approvals/<approval-id>/approve \
  -H "Authorization: Bearer $ACP_API_KEY" \
  -H "X-Tenant-ID: $ACP_TENANT_ID"
```

## 4. Read the audit trail

```bash
curl -s "$ACP_API_URL/api/v1/audit?task_id=$TASK" \
  -H "Authorization: Bearer $ACP_API_KEY" \
  -H "X-Tenant-ID: $ACP_TENANT_ID" | python3 -m json.tool
```

Every decision — admission, plan, routing, policy, risk, approval, tool
calls — is a hash-chained, signed entry.

## Next

For the full governed flow with a high-risk approval and a deny path, see
[`../logistics-agent/`](../logistics-agent/) (`demo.py` + walkthrough).
