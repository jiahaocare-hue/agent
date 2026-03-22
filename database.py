import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class TaskRepository:
    def __init__(self, db_path: str = None):
        if db_path is None:
            from config import settings
            db_path = settings.tasks_db_path
        self.db_path = db_path
        
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    task_name TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    raw_input TEXT,
                    dependencies TEXT,
                    output_data TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    scheduled_at DATETIME,
                    repeat_type TEXT,
                    repeat_config TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME,
                    parent_task_id INTEGER REFERENCES tasks(task_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_json (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    workflow_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_knowledge_base (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_signature TEXT NOT NULL,
                    error_type TEXT,
                    error_message TEXT,
                    solution TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_at ON tasks(scheduled_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")

    def create_task(
        self,
        task_type: str,
        task_name: str,
        raw_input: str,
        dependencies: Optional[List[int]] = None,
    ) -> int:
        initial_status = 'blocked' if dependencies else 'pending'
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (task_type, task_name, status, raw_input, dependencies, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_type,
                    task_name,
                    initial_status,
                    raw_input,
                    json.dumps(dependencies) if dependencies else None,
                    datetime.now().isoformat(),
                ),
            )
            return cursor.lastrowid

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_status(
        self,
        task_id: int,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE tasks 
                SET status = ?, output_data = ?, error_message = ?, updated_at = ? 
                WHERE task_id = ?
                """,
                (status, output, error, datetime.now().isoformat(), task_id),
            )

    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM tasks 
                WHERE status = 'pending' 
                ORDER BY created_at 
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM tasks 
                WHERE status = 'scheduled' 
                ORDER BY scheduled_at
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_running_tasks(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM tasks 
                WHERE status = 'running'
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at",
                (status,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def count_by_status(self, status: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = ?",
                (status,)
            )
            return cursor.fetchone()[0]

    def get_all_active_tasks(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status IN ('pending', 'running', 'scheduled', 'blocked') ORDER BY created_at"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_tasks_depending_on(self, task_id: int) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT DISTINCT t.* FROM tasks t, json_each(t.dependencies) 
                WHERE json_each.value = ?
                """,
                (task_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_scheduled_task(
        self,
        task_type: str,
        task_name: str,
        raw_input: str,
        scheduled_at: datetime,
        repeat_type: Optional[str] = None,
        repeat_config: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[int]] = None,
        parent_task_id: Optional[int] = None,
    ) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (
                    task_type, task_name, status, raw_input,
                    dependencies, scheduled_at, repeat_type,
                    repeat_config, created_at, parent_task_id
                )
                VALUES (?, ?, 'scheduled', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_type,
                    task_name,
                    raw_input,
                    json.dumps(dependencies) if dependencies else None,
                    scheduled_at.isoformat(),
                    repeat_type,
                    json.dumps(repeat_config) if repeat_config else None,
                    datetime.now().isoformat(),
                    parent_task_id,
                ),
            )
            return cursor.lastrowid


class WorkflowRepository:
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_json (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    workflow_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

    def save_workflow(self, task_id: int, workflow_json: Dict[str, Any]) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO workflow_json (task_id, workflow_json, created_at)
                VALUES (?, ?, ?)
                """,
                (task_id, json.dumps(workflow_json), datetime.now().isoformat())
            )
            return cursor.lastrowid

    def get_workflow(self, task_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM workflow_json WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['workflow_json'] = json.loads(result['workflow_json'])
                return result
            return None

    def delete_workflow(self, task_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM workflow_json WHERE task_id = ?",
                (task_id,)
            )
            return cursor.rowcount > 0


