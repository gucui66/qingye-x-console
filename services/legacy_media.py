"""Helpers for reading legacy filesystem media outside the SQLite store."""
import os
from typing import Dict, List

import core.config as config

from .media_store import media_store


def extract_tweet_id_from_filename(filename: str):
    stem = os.path.basename(filename or '')
    parts = stem.split('tweet_', 1)
    if len(parts) != 2:
        return None
    suffix = parts[1].split('_', 1)[0].split('.', 1)[0]
    return suffix or None


def normalize_username(username: str) -> str:
    return (username or '').strip().lstrip('@')


def list_output_usernames() -> List[str]:
    if not os.path.exists(config.OUTPUT_DIR):
        return []

    return [
        name for name in os.listdir(config.OUTPUT_DIR)
        if os.path.isdir(os.path.join(config.OUTPUT_DIR, name))
    ]


def _pick_preferred_output_username(candidates: List[str], fallback: str = '') -> str:
    if not candidates:
        return fallback

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
    return decorated[0]


def resolve_output_username(username: str) -> str:
    normalized = normalize_username(username)
    if not normalized:
        return ''

    matches = [
        name for name in list_output_usernames()
        if name.lower() == normalized.lower()
    ]
    if not matches:
        return normalized

    return _pick_preferred_output_username(matches, fallback=normalized)


def peek_user_dirs(username: str) -> Dict[str, str]:
    resolved_username = resolve_output_username(username)
    user_output_dir = os.path.join(config.OUTPUT_DIR, resolved_username)
    return {
        'output': user_output_dir,
        'videos': os.path.join(user_output_dir, 'videos'),
        'photos': os.path.join(user_output_dir, 'photos'),
        'replies': os.path.join(user_output_dir, 'replies'),
        'documents': os.path.join(user_output_dir, 'documents'),
    }


def build_filesystem_media_item(username: str, media_type: str, file_path: str, filename: str):
    return {
        'id': None,
        'name': filename,
        'username': username,
        'path': os.path.join(username, f'{media_type}s', filename),
        'size': os.path.getsize(file_path),
        'modified_at': os.path.getmtime(file_path),
        'mime_type': 'video/mp4' if media_type == 'video' else 'image/jpeg',
        'storage_backend': 'filesystem',
        'media_type': media_type,
        'tweet_id': extract_tweet_id_from_filename(filename),
        'tweet_url': None,
        'source_url': None,
        'annotations': {
            'favorite': False,
            'watched': False,
            'watch_later': False,
            'tags': [],
            'note': '',
            'last_position': 0,
            'play_count': 0,
            'last_played_at': None,
            'annotation_updated_at': None,
        },
    }


def collect_legacy_media(username: str = None, media_type: str = None, task_id: str = None) -> List[Dict]:
    if task_id:
        return []
    normalized_username = normalize_username(username) if username else None
    users = []

    if normalized_username:
        users = [resolve_output_username(normalized_username)]
    else:
        deduped_users = {}
        for output_username in list_output_usernames():
            deduped_users.setdefault(output_username.lower(), []).append(output_username)
        users = [
            _pick_preferred_output_username(candidates, fallback=normalized_key)
            for normalized_key, candidates in sorted(deduped_users.items())
        ]

    items = []
    for each_username in users:
        user_dirs = peek_user_dirs(each_username)
        if media_type in (None, 'video') and os.path.exists(user_dirs['videos']):
            for filename in os.listdir(user_dirs['videos']):
                if filename.endswith('.mp4'):
                    items.append(
                        build_filesystem_media_item(
                            each_username,
                            'video',
                            os.path.join(user_dirs['videos'], filename),
                            filename,
                        )
                    )
        if media_type in (None, 'photo') and os.path.exists(user_dirs['photos']):
            for filename in os.listdir(user_dirs['photos']):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    items.append(
                        build_filesystem_media_item(
                            each_username,
                            'photo',
                            os.path.join(user_dirs['photos'], filename),
                            filename,
                        )
                    )
    items = media_store.dedupe_media_items(items)
    items.sort(key=lambda item: item.get('modified_at', 0), reverse=True)
    return items
