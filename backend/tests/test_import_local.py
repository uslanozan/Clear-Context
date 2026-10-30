import sqlite3

import pytest

from clear_context.db.import_local import ImportRefused, import_databases


def make_database(path, rows=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE items (value TEXT)")
    connection.executemany("INSERT INTO items VALUES (?)", [(f"row {i}",) for i in range(rows)])
    connection.commit()
    connection.close()


def row_count(path):
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    finally:
        connection.close()


def test_copies_main_and_research_databases(tmp_path):
    make_database(tmp_path / "source" / "clear-context.db", rows=2)
    make_database(tmp_path / "source" / "research.sqlite", rows=3)
    destination = tmp_path / "volume" / "clear-context.db"

    copied = import_databases(tmp_path / "source" / "clear-context.db", destination)

    assert len(copied) == 2
    assert row_count(destination) == 2
    assert row_count(destination.with_name("research.sqlite")) == 3


def test_refuses_to_overwrite_existing_data_without_replace(tmp_path):
    make_database(tmp_path / "source" / "clear-context.db", rows=2)
    destination = tmp_path / "volume" / "clear-context.db"
    make_database(destination, rows=5)

    with pytest.raises(ImportRefused, match="already contains data"):
        import_databases(tmp_path / "source" / "clear-context.db", destination)
    assert row_count(destination) == 5

    import_databases(tmp_path / "source" / "clear-context.db", destination, replace=True)
    assert row_count(destination) == 2


def test_allows_a_freshly_migrated_empty_destination(tmp_path):
    make_database(tmp_path / "source" / "clear-context.db", rows=1)
    destination = tmp_path / "volume" / "clear-context.db"
    make_database(destination, rows=0)

    import_databases(tmp_path / "source" / "clear-context.db", destination)
    assert row_count(destination) == 1


def test_refuses_a_source_with_a_pending_journal(tmp_path):
    source = tmp_path / "source" / "clear-context.db"
    make_database(source)
    source.with_name("clear-context.db-journal").write_bytes(b"pending")

    with pytest.raises(ImportRefused, match="not empty"):
        import_databases(source, tmp_path / "volume" / "clear-context.db")
