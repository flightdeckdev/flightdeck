"""Read-only workspace health checks (`flightdeck doctor`)."""

from __future__ import annotations

from dataclasses import dataclass

from flightdeck.storage import LATEST_SCHEMA_MIGRATION_VERSION, Storage


@dataclass(frozen=True)
class DoctorCheck:
    """One named check; `ok` is True when the ledger looks consistent."""

    name: str
    ok: bool
    detail: str


def run_doctor(storage: Storage) -> list[DoctorCheck]:
    """
    Run local integrity checks. Mutates nothing beyond what `migrate()` does
    (idempotent schema/index application).
    """
    storage.migrate()
    checks: list[DoctorCheck] = []

    applied = set(storage.list_applied_migrations())
    expected = set(range(1, LATEST_SCHEMA_MIGRATION_VERSION + 1))
    missing = sorted(expected - applied)
    checks.append(
        DoctorCheck(
            name="schema_migrations",
            ok=len(missing) == 0,
            detail=(
                f"applied={sorted(applied)} expected 1..{LATEST_SCHEMA_MIGRATION_VERSION}"
                if not missing
                else f"missing migration versions: {missing} (applied={sorted(applied)})"
            ),
        )
    )

    for agent_id, environment, release_id in storage.list_promoted_pointers():
        row = storage.get_release(release_id)
        checks.append(
            DoctorCheck(
                name=f"promoted_pointer:{agent_id}:{environment}",
                ok=row is not None,
                detail=(
                    f"release_id={release_id} ok"
                    if row is not None
                    else f"release_id={release_id!r} missing from releases table"
                ),
            )
        )

    ok, detail = storage.check_release_actions_audit_seq()
    checks.append(DoctorCheck(name="audit_seq", ok=ok, detail=detail))

    return checks
