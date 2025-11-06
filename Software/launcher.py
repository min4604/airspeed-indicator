# launch.py
import multiprocessing
import signal
import time
import os

from utils.log import Logger_tool


def start_serial_reader():
    """啟動 UART Reader 模組"""
    try:
        from serial_reader import main
        main()
    except Exception as e:
        logger.exception(f"[serial_reader] 發生例外: {e}")


def start_analyze():
    """啟動分析 / ZMQ Publisher 模組"""
    try:
        from analyze import main
        main()
    except Exception as e:
        logger.exception(f"[Analyzer] 發生例外: {e}")

# TODO: 
# def start_dashboard():
#     """啟動 Dashboard（或 Flask Web Server）"""
#     try:
#         from dashboard import main
#         main()
#     except Exception:
#         traceback.print_exc()


class SensorSystem:
    """
    系統總控制器：
    - 負責啟動所有子模組
    - 支援 Ctrl+C 安全關閉
    """

    def __init__(self):
        self.processes = []
        self.running = True
        ##### 輸入開啟的服務 #####
        self.modules = [
            ("serial_reader", start_serial_reader),
            ("analyze", start_analyze),
        ]

    def start_all(self):
        """啟動所有子進程"""

        for name, target in self.modules:
            try:
                p = multiprocessing.Process(target=target, name=name, daemon=False)
                p.start()
                self.processes.append(p)
                logger.info(f"[Launch] 啟動成功: {name} (PID={p.pid})")
                time.sleep(0.1)
            except Exception as e:
                logger.exception(f"[Launch] 無法啟動 {name}: {e}")

    def stop_all(self):
        """安全關閉所有子進程"""
        logger.warning("[Launch] 收到結束指令，正在關閉所有模組...")
        for p in self.processes:
            if p.is_alive():
                logger.info(f"[System] 關閉 {p.name} (PID={p.pid})")
                p.terminate()
                p.join(timeout=3)
                    
        logger.warning("[Launch] 所有模組已安全結束。")
        logger.warning("[Launch] All threads have been safely stopped.")

    def run(self):
        """主迴圈，監控 Ctrl+C 或異常"""
        self.start_all()

        try:
            while self.running:
                alive = [p.is_alive() for p in self.processes]
                if not any(alive):
                    logger.warning("[Launch] All threads have been safely stopped.")
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.warning("[Launch] 偵測到 中斷命令，準備停止系統..")
            self.stop_all()
        except Exception as e:
            logger.exception(f"[Launch] 主控迴圈例外: {e}")
        finally:
            logger.warning(f"[Launch] program stop, please check {log_file}")


if __name__ == "__main__":
    # 初始化logger
    log_file="console.log"
    logger = Logger_tool.init_logger(log_file)
    filename = os.path.basename(__file__)
    logger.debug(f"{filename} logger Initialization")

    logger.info("[Launch] Launch control system ready")
    
    system = SensorSystem()
    system.run()