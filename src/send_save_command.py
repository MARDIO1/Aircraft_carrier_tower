import argparse
import time

import serial

from protocol import SAVE_TO_FLASH_ACK, encode_save_to_flash, verify_crc8


def _find_ack(buffer: bytearray):
    while len(buffer) >= 16:
        start = buffer.find(0xCC)
        if start < 0:
            del buffer[:-15]
            return None
        if start:
            del buffer[:start]
        if len(buffer) < 16:
            return None

        packet = bytes(buffer[:16])
        if packet[1] == SAVE_TO_FLASH_ACK and packet[-1] == 0xDD:
            del buffer[:16]
            if verify_crc8(bytearray(packet), crc_position=-2, calc_start=0):
                return packet
            continue
        del buffer[0]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM15")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    packet = bytes(encode_save_to_flash())
    print(f"TX save: {packet.hex(' ')}")

    deadline = time.time() + args.timeout
    next_tx = 0.0
    buffer = bytearray()
    with serial.Serial(args.port, args.baud, timeout=0.05) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        while time.time() < deadline:
            now = time.time()
            if now >= next_tx:
                ser.write(packet)
                ser.flush()
                next_tx = now + 0.25

            chunk = ser.read(max(1, ser.in_waiting))
            if not chunk:
                continue
            buffer.extend(chunk)
            ack = _find_ack(buffer)
            if ack is None:
                continue

            print(f"RX ack : {ack.hex(' ')}")
            print(f"status : {ack[2]}")
            return 0 if ack[2] == 0 else ack[2]

    print("timeout waiting for 0xA6 ack")
    if buffer:
        print(f"tail   : {bytes(buffer[-64:]).hex(' ')}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
