"""Local, reversible overrides for the user feed view."""
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from typing import Dict, List

import core.config as config


class UserFeedOverrideStore:
    """Stores manual feed edits without mutating raw scrape data or media files."""

    def __init__(self, path: str = None):
        self.path = path or os.path.join(config.DATA_DIR, 'user_feed_overrides.json')
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_username(username: str) -> str:
        return (username or '').strip().lstrip('@')

    @staticmethod
    def _normalize_tweet_id(tweet_id) -> str:
        return str(tweet_id or '').strip()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _empty_payload(self) -> Dict:
        return {'version': 1, 'users': {}}

    def _load_unlocked(self) -> Dict:
        if not os.path.exists(self.path):
            return self._empty_payload()
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return self._empty_payload()
            payload.setdefault('version', 1)
            payload.setdefault('users', {})
            return payload
        except Exception as e:
            print(f"读取用户流覆盖数据失败: {e}")
            return self._empty_payload()

    def _save_unlocked(self, payload: Dict):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix='user_feed_overrides_', suffix='.json', dir=os.path.dirname(self.path))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _user_bucket(self, payload: Dict, username: str) -> Dict:
        users = payload.setdefault('users', {})
        bucket = users.setdefault(username, {})
        bucket.setdefault('posts', {})
        bucket.setdefault('hidden_videos', {})
        return bucket

    def get_user_overrides(self, username: str) -> Dict:
        normalized = self._normalize_username(username)
        if not normalized:
            return {'posts': {}, 'hidden_videos': {}}
        with self._lock:
            payload = self._load_unlocked()
            bucket = payload.get('users', {}).get(normalized, {})
            return {
                'posts': dict(bucket.get('posts') or {}),
                'hidden_videos': {
                    str(tweet_id): list(entries or [])
                    for tweet_id, entries in (bucket.get('hidden_videos') or {}).items()
                },
            }

    def update_post_content(self, username: str, tweet_id, content: str) -> Dict:
        normalized = self._normalize_username(username)
        normalized_tweet_id = self._normalize_tweet_id(tweet_id)
        if not normalized or not normalized_tweet_id:
            raise ValueError('缺少用户名或推文 ID')

        text = str(content or '')
        if len(text) > 10000:
            raise ValueError('正文太长，请控制在 10000 字以内')

        with self._lock:
            payload = self._load_unlocked()
            bucket = self._user_bucket(payload, normalized)
            posts = bucket.setdefault('posts', {})
            override = posts.setdefault(normalized_tweet_id, {})
            override.update({
                'content': text,
                'content_updated_at': self._now(),
            })
            self._save_unlocked(payload)
            return dict(override)

    def reset_post_content(self, username: str, tweet_id) -> Dict:
        normalized = self._normalize_username(username)
        normalized_tweet_id = self._normalize_tweet_id(tweet_id)
        if not normalized or not normalized_tweet_id:
            raise ValueError('缺少用户名或推文 ID')

        with self._lock:
            payload = self._load_unlocked()
            bucket = self._user_bucket(payload, normalized)
            posts = bucket.setdefault('posts', {})
            removed = posts.pop(normalized_tweet_id, None) or {}
            self._save_unlocked(payload)
            return removed

    def hide_video(self, username: str, tweet_id, video: Dict) -> Dict:
        normalized = self._normalize_username(username)
        normalized_tweet_id = self._normalize_tweet_id(tweet_id)
        if not normalized or not normalized_tweet_id:
            raise ValueError('缺少用户名或推文 ID')

        item = {
            'media_id': str(video.get('media_id') or video.get('id') or '').strip(),
            'media_index': video.get('media_index'),
            'path': str(video.get('path') or '').strip(),
            'name': str(video.get('name') or '').strip(),
            'hidden_at': self._now(),
        }
        if not item['media_id'] and item['media_index'] is None and not item['path']:
            raise ValueError('缺少可识别的视频信息')

        with self._lock:
            payload = self._load_unlocked()
            bucket = self._user_bucket(payload, normalized)
            hidden = bucket.setdefault('hidden_videos', {}).setdefault(normalized_tweet_id, [])
            if not any(self.video_matches(entry, item) for entry in hidden):
                hidden.append(item)
            self._save_unlocked(payload)
            return item

    def restore_videos(self, username: str, tweet_id) -> List[Dict]:
        normalized = self._normalize_username(username)
        normalized_tweet_id = self._normalize_tweet_id(tweet_id)
        if not normalized or not normalized_tweet_id:
            raise ValueError('缺少用户名或推文 ID')

        with self._lock:
            payload = self._load_unlocked()
            bucket = self._user_bucket(payload, normalized)
            restored = list(bucket.setdefault('hidden_videos', {}).pop(normalized_tweet_id, []) or [])
            self._save_unlocked(payload)
            return restored

    @staticmethod
    def video_matches(hidden: Dict, item: Dict) -> bool:
        hidden_media_id = str(hidden.get('media_id') or '').strip()
        item_media_id = str(item.get('media_id') or item.get('id') or '').strip()
        if hidden_media_id and item_media_id and hidden_media_id == item_media_id:
            return True

        hidden_path = str(hidden.get('path') or '').strip()
        item_path = str(item.get('path') or '').strip()
        if hidden_path and item_path and hidden_path == item_path:
            return True

        hidden_index = hidden.get('media_index')
        item_index = item.get('media_index')
        return hidden_index is not None and item_index is not None and str(hidden_index) == str(item_index)


feed_overrides = UserFeedOverrideStore()
