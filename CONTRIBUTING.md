# Contributing to Agent Control Plane

Thanks for contributing. This project follows an **open-core** model:
the core in this repository is Apache-2.0; enterprise modules (if any) live
elsewhere under a commercial license. Everything in this repo is Apache-2.0.

## Ground rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Security reports go to the maintainers privately — see [SECURITY.md](SECURITY.md).
  Never open a public issue for a vulnerability.
- Discuss significant changes (new endpoints, schema changes, new planes)
  in an issue or ADR first. Architecture decisions are recorded in
  `docs/architecture/decisions.md`.

## Dev setup

```bash
cp .env.example .env   # fill in your local values; never commit .env
make dev               # docker compose up: postgres, redis, api, worker
```

To run the API locally against SQLite (no Docker):

```bash
make run-api
```

## Workflow

1. Fork and create a feature branch.
2. Run `make fmt` and `make lint` before committing. CI enforces ruff.
3. Add or update tests (`make test`). Behavior changes to the governance
   rail (policy, approvals, audit) require tests covering the fail-closed
   paths.
4. Open a PR against `main`. Keep it focused; large refactors should be
   split.

## Code conventions

- Python 3.12+, ruff for lint/format, type hints on all public functions.
- The monolith is organized into bounded packages under `src/acp/`; do not
  create new cross-package imports that bypass a package's public interface.
- Every state machine (task, approval, workflow execution) must enumerate
  states and transitions explicitly — no string-status soup.
- Fail closed: when in doubt about a governance decision, deny and escalate.
  Add a test proving the denial path.
- No secrets in code, tests, or fixtures. Use clearly fake placeholders
  (e.g. `test-key-000`).

## Docs

- User-facing behavior changes need docs updates (`docs/`).
- Architecture-decision records go in `docs/architecture/decisions.md`
  as numbered ADRs (see existing ADR-001… for format).

## License

By contributing you agree your contributions are licensed under the
Apache License 2.0.
