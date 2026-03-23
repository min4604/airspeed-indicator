import csv
import json

def csv_to_json(csv_path, json_path):
    """
    將協定定義的 CSV 檔轉換為 JSON 結構。

    Args:
        csv_path (str): 輸入的 CSV 檔案路徑
        json_path (str): 輸出的 JSON 檔案路徑
    """
    # 固定協定設定
    protocol = {
        "header": [2, 0],
        "length_index": 2,
        "data_offset": 3
    }

    fields = []

    with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = list(csv.reader(csvfile))

        # 第一列: 標題(header, length, data0...dataN)
        # 第二列: 各欄位名稱 (HIDS_Temp、PADS_pressure...)
        # 第三列: MSB/LSB 資訊
        headers = reader[0]
        names = reader[2]
        msb_lsb = reader[3]
        unit_raw = reader[4]
        
        # 根據名稱列逐欄分析
        for i, name in enumerate(names):
            if name and name not in ["NAME", "length"]:
                offset = i - 1
                byte_order = msb_lsb[i].lower()

                # 判斷此欄是否有連續多位元資料（例如 MSB+LSB）
                length = 1
                if i + 1 < len(names) and names[i + 1] == name:
                    length = 2

                # 根據欄名
                unit = unit_raw[i]

                # 避免重複名稱（只保留一次）
                if any(f["name"] == name for f in fields):
                    continue

                fields.append({
                    "name": name,
                    "offset": offset,
                    "length": length,
                    "byte_order": byte_order,
                    "unit": unit
                })

    result = {
        "protocol": protocol,
        "fields": fields
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ JSON 已輸出至：{json_path}")


# 範例使用方式
if __name__ == "__main__":
    csv_to_json("./Software/uart_format.csv", "uart_format.json")
