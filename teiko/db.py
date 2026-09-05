"""Database paths, connections, and bootstrap."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "teiko.db"
CSV_PATH = ROOT / "cell-count.csv"
SCHEMA_PATH = ROOT / "schema.sql"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    # SQLite does not persist foreign_keys in the file; it is per connection.
    # Every connection in this project comes from here so the constraints hold.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def ensure_database(
    db_path: Path = DB_PATH, csv_path: Path = CSV_PATH
) -> sqlite3.Connection:
    """Open the database, building it first if it does not exist."""
    if not Path(db_path).exists():
        from teiko.loading import build_database

        build_database(Path(db_path), Path(csv_path))
    return connect(db_path)
