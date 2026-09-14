# Evaluation Metrics

Evaluation in the ACP serves two masters: **acceptance** (is this agent
version safe to promote?) and **operations** (is the fleet healthy right
now?). Eval signals feed the behavioral controllers; eval gates promote
agent versions.

## Metric classes

| Class | Examples | Consumer |
|---|---|---|
| **Task outcome** | success/failure rate, completion time, goal-achievement score | dashboards, SLOs |
| **Trajectory** | plan adherence (tool calls vs. plan), goal drift, loop signatures | behavioral controllers |
| **Policy/governance** | policy-decision distribution, approval rate/reject rate, approval latency, denial reasons | governance analytics |
| **Risk** | risk-score distribution, high-risk action rate, override rate | risk dashboards |
| **Cost** | cost per task, per agent, per tenant; budget consumption velocity; 50/80/95% alert counts | cost manager, kill switch |
| **Quality** | task-specific eval suite scores, regression vs. baseline | version gates, canary |
| **Security** | injection-detection hits, anomalous tool-call rate, cross-tenant attempt count (must be 0) | SOC/SIEM feed |

## Behavioral versioning

Agent versions bundle prompts, model pins, tool sets, and memory state.
Promotion requires passing the eval gate: the candidate runs the task
suite (and canary tasks in production) and must not regress quality or
exceed risk/cost bounds. Rollout is **canary-by-outcome**, not
canary-by-traffic — agent behavior is probabilistic, so promotion is a
statistical judgment, never K8s-deterministic.

## Online eval

Production trajectories are scored (heuristic + model-judged) and fed to
the behavioral controllers: stuck/loop detection, eval/trajectory drift,
goal-drift. N consecutive validation failures ⇒ quarantine + re-plan
without the agent (poison-pill protocol) rather than propagating its
outputs downstream.

## What we delegate

Trace storage, trajectory scoring UI, offline eval harnesses — LangSmith,
Arize AX/Phoenix, Langfuse, Braintrust, MLflow. The ACP consumes their
signals via standard interfaces; it does not rebuild them. What the ACP
owns: eval *gates* wired into the lifecycle and version promotion, and the
immutable `EvaluationCompleted` audit events.
