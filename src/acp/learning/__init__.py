"""Learning: PROPOSE-ONLY.

Any learning proposal (prompt change, policy change, routing-weight change)
must pass policy evaluation AND human approval before it takes effect.
There is NO uncontrolled self-modification: proposals are inert records until
a human approves them through the approval workflow.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from acp.core.errors import PolicyDenied
from acp.core.utils import new_id
from acp.db.models import LearningProposal


class LearningService:
    def __init__(self, policy_engine):
        self._policy = policy_engine

    def propose_change(
        self, session: Session, *, tenant_id: str, proposal_type: str,
        payload: dict[str, Any], proposed_by: str,
    ) -> LearningProposal:
        decision = self._policy.evaluate({
            "kind": "learning",
            "tenant_id": tenant_id,
            "proposal_type": proposal_type,
            "payload": payload,
        })
        if decision.decision == "deny":
            raise PolicyDenied(f"learning proposal denied by policy: {decision.reasons}")
        # require_approval is the normal path: the proposal is recorded as
        # "proposed" and a human must approve it before application.
        proposal = LearningProposal(
            id=new_id(), tenant_id=tenant_id, proposal_type=proposal_type,
            payload={**payload, "proposed_by": proposed_by},
            policy_decision={"decision": decision.decision, "reasons": decision.reasons,
                             "version_hash": decision.policy_version_hash},
            status="proposed",
        )
        session.add(proposal)
        session.flush()
        return proposal

    def apply_proposal(self, session: Session, *, tenant_id: str, proposal_id: str,
                       approved_by_human: bool) -> LearningProposal:
        """Application requires explicit human approval — never automatic."""
        from sqlalchemy import select

        from acp.core.errors import NotFound

        proposal = session.execute(
            select(LearningProposal).where(
                LearningProposal.id == proposal_id, LearningProposal.tenant_id == tenant_id
            )
        ).scalars().first()
        if proposal is None:
            raise NotFound("learning proposal not found")
        if not approved_by_human:
            raise PolicyDenied("learning proposals require human approval (no self-modification)")
        proposal.status = "applied"
        session.flush()
        return proposal
