#!/usr/bin/env python3
"""
X/Twitter 爬虫 Web 应用入口
"""
import os

from core.auth import init_admin_user
import core.config as config
from core.runtime import app, print_startup_banner, socketio
from routes.admin import register_admin_routes
from routes.api import register_api_routes
from routes.files import register_file_routes
from routes.socket_handlers import register_socket_handlers
from scrapers import SELENIUM_AVAILABLE
from tasks import task_manager


def print_runtime_capabilities():
    """打印当前可用的抓取能力"""
    selenium_available = SELENIUM_AVAILABLE

    if selenium_available:
        print("✅ Selenium模式可用（无需API）")
    else:
        print("ℹ️  Selenium模式不可用（需要安装selenium和chromedriver）")

    if not config.TWITTER_BEARER_TOKEN or config.TWITTER_BEARER_TOKEN == "":
        print("⚠️  Twitter API未配置")
        if not selenium_available:
            print("   请选择：1) 配置API  2) 安装Selenium")
    else:
        print("✅ Twitter API已配置")


init_admin_user()
register_admin_routes(app)
register_api_routes(app)
register_file_routes(app)
register_socket_handlers(socketio)
print_runtime_capabilities()


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5001'))
    print_startup_banner(port)

    task_manager.start()
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
    finally:
        task_manager.stop()
