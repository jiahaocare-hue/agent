import subprocess
import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional


def get_popup_worker_path() -> str:
    popup_worker = Path(__file__).parent / "popup_worker.py"
    return str(popup_worker)


def show_missing_params_dialog(
    missing_params: List[str],
    reply_message: str
) -> Optional[Dict[str, str]]:
    """
    显示缺失参数弹窗，让用户输入。
    
    Args:
        missing_params: 缺失的参数名称列表
        reply_message: Agent 的说明消息
    
    Returns:
        用户输入的参数字典，如果取消则返回 None
    
    Note:
        超时时返回空参数字典 {}，允许工作流继续执行
    """
    try:
        popup_worker_path = get_popup_worker_path()
        
        payload = {
            "type": "missing_params",
            "missing_params": missing_params,
            "reply_message": reply_message
        }
        payload_str = json.dumps(payload, ensure_ascii=False)
        my_env = os.environ.copy()
        my_env["PYTHONIOENCODING"] = "utf-8"
        
        process = subprocess.run(
            [sys.executable, popup_worker_path],
            input=payload_str,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300,
            errors='replace',
            env=my_env
        )
        
        if process.returncode == 0 and process.stdout.strip():
            result = json.loads(process.stdout.strip())
            if result.get("action") == "confirmed":
                return result.get("params", {})
            else:
                return None
        else:
            print(f"弹窗进程返回错误码或无输出: {process.stderr}")
            return {}
            
    except subprocess.TimeoutExpired:
        print("弹窗超时，使用空参数继续执行")
        return {}
    except Exception as e:
        print(f"启动弹窗进程失败: {e}")
        return {}


def translate_workflow_to_human_readable(workflow_json: dict) -> list:
    """
    将工作流 JSON 翻译为人可读的步骤列表
    
    Args:
        workflow_json: 工作流 JSON，包含 nodes 和 edges
    
    Returns:
        步骤列表，如 ["1. 执行脚本: python -c 'print(你好)'", "2. 调用工具: send_email"]
    """
    steps = []
    nodes = workflow_json.get("nodes", [])
    edges = workflow_json.get("edges", [])
    
    node_map = {n["node_id"]: n for n in nodes}
    
    start_nodes = [e["target"] for e in edges if e["source"] == "START"]
    
    visited = set()
    queue = start_nodes.copy()
    ordered_nodes = []
    
    while queue:
        node_id = queue.pop(0)
        if node_id in visited or node_id == "END":
            continue
        visited.add(node_id)
        if node_id in node_map:
            ordered_nodes.append(node_map[node_id])
        for e in edges:
            if e["source"] == node_id and e["target"] not in visited:
                queue.append(e["target"])
    
    for i, node in enumerate(ordered_nodes, 1):
        node_id = node.get("node_id", "unknown")
        action = node.get("action_type", "unknown")
        
        if action == "script":
            script = node.get("script_action", {})
            executable = script.get("executable", "")
            args = " ".join(script.get("args", []))
            steps.append(f"{i}. 执行脚本: {executable} {args}")
        elif action == "tool":
            tool = node.get("tool_action", {})
            tool_name = tool.get("tool_name", "未知工具")
            kwargs = tool.get("tool_kwargs", {})
            kwargs_str = ", ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
            steps.append(f"{i}. 调用工具: {tool_name}({kwargs_str})")
        else:
            steps.append(f"{i}. 执行节点: {node_id} ({action})")
    
    return steps


def show_workflow_confirmation(
    task_id: int,
    workflow_description: str,
    workflow_json: dict
) -> dict:
    """
    显示工作流确认弹窗（通过独立进程）
    
    Args:
        task_id: 任务 ID
        workflow_description: 工作流的人类可读描述
        workflow_json: 原始工作流 JSON
    
    Returns:
        {"action": "approved" | "cancelled" | "modify", "modification": str}
    
    Note:
        超时时默认执行（approved）
    """
    default_result = {"action": "approved", "modification": None}
    
    try:
        popup_worker_path = get_popup_worker_path()
        
        payload = {
            "task_id": str(task_id),
            "description": workflow_description,
            "workflow_json": json.dumps(workflow_json, ensure_ascii=False)
        }
        payload_str = json.dumps(payload, ensure_ascii=False)
        my_env = os.environ.copy()
        my_env["PYTHONIOENCODING"] = "utf-8"
        
        process = subprocess.run(
            [sys.executable, popup_worker_path],
            input=payload_str,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300,
            errors='replace',
            env=my_env
        )
        
        if process.returncode == 0 and process.stdout.strip():
            result = json.loads(process.stdout.strip())
            return result
        else:
            print(f"弹窗进程返回错误码或无输出: {process.stderr}")
            return default_result
            
    except subprocess.TimeoutExpired:
        print("弹窗超时，自动执行")
        return default_result
    except Exception as e:
        print(f"启动弹窗进程失败: {e}")
        return default_result
