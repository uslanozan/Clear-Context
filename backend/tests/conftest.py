import ipaddress
import socket
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from clear_context.core.settings import PROJECT_ROOT, Settings


def migration_config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    config.attributes["database_path"] = database_path
    return config


@pytest.fixture(autouse=True)
def block_outbound_network(monkeypatch):
    original_connect = socket.socket.connect

    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not open network connections.")

    def local_connect(connection, address):
        # Windows event loops use a loopback socket pair for internal wakeups.
        if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
            return original_connect(connection, address)
        return blocked()

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", local_connect)


@pytest.fixture
def settings(tmp_path):
    database_path = tmp_path / "test.db"
    command.upgrade(migration_config(database_path), "head")
    return Settings(
        _env_file=None,
        database_path=database_path,
        meta_api_key="test-secret-never-expose",
        model_default="spark_1_3",
    )
