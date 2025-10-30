# High scalability framework Sensor monitoring system

## Outline
透過使用 wurth EK 無線電模組搭配 IPC 通訊，框架不限制使用4G, RF，顯示方式不限制Web or app


## Requirements
| 元件 | 說明 |
|------|------|
| **Python** ≥ 3.8 | 已在 Raspberry Pi OS (Bullseye/Bookworm) 測試 |
| **pyserial** | 串口通訊模組 |
| **pyzmq** | ZeroMQ 通訊框架 |
| **Flask** | Web 儀表板後端 |
| (選用) **Chart.js** | 前端即時圖表顯示 |

## Usage
```bash
python3 main.py
```

## TODO
- [ ] main.py
- [ ] Serial 解碼
- [ ] 數據計算
- [ ] IPC通道訂閱與發布
- [ ] UI 發布
- [ ] Logging系統

## TL;DR
高擴展性的車輛動態監測系統，使用IPC

**最後更新**：2025 年 10 月
