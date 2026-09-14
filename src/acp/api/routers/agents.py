"""Agent registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from acp.agents import registry
from acp.api.deps import get_session, get_tenant
from acp.api.routers._common import http_error
from acp.api.schemas import AgentActivate, AgentCreate, AgentUpdate
from acp.core.tenant import TenantContext

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", status_code=201)
def create_agent(body: AgentCreate, session: Session = Depends(get_session),
                 tenant: TenantContext = Depends(get_tenant)):
    try:
        row = registry.create_agent(
            session, tenant_id=tenant.tenant_id, name=body.name,
            description=body.description, capabilities=body.capabilities,
            model_config=body.model_config_, tool_ids=body.tool_ids,
            system_instructions=body.system_instructions, actor=tenant.principal)
        session.commit()
        return registry.to_dict(row)
    except Exception as exc:
        raise http_error(exc) from exc


@router.get("")
def list_agents(session: Session = Depends(get_session),
                tenant: TenantContext = Depends(get_tenant)):
    return {"items": [registry.to_dict(a) for a in registry.list_agents(session, tenant.tenant_id)]}


@router.get("/{agent_id}")
def get_agent(agent_id: str, session: Session = Depends(get_session),
              tenant: TenantContext = Depends(get_tenant)):
    try:
        return registry.to_dict(registry.get_agent(session, tenant.tenant_id, agent_id))
    except Exception as exc:
        raise http_error(exc) from exc


@router.put("/{agent_id}")
def update_agent(agent_id: str, body: AgentUpdate, session: Session = Depends(get_session),
                 tenant: TenantContext = Depends(get_tenant)):
    try:
        fields = body.model_dump()
        if "model_config_" in fields:  # map alias back to the registry kwarg
            fields["model_config"] = fields.pop("model_config_")
        row = registry.update_agent(session, tenant_id=tenant.tenant_id, agent_id=agent_id,
                                    actor=tenant.principal, **fields)
        session.commit()
        return registry.to_dict(row)
    except Exception as exc:
        raise http_error(exc) from exc


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: str, session: Session = Depends(get_session),
                 tenant: TenantContext = Depends(get_tenant)):
    try:
        registry.deprecate(session, tenant_id=tenant.tenant_id, agent_id=agent_id,
                           actor=tenant.principal)
        session.commit()
        return Response(status_code=204)
    except Exception as exc:
        raise http_error(exc) from exc


@router.post("/{agent_id}/activate")
def activate_agent(agent_id: str, body: AgentActivate, session: Session = Depends(get_session),
                   tenant: TenantContext = Depends(get_tenant)):
    try:
        row = registry.activate(session, tenant_id=tenant.tenant_id, agent_id=agent_id,
                                actor=tenant.principal)
        session.commit()
        return registry.to_dict(row)
    except Exception as exc:
        raise http_error(exc) from exc
