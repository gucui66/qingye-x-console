"""
文件列表、下载和预览相关路由
"""
from datetime import datetime
import json
import os
import tempfile
import zipfile

from flask import Response, jsonify, request, send_file, send_from_directory

import core.config as config
from services import infer_legacy_task_artifacts, media_store
from tasks import task_manager


def _is_within_directory(base_dir: str, target_path: str) -> bool:
    try:
        return os.path.commonpath([
            os.path.realpath(base_dir),
            os.path.realpath(target_path),
        ]) == os.path.realpath(base_dir)
    except ValueError:
        return False


def _extract_tweet_id_from_filename(filename: str):
    stem = os.path.basename(filename or '')
    parts = stem.split('tweet_', 1)
    if len(parts) != 2:
        return None
    suffix = parts[1].split('_', 1)[0].split('.', 1)[0]
    return suffix or None


def _peek_user_dirs(username: str):
    user_output_dir = os.path.join(config.OUTPUT_DIR, username)
    return {
        'output': user_output_dir,
        'videos': os.path.join(user_output_dir, 'videos'),
        'photos': os.path.join(user_output_dir, 'photos'),
        'replies': os.path.join(user_output_dir, 'replies'),
        'documents': os.path.join(user_output_dir, 'documents'),
        'thumbnails': os.path.join(user_output_dir, 'thumbnails'),
        'duplicates': os.path.join(user_output_dir, 'duplicates'),
        'tasks': os.path.join(user_output_dir, 'tasks'),
    }


def _append_legacy_user_files(files, username: str):
    """兼容旧版磁盘文件结构。"""
    user_dirs = _peek_user_dirs(username)

    if os.path.exists(user_dirs['videos']):
        for filename in os.listdir(user_dirs['videos']):
            if filename.endswith('.mp4'):
                file_path = os.path.join(user_dirs['videos'], filename)
                files['videos'].append({
                    'name': filename,
                    'username': username,
                    'path': os.path.join(username, 'videos', filename),
                    'size': os.path.getsize(file_path),
                    'modified_at': os.path.getmtime(file_path),
                    'media_type': 'video',
                    'tweet_id': _extract_tweet_id_from_filename(filename),
                    'storage_backend': 'filesystem',
                })

    if os.path.exists(user_dirs['photos']):
        for filename in os.listdir(user_dirs['photos']):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                file_path = os.path.join(user_dirs['photos'], filename)
                files['photos'].append({
                    'name': filename,
                    'username': username,
                    'path': os.path.join(username, 'photos', filename),
                    'size': os.path.getsize(file_path),
                    'modified_at': os.path.getmtime(file_path),
                    'media_type': 'photo',
                    'tweet_id': _extract_tweet_id_from_filename(filename),
                    'storage_backend': 'filesystem',
                })

    if os.path.exists(user_dirs['documents']):
        for filename in os.listdir(user_dirs['documents']):
            if filename.endswith(('.html', '.md')):
                file_path = os.path.join(user_dirs['documents'], filename)
                files['documents'].append({
                    'name': filename,
                    'username': username,
                    'path': os.path.join(username, 'documents', filename),
                    'size': os.path.getsize(file_path),
                    'modified_at': os.path.getmtime(file_path),
                    'storage_backend': 'filesystem',
                })


def _append_legacy_all_users_files(files):
    """遍历旧版磁盘输出目录。"""
    if not os.path.exists(config.OUTPUT_DIR):
        return

    for user_folder in os.listdir(config.OUTPUT_DIR):
        user_path = os.path.join(config.OUTPUT_DIR, user_folder)
        if not os.path.isdir(user_path):
            continue
        _append_legacy_user_files(files, user_folder)


def _append_database_user_files(files, username: str):
    files['videos'].extend(media_store.list_media(username, 'video'))
    files['photos'].extend(media_store.list_media(username, 'photo'))


def _append_database_all_users_files(files):
    files['videos'].extend(media_store.list_media(media_type='video'))
    files['photos'].extend(media_store.list_media(media_type='photo'))


def _load_task_artifact_documents(task_id: str, username: str = None):
    history = []
    if os.path.exists(config.HISTORY_FILE):
        try:
            with open(config.HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []

    live_task = task_manager.get_task(task_id) if task_id else None
    candidates = []
    if live_task:
        candidates.append(live_task.to_dict())
    candidates.extend([item for item in history if item.get('task_id') == task_id])

    documents = []
    normalized = (username or '').strip().lstrip('@') if username else None
    for entry in candidates:
        entry_username = (entry.get('username') or '').strip().lstrip('@')
        if normalized and entry_username != normalized:
            continue
        artifacts = ((entry.get('results') or {}).get('artifacts') or entry.get('artifacts') or {})
        for item in artifacts.get('documents', []) or []:
            documents.append(item)
    documents = media_store.dedupe_media_items(documents)
    if not documents:
        legacy = infer_legacy_task_artifacts(task_id, username=username)
        documents = legacy.get('documents', [])
    return documents


def _append_recursive_folder_targets(targets, folder_path: str, arc_prefix: str):
    """把一个输出目录递归加入下载包，适合缩略图、重复暂存等子目录。"""
    if not folder_path or not os.path.exists(folder_path):
        return

    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            if not os.path.isfile(file_path):
                continue
            relative = os.path.relpath(file_path, folder_path)
            targets.append({
                'kind': 'file',
                'path': file_path,
                'arcname': os.path.join(arc_prefix, relative),
            })


def _sort_files(files):
    files['videos'] = media_store.dedupe_media_items(files['videos'])
    files['photos'] = media_store.dedupe_media_items(files['photos'])
    files['videos'].sort(key=lambda item: item.get('modified_at', 0), reverse=True)
    files['photos'].sort(key=lambda item: item.get('modified_at', 0), reverse=True)
    files['documents'].sort(key=lambda item: item.get('modified_at', 0), reverse=True)


def _parse_range_header(range_header: str, file_size: int):
    if not range_header or not range_header.startswith('bytes=') or file_size <= 0:
        return None

    try:
        range_value = range_header.split('=', 1)[1]
        start_str, end_str = range_value.split('-', 1)

        if start_str == '':
            suffix_length = int(end_str)
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1

        if start < 0 or end < start:
            return None

        end = min(end, file_size - 1)
        if start >= file_size:
            return None

        return start, end
    except (TypeError, ValueError):
        return None


def _serve_db_virtual_file(virtual_path: str):
    resolved = media_store.resolve_virtual_media(virtual_path)
    metadata = resolved['metadata'] if resolved else None
    parsed = resolved['parsed'] if resolved else None

    if not metadata or not parsed:
        return jsonify({'error': '文件不存在'}), 404

    file_size = metadata.get('size', 0)
    mime_type = metadata.get('mime_type') or 'application/octet-stream'
    range_header = request.headers.get('Range')
    byte_range = _parse_range_header(range_header, file_size)

    if range_header and byte_range is None:
        response = Response(status=416)
        response.headers['Content-Range'] = f'bytes */{file_size}'
        return response

    if byte_range:
        start, end = byte_range
        _, chunk = media_store.read_media_blob(
            parsed['username'],
            parsed['media_id'],
            parsed['media_type'],
            start,
            end,
            parsed.get('shard_key'),
        )
        response = Response(chunk or b'', status=206, mimetype=mime_type)
        response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = str(end - start + 1)
        response.headers['Content-Disposition'] = f'inline; filename="{metadata["name"]}"'
        return response

    _, content = media_store.read_media_blob(
        parsed['username'],
        parsed['media_id'],
        parsed['media_type'],
        shard_key=parsed.get('shard_key'),
    )
    response = Response(content or b'', mimetype=mime_type)
    response.headers['Content-Length'] = str(file_size)
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Disposition'] = f'inline; filename="{metadata["name"]}"'
    return response


def _iter_download_targets(username: str = None, task_id: str = None):
    """汇总数据库媒体和旧版文件，供打包下载使用。"""
    targets = []

    if task_id:
        normalized = username.strip().lstrip('@') if username else None
        db_count = 0
        for media_type in ('video', 'photo'):
            for item in media_store.list_media(normalized, media_type, task_id):
                db_count += 1
                targets.append({
                    'kind': 'db',
                    'username': item['username'],
                    'media_type': media_type,
                    'name': item['name'],
                    'arcname': os.path.join(item['username'], task_id, f'{media_type}s', item['name']),
                    'id': item['id'],
                    'shard_key': media_store.parse_virtual_path(item['path']).get('shard_key') if item.get('path') else None,
                })

        if db_count == 0:
            legacy = infer_legacy_task_artifacts(task_id, username=normalized)
            for media_type, bucket in (('video', legacy.get('videos', [])), ('photo', legacy.get('photos', []))):
                for item in bucket:
                    file_path = os.path.join(config.OUTPUT_DIR, item['path'])
                    if os.path.isfile(file_path):
                        targets.append({
                            'kind': 'file',
                            'path': file_path,
                            'arcname': os.path.join(item.get('username') or normalized or 'task', task_id, f'{media_type}s', os.path.basename(item['path'])),
                        })

        for document in _load_task_artifact_documents(task_id, normalized):
            file_path = os.path.join(config.OUTPUT_DIR, document['path'])
            if os.path.isfile(file_path):
                targets.append({
                    'kind': 'file',
                    'path': file_path,
                    'arcname': os.path.join(document.get('username') or normalized or 'task', task_id, 'documents', os.path.basename(document['path'])),
                })

        for duplicate in media_store.list_duplicate_files(username=normalized, task_id=task_id, limit=500).get('items', []):
            file_path = os.path.join(config.OUTPUT_DIR, duplicate.get('path') or '')
            if os.path.isfile(file_path):
                targets.append({
                    'kind': 'file',
                    'path': file_path,
                    'arcname': os.path.join(
                        duplicate.get('username') or normalized or 'task',
                        task_id,
                        'duplicates',
                        duplicate.get('media_type') or 'media',
                        os.path.basename(file_path),
                    ),
                })
        return targets

    if username:
        normalized = username.strip().lstrip('@')
        for media_type in ('video', 'photo'):
            for item in media_store.list_media(normalized, media_type):
                targets.append({
                    'kind': 'db',
                    'username': normalized,
                    'media_type': media_type,
                    'name': item['name'],
                    'arcname': os.path.join(f'{media_type}s', item['name']),
                    'id': item['id'],
                })

        user_dirs = _peek_user_dirs(normalized)
        for folder_name in ['videos', 'photos', 'documents', 'thumbnails', 'duplicates', 'tasks']:
            folder_path = user_dirs[folder_name]
            _append_recursive_folder_targets(targets, folder_path, folder_name)
        return targets

    usernames = set(media_store.list_usernames())
    if os.path.exists(config.OUTPUT_DIR):
        for user_folder in os.listdir(config.OUTPUT_DIR):
            user_path = os.path.join(config.OUTPUT_DIR, user_folder)
            if os.path.isdir(user_path):
                usernames.add(user_folder)

    for each_username in sorted(usernames):
        for media_type in ('video', 'photo'):
            for item in media_store.list_media(each_username, media_type):
                targets.append({
                    'kind': 'db',
                    'username': each_username,
                    'media_type': media_type,
                    'name': item['name'],
                    'arcname': os.path.join(each_username, f'{media_type}s', item['name']),
                    'id': item['id'],
                })

        user_dirs = _peek_user_dirs(each_username)
        for folder_name in ['videos', 'photos', 'documents', 'thumbnails', 'duplicates', 'tasks']:
            folder_path = user_dirs[folder_name]
            _append_recursive_folder_targets(targets, folder_path, os.path.join(each_username, folder_name))

    return targets


def register_file_routes(app):
    """注册文件相关路由"""

    @app.route('/api/files')
    def list_files():
        try:
            username = request.args.get('username')
            task_id = request.args.get('task_id')
            files = {'videos': [], 'photos': [], 'documents': []}

            if task_id:
                normalized = username.strip().lstrip('@') if username else None
                files['videos'].extend(media_store.list_media(normalized, 'video', task_id))
                files['photos'].extend(media_store.list_media(normalized, 'photo', task_id))
                if not files['videos'] and not files['photos']:
                    legacy = infer_legacy_task_artifacts(task_id, username=normalized)
                    files['videos'].extend(legacy.get('videos', []))
                    files['photos'].extend(legacy.get('photos', []))
                files['documents'].extend(_load_task_artifact_documents(task_id, normalized))
            elif username:
                normalized = username.strip().lstrip('@')
                _append_database_user_files(files, normalized)
                _append_legacy_user_files(files, normalized)
            else:
                _append_database_all_users_files(files)
                _append_legacy_all_users_files(files)

            _sort_files(files)
            return jsonify(files)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/output/<path:filename>')
    def download_file(filename):
        if '..' in filename or filename.startswith('/'):
            return jsonify({'error': '非法路径'}), 403

        normalized = filename.lstrip('/')
        if normalized.startswith(f'{media_store.VIRTUAL_PREFIX}/'):
            return _serve_db_virtual_file(normalized)

        file_path = os.path.join(config.OUTPUT_DIR, normalized)
        real_path = os.path.realpath(file_path)
        real_output_dir = os.path.realpath(config.OUTPUT_DIR)

        if not _is_within_directory(real_output_dir, real_path):
            return jsonify({'error': '非法路径'}), 403

        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        return send_from_directory(config.OUTPUT_DIR, normalized)

    @app.route('/api/download-all')
    def download_all():
        username = request.args.get('username')
        task_id = request.args.get('task_id')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if task_id:
            safe_name = username or 'task'
            zip_filename = f'twitter_{safe_name}_{task_id}_{timestamp}.zip'
        else:
            zip_filename = f'twitter_{username}_{timestamp}.zip' if username else f'twitter_all_{timestamp}.zip'
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for target in _iter_download_targets(username, task_id):
                    if target['kind'] == 'file':
                        zipf.write(target['path'], target['arcname'])
                        continue

                    _, content = media_store.read_media_blob(
                        target['username'],
                        target['id'],
                        target['media_type'],
                        shard_key=target.get('shard_key'),
                    )
                    if content is None:
                        continue
                    zipf.writestr(target['arcname'], content)

            response = send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )
            response.call_on_close(lambda: os.path.exists(zip_path) and os.remove(zip_path))
            return response
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/view/<path:filepath>')
    def view_file(filepath):
        if '..' in filepath or filepath.startswith('/'):
            return "非法路径", 403

        normalized = filepath.lstrip('/')
        if normalized.startswith(f'{media_store.VIRTUAL_PREFIX}/'):
            return _serve_db_virtual_file(normalized)

        full_path = os.path.join(config.OUTPUT_DIR, normalized)
        real_path = os.path.realpath(full_path)
        real_output_dir = os.path.realpath(config.OUTPUT_DIR)

        if not _is_within_directory(real_output_dir, real_path):
            return "非法路径", 403

        if os.path.exists(full_path):
            return send_file(full_path)
        return "文件不存在", 404
