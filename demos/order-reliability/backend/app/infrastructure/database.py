import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ENTITY_TABLES = (
    "orders",
    "inventory",
    "reservations",
    "create_journal",
    "mutation_fences",
    "recovery_tasks",
    "terminal_receipts",
    "events",
    "fault_plans",
)
PROVIDER_TABLES = ("crm_orders", "crm_inventory", "crm_calls")


class Database:
    """Short transactions on fresh connections; no transaction crosses the provider boundary."""

    def __init__(self, path: Path, schema: str = "schema.sql") -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.executescript(Path(__file__).with_name(schema).read_text())

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def rows(self, query: str, parameters: tuple = ()) -> list[dict]:
        with self.transaction() as connection:
            return [dict(row) for row in connection.execute(query, parameters)]

    def clear(self, tables: tuple[str, ...]) -> None:
        with self.transaction() as connection:
            for table in reversed(tables):
                if table not in ENTITY_TABLES + PROVIDER_TABLES:
                    raise ValueError("Unknown reset table")
                connection.execute(f"DELETE FROM {table}")
