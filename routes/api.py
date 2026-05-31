"""
用户登录、任务队列和预览相关 API 路由
"""
import re

from flask import jsonify, request, session

from core.auth import api_login_required, verify_admin
from core.runtime import scraping_status
from tasks import task_manager


USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_]{1,15}$')


def _normalize_username(raw_value: str):
    username = (raw_value or '').strip().lstrip('@')
    if not username:
        return None, '请输入用户名'
    if not USERNAME_PATTERN.fullmatch(username):
        return None, '用户名格式无效，请输入 1-15 位字母、数字或下划线'
    return username, None


def register_api_routes(app):
    """注册 API 路由"""

    @app.route('/api/user/login', methods=['POST'])
    def user_login():
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if verify_admin(username, password):
            session['user_logged_in'] = True
            session['admin_logged_in'] = True
            session['username'] = username
            return jsonify({
                'success': True,
                'message': '登录成功',
                'role': 'admin'
            })

        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

    @app.route('/api/user/status')
    def user_status():
        if session.get('user_logged_in'):
            return jsonify({
                'logged_in': True,
                'username': session.get('username', 'admin'),
                'is_admin': bool(session.get('admin_logged_in'))
            })
        return jsonify({'logged_in': False, 'is_admin': False})

    @app.route('/api/user/logout', methods=['POST'])
    def user_logout():
        session.pop('user_logged_in', None)
        session.pop('username', None)
        session.pop('admin_logged_in', None)
        return jsonify({'success': True, 'message': '已退出登录'})

    @app.route('/api/scrape', methods=['POST'])
    @api_login_required
    def start_scrape():
        data = request.json or {}
        username, username_error = _normalize_username(data.get('username', ''))
        if username_error:
            return jsonify({'error': username_error}), 400

        max_tweets = data.get('max_tweets')
        if max_tweets in [None, '']:
            max_tweets = None
        else:
            try:
                max_tweets = int(max_tweets)
            except (TypeError, ValueError):
                return jsonify({'error': '最大推文数必须是数字'}), 400
            if max_tweets <= 0:
                max_tweets = None

        scrape_method = data.get('scrape_method', 'api')
        if scrape_method not in ['api', 'selenium']:
            return jsonify({'error': '不支持的爬取方式'}), 400

        selenium_behavior_mode = data.get('selenium_behavior_mode', 'balanced')
        if selenium_behavior_mode not in ['balanced', 'stable', 'human']:
            return jsonify({'error': '不支持的 Selenium 行为模式'}), 400

        options = {
            'download_videos': data.get('download_videos', True),
            'download_photos': data.get('download_photos', True),
            'download_replies': data.get('download_replies', True),
            'scrape_method': scrape_method,
            'selenium_behavior_mode': selenium_behavior_mode,
        }

        task, existed = task_manager.add_or_get_active_task(username, max_tweets, options)
        if existed:
            return jsonify({
                'success': True,
                'message': f'@{username} 已有进行中的任务，已为你定位到现有任务',
                'task_id': task.task_id,
                'existing_task': True,
                'status': task.status
            })

        return jsonify({
            'success': True,
            'message': '任务已添加到队列',
            'task_id': task.task_id
        })

    @app.route('/api/status')
    @api_login_required
    def get_status():
        return jsonify(scraping_status)

    @app.route('/api/tasks', methods=['GET'])
    @api_login_required
    def get_tasks():
        return jsonify(task_manager.get_all_tasks())

    @app.route('/api/tasks/<task_id>', methods=['GET'])
    @api_login_required
    def get_task(task_id):
        task = task_manager.get_task(task_id)
        if task:
            return jsonify(task.to_dict())
        return jsonify({'error': '任务不存在'}), 404

    @app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
    @api_login_required
    def cancel_task(task_id):
        if task_manager.cancel_task(task_id):
            return jsonify({'success': True, 'message': '任务已取消'})
        return jsonify({'success': False, 'message': '无法取消任务'}), 400

    @app.route('/api/tasks/<task_id>/pause', methods=['POST'])
    @api_login_required
    def pause_task(task_id):
        if task_manager.pause_task(task_id):
            return jsonify({'success': True, 'message': '任务已暂停'})
        return jsonify({'success': False, 'message': '无法暂停任务'}), 400

    @app.route('/api/tasks/<task_id>/resume', methods=['POST'])
    @api_login_required
    def resume_task(task_id):
        if task_manager.resume_task(task_id):
            return jsonify({'success': True, 'message': '任务已恢复'})
        return jsonify({'success': False, 'message': '无法恢复任务'}), 400

    @app.route('/api/tasks/<task_id>', methods=['DELETE'])
    @api_login_required
    def delete_task(task_id):
        if task_manager.delete_task(task_id):
            return jsonify({'success': True, 'message': '任务已删除'})
        return jsonify({'success': False, 'message': '任务不存在或无法删除'}), 400

    @app.route('/api/preview-profile', methods=['POST'])
    def preview_profile():
        try:
            data = request.json or {}
            username, username_error = _normalize_username(data.get('username', ''))
            if username_error:
                return jsonify({'error': username_error}), 400

            return jsonify({
                'success': True,
                'user': {
                    'username': username,
                    'profile_url': f'https://twitter.com/{username}',
                    'x_url': f'https://x.com/{username}',
                    'message': '点击下方链接在浏览器中查看用户主页'
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
