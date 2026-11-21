"""SQLite storage: ordered migrations and the saved-routes store."""

import contextlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_NAME = "routes.sqlite3"

MIGRATIONS = [
    (
        1,
        [
            """CREATE TABLE routes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 80),
  title_key TEXT NOT NULL UNIQUE,
  from_id TEXT NOT NULL, to_id TEXT NOT NULL,
  distance_m INTEGER NOT NULL CHECK(distance_m >= 0),
  path_json TEXT NOT NULL, steps_json TEXT NOT NULL,
  graph_id TEXT NOT NULL,
  created_at TEXT NOT NULL)""",
        ],
    ),
]


class StoreError(Exception):
    """Data directory or database cannot be used."""


class TitleExists(Exception):
    pass


def prepare_data_dir(data_dir):
    """Validate/create the data dir; return the DB file path. Raises StoreError."""
    if not isinstance(data_dir, (str, os.PathLike)):
        raise StoreError("data directory is required")
    text = os.fspath(data_dir)
    if not isinstance(text, str) or not text.strip() or "\x00" in text:
        raise StoreError("data directory is empty or invalid")
    if os.path.exists(text) and not os.path.isdir(text):
        raise StoreError(f"data directory is not a directory: {text}")
    try:
        os.makedirs(text, exist_ok=True)
    except (OSError, ValueError) as exc:
        raise StoreError(f"cannot create data directory {text}: {exc}") from exc
    return os.path.join(text, DB_NAME)


def _connect(db_path):
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        conn.close()
        raise
    return conn


def apply_migrations(conn, migrations=MIGRATIONS):
    """Apply missing migrations in one transaction; return the schema version.

    `conn` must be in autocommit mode (isolation_level=None). On any failure
    everything is rolled back, so a half-migrated database is never left.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY)"
        )
        applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        known = {v for v, _ in migrations}
        unknown = applied - known
        if unknown:
            raise StoreError(
                f"database schema version {max(unknown)} is newer than this program"
            )
        for version, statements in sorted(migrations, key=lambda m: m[0]):
            if version in applied:
                continue
            for sql in statements:
                conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        current = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        conn.execute("COMMIT")
        return current or 0
    except BaseException:
        with contextlib.suppress(sqlite3.Error):
            conn.execute("ROLLBACK")
        raise


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _full(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "from": row["from_id"],
        "to": row["to_id"],
        "distance_m": row["distance_m"],
        "path": json.loads(row["path_json"]),
        "steps": json.loads(row["steps_json"]),
        "graph_id": row["graph_id"],
        "created_at": row["created_at"],
    }


class Store:
    """Opens one short-lived SQLite connection per operation."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.schema_version = 0

    def open(self):
        """Create/upgrade the database. Raises StoreError on any DB failure."""
        try:
            with contextlib.closing(_connect(self.db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                self.schema_version = apply_migrations(conn)
        except sqlite3.Error as exc:
            raise StoreError(f"cannot open database {self.db_path}: {exc}") from exc
        return self

    def close(self):
        """No persistent connections are held; kept for lifecycle symmetry."""

    def save_route(self, title, route, graph_id):
        """Insert a route; raise TitleExists on a case-insensitive duplicate."""
        created = utc_now()
        try:
            with contextlib.closing(_connect(self.db_path)) as conn:
                cur = conn.execute(
                    "INSERT INTO routes(title, title_key, from_id, to_id, distance_m,"
                    " path_json, steps_json, graph_id, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        title,
                        title.casefold(),
                        route["from"],
                        route["to"],
                        route["distance_m"],
                        json.dumps(route["path"]),
                        json.dumps(route["steps"]),
                        graph_id,
                        created,
                    ),
                )
                new_id = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            if "title_key" in str(exc):
                raise TitleExists(title) from exc
            raise
        return {
            "id": new_id,
            "title": title,
            "from": route["from"],
            "to": route["to"],
            "distance_m": route["distance_m"],
            "path": list(route["path"]),
            "steps": list(route["steps"]),
            "graph_id": graph_id,
            "created_at": created,
        }

    def list_routes(self):
        with contextlib.closing(_connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT id, title, from_id, to_id, distance_m, created_at"
                " FROM routes ORDER BY id DESC"
            ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "from": r["from_id"],
                "to": r["to_id"],
                "distance_m": r["distance_m"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_route(self, route_id):
        """Return the full route dict or None."""
        with contextlib.closing(_connect(self.db_path)) as conn:
            row = conn.execute("SELECT * FROM routes WHERE id = ?", (route_id,)).fetchone()
        return _full(row) if row else None
