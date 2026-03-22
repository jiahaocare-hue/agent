# Windows Agent Framework

基于 LLM 的多代理任务编排框架，支持工作流生成、定时调度、任务管理和人工确认。

## 目录

- [特性](#特性)
- [安装](#安装)
- [快速开始](#快速开始)
- [代码框架](#代码框架)
- [可用功能](#可用功能)
- [使用示例](#使用示例)
- [命令参考](#命令参考)
- [扩展指南](#扩展指南)
- [目录结构](#目录结构)

---

## 特性

- **多代理架构**: Main Agent（主代理）+ SubAgent（子代理）分离决策与执行
- **工作流生成**: LLM 自动生成可执行的工作流蓝图
- **定时调度**: 支持一次性/间隔/每日/每周/每月周期性任务
- **人工确认**: 执行前弹出 Tkinter 窗口请求用户确认
- **断点恢复**: 基于 LangGraph Checkpoint 的故障恢复
- **技能扩展**: 从文件系统动态加载 Skills 和 SubAgents
- **成功案例复用**: ChromaDB 存储成功工作流，相似任务自动复用

---

## 安装

### 环境要求

- Python 3.11.x（推荐 3.11.15）
- Windows 操作系统

### 安装步骤

```bash
# 1. 克隆或下载项目
cd d:\tmp\start1

# 2. 使用 Conda 创建环境（推荐）
conda create -n agent python=3.11
conda activate agent

# 3. 安装依赖
pip install -r requirements.txt
```

### 备选：使用 venv

```bash
# 1. 克隆或下载项目
cd d:\tmp\start1

# 2. 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 依赖说明

```
# 核心依赖
langchain                  # LLM 框架
langchain-core             # LangChain 核心
langchain-openai           # OpenAI 模型支持
langgraph                  # 工作流图框架
langgraph-checkpoint-sqlite # SQLite 检查点
pydantic                   # 数据验证
pyyaml                     # YAML 解析（解析 skill.md frontmatter）
chromadb                   # 向量存储（成功工作流案例库）
posthog                    # 遥测控制（禁用 LangChain 遥测）

# 传递依赖（自动安装）
aiosqlite                  # 异步 SQLite（langgraph 依赖）
tiktoken                   # Token 计数（langchain 依赖）
openai                     # OpenAI API（langchain-openai 依赖）
```

### 注意

`requirements.txt` 中的 `deepagents` 未被使用，可以从依赖中移除。

---

## 快速开始

### 启动系统

```bash
python main.py
```

### 基本交互

```
Backend Engine started. Type 'exit' to quit.
Type '/help' for available commands.

You: 打印你好
=== Task Decision ===
Task Type: general
Task Name: 打印
Description: 打印你好
Is Single Task: True
Created Tasks: [1]
Engine Status: {'running': True, 'active_tasks': 0, 'max_workers': 3}

You: /help
可用命令:
  /running, /r                    - 查看运行中的任务
  /pending, /p                    - 查看待执行的任务
  /completed, /c                  - 查看已完成的任务
  /scheduled, /s                  - 查看定时任务
  /cancel <task_id> [task_id2]... - 取消指定任务
  /cancel all <status>            - 批量取消任务
  /clear, /cls                    - 清除 MainAgent 的历史记忆
  /reset-workflows, /rw           - 清空成功工作流案例库
  /help, /h                       - 显示帮助信息

You: exit
Goodbye!
```

---

## 代码框架

### 1. 主入口 (main.py)

```
main.py
├── 初始化 LLM (ChatOpenAI)
├── 初始化数据库 (TaskRepository)
├── 初始化 MCP 模块 (MCPManager.register_default_modules)
├── 初始化 Skills (initialize_skills)
├── 创建 MainAgent (带 SqliteSaver checkpointer)
├── 创建 BackendEngine (线程池 + 调度循环)
└── 命令行循环
    ├── 解析 / 命令 → CommandExecutor
    └── 普通输入 → MainAgent.decide_with_logging()
```

**核心流程**:
```python
# 1. 创建任务
response = main_agent.decide_with_logging(user_input, thread_id="main-session")
task_ids = create_tasks_from_decision(decision, repo, engine, user_input)

# 2. 唤醒引擎执行
engine.wakeup()
```

### 2. 主代理 (main_agent.py)

**MainAgent** 负责理解用户意图并决定任务类型。

**核心方法**:
- `decide_with_logging()`: 决策并打印思考过程
- `_create_list_available_agents_tool()`: 提供工具让 LLM 查询可用代理

**决策模型**:
```python
TaskDecision {
    task_type: str,           # 任务类型: "meeting", "email", "general"
    task_name: str,           # 任务名称
    description: str,          # 任务描述（剥离了定时语义）
    tasks: List[TaskInfo],    # 子任务列表（多任务时使用）
    scheduled_info: ScheduledInfo  # 定时配置
}

DirectResponse {
    response: str,             # 直接回复内容
    reason: str               # 原因说明
}
```

**定时配置**:
```python
ScheduledInfo {
    scheduled_at: datetime,           # 首次执行时间
    repeat_type: "once"|"interval"|"daily"|"weekly"|"monthly",
    repeat_config: {
        # interval: {interval_minutes: int}
        # daily: {time: "HH:MM"}
        # weekly: {time: "HH:MM", day_of_week: 0-6}
        # monthly: {time: "HH:MM", day_of_month: 1-31}
    }
}
```

### 3. 子代理 (subagent.py)

**GeneralAgent** 负责生成具体工作流。

**核心方法**:
- `generate_workflow_with_logging()`: 生成工作流并记录日志
- `_create_read_skill_tool()`: 让 LLM 读取技能定义
- `_create_list_mcp_tools_tool()`: 让 LLM 查询可用 MCP 工具

**工作流蓝图**:
```python
WorkflowBlueprint {
    can_handle: bool,              # 能否处理
    reply_message: str,           # 回复消息
    missing_params: List[str],     # 缺失参数
    description: str,              # 人类可读描述
    nodes: [
        {
            node_id: str,
            action_type: "tool"|"script",
            tool_action: {          # action_type=tool
                tool_name: "module.function",
                tool_kwargs: {key: value}
            },
            script_action: {       # action_type=script
                executable: "python",
                script_path: str,
                args: [str],
                env_vars: {key: value}
            }
        }
    ],
    edges: [
        {
            source: str,            # "START" 或 node_id
            target: str,           # node_id 或 "END"
            is_conditional: bool,
            condition_variable: str,  # 如 "node_outputs.check.available"
            routing_map: {value: target_node}
        }
    ]
}
```

### 4. 后端引擎 (engine.py)

**BackendEngine** 负责任务调度和执行管理。

**核心组件**:
- `ThreadPoolExecutor`: 任务执行线程池
- `TimerScheduler`: 定时任务调度
- `RecoveryManager`: 崩溃恢复
- `VectorStore`: 工作流存储

**核心流程**:
```python
def _run_task(task):
    # 1. 获取 SubAgent
    subagent = get_subagent(task_type, llm, raw_input)

    # 2. 生成工作流（带用户确认）
    workflow_json = _generate_workflow_with_confirmation(...)

    # 3. 构建图
    graph = graph_executor.build_graph(workflow_json)

    # 4. 执行
    result = graph_executor.execute(graph, initial_state, task_id)

    return result
```

### 5. 图执行器 (graph_executor.py)

**GraphExecutor** 负责执行工作流。

**核心方法**:
- `build_graph()`: 将 WorkflowBlueprint 构建为 StateGraph
- `execute()`: 执行工作流，支持检查点恢复
- `_execute_tool()`: 调用 MCP 工具
- `_execute_script()`: 执行脚本

**状态模型**:
```python
AgentState {
    input: str,                              # 原始输入
    output: Annotated[str, keep_last],       # 最终输出
    node_outputs: Annotated[Dict, merge_outputs],  # 各节点输出
    task_id: int,
    current_node: Annotated[str, keep_last]
}
```

**参数渲染**: `${{ state.node_outputs.<node_id>.<field> }}`

### 6. MCP 管理器 (mcp_manager.py)

**MCPManager** 管理 MCP 模块和函数调用。

**默认模块**:
```python
connect_module = {
    "zoom_connect": MCPFunction(
        handler=zoom_connect,
        required_params=["meeting_id"],
        input_schema={...},
        output_schema={...}
    ),
    "qq_meeting_connect": MCPFunction(...)
}
```

**使用方式**:
```python
MCPManager.call("connect_module", "qq_meeting_connect", {"meeting_id": "123456"})
```

### 7. 技能加载器 (skill_loader.py)

**SkillLoader** 从文件系统动态加载技能。

**目录结构**:
```
skills/
  ├── check_room/
  │   ├── skill.md          # 技能定义
  │   └── scripts/
  │       └── check_room.py # 脚本
  ├── send_email/
  │   ├── skill.md
  │   └── scripts/
  │       └── send_email.py
  └── ...

subagent_skills/
  ├── meeting_subagent.md   # 会议代理定义
  └── email_subagent.md     # 邮件代理定义
```

**SubAgent 定义格式**:
```markdown
---
agent_type: meeting
dependencies:
  - check_room
mcp_modules:
  - connect_module
---

# Meeting SubAgent

会议 Agent 能力...
```

### 8. 定时调度器 (timer_scheduler.py)

**TimerScheduler** 管理定时任务。

**重复类型**:
- `once`: 单次执行
- `interval`: 间隔执行（如每 5 分钟）
- `daily`: 每日定时
- `weekly`: 每周定时
- `monthly`: 每月定时

### 9. 命令解析器 (command_parser.py)

**CommandParser** 解析用户命令。

**支持命令**:
| 命令 | 说明 |
|------|------|
| `/r`, `/running` | 查看运行中任务 |
| `/p`, `/pending` | 查看待执行任务 |
| `/c`, `/completed` | 查看已完成任务 |
| `/s`, `/scheduled` | 查看定时任务 |
| `/cancel <id>` | 取消指定任务 |
| `/cancel all <status>` | 批量取消 |
| `/clear`, `/cls` | 清除 Agent 记忆 |
| `/rw`, `/reset-workflows` | 清空工作流库 |
| `/h`, `/help` | 显示帮助 |

### 10. 向量存储 (vector_store.py)

**WorkflowVectorStore** 存储和检索成功工作流。

```python
# 添加成功工作流
store.add_workflow(
    raw_input="创建腾讯会议",
    workflow_json={...},
    task_type="meeting"
)

# 检索相似工作流
similar = store.search_similar(
    query="安排会议",
    task_type="meeting",
    n_results=3
)
```

---

## 可用功能

### 任务类型

| 类型 | 说明 | 依赖技能 |
|------|------|----------|
| `meeting` | 会议相关任务 | check_room |
| `email` | 邮件相关任务 | send_email, qq_mail, google_mail, favorite_mail, email_config |
| `general` | 通用任务 | 无 |

### MCP 工具

| 工具 | 模块 | 参数 | 说明 |
|------|------|------|------|
| `zoom_connect` | connect_module | meeting_id (必填), password (可选) | 连接 Zoom 会议 |
| `qq_meeting_connect` | connect_module | meeting_id (必填) | 连接腾讯会议 |

### 工作流模式

| 模式 | 关键词 | 说明 |
|------|--------|------|
| 并行汇聚 | 同时、并行、一起 | 多任务并行后汇聚 |
| 条件分支 | 如果、判断、条件 | 根据条件选择路径 |
| 多阶段处理 | 先、然后、接着、最后 | 顺序执行多个阶段 |
| 错误处理 | 失败、错误、异常 | 包含错误处理节点 |
| 分发收集 | 分发、广播、通知所有 | 分发后收集结果 |

---

## 使用示例

### 示例 1: 执行简单任务

```
You: 打印你好
-> MainAgent 分析输入，创建 general 类型任务
-> BackendEngine 执行，打印 "你好"
```

### 示例 2: 创建定时任务

```
You: 每隔5分钟检查一次A会议室
-> MainAgent 解析定时语义
-> 创建 scheduled 状态任务
-> 每隔5分钟自动执行
```

### 示例 3: 创建腾讯会议

```
You: 帮我创建一个腾讯会议，会议号是123456789
-> MainAgent 返回 meeting 类型任务
-> SubAgent 生成工作流
-> 弹出确认窗口
-> 用户确认后执行 qq_meeting_connect
```

### 示例 4: 查询和取消任务

```
You: /pending
-> 显示所有待执行任务

You: /cancel 5
-> 取消任务 5
```

---

## 命令参考

### 任务查询

```bash
/running, /r        # 查看运行中任务
/pending, /p        # 查看待执行任务
/completed, /c      # 查看已完成任务
/scheduled, /s      # 查看定时任务
```

### 任务控制

```bash
/cancel 1 2 3       # 取消指定任务
/cancel all pending # 批量取消待执行任务
/cancel all running # 批量取消运行中任务
```

### 系统控制

```bash
/clear, /cls        # 清除 MainAgent 对话记忆
/reset-workflows, /rw  # 清空成功工作流库
/help, /h           # 显示帮助
```

---

## 扩展指南

### 添加新技能

1. 在 `skills/` 下创建目录：
```
skills/
  └── my_skill/
      ├── skill.md
      └── scripts/
          └── my_script.py
```

2. 编写 `skill.md`：
```markdown
---
skill_name: my_skill
---

# 我的技能

## 能力描述

这是我的技能描述...

## 脚本

- 脚本路径: scripts/my_script.py

## 参数

- param1: 参数1描述
- param2: 参数2描述
```

3. 编写脚本 `scripts/my_script.py`：
```python
import json
import sys

def main():
    # 解析参数
    # 执行逻辑
    result = {"output": "执行结果", "status": "success"}
    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

### 添加新子代理

1. 在 `subagent_skills/` 下创建文件：
```
subagent_skills/
  └── myagent_subagent.md
```

2. 编写定义：
```markdown
---
agent_type: myagent
dependencies:
  - my_skill
mcp_modules:
  - connect_module
---

# MyAgent

我的代理能力描述...

## 支持的任务类型

- 任务类型1
- 任务类型2
```

### 添加新 MCP 工具

1. 在 `mcp_manager.py` 中定义函数：
```python
def my_tool(param1: str, param2: str = None) -> dict:
    """
    我的工具描述

    Args:
        param1: 必填参数
        param2: 可选参数

    Returns:
        执行结果字典
    """
    # 实现逻辑
    return {"status": "success", "result": "..."}
```

2. 注册到 MCPManager：
```python
MCPManager.register_module("my_module", {
    "my_tool": MCPFunction(
        name="my_tool",
        description="我的工具描述",
        input_schema={"param1": "string", "param2": "string"},
        output_schema={"status": "string", "result": "string"},
        handler=my_tool,
        required_params=["param1"]
    )
})
```

---

## 目录结构

```
d:\tmp\start1\
├── main.py                      # 主入口
├── engine.py                    # 后端引擎
├── main_agent.py                # 主代理
├── subagent.py                  # 子代理
├── graph_executor.py             # 图执行器
├── database.py                   # 数据仓库
├── skill_loader.py               # 技能加载器
├── mcp_manager.py                # MCP 管理器
├── command_parser.py             # 命令解析器
├── timer_scheduler.py            # 定时调度器
├── recovery_manager.py          # 恢复管理器
├── task_logger.py                # 任务日志
├── vector_store.py               # 向量存储
├── human_loop.py                 # 人工确认
├── popup_worker.py               # Tkinter 弹窗
├── workflow_examples.py          # 工作流模板
├── requirements.txt              # Python 依赖
│
├── skills/                      # 技能目录
│   ├── check_room/
│   │   ├── skill.md
│   │   └── scripts/
│   │       └── check_room.py
│   ├── send_email/
│   ├── qq_mail/
│   ├── google_mail/
│   ├── favorite_mail/
│   └── email_config/
│
├── subagent_skills/             # 子代理定义
│   ├── meeting_subagent.md
│   └── email_subagent.md
│
├── logs/                        # 任务日志
│   └── task_*.log
│
├── chroma_db/                   # ChromaDB 存储
├── tasks.db                     # SQLite 数据库
├── main_agent_checkpoint.db     # MainAgent 检查点
└── checkpoints.db               # 工作流检查点
```

---

## 许可证

本项目仅供学习和研究使用。
