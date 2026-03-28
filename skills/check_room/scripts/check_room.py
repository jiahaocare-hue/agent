#!/usr/bin/env python3
"""检查会议室容量"""
import sys
import json

def check_room_capacity(room_name: str) -> dict:
    """检查会议室容量（模拟数据）"""
    rooms = {
        "A": {"capacity": 10, "available": True},
        "B": {"capacity": 20, "available": False},
        "C": {"capacity": 5, "available": True},
    }
    room_key = room_name.upper().replace("会议室", "").strip()
    if room_key in rooms:
        return {"room": room_name, **rooms[room_key]}
    return {"error": f"未找到会议室: {room_name}"}

def main():
    import argparse
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--room", required=True, help="会议室名称")
    args = arg_parser.parse_args()
    room_name = args.room.upper()  # 使用 args.room
    result = check_room_capacity(room_name)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
