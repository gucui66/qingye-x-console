"""
任务模型定义
"""
from datetime import datetime
from typing import Dict


class TaskStatus:
    """任务状态"""

    PENDING = 'pending'
    RUNNING = 'running'
    PAUSED = 'paused'
    USER_PAUSED = 'user_paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class TaskInterruptedError(Exception):
    """任务被用户中断"""

    def __init__(self, action: str):
        self.action = action
        message = "任务已取消" if action == 'cancel' else "任务已暂停"
        super().__init__(message)


class Task:
    """爬取任务"""

    def __init__(self, task_id: str, username: str, max_tweets: int, options: Dict):
        self.task_id = task_id
        self.username = username
        self.max_tweets = max_tweets
        self.options = options

        self.status = TaskStatus.PENDING
        self.progress = 0
        self.total = max_tweets
        self.scraped_count = 0
        self.error_message = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.retry_after = None
        self.retry_count = 0
        self.control_action = None

        self.results = {
            'tweets': [],
            'videos': 0,
            'photos': 0,
            'replies': 0
        }

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'username': self.username,
            'max_tweets': self.max_tweets,
            'options': self.options,
            'status': self.status,
            'progress': self.progress,
            'total': self.total,
            'scraped_count': self.scraped_count,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'retry_after': self.retry_after.isoformat() if self.retry_after else None,
            'retry_count': self.retry_count,
            'control_action': self.control_action,
            'results': self.results
        }
