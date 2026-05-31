"""
Flask 和 Socket.IO 运行时对象
"""
from datetime import datetime
import os

from flask import Flask
from flask_socketio import SocketIO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
    static_url_path='/static',
)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'twitter-scraper-local-dev-key')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['TEMPLATES_AUTO_RELOAD'] = True

socketio = SocketIO(app, cors_allowed_origins="*")

scraping_status = {
    'is_running': False,
    'current_step': '',
    'progress': 0,
    'total': 0,
    'username': '',
    'results': {}
}


class WebLogger:
    """Web日志输出类"""

    @staticmethod
    def log(message, level='info'):
        """发送日志消息到前端"""
        socketio.emit('log', {
            'message': message,
            'level': level,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })

    @staticmethod
    def progress(current, total, step=''):
        """更新进度"""
        scraping_status['progress'] = current
        scraping_status['total'] = total
        scraping_status['current_step'] = step

        socketio.emit('progress', {
            'current': current,
            'total': total,
            'step': step,
            'percentage': int((current / total * 100)) if total > 0 else 0
        })


def print_startup_banner(port: int):
    """打印启动信息"""
    print("=" * 60)
    print("  X/Twitter 用户主页爬虫 - Web版（任务队列模式）")
    print("=" * 60)
    print()
    print(f"  🌐 访问地址: http://localhost:{port}")
    print(f"  🌐 局域网访问: http://0.0.0.0:{port}")
    print("  📝 按 Ctrl+C 停止服务器")
    print()
    print("  ✨ 新功能:")
    print("     📋 任务队列管理")
    print("     ⏰ 自动处理速率限制（15分钟后重试）")
    print("     💾 断点续传")
    print()
    print("=" * 60)
