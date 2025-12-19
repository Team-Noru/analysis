import json
from utils.data import yyyymmdd_to_yyyy_mm_dd
from utils.sql import esc_sql
INPUT_JSON = "./output/announcements_all_tickers_major5.json"
OUTPUT_SQL = "./output/announcements_insert_all.sql"

def main():
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        rows = json.load(f)

    values = []
    for r in rows:
        company_id = str(r.get("company_id") or "")
        category = r.get("category")
        title = r.get("title")
        url = r.get("announcement_url")
        published_at = yyyymmdd_to_yyyy_mm_dd(r.get("published_at"))

        if not company_id or not title:
            continue

        values.append(
            f"({esc_sql(company_id)}, {esc_sql(category)}, {esc_sql(title)}, {esc_sql(url)}, {esc_sql(published_at)})"
        )

    sql = "INSERT INTO announcements (company_id, category, title, announcement_url, published_at)\nVALUES\n"
    sql += ",\n".join(values) + ";\n"

    with open(OUTPUT_SQL, "w", encoding="utf-8") as f:
        f.write(sql)

    print(f" {OUTPUT_SQL} (rows={len(values)})")

if __name__ == "__main__":
    main()
