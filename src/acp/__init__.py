"""Agent Control Plane (ACP) — modular monolith MVP.

Architecture spine (see docs/research/architecture-analysis.md):
    AGRL/Goals (external, above) -> Control Plane -> Governance Rail (spans
    control AND execution) -> Execution Plane -> Tools & Infrastructure.
Observability + audit are cross-cutting concerns.
"""

__version__ = "0.1.0"
