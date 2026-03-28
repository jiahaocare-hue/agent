---
skill_name: check_room
---

# 会议室查询能力

## 能力描述

检查会议室容量和可用性。

## 脚本

- 脚本路径: scripts/check_room.py

## 参数

- room: 会议室名称

## 返回值

脚本执行后返回 JSON 格式：

```json
{
  "room": "会议室名称",
  "capacity": 10,
  "available": true
}
```

**字段说明**：
- `room`: 会议室名称
- `capacity`: 容量（人数）
- `available`: 是否可用（布尔值）

## 使用方式
`
python check_room.py --room A
`
