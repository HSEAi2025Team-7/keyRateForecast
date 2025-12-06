import os
import json
import csv

folder_path = "/Users/polinakokova/Desktop/HSE/keyRateForecastNew/data/raw/cbr_press"

output_csv = os.path.join(folder_path, "press_releases.csv")

fields = ["date", "title", "text", "url"]

rows = []

for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        file_path = os.path.join(folder_path, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)


                row = {key: data.get(key, "") for key in fields}
                rows.append(row)

        except json.JSONDecodeError:
            print(f"⚠️ Ошибка чтения JSON: {filename}")
        except Exception as e:
            print(f"⚠️ Ошибка в файле {filename}: {e}")


with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Готово! Создан файл: {output_csv}")
print(f"Всего собрано записей: {len(rows)}")
