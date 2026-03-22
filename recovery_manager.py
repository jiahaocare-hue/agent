from datetime import datetime

from database import TaskRepository
from timer_scheduler import TimerScheduler


class RecoveryManager:
    def __init__(self, repo: TaskRepository, timer_scheduler: TimerScheduler):
        self.repo = repo
        self.timer_scheduler = timer_scheduler

    def recover_all(self):
        self._recover_running_tasks()
        self._recover_scheduled_tasks()

    def _recover_running_tasks(self):
        tasks = self.repo.get_running_tasks()
        for task in tasks:
            self.repo.update_status(task['task_id'], 'pending')
            print(f"Recovered task {task['task_id']}: running → pending")

    def _recover_scheduled_tasks(self):
        tasks = self.repo.get_scheduled_tasks()
        for task in tasks:
            task_id = task['task_id']
            scheduled_at_str = task.get('scheduled_at')
            if scheduled_at_str:
                scheduled_at = datetime.fromisoformat(scheduled_at_str)
                if scheduled_at.tzinfo is not None:
                    scheduled_at = scheduled_at.replace(tzinfo=None)
                self.timer_scheduler.schedule_task(task_id, scheduled_at)
                print(f"Recovered scheduled task {task_id}")
