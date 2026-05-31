"""
后台管理认证模块
"""
from functools import wraps
from flask import session, redirect, request, flash
import hashlib
import os

import core.config as config

# 默认管理员账号
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123"

def hash_password(password):
    """密码加密"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password, hashed):
    """验证密码"""
    return hash_password(password) == hashed

def login_required(f):
    """登录验证装饰器（用于页面）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('请先登录', 'warning')
            return redirect(f"/login?redirect={request.url}")
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    """API登录验证装饰器（返回JSON）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import jsonify
        # 检查前端用户登录或后台管理员登录
        if not session.get('user_logged_in') and not session.get('admin_logged_in'):
            return jsonify({'success': False, 'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def api_admin_required(f):
    """管理员 API 登录验证（返回 JSON）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import jsonify
        if not session.get('admin_logged_in'):
            return jsonify({'success': False, 'error': '请先以管理员身份登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

def init_admin_user():
    """初始化管理员账号"""
    admin_file = config.ADMIN_FILE
    
    if not os.path.exists(admin_file):
        # 创建默认管理员
        with open(admin_file, 'w', encoding='utf-8') as f:
            f.write(f"{DEFAULT_ADMIN_USER}:{hash_password(DEFAULT_ADMIN_PASS)}")
        return DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS
    return None, None

def verify_admin(username, password):
    """验证管理员账号"""
    admin_file = config.ADMIN_FILE
    
    if not os.path.exists(admin_file):
        init_admin_user()
    
    try:
        with open(admin_file, 'r', encoding='utf-8') as f:
            stored = f.read().strip()
            stored_user, stored_hash = stored.split(':')
            
            if username == stored_user and check_password(password, stored_hash):
                return True
    except (FileNotFoundError, ValueError, IndexError):
        pass
    
    return False

def change_admin_password(old_password, new_password):
    """修改管理员密码"""
    admin_file = config.ADMIN_FILE
    
    try:
        with open(admin_file, 'r', encoding='utf-8') as f:
            stored = f.read().strip()
            stored_user, stored_hash = stored.split(':')
        
        if check_password(old_password, stored_hash):
            with open(admin_file, 'w', encoding='utf-8') as f:
                f.write(f"{stored_user}:{hash_password(new_password)}")
            return True
    except (FileNotFoundError, ValueError, IndexError, IOError):
        pass
    
    return False
