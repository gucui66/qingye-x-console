"""
任务产物推断与旧任务兼容
"""
from datetime import datetime
import json
import os
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import core.config as config


LOCAL_TZ = ZoneInfo('Asia/Shanghai')
HISTORY_TO_FILESYSTEM_OFFSET_SECONDS = 8 * 3600


def parse_datetime(value):
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TZ)
        return parsed
    except (TypeError, ValueError):
        return None


def load_history_records() -> List[Dict]:
    if not os.path.exists(config.HISTORY_FILE):
        return []
    try:
        with open(config.HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _normalize_username(username: str) -> str:
    return (username or '').strip().lstrip('@')


def _peek_user_dirs(username: str):
    user_output_dir = os.path.join(config.OUTPUT_DIR, username)
    return {
        'output': user_output_dir,
        'videos': os.path.join(user_output_dir, 'videos'),
        'photos': os.path.join(user_output_dir, 'photos'),
        'documents': os.path.join(user_output_dir, 'documents'),
    }


def _build_task_windows(username: str, history_records: List[Dict]) -> List[Dict]:
    normalized = _normalize_username(username)
    rows = []
    for item in history_records:
        if _normalize_username(item.get('username')) != normalized:
            continue
        created_at = parse_datetime(item.get('created_at'))
        completed_at = parse_datetime(item.get('completed_at')) or created_at
        rows.append({
            'task_id': item.get('task_id'),
            'created_at': created_at,
            'completed_at': completed_at,
            'source': item,
        })

    rows.sort(key=lambda row: row['created_at'] or datetime.min)
    windows = []
    for index, row in enumerate(rows):
        prev_completed = rows[index - 1]['completed_at'] if index > 0 else None
        next_created = rows[index + 1]['created_at'] if index + 1 < len(rows) else None

        start_dt = row['created_at'] or row['completed_at'] or prev_completed
        end_dt = row['completed_at'] or next_created or start_dt

        start_ts = start_dt.timestamp() if start_dt else 0
        end_ts = end_dt.timestamp() if end_dt else start_ts

        if prev_completed:
            start_ts = max(start_ts, prev_completed.timestamp() - 2)
        else:
            start_ts -= 300

        if next_created:
            end_ts = min(end_ts + 600, next_created.timestamp() - 1)
        else:
            end_ts += 1800

        windows.append({
            'task_id': row['task_id'],
            'start_ts': start_ts + HISTORY_TO_FILESYSTEM_OFFSET_SECONDS,
            'end_ts': max(end_ts, start_ts) + HISTORY_TO_FILESYSTEM_OFFSET_SECONDS,
            'source': row['source'],
        })
    return windows


def _build_fs_item(username: str, file_path: str, relative_path: str, kind: str) -> Dict:
    return {
        'name': os.path.basename(file_path),
        'username': username,
        'task_id': None,
        'path': relative_path,
        'url': f"/output/{relative_path}",
        'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        'modified_at': os.path.getmtime(file_path) if os.path.exists(file_path) else 0,
        'storage_backend': 'filesystem',
        'media_type': kind if kind in {'video', 'photo'} else None,
        'document_type': kind if kind not in {'video', 'photo'} else None,
    }


def infer_legacy_task_artifacts(task_id: str, username: str = None, history_records: Optional[List[Dict]] = None) -> Dict:
    history_records = history_records or load_history_records()
    target = next((item for item in history_records if item.get('task_id') == task_id), None)
    if not target:
        return {
            'summary': {'videos': 0, 'photos': 0, 'documents': 0, 'screenshots': 0, 'total_media_size_display': '0 B'},
            'videos': [],
            'photos': [],
            'documents': [],
        }

    normalized = _normalize_username(username or target.get('username'))
    user_dirs = _peek_user_dirs(normalized)
    windows = _build_task_windows(normalized, history_records)
    window = next((item for item in windows if item['task_id'] == task_id), None)
    if not window:
        return {
            'summary': {'videos': 0, 'photos': 0, 'documents': 0, 'screenshots': 0, 'total_media_size_display': '0 B'},
            'videos': [],
            'photos': [],
            'documents': [],
        }

    def collect(folder_key: str, suffixes: tuple, kind: str):
        folder = user_dirs[folder_key]
        rows = []
        if not os.path.exists(folder):
            return rows
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if not os.path.isfile(file_path):
                continue
            if not filename.lower().endswith(suffixes):
                continue
            modified_at = os.path.getmtime(file_path)
            if window['start_ts'] <= modified_at <= window['end_ts']:
                relative_path = os.path.relpath(file_path, config.OUTPUT_DIR)
                rows.append(_build_fs_item(normalized, file_path, relative_path, kind))
        rows.sort(key=lambda item: item.get('modified_at', 0), reverse=True)
        return rows

    videos = collect('videos', ('.mp4', '.mov', '.m4v'), 'video')
    photos = collect('photos', ('.jpg', '.jpeg', '.png', '.gif', '.webp'), 'photo')
    documents = collect('documents', ('.html', '.md'), 'document')
    for bucket in (videos, photos, documents):
        for item in bucket:
            item['task_id'] = task_id
    total_media_size = sum(item.get('size', 0) for item in videos + photos)
    if total_media_size < 1024:
        total_media_size_display = f'{total_media_size} B'
    elif total_media_size < 1024 * 1024:
        total_media_size_display = f'{total_media_size / 1024:.1f} KB'
    else:
        total_media_size_display = f'{total_media_size / 1024 / 1024:.1f} MB'

    return {
        'summary': {
            'videos': len(videos),
            'photos': len(photos),
            'documents': len(documents),
            'screenshots': 0,
            'total_media_size_display': total_media_size_display,
        },
        'videos': videos,
        'photos': photos,
        'documents': documents,
    }


def backfill_history_artifacts() -> Dict:
    history_records = load_history_records()
    if not history_records:
        return {'updated': 0, 'total': 0}

    updated = 0
    for item in history_records:
        if (item.get('artifacts') or {}).get('videos') or (item.get('results') or {}).get('artifacts'):
            continue

        inferred = infer_legacy_task_artifacts(
            item.get('task_id'),
            username=item.get('username'),
            history_records=history_records,
        )
        if inferred.get('videos') or inferred.get('photos') or inferred.get('documents'):
            item['artifacts'] = inferred
            updated += 1

    if updated:
        with open(config.HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_records, f, ensure_ascii=False, indent=2)

    return {
        'updated': updated,
        'total': len(history_records),
    }


def backfill_database_task_links() -> Dict:
    from services.media_store import media_store

    history_records = load_history_records()
    linked = 0

    usernames = sorted({_normalize_username(item.get('username')) for item in history_records if item.get('username')})
    for username in usernames:
        windows = _build_task_windows(username, history_records)
        if not windows:
            continue

        for db_path in media_store.get_candidate_db_paths(username):
            if not os.path.exists(db_path):
                continue
            with media_store._connect_by_path(db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT media_items.id, media_items.media_type, media_items.modified_at, media_items.task_id
                    FROM media_items
                    LEFT JOIN task_media_links
                        ON media_items.id = task_media_links.media_id
                        AND media_items.media_type = task_media_links.media_type
                        AND media_items.username = task_media_links.username
                    WHERE media_items.username = ?
                      AND task_media_links.task_id IS NULL
                    ORDER BY media_items.modified_at ASC
                    """,
                    (username,)
                ).fetchall()

                for row in rows:
                    matches = [
                        window for window in windows
                        if window['start_ts'] <= (row['modified_at'] or 0) <= window['end_ts']
                    ]
                    if len(matches) != 1:
                        continue

                    task_id = matches[0]['task_id']
                    media_store._link_media_to_task(conn, username, row['id'], row['media_type'], task_id)
                    conn.execute(
                        """
                        UPDATE media_items
                        SET task_id = COALESCE(task_id, ?), updated_at = ?
                        WHERE id = ? AND media_type = ? AND username = ?
                        """,
                        (
                            task_id,
                            datetime.now().isoformat(),
                            row['id'],
                            row['media_type'],
                            username,
                        )
                    )
                    linked += 1
                conn.commit()

    return {
        'linked': linked,
        'total_tasks': len(history_records),
    }
