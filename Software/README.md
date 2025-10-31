# High scalability framework Sensor monitoring system

## Outline
主要以框架的思維角度設計，以IPC作為核心通訊框架  
加上log系統輔助紀錄   
增強框架下車輛動態監測系統維護性並降低升級難度


## Requirements

## Installation
```bash
pip install zmq
pip install pyserial
```

## Usage
```bash
python3 launch.py
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

**最後更新**：2025/10/31
