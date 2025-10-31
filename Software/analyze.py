# analyze.py
import os
import time

from utils.log import Logger_tool

def main():
    # 初始化logger
    logger = Logger_tool.init_logger(log_file="a.log")
    filename = os.path.basename(__file__)
    logger.debug(f"{filename} logger Initialization")
    try:
        while True:
            logger.debug("hello world")
            time.sleep(1) 
    except KeyboardInterrupt:     
        logger.warning("[analyze] program stop")



if __name__ == "__main__" :

    main()