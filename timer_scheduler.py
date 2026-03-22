import threading
from datetime import datetime, timedelta

from database import TaskRepository


class TimerScheduler:
    def __init__(self, repo: TaskRepository, on_trigger_callback):
        self.repo = repo
        self.on_trigger_callback = on_trigger_callback
        self.active_timers: dict[int, threading.Timer] = {}
        self.lock = threading.Lock()
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False
        with self.lock:
            for timer in self.active_timers.values():
                timer.cancel()
            self.active_timers.clear()

    def schedule_task(self, task_id: int, scheduled_at: datetime):
        if not self.running:
            return

        if scheduled_at.tzinfo is not None:
            scheduled_at = scheduled_at.replace(tzinfo=None)

        delay = (scheduled_at - datetime.now()).total_seconds()
        if delay <= 0:
            self._trigger_task(task_id)
        else:
            timer = threading.Timer(delay, self._trigger_task, args=[task_id])
            with self.lock:
                self.active_timers[task_id] = timer
            timer.start()

    def cancel_schedule(self, task_id: int) -> bool:
        with self.lock:
            if task_id in self.active_timers:
                self.active_timers[task_id].cancel()
                del self.active_timers[task_id]
                return True
            return False

    def on_task_completed(self, task_id: int):
        task = self.repo.get_task(task_id)
        if not task:
            return

        repeat_type = task.get('repeat_type')
        if not repeat_type or repeat_type == 'once':
            return

        self._create_next_instance(task)

    def _trigger_task(self, task_id: int):
        with self.lock:
            self.active_timers.pop(task_id, None)

        self.repo.update_status(task_id, 'pending')
        self.on_trigger_callback()

    def _create_next_instance(self, task: dict):
        import json

        task_id = task['task_id']
        task_type = task['task_type']
        task_name = task['task_name']
        raw_input = task['raw_input']
        repeat_type = task.get('repeat_type')
        repeat_config_str = task.get('repeat_config')
        parent_task_id = task.get('parent_task_id')

        repeat_config = {}
        if repeat_config_str:
            repeat_config = json.loads(repeat_config_str)

        next_scheduled_at = self._calculate_next_time(repeat_type, repeat_config)
        if not next_scheduled_at:
            return

        effective_parent_id = parent_task_id if parent_task_id else task_id

        new_task_id = self.repo.create_scheduled_task(
            task_type=task_type,
            task_name=task_name,
            raw_input=raw_input,
            scheduled_at=next_scheduled_at,
            repeat_type=repeat_type,
            repeat_config=repeat_config,
            parent_task_id=effective_parent_id,
        )

        self.schedule_task(new_task_id, next_scheduled_at)

    def _calculate_next_time(self, repeat_type: str, repeat_config: dict) -> datetime | None:
        now = datetime.now()

        if repeat_type == 'interval':
            interval_minutes = repeat_config.get('interval_minutes', 1)
            return now + timedelta(minutes=interval_minutes)

        elif repeat_type == 'daily':
            time_str = repeat_config.get('time', '00:00')
            hour, minute = map(int, time_str.split(':'))
            next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time

        elif repeat_type == 'weekly':
            time_str = repeat_config.get('time', '00:00')
            target_weekday = repeat_config.get('day_of_week', 0)
            hour, minute = map(int, time_str.split(':'))

            days_ahead = target_weekday - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7

            next_time = now + timedelta(days=days_ahead)
            next_time = next_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_time

        elif repeat_type == 'monthly':
            time_str = repeat_config.get('time', '00:00')
            target_day = repeat_config.get('day_of_month', 1)
            hour, minute = map(int, time_str.split(':'))

            next_time = now.replace(day=target_day, hour=hour, minute=minute, second=0, microsecond=0)
            if next_time <= now:
                if now.month == 12:
                    next_time = next_time.replace(year=now.year + 1, month=1)
                else:
                    next_time = next_time.replace(month=now.month + 1)
            return next_time

        return None
