import json
import re
from pathlib import Path
INPUT_DIR = "./wordcloud_out"
OUTPUT_SQL = "./output/word_clouds_insert.sql"

# 파일명에서 "정확히 6자리 숫자"만 추출 (000270 같은 코드)
CODE6_REGEX = re.compile(r"(?<!\d)(\d{6})(?!\d)")

def esc_sql_str(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"

def esc_sql_int(n) -> str:
    if n is None or n == "":
        return "NULL"
    try:
        return str(int(n))
    except Exception:
        return "NULL"

def extract_code6(filename: str) -> str | None:
    m = CODE6_REGEX.search(filename)
    if not m:
        return None
    return m.group(1) 
def main():
    input_path = Path(INPUT_DIR)
    out_path = Path(OUTPUT_SQL)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    values = []
    skipped_files = 0
    total_files = 0

    for file_path in input_path.rglob("*_final.json"):
        total_files += 1
        fname = file_path.name
        company_id = extract_code6(fname)

        if company_id is None:
            skipped_files += 1
            print(f"6자리 종목코드 못찾음 → skip: {fname}")
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                rows = json.load(f)
        except Exception as e:
            skipped_files += 1
            print(f"JSON 로드 실패 → skip: {fname} ({e})")
            continue

        if not isinstance(rows, list):
            skipped_files += 1
            print(f"JSON 형식이 list가 아님 → skip: {fname}")
            continue

        for r in rows:
            text = r.get("text")
            weight = r.get("weight")
            wtype = r.get("type")  # 없으면 NULL

            if not text or weight is None:
                continue

            # company_id는 문자열로 넣기 (ex 6자리 코드)
            values.append(
                f"({esc_sql_str(text)}, {esc_sql_int(weight)}, {esc_sql_str(wtype)}, {esc_sql_str(company_id)})"
            )

    if not values:
        print("생성할 데이터가 없음. _final.json 경로/형식을 확인해줘.")
        return

    sql = []
    sql.append("-- auto-generated SQL for word_clouds")
    sql.append("-- source: wordcloud_out/*_final.json")
    sql.append("")
    sql.append("INSERT INTO word_clouds (text, weight, type, company_id)")
    sql.append("VALUES")
    sql.append(",\n".join(values) + ";")
    sql.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sql))

    print(f"wrote: {out_path} (files={total_files}, skipped_files={skipped_files}, rows={len(values)})")

if __name__ == "__main__":
    main()
