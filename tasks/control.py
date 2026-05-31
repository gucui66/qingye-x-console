"""
任务管理器的控制和状态管理逻辑
"""
from datetime import datetime
import json
import os
import shutil
import time
from typing import List, Optional
from uuid import uuid4

import core.config as config
from services import media_store
from tasks.models import Task, TaskInterruptedError, TaskStatus


class TaskManagerControlMixin:
    """任务增删改查与控制逻辑"""

    def _is_task_queued_locked(self, task_id: str) -> bool:
        return any(queued_task.task_id == task_id for queued_task in list(self.task_queue.queue))

    def _enqueue_task_if_needed_locked(self, task: Task) -> bool:
        if task.task_id in self.running_tasks:
            return False
        if self._is_task_queued_locked(task.task_id):
            return False
        self.task_queue.put(task)
        return True

    def find_active_task_by_username(self, username: str) -> Optional[Task]:
        normalized_username = (username or '').strip().lstrip('@').lower()
        if not normalized_username:
            return None

        active_statuses = {
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.USER_PAUSED,
        }
        status_priority = {
            TaskStatus.RUNNING: 4,
            TaskStatus.PENDING: 3,
            TaskStatus.PAUSED: 2,
            TaskStatus.USER_PAUSED: 1,
        }

        matches = [
            task for task in self.tasks.values()
            if task.username.lower() == normalized_username and task.status in active_statuses
        ]
        if not matches:
            return None

        matches.sort(
            key=lambda task: (
                status_priority.get(task.status, 0),
                task.created_at or datetime.min
            ),
            reverse=True
        )
        return matches[0]

    def add_or_get_active_task(self, username: str, max_tweets: int, options: dict):
        with self.lock:
            existing_task = self.find_active_task_by_username(username)
            if existing_task:
                return existing_task, True

            task_id = self._generate_task_id(username)
            task = Task(task_id, username, max_tweets, options)
            self.tasks[task_id] = task
            self._enqueue_task_if_needed_locked(task)
            self._save_tasks()

        print(f"➕ 添加任务: {task_id} - @{username}")
        return task, False

    def add_task(self, username: str, max_tweets: int, options: dict) -> str:
        task, _ = self.add_or_get_active_task(username, max_tweets, options)
        return task.task_id

    def _generate_task_id(self, username: str) -> str:
        timestamp_ms = int(time.time() * 1000)
        return f"task_{timestamp_ms}_{username}_{uuid4().hex[:6]}"

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[dict]:
        self._cleanup_old_tasks()
        return [task.to_dict() for task in self.tasks.values()]

    def _cleanup_old_tasks(self):
        completed_tasks = [
            (task_id, task) for task_id, task in self.tasks.items()
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        ]

        if len(completed_tasks) > 100:
            completed_tasks.sort(key=lambda x: x[1].completed_at or x[1].created_at)
            tasks_to_remove = completed_tasks[:-100]
            for task_id, _ in tasks_to_remove:
                del self.tasks[task_id]

            if tasks_to_remove:
                self._save_tasks()
                print(f"🧹 清理了 {len(tasks_to_remove)} 个老旧任务")

    def _refresh_rate_limit_reset_time(self):
        now = datetime.now()
        retry_times = [
            task.retry_after
            for task in self.tasks.values()
            if task.status == TaskStatus.PAUSED and task.retry_after and task.retry_after > now
        ]
        self.rate_limit_reset_time = min(retry_times) if retry_times else None

    def cancel_task(self, task_id: str) -> bool:
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False

            task.control_action = 'cancel'
            task.retry_after = None

            if task.status != TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.error_message = "用户已取消任务"
                self._save_history(task)
            else:
                task.error_message = "正在取消任务..."

            self._refresh_rate_limit_reset_time()
            self._save_tasks()
            print(f"🚫 任务已取消: {task_id}")
            return True
        return False

    def pause_task(self, task_id: str) -> bool:
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or task.status in [TaskStatus.USER_PAUSED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False

            if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                task.control_action = 'pause'
                task.retry_after = None
                task.status = TaskStatus.USER_PAUSED
                task.error_message = "正在暂停任务..."
                self._save_tasks()
                print(f"⏸️  任务已暂停: {task_id}")
                return True
        return False

    def resume_task(self, task_id: str) -> bool:
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status in [TaskStatus.USER_PAUSED, TaskStatus.PAUSED]:
                task.control_action = None
                task.error_message = None
                task.retry_after = None
                task.completed_at = None

                if task.task_id in self.running_tasks:
                    task.status = TaskStatus.RUNNING
                else:
                    task.status = TaskStatus.PENDING
                    self._enqueue_task_if_needed_locked(task)

                self._refresh_rate_limit_reset_time()
                self._save_tasks()
                print(f"▶️  任务已恢复: {task_id}")
                return True
        return False

    def delete_task(self, task_id: str) -> bool:
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False

            del self.tasks[task_id]

        self._remove_task_from_history(task_id)
        self._remove_task_artifacts(task)
        self._save_tasks()
        print(f"🗑️ 已删除任务记录: {task_id}")
        return True

    def _remove_task_from_history(self, task_id: str):
        history_file = config.HISTORY_FILE
        if not os.path.exists(history_file):
            return

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            filtered_history = [item for item in history if item.get('task_id') != task_id]

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(filtered_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"删除历史记录失败: {e}")

    def _remove_task_artifacts(self, task: Task):
        task_id = task.task_id
        username = (task.username or '').strip().lstrip('@')

        screenshot_dir = os.path.join(config.SCREENSHOTS_DIR, task_id)
        if os.path.exists(screenshot_dir):
            try:
                shutil.rmtree(screenshot_dir)
            except Exception as e:
                print(f"删除任务截图失败: {e}")

        if username:
            task_output_dir = os.path.join(config.OUTPUT_DIR, username, 'tasks', task_id)
            if os.path.exists(task_output_dir):
                try:
                    shutil.rmtree(task_output_dir)
                except Exception as e:
                    print(f"删除任务文档快照失败: {e}")

        try:
            result = media_store.delete_task_artifacts(task_id, username=username or None)
            if any(result.values()):
                print(
                    f"🧹 已清理任务媒体: 删除 {result['deleted_items']} 个，"
                    f"解绑 {result['unlinked_items']} 个，"
                    f"转移归属 {result['updated_items']} 个"
                )
        except Exception as e:
            print(f"删除任务媒体失败: {e}")

    def _get_requested_action(self, task: Task) -> Optional[str]:
        with self.lock:
            if task.control_action in ['pause', 'cancel']:
                return task.control_action
            if task.status == TaskStatus.CANCELLED:
                return 'cancel'
            if task.status == TaskStatus.USER_PAUSED:
                return 'pause'
        return None

    def _raise_if_task_interrupted(self, task: Task):
        action = self._get_requested_action(task)
        if action:
            raise TaskInterruptedError(action)

    def _build_stop_callback(self, task: Task):
        def stop_callback():
            self._raise_if_task_interrupted(task)
        return stop_callback

    def _handle_task_interruption(self, task: Task, interruption: TaskInterruptedError):
        task.control_action = None
        task.retry_after = None

        if interruption.action == 'cancel':
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.error_message = "用户已取消任务"
            self._save_history(task)
            print(f"🚫 任务已取消并停止执行: {task.task_id}")
        else:
            task.status = TaskStatus.USER_PAUSED
            task.completed_at = None
            task.error_message = "任务已暂停，可稍后继续"
            print(f"⏸️ 任务已暂停并停止执行: {task.task_id}")
