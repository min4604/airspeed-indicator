# High scalability framework Sensor monitoring system

## Outline
主要以框架的思維角度設計，以IPC作為核心通訊框架  
加上log系統輔助紀錄   
增強框架下車輛動態監測系統維護性並降低升級難度


## Requirements
- OS: Raspbian
- Device: RPI4
## Installation
請先安裝miniconda
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash ~/Miniconda3-latest-Linux-aarch64.sh
```
安裝所需套件
```bash
pip install zmq pyserial
```

## Usage  
1. 移動到專案資料夾  
```bash
cd ./Software/
```
2. 啟動控制台
```bash
python3 launcher.py
```
3. 按下`q`結束

## TODO
- [ ] main.py
- [ ] Serial 解碼
- [ ] 數據計算
- [ ] IPC通道訂閱與發布
- [ ] UI 發布
- [ ] Logging系統
- [ ] 驗證RPI5相容性
- [ ] known issue: windows環境下`p.terminate()`會強制退出子程序

## TL;DR
高擴展性的車輛動態監測系統，使用IPC

**最後更新**：2025/10/31
