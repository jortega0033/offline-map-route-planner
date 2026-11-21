import contextlib
import os
import io
import sqlite3
import tempfile
import unittest

from offline_routes import store
from offline_routes.server import create_server, main


def sample_route():
    return {
        "from": "depot",
        "to": "observatory",
        "distance_m": 120,
        "path": ["depot", "library", "observatory"],
        "steps": ["a", "b"],
    }


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name


class MigrationTests(TmpCase):
    def test_open_twice_is_noop(self):
        path = store.prepare_data_dir(self.dir)
        s = store.Store(path).open()
        s.save_route("Keep me", sample_route(), "fixture-v1")
        s2 = store.Store(path).open()
        self.assertEqual(s2.schema_version, 1)
        self.assertEqual(len(s2.list_routes()), 1)
        conn = sqlite3.connect(path)
        try:
            self.assertEqual(conn.execute("SELECT version FROM schema_migrations").fetchall(), [(1,)])
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        finally:
            conn.close()

    def test_failed_migration_rolls_back_everything(self):
        conn = sqlite3.connect(os.path.join(self.dir, "x.db"), isolation_level=None)
        try:
            bad = [(1, ["CREATE TABLE t(a)"]), (2, ["CREATE TABLE broken("])]
            with self.assertRaises(sqlite3.Error):
                store.apply_migrations(conn, bad)
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            self.assertNotIn("t", tables)
            # Recoverable: a corrected list now applies cleanly.
            self.assertEqual(store.apply_migrations(conn, bad[:1]), 1)
            self.assertEqual(store.apply_migrations(conn, bad[:1]), 1)
        finally:
            conn.close()

    def test_newer_schema_refused(self):
        path = os.path.join(self.dir, store.DB_NAME)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_migrations VALUES (99)")
        conn.commit()
        conn.close()
        with self.assertRaises(store.StoreError):
            store.Store(path).open()

    def test_corrupt_db_is_store_error(self):
        path = os.path.join(self.dir, store.DB_NAME)
        with open(path, "wb") as f:
            f.write(b"this is not a sqlite database" * 50)
        with self.assertRaises(store.StoreError):
            store.Store(path).open()


class StoreTests(TmpCase):
    def setUp(self):
        super().setUp()
        self.s = store.Store(store.prepare_data_dir(self.dir)).open()

    def test_save_get_list(self):
        a = self.s.save_route("First", sample_route(), "fixture-v1")
        b = self.s.save_route("Second", sample_route(), "fixture-v1")
        self.assertEqual((a["id"], b["id"]), (1, 2))
        self.assertEqual([r["id"] for r in self.s.list_routes()], [2, 1])
        self.assertEqual(self.s.get_route(1), a)
        self.assertIsNone(self.s.get_route(999))
        self.assertRegex(a["created_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_duplicate_title_case_insensitive(self):
        self.s.save_route("Morning Run", sample_route(), "fixture-v1")
        for t in ("morning run", "MORNING RUN", "Morning Run"):
            with self.assertRaises(store.TitleExists):
                self.s.save_route(t, sample_route(), "fixture-v1")
        self.s.save_route("Straße", sample_route(), "fixture-v1")
        with self.assertRaises(store.TitleExists):
            self.s.save_route("STRASSE", sample_route(), "fixture-v1")
        self.assertEqual(len(self.s.list_routes()), 2)

    def test_db_rejects_bad_rows(self):
        conn = sqlite3.connect(self.s.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO routes(title,title_key,from_id,to_id,distance_m,path_json,"
                    "steps_json,graph_id,created_at) VALUES ('x'||printf('%100s',''),'k','a','b',1,'[]','[]','g','t')"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO routes(title,title_key,from_id,to_id,distance_m,path_json,"
                    "steps_json,graph_id,created_at) VALUES ('x','k','a','b',-1,'[]','[]','g','t')"
                )
        finally:
            conn.close()


class DataDirTests(TmpCase):
    def test_empty_and_blank(self):
        for bad in ("", "   "):
            with self.assertRaises(store.StoreError):
                store.prepare_data_dir(bad)

    def test_path_is_file(self):
        p = os.path.join(self.dir, "afile")
        with open(p, "w") as f:
            f.write("x")
        with self.assertRaises(store.StoreError):
            store.prepare_data_dir(p)

    def test_uncreatable_under_file(self):
        p = os.path.join(self.dir, "afile")
        with open(p, "w") as f:
            f.write("x")
        with self.assertRaises(store.StoreError):
            store.prepare_data_dir(os.path.join(p, "sub"))

    def test_missing_nested_dir_created(self):
        target = os.path.join(self.dir, "a", "b")
        path = store.prepare_data_dir(target)
        self.assertTrue(os.path.isdir(target))
        self.assertEqual(path, os.path.join(target, "routes.sqlite3"))

    def test_db_path_is_directory(self):
        os.mkdir(os.path.join(self.dir, store.DB_NAME))
        with self.assertRaises(store.StoreError):
            create_server(self.dir, 0)

    def test_main_exit_code_2(self):
        afile = os.path.join(self.dir, "afile")
        with open(afile, "w") as f:
            f.write("x")
        for args in (
            ["--data-dir", "", "--port", "0"],
            ["--data-dir", afile, "--port", "0"],
            ["--data-dir", os.path.join(afile, "sub"), "--port", "0"],
        ):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(main(args), 2, args)
            self.assertTrue(err.getvalue().startswith("error:"))
            self.assertEqual(len(err.getvalue().strip().splitlines()), 1)

    def test_main_bad_args_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main(["--data-dir", self.dir, "--port", "99999"])
            self.assertEqual(cm.exception.code, 2)
            with self.assertRaises(SystemExit) as cm:
                main(["--port", "0"])
            self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
