"""
Socket.IO 事件处理
"""
from flask_socketio import emit


def register_socket_handlers(socketio):
    """注册 Socket 事件"""

    @socketio.on('connect')
    def handle_connect():
        emit('connected', {'message': '已连接到服务器'})

    @socketio.on('disconnect')
    def handle_disconnect():
        return None
