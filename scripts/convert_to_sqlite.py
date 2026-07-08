"""
Converts the raw Criteo dataset file(s) in data/raw/ into a single
SQLite database at data/criteo.db, so Claude Code can query it via
an MCP SQLite server.
"""
import sqlite3
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "criteo.db"
TABLE_NAME = "impressions"
READ_KWARGS = {"sep": "\t"}


def find_data_file() -> Path:
    candidates = sorted(RAW_DIR.glob("*"))
    if not candidates:
        raise FileNotFoundError(f"No files found in {RAW_DIR}.")
    data_files = [
        f for f in candidates
        if f.suffix in (".csv", ".tsv", ".gz") or f.name.endswith(".tsv.gz")
    ]
    return data_files[0] if data_files else candidates[0]


def main():
    source = find_data_file()
    print(f"Reading: {source}")

    df = pd.read_csv(source, **READ_KWARGS)
    print(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        cur = conn.cursor()
        for col in ("click", "conversion", "cost"):
            if col in df.columns:
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{col} ON {TABLE_NAME}({col})")
        conn.commit()

    print(f"Wrote table '{TABLE_NAME}' to {DB_PATH}")


if __name__ == "__main__":
    main()
