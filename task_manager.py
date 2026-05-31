"""
任务管理器兼容入口
"""
from tasks import Task, TaskInterruptedError, TaskManager, TaskStatus, task_manager

__all__ = [
    'Task',
    'TaskInterruptedError',
    'TaskManager',
    'TaskStatus',
    'task_manager',
]
