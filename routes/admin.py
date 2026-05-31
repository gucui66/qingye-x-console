"""
后台管理相关路由
"""
from datetime import datetime
import json
import os
import platform
import shutil
import sys
import tempfile
import zipfile

from flask import jsonify, request, send_file, send_from_directory, session

from core.auth import api_admin_required, change_admin_password
import core.config as config
from services import backfill_database_task_links, infer_legacy_task_artifacts, media_store
from services.feed_overrides import feed_overrides
from services.legacy_media import (
    collect_legacy_media as _collect_legacy_media,
    extract_tweet_id_from_filename as _extract_tweet_id_from_filename,
    peek_user_dirs as _peek_user_dirs,
    resolve_output_username as _resolve_output_username,
)
from services.user_directory import user_directory
from services.user_feed import build_user_feed_payload as _build_user_feed_payload
from tasks import task_manager


STATUS_META = {
    'pending': ('warning', '等待中'),
    'running': ('running', '运行中'),
    'paused': ('warning', '自动暂停'),
    'user_paused': ('warning', '手动暂停'),
    'completed': ('success', '已完成'),
    'failed': ('error', '失败'),
    'cancelled': ('error', '已取消'),
}

def _read_bearer_token_from_config() -> str:
    """从 .env 或当前运行配置读取 Bearer Token。"""
    try:
        if os.path.exists(config.ENV_FILE):
            with open(config.ENV_FILE, 'r', encoding='utf-8') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith('#') or not line.startswith('TWITTER_BEARER_TOKEN='):
                        continue
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"读取配置失败: {e}")

    return config.TWITTER_BEARER_TOKEN or ''


def _mask_secret(value: str) -> str:
    secret = str(value or '').strip()
    if not secret:
        return ''
    if len(secret) <= 12:
        return '*' * len(secret)
    return f'{secret[:6]}...{secret[-6:]}'


def _load_history():
    """读取任务历史。"""
    history_file = config.HISTORY_FILE
    if not os.path.exists(history_file):
        return []

    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取历史失败: {e}")
        return []


def _parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _format_datetime(value):
    parsed = _parse_datetime(value) if isinstance(value, str) else value
    if not parsed:
        return '暂无'
    return parsed.strftime('%Y-%m-%d %H:%M:%S')


def _format_file_size(size_bytes):
    size = int(size_bytes or 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024 / 1024 / 1024:.1f} GB"


def _safe_int(value, default: int, maximum: int = None, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _dir_size(path: str) -> int:
    if not os.path.exists(path):
        return 0

    total = 0
    for root, _, files in os.walk(path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                total += os.path.getsize(file_path)
            except OSError:
                continue
    return total


def _normalize_history(history_records):
    normalized = []

    for item in history_records:
        status = item.get('status', 'pending')
        status_class, status_text = STATUS_META.get(status, ('warning', status))
        created_at = _parse_datetime(item.get('created_at'))
        completed_at = _parse_datetime(item.get('completed_at'))
        sort_time = completed_at or created_at or datetime.min
        task_id = item.get('task_id', '')
        total_tweets = item.get('total_tweets', item.get('tweets', 0)) or 0
        videos = item.get('videos', 0) or 0
        photos = item.get('photos', 0) or 0

        normalized.append({
            'task_id': task_id,
            'task_id_short': task_id[-12:] if task_id else '-',
            'username': item.get('username', ''),
            'tweets': total_tweets,
            'videos': videos,
            'photos': photos,
            'status': status,
            'status_class': status_class,
            'status_text': status_text,
            'timestamp': _format_datetime(completed_at or created_at),
            'created_at_display': _format_datetime(created_at),
            'completed_at_display': _format_datetime(completed_at),
            'created_at': item.get('created_at'),
            'completed_at': item.get('completed_at'),
            'error_message': (item.get('error_message') or '').strip(),
            'sort_time': sort_time,
        })

    normalized.sort(key=lambda item: item['sort_time'], reverse=True)
    return normalized


def _collect_admin_files():
    """收集后台文件管理所需的全部用户文件。"""
    users_files = {}
    usernames_by_key = {}

    def _remember_username(raw_username: str):
        normalized = (raw_username or '').strip().lstrip('@')
        if not normalized:
            return
        bucket = usernames_by_key.setdefault(normalized.lower(), [])
        if normalized not in bucket:
            bucket.append(normalized)

    for username in media_store.list_usernames():
        _remember_username(username)
    if os.path.exists(config.OUTPUT_DIR):
        for username in os.listdir(config.OUTPUT_DIR):
            user_path = os.path.join(config.OUTPUT_DIR, username)
            if os.path.isdir(user_path):
                _remember_username(username)

    canonical_usernames = []
    for normalized_key in sorted(usernames_by_key):
        candidates = usernames_by_key[normalized_key]
        preferred = _resolve_output_username(candidates[0])
        if preferred and preferred.lower() == normalized_key:
            canonical_usernames.append(preferred)
            continue

        decorated = sorted(
            candidates,
            key=lambda name: (
                0 if any(char.isupper() for char in name) else 1,
                0 if name and not name.islower() else 1,
                len(name),
                name.lower(),
                name,
            ),
        )
        canonical_usernames.append(decorated[0])

    for username in canonical_usernames:
        if user_directory.is_hidden(username):
            continue
        user_dirs = _peek_user_dirs(username)
        videos = [
            {
                **item,
                'url': f"/output/{item['path']}",
            }
            for item in media_store.list_media(username, 'video')
        ]
        photos = [
            {
                **item,
                'url': f"/output/{item['path']}",
            }
            for item in media_store.list_media(username, 'photo')
        ]
        documents = []
        last_modified = max([item.get('modified_at', 0) for item in videos + photos] or [0])
        total_size = sum(item.get('size', 0) for item in videos + photos)

        if os.path.exists(user_dirs['videos']):
            for filename in os.listdir(user_dirs['videos']):
                if filename.endswith('.mp4'):
                    file_path = os.path.join(user_dirs['videos'], filename)
                    file_size = os.path.getsize(file_path)
                    modified_at = os.path.getmtime(file_path)
                    videos.append({
                        'name': filename,
                        'username': username,
                        'path': os.path.join(username, 'videos', filename),
                        'url': f'/output/{username}/videos/{filename}',
                        'size': file_size,
                        'modified_at': modified_at,
                        'storage_backend': 'filesystem',
                        'media_type': 'video',
                        'tweet_id': _extract_tweet_id_from_filename(filename),
                        'annotations': {
                            'favorite': False,
                            'watched': False,
                            'watch_later': False,
                            'tags': [],
                            'note': '',
                            'last_position': 0,
                            'play_count': 0,
                            'last_played_at': None,
                        },
                    })

        if os.path.exists(user_dirs['photos']):
            for filename in os.listdir(user_dirs['photos']):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    file_path = os.path.join(user_dirs['photos'], filename)
                    file_size = os.path.getsize(file_path)
                    modified_at = os.path.getmtime(file_path)
                    photos.append({
                        'name': filename,
                        'username': username,
                        'path': os.path.join(username, 'photos', filename),
                        'url': f'/output/{username}/photos/{filename}',
                        'size': file_size,
                        'modified_at': modified_at,
                        'storage_backend': 'filesystem',
                        'media_type': 'photo',
                        'tweet_id': _extract_tweet_id_from_filename(filename),
                        'annotations': {
                            'favorite': False,
                            'watched': False,
                            'watch_later': False,
                            'tags': [],
                            'note': '',
                            'last_position': 0,
                            'play_count': 0,
                            'last_played_at': None,
                        },
                    })

        if os.path.exists(user_dirs['documents']):
            for filename in os.listdir(user_dirs['documents']):
                if filename.endswith(('.html', '.md')):
                    file_path = os.path.join(user_dirs['documents'], filename)
                    file_size = os.path.getsize(file_path)
                    modified_at = os.path.getmtime(file_path)
                    documents.append({
                        'name': filename,
                        'url': f'/output/{username}/documents/{filename}',
                        'size': file_size,
                        'modified_at': modified_at,
                    })
                    total_size += file_size
                    last_modified = max(last_modified, modified_at)

        videos = media_store.dedupe_media_items(videos)
        photos = media_store.dedupe_media_items(photos)
        total_size = sum(item.get('size', 0) for item in videos + photos) + sum(item.get('size', 0) for item in documents)
        last_modified = max([item.get('modified_at', 0) for item in videos + photos + documents] or [0])

        if videos or photos or documents:
            users_files[username] = {
                'videos': videos,
                'photos': photos,
                'documents': documents,
                'summary': {
                    'videos': len(videos),
                    'photos': len(photos),
                    'documents': len(documents),
                    'total_files': len(videos) + len(photos) + len(documents),
                    'total_size': total_size,
                    'total_size_display': _format_file_size(total_size),
                    'last_modified': last_modified,
                    'last_modified_display': _format_datetime(
                        datetime.fromtimestamp(last_modified) if last_modified else None
                    ),
                },
            }

    return users_files


def _build_task_artifacts(task_id: str, username: str = None, task_payload: dict = None, history_entry: dict = None):
    results = {}
    if history_entry and isinstance(history_entry.get('results'), dict):
        results.update(history_entry.get('results') or {})
    if task_payload and isinstance(task_payload.get('results'), dict):
        results.update(task_payload.get('results') or {})

    base_artifacts = results.get('artifacts') or {}
    videos = media_store.list_media(username=username, media_type='video', task_id=task_id)
    photos = media_store.list_media(username=username, media_type='photo', task_id=task_id)
    documents = list(base_artifacts.get('documents') or [])
    screenshots = _collect_task_screenshots(task_id)

    if not videos or not photos or not documents:
        legacy_artifacts = infer_legacy_task_artifacts(task_id, username=username)
        if not videos:
            videos = legacy_artifacts.get('videos', [])
        if not photos:
            photos = legacy_artifacts.get('photos', [])
        if not documents:
            documents = legacy_artifacts.get('documents', [])

    summary = {
        'videos': len(videos),
        'photos': len(photos),
        'documents': len(documents),
        'screenshots': len(screenshots),
        'total_media_size_display': _format_file_size(sum(item.get('size', 0) for item in videos + photos)),
    }

    return {
        'summary': summary,
        'videos': videos,
        'photos': photos,
        'documents': documents,
        'screenshots': screenshots,
    }


def _build_live_task_summary():
    live_tasks = []
    active_statuses = {'pending', 'running', 'paused', 'user_paused'}

    for task in task_manager.get_all_tasks():
        status = task.get('status', 'pending')
        if status not in active_statuses:
            continue

        status_class, status_text = STATUS_META.get(status, ('warning', status))
        live_tasks.append({
            'task_id': task.get('task_id'),
            'username': task.get('username'),
            'status': status,
            'status_class': status_class,
            'status_text': status_text,
            'progress': task.get('progress', 0),
            'scraped_count': task.get('scraped_count', 0),
            'max_tweets': task.get('max_tweets'),
            'created_at_display': _format_datetime(task.get('created_at')),
            'error_message': task.get('error_message') or '',
            'results': task.get('results', {}),
        })

    live_tasks.sort(
        key=lambda item: (
            1 if item['status'] == 'running' else 0,
            item['progress'],
        ),
        reverse=True,
    )
    return live_tasks[:8]


def _build_library_rows(users_files):
    rows = []
    for username, payload in users_files.items():
        summary = payload.get('summary', {})
        rows.append({
            'username': username,
            'videos': summary.get('videos', 0),
            'photos': summary.get('photos', 0),
            'documents': summary.get('documents', 0),
            'total_files': summary.get('total_files', 0),
            'total_size_display': summary.get('total_size_display', '0 B'),
            'last_modified': summary.get('last_modified', 0),
            'last_modified_display': summary.get('last_modified_display', '暂无'),
        })

    rows.sort(key=lambda item: item['last_modified'], reverse=True)
    return rows[:10]


def _build_dashboard_summary(history_records, users_files, live_tasks):
    completed_count = sum(1 for item in history_records if item['status'] == 'completed')
    failed_count = sum(1 for item in history_records if item['status'] in {'failed', 'cancelled'})
    total_history = len(history_records)
    total_videos = sum(len(item.get('videos', [])) for item in users_files.values())
    total_photos = sum(len(item.get('photos', [])) for item in users_files.values())
    total_documents = sum(len(item.get('documents', [])) for item in users_files.values())
    total_storage = sum(item.get('summary', {}).get('total_size', 0) for item in users_files.values())
    success_rate = round((completed_count / total_history) * 100) if total_history else 0
    last_run = history_records[0]['timestamp'] if history_records else '暂无'

    return {
        'total_users': len(users_files),
        'total_tasks': total_history,
        'completed_tasks': completed_count,
        'failed_tasks': failed_count,
        'active_tasks': len(live_tasks),
        'total_videos': total_videos,
        'total_photos': total_photos,
        'total_documents': total_documents,
        'success_rate': success_rate,
        'last_run': last_run,
        'total_storage_display': _format_file_size(total_storage),
        'api_mode_enabled': bool(_read_bearer_token_from_config()),
    }


def _collect_task_screenshots(task_id: str):
    screenshot_dir = os.path.join(config.SCREENSHOTS_DIR, task_id)
    if not os.path.exists(screenshot_dir):
        return []

    screenshots = []
    for filename in sorted(os.listdir(screenshot_dir)):
        if not filename.lower().endswith('.png'):
            continue
        file_path = os.path.join(screenshot_dir, filename)
        screenshots.append({
            'name': filename,
            'url': f"/static/screenshots/{task_id}/{filename}",
            'modified_at': os.path.getmtime(file_path),
            'modified_at_display': _format_datetime(datetime.fromtimestamp(os.path.getmtime(file_path))),
        })
    screenshots.sort(key=lambda item: item['modified_at'], reverse=True)
    return screenshots


def _get_task_history_entry(task_id: str):
    history = _load_history()
    for item in history:
        if item.get('task_id') == task_id:
            return item
    return None


def _build_task_detail(task_id: str):
    live_task = task_manager.get_task(task_id)
    history_entry = _get_task_history_entry(task_id)
    task_payload = live_task.to_dict() if live_task else (history_entry or {})
    username = task_payload.get('username') or (history_entry or {}).get('username')
    normalized_history = _normalize_history(_load_history())
    related_history = [item for item in normalized_history if item.get('username') == username][:8] if username else []
    diff = _build_recent_diff(username) if username else None
    artifacts = _build_task_artifacts(task_id, username=username, task_payload=task_payload, history_entry=history_entry)

    return {
        'task': task_payload,
        'history_entry': history_entry,
        'screenshots': artifacts['screenshots'],
        'artifacts': artifacts,
        'integrity': _build_task_integrity_report(task_id, task_payload, history_entry, artifacts),
        'related_history': related_history,
        'diff': diff,
    }


def _build_task_integrity_report(task_id: str, task_payload: dict = None, history_entry: dict = None, artifacts: dict = None):
    """给任务详情页使用的轻量完整性报告。"""
    task_payload = task_payload or {}
    history_entry = history_entry or {}
    artifacts = artifacts or {'summary': {}, 'videos': [], 'photos': [], 'documents': [], 'screenshots': []}
    results = {}
    if isinstance(history_entry.get('results'), dict):
        results.update(history_entry.get('results') or {})
    if isinstance(task_payload.get('results'), dict):
        results.update(task_payload.get('results') or {})

    username = task_payload.get('username') or history_entry.get('username')
    videos = artifacts.get('videos') or []
    photos = artifacts.get('photos') or []
    documents = artifacts.get('documents') or []
    screenshots = artifacts.get('screenshots') or []
    stored_video_count = len(videos)
    stored_photo_count = len(photos)
    expected_videos = int(history_entry.get('videos') or results.get('videos') or stored_video_count or 0)
    expected_photos = int(history_entry.get('photos') or results.get('photos') or stored_photo_count or 0)
    scraped_tweets = int(
        history_entry.get('total_tweets')
        or results.get('total_tweets')
        or len(results.get('tweets') or [])
        or task_payload.get('scraped_count')
        or 0
    )
    missing_videos = max(expected_videos - stored_video_count, 0)
    missing_photos = max(expected_photos - stored_photo_count, 0)
    missing_thumbnails = sum(
        1 for item in videos
        if item.get('storage_backend') != 'filesystem' and not item.get('thumbnail_path') and not item.get('thumbnail_url')
    )
    duplicate_payload = media_store.list_duplicate_files(username=username, task_id=task_id, limit=200) if task_id else {'items': [], 'summary': {}}
    duplicate_summary = duplicate_payload.get('summary') or {}

    issues = []
    status = task_payload.get('status') or history_entry.get('status')
    error_message = task_payload.get('error_message') or history_entry.get('error_message')
    if status in {'failed', 'cancelled'}:
        issues.append({
            'level': 'error',
            'title': '任务未正常完成',
            'description': error_message or '任务结束状态异常，建议检查截图时间线后重试。',
        })
    if missing_videos or missing_photos:
        issues.append({
            'level': 'warning',
            'title': '产物数量和记录数量不完全一致',
            'description': f'记录中视频 {expected_videos} 个、照片 {expected_photos} 个；当前可管理产物视频 {stored_video_count} 个、照片 {stored_photo_count} 个。',
        })
    if missing_thumbnails:
        issues.append({
            'level': 'warning',
            'title': '部分视频缺少预览图',
            'description': f'本任务有 {missing_thumbnails} 个视频没有缩略图，可在数据库维护中心批量补全。',
        })
    if duplicate_summary.get('total'):
        issues.append({
            'level': 'info',
            'title': '存在重复暂存文件',
            'description': f'本任务有 {duplicate_summary.get("total", 0)} 个重复文件已放入暂存区，原始产物仍可手动保留或删除。',
        })

    health = 'ok'
    if any(item['level'] == 'error' for item in issues):
        health = 'error'
    elif any(item['level'] == 'warning' for item in issues):
        health = 'warning'
    elif issues:
        health = 'info'

    return {
        'health': health,
        'health_text': {
            'ok': '完整',
            'info': '可整理',
            'warning': '需检查',
            'error': '异常',
        }.get(health, '未知'),
        'counts': {
            'scraped_tweets': scraped_tweets,
            'expected_videos': expected_videos,
            'stored_videos': stored_video_count,
            'missing_videos': missing_videos,
            'expected_photos': expected_photos,
            'stored_photos': stored_photo_count,
            'missing_photos': missing_photos,
            'documents': len(documents),
            'screenshots': len(screenshots),
            'missing_thumbnails': missing_thumbnails,
            'duplicates': duplicate_summary.get('total', 0) or 0,
        },
        'duplicate_summary': duplicate_summary,
        'issues': issues,
        'can_retry': status in {'failed', 'cancelled'},
    }


def _build_retry_options(source: dict):
    options = source.get('options') if isinstance(source.get('options'), dict) else {}
    return {
        'download_videos': options.get('download_videos', True),
        'download_photos': options.get('download_photos', True),
        'download_replies': options.get('download_replies', True),
        'scrape_method': options.get('scrape_method') or 'selenium',
        'selenium_behavior_mode': options.get('selenium_behavior_mode') or 'balanced',
    }


def _retry_task_from_record(task_id: str, overrides: dict = None):
    live_task = task_manager.get_task(task_id)
    source = live_task.to_dict() if live_task else (_get_task_history_entry(task_id) or {})
    if not source:
        return None, '任务不存在'

    username = (source.get('username') or '').strip().lstrip('@')
    if not username:
        return None, '任务缺少账号信息，无法重试'

    overrides = overrides or {}
    max_tweets = overrides.get('max_tweets') or source.get('max_tweets') or source.get('total_tweets') or 100
    try:
        max_tweets = max(1, int(max_tweets))
    except (TypeError, ValueError):
        max_tweets = 100

    options = _build_retry_options(source)
    for key in ('download_videos', 'download_photos', 'download_replies', 'scrape_method', 'selenium_behavior_mode'):
        if key in overrides:
            options[key] = overrides[key]

    task, existed = task_manager.add_or_get_active_task(username, max_tweets, options)
    return {
        'success': True,
        'message': f'@{username} 已重新加入任务队列' if not existed else f'@{username} 已有进行中的任务，已定位到现有任务',
        'task_id': task.task_id,
        'existing_task': existed,
        'source_task_id': task_id,
        'username': username,
        'status': task.status,
    }, None


def _build_recent_diff(username: str):
    if not username:
        return None

    normalized = (username or '').strip().lstrip('@')
    relevant = [
        item for item in _normalize_history(_load_history())
        if item['username'] == normalized and item['status'] == 'completed'
    ]
    if not relevant:
        return None

    current = relevant[0]
    previous = relevant[1] if len(relevant) > 1 else None
    if not previous:
        return {
            'username': normalized,
            'current': current,
            'previous': None,
            'delta': {
                'tweets': current['tweets'],
                'videos': current['videos'],
                'photos': current['photos'],
            },
        }

    return {
        'username': normalized,
        'current': current,
        'previous': previous,
        'delta': {
            'tweets': current['tweets'] - previous['tweets'],
            'videos': current['videos'] - previous['videos'],
            'photos': current['photos'] - previous['photos'],
        },
    }


def _build_media_center_payload(username=None, media_type=None, task_id=None, query='', favorite=None, watched=None, watch_later=None, sort='latest', limit=120):
    if query:
        db_items = media_store.search_media(query, username=username, media_type=media_type, task_id=task_id, limit=limit)
        fs_items = []
        for item in _collect_legacy_media(username=username, media_type=media_type, task_id=task_id):
            haystack = f"{item.get('name', '')} {item.get('path', '')} {item.get('username', '')}".lower()
            if query.lower() in haystack:
                fs_items.append(item)
        items = media_store.dedupe_media_items(db_items + fs_items)
    else:
        items = media_store.dedupe_media_items(media_store.list_media(username=username, media_type=media_type, task_id=task_id) + _collect_legacy_media(
            username=username,
            media_type=media_type,
            task_id=task_id,
        ))

    filtered = []
    for item in items:
        annotations = item.get('annotations', {})
        if favorite is not None and bool(annotations.get('favorite')) != favorite:
            continue
        if watched is not None and bool(annotations.get('watched')) != watched:
            continue
        if watch_later is not None and bool(annotations.get('watch_later')) != watch_later:
            continue
        filtered.append(item)

    if sort == 'largest':
        filtered.sort(key=lambda item: item.get('size', 0), reverse=True)
    elif sort == 'plays':
        filtered.sort(key=lambda item: item.get('annotations', {}).get('play_count', 0), reverse=True)
    else:
        filtered.sort(key=lambda item: item.get('modified_at', 0), reverse=True)

    limited = filtered[:limit]
    summary = {
        'total_items': len(filtered),
        'favorites': sum(1 for item in filtered if item.get('annotations', {}).get('favorite')),
        'watched': sum(1 for item in filtered if item.get('annotations', {}).get('watched')),
        'watch_later': sum(1 for item in filtered if item.get('annotations', {}).get('watch_later')),
        'anomalies': sum(
            1 for item in filtered
            if (item.get('media_type') == 'video' and item.get('size', 0) < 300 * 1024)
            or not item.get('tweet_url')
        ),
        'storage_total': _format_file_size(sum(item.get('size', 0) for item in filtered)),
    }

    return {
        'summary': summary,
        'items': limited,
    }


def _build_database_user_rows():
    rows = media_store.summarize_by_username()
    for row in rows:
        row['total_size_display'] = _format_file_size(row.get('total_size', 0))
        row['last_modified_display'] = _format_datetime(
            datetime.fromtimestamp(row['last_modified']) if row.get('last_modified') else None
        )
    return rows


def _build_database_task_rows():
    history_map = {item.get('task_id'): item for item in _normalize_history(_load_history())}
    rows = []
    seen_task_ids = set()
    for row in media_store.summarize_by_task():
        history_item = history_map.get(row.get('task_id')) or {}
        artifact_docs = ((history_item.get('artifacts') or {}).get('documents') or [])
        seen_task_ids.add(row.get('task_id'))
        rows.append({
            **row,
            'documents': len(artifact_docs),
            'status': history_item.get('status'),
            'status_text': STATUS_META.get(history_item.get('status'), ('default', '未知'))[1] if history_item else '未知',
            'created_at': history_item.get('created_at'),
            'completed_at': history_item.get('completed_at'),
            'total_size_display': _format_file_size(row.get('total_size', 0)),
            'last_modified_display': _format_datetime(
                datetime.fromtimestamp(row['last_modified']) if row.get('last_modified') else None
            ),
        })

    for task_id, history_item in history_map.items():
        if task_id in seen_task_ids:
            continue
        artifact_docs = ((history_item.get('artifacts') or {}).get('documents') or [])
        rows.append({
            'task_id': task_id,
            'username': history_item.get('username'),
            'total_items': (history_item.get('videos', 0) or 0) + (history_item.get('photos', 0) or 0),
            'videos': history_item.get('videos', 0) or 0,
            'photos': history_item.get('photos', 0) or 0,
            'documents': len(artifact_docs),
            'status': history_item.get('status'),
            'status_text': STATUS_META.get(history_item.get('status'), ('default', '未知'))[1],
            'created_at': history_item.get('created_at'),
            'completed_at': history_item.get('completed_at'),
            'total_size': 0,
            'total_size_display': _format_file_size(0),
            'last_modified': (_parse_datetime(history_item.get('completed_at')) or _parse_datetime(history_item.get('created_at')) or datetime.min).timestamp() if (_parse_datetime(history_item.get('completed_at')) or _parse_datetime(history_item.get('created_at'))) else 0,
            'last_modified_display': _format_datetime(history_item.get('completed_at') or history_item.get('created_at')),
            'shard_keys': [],
        })
    rows.sort(key=lambda item: item.get('last_modified', 0), reverse=True)
    return rows


def _build_search_payload(query: str):
    keyword = (query or '').strip()
    if not keyword:
        return {
            'query': '',
            'media': [],
            'tasks': [],
            'users': [],
        }

    media_results = media_store.search_media(keyword, limit=30)
    for item in _collect_legacy_media():
        haystack = f"{item.get('name', '')} {item.get('path', '')} {item.get('username', '')}".lower()
        if keyword.lower() in haystack:
            media_results.append(item)
    media_results = media_store.dedupe_media_items(media_results)
    media_results.sort(key=lambda item: item.get('modified_at', 0), reverse=True)
    media_results = media_results[:30]
    task_results = []
    for task in task_manager.get_all_tasks():
        haystack = f"{task.get('task_id', '')} {task.get('username', '')} {task.get('error_message', '')}".lower()
        if keyword.lower() in haystack:
            task_results.append(task)

    history_matches = []
    for item in _normalize_history(_load_history()):
        haystack = f"{item.get('task_id', '')} {item.get('username', '')} {item.get('error_message', '')}".lower()
        if keyword.lower() in haystack:
            history_matches.append(item)

    all_usernames = set(media_store.list_usernames())
    if os.path.exists(config.OUTPUT_DIR):
        for name in os.listdir(config.OUTPUT_DIR):
            if os.path.isdir(os.path.join(config.OUTPUT_DIR, name)):
                all_usernames.add(name)

    users = []
    for username in sorted(all_usernames):
        if user_directory.is_hidden(username):
            continue
        if keyword.lower() in username.lower():
            diff = _build_recent_diff(username)
            users.append({
                'username': username,
                'diff': diff,
            })

    return {
        'query': keyword,
        'media': media_results,
        'tasks': task_results[:12],
        'history': history_matches[:12],
        'users': users[:12],
    }


def _build_system_payload():
    history = _normalize_history(_load_history())
    users_files = _collect_admin_files()
    active_tasks = _build_live_task_summary()
    queue_size = task_manager.task_queue.qsize() if hasattr(task_manager.task_queue, 'qsize') else 0
    latest_completed_per_user = []
    for username in media_store.list_usernames()[:20]:
        diff = _build_recent_diff(username)
        if diff:
            latest_completed_per_user.append(diff)

    latest_completed_per_user.sort(
        key=lambda item: item['current']['sort_time'] if item.get('current') else datetime.min,
        reverse=True,
    )

    return {
        'runtime': {
            'python': sys.version.split()[0],
            'platform': platform.platform(),
            'hostname': platform.node(),
            'active_tasks': len(active_tasks),
            'queue_size': queue_size,
            'max_workers': getattr(task_manager, 'max_workers', 0),
        },
        'storage': {
            'data_dir': config.DATA_DIR,
            'output_dir': config.OUTPUT_DIR,
            'media_shards_dir': config.MEDIA_SHARDS_DIR,
            'screenshots_dir': config.SCREENSHOTS_DIR,
            'data_size_display': _format_file_size(_dir_size(config.DATA_DIR)),
            'output_size_display': _format_file_size(_dir_size(config.OUTPUT_DIR)),
            'screenshots_size_display': _format_file_size(_dir_size(config.SCREENSHOTS_DIR)),
            'users': len(users_files),
        },
        'history': {
            'completed': sum(1 for item in history if item['status'] == 'completed'),
            'failed': sum(1 for item in history if item['status'] in {'failed', 'cancelled'}),
            'total': len(history),
        },
        'activity': latest_completed_per_user[:10],
    }


def _build_database_shard_detail(identifier: str):
    detail = media_store.inspect_shard_detail(identifier)
    if not detail:
        return None

    related_usernames = set(detail.get('usernames') or [])
    if detail.get('username'):
        related_usernames.add(detail['username'])

    related_history = [
        item for item in _normalize_history(_load_history())
        if item['username'] in related_usernames
    ][:12]

    detail.update({
        'size_display': _format_file_size(detail.get('size_bytes', 0)),
        'modified_at_display': _format_datetime(datetime.fromtimestamp(detail['modified_at'])),
        'related_history': related_history,
    })
    return detail


def _build_database_health():
    report = media_store.health_report()
    for shard in report['shards']:
        shard['size_display'] = _format_file_size(shard.get('size_bytes', 0))
        shard['modified_at_display'] = _format_datetime(datetime.fromtimestamp(shard['modified_at']))
    return report


def _build_maintenance_report():
    report = media_store.build_maintenance_report()
    report['duplicates']['total_size_display'] = _format_file_size(report['duplicates'].get('total_size', 0))
    history = _normalize_history(_load_history())
    report['tasks'] = {
        'failed_or_cancelled': sum(1 for item in history if item['status'] in {'failed', 'cancelled'}),
        'recent_failures': [item for item in history if item['status'] in {'failed', 'cancelled'}][:10],
    }
    return report


def _build_database_backup(shard_key: str = None):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = (shard_key or 'all').replace(':', '_')
    zip_filename = f'database_backup_{safe_name}_{timestamp}.zip'
    zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
    targets = media_store.get_shard_backup_paths(shard_key)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for db_path in targets:
            if os.path.exists(db_path):
                zipf.write(db_path, os.path.basename(db_path))

    return zip_path, zip_filename


def _serve_spa_shell(app):
    vue_dist_dir = os.path.join(app.static_folder, 'vue')
    vue_index_file = os.path.join(vue_dist_dir, 'index.html')

    if os.path.exists(vue_index_file):
        response = send_from_directory(vue_dist_dir, 'index.html')
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return (
        "Vue 前端构建产物不存在，请先在 frontend/ 目录执行 npm install && npm run build，"
        "然后再执行 docker compose up --build -d。",
        503,
    )


def register_admin_routes(app):
    """注册后台管理相关路由。"""

    @app.route('/api/admin/overview')
    @api_admin_required
    def admin_overview():
        history = _normalize_history(_load_history())
        users_files = _collect_admin_files()
        live_tasks = _build_live_task_summary()
        dashboard = _build_dashboard_summary(history, users_files, live_tasks)
        libraries = _build_library_rows(users_files)
        recent_failures = [item for item in history if item['status'] in {'failed', 'cancelled'}][:8]
        media_snapshot = _build_media_center_payload(media_type='video', limit=8)

        return jsonify({
            'summary': dashboard,
            'history': history[:30],
            'live_tasks': live_tasks,
            'libraries': libraries,
            'recent_failures': recent_failures,
            'media_snapshot': media_snapshot,
            'maintenance': _build_maintenance_report(),
        })

    @app.route('/api/admin/usernames')
    @api_admin_required
    def admin_usernames():
        include_hidden = str(request.args.get('include_hidden', 'true')).lower() not in {'false', '0', 'no'}
        return jsonify({
            'items': user_directory.list_items(include_hidden=include_hidden),
        })

    @app.route('/api/admin/usernames/<username>', methods=['POST'])
    @api_admin_required
    def admin_update_username(username):
        data = request.json or {}
        try:
            item = user_directory.update_item(
                username,
                alias=data.get('alias') if 'alias' in data else None,
                hidden=data.get('hidden') if 'hidden' in data else None,
                reset=bool(data.get('reset')),
            )
            return jsonify({'success': True, 'item': item})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/files')
    @api_admin_required
    def admin_files():
        try:
            return jsonify(_collect_admin_files())
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/media')
    @api_admin_required
    def admin_media():
        try:
            username = request.args.get('username')
            media_type = request.args.get('media_type') or None
            task_id = request.args.get('task_id') or None
            query = request.args.get('query', '')
            favorite = request.args.get('favorite')
            watched = request.args.get('watched')
            watch_later = request.args.get('watch_later')
            sort = request.args.get('sort', 'latest')
            limit = _safe_int(request.args.get('limit'), default=120, maximum=300)

            def _parse_flag(value):
                if value is None or value == '':
                    return None
                return value.lower() in {'1', 'true', 'yes', 'on'}

            return jsonify(
                _build_media_center_payload(
                    username=username,
                    media_type=media_type,
                    task_id=task_id,
                    query=query,
                    favorite=_parse_flag(favorite),
                    watched=_parse_flag(watched),
                    watch_later=_parse_flag(watch_later),
                    sort=sort,
                    limit=limit,
                )
            )
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/media/annotation', methods=['POST'])
    @api_admin_required
    def admin_media_annotation():
        data = request.json or {}
        username = (data.get('username') or '').strip().lstrip('@')
        media_type = (data.get('media_type') or '').strip()
        media_id = data.get('media_id')
        shard_key = (data.get('shard_key') or '').strip() or None
        if not username or media_type not in {'video', 'photo'} or not media_id:
            return jsonify({'error': '缺少必要参数'}), 400

        try:
            updated = media_store.update_media_annotation(username, int(media_id), media_type, data, shard_key=shard_key)
            if not updated:
                return jsonify({'error': '媒体不存在'}), 404
            return jsonify({'success': True, 'item': updated})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/duplicates')
    @api_admin_required
    def admin_duplicate_media():
        try:
            username = request.args.get('username') or None
            task_id = request.args.get('task_id') or None
            media_type = request.args.get('media_type') or None
            include_deleted = str(request.args.get('include_deleted') or '').lower() in {'1', 'true', 'yes', 'on'}
            limit = _safe_int(request.args.get('limit'), default=200, maximum=500)
            return jsonify(media_store.list_duplicate_files(
                username=username,
                task_id=task_id,
                media_type=media_type,
                include_deleted=include_deleted,
                limit=limit,
            ))
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/duplicates/<int:duplicate_id>', methods=['DELETE'])
    @api_admin_required
    def admin_delete_duplicate_media(duplicate_id):
        try:
            item = media_store.delete_duplicate_file(duplicate_id, shard_key=request.args.get('shard_key'))
            if not item:
                return jsonify({'error': '重复文件不存在'}), 404
            return jsonify({'success': True, 'item': item})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/task-detail/<task_id>')
    @api_admin_required
    def admin_task_detail(task_id):
        detail = _build_task_detail(task_id)
        if not detail.get('task') and not detail.get('history_entry'):
            return jsonify({'error': '任务不存在'}), 404
        return jsonify(detail)

    @app.route('/api/admin/tasks/<task_id>/retry', methods=['POST'])
    @api_admin_required
    def admin_retry_task(task_id):
        try:
            payload, error = _retry_task_from_record(task_id, request.json or {})
            if error:
                return jsonify({'error': error}), 404
            return jsonify(payload)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/search')
    @api_admin_required
    def admin_search():
        query = request.args.get('q', '')
        return jsonify(_build_search_payload(query))

    @app.route('/api/admin/feed/<username>')
    @api_admin_required
    def admin_user_feed(username):
        limit = _safe_int(request.args.get('limit'), default=120, maximum=1000)
        return jsonify(_build_user_feed_payload(username, limit=limit))

    @app.route('/api/admin/feed/<username>/posts/<tweet_id>/content', methods=['POST'])
    @api_admin_required
    def admin_update_user_feed_content(username, tweet_id):
        data = request.json or {}
        try:
            override = feed_overrides.update_post_content(
                username,
                tweet_id,
                data.get('content') or '',
            )
            return jsonify({'success': True, 'override': override})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/feed/<username>/posts/<tweet_id>/content/reset', methods=['POST'])
    @api_admin_required
    def admin_reset_user_feed_content(username, tweet_id):
        try:
            removed = feed_overrides.reset_post_content(username, tweet_id)
            return jsonify({'success': True, 'removed': removed})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/feed/<username>/posts/<tweet_id>/videos/hide', methods=['POST'])
    @api_admin_required
    def admin_hide_user_feed_video(username, tweet_id):
        data = request.json or {}
        try:
            hidden = feed_overrides.hide_video(username, tweet_id, data)
            return jsonify({'success': True, 'hidden': hidden})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/feed/<username>/posts/<tweet_id>/videos/restore', methods=['POST'])
    @api_admin_required
    def admin_restore_user_feed_videos(username, tweet_id):
        try:
            restored = feed_overrides.restore_videos(username, tweet_id)
            return jsonify({'success': True, 'restored': restored})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/system')
    @api_admin_required
    def admin_system():
        return jsonify(_build_system_payload())

    @app.route('/api/admin/diff/<username>')
    @api_admin_required
    def admin_diff(username):
        payload = _build_recent_diff(username.strip().lstrip('@'))
        if not payload:
            return jsonify({'error': '没有可比较的历史记录'}), 404
        return jsonify(payload)

    @app.route('/api/admin/database')
    @api_admin_required
    def admin_database():
        shards = media_store.inspect_shards()
        bucket_count = sum(1 for item in shards if item.get('shard_type') == 'bucket')
        legacy_count = sum(1 for item in shards if item.get('shard_type') == 'legacy')
        summary = {
            'shard_count': len(shards),
            'bucket_count': bucket_count,
            'legacy_count': legacy_count,
            'total_size_bytes': sum(item.get('size_bytes', 0) for item in shards),
            'total_videos': sum(item.get('videos', 0) for item in shards),
            'total_photos': sum(item.get('photos', 0) for item in shards),
            'total_items': sum(item.get('total_items', 0) for item in shards),
            'shards_dir': config.MEDIA_SHARDS_DIR,
        }
        user_rows = _build_database_user_rows()
        task_rows = _build_database_task_rows()

        return jsonify({
            'summary': {
                **summary,
                'total_size_display': _format_file_size(summary['total_size_bytes']),
            },
            'users': user_rows,
            'tasks': task_rows,
            'shards': [
                {
                    **item,
                    'size_display': _format_file_size(item.get('size_bytes', 0)),
                    'modified_at_display': _format_datetime(
                        datetime.fromtimestamp(item['modified_at']) if item.get('modified_at') else None
                    ),
                    'latest_media_modified_display': _format_datetime(
                        datetime.fromtimestamp(item['latest_media_modified'])
                        if item.get('latest_media_modified') else None
                    ),
                }
                for item in shards
            ],
        })

    @app.route('/api/admin/database/health')
    @api_admin_required
    def admin_database_health():
        return jsonify(_build_database_health())

    @app.route('/api/admin/maintenance/report')
    @api_admin_required
    def admin_maintenance_report():
        return jsonify(_build_maintenance_report())

    @app.route('/api/admin/maintenance/backfill-thumbnails', methods=['POST'])
    @api_admin_required
    def admin_backfill_thumbnails():
        data = request.json or {}
        limit = _safe_int(data.get('limit'), default=80, maximum=300)
        username = data.get('username') or None
        try:
            result = media_store.backfill_video_thumbnails(username=username, limit=limit)
            return jsonify({'success': True, 'result': result, 'report': _build_maintenance_report()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/maintenance/scan-duplicates', methods=['POST'])
    @api_admin_required
    def admin_scan_duplicates():
        data = request.json or {}
        limit = _safe_int(data.get('limit'), default=200, maximum=500)
        username = data.get('username') or None
        try:
            result = media_store.scan_historical_duplicates(username=username, limit=limit)
            return jsonify({'success': True, 'result': result, 'report': _build_maintenance_report()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/maintenance/backfill-task-links', methods=['POST'])
    @api_admin_required
    def admin_backfill_task_links():
        try:
            result = backfill_database_task_links()
            return jsonify({'success': True, 'result': result, 'report': _build_maintenance_report()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/database/shards/<path:shard_key>')
    @api_admin_required
    def admin_database_shard_detail(shard_key):
        detail = _build_database_shard_detail(shard_key.strip())
        if not detail:
            return jsonify({'error': '数据库分片不存在'}), 404
        return jsonify(detail)

    @app.route('/api/admin/database/backup')
    @api_admin_required
    def admin_database_backup():
        shard_key = (request.args.get('shard_key') or '').strip() or None
        try:
            zip_path, zip_filename = _build_database_backup(shard_key)
            response = send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename,
            )
            response.call_on_close(lambda: os.path.exists(zip_path) and os.remove(zip_path))
            return response
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/admin/database/migrate-legacy', methods=['POST'])
    @api_admin_required
    def admin_database_migrate_legacy():
        data = request.json or {}
        shard_key = (data.get('shard_key') or '').strip() or None
        try:
            if shard_key:
                result = media_store.migrate_legacy_shard(shard_key)
            else:
                result = media_store.migrate_all_legacy_shards()
            return jsonify({
                'success': True,
                'message': '旧版账号库迁移完成',
                'result': result,
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    @app.route('/api/admin/config', methods=['GET'])
    @api_admin_required
    def admin_config_status():
        bearer_token = _read_bearer_token_from_config()
        return jsonify({
            'bearer_token': '',
            'bearer_token_masked': _mask_secret(bearer_token),
            'bearer_token_configured': bool(bearer_token),
            'api_mode_enabled': bool(bearer_token),
            'env_file': config.ENV_FILE,
            'media_shards_dir': config.MEDIA_SHARDS_DIR,
            'output_dir': config.OUTPUT_DIR,
            'data_dir': config.DATA_DIR,
            'screenshots_dir': config.SCREENSHOTS_DIR,
            'port': os.getenv('PORT', '5001'),
            'selenium_headless': config.SELENIUM_HEADLESS,
            'generate_html_doc': config.GENERATE_HTML_DOC,
            'generate_md_doc': config.GENERATE_MD_DOC,
        })

    @app.route('/api/admin/config', methods=['POST'])
    @api_admin_required
    def admin_config_update():
        data = request.json or {}
        current_bearer_token = _read_bearer_token_from_config()
        requested_bearer_token = (data.get('bearer_token') or '').strip()
        should_clear_bearer_token = bool(data.get('clear_bearer_token'))
        bearer_token = requested_bearer_token or current_bearer_token
        if should_clear_bearer_token:
            bearer_token = ''
        env_file = config.ENV_FILE

        try:
            lines = []
            if os.path.exists(env_file):
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

            new_line = f"TWITTER_BEARER_TOKEN={bearer_token}\n"
            replaced = False
            updated_lines = []

            for line in lines:
                if line.strip().startswith('TWITTER_BEARER_TOKEN='):
                    updated_lines.append(new_line)
                    replaced = True
                else:
                    updated_lines.append(line)

            if not replaced:
                if updated_lines and not updated_lines[-1].endswith('\n'):
                    updated_lines[-1] += '\n'
                updated_lines.append(new_line)

            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)

            os.environ['TWITTER_BEARER_TOKEN'] = bearer_token
            config.TWITTER_BEARER_TOKEN = bearer_token
            return jsonify({
                'success': True,
                'message': '配置已保存，请重启服务器以完全生效',
            })
        except Exception as e:
            return jsonify({'success': False, 'error': f'保存失败: {str(e)}'}), 500

    @app.route('/api/admin/change-password', methods=['POST'])
    @api_admin_required
    def admin_change_password():
        data = request.json or {}
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')

        if new_password != confirm_password:
            return jsonify({'success': False, 'error': '两次输入的新密码不一致'}), 400
        if not new_password or len(new_password) < 6:
            return jsonify({'success': False, 'error': '密码长度不能少于6位'}), 400
        if change_admin_password(old_password, new_password):
            return jsonify({'success': True, 'message': '密码修改成功'})
        return jsonify({'success': False, 'error': '原密码错误'}), 400

    @app.route('/admin/logout')
    def admin_logout():
        session.pop('admin_logged_in', None)
        session.pop('user_logged_in', None)
        session.pop('username', None)
        return _serve_spa_shell(app)

    @app.route('/', defaults={'spa_path': ''})
    @app.route('/<path:spa_path>')
    def spa_entry(spa_path):
        reserved_prefixes = ('api/', 'output/', 'view/', 'static/')
        if spa_path and any(spa_path.startswith(prefix) for prefix in reserved_prefixes):
            return jsonify({'error': '页面不存在'}), 404
        return _serve_spa_shell(app)
