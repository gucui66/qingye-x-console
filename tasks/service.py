"""
任务管理器主类
"""
import queue
import threading

from tasks.control import TaskManagerControlMixin
from tasks.execution import TaskManagerExecutionMixin
from tasks.persistence import TaskManagerPersistenceMixin


class TaskManager(
    TaskManagerControlMixin,
    TaskManagerExecutionMixin,
    TaskManagerPersistenceMixin,
):
    """任务管理器（支持多任务并发）"""

    def __init__(self, max_workers=3):
        self.tasks = {}
        self.task_queue = queue.Queue()
        self.running_tasks = {}
        self.max_workers = max_workers
        self.is_running = False
        self.worker_threads = []
        self.rate_limit_reset_time = None
        self.lock = threading.Lock()

        self._load_tasks()

    def start(self):
        if not self.is_running:
            self.is_running = True
            for worker_id in range(self.max_workers):
                worker = threading.Thread(target=self._worker, args=(worker_id,), daemon=True)
                worker.start()
                self.worker_threads.append(worker)
            print(f"📋 任务管理器已启动（{self.max_workers}个并发线程）")

    def stop(self):
        self.is_running = False
        for worker in self.worker_threads:
            worker.join(timeout=5)
        print("📋 任务管理器已停止")


task_manager = TaskManager()
