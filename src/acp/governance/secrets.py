"""Credential brokering: agents NEVER see raw secrets.

SecretBroker interface: issue / lease / revoke / rotate.
- EnvSecretBroker: dev adapter. Reads from environment, holds values ONLY in
  memory under a lease, and WARNS LOUDLY that it is not production.
- VaultSecretBroker: stub adapter for HashiCorp Vault (dynamic secrets).
  Raises NotImplementedError until wired; documents the intended integration.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

from acp.core.utils import new_id

log = logging.getLogger(__name__)


@dataclass
class Lease:
    lease_id: str
    tenant_id: str
    tool_id: str
    issued_at: float
    expires_at: float
    revoked: bool = False
    # The credential VALUE is intentionally not stored on the Lease object that
    # crosses boundaries; issue() returns a one-time envelope to the caller
    # (the tool gateway), which injects it server-side.
    _credential: str = field(default="", repr=False)


class EnvSecretBroker:
    """DEV ONLY broker. Secrets come from process env (ACP_TOOL_SECRET_<NAME>).

    WARNING: not for production — use VaultSecretBroker (Vault dynamic secrets).
    """

    def __init__(self):
        log.warning(
            "SecretBroker: using EnvSecretBroker (DEV ONLY). Agents never see raw "
            "secrets, but env-backed static secrets lack rotation/lease enforcement "
            "of Vault. Do not use in production."
        )
        self._leases: dict[str, Lease] = {}

    def _env_name(self, tool_id: str, tool_name: str = "") -> str:
        base = (tool_name or tool_id).upper().replace("-", "_").replace(" ", "_")
        return f"ACP_TOOL_SECRET_{base}"

    def issue(self, tenant_id: str, tool_id: str, ttl_seconds: int = 300, tool_name: str = "") -> dict:
        value = os.environ.get(self._env_name(tool_id, tool_name), "")
        if not value:
            log.warning("EnvSecretBroker: no secret configured for tool %r; issuing empty lease", tool_id)
        lease = Lease(
            lease_id=new_id(), tenant_id=tenant_id, tool_id=tool_id,
            issued_at=time.time(), expires_at=time.time() + ttl_seconds,
            _credential=value,
        )
        self._leases[lease.lease_id] = lease
        # The envelope hands the VALUE only to the tool gateway (server-side
        # injection). It is never placed in agent-visible context.
        return {"lease_id": lease.lease_id, "expires_at": lease.expires_at, "_credential": value}

    def revoke(self, lease_id: str) -> None:
        lease = self._leases.get(lease_id)
        if lease:
            lease.revoked = True
            lease._credential = ""

    def rotate(self, tool_id: str) -> None:
        for lease in self._leases.values():
            if lease.tool_id == tool_id and not lease.revoked:
                lease.revoked = True
                lease._credential = ""
        log.info("EnvSecretBroker: revoked all leases for tool %r (rotation = update env + restart)", tool_id)

    def lease_valid(self, lease_id: str) -> bool:
        lease = self._leases.get(lease_id)
        return bool(lease and not lease.revoked and lease.expires_at > time.time())


class VaultSecretBroker:
    """STUB: HashiCorp Vault adapter (dynamic secrets, SPIFFE auth).

    Intended integration: hvac client, Vault dynamic-secret roles per tool,
    5-minute leases, immediate revocation. Not wired in the MVP — the
    interface boundary is the architecture; this adapter is the V1 step.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "VaultSecretBroker is a documented stub for V1. "
            "Use EnvSecretBroker for dev (it warns loudly)."
        )

    def issue(self, tenant_id: str, tool_id: str, ttl_seconds: int = 300) -> dict:  # pragma: no cover
        raise NotImplementedError

    def revoke(self, lease_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def rotate(self, tool_id: str) -> None:  # pragma: no cover
        raise NotImplementedError
