"""Load the KBO Open Data full extract and apply daily updates into DuckDB.

Contract (from phase 1): updates are applied in order and never twice, via an
extract log; gaps raise a warning; an update deletes the listed keys, then inserts.

A full extract has one CSV per table (enterprise.csv, activity.csv, ...).
An update has <table>_delete.csv (one key column) and <table>_insert.csv.
Both carry meta.csv with ExtractNumber. Input is the .zip or an unpacked folder.
"""

import tempfile
import warnings
import zipfile
from contextlib import contextmanager
from pathlib import Path

import duckdb

# Only these files are loaded; anything else in the folder is ignored.
KBO_TABLES = ("meta", "code", "enterprise", "establishment", "denomination", "address", "contact", "activity", "branch")


@contextmanager
def _unpacked(path):
    path = Path(path)
    if path.is_dir():
        yield path
        return
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(path).extractall(tmp)
        yield Path(tmp)


@contextmanager
def _transaction(con):
    con.execute("BEGIN")
    try:
        yield
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")


def _csv(path):
    path = str(path).replace("'", "''")
    return f"read_csv('{path}', header=true, all_varchar=true)"


def _extract_number(folder):
    rows = duckdb.sql(f"SELECT Variable, Value FROM {_csv(folder / 'meta.csv')}").fetchall()
    return int(dict(rows)["ExtractNumber"])


def last_applied(con):
    try:
        return con.execute("SELECT max(extract_number) FROM extract_log").fetchone()[0]
    except duckdb.CatalogException:
        return None


def load_full(con, path):
    """Replace all tables with a full extract and restart the extract log."""
    with _unpacked(path) as folder:
        number = _extract_number(folder)
        with _transaction(con):
            for name in KBO_TABLES:
                if (f := folder / f"{name}.csv").exists():
                    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM {_csv(f)}")
            con.execute("CREATE OR REPLACE TABLE extract_log (extract_number INTEGER, kind VARCHAR, applied_at TIMESTAMP)")
            con.execute("INSERT INTO extract_log VALUES (?, 'full', now())", [number])
    return number


def apply_update(con, path):
    """Apply one daily update. Returns False if it was already applied (or older)."""
    with _unpacked(path) as folder:
        number = _extract_number(folder)
        last = last_applied(con)
        if last is None:
            raise RuntimeError("Load a full extract first.")
        if number <= last:
            return False
        if number != last + 1:
            warnings.warn(f"Gap in KBO updates: last applied {last}, now {number}.")
        with _transaction(con):
            for f in sorted(folder.glob("*_delete.csv")):
                table = f.stem.removesuffix("_delete")
                key = duckdb.sql(f"SELECT * FROM {_csv(f)} LIMIT 0").columns[0]
                con.execute(f"DELETE FROM {table} WHERE {key} IN (SELECT {key} FROM {_csv(f)})")
            for f in sorted(folder.glob("*_insert.csv")):
                table = f.stem.removesuffix("_insert")
                con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM {_csv(f)}")
            con.execute("INSERT INTO extract_log VALUES (?, 'update', now())", [number])
    return True


def apply_updates(con, paths):
    """Apply several updates in extract-number order, whatever order they are given in."""
    def number(p):
        with _unpacked(p) as folder:
            return _extract_number(folder)
    return [apply_update(con, p) for p in sorted(paths, key=number)]
