from datetime import datetime
from pathlib import Path


class TaskLogger:
    """
    任务日志记录器，支持控制台和文件双重输出。
    
    使用方式：
        logger = TaskLogger(task_id)
        logger.log_thinking("开始分析任务...")
        logger.log_tool_call("read_skill", {"agent_type": None})
        logger.log_tool_result("read_skill", "技能文档内容...")
    """
    
    def __init__(self, task_id: int, log_dir: str = "logs"):
        self.task_id = task_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"task_{task_id}.log"
        self.prefix = f"[Task {task_id}]"
    
    def _write_file(self, content: str):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(content)
            f.flush()
    
    def _print_console(self, content: str):
        pass
        # print(content)
    
    def log_thinking(self, content: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._print_console(f"{self.prefix}[{timestamp}] 🤔 思考: {content[:100]}")
        self._write_file(f"[{timestamp}] LLM_THINKING:\n{content}\n\n")
    
    def log_tool_call(self, tool_name: str, args: dict = None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._print_console(f"{self.prefix}[{timestamp}] 🔧 调用工具: {tool_name}")
        args_str = str(args) if args else "{}"
        self._write_file(f"[{timestamp}] TOOL_CALL: {tool_name}\n  args: {args_str}\n\n")
    
    def log_tool_result(self, tool_name: str, content: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._print_console(f"{self.prefix}[{timestamp}] 📥 工具返回 ({tool_name}): {content[:100]}")
        self._write_file(f"[{timestamp}] TOOL_RESULT: {tool_name}\n  {content}\n\n")
    
    def log_response(self, content: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._print_console(f"{self.prefix}[{timestamp}] 📤 响应: {content[:100]}")
        self._write_file(f"[{timestamp}] LLM_RESPONSE:\n{content}\n\n")
    
    def log_complete(self, success: bool = True):
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "✅ 完成" if success else "❌ 失败"
        self._print_console(f"{self.prefix}[{timestamp}] {status}")
        self._write_file(f"[{timestamp}] TASK_{status}\n")
