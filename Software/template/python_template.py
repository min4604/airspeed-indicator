# python_template.py
import os

import zmq

from utils.log import Logger_tool


def main():
    # 初始化logger
    logger = Logger_tool.init_logger(log_file="console.log")
    filename = os.path.basename(__file__)
    logger.debug(f"{filename} logger Initialization")

    # 初始化 ZMQ
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    ipc_path = "ipc://sensors.ipc"
    socket.connect(ipc_path)
    socket.setsockopt(zmq.SUBSCRIBE, b"") 
    logger.info(f"[template] 已連線到 {ipc_path}")  

    try:
        ###### your function ######
        print("hello world")
        ###########################


    except KeyboardInterrupt:
      
        logger.warning("[template] pregram stop")
        exit(0)


if __name__ == "__main__" :
    main()