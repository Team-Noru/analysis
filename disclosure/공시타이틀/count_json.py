# json 몇 개 있는지 확인
import json

INPUT_JSON = "./output/announcements_all_tickers_major5.json"

def main():
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"announcements count: {len(data)}")

if __name__ == "__main__":
    main()
