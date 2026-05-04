import socket
import threading
import time
import struct
import argparse
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def mock_device(port=9999):
    """
    通过 TCP Socket 仿真飞控串口。
    地面站测试时可以通过 pyserial 连接: serial.serial_for_url(f'socket://127.0.0.1:{port}')
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    logging.info(f"虚拟 STM32 飞控已启动，监听 TCP 端口 {port}...")
    logging.info("请在地面站使用 'socket://127.0.0.1:9999' 作为 COM 口进行连接测试")

    while True:
        conn, addr = server.accept()
        logging.info(f"地面站已连接: {addr}")
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                
                # 简单解析帧头 0xAA 和 帧尾 0xBB
                if len(data) >= 4 and data[0] == 0xAA and data[-1] == 0xBB:
                    cmd = data[1]
                    logging.info(f"收到指令: 0x{cmd:02X}")
                    
                    # 模拟响应 0xA5 (SAVE_DATA)
                    if cmd == 0xA5:
                        time.sleep(0.01) # 模拟 Flash 耗时
                        # 构造 ACK 包: CC A6 00 00 ... 85 DD (16 bytes)
                        ack = bytearray([0x00] * 16)
                        ack[0] = 0xCC
                        ack[1] = 0xA6
                        ack[2] = 0x00 # status: 0
                        ack[14] = 0x85 # fake crc
                        ack[15] = 0xDD
                        conn.sendall(ack)
                        logging.info("已回复 SAVE_DATA ACK (0xCC 0xA6)")
                    
        except ConnectionResetError:
            pass
        finally:
            conn.close()
            logging.info("地面站已断开连接")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="STM32 虚拟飞控仿真器")
    parser.add_argument("--port", type=int, default=9999, help="TCP 监听端口 (默认 9999)")
    args = parser.parse_args()
    mock_device(args.port)
