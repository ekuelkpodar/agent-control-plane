# Planner Strategies

The planner turns a task goal into a plan (steps, tool calls, cost
estimate) that the governance rail then evaluates. The planner is
**strategy-based**: a `PlannerStrategy` interface with swappable
implementations. The plan is *advisory* — nothing executes until policy,
risk, and (where required) approval gates clear it.

## Strategy interface

```python
class PlannerStrategy(Protocol):
    name: str
    def plan(self, task: Task, context: PlanContext) -> Plan: ...
```

`PlanContext` carries: the agent's capabilities and granted tools, budget
envelope, tenant policy constraints, memory/knowledge retrieval access,
and the delegation scope. The strategy may only propose tools inside the
granted set.

## MVP strategies

1. **`rule_based`** (default): deterministic decomposition from a
   capability→tool mapping. Predictable, testable, auditable. Sufficient
   for the MVP demo flows (quote → approve → book).
2. **`template`**: plan templates for known task shapes (e.g. "compare
   then decide"), parameterized by the task input.
3. **`llm_assisted`** (V1): an LLM proposes plans; a deterministic
   validator checks the plan against granted tools, schemas, and budget
   *before* it enters the governance rail. The validator is the trust
   boundary, not the model.

## Plan contents

Every plan declares: ordered steps, the exact tools per step with
argument schemas, estimated cost, estimated risk tier, and fallback
actions per step (retry with backoff, alternate tool, compensation).
Plans are versioned artifacts; a changed plan re-enters policy evaluation.

## Planner fallback

If a strategy fails (model timeout, no viable decomposition), the task
falls back to the next strategy in order, then to human escalation — a
failed plan is a paused task, not a silently-degraded one. Confidence-gated
escalation: low-confidence plans on high-stakes tasks route to human review
*before* any execution.

## What the planner does NOT do

- It does not authorize (the rail does).
- It does not choose models by itself (the router does).
- It does not see secrets or raw credentials.
- It does not mutate goals — task intents arrive from AGRL; the planner
  works strictly within the task's goal and constraints.
