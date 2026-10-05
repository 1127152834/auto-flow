"""Saved environments become identities; records link to identities (remediation M4 R4-10).

Each live saved environment gets one identity that keeps the seed, timezone and locale frozen in
the environment's own identity package (never re-derived from today's profile). Environments that
share a seed share one registration marked legacy_shared, which the seed report lists; nothing is
re-generated. An environment without an identity package gets a new seed and says so in origin.
"""

import json
import secrets
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "rm4_record_identity"
down_revision = "rm4_identities"
branch_labels = None
depends_on = None

SEED_MIN, SEED_MAX = 10_000, 2**31 - 1


def upgrade() -> None:
    # Plain ALTER TABLE: a batch rebuild of project_data_records would drop its M3 expression indexes.
    op.add_column("identities", sa.Column("origin", sa.JSON()))
    op.add_column("project_data_records", sa.Column("current_identity_id", sa.String(36)))
    connection = op.get_bind()
    now = datetime.now(UTC).isoformat()
    registry: dict[int, str] = {
        int(seed): str(registry_id)
        for registry_id, seed in connection.execute(sa.text("SELECT id, seed_value FROM seed_registry"))
    }
    names = {
        (str(project), str(key)) for project, key in connection.execute(sa.text("SELECT project_id, name_key FROM identities"))
    }
    used = {
        str(registry_id) for (registry_id,) in connection.execute(sa.text("SELECT DISTINCT seed_id FROM identities"))
    }
    environments = connection.execute(sa.text(
        "SELECT id, project_id, name, profile_id, identity_package FROM project_environments "
        "WHERE state != 'deleted' AND id NOT IN (SELECT environment_id FROM identities WHERE environment_id IS NOT NULL) "
        "ORDER BY created_at, id"
    )).all()
    for environment_id, project_id, name, profile_id, raw_package in environments:
        package = _json(raw_package)
        frozen = package.get("frozenConfiguration") if isinstance(package.get("frozenConfiguration"), dict) else {}
        spec = frozen.get("profileSpec") if isinstance(frozen.get("profileSpec"), dict) else {}
        seed = frozen.get("fingerprintSeed")
        missing = not (type(seed) is int and SEED_MIN <= seed <= SEED_MAX)
        if missing:
            seed = _fresh_seed(registry)
        if seed in registry:
            registry_id = registry[seed]
            if registry_id in used:
                connection.execute(sa.text("UPDATE seed_registry SET legacy_shared = 1 WHERE id = :id"), {"id": registry_id})
        else:
            registry_id = str(uuid4())
            connection.execute(
                sa.text("INSERT INTO seed_registry (id, seed_value, legacy_shared, created_at) VALUES (:id, :seed, 0, :now)"),
                {"id": registry_id, "seed": seed, "now": now},
            )
            registry[seed] = registry_id
        used.add(registry_id)
        identity_name = name
        suffix = 1
        while (project_id, identity_name.casefold()) in names:
            identity_name = f"{name}（环境）" if suffix == 1 else f"{name}（环境 {suffix}）"
            suffix += 1
        names.add((project_id, identity_name.casefold()))
        region = {key: spec[key] for key in ("timezone", "locale") if isinstance(spec.get(key), str) and spec[key]}
        connection.execute(
            sa.text(
                "INSERT INTO identities (id, project_id, name, name_key, template_profile_id, seed_id, region, proxy_binding, "
                "environment_id, health, origin, created_at, updated_at) VALUES (:id, :project, :name, :key, :profile, :seed, "
                ":region, NULL, :environment, :health, :origin, :now, :now)"
            ),
            {
                "id": str(uuid4()), "project": project_id, "name": identity_name, "key": identity_name.casefold(), "profile": profile_id,
                "seed": registry_id, "region": json.dumps(region, ensure_ascii=False), "environment": environment_id,
                "health": json.dumps({"lastLoginSuccessAt": None, "consecutiveFailures": 0, "banned": False}),
                "origin": json.dumps({"environmentId": environment_id, "seedMissing": missing}), "now": now,
            },
        )
    connection.execute(sa.text(
        "UPDATE project_data_records SET current_identity_id = "
        "(SELECT i.id FROM identities i WHERE i.environment_id = project_data_records.current_environment_id) "
        "WHERE current_environment_id IS NOT NULL"
    ))


def downgrade() -> None:
    # SQLite >= 3.35 drops an unindexed column in place, keeping the table's other indexes.
    op.drop_column("project_data_records", "current_identity_id")
    op.drop_column("identities", "origin")


def _json(value: object) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fresh_seed(registry: dict[int, str]) -> int:
    while True:
        seed = SEED_MIN + secrets.randbelow(SEED_MAX - SEED_MIN + 1)
        if seed not in registry:
            return seed
