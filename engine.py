import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Union, Dict

from config import settings
from database import TaskRepository, WorkflowRepository
from graph_executor import GraphExecutor
from mcp_manager import MCPManager
from recovery_manager import RecoveryManager
from subagent import get_subagent
from timer_scheduler import TimerScheduler
from vector_store import WorkflowVectorStore
from logging_config import get_logger

logger = get_logger(__name__)


class UserCancelledException(Exception):
    """用户取消操作异常"""
    pass


def validate_workflow_resources(workflow_json: dict) -> list:
    """
    验证工作流中的资源是否存在。
    
    Args:
        workflow_json: 工作流 JSON
    
    Returns:
        错误消息列表，空列表表示验证通过
    """
    errors = []
    nodes = workflow_json.get("nodes", [])
    
    for node in nodes:
        node_id = node.get("node_id", "unknown")
        action_type = node.get("action_type", "")
        
        if action_type == "script":
            script_action = node.get("script_action", {})
            script_path = script_action.get("script_path", "")
            
            if script_path:
                if not os.path.exists(script_path):
                    errors.append(f"节点 '{node_id}': 脚本路径不存在: {script_path}")
            else:
                errors.append(f"节点 '{node_id}': 缺少 script_path")
        
        elif action_type == "tool":
            tool_action = node.get("tool_action", {})
            tool_name = tool_action.get("tool_name", "")
            
            if tool_name:
                parts = tool_name.split(".")
                if len(parts) != 2:
                    errors.append(f"节点 '{node_id}': tool_name 格式错误，应为 'module_name.function_name': {tool_name}")
                else:
                    module_name, func_name = parts
                    if module_name not in MCPManager._modules:
                        errors.append(f"节点 '{node_id}': MCP 模块不存在: {module_name}")
                    elif func_name not in MCPManager._modules[module_name]:
                        available_funcs = list(MCPManager._modules[module_name].keys())
                        errors.append(f"节点 '{node_id}': MCP 工具不存在: {func_name}，模块 {module_name} 可用工具: {available_funcs}")
            else:
                errors.append(f"节点 '{node_id}': 缺少 tool_name")
    
    return errors


class BackendEngine:
    def __init__(
        self,
        max_workers: int = 3,
        llm=None,
        repo: Optional[TaskRepository] = None,
    ):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.event = threading.Event()
        self.running = False
        self.repo = repo or TaskRepository()
        self._thread = None
        self._active_tasks: set[int] = set()
        self._lock = threading.Lock()
        self.timer_scheduler = TimerScheduler(self.repo, self.wakeup)
        self.recovery_manager = RecoveryManager(self.repo, self.timer_scheduler)
        self.llm = llm or self._create_default_llm()
        self.vector_store = WorkflowVectorStore()

    def _create_default_llm(self):
        from langchain_openai import ChatOpenAI
        
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY 未配置，请在 .env 文件中设置")
        
        return ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )

    def start(self):
        self.running = True
        self.timer_scheduler.start()
        self.recovery_manager.recover_all()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self.timer_scheduler.stop()
        self.event.set()
        if self._thread:
            self._thread.join()
        self.executor.shutdown(wait=True)

    def wakeup(self):
        self.event.set()

    def _scheduler_loop(self):
        while self.running:
            self.event.wait(timeout=5)
            self.event.clear()
            if self.running:
                self._dispatch_pending_tasks()

    def _all_dependencies_met(self, task: dict) -> bool:
        deps_str = task.get('dependencies')
        if not deps_str:
            return True
        deps = json.loads(deps_str)
        for dep_id in deps:
            dep_task = self.repo.get_task(dep_id)
            if not dep_task or dep_task.get('status') != 'completed':
                return False
        return True

    def _check_and_unblock_tasks(self):
        blocked_tasks = self.repo.get_tasks_by_status('blocked')
        for task in blocked_tasks:
            if self._all_dependencies_met(task):
                self.repo.update_status(task['task_id'], 'pending')
                logger.info(f"Unblocked task {task['task_id']} ({task['task_name']})")

    def _dispatch_pending_tasks(self):
        with self._lock:
            available_slots = self.max_workers - len(self._active_tasks)
            if available_slots <= 0:
                return

        self._check_and_unblock_tasks()

        tasks = self.repo.get_pending_tasks(limit=available_slots)
        for task in tasks:
            with self._lock:
                if len(self._active_tasks) >= self.max_workers:
                    break
                self._active_tasks.add(task['task_id'])
            self._submit_task(task)

    def _submit_task(self, task: dict):
        self.repo.update_status(task['task_id'], 'running')
        future = self.executor.submit(self._run_task, task)
        future.add_done_callback(lambda f: self._on_task_done(f, task['task_id']))

    def _get_existing_workflow(
        self,
        task_id: int,
        parent_task_id: Optional[int],
        graph_executor,
        workflow_repo,
    ) -> Optional[dict]:
        """获取现有工作流（恢复或父任务）"""
        existing_workflow = graph_executor.get_workflow(task_id)
        if existing_workflow:
            logger.info(f"Found existing workflow for task {task_id} (recovery)")
            return existing_workflow.get('workflow_json')
        
        if parent_task_id:
            parent_workflow = workflow_repo.get_workflow(parent_task_id)
            if parent_workflow:
                logger.info(f"Using workflow from parent task {parent_task_id}")
                return parent_workflow.get('workflow_json')
        
        return None

    def _generate_workflow_with_retry(
        self,
        subagent,
        raw_input: str,
        thread_id: str,
        task_id: int,
        max_retries: int = 5,
    ) -> dict:
        """生成工作流（带重试）"""
        from graph_executor import validate_workflow_graph
        from human_loop import show_missing_params_dialog
        
        current_message = raw_input
        
        for attempt in range(max_retries):
            try:
                workflow_json = subagent.generate_workflow_with_logging(
                    current_message,
                    thread_id=thread_id,
                    task_id=task_id,
                )
                
                if not workflow_json.get("can_handle", True):
                    missing_params = workflow_json.get("missing_params", [])
                    reply_message = workflow_json.get("reply_message", "")
                    
                    if missing_params:
                        user_inputs = show_missing_params_dialog(missing_params, reply_message)
                        if user_inputs is None:
                            raise UserCancelledException("用户取消输入")
                        
                        params_str = ", ".join(f"{k}={v}" for k, v in user_inputs.items())
                        current_message = raw_input + f"\n用户补充信息：{params_str}"
                        continue
                    
                    raise Exception(f"Agent 无法处理: {reply_message}")
                
                validate_workflow_graph(workflow_json)
                
                validation_errors = validate_workflow_resources(workflow_json)
                if validation_errors:
                    error_msg = "\n".join(validation_errors)
                    raise Exception(f"资源验证失败:\n{error_msg}")
                
                return workflow_json
                
            except UserCancelledException:
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt + 1}/{max_retries}: {e}")
                    current_message = f"之前生成的工作流有错误，请修正：\n\n{str(e)}"
                else:
                    raise ValueError(f"工作流生成失败: {e}")
        
        return {}

    def _confirm_workflow(
        self,
        workflow_json: dict,
        task_id: int,
        raw_input: str,
    ) -> tuple[Optional[dict], bool]:
        """用户确认工作流"""
        from human_loop import show_workflow_confirmation
        
        workflow_description = workflow_json.get("description")
        current_message = raw_input
        workflow_generated = False
        
        while not workflow_generated:
            user_response = show_workflow_confirmation(
                task_id=task_id,
                workflow_description=workflow_description,
                workflow_json=workflow_json
            )
            
            if user_response["action"] == "approved":
                workflow_generated = True
            elif user_response["action"] == "cancelled":
                self.repo.update_status(task_id, "cancelled")
                logger.info(f"Task {task_id} cancelled by user")
                return None, False
            elif user_response["action"] == "modify":
                modification = user_response["modification"]
                logger.info(f"User requested modification: {modification}")
                return {"action": "modify", "modification": modification}, False
        
        return workflow_json, workflow_generated

    def _generate_workflow_with_confirmation(
        self,
        task_id: int,
        task_type: str,
        raw_input: str,
        parent_task_id: int,
        subagent,
        workflow_repo,
        graph_executor
    ) -> tuple:
        """生成工作流（带重试和用户确认）"""
        from human_loop import show_missing_params_dialog
        
        workflow_json = self._get_existing_workflow(
            task_id, parent_task_id, graph_executor, workflow_repo
        )
        if workflow_json:
            return workflow_json, True
        
        logger.info(f"Generating workflow for task {task_id}...")
        
        thread_id = f"task-{task_id}"
        current_message = raw_input
        
        while True:
            try:
                workflow_json = self._generate_workflow_with_retry(
                    subagent, current_message, thread_id, task_id
                )
                logger.info("generate workflow done")
            except UserCancelledException as e:
                logger.info(f"用户取消操作: {str(e)}")
                return None, False
            
            result, workflow_generated = self._confirm_workflow(
                workflow_json, task_id, current_message
            )
            
            if result is None:
                return None, False
            elif isinstance(result, dict) and result.get("action") == "modify":
                current_message = f"请修改工作流：{result['modification']}"
                continue
            else:
                return workflow_json, workflow_generated

    def _run_task(self, task: dict) -> dict:
        task_id = task['task_id']
        task_type = task.get('task_type', 'general')
        raw_input = task.get('raw_input', '')
        parent_task_id = task.get('parent_task_id')

        logger.info(f"Running task {task_id}: {task['task_name']}")

        try:
            graph_executor = GraphExecutor(self.repo)
            subagent = get_subagent(task_type, self.llm, raw_input)
            workflow_repo = WorkflowRepository(self.repo.db_path)

            workflow_json, workflow_generated = self._generate_workflow_with_confirmation(
                task_id=task_id,
                task_type=task_type,
                raw_input=raw_input,
                parent_task_id=parent_task_id,
                subagent=subagent,
                workflow_repo=workflow_repo,
                graph_executor=graph_executor
            )
            
            if workflow_json is None:
                return {
                    "task_id": task_id,
                    "status": "cancelled",
                    "output": "",
                }

            if workflow_generated:
                logger.info(f"Saving workflow for task {task_id}...")
                graph_executor.save_workflow(task_id, workflow_json)

            logger.info(f"Building graph for task {task_id}...")
            graph = graph_executor.build_graph(workflow_json)

            initial_state = {
                "input": raw_input,
                "output": "",
                "node_outputs": {},
                "task_id": task_id,
                "current_node": "",
            }

            logger.info(f"Executing workflow for task {task_id}...")
            result = graph_executor.execute(graph, initial_state, task_id)

            output = result.get("output", "")
            node_outputs = result.get("node_outputs", {})
            logger.info(f"Task {task_id} completed. Output: {output[:1000]}...")

            task = self.repo.get_task(task_id)
            if task and task.get("status") == "cancelled":
                return {
                    "task_id": task_id,
                    "status": "cancelled",
                    "output": output,
                }

            has_error = any(
                node_output.get("error") is True
                for node_output in node_outputs.values()
                if isinstance(node_output, dict)
            )

            if has_error:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": output,
                }

            return {
                "task_id": task_id,
                "status": "completed",
                "output": output,
                "workflow_json": workflow_json,
            }

        except Exception as e:
            error_msg = f"Task {task_id} failed: {str(e)}"
            logger.error(error_msg)
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
            }

    def _on_task_done(self, future, task_id: int):
        with self._lock:
            self._active_tasks.discard(task_id)

        try:
            result = future.result()
            status = result.get("status", "completed")
            output = result.get("output", "")
            error = result.get("error")
            
            if status == "completed":
                self.repo.update_status(task_id, "completed", output=output)
                
                workflow_json = result.get("workflow_json")
                task = self.repo.get_task(task_id)
                if workflow_json and len(workflow_json.get("nodes", [])) >= 2:
                    self.vector_store.add_workflow(
                        raw_input=task.get("raw_input", ""),
                        workflow_json=workflow_json,
                        task_type=task.get("task_type", "general")
                    )
                    logger.info(f"Saved successful workflow to vector store for task {task_id}")
            elif status == "cancelled":
                self.repo.update_status(task_id, "cancelled")
                logger.info(f"Task {task_id} was cancelled")
            else:
                self.repo.update_status(task_id, "failed", output=output, error=error)
                logger.error(f"Task {task_id} failed: {error}")
            
            self._show_task_complete_popup(task_id, status, output, error)
            
        except Exception as e:
            error_msg = f"Task {task_id} callback error: {str(e)}"
            logger.error(error_msg)
            self.repo.update_status(task_id, "failed", output=str(e), error=str(e))
            self._show_task_complete_popup(task_id, "failed", str(e), str(e))

        self.timer_scheduler.on_task_completed(task_id)
        self.wakeup()
    
    def _show_task_complete_popup(self, task_id: int, status: str, output: str, error: str = None):
        """显示任务完成弹窗"""
        try:
            import subprocess
            import sys
            from human_loop import get_popup_worker_path
            
            payload = {
                "type": "task_complete",
                "task_id": task_id,
                "status": status,
                "output": output,
                "error": error
            }
            
            popup_worker_path = get_popup_worker_path()
            process = subprocess.run(
                [sys.executable, popup_worker_path],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=120
            )
        except subprocess.TimeoutExpired:
            logger.info(f"任务完成弹窗超时，已自动关闭")
        except Exception as e:
            logger.error(f"显示任务完成弹窗失败: {e}")

    def get_status(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "active_tasks": len(self._active_tasks),
                "max_workers": self.max_workers,
            }

    def schedule_task(self, task_id: int, scheduled_at):
        self.timer_scheduler.schedule_task(task_id, scheduled_at)

    def cancel_task(self, task_id: int) -> tuple[bool, str]:
        task = self.repo.get_task(task_id)
        if task is None:
            return (False, f"任务 {task_id} 不存在")

        status = task.get('status')
        terminal_statuses = ('completed', 'failed', 'cancelled')

        if status in terminal_statuses:
            return (False, f"任务 {task_id} 已处于终态 '{status}'，无法取消")

        if status == 'pending':
            self.repo.update_status(task_id, 'cancelled')
            return (True, f"任务 {task_id} 已取消（pending 状态）")

        elif status == 'running':
            self.repo.update_status(task_id, 'cancelled')
            return (True, f"任务 {task_id} 已标记为取消（running 状态，GraphExecutor 将检测状态安全退出）")

        elif status == 'scheduled':
            self.timer_scheduler.cancel_schedule(task_id)
            self.repo.update_status(task_id, 'cancelled')
            return (True, f"任务 {task_id} 已取消（scheduled 状态，定时器已取消）")

        elif status == 'blocked':
            self.repo.update_status(task_id, 'cancelled')
            cancelled_downstream = self._cancel_downstream_tasks(task_id)
            if cancelled_downstream:
                return (True, f"任务 {task_id} 已取消（blocked 状态），级联取消下游任务: {cancelled_downstream}")
            return (True, f"任务 {task_id} 已取消（blocked 状态）")

        else:
            return (False, f"任务 {task_id} 状态 '{status}' 无法识别，取消失败")

    def _cancel_downstream_tasks(self, task_id: int) -> list[int]:
        dependent_tasks = self.repo.get_tasks_depending_on(task_id)
        cancelled_ids = []

        for task in dependent_tasks:
            dep_task_id = task['task_id']
            success, _ = self.cancel_task(dep_task_id)
            if success:
                cancelled_ids.append(dep_task_id)

        return cancelled_ids

    def cancel_tasks_by_status(self, status: str) -> tuple[int, str]:
        valid_statuses = ('scheduled', 'running', 'pending', 'all_active')

        if status not in valid_statuses:
            return (0, f"无效的状态 '{status}'，支持的状态: {valid_statuses}")

        cancelled_count = 0

        if status == 'all_active':
            for s in ('scheduled', 'pending', 'blocked', 'running'):
                tasks = self.repo.get_tasks_by_status(s)
                for task in tasks:
                    task_id = task['task_id']
                    success, _ = self.cancel_task(task_id)
                    if success:
                        cancelled_count += 1
        else:
            tasks = self.repo.get_tasks_by_status(status)
            for task in tasks:
                task_id = task['task_id']
                success, _ = self.cancel_task(task_id)
                if success:
                    cancelled_count += 1

        return (cancelled_count, f"已取消 {cancelled_count} 个 '{status}' 状态的任务")
