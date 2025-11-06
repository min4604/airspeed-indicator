import json
import random
from pathlib import Path

def generate_fake_packet(json_path: str) -> bytes:
    """
    根據指定的 JSON 協定檔產生一筆模擬封包資料。

    參數：
        json_path (str): 協定設定檔路徑 (.json)
    回傳：
        bytes: 模擬封包資料
    """
    # 讀取 JSON 檔
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到檔案：{json_path}")

    with open(path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # 取得協定基本資訊
    header = bytes(schema["protocol"]["header"])
    length_index = schema["protocol"]["length_index"]
    data_offset = schema["protocol"]["data_offset"]

    # 建立初始封包（包含 header + 預留長度）
    packet = bytearray()
    packet.extend(header)
    packet.extend(b'\x00' * (data_offset - len(header)))  # 預留空位

    # 為每個欄位生成假資料
    for field in schema["fields"]:
        length = field["length"]
        byte_order = field["byte_order"]
        fake_value = random.randint(0, 2 ** (length * 8) - 1)
        packet.extend(fake_value.to_bytes(length, byteorder=byte_order))

    # 計算並填入封包總長度
    total_length = len(packet)
    packet[length_index] = total_length

    return bytes(packet)


# 範例執行
if __name__ == "__main__":
    json_file = "./Software/utils/uart_format.json"  # 例如存成同資料夾的檔案
    fake_bytes = generate_fake_packet(json_file)

    # 顯示結果
    print("封包 Bytes:", fake_bytes)
    print("十六進位表示:", fake_bytes.hex(" "))
    print("封包長度:", len(fake_bytes))
