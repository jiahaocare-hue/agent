def format_task_for_display(task: dict) -> str:
    lines = []
    lines.append(f"  任务ID: {task.get('task_id', 'N/A')}")
    lines.append(f"  任务名称: {task.get('task_name', 'N/A')}")
    lines.append(f"  任务类型: {task.get('task_type', 'N/A')}")
    lines.append(f"  当前状态: {task.get('status', 'N/A')}")
    
    created_at = task.get('created_at')
    if created_at:
        lines.append(f"  创建时间: {created_at}")
    
    if task.get('scheduled_at'):
        lines.append(f"  计划执行时间: {task.get('scheduled_at')}")
    
    if task.get('repeat_type'):
        lines.append(f"  重复类型: {task.get('repeat_type')}")
    
    return '\n'.join(lines)


def format_tasks_table(tasks: list[dict]) -> str:
    if not tasks:
        return "没有任务"
    
    headers = ['ID', '名称', '类型', '状态', '创建时间']
    col_widths = [6, 20, 12, 10, 20]
    
    header_line = '  '.join(h.ljust(w) for h, w in zip(headers, col_widths))
    separator = '  '.join('-' * w for w in col_widths)
    
    lines = [header_line, separator]
    
    for task in tasks:
        task_id = str(task.get('task_id', 'N/A')).ljust(col_widths[0])
        task_name = str(task.get('task_name', 'N/A'))[:col_widths[1]].ljust(col_widths[1])
        task_type = str(task.get('task_type', 'N/A'))[:col_widths[2]].ljust(col_widths[2])
        status = str(task.get('status', 'N/A')).ljust(col_widths[3])
        created_at = str(task.get('created_at', 'N/A'))[:col_widths[4]].ljust(col_widths[4])
        
        row = f"{task_id}  {task_name}  {task_type}  {status}  {created_at}"
        lines.append(row)
    
    return '\n'.join(lines)


def prompt_confirmation(message: str) -> bool:
    print(message)
    print()
    user_input = input("输入 y/yes 确认: ").strip().lower()
    return user_input in ('y', 'yes', '确认')


class CommandParser:
    QUERY_ALIASES = {
        'running': 'running',
        'r': 'running',
        'pending': 'pending',
        'p': 'pending',
        'completed': 'completed',
        'c': 'completed',
        'scheduled': 'scheduled',
        's': 'scheduled',
    }

    def parse(self, user_input: str) -> dict:
        if not user_input.startswith("/"):
            return {"is_command": False}
        
        command_str = user_input[1:].strip()
        if not command_str:
            return {"is_command": False, "error": "命令不能为空"}
        
        parts = command_str.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in self.QUERY_ALIASES:
            return {
                "is_command": True,
                "command_type": "query",
                "target": self.QUERY_ALIASES[cmd],
            }
        elif cmd == "cancel":
            if not args:
                return {"is_command": False, "error": "cancel 命令需要指定任务ID或 'all <status>'"}
            
            if args[0].lower() == "all":
                if len(args) < 2:
                    return {"is_command": False, "error": "cancel all 需要指定状态 (scheduled/running/pending)"}
                status = args[1].lower()
                valid_statuses = ('scheduled', 'running', 'pending')
                if status not in valid_statuses:
                    return {"is_command": False, "error": f"无效状态 '{status}'，支持: {valid_statuses}"}
                return {
                    "is_command": True,
                    "command_type": "cancel",
                    "target": "batch",
                    "params": {"status": status},
                }
            else:
                task_ids = []
                invalid_ids = []
                for arg in args:
                    try:
                        task_ids.append(int(arg))
                    except ValueError:
                        invalid_ids.append(arg)
                
                if invalid_ids:
                    return {"is_command": False, "error": f"无效的任务ID: {', '.join(invalid_ids)}"}
                
                return {
                    "is_command": True,
                    "command_type": "cancel",
                    "target": "multiple",
                    "params": {"task_ids": task_ids},
                }
        elif cmd in ("clear", "cls"):
            return {
                "is_command": True,
                "command_type": "clear",
                "target": "memory",
            }
        elif cmd in ("help", "h"):
            return {
                "is_command": True,
                "command_type": "help",
                "target": None,
            }
        elif cmd in ("reset-workflows", "rw"):
            return {
                "is_command": True,
                "command_type": "reset_workflows",
                "target": None,
            }
        elif cmd in ["delete-workflow", "dw"]:
            if not args:
                return {"is_command": False, "error": "请指定要删除的 task_id，例如: /delete-workflow 123"}
            return {
                "is_command": True,
                "command_type": "delete_workflow",
                "target": args[0],
            }
        elif cmd == "config":
            if not args:
                return {"is_command": True, "command_type": "config", "action": "list"}
            
            action = args[0].lower()
            if action == "list":
                return {"is_command": True, "command_type": "config", "action": "list"}
            elif action == "get":
                if len(args) < 2:
                    return {"is_command": False, "error": "用法: /config get <key>"}
                return {"is_command": True, "command_type": "config", "action": "get", "key": args[1]}
            elif action == "set":
                if len(args) < 3:
                    return {"is_command": False, "error": "用法: /config set <key> <value>"}
                return {"is_command": True, "command_type": "config", "action": "set", "key": args[1], "value": " ".join(args[2:])}
            else:
                return {"is_command": False, "error": "用法: /config [list|get <key>|set <key> <value>]"}
        else:
            return {"is_command": False, "error": f"未知命令: {cmd}"}


class CommandExecutor:
    def __init__(self, engine):
        self.engine = engine

    def execute(self, parsed_command: dict) -> str:
        command_type = parsed_command.get('command_type')
        target = parsed_command.get('target')
        params = parsed_command.get('params', {})

        if command_type == 'query':
            return self.execute_query(target)
        elif command_type == 'cancel':
            if target == 'multiple':
                return self.execute_cancel(params.get('task_ids'))
            elif target == 'batch':
                return self.execute_cancel_batch(params.get('status'))
            else:
                return f"无效的取消目标: {target}"
        elif command_type == 'clear':
            return self.execute_clear()
        elif command_type == 'help':
            return self.execute_help()
        elif command_type == 'reset_workflows':
            return self.execute_reset_workflows()
        elif command_type == 'delete_workflow':
            return self.execute_delete_workflow(target)
        elif command_type == 'config':
            return self.execute_config(
                parsed_command.get('action', 'list'),
                parsed_command.get('key'),
                parsed_command.get('value')
            )
        else:
            return f"未知命令类型: {command_type}"

    def execute_query(self, status: str) -> str:
        tasks = self.engine.repo.get_tasks_by_status(status)
        return format_tasks_table(tasks)

    def execute_cancel(self, task_ids: list[int]) -> str:
        if not task_ids:
            return "没有指定要取消的任务"
        
        if len(task_ids) == 1:
            task_id = task_ids[0]
            task = self.engine.repo.get_task(task_id)
            if task is None:
                return f"任务 {task_id} 不存在"

            status = task.get('status')
            terminal_statuses = ('completed', 'failed', 'cancelled')
            if status in terminal_statuses:
                return f"任务 {task_id} 已处于终态 '{status}'，无法取消"

            task_info = format_task_for_display(task)
            message = f"确认取消以下任务？\n{task_info}"

            if not prompt_confirmation(message):
                return "取消操作已取消"

            success, result = self.engine.cancel_task(task_id)
            return result
        
        results = []
        terminal_statuses = ('completed', 'failed', 'cancelled')
        
        valid_tasks = []
        for task_id in task_ids:
            task = self.engine.repo.get_task(task_id)
            if task is None:
                results.append(f"任务 {task_id}: 不存在")
            elif task.get('status') in terminal_statuses:
                results.append(f"任务 {task_id}: 已处于终态 '{task.get('status')}'，无法取消")
            else:
                valid_tasks.append(task)
        
        if not valid_tasks:
            return "没有可取消的任务\n" + "\n".join(results)
        
        message = f"确认取消 {len(valid_tasks)} 个任务？\n"
        message += f"任务ID: {', '.join(str(t['task_id']) for t in valid_tasks)}"
        
        if not prompt_confirmation(message):
            return "取消操作已取消"
        
        for task in valid_tasks:
            task_id = task['task_id']
            success, result = self.engine.cancel_task(task_id)
            status = "成功" if success else "失败"
            results.append(f"任务 {task_id}: {status} - {result}")
        
        return "\n".join(results)

    def execute_cancel_batch(self, status: str) -> str:
        valid_statuses = ('scheduled', 'running', 'pending', 'all_active')
        if status not in valid_statuses:
            return f"无效的状态 '{status}'，支持的状态: {valid_statuses}"

        if status == 'all_active':
            count = 0
            for s in ('scheduled', 'pending', 'blocked', 'running'):
                count += self.engine.repo.count_by_status(s)
        else:
            count = self.engine.repo.count_by_status(status)

        if count == 0:
            return f"没有 '{status}' 状态的任务"

        message = f"确认取消 {count} 个 '{status}' 状态的任务？"

        if not prompt_confirmation(message):
            return "取消操作已取消"

        cancelled_count, result = self.engine.cancel_tasks_by_status(status)
        return result

    def execute_clear(self) -> str:
        """清除 MainAgent 的历史记忆（清空 checkpoints 表数据）"""
        import sqlite3
        from config import settings
        
        db_path = settings.main_agent_checkpoint_db
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM checkpoints")
            count = cursor.fetchone()[0]
            
            if count == 0:
                conn.close()
                return "记忆库为空，无需清除。"
            
            message = f"当前记忆库有 {count} 条记录，确认清除吗？"
            
            if not prompt_confirmation(message):
                conn.close()
                return "清除操作已取消"
            
            cursor.execute("DELETE FROM checkpoints")
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            return f"已清除 MainAgent 的历史记忆（删除了 {deleted_count} 条记录）。"
            
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                return "历史记忆表不存在，无需清除。"
            return f"清除失败: {str(e)}"
        except Exception as e:
            return f"清除失败: {str(e)}"

    def execute_help(self) -> str:
        help_text = """可用命令:
  /running, /r                    - 查看运行中的任务
  /pending, /p                    - 查看待执行的任务
  /completed, /c                  - 查看已完成的任务
  /scheduled, /s                  - 查看定时任务
  /cancel <task_id> [task_id2]... - 取消指定任务（支持多个，如 /cancel 1 2 3）
  /cancel all <status>            - 批量取消任务 (status: scheduled/running/pending)
  /clear, /cls                    - 清除 MainAgent 的历史记忆
  /reset-workflows, /rw           - 清空成功工作流案例库
  /delete-workflow <task_id>, /dw <task_id> - 删除指定任务的 workflow 记录
  /config                         - 查看所有配置
  /config get <key>               - 查看指定配置
  /config set <key> <value>       - 修改配置
  /help, /h                       - 显示帮助信息"""
        return help_text

    def execute_reset_workflows(self) -> str:
        """清空 ChromaDB 中的成功工作流案例库"""
        from vector_store import WorkflowVectorStore
        
        try:
            store = WorkflowVectorStore()
            count = store.count()
            
            if count == 0:
                return "成功工作流案例库为空，无需清空。"
            
            message = f"确认清空成功工作流案例库？当前有 {count} 条记录。"
            
            if not prompt_confirmation(message):
                return "操作已取消"
            
            deleted_count = store.clear()
            return f"已清空成功工作流案例库（删除了 {deleted_count} 条记录）。"
        except Exception as e:
            return f"清空失败: {str(e)}"

    def execute_delete_workflow(self, task_id_str: str) -> str:
        """删除指定任务的 workflow 记录"""
        try:
            task_id = int(task_id_str)
        except ValueError:
            return f"无效的 task_id: {task_id_str}，请输入有效的数字"
        
        from database import WorkflowRepository
        repo = WorkflowRepository(self.task_repo.db_path)
        
        workflow = repo.get_workflow(task_id)
        if not workflow:
            return f"task_id {task_id} 没有对应的 workflow 记录"
        
        success = repo.delete_workflow(task_id)
        if success:
            return f"已删除 task_id {task_id} 的 workflow 记录"
        else:
            return f"删除 task_id {task_id} 的 workflow 记录失败"

    def execute_config(self, action: str, key: str = None, value: str = None) -> str:
        """执行配置管理命令"""
        from config import settings, get_config_schema, get_all_settings, update_setting
        
        if action == "list":
            lines = ["当前配置:\n"]
            all_settings = get_all_settings()
            schema = get_config_schema()
            
            for k, v in all_settings.items():
                desc = schema.get(k, {}).get("description", "")
                is_sensitive = schema.get(k, {}).get("sensitive", False)
                display_value = "******" if is_sensitive and str(v) else str(v)
                lines.append(f"  {k}: {display_value}")
                if desc:
                    lines.append(f"    ({desc})")
            
            return "\n".join(lines)
        
        elif action == "get":
            if key is None:
                return "请指定配置项名称，用法: /config get <key>"
            
            schema = get_config_schema()
            if key not in schema:
                available = ", ".join(schema.keys())
                return f"未知配置项: {key}\n可用的配置项: {available}"
            
            if not hasattr(settings, key):
                return f"配置项 '{key}' 不存在"
            
            current_value = getattr(settings, key)
            is_sensitive = schema.get(key, {}).get("sensitive", False)
            display_value = "******" if is_sensitive else str(current_value)
            desc = schema.get(key, {}).get("description", "")
            
            return f"{key}: {display_value}\n  ({desc})"
        
        elif action == "set":
            if key is None or value is None:
                return "用法: /config set <key> <value>"
            
            success, message = update_setting(key, value)
            return message
        
        else:
            return f"未知操作: {action}"
