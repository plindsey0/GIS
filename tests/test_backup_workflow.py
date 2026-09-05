from pathlib import Path


def test_development_migration_requires_verified_backup_before_upgrade() -> None:
    script = Path("scripts/dev-migrate.sh").read_text()
    dump = script.index("pg_dump")
    nonempty = script.index('test -s "$backup_path"')
    verify = script.index("pg_restore --list")
    upgrade = script.index("alembic upgrade head")
    assert dump < nonempty < verify < upgrade
    assert "gis-pre-migration-" in script
    assert "NR > 20" in script


def test_restore_requires_archive_verification_confirmation_and_safety_backup() -> None:
    script = Path("scripts/dev-restore.sh").read_text()
    assert "pg_restore --list" in script
    assert "Type RESTORE gis" in script
    assert "gis-pre-restore-" in script
    assert script.index("pg_dump") < script.index("pg_restore --clean")
