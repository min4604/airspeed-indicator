import os
import json

try:
    from utils.log import Logger_tool
except ModuleNotFoundError:
    from log import Logger_tool

def decode_packet(packet: bytes, json_path="./Software/utils/uart_format.json") -> dict:
    """根據 JSON 格式自動解碼 UART 封包"""
    with open(json_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    proto = cfg["protocol"]
    header = bytes(proto["header"])
    length_index = proto["length_index"]
    data_offset = proto["data_offset"]

    # === 驗證 header ===
    if not packet.startswith(header):
        raise ValueError(f"封包開頭錯誤，預期 {header}, 實際 {packet[:len(header)]}")

    result = {}
    for field in cfg["fields"]:
        name = field["name"]
        offset = field["offset"]
        length = field["length"]
        order = field.get("byte_order", "big")

        raw_bytes = packet[offset:offset + length]
        if len(raw_bytes) < length:
            result[name] = None
            continue

        # 轉換為整數
        value = int.from_bytes(raw_bytes, byteorder=order, signed=False)

        # 儲存原始值與單位
        result[name] = {
            "raw": value,
            "unit": field.get("unit", "")
        }

    return result


if __name__ == "__main__":
    # 測試封包（隨機範例）
    fake_packet = bytes.fromhex("02 00 10 68 00 44 00 12 34 56 78 9A 0A 0B 1C 2D 08")

    decoded = decode_packet(fake_packet)
    print("解析結果：",decoded)
    for k, v in decoded.items():
        print(f"  {k}: {v['raw']} {v['unit']}")
