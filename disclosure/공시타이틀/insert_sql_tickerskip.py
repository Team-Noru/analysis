import os
import json
from datetime import datetime
from typing import List, Dict, Any
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

load_dotenv()
INPUT_JSON = "./output/announcements_all_tickers_major5.json"
SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT"))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")
REMOTE_DB_HOST = os.getenv("REMOTE_DB_HOST")
REMOTE_DB_PORT = int(os.getenv("REMOTE_DB_PORT"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

from utils.data import yyyymmdd_to_yyyy_mm_dd
from utils.data import chunked




def main():
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        rows: List[Dict[str, Any]] = json.load(f)

    tickers_in_json = sorted({str(r.get("company_id") or "").strip() for r in rows if r.get("company_id")})
    tickers_in_json = [t for t in tickers_in_json if t]

    with SSHTunnelForwarder(
        (SSH_HOST, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_pkey=SSH_KEY_PATH,
        remote_bind_address=(REMOTE_DB_HOST, REMOTE_DB_PORT),
        local_bind_address=("127.0.0.1", 0),  
    ) as tunnel:
        local_port = tunnel.local_bind_port
        
        conn = pymysql.connect(
            host="127.0.0.1",
            port=local_port,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

        try:
            with conn.cursor() as cur:
                existing_tickers = set()
                for part in chunked(tickers_in_json, 800):
                    placeholders = ",".join(["%s"] * len(part))
                    sql = f"""
                        SELECT DISTINCT company_id
                        FROM announcements
                        WHERE company_id IN ({placeholders})
                    """
                    cur.execute(sql, part)
                    for r in cur.fetchall():
                        existing_tickers.add(str(r["company_id"]))

                skip_tickers = existing_tickers
                insert_tickers = set(tickers_in_json) - skip_tickers

                rows_to_insert = []
                skipped_rows = 0

                for r in rows:
                    company_id = str(r.get("company_id") or "").strip()
                    if not company_id:
                        continue
                    if company_id in skip_tickers:
                        skipped_rows += 1
                        continue

                    title = (r.get("title") or "").strip()
                    if not title:
                        continue

                    rows_to_insert.append((
                        company_id,
                        (r.get("category") or None),
                        title,
                        (r.get("announcement_url") or None),
                        yyyymmdd_to_yyyy_mm_dd(r.get("published_at")),
                    ))

                print(f"새로 넣을 ticker 수: {len(insert_tickers)}")
                print(f"insert 예정 rows 수: {len(rows_to_insert)}")

                if not rows_to_insert:
                    print("insert할 데이터 X")
                    return

                insert_sql = """
                    INSERT INTO announcements
                        (company_id, category, title, announcement_url, published_at)
                    VALUES
                        (%s, %s, %s, %s, %s)
                """

                total_inserted = 0
                for part in chunked(rows_to_insert, 1000):
                    cur.executemany(insert_sql, part)
                    total_inserted += cur.rowcount

                conn.commit()
                print(f"INSERT rows: {total_inserted}")

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

if __name__ == "__main__":
    main()
