"""Part 1: build teiko.db from cell-count.csv.

Run as `python load_data.py` from anywhere. Takes no arguments.
"""
from teiko.db import CSV_PATH, DB_PATH
from teiko.loading import build_database


def main() -> None:
    counts = build_database(DB_PATH, CSV_PATH)
    print(f"Built {DB_PATH.name} from {CSV_PATH.name}")
    for table, count in counts.items():
        print(f"  {table:<12} {count:>6,} rows")


if __name__ == "__main__":
    main()
