"""Shared fixtures.

`db` tests get a throwaway Postgres (same image as the local Supabase stack), migrated by the real Flyway
image, so they never touch your data. Each test runs inside a transaction that is rolled back.
"""
import subprocess
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

MIGRATIONS = Path(__file__).resolve().parents[1] / "db" / "migration"
# Keep in sync with docker-compose.yml (flyway) and the Supabase CLI's Postgres image.
FLYWAY_IMAGE = "flyway/flyway:11.3.4"
POSTGRES_IMAGE = "public.ecr.aws/supabase/postgres:17.6.1.106"


def run_flyway(port: int, command: str = "migrate") -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
            "-v", f"{MIGRATIONS}:/flyway/sql:ro", FLYWAY_IMAGE,
            f"-url=jdbc:postgresql://host.docker.internal:{port}/postgres",
            "-user=postgres", "-password=postgres", "-locations=filesystem:/flyway/sql",
            "-schemas=public", "-validateMigrationNaming=true", command,
        ],
        capture_output=True, text=True, timeout=300,
    )


def _wait_for_login(url: str, seconds: int = 90) -> None:
    """The Supabase image creates the `postgres` role in its own start-up scripts, after the server is up."""
    import psycopg

    deadline = time.monotonic() + seconds
    while True:
        try:
            psycopg.connect(url, connect_timeout=3).close()
            return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


@pytest.fixture(scope="session")
def pg_engine():
    from testcontainers.community.postgres import PostgresContainer

    # The Supabase image's start-up scripts log in as supabase_admin, so that has to be the container's main user.
    # The app and Flyway then use `postgres` (not a superuser, but BYPASSRLS), exactly like the CLI stack.
    with PostgresContainer(POSTGRES_IMAGE, username="supabase_admin", password="postgres", dbname="postgres",
                           driver="psycopg") as pg:
        host, port = pg.get_container_host_ip(), int(pg.get_exposed_port(5432))
        _wait_for_login(f"postgresql://postgres:postgres@{host}:{port}/postgres")
        result = run_flyway(port)
        if result.returncode != 0:
            pytest.fail(f"flyway migrate failed:\n{result.stdout}\n{result.stderr}")
        engine = create_engine(f"postgresql+psycopg://postgres:postgres@{host}:{port}/postgres")
        yield engine
        engine.dispose()


@pytest.fixture
def db_session(pg_engine):
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
