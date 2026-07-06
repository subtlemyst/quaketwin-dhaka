"""Initialize PostGIS schema (requires PostgreSQL + PostGIS)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SQL_PATH = ROOT / "data" / "schema" / "dhaka_graph.sql"


def main() -> None:
    import argparse

    from quaketwin.config import ProjectSettings

    parser = argparse.ArgumentParser(description="Apply QuakeTwin Dhaka PostGIS schema")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL only")
    args = parser.parse_args()

    sql = SQL_PATH.read_text(encoding="utf-8")
    if args.dry_run:
        print(sql)
        return

    try:
        from sqlalchemy import create_engine, text
    except ImportError as e:
        raise SystemExit("sqlalchemy required: pip install -e '.[dev]'") from e

    settings = ProjectSettings()
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(text(sql))
    print(f"Schema applied to {settings.database_url}")


if __name__ == "__main__":
    main()
