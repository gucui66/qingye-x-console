"""Build the X-style user feed payload used by the admin UI."""
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List

import core.config as config

from .feed_overrides import feed_overrides
from .legacy_media import collect_legacy_media, normalize_username, resolve_output_username
from .media_store import media_store


_RAW_FEED_CACHE = {}
_LOCAL_MEDIA_CACHE = {}
_USER_FEED_PAYLOAD_CACHE = {}


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


def _resolve_publish_time(tweet_id, raw_value):
    parsed = _parse_datetime(raw_value)
    if parsed:
        return _datetime_to_iso(parsed)

    inferred = _infer_datetime_from_tweet_id(tweet_id)
    return _datetime_to_iso(inferred)


def find_latest_raw_feed_file(username: str):
    normalized = normalize_username(username)
    if not normalized:
        return None

    resolved_username = resolve_output_username(normalized) or normalized
    candidates = [
        os.path.join(config.OUTPUT_DIR, resolved_username, 'tweets_raw_selenium.json'),
        os.path.join(config.OUTPUT_DIR, resolved_username, 'tweets_raw.json'),
    ]
    existing = [path for path in candidates if os.path.exists(path)]
    if not existing:
        return None
    existing.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return existing[0]


def load_cached_raw_feed(raw_path: str) -> List[Dict]:
    if not raw_path or not os.path.exists(raw_path):
        return []

    try:
        stat = os.stat(raw_path)
    except OSError:
        return []

    cache_key = raw_path
    cache_stamp = (stat.st_mtime, stat.st_size)
    cached = _RAW_FEED_CACHE.get(cache_key)
    if cached and cached.get('stamp') == cache_stamp:
        return list(cached.get('tweets') or [])

    tweets = []
    try:
        with open(raw_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        if isinstance(payload, list):
            tweets = payload
        elif isinstance(payload, dict):
            tweets = payload.get('tweets') or payload.get('items') or []
            if not isinstance(tweets, list):
                tweets = []
    except Exception as e:
        print(f"读取原始推文失败 {raw_path}: {e}")
        tweets = []

    _RAW_FEED_CACHE[cache_key] = {
        'stamp': cache_stamp,
        'tweets': tweets,
        'loaded_at': time.time(),
    }
    return list(tweets)


def _path_stamp(path: str):
    normalized = os.path.realpath(path) if path else ''
    if not path or not os.path.exists(path):
        return (normalized, None, None)

    try:
        stat = os.stat(path)
    except OSError:
        return (normalized, None, None)
    return (normalized, stat.st_mtime, stat.st_size)


def _build_local_media_signature(username: str):
    normalized = normalize_username(username)
    if not normalized:
        return ()

    resolved_username = resolve_output_username(normalized) or normalized
    user_output_dir = os.path.join(config.OUTPUT_DIR, resolved_username)
    legacy_dirs = (
        os.path.join(user_output_dir, 'videos'),
        os.path.join(user_output_dir, 'photos'),
    )
    db_paths = tuple(_path_stamp(path) for path in media_store.get_candidate_db_paths(normalized))
    return (
        db_paths,
        tuple(_path_stamp(path) for path in legacy_dirs),
    )


def _clone_local_media_by_tweet(payload: Dict[str, Dict[str, List[Dict]]]) -> Dict[str, Dict[str, List[Dict]]]:
    return {
        str(tweet_id): {
            'videos': [dict(item) for item in (bucket.get('videos') or [])],
            'photos': [dict(item) for item in (bucket.get('photos') or [])],
        }
        for tweet_id, bucket in (payload or {}).items()
    }


def _local_media_sort_key(item):
    media_index = item.get('media_index')
    try:
        normalized_index = int(media_index)
    except (TypeError, ValueError):
        normalized_index = None

    if normalized_index is not None:
        return (0, normalized_index, str(item.get('path') or item.get('name') or ''))

    return (1, str(item.get('path') or item.get('name') or ''), -float(item.get('modified_at') or 0))


def load_cached_local_media_by_tweet(username: str):
    normalized = normalize_username(username)
    if not normalized:
        return (), {}

    signature = _build_local_media_signature(normalized)
    cached = _LOCAL_MEDIA_CACHE.get(normalized)
    if cached and cached.get('signature') == signature:
        return signature, _clone_local_media_by_tweet(cached.get('items') or {})

    local_media_by_tweet = {}

    def _append_local_media(item):
        tweet_id = item.get('tweet_id')
        if not tweet_id:
            return

        bucket = local_media_by_tweet.setdefault(str(tweet_id), {'videos': [], 'photos': []})
        target_key = 'videos' if item.get('media_type') == 'video' else 'photos'
        identity = item.get('path') or item.get('source_url') or item.get('tweet_url') or item.get('name')
        if identity and any(
            (existing.get('path') or existing.get('source_url') or existing.get('tweet_url') or existing.get('name')) == identity
            for existing in bucket[target_key]
        ):
            return

        bucket[target_key].append({
            **item,
            'url': f"/output/{item['path']}" if item.get('path') else item.get('url'),
        })

    for item in media_store.list_media(username=normalized):
        _append_local_media(item)

    for item in collect_legacy_media(username=normalized):
        _append_local_media(item)

    for bucket in local_media_by_tweet.values():
        bucket['videos'].sort(key=_local_media_sort_key)
        bucket['photos'].sort(key=_local_media_sort_key)

    _LOCAL_MEDIA_CACHE[normalized] = {
        'signature': signature,
        'items': local_media_by_tweet,
        'loaded_at': time.time(),
    }
    return signature, _clone_local_media_by_tweet(local_media_by_tweet)


def build_user_feed_payload(username: str, limit: int = 120):
    normalized = normalize_username(username)
    raw_path = find_latest_raw_feed_file(normalized)
    raw_stamp = _path_stamp(raw_path)
    overrides_stamp = _path_stamp(feed_overrides.path)
    local_media_signature, local_media_source = load_cached_local_media_by_tweet(normalized)
    payload_signature = (raw_stamp, local_media_signature, overrides_stamp)
    cache_key = (normalized, int(limit or 0))
    cached_payload = _USER_FEED_PAYLOAD_CACHE.get(cache_key)
    if cached_payload and cached_payload.get('signature') == payload_signature:
        return cached_payload.get('payload')

    tweets = load_cached_raw_feed(raw_path) if raw_path else []
    raw_collected_at = None
    if raw_path and os.path.exists(raw_path):
        raw_collected_at = _datetime_to_iso(datetime.fromtimestamp(os.path.getmtime(raw_path), tz=timezone.utc))
    overrides = feed_overrides.get_user_overrides(normalized)
    post_overrides = overrides.get('posts') or {}
    hidden_videos = overrides.get('hidden_videos') or {}
    profile_avatar_url = next(
        (
            str(tweet.get('author_avatar_url') or '').strip()
            for tweet in tweets
            if str(tweet.get('author_avatar_url') or '').strip()
        ),
        ''
    )

    local_media_by_tweet = {}

    def _hidden_video_entries(tweet_id):
        return list(hidden_videos.get(str(tweet_id), []) or [])

    def _is_hidden_video(item):
        if item.get('media_type') != 'video':
            return False
        return any(feed_overrides.video_matches(entry, item) for entry in _hidden_video_entries(item.get('tweet_id')))

    def _apply_post_override(tweet_id, content):
        override = post_overrides.get(str(tweet_id)) or {}
        if 'content' not in override:
            return (content or '').strip(), False, None
        return str(override.get('content') or '').strip(), True, override.get('content_updated_at')

    for tweet_id, bucket in local_media_source.items():
        filtered_videos = [
            item for item in (bucket.get('videos') or [])
            if not _is_hidden_video(item)
        ]
        filtered_photos = [dict(item) for item in (bucket.get('photos') or [])]
        local_media_by_tweet[str(tweet_id)] = {
            'videos': filtered_videos,
            'photos': filtered_photos,
        }

    rows = []
    seen_ids = set()
    for tweet in tweets:
        tweet_id = str(tweet.get('id') or '').strip()
        if not tweet_id or tweet_id in seen_ids:
            continue
        seen_ids.add(tweet_id)
        local_media = local_media_by_tweet.get(tweet_id, {'videos': [], 'photos': []})
        content, content_edited, content_updated_at = _apply_post_override(tweet_id, tweet.get('content') or '')
        publish_time = _resolve_publish_time(tweet_id, tweet.get('date'))
        rows.append({
            'id': tweet_id,
            'username': normalized,
            'author_username': tweet.get('author_username') or tweet.get('user') or normalized,
            'author_avatar_url': tweet.get('author_avatar_url') or profile_avatar_url,
            'content': content,
            'content_edited': content_edited,
            'content_updated_at': content_updated_at,
            'date': publish_time,
            'publish_time': publish_time,
            # raw 文件没有逐条采集时间，先明确标记为批次时间，前端会按这个口径展示。
            'crawled_at': raw_collected_at,
            'crawled_at_source': 'raw_file',
            'url': tweet.get('url'),
            'likes': tweet.get('likes', 0),
            'retweets': tweet.get('retweets', 0),
            'replies': tweet.get('replies', 0),
            'tab_source': tweet.get('tab_source'),
            'is_reply': bool(tweet.get('is_reply')),
            'reply_context': tweet.get('reply_context'),
            'local_videos': local_media.get('videos', []),
            'local_photos': local_media.get('photos', []),
            'remote_videos': tweet.get('videos', []) or [],
            'remote_photos': tweet.get('photos', []) or [],
            'hidden_videos_count': len(_hidden_video_entries(tweet_id)),
        })

    for tweet_id, local_media in local_media_by_tweet.items():
        if not tweet_id or tweet_id in seen_ids:
            continue

        timestamps = [item.get('modified_at', 0) for item in (local_media.get('videos', []) + local_media.get('photos', [])) if item.get('modified_at')]
        latest_ts = max(timestamps) if timestamps else 0
        latest_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc).isoformat() if latest_ts else None
        sample_item = (local_media.get('videos') or local_media.get('photos') or [None])[0]
        content, content_edited, content_updated_at = _apply_post_override(tweet_id, '')
        publish_time = _resolve_publish_time(tweet_id, None)

        rows.append({
            'id': str(tweet_id),
            'username': normalized,
            'author_username': normalized,
            'author_avatar_url': profile_avatar_url,
            'content': content,
            'content_edited': content_edited,
            'content_updated_at': content_updated_at,
            'date': publish_time or latest_dt,
            'publish_time': publish_time,
            'crawled_at': latest_dt,
            'crawled_at_source': 'media_file',
            'url': sample_item.get('tweet_url') if sample_item else None,
            'likes': 0,
            'retweets': 0,
            'replies': 0,
            'tab_source': '本地媒体',
            'is_reply': False,
            'reply_context': None,
            'local_videos': local_media.get('videos', []),
            'local_photos': local_media.get('photos', []),
            'remote_videos': [],
            'remote_photos': [],
            'hidden_videos_count': len(_hidden_video_entries(tweet_id)),
        })

    for tweet_id, entries in hidden_videos.items():
        if not tweet_id or tweet_id in seen_ids or tweet_id in local_media_by_tweet:
            continue

        content, content_edited, content_updated_at = _apply_post_override(tweet_id, '')
        publish_time = _resolve_publish_time(tweet_id, None)
        rows.append({
            'id': str(tweet_id),
            'username': normalized,
            'author_username': normalized,
            'author_avatar_url': profile_avatar_url,
            'content': content,
            'content_edited': content_edited,
            'content_updated_at': content_updated_at,
            'date': publish_time,
            'publish_time': publish_time,
            'crawled_at': raw_collected_at,
            'crawled_at_source': 'raw_file',
            'url': None,
            'likes': 0,
            'retweets': 0,
            'replies': 0,
            'tab_source': '已隐藏媒体',
            'is_reply': False,
            'reply_context': None,
            'local_videos': [],
            'local_photos': [],
            'remote_videos': [],
            'remote_photos': [],
            'hidden_videos_count': len(entries or []),
        })

    def _feed_sort_key(item):
        # 推文列表默认按 X 原始发布时间排序；发布时间缺失时才回退到采集/文件时间。
        published = _parse_datetime(item.get('publish_time') or item.get('date'))
        crawled = _parse_datetime(item.get('crawled_at'))
        if published:
            return (1, published.timestamp())
        if crawled:
            return (0, crawled.timestamp())
        return (0, float('-inf'))

    def _count_video_slots(item):
        return max(len(item.get('local_videos', [])), len(item.get('remote_videos', [])))

    def _count_photo_slots(item):
        return max(len(item.get('local_photos', [])), len(item.get('remote_photos', [])))

    rows.sort(key=_feed_sort_key, reverse=True)
    limited_rows = rows[:limit]
    payload = {
        'username': normalized,
        'source_file': os.path.basename(raw_path) if raw_path else None,
        'profile': {
            'username': normalized,
            'avatar_url': profile_avatar_url,
        },
        'items': limited_rows,
        'summary': {
            'tweets': len(rows),
            'returned_tweets': len(limited_rows),
            'limit': limit,
            'videos': sum(_count_video_slots(item) for item in rows),
            'photos': sum(_count_photo_slots(item) for item in rows),
            'edited_posts': sum(1 for item in rows if item.get('content_edited')),
            'hidden_videos': sum(len(entries or []) for entries in hidden_videos.values()),
        },
    }
    _USER_FEED_PAYLOAD_CACHE[cache_key] = {
        'signature': payload_signature,
        'payload': payload,
        'loaded_at': time.time(),
    }
    return payload
