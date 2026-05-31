"""
任务管理器的持久化逻辑
"""
from datetime import datetime
import json
import os

import core.config as config
from tasks.models import Task, TaskStatus


class TaskManagerPersistenceMixin:
    """任务读写与历史记录"""

    def _save_tasks(self):
        try:
            tasks_data = {
                task_id: task.to_dict()
                for task_id, task in self.tasks.items()
            }
            with open(config.TASKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务失败: {e}")

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    def _load_tasks(self):
        try:
            if not os.path.exists(config.TASKS_FILE):
                return

            with open(config.TASKS_FILE, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)

            next_retry_after = None
            for task_id, data in tasks_data.items():
                task = Task(
                    data['task_id'],
                    data['username'],
                    data['max_tweets'],
                    data.get('options', {})
                )
                task.status = data.get('status', TaskStatus.PENDING)
                task.progress = data.get('progress', 0)
                task.total = data.get('total', task.max_tweets)
                task.scraped_count = data.get('scraped_count', 0)
                task.error_message = data.get('error_message')
                task.created_at = self._parse_datetime(data.get('created_at')) or task.created_at
                task.started_at = self._parse_datetime(data.get('started_at'))
                task.completed_at = self._parse_datetime(data.get('completed_at'))
                task.retry_after = self._parse_datetime(data.get('retry_after'))
                task.retry_count = data.get('retry_count', 0)
                task.control_action = data.get('control_action')
                task.results = data.get('results', task.results)

                if task.control_action in ['pause', 'cancel']:
                    task.control_action = None

                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.PENDING
                    task.error_message = "服务重启后自动恢复任务"

                if task.status == TaskStatus.PAUSED and task.retry_after and task.retry_after <= datetime.now():
                    task.status = TaskStatus.PENDING
                    task.retry_after = None
                    task.error_message = None

                if task.status == TaskStatus.PAUSED and task.retry_after:
                    next_retry_after = min(next_retry_after or task.retry_after, task.retry_after)

                self.tasks[task_id] = task

                if task.status in [TaskStatus.PENDING, TaskStatus.PAUSED]:
                    self.task_queue.put(task)

                print(f"📥 恢复任务: {task_id} [{task.status}]")

            if next_retry_after:
                self.rate_limit_reset_time = next_retry_after
        except Exception as e:
            print(f"加载任务失败: {e}")

    def _save_history(self, task: Task):
        try:
            history_file = config.HISTORY_FILE

            history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                except Exception:
                    history = []

            history.insert(0, {
                'task_id': task.task_id,
                'username': task.username,
                'max_tweets': task.max_tweets,
                'options': task.options,
                'status': task.status,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'total_tweets': task.results.get('total_tweets', 0),
                'videos': task.results.get('videos', 0),
                'photos': task.results.get('photos', 0),
                'error_message': task.error_message,
                'results': task.results,
                'artifacts': task.results.get('artifacts', {}),
            })

            history = history[:100]

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            print(f"📝 历史记录已保存: {task.username}")
        except Exception as e:
            print(f"保存历史失败: {e}")
