# serial_reader.py
import os
import time

import zmq

from utils.log import Logger_tool
from utils.fake_tty_trans import generate_fake_packet
from utils.uart_format_communication import decode_packet


def main():
    # 初始化logger
    logger = Logger_tool.init_logger(log_file="console.log")
    filename = os.path.basename(__file__)
    logger.debug(f"{filename} logger Initialization")

    # 初始化zmq
    ctx = zmq.Context()
    socket = ctx.socket(zmq.PUB)
    socket.bind("ipc://sensors.ipc")
    logger.debug("[ZMQ] 啟動完成，開始發送資料...")
    try:
        while True:
            
            # TODO: 等待 pyserial 硬體測試
            # testbench START
            json_file = "./Software/utils/uart_format.json"
            fake_packet = generate_fake_packet(json_file)
            # testbench END
            
            decoded = decode_packet(fake_packet)
            socket.send_json(decoded)
            logger.info(f"[ZMQ] broadcast message success")
            time.sleep(1) 
    except KeyboardInterrupt:
        logger.warning("[ZMQ] socket close")
        socket.close()    
        ctx.term()   
        logger.warning("[ZMQ] program stop")
        exit(0)



if __name__ == "__main__" :
    main()