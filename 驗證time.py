import os
from datetime import date, timedelta

DIR_PATH = r"C:\Huan_work\Taiwan Railway Travel Tools\data"
START_DATE = date(2026, 4, 5)
END_DATE = date(2026, 10, 2)


def check_missing_dates(dir_path, start_date, end_date):
    missing = []
    existing = []
    current = start_date
    while current <= end_date:
        filename = current.strftime("%Y%m%d") + ".json"
        full_path = os.path.join(dir_path, filename)
        if os.path.isfile(full_path):
            existing.append(filename)
        else:
            missing.append(filename)
        current += timedelta(days=1)
    return existing, missing


def main():
    total_days = (END_DATE - START_DATE).days + 1
    print("=" * 50)
    print(rf"📁 檢查路徑：{DIR_PATH}\time")
    print(
        f"📅 日期範圍：{START_DATE.strftime('%Y%m%d')} ～ {END_DATE.strftime('%Y%m%d')}"
    )
    print(f"📊 應有天數：{total_days} 天")
    print("=" * 50)
    existing, missing = check_missing_dates(rf"{DIR_PATH}\time", START_DATE, END_DATE)
    print(f"\n✅ 已存在檔案：{len(existing)} 個")
    print(f"❌ 缺少檔案：{len(missing)} 個")
    if missing:
        print("\n【缺少的日期檔案】")
        for f in missing:
            print(f"  ✗ {f}")
    else:
        print("\n🎉 所有日期檔案都存在，沒有缺漏！")
    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
