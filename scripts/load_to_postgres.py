"""
One-time load: CSV files -> Postgres. Idempotent -- TRUNCATE + reload each table,
safe to re-run after a data refresh.

    python -m scripts.load_to_postgres
"""
import csv
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.config import DATA_DIR, DATABASE_URL  # noqa: E402

TABLES = {
    "audit.accounts": "d1_account_master_thin.csv",
    "audit.contact_log": "d4_contact_history.csv",
    "audit.transcripts": "d5_call_transcripts.csv",
    "audit.consent": "d10_consent_registry.csv",
    "audit.templates": "d11_template_registry.csv",
    "audit.policy": "d12_policy_rules.csv",
    "audit.notices": "notice_dispatch_history.csv",
    "audit.holidays": "holiday_calendar.csv",
    "audit.roster": "collector_roster.csv",
    "audit.certificates": "certification_register.csv",
    "audit.guidelines": "rbi_guidelines.csv",
    "audit.caller_numbers": "caller_numbers.csv",
    "audit.message_content": "message_content.csv",
    "audit.call_conduct_log": "call_conduct_log.csv",
    "audit.field_visits": "field_visits.csv",
    "audit.closures": "closures.csv",
    "audit.penal_charges": "penal_charges.csv",
}


def load_table(conn, table: str, csv_path: Path) -> int:
    with open(csv_path) as f:
        header = next(csv.reader(f))
    cols = ", ".join(header)
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {table}")
        with cur.copy(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')") as copy:
            with open(csv_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    copy.write(chunk)
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()["count"]


def main():
    print(f"Connecting to {DATABASE_URL}")
    with psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row) as conn:
        for table, filename in TABLES.items():
            path = DATA_DIR / filename
            n = load_table(conn, table, path)
            print(f"  {table:<24} <- {filename:<32} {n:>7} rows")
        conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
