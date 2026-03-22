from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Type
from datetime import datetime
from pathlib import Path
import json

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from graph_executor import WorkflowBlueprint, NodeDef, EdgeDef, ToolActionDef, ScriptActionDef, validate_workflow_graph
from skill_loader import Skill, SubAgentDef, SkillMemory, SkillLoader
from task_logger import TaskLogger
from mcp_manager import MCPManager
from workflow_examples import get_relevant_examples
from vector_store import WorkflowVectorStore
from logging_config import get_logger

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_workflow_prompt() -> str:
    """加载工作流提示词模板"""
    prompt_path = PROMPTS_DIR / "workflow_prompt.md"
    return prompt_path.read_text(encoding="utf-8")


WORKFLOW_PROMPT_TEMPLATE = load_workflow_prompt()


def extract_description(skill_content: str) -> str:
    """
    从 skill.md 内容中提取能力描述。
    
    Args:
        skill_content: skill.md 的完整内容
    
    Returns:
        能力描述字符串
    """
    import re
    
    match = re.search(r'##\s*能力描述\s*\n+(.+?)(?=\n##|\n#|\Z)', skill_content, re.DOTALL)
    if match:
        return match.group(1).strip().split('\n')[0].strip()
    
    lines = skill_content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# ') and i + 1 < len(lines):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() and not lines[j].startswith('#'):
                    return lines[j].strip()
                if lines[j].startswith('#'):
                    break
    
    return "无描述"


WORKFLOW_PROMPT_TEMPLATE = load_workflow_prompt()


def format_examples_for_prompt(examples: List[dict]) -> str:
    """将工作流示例格式化为提示词"""
    if not examples:
        return ""
    
    lines = ["## 参考示例\n"]
    lines.append("以下是类似场景的成功工作流示例，供你参考：\n")
    
    for i, example in enumerate(examples, 1):
        lines.append(f"### 示例 {i}")
        lines.append(f"描述: {example.get('description', '无')}")
        lines.append(f"节点数: {len(example.get('nodes', []))}")
        lines.append("```json")
        lines.append(json.dumps(example, ensure_ascii=False, indent=2))
        lines.append("```\n")
    
    return "\n".join(lines)


class SubAgent(ABC):
    @abstractmethod
    def generate_workflow(self, raw_input: str) -> dict:
        pass


class AgentFactory:
    """
    Agent 工厂类，根据 SubAgentDef 信息动态创建 Agent。
    """
    _registry: Dict[str, Type['SubAgent']] = {}
    
    @classmethod
    def register_from_subagents(cls, subagents: Dict[str, SubAgentDef]) -> None:
        """
        根据 SubAgent 定义自动注册 Agent。
        
        Args:
            subagents: SubAgentDef 字典，key 是 agent_type
        """
        for agent_type, subagent_def in subagents.items():
            SkillMemory.add_subagent(subagent_def)
            cls._registry[agent_type] = GeneralAgent
    
    @classmethod
    def create(cls, agent_type: str, llm, raw_input: str = None) -> SubAgent:
        """
        创建 Agent 实例。
        
        Args:
            agent_type: Agent 类型
            llm: LLM 实例
        
        Returns:
            Agent 实例，关联对应的 SubAgentDef
        
        Raises:
            ValueError: 如果 agent_type 未注册
        """
        if agent_type not in cls._registry:
            raise ValueError(f"未注册的 Agent 类型: {agent_type}。可用类型: {cls.get_available_types()}")
        
        subagent_def = SkillMemory.get_subagent(agent_type)
        return GeneralAgent(llm, raw_input, subagent_def)
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """获取所有可用的 Agent 类型"""
        return list(cls._registry.keys())


class GeneralAgent(SubAgent):
    """
    通用 Agent，使用 create_agent 创建。
    
    所有 Agent 实例都使用：
    - 系统提示词: WORKFLOW_PROMPT_TEMPLATE
    - 结构化输出: WorkflowBlueprint
    """
    
    def __init__(self, llm, raw_input: str = None, subagent_def: Optional[SubAgentDef] = None):
        self.llm = llm
        self.subagent_def = subagent_def
        self.vector_store = WorkflowVectorStore()
        
        self._build_agent(raw_input)
    
    def _build_agent(self, raw_input: str = None):
        """构建 Agent 实例"""
        agent_tools = [
            self._create_read_skill_tool(),
            self._create_list_mcp_tools_tool()
        ]
        self.agent_tools = agent_tools
        
        self.response_format = ToolStrategy(
            WorkflowBlueprint,
            handle_errors=True,
        )

        system_prompt = self._build_system_prompt(raw_input)

        self.agent = create_agent(
            model=self.llm,
            tools=agent_tools,
            system_prompt=system_prompt,
            response_format=self.response_format,
            checkpointer=MemorySaver(
                serde=JsonPlusSerializer(allowed_msgpack_modules=[
                    ('graph_executor', 'WorkflowBlueprint'),
                    ('graph_executor', 'NodeDef'),
                    ('graph_executor', 'EdgeDef'),
                    ('graph_executor', 'ToolActionDef'),
                    ('graph_executor', 'ScriptActionDef'),
                ])
            ),
        )
    
    def _create_read_skill_tool(self):
        """
        创建 read_skill 工具，支持读取依赖的 skills。
        
        权限规则：
        - 不传参数：返回当前 Agent 的定义内容
        - 传入 skill_name：读取指定的依赖 skill
        - 只能读取 dependencies 中声明的 skill
        """
        current_subagent = self.subagent_def
        
        @tool
        def read_skill(skill_name: str = None) -> str:
            """
            读取 skill 文档内容。
            
            使用方式：
            - 不传参数：返回当前 Agent 的定义内容，包含依赖的 skills 列表
            - 传入 skill_name：读取指定的依赖 skill
            
            Args:
                skill_name: 可选，指定要读取的 skill 名称。
                           如果不指定，返回 Agent 定义内容。
                           如果指定，返回该 skill 的内容。
            
            Returns:
                skill 文档内容
            """
            if current_subagent is None:
                return "当前 Agent 没有关联定义"
            
            if skill_name is None:
                return current_subagent.skill_content
            
            if skill_name not in current_subagent.dependencies:
                return f"未找到 skill: {skill_name}。可用的 skills: {current_subagent.dependencies}"
            
            skill = SkillMemory.get_skill(skill_name)
            if skill:
                result = skill.skill_content
                if skill.scripts_path:
                    result += f"\n\n## 脚本路径\n{skill.scripts_path}"
                return result
            
            return f"未找到 skill: {skill_name}"
        
        return read_skill
    
    def _create_list_mcp_tools_tool(self):
        """
        创建 list_mcp_tools 工具，查询当前 SubAgent 可用的 MCP 接口。
        
        数据来源：从 SubAgentDef.mcp_modules 获取模块列表
        """
        current_subagent = self.subagent_def
        
        @tool
        def list_mcp_tools() -> str:
            """
            列出当前 SubAgent 可用的 MCP 接口。
            
            根据当前 Agent 的 mcp_modules 配置，查询可用接口。
            返回接口名称、描述、入参、出参信息。
            
            Returns:
                可用的 MCP 接口描述
            """
            if current_subagent is None:
                return "当前 Agent 没有关联定义"
            
            mcp_modules = current_subagent.mcp_modules
            if not mcp_modules:
                return "当前 Agent 没有配置 MCP 模块"
            
            return MCPManager.get_module_functions(mcp_modules)
        
        return list_mcp_tools
    
    def _build_system_prompt(self, raw_input: str = None) -> str:
        """构建系统提示词"""
        if not self.subagent_def:
            raise ValueError("Agent 必须关联一个 SubAgentDef")
        
        agent_type = self.subagent_def.agent_type
        dependencies = self.subagent_def.dependencies
        
        skills_info = []
        for dep in dependencies:
            skill = SkillMemory.get_skill(dep)
            if skill:
                scripts_info = f"（脚本路径: {skill.scripts_path}）" if skill.scripts_path else ""
                skills_info.append(f"- {dep}{scripts_info}")
        
        skill_info = f"""
## 当前 Agent

Agent 类型: {agent_type}
依赖的 Skills: {', '.join(dependencies) if dependencies else '无'}

### 可用 Skills

{chr(10).join(skills_info) if skills_info else '无'}

**重要**：生成 WorkflowBlueprint 时，脚本路径必须使用上述脚本路径下的脚本文件。
"""
        
        base_prompt = WORKFLOW_PROMPT_TEMPLATE.format(
            agent_type=agent_type,
            skill_info=skill_info
        )
        
        examples = []
        TEMPLATE_QUOTA = 2
        SUCCESS_QUOTA = 3
        
        if raw_input:
            template_examples = get_relevant_examples(raw_input, limit=TEMPLATE_QUOTA)
            if template_examples:
                logger.debug(f"从模板库获取 {len(template_examples)} 个相关模板")
            examples.extend(template_examples)
        
        if raw_input:
            similar_workflows = self.vector_store.search_similar(
                query=raw_input,
                task_type=agent_type,
                n_results=SUCCESS_QUOTA
            )
            if similar_workflows:
                logger.debug(f"从成功案例库获取 {len(similar_workflows)} 个相似案例")
            examples.extend([w['workflow_json'] for w in similar_workflows])
        
        if examples:
            examples_text = format_examples_for_prompt(examples)
            base_prompt += "\n\n" + examples_text
            logger.debug(f"共注入 {len(examples)} 个示例到提示词")
        
        return base_prompt

    def _invoke_agent(self, message: str, thread_id: str):
        """公共的 agent 调用逻辑"""
        return self.agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": thread_id}}
        )

    def _stream_agent(self, message: str, thread_id: str):
        """公共的 agent 流式调用逻辑"""
        return self.agent.stream(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode=["messages", "updates"],
        )

    def generate_workflow(
        self,
        message: str,
        thread_id: str = "workflow-generation"
    ) -> dict:
        result = self._invoke_agent(message, thread_id)
        return result["structured_response"].model_dump()
    
    def generate_workflow_with_logging(
        self,
        message: str,
        thread_id: str = "workflow-generation",
        *,
        task_id: int = 0,
    ) -> dict:
        task_logger = TaskLogger(task_id)
        final_state = None

        for chunk in self._stream_agent(message, thread_id):
            if not isinstance(chunk, tuple) or len(chunk) != 2:
                continue
                
            stream_mode, payload = chunk

            if stream_mode == "messages":
                self._process_and_log_chunk(payload, task_logger)
                    
            elif stream_mode == "updates":
                if isinstance(payload, dict):
                    for node_name, node_data in payload.items():
                        if isinstance(node_data, dict) and "structured_response" in node_data:
                            final_state = node_data

        if final_state and "structured_response" in final_state:
            task_logger.log_complete(success=True)
            return final_state["structured_response"].model_dump()

        task_logger.log_complete(success=False)
        return {}
    
    def _process_and_log_chunk(self, payload, logger: TaskLogger):
        """
        解析并记录流式输出。
        
        Args:
            payload: (message_obj, metadata) 二元组
            logger: TaskLogger 实例
        """
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
            
        message_obj, metadata = payload
        
        if hasattr(message_obj, 'content'):
            has_stream_tools = hasattr(message_obj, 'tool_call_chunks') and message_obj.tool_call_chunks
            has_normal_tools = hasattr(message_obj, 'tool_calls') and message_obj.tool_calls

            content = str(message_obj.content)
            if content.strip():
                logger.log_thinking(content)

            if has_stream_tools or has_normal_tools:
                tools = message_obj.tool_call_chunks if has_stream_tools else message_obj.tool_calls
                for tool in tools:
                    tool_name = tool.get('name')
                    if tool_name:
                        logger.log_tool_call(tool_name, tool.get('args'))
                        return
        
        if hasattr(message_obj, 'name') and hasattr(message_obj, 'content') and getattr(message_obj, 'type', None) == "tool":
            content = str(message_obj.content)
            logger.log_tool_result(message_obj.name, content)


def get_subagent(task_type: str, llm, raw_input: str = None) -> SubAgent:
    """
    获取指定类型的 subagent。
    
    Args:
        task_type: Agent 类型（如 "meeting", "email"）
        llm: LLM 实例
    
    Returns:
        SubAgent 实例
    
    Raises:
        ValueError: 如果 task_type 未注册
    """
    return AgentFactory.create(task_type, llm, raw_input)


def initialize_skills(skills_dir: str, subagent_dir: str) -> None:
    """
    初始化 skills 和 subagents，加载所有定义并注册 Agent。
    
    应在系统启动时调用。
    
    Args:
        skills_dir: skills 目录路径
        subagent_dir: subagent_skills 目录路径
    """
    SkillLoader.scan_all(skills_dir, subagent_dir)
    
    subagents = SkillMemory.get_all_subagents()
    AgentFactory.register_from_subagents(subagents)
