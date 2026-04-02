---
agent_type: meeting
dependencies:
  - check_room
  - check_production_progress
  - llm_process
mcp_modules:
  - connect_module
---

# Meeting SubAgent

会议 Agent 能力，处理会议相关任务。

## 能力描述

MeetingAgent 是一个专门处理会议相关任务的 Agent。

## 支持的任务类型

- 日程管理：查询、创建、修改日程
- 会议安排：创建会议邀请、协调参与者时间
- 会议室管理：查询会议室容量、预订会议室
- 会议连接：连接 Zoom 会议、腾讯会议等
