# analyze.py
import os
import time

import zmq

from utils.log import Logger_tool
from utils.uart_format_communication import decode_packet

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
    logger.info(f"[analyze] 已連線到 {ipc_path}")  


    try:
        while True:
            msg = socket.recv_json(flags=0)
            text = ""
            for k, v in msg.items():
                text += f"  {k}: {v['raw']} {v['unit']}\n"
            logger.info(f"[analyze] 收到資料:\n{text}")
    except KeyboardInterrupt: 
        logger.warning("[analyze] socket close")
        socket.close()    
        ctx.term()   
        logger.warning("[analyze] program stop")
        exit(0)    
        logger.warning("[analyze] program stop")



if __name__ == "__main__" :
    main()