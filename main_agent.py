from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime

from logging_config import get_logger

logger = get_logger(__name__)


class TaskInfo(BaseModel):
    task_type: str = Field(description="任务类型")
    task_name: str = Field(description="任务名称")
    description: str = Field(description="任务描述")
    dependencies: list[int] = Field(default_factory=list, description="依赖的任务索引列表")


class IntervalConfig(BaseModel):
    interval_minutes: int = Field(description="间隔分钟数")


class DailyConfig(BaseModel):
    time: str = Field(description="执行时间，格式 HH:MM")


class WeeklyConfig(BaseModel):
    time: str = Field(description="执行时间，格式 HH:MM")
    day_of_week: int = Field(description="星期几，0=周一")


class MonthlyConfig(BaseModel):
    time: str = Field(description="执行时间，格式 HH:MM")
    day_of_month: int = Field(description="每月几号，1-31")


class ScheduledInfo(BaseModel):
    scheduled_at: Optional[datetime] = Field(default=None, description="首次执行时间")
    repeat_type: Optional[str] = Field(default=None, description="重复类型: once/interval/daily/weekly/monthly")
    repeat_config: Optional[Union[IntervalConfig, DailyConfig, WeeklyConfig, MonthlyConfig]] = Field(
        default=None,
        description="周期配置"
    )


class DirectResponse(BaseModel):
    """直接返回给用户的响应，不创建任务"""
    response: str = Field(description="直接返回给用户的回答内容")
    reason: str = Field(description="为什么选择直接响应而不是创建任务")


class TaskDecision(BaseModel):
    task_type: str = Field(description="任务类型")
    task_name: str = Field(description="任务名称")
    description: str = Field(description="任务描述")
    tasks: list[TaskInfo] = Field(default_factory=list, description="子任务列表")
    scheduled_info: Optional[ScheduledInfo] = Field(default=None, description="定时信息")

    @property
    def is_single_task(self) -> bool:
        return len(self.tasks) == 0


class MainAgent:
    """
    主 Agent，负责任务调度决策。

    使用 create_agent 创建，支持：
    - 工具调用（list_available_agents）
    - 持久化记忆（SqliteSaver）
    - 多次 LLM 调用循环
    - 强制返回 TaskDecision 结构化输出
    """

    def __init__(self, llm, checkpointer: SqliteSaver):
        self.llm = llm
        self.checkpointer = checkpointer
        self.checkpointer.setup()
        
        agent_tools = [
            self._create_list_available_agents_tool(),
        ]
        
        self.response_format = ToolStrategy(
            Union[DirectResponse, TaskDecision],
            handle_errors=True,
        )

        system_prompt = self._build_system_prompt()
        
        self.agent = create_agent(
            model=llm,
            tools=agent_tools,
            system_prompt=system_prompt,
            response_format=self.response_format,
            checkpointer=checkpointer,
        )
    
    def _create_list_available_agents_tool(self):
        """创建 list_available_agents 工具"""
        @tool
        def list_available_agents() -> str:
            """
            列出所有可用的 Subagent 及其能力描述。
            
            Returns:
                所有 Subagent 的能力描述，包含依赖的 skills 列表
            """
            from skill_loader import SkillMemory
            from subagent import extract_description
            
            subagents = SkillMemory.get_all_subagents()
            result = []
            for agent_type, subagent in subagents.items():
                description = subagent.skill_content
                line = f"{agent_type}: {description}"
                
                # if subagent.dependencies:
                #     line += f" [依赖 skills: {', '.join(subagent.dependencies)}]"
                
                result.append(line)
            return "\n".join(result) if result else "当前没有可用的 Agent"
        
        return list_available_agents
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个高级任务调度主节点（Supervisor）。

## 可用工具

你可以使用以下工具来获取信息：
- list_available_agents(): 列出所有可用的 Subagent 及其能力描述

## 核心职责

当用户输入包含"周期性/定时/每隔"等执行语义时，你必须将任务拆解为两部分：

1. **调度配置（Schedule Config）**：提取出定时的频率或规则，存入 scheduled_info
2. **核心子任务（Core Sub-task）**：剥离掉所有时间、频率、周期相关的词汇，提炼出单次执行的纯粹任务动作，存入 description

## description 字段规则

**极其重要**：description 字段必须剥离所有定时/循环/周期相关的语义！

示例：
- 用户输入："每隔5分钟去数据库查一下最新的交易记录"
  - description = "去数据库查一下最新的交易记录"（不能包含"每隔5分钟"）
  - scheduled_info = {repeat_type: "interval", repeat_config: {interval_minutes: 5}}

- 用户输入："每天早上9点发送日报邮件"
  - description = "发送日报邮件"（不能包含"每天早上9点"）
  - scheduled_info = {repeat_type: "daily", repeat_config: {time: "09:00"}}

- 用户输入："每周一打印你好"
  - description = "打印你好"（不能包含"每周一"）
  - scheduled_info = {repeat_type: "weekly", ...}

- 用户输入："打印你好"（无定时语义）
  - description = "打印你好"
  - scheduled_info = null

## 任务类型

首先调用 list_available_agents() 获取可用的 Subagent 类型，然后根据用户任务选择最合适的类型。

## 任务拆分规则（极其重要）

**规则**：只有当子任务属于**不同类型**时，才使用多任务模式（tasks 非空）。

## 并行执行说明

**重要**：并行执行应该在**工作流层面**由 SubAgent 处理，而不是在任务层面拆分！

- 用户说"同时做A和B" → 单任务模式，让 SubAgent 生成并行工作流
- 用户说"先做A再做B" → 单任务模式，让 SubAgent 生成串行工作流
- 用户说"做A和B，它们是不同类型的任务" → 多任务模式

## 定时任务配置说明

- once: 执行一次，repeat_config 为空
- interval: 间隔执行，repeat_config 使用 IntervalConfig，包含 interval_minutes
- daily: 每天执行，repeat_config 使用 DailyConfig，包含 time (HH:MM)
- weekly: 每周执行，repeat_config 使用 WeeklyConfig，包含 time 和 day_of_week (0=周一)
- monthly: 每月执行，repeat_config 使用 MonthlyConfig，包含 time 和 day_of_month

## scheduled_at 计算规则

- "每隔10分钟提醒我" → scheduled_at = 当前时间 + 10分钟
- "每天3点提醒我" → scheduled_at = 今天或明天的 03:00:00
- "每周一9点提醒我" → scheduled_at = 下周一的 09:00:00
- "每月15号提醒我" → scheduled_at = 本月或下月15号的时间
- "3月12号12点提醒我" → scheduled_at = 2025-03-12 12:00:00

## 响应类型选择

你需要根据用户输入选择合适的响应类型：

### 使用 DirectResponse 的情况：
- 用户询问系统信息（如"有哪些可用的 agent？"）
- 用户询问当前状态（如"现在有什么任务在运行？"）
- 用户请求帮助或说明（如"这个系统是做什么的？"）
- 简单的问答，不需要执行任何操作
- **用户的任务没有匹配的 Agent 类型**（如用户请求执行一个不存在的任务类型）

### 使用 TaskDecision 的情况：
- 用户请求执行具体任务（如"打印你好"、"发送邮件"）
- 用户请求定时任务（如"每天早上9点提醒我"）
- 用户请求执行脚本或工具

**重要**：
- 如果用户只是询问信息，使用 DirectResponse
- 如果用户请求执行操作，使用 TaskDecision
- **如果用户请求的任务类型没有对应的 Agent，使用 DirectResponse 告诉用户"当前系统不支持该任务类型"**
"""
    
    def _build_message(self, user_input: str) -> str:
        current_time = datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        current_weekday = current_time.weekday()
        
        return f"""当前时间: {current_time_str}
当前星期: {current_weekday} (0=周一, 1=周二, ..., 6=周日)

用户输入: {user_input}

请分析用户输入，返回 TaskDecision JSON 对象。"""
    
    def decide(
        self,
        user_input: str,
        thread_id: str = "main-agent"
    ) -> Union[DirectResponse, TaskDecision]:
        message = self._build_message(user_input)
        
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": thread_id}}
        )

        return result["structured_response"]
    
    def decide_with_logging(
        self,
        user_input: str,
        thread_id: str = "main-agent"
    ) -> Union[DirectResponse, TaskDecision]:
        message = self._build_message(user_input)
        final_state = None

        for chunk in self.agent.stream(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode=["messages", "updates"],
        ):
            if not isinstance(chunk, tuple) or len(chunk) != 2:
                continue

            stream_mode, payload = chunk

            if stream_mode == "messages":
                self._print_stream_chunk(payload)

            elif stream_mode == "updates":
                if isinstance(payload, dict):
                    for node_name, node_data in payload.items():
                        if isinstance(node_data, dict) and "structured_response" in node_data:
                            final_state = node_data

        if final_state and "structured_response" in final_state:
            return final_state["structured_response"]

        return None
    
    def _print_stream_chunk(self, payload):
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
            
        message_obj, metadata = payload
        
        if hasattr(message_obj, 'content'):
            has_stream_tools = hasattr(message_obj, 'tool_call_chunks') and message_obj.tool_call_chunks
            has_normal_tools = hasattr(message_obj, 'tool_calls') and message_obj.tool_calls

            content = str(message_obj.content)
            if content.strip():
                logger.debug(f"思考: {content[:200]}")
            
            if has_stream_tools or has_normal_tools:
                tools = message_obj.tool_call_chunks if has_stream_tools else message_obj.tool_calls
                for tool in tools:
                    tool_name = tool.get('name')
                    if tool_name:
                        logger.debug(f"调用工具: {tool_name}")
                        return
        
        if hasattr(message_obj, 'name') and hasattr(message_obj, 'content') and getattr(message_obj, 'type', None) == "tool":
            content = str(message_obj.content)[:200]
            logger.debug(f"工具返回 ({message_obj.name}): {content}")
