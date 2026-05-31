"""Lightweight username directory and per-user visibility/display preferences."""
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List

import core.config as config

from .legacy_media import list_output_usernames, normalize_username, resolve_output_username
from .media_store import media_store
from .user_feed import find_latest_raw_feed_file, load_cached_raw_feed


def _read_json_file(path: str, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return default


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _datetime_to_iso(value):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _to_timestamp(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.timestamp()
    return 0.0


def _infer_datetime_from_tweet_id(tweet_id):
    try:
        numeric_id = int(str(tweet_id or '').strip())
    except (TypeError, ValueError):
        return None
    if numeric_id <= 0:
        return None
    timestamp_ms = (numeric_id >> 22) + 1288834974657
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _resolve_publish_time(tweet):
    parsed = _parse_datetime((tweet or {}).get('date'))
    if parsed:
        return parsed
    return _infer_datetime_from_tweet_id((tweet or {}).get('id'))


def _build_preview_text(tweet):
    content = str((tweet or {}).get('content') or '').strip()
    if content:
        return content[:140]
    photos = len((tweet or {}).get('photos') or [])
    videos = len((tweet or {}).get('videos') or [])
    media_count = photos + videos
    if media_count:
        return f'最近采集到 {media_count} 个媒体资源'
    return '最近一次采集内容暂无正文'


class UserDirectory:
    CACHE_TTL_SECONDS = 15
    RAW_SUMMARY_CACHE_VERSION = 1

    def __init__(self):
        self.path = os.path.join(config.DATA_DIR, 'user_directory.json')
        self.raw_summary_cache_path = os.path.join(config.DATA_DIR, 'user_feed_summary_cache.json')
        self._cache = {
            'fingerprint': None,
            'items': [],
            'loaded_at': 0.0,
        }
        self._raw_summary_cache = None

    @staticmethod
    def _file_fingerprint(path: str):
        if not os.path.exists(path):
            return None
        try:
            stat = os.stat(path)
        except OSError:
            return None
        return (path, int(stat.st_mtime_ns), int(stat.st_size))

    def _output_fingerprint(self):
        if not os.path.exists(config.OUTPUT_DIR):
            return ()

        entries = []
        try:
            names = sorted(os.listdir(config.OUTPUT_DIR))
        except OSError:
            return ()

        for name in names:
            entry_path = os.path.join(config.OUTPUT_DIR, name)
            if not os.path.isdir(entry_path):
                continue
            try:
                stat = os.stat(entry_path)
            except OSError:
                continue
            entries.append((name, int(stat.st_mtime_ns)))
        return tuple(entries)

    def _cache_fingerprint(self):
        # 首页用户目录依赖多个来源；这里只做轻量指纹，避免命中缓存时还去扫媒体库。
        return (
            self._file_fingerprint(self.path),
            self._file_fingerprint(config.TASKS_FILE),
            self._file_fingerprint(config.HISTORY_FILE),
            self._output_fingerprint(),
            media_store.usernames_fingerprint(),
        )

    def _load_preferences(self) -> Dict:
        payload = _read_json_file(self.path, {})
        users = payload.get('users') if isinstance(payload, dict) else {}
        if not isinstance(users, dict):
            users = {}
        normalized_users = {}
        for username, prefs in users.items():
            normalized = normalize_username(username).lower()
            if not normalized or not isinstance(prefs, dict):
                continue
            # 偏好按小写账号存储，避免 MasterTopkr/mastertopkr 被当成两个人。
            normalized_users[normalized] = {
                **normalized_users.get(normalized, {}),
                **prefs,
            }
        return {'users': normalized_users}

    def _save_preferences(self, payload: Dict):
        with open(self.path, 'w', encoding='utf-8') as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)

    def _load_raw_summary_cache(self) -> Dict:
        if isinstance(self._raw_summary_cache, dict):
            return self._raw_summary_cache

        payload = _read_json_file(self.raw_summary_cache_path, {})
        if not isinstance(payload, dict) or payload.get('version') != self.RAW_SUMMARY_CACHE_VERSION:
            payload = {'version': self.RAW_SUMMARY_CACHE_VERSION, 'entries': {}}
        if not isinstance(payload.get('entries'), dict):
            payload['entries'] = {}
        self._raw_summary_cache = payload
        return self._raw_summary_cache

    def _save_raw_summary_cache(self):
        if not isinstance(self._raw_summary_cache, dict):
            return
        try:
            os.makedirs(os.path.dirname(self.raw_summary_cache_path), exist_ok=True)
            tmp_path = f'{self.raw_summary_cache_path}.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as file:
                json.dump(self._raw_summary_cache, file, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_path, self.raw_summary_cache_path)
        except Exception:
            # 摘要缓存只是加速用户时间流首页，写失败不影响真实数据读取。
            pass

    def _raw_summary_stamp(self, raw_path: str):
        try:
            stat = os.stat(raw_path)
        except OSError:
            return None
        return {
            'path': os.path.realpath(raw_path),
            'mtime_ns': int(stat.st_mtime_ns),
            'size': int(stat.st_size),
        }

    def _get_cached_raw_summary(self, raw_path: str):
        stamp = self._raw_summary_stamp(raw_path)
        if not stamp:
            return None

        cache = self._load_raw_summary_cache()
        entry = (cache.get('entries') or {}).get(stamp['path'])
        if not isinstance(entry, dict):
            return None
        if entry.get('mtime_ns') != stamp['mtime_ns'] or entry.get('size') != stamp['size']:
            return None
        summary = entry.get('summary')
        return dict(summary) if isinstance(summary, dict) else None

    def _remember_raw_summary(self, raw_path: str, summary: Dict):
        stamp = self._raw_summary_stamp(raw_path)
        if not stamp:
            return

        cache = self._load_raw_summary_cache()
        cache.setdefault('entries', {})[stamp['path']] = {
            'mtime_ns': stamp['mtime_ns'],
            'size': stamp['size'],
            'summary': dict(summary or {}),
            'cached_at': _datetime_to_iso(datetime.now(timezone.utc)),
        }
        self._save_raw_summary_cache()

    def _load_tasks_usernames(self) -> List[str]:
        payload = _read_json_file(config.TASKS_FILE, {})
        items = payload.values() if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        return [
            username for username in (
                normalize_username(item.get('username')) for item in items if isinstance(item, dict)
            )
            if username
        ]

    def _load_history_usernames(self) -> List[str]:
        payload = _read_json_file(config.HISTORY_FILE, [])
        items = payload if isinstance(payload, list) else []
        return [
            username for username in (
                normalize_username(item.get('username')) for item in items if isinstance(item, dict)
            )
            if username
        ]

    def _load_all_task_records(self) -> List[Dict]:
        task_payload = _read_json_file(config.TASKS_FILE, {})
        history_payload = _read_json_file(config.HISTORY_FILE, [])

        merged = {}
        task_items = task_payload.values() if isinstance(task_payload, dict) else task_payload if isinstance(task_payload, list) else []
        history_items = history_payload if isinstance(history_payload, list) else []

        for item in list(history_items) + list(task_items):
            if not isinstance(item, dict):
                continue
            task_id = str(item.get('task_id') or '').strip()
            if not task_id:
                continue
            existing = merged.get(task_id, {})
            merged[task_id] = {
                **existing,
                **item,
                'results': {
                    **(existing.get('results') or {}),
                    **(item.get('results') or {}),
                },
            }
        return list(merged.values())

    def _build_task_summary_by_username(self) -> Dict[str, Dict]:
        summary = {}
        for item in self._load_all_task_records():
            username = normalize_username(item.get('username'))
            if not username:
                continue
            key = username.lower()
            results = item.get('results') or {}
            total_tweets = int(
                item.get('total_tweets')
                or results.get('total_tweets')
                or item.get('scraped_count')
                or 0
            )
            completed_at = item.get('completed_at')
            created_at = item.get('created_at')
            status = str(item.get('status') or '').strip().lower()

            existing = summary.setdefault(key, {
                'latest_task_finished_at': None,
                'latest_task_finished_ts': 0.0,
                'latest_task_started_at': None,
                'latest_task_started_ts': 0.0,
                'latest_task_tweets': 0,
                'total_tweets_collected': 0,
                'task_count': 0,
            })

            created_ts = _to_timestamp(created_at)
            if created_ts >= existing['latest_task_started_ts']:
                existing['latest_task_started_ts'] = created_ts
                existing['latest_task_started_at'] = created_at

            if status == 'completed':
                finished_value = completed_at or created_at
                finished_ts = _to_timestamp(finished_value)
                if finished_ts >= existing['latest_task_finished_ts']:
                    existing['latest_task_finished_ts'] = finished_ts
                    existing['latest_task_finished_at'] = finished_value
                    existing['latest_task_tweets'] = total_tweets
                existing['total_tweets_collected'] += total_tweets
                existing['task_count'] += 1
        return summary

    def _build_raw_feed_summary(self, username: str) -> Dict:
        raw_path = find_latest_raw_feed_file(username)
        if not raw_path:
            return {}

        cached_summary = self._get_cached_raw_summary(raw_path)
        if cached_summary:
            return cached_summary

        tweets = load_cached_raw_feed(raw_path)
        # raw 文件本身就是本次采集结果，首页预览按文件顺序取第一条，避免和“发布时间排序”混用。
        latest_collected_tweet = next((tweet for tweet in tweets if isinstance(tweet, dict)), None)

        raw_collected_at = None
        try:
            raw_collected_at = _datetime_to_iso(datetime.fromtimestamp(os.path.getmtime(raw_path), tz=timezone.utc))
        except OSError:
            raw_collected_at = None

        summary = {
            'raw_path': raw_path,
            'raw_collected_at': raw_collected_at,
            'raw_collected_ts': _to_timestamp(raw_collected_at),
            'latest_preview': _build_preview_text(latest_collected_tweet or {}),
            'latest_publish_time': _datetime_to_iso(_resolve_publish_time(latest_collected_tweet or {})),
            'avatar_url': str((latest_collected_tweet or {}).get('author_avatar_url') or '').strip(),
            'author_name': str((latest_collected_tweet or {}).get('author_name') or (latest_collected_tweet or {}).get('user') or '').strip(),
            'latest_tweet_count': len(tweets),
        }
        self._remember_raw_summary(raw_path, summary)
        return summary

    def _pick_display_username(self, candidates: List[str], normalized: str) -> str:
        if not candidates:
            return normalized

        resolved = resolve_output_username(candidates[0])
        if resolved and resolved.lower() == normalized:
            return resolved

        decorated = sorted(
            set(candidates),
            key=lambda name: (
                0 if any(char.isupper() for char in name) else 1,
                0 if name and not name.islower() else 1,
                len(name),
                name.lower(),
                name,
            ),
        )
        return decorated[0]

    def list_items(self, include_hidden: bool = True) -> List[Dict]:
        fingerprint = self._cache_fingerprint()
        if (
            self._cache.get('items')
            and self._cache.get('fingerprint') == fingerprint
            and time.monotonic() - float(self._cache.get('loaded_at') or 0.0) < self.CACHE_TTL_SECONDS
        ):
            cached_items = list(self._cache.get('items') or [])
            if include_hidden:
                return cached_items
            return [item for item in cached_items if not item.get('hidden')]

        preferences = self._load_preferences().get('users', {})
        task_summary = self._build_task_summary_by_username()
        media_summary = {
            normalize_username(item.get('username')).lower(): item
            for item in media_store.summarize_by_username()
        }
        sources = {}

        def remember(raw_username: str, source: str):
            username = normalize_username(raw_username)
            if not username:
                return
            bucket = sources.setdefault(username.lower(), {'usernames': [], 'sources': set()})
            if username not in bucket['usernames']:
                bucket['usernames'].append(username)
            bucket['sources'].add(source)

        for username in media_store.list_usernames():
            remember(username, 'database')
        for username in list_output_usernames():
            remember(username, 'output')
        for username in self._load_tasks_usernames():
            remember(username, 'tasks')
        for username in self._load_history_usernames():
            remember(username, 'history')

        for normalized in preferences.keys():
            remember(normalized, 'preferences')

        items = []
        for normalized in sorted(sources.keys()):
            source_bucket = sources.get(normalized) or {}
            usernames = source_bucket.get('usernames') or [normalized]
            prefs = preferences.get(normalized) if isinstance(preferences.get(normalized), dict) else {}
            hidden = bool(prefs.get('hidden'))
            if hidden and not include_hidden:
                continue

            username = self._pick_display_username(usernames, normalized)
            alias = str(prefs.get('alias') or '').strip()
            display_name = alias or username
            raw_summary = self._build_raw_feed_summary(username)
            task_info = task_summary.get(normalized, {})
            media_info = media_summary.get(normalized, {})
            media_last_modified = media_info.get('last_modified') or 0
            media_last_modified_iso = _datetime_to_iso(datetime.fromtimestamp(media_last_modified, tz=timezone.utc)) if media_last_modified else None

            # 用户卡片排序看最近采集行为；推文详情页排序另按 publish_time，在 user_feed.py 里处理。
            last_crawled_candidates = [
                task_info.get('latest_task_finished_at'),
                raw_summary.get('raw_collected_at'),
                media_last_modified_iso,
                task_info.get('latest_task_started_at'),
            ]
            last_crawled_at = max(last_crawled_candidates, key=_to_timestamp, default=None)
            items.append({
                'username': username,
                'normalized_username': normalized,
                'display_name': display_name,
                'alias': alias,
                'hidden': hidden,
                'sources': sorted(source_bucket.get('sources') or []),
                'avatar_url': raw_summary.get('avatar_url') or '',
                'author_name': raw_summary.get('author_name') or display_name,
                'latest_preview': raw_summary.get('latest_preview') or '',
                'latest_publish_time': raw_summary.get('latest_publish_time'),
                'latest_tweet_count': raw_summary.get('latest_tweet_count') or 0,
                'total_tweets_collected': task_info.get('total_tweets_collected') or raw_summary.get('latest_tweet_count') or 0,
                'latest_task_tweets': task_info.get('latest_task_tweets') or raw_summary.get('latest_tweet_count') or 0,
                'latest_task_finished_at': task_info.get('latest_task_finished_at'),
                'latest_task_started_at': task_info.get('latest_task_started_at'),
                'last_crawled_at': last_crawled_at,
                'last_crawled_ts': _to_timestamp(last_crawled_at),
                'videos': media_info.get('videos') or 0,
                'photos': media_info.get('photos') or 0,
                'task_count': task_info.get('task_count') or media_info.get('task_count') or 0,
            })

        items.sort(
            key=lambda item: (
                1 if item.get('hidden') else 0,
                -float(item.get('last_crawled_ts') or 0),
                item.get('display_name', '').lower(),
                item.get('username', '').lower(),
            )
        )
        self._cache = {
            'fingerprint': fingerprint,
            'items': items,
            'loaded_at': time.monotonic(),
        }
        return items

    def get_visible_items(self) -> List[Dict]:
        return self.list_items(include_hidden=False)

    def update_item(self, username: str, alias=None, hidden=None, reset: bool = False) -> Dict:
        normalized = normalize_username(username).lower()
        if not normalized:
            raise ValueError('缺少用户名')

        payload = self._load_preferences()
        users = payload['users']
        current = users.get(normalized) if isinstance(users.get(normalized), dict) else {}

        if reset:
            users.pop(normalized, None)
        else:
            next_value = dict(current)
            if alias is not None:
                normalized_alias = str(alias or '').strip()
                if normalized_alias:
                    next_value['alias'] = normalized_alias
                else:
                    next_value.pop('alias', None)
            if hidden is not None:
                next_value['hidden'] = bool(hidden)

            if next_value:
                users[normalized] = next_value
            else:
                users.pop(normalized, None)

        self._save_preferences(payload)
        self._cache = {
            'fingerprint': None,
            'items': [],
            'loaded_at': 0.0,
        }
        return next(
            (item for item in self.list_items(include_hidden=True) if item['normalized_username'] == normalized),
            {
                'username': normalized,
                'normalized_username': normalized,
                'display_name': normalize_username(alias) if alias else normalized,
                'alias': str(alias or '').strip(),
                'hidden': bool(hidden),
                'sources': ['preferences'],
            },
        )

    def is_hidden(self, username: str) -> bool:
        normalized = normalize_username(username).lower()
        if not normalized:
            return False
        preferences = self._load_preferences().get('users', {})
        prefs = preferences.get(normalized) if isinstance(preferences.get(normalized), dict) else {}
        return bool(prefs.get('hidden'))


user_directory = UserDirectory()
