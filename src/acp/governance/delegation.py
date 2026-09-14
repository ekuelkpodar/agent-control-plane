"""Constrained delegation tokens (OAuth 2.1 token-exchange style).

Authority = identity + policy decision + delegation token.
Tokens are: tenant-bound, task-scoped, tool-scoped, short-lived,
audience-bound, and NARROW-ONLY (a derived token can only narrow scope).
"""

from __future__ import annotations

import time
from typing import Any

import jwt

from acp.core.errors import PolicyDenied
from acp.core.utils import new_id, utcnow


class DelegationIssuer:
    AUDIENCE = "acp-tool-gateway"

    def __init__(self, signing_secret: str):
        self._secret = signing_secret

    def issue(
        self,
        *,
        tenant_id: str,
        subject: str,  # human user delegating
        actor_agent_id: str,
        task_id: str | None,
        scope_tools: list[str],
        audience: str,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        now = int(time.time())
        jti = new_id()
        claims = {
            "jti": jti,
            "iss": "acp-control-plane",
            "sub": subject,
            "act": actor_agent_id,  # the agent acting
            "tenant": tenant_id,
            "task": task_id,
            "scope_tools": sorted(set(scope_tools)),
            "aud": audience,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        token = jwt.encode(claims, self._secret, algorithm="HS256")
        return {"token": token, "jti": jti, "claims": claims, "expires_at": utcnow()}

    def validate(self, token: str, *, tenant_id: str, revoked_jtis: set[str] | None = None) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token, self._secret, algorithms=["HS256"], audience=self.AUDIENCE,
                options={"require": ["exp", "jti", "tenant"]},
            )
        except jwt.PyJWTError as exc:
            raise PolicyDenied(f"invalid delegation token: {exc}") from exc
        if claims.get("tenant") != tenant_id:
            raise PolicyDenied("delegation token tenant mismatch (fail closed)")
        if revoked_jtis and claims.get("jti") in revoked_jtis:
            raise PolicyDenied("delegation token revoked")
        return claims

    @staticmethod
    def narrow(parent_claims: dict[str, Any], scope_tools: list[str]) -> dict[str, Any]:
        """Derive a narrowed child claim set. Raises if scope widens."""
        parent = set(parent_claims.get("scope_tools") or [])
        child = set(scope_tools)
        if not child.issubset(parent):
            raise PolicyDenied("delegation may only narrow scope, never widen")
        narrowed = dict(parent_claims)
        narrowed["scope_tools"] = sorted(child)
        narrowed["parent_jti"] = parent_claims.get("jti")
        return narrowed
