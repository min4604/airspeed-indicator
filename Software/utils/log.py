# utils/log.py
import logging

class ColorFormatter(logging.Formatter):
    """
    自訂彩色 Formatter。
    不同等級輸出不同 ANSI 顏色，INFO 不上色。
    """
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[1;31m' # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        msg = super().format(record)
        return f"{color}{msg}{self.RESET}"


class Logger_tool:

    @staticmethod
    def init_logger(
        log_file: str = "app.log",
        level = logging.DEBUG,
        log_format: str = "%(asctime)s [%(levelname)s] %(message)s",
        date_format: str = "%Y-%m-%dT%H:%M:%S",
        reset_handlers: bool = True):
        """
        初始化 logger。
        Args:
            log_file (str): 輸出檔案路徑
            level (int): logging level
            log_format (str): log 訊息格式
            date_format (str): 時間格式
            reset_handlers (bool): 若已有 handlers 是否清除舊的
        Returns:
            logging.Logger
        """

        # 建立 logger
        logger = logging.getLogger()
        logger.setLevel(level)

        # 清除舊 handler，避免重複輸出
        if reset_handlers and logger.hasHandlers():
            logger.handlers.clear()

        # 檔案輸出
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(file_handler)

        # 終端輸出（帶顏色）
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColorFormatter(log_format, date_format))
        logger.addHandler(console_handler)
        return logger


# --- 測試 ---
if __name__ == "__main__":
    logger = Logger_tool.init_logger(log_file="a.log",level=logging.INFO)
    logger.debug("This is debug (除錯訊息)")
    logger.info("Hello python with color")
    logger.warning("Be careful")
    logger.error("Something went wrong")
    logger.critical("System down!")

    # function template
    # from utils.log import Logger_tool

    # logger = Logger_tool.init_logger(log_file="a.log",level=logging.INFO)
    # filename = os.path.basename(__file__)
    # logger.debug(f"{filename} logger Initialization")