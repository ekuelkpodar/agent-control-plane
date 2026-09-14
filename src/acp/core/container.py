"""DI container: all components constructed once, injected explicitly.
No hidden global state — the container lives on app.state."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field

from nacl.signing import SigningKey

from acp.core.config import Settings
from acp.db import get_session_factory, init_db
from acp.evaluation import run_evaluation  # noqa: F401  (re-export for services)
from acp.events import EventBus, InProcessEventBus, RedisStreamsEventBus
from acp.governance.audit import AuditLedger
from acp.governance.delegation import DelegationIssuer
from acp.governance.policy import build_policy_engine
from acp.governance.risk import RiskEngine
from acp.governance.secrets import EnvSecretBroker
from acp.knowledge import KnowledgeService
from acp.learning import LearningService
from acp.memory import PostgresMemoryStore
from acp.observability import configure_observability
from acp.planner import build_planner
from acp.router import WeightedRouter
from acp.tools import LocalFunctionToolExecutor
from acp.workflow import PostgresDurableRunner


@dataclass
class AppContainer:
    settings: Settings
    session_factory: object = field(repr=False)
    policy_engine: object = field(repr=False)
    risk_engine: RiskEngine = field(repr=False)
    audit_ledger: AuditLedger = field(repr=False)
    event_bus: EventBus = field(repr=False)
    delegation_issuer: DelegationIssuer = field(repr=False)
    secret_broker: EnvSecretBroker = field(repr=False)
    tool_executor: LocalFunctionToolExecutor = field(repr=False)
    planner: object = field(repr=False)
    router: WeightedRouter = field(repr=False)
    workflow_runner: PostgresDurableRunner = field(repr=False)
    memory_store: PostgresMemoryStore = field(repr=False)
    knowledge: KnowledgeService = field(repr=False)
    learning: LearningService = field(repr=False)
    revoked_delegation_jtis: set = field(default_factory=set, repr=False)

    def session(self):
        return self.session_factory()


def _ledger_signing_key(settings: Settings) -> SigningKey | None:
    if settings.ledger_signing_key_b64:
        return SigningKey(base64.b64decode(settings.ledger_signing_key_b64))
    return None  # AuditLedger generates an ephemeral key and warns loudly


def build_container(settings: Settings | None = None) -> AppContainer:
    from acp.core.config import settings as default_settings

    settings = settings or default_settings
    configure_observability(otlp_endpoint=settings.otlp_endpoint)
    if settings.auto_migrate:
        init_db(settings.database_url)
    session_factory = get_session_factory(settings.database_url)

    policy_engine = build_policy_engine(settings)
    risk_engine = RiskEngine(settings)
    ledger = AuditLedger(_ledger_signing_key(settings))
    if settings.redis_url:
        event_bus: EventBus = RedisStreamsEventBus(settings.redis_url)
    else:
        event_bus = InProcessEventBus()

    delegation_secret = getattr(settings, "delegation_signing_secret", "") or "dev-delegation-secret-change-me"
    container = AppContainer(
        settings=settings,
        session_factory=session_factory,
        policy_engine=policy_engine,
        risk_engine=risk_engine,
        audit_ledger=ledger,
        event_bus=event_bus,
        delegation_issuer=DelegationIssuer(delegation_secret),
        secret_broker=EnvSecretBroker(),
        tool_executor=LocalFunctionToolExecutor(),
        planner=build_planner(settings.planner),
        router=WeightedRouter(),
        workflow_runner=PostgresDurableRunner(settings),
        memory_store=PostgresMemoryStore(),
        knowledge=KnowledgeService(),
        learning=LearningService(policy_engine),
    )
    return container
