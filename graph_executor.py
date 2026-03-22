import re
import subprocess
import json
import sys
import os
from contextlib import ExitStack, closing
from typing import Annotated, Dict, Any, List, Optional, Literal, TypedDict
import sqlite3

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel, Field

from database import TaskRepository, WorkflowRepository
from mcp_manager import MCPManager
from logging_config import get_logger
from config import settings

logger = get_logger(__name__)


def validate_workflow_graph(workflow_json: dict) -> bool:
    edges = workflow_json.get("edges", [])
    nodes = {node["node_id"] for node in workflow_json.get("nodes", [])}
    
    has_end = False
    for edge in edges:
        if edge.get("target") == "END":
            has_end = True
            break
        if edge.get("is_conditional"):
            routing_map = edge.get("routing_map", {})
            if "END" in routing_map.values():
                has_end = True
                break
    
    if not has_end:
        raise ValueError("图结构错误：没有找到任何指向 'END' 的连线！你必须确保工作流能正常结束。")
    
    has_start = any(edge.get("source") == "START" for edge in edges)
    if not has_start:
        raise ValueError("图结构错误：没有找到从 'START' 出发的连线！")
    
    for edge in edges:
        if edge.get("source") == edge.get("target") and edge.get("is_conditional") is not True:
            raise ValueError(f"图结构错误：检测到节点 '{edge.get('source')}' 存在无限死循环（自己连自己）！")
        
        src, tgt = edge.get("source"), edge.get("target")
        if src != "START" and src not in nodes:
            raise ValueError(f"图结构错误：连线的起点 '{src}' 在 nodes 列表中不存在！")
        
        if edge.get("is_conditional"):
            routing_map = edge.get("routing_map", {})
            for target_node in routing_map.values():
                if target_node != "END" and target_node not in nodes:
                    raise ValueError(f"图结构错误：条件边的目标节点 '{target_node}' 在 nodes 列表中不存在！")
        else:
            if tgt != "END" and tgt not in nodes:
                raise ValueError(f"图结构错误：连线的终点 '{tgt}' 在 nodes 列表中不存在！")
    
    conditional_edges = {}
    for edge in edges:
        if edge.get("is_conditional"):
            key = (edge.get("source"), edge.get("condition_variable"))
            if key in conditional_edges:
                raise ValueError(
                    f"图结构错误：节点 '{edge.get('source')}' 的条件变量 '{edge.get('condition_variable')}' "
                    f"存在重复的条件边！请将 routing_map 合并为一条条件边。"
                )
            conditional_edges[key] = edge
    
    return True


def merge_outputs(old_outputs: Dict[str, Any], new_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并节点输出的 reducer 函数
    用于 Annotated 类型，LangGraph 会在每次节点返回时自动调用
    """
    merged = old_outputs.copy()
    merged.update(new_outputs)
    return merged


def keep_last(old: str, new: str) -> str:
    return new

class AgentState(TypedDict):
    input: str
    output: Annotated[str, keep_last]  # 复用 keep_last reducer
    node_outputs: Annotated[Dict[str, Any], merge_outputs]
    task_id: int
    current_node: Annotated[str, keep_last]


class ToolActionDef(BaseModel):
    tool_name: str = Field(description="内部工具的名称")
    tool_kwargs: Dict[str, str] = Field(default_factory=dict, description="传递给工具的参数")


class ScriptActionDef(BaseModel):
    executable: str = Field(description="执行环境: python, bash 等")
    script_path: str = Field(description="脚本文件路径")
    args: List[str] = Field(default_factory=list, description="参数数组")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="环境变量")


class NodeDef(BaseModel):
    node_id: str = Field(description="节点唯一标识")
    action_type: Literal["tool", "script"] = Field(description="动作类型")
    tool_action: Optional[ToolActionDef] = Field(None, description="tool 类型时填充")
    script_action: Optional[ScriptActionDef] = Field(None, description="script 类型时填充")


class EdgeDef(BaseModel):
    source: str = Field(description="起始节点")
    target: Optional[str] = Field(None, description="目标节点")
    is_conditional: bool = Field(False, description="是否条件边")
    condition_variable: Optional[str] = Field(None, description="条件变量")
    routing_map: Optional[Dict[str, str]] = Field(None, description="路由映射")


class WorkflowBlueprint(BaseModel):
    can_handle: bool = Field(
        True,
        description="你当前具备的工具和能力，是否足以完成用户的请求？如果可以生成工作流，设为 true；如果是闲聊、超出能力范围或缺少必要信息，设为 false。"
    )
    reply_message: str = Field(
        default="",
        description="如果你无法处理（can_handle=false），请在这里向用户解释原因；如果可以处理，可以在这里说一句简短的确认。"
    )
    missing_params: List[str] = Field(
        default_factory=list,
        description="缺失的参数列表。例如：['收件人邮箱', '邮件主题']。如果参数齐全，返回空列表。"
    )
    description: Optional[str] = Field(None, description="工作流的人类可读描述，用简洁清晰的中文描述将要执行的操作步骤")
    nodes: List[NodeDef] = Field(default_factory=list, description="节点数组")
    edges: List[EdgeDef] = Field(default_factory=list, description="边数组")


def render_params(raw_value: str, current_state: dict) -> str:
    """
    参数渲染器：将 ${{ state.node_outputs.xxx }} 占位符替换为真实值
    支持嵌套路径：node_outputs.xxx.output, node_outputs.xxx.data.arg1
    """
    pattern = re.compile(r"\$\{\{\s*state\.([\w.]+)\s*\}\}")
    
    def replace_match(match):
        path = match.group(1)
        
        parts = path.split(".")
        value = current_state
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part, "")
            else:
                return match.group(0)
        
        return str(value) if value is not None else ""
    
    return pattern.sub(replace_match, raw_value)


class GraphExecutor:
    def __init__(self, repo: TaskRepository):
        self.repo = repo
        self.workflow_repo = WorkflowRepository(repo.db_path)
        self.tools: Dict[str, callable] = {}
        self._stack = ExitStack()
        custom_serde = JsonPlusSerializer(allowed_msgpack_modules=[
            ('graph_executor', 'WorkflowBlueprint'),
            ('graph_executor', 'NodeDef'),
            ('graph_executor', 'EdgeDef'),
            ('graph_executor', 'ToolActionDef'),
            ('graph_executor', 'ScriptActionDef'),
        ])
        db_dir = os.path.dirname(settings.checkpoint_db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(settings.checkpoint_db_path, check_same_thread=False)
        self.sqlite_conn = self._stack.enter_context(closing(conn))
        self.checkpointer = SqliteSaver(self.sqlite_conn, serde=custom_serde)

    def build_graph(self, workflow_json: dict) -> StateGraph:
        graph = StateGraph(AgentState)

        blueprint = WorkflowBlueprint(**workflow_json)
        nodes = blueprint.nodes
        edges = blueprint.edges

        for node in nodes:
            node_id = node.node_id
            node_func = self._create_node_func(node)
            graph.add_node(node_id, node_func)

        start_targets = []
        for edge in edges:
            if edge.source == "START":
                start_targets.append(edge.target)

        for target in start_targets:
            graph.set_entry_point(target)

        for edge in edges:
            source = edge.source
            target = edge.target

            if source == "START":
                continue

            if edge.is_conditional:
                self._add_conditional_edge(graph, edge)
            elif target == "END":
                graph.add_edge(source, END)
            else:
                graph.add_edge(source, target)

        return graph

    def _get_nested_value(self, state: AgentState, path: str):
        """从嵌套字典中获取值，支持点分隔路径"""
        keys = path.split(".")
        value = state
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _add_conditional_edge(self, graph: StateGraph, edge: EdgeDef):
        condition_variable = edge.condition_variable or "output"
        if condition_variable.startswith("state."):
            condition_variable = condition_variable[6:]
        routing_map = edge.routing_map or {}

        def route_func(state: AgentState) -> str:
            # 1. 首先检查error字段
            error_value = self._get_nested_value(state, f"node_outputs.{edge.source}.error")
            if error_value is True or error_value == "true" or error_value == "True":
                return "__end__"  # 失败时直接结束
            
            # 2. 检查cancelled字段
            cancelled_value = self._get_nested_value(state, f"node_outputs.{edge.source}.cancelled")
            if cancelled_value is True or cancelled_value == "true" or cancelled_value == "True":
                return "__end__"  # 取消时直接结束
            
            # 3. 获取条件变量值
            value = self._get_nested_value(state, condition_variable)
            
            # 4. 如果值不存在，报错（工作流设计问题）
            if value is None:
                raise ValueError(f"条件变量 '{condition_variable}' 的值为空，请检查工作流设计")
            
            # 5. 正常路由匹配
            value_str = str(value).lower()
            for k in routing_map.keys():
                if k.lower() == value_str:
                    return k
            
            # 6. 未匹配到，报错
            raise ValueError(f"条件值 '{value}' 不在 routing_map 中，可用的值: {list(routing_map.keys())}")
        
        route_func.__name__ = f"route_{edge.source}_{condition_variable.replace('.', '_')}"
        
        # 构建完整的路由映射，包含错误路由
        full_routing_map = {k: (END if v == "END" else v) for k, v in routing_map.items()}
        full_routing_map["__end__"] = END  # 错误时直接结束
        
        graph.add_conditional_edges(
            edge.source,
            route_func,
            full_routing_map
        )

    def execute(self, graph: StateGraph, initial_state: dict, task_id: int) -> dict:
        compiled_graph = graph.compile(checkpointer=self.checkpointer)
        config = {"configurable": {"thread_id": str(task_id)}}
        
        existing_state = compiled_graph.get_state(config)
        if existing_state and existing_state.values:
            logger.debug(f"Found checkpoint for task {task_id}, resuming from checkpoint...")
            result = compiled_graph.invoke(None, config)
        else:
            logger.debug(f"No checkpoint found for task {task_id}, starting fresh...")
            logger.info(f"Starting workflow execution...")
            result = compiled_graph.invoke(initial_state, config)
        
        return result

    def save_workflow(self, task_id: int, workflow_json: dict) -> int:
        return self.workflow_repo.save_workflow(task_id, workflow_json)

    def get_workflow(self, task_id: int) -> Optional[dict]:
        return self.workflow_repo.get_workflow(task_id)

    def check_cancellation(self, task_id: int) -> bool:
        task = self.repo.get_task(task_id)
        if task and task.get("status") == "cancelled":
            return True
        return False

    def _create_node_func(self, node_def: NodeDef):
        def node_func(state: AgentState) -> dict:
            node_id = node_def.node_id
            task_id = state.get("task_id", 0)
            
            logger.debug(f"Executing node: {node_id}")
            
            if self.check_cancellation(task_id):
                return {
                    "output": "Task cancelled",
                    "node_outputs": {
                        node_id: {
                            "output": "cancelled",
                            "cancelled": True
                        }
                    }
                }
            
            result = self._execute_node(node_def, state)
            
            if isinstance(result, dict):
                node_output = result.copy()
                if "output" not in node_output:
                    node_output["output"] = str(result)
            else:
                node_output = {"output": str(result)}
            
            import json
            logger.debug(f"Node output: {json.dumps(node_output, ensure_ascii=False)[:300]}")
            
            return {
                "current_node": node_id,
                "output": node_output["output"],
                "node_outputs": {node_id: node_output}
            }
        
        return node_func

    def _execute_node(self, node_def: NodeDef, state: AgentState) -> dict:
        if node_def.action_type == "tool":
            return self._execute_tool(node_def.tool_action, state)
        elif node_def.action_type == "script":
            return self._execute_script(node_def.script_action, state)
        else:
            return {"output": f"Unknown action type: {node_def.action_type}", "error": True}

    def _execute_tool(self, tool_action: Optional[ToolActionDef], state: AgentState) -> dict:
        if not tool_action:
            return {"output": "Tool action is None", "error": True}

        tool_name = tool_action.tool_name
        kwargs = {
            k: render_params(str(v), state)
            for k, v in tool_action.tool_kwargs.items()
        }

        logger.info(f"Calling MCP tool: {tool_name}({kwargs})")

        try:
            module_name, function_name = tool_name.split(".", 1)
            result = MCPManager.call(module_name, function_name, kwargs)
            if isinstance(result, dict):
                return result
            return {"output": str(result)}
        except ValueError as e:
            return {"output": f"MCP call error: {str(e)}", "error": True}
        except Exception as e:
            return {"output": f"Tool error: {str(e)}", "error": True}

    def smart_decode(self, raw_bytes: bytes) -> str:
        if not raw_bytes:
            return ""
        try:
            return raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return raw_bytes.decode('gbk', errors='replace')

    def _execute_script(self, script_action: Optional[ScriptActionDef], state: AgentState) -> dict:
        if not script_action:
            return {"output": "Script action is None", "error": True}

        executable = script_action.executable
        script_path = script_action.script_path
        args = [render_params(arg, state) for arg in script_action.args]
        env_vars = script_action.env_vars

        if executable == "python":
            executable = sys.executable

        if script_path:
            command_list = [executable, script_path] + args
        else:
            command_list = [executable] + args
        logger.info(f"Executing script: {command_list}")

        try:
            import os
            env = os.environ.copy()
            env.update(env_vars)

            result = subprocess.run(
                command_list,
                capture_output=True,
                env=env,
                stdin=subprocess.DEVNULL,
            )

            stdout = self.smart_decode(result.stdout).strip()
            stderr = self.smart_decode(result.stderr).strip()
            
            logger.debug(f"Script stdout: {stdout[:500]}")
            if stderr:
                logger.debug(f"Script stderr: {stderr[:500]}")

            if result.returncode == 0:
                try:
                    parsed = json.loads(stdout)
                    if isinstance(parsed, dict):
                        parsed.setdefault("output", stdout)
                        return parsed
                except json.JSONDecodeError:
                    pass
                return {"output": stdout}
            else:
                return {"output": f"Script error (code {result.returncode}): {stderr}", "error": True}
        except FileNotFoundError:
            return {"output": f"Script not found: {script_path}", "error": True}
        except Exception as e:
            return {"output": f"Execution error: {str(e)}", "error": True}
