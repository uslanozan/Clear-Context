"""Copy existing local databases into the configured database directory.

Used to move a non-Docker `.local/` setup into the Docker volume. Run it while no
API process uses either side:

    python -m clear_context.db.import_local SOURCE_DATABASE [--replace]

The research cache is copied from `research.sqlite` beside the source database,
matching how the application locates it. Migrations run on the next API start.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from clear_context.core.settings import Settings, resolve_path

RESEARCH_DATABASE_NAME = "research.sqlite"


class ImportRefused(Exception):
    pass


def has_rows(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    connection = sqlite3.connect(path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
            )
        ]
        return any(
            connection.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() for table in tables
        )
    finally:
        connection.close()


def check_source_is_idle(path: Path) -> None:
    # A non-empty journal or WAL means a writer is active or did not shut down cleanly.
    for suffix in ("-journal", "-wal"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists() and sidecar.stat().st_size > 0:
            raise ImportRefused(
                f"{sidecar.name} is not empty. Stop the process using {path.name} and retry."
            )


def copy_database(source: Path, destination: Path) -> None:
    # immutable=1 reads without creating lock files, so a read-only mount works.
    reader = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    writer = sqlite3.connect(destination)
    try:
        reader.backup(writer)
    finally:
        writer.close()
        reader.close()


def import_databases(source: Path, destination: Path, replace: bool = False) -> list[str]:
    if not source.is_file():
        raise ImportRefused(f"Source database not found: {source}")
    if source.resolve() == destination.resolve():
        raise ImportRefused("Source and destination are the same file.")

    pairs = [(source, destination)]
    research_source = source.with_name(RESEARCH_DATABASE_NAME)
    if research_source.is_file():
        pairs.append((research_source, destination.with_name(RESEARCH_DATABASE_NAME)))

    for source_path, destination_path in pairs:
        check_source_is_idle(source_path)
        if not replace and has_rows(destination_path):
            raise ImportRefused(
                f"{destination_path} already contains data. Use --replace to overwrite it."
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    copied = []
    for source_path, destination_path in pairs:
        copy_database(source_path, destination_path)
        copied.append(f"{source_path.name} -> {destination_path}")
    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="Path to an existing clear-context.db")
    parser.add_argument(
        "--replace", action="store_true", help="Overwrite destination databases that hold data"
    )
    arguments = parser.parse_args(argv)
    destination = resolve_path(Settings().database_path)
    try:
        copied = import_databases(arguments.source, destination, arguments.replace)
    except ImportRefused as error:
        print(f"Import refused: {error}", file=sys.stderr)
        return 1
    for line in copied:
        print(f"Copied {line}")
    print("Start the API to apply any pending migrations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
