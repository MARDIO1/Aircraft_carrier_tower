import serial
import time
import argparse
import json
import sys

def ping_board(port, timeout, is_virtual=False):
    """
    基础连通性测试 (发送 0xA5 SAVE_DATA，期望返回 0xCC 0xA6 ACK)
    """
    try:
        # 如果是虚拟口，自动转化为 socket URL
        serial_port = f"socket://127.0.0.1:{port}" if is_virtual else port
        
        # 兼容真实串口和 TCP 虚拟串口
        ser = serial.serial_for_url(serial_port, baudrate=115200, timeout=timeout)
        
        # 构造 AA A5 CRC BB
        payload = bytes([0xAA, 0xA5, 0x68, 0xBB])
        
        start_time = time.time()
        ser.write(payload)
        
        # 期望读取 16 bytes 的 ACK
        resp = ser.read(16)
        rtt = (time.time() - start_time) * 1000
        ser.close()
        
        if len(resp) == 16 and resp[0] == 0xCC and resp[1] == 0xA6 and resp[15] == 0xDD:
            result = {
                "status": "success",
                "rtt_ms": round(rtt, 2),
                "response": resp.hex().upper(),
                "error": None
            }
        else:
             result = {
                "status": "fail",
                "rtt_ms": None,
                "response": resp.hex().upper() if resp else None,
                "error": "Invalid ACK length or format" if resp else "Timeout"
            }
        
    except Exception as e:
        result = {
            "status": "error",
            "rtt_ms": None,
            "response": None,
            "error": str(e)
        }
        
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="STM32 连通性测试仪")
    parser.add_argument("--port", type=str, required=True, help="COM号(如 COM16) 或 TCP端口 (配合--virtual)")
    parser.add_argument("--timeout", type=float, default=2.0, help="超时时间(秒)")
    parser.add_argument("--virtual", action="store_true", help="是否连接虚拟模拟器")
    args = parser.parse_args()
    
    sys.exit(ping_board(args.port, args.timeout, args.virtual))
