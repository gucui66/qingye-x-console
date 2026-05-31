"""
Operational helpers for MediaStore.

This mixin keeps lower-frequency admin operations out of the core storage
class without changing the public MediaStore API.
"""
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import core.config as config


class MediaStoreOperationsMixin:
    USERNAME_SUMMARY_CACHE_VERSION = 1

    def _username_summary_disk_cache_path(self) -> str:
        return os.path.join(config.DATA_DIR, 'media_username_summary_cache.json')

    def _load_username_summary_disk_cache(self, fingerprint):
        path = self._username_summary_disk_cache_path()
        if not os.path.exists(path):
            return None

        try:
            with open(path, 'r', encoding='utf-8') as file:
                payload = json.load(file)
        except Exception:
            return None

        cached_fingerprint = tuple(tuple(item) for item in payload.get('fingerprint') or [])
        cached_at = float(payload.get('cached_at') or 0)
        if payload.get('version') != self.USERNAME_SUMMARY_CACHE_VERSION:
            return None
        if cached_fingerprint != tuple(fingerprint):
            return None
        if time.time() - cached_at > self.USERNAME_SUMMARY_DISK_CACHE_TTL_SECONDS:
            return None

        items = payload.get('items')
        if not isinstance(items, list):
            return None
        return [dict(item) for item in items if isinstance(item, dict)]

    def _save_username_summary_disk_cache(self, fingerprint, items):
        try:
            os.makedirs(config.DATA_DIR, exist_ok=True)
            path = self._username_summary_disk_cache_path()
            tmp_path = f'{path}.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as file:
                json.dump({
                    'version': self.USERNAME_SUMMARY_CACHE_VERSION,
                    'fingerprint': list(fingerprint),
                    'items': [dict(item) for item in items],
                    'cached_at': time.time(),
                }, file, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_path, path)
        except Exception:
            # 磁盘缓存只用于降低用户时间流冷启动耗时，写失败不影响真实数据库读取。
            pass

    def _inspect_connection(self, conn, db_path: str) -> Dict:
        shard_meta = self._get_shard_meta(conn, db_path)
        counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total_items,
                SUM(CASE WHEN media_type = 'video' THEN 1 ELSE 0 END) AS videos,
                SUM(CASE WHEN media_type = 'photo' THEN 1 ELSE 0 END) AS photos,
                MAX(modified_at) AS latest_modified,
                COUNT(DISTINCT username) AS username_count
            FROM media_items
            """
        ).fetchone()
        usernames = [
            row['username']
            for row in conn.execute(
                """
                SELECT DISTINCT username
                FROM media_items
                WHERE username IS NOT NULL AND TRIM(username) != ''
                ORDER BY username
                LIMIT 24
                """
            ).fetchall()
        ]
        return {
            'shard_key': shard_meta['shard_key'],
            'shard_type': shard_meta['shard_type'],
            'bucket_id': shard_meta.get('bucket_id'),
            'display_name': shard_meta['label'],
            'db_name': os.path.basename(db_path),
            'db_path': db_path,
            'size_bytes': os.path.getsize(db_path),
            'modified_at': os.path.getmtime(db_path),
            'videos': counts['videos'] or 0,
            'photos': counts['photos'] or 0,
            'total_items': counts['total_items'] or 0,
            'latest_media_modified': counts['latest_modified'] or 0,
            'username_count': counts['username_count'] or 0,
            'usernames': usernames,
            'primary_username': usernames[0] if usernames else '',
            'username': usernames[0] if usernames else shard_meta['label'],
        }

    def inspect_shards(self) -> List[Dict]:
        shards = []
        for db_path in self._iter_db_paths():
            with self._connect_by_path(db_path) as conn:
                shards.append(self._inspect_connection(conn, db_path))
        shards.sort(key=lambda item: item.get('modified_at', 0), reverse=True)
        return shards

    def inspect_shard_detail(self, identifier: str) -> Optional[Dict]:
        resolved = self._resolve_shard_reference(identifier)
        if not resolved:
            return None

        db_path = resolved['db_path']
        with self._connect_by_path(db_path) as conn:
            shard_meta = self._get_shard_meta(conn, db_path)
            tables = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            ).fetchall()
            table_names = [row['name'] for row in tables]

            schema = {}
            for table_name in table_names:
                columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                schema[table_name] = [
                    {
                        'name': row['name'],
                        'type': row['type'],
                        'notnull': bool(row['notnull']),
                        'pk': bool(row['pk']),
                        'default': row['dflt_value'],
                    }
                    for row in columns
                ]

            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            usernames = [
                row['username']
                for row in conn.execute(
                    """
                    SELECT DISTINCT username
                    FROM media_items
                    WHERE username IS NOT NULL AND TRIM(username) != ''
                    ORDER BY username
                    """
                ).fetchall()
            ]
            recent_media = self._list_media_from_connection(conn, db_path=db_path)[:12]
            annotation_stats = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN favorite = 1 THEN 1 ELSE 0 END) AS favorites,
                    SUM(CASE WHEN watched = 1 THEN 1 ELSE 0 END) AS watched,
                    SUM(CASE WHEN watch_later = 1 THEN 1 ELSE 0 END) AS watch_later
                FROM media_annotations
                """
            ).fetchone()
            user_summary = conn.execute(
                """
                SELECT
                    media_items.username AS username,
                    COUNT(*) AS total_items,
                    SUM(CASE WHEN media_items.media_type = 'video' THEN 1 ELSE 0 END) AS videos,
                    SUM(CASE WHEN media_items.media_type = 'photo' THEN 1 ELSE 0 END) AS photos,
                    SUM(media_items.size_bytes) AS total_size,
                    MAX(media_items.modified_at) AS last_modified
                FROM media_items
                GROUP BY media_items.username
                ORDER BY last_modified DESC, username ASC
                """
            ).fetchall()
            task_summary = conn.execute(
                """
                SELECT
                    links.task_id AS task_id,
                    links.username AS username,
                    COUNT(*) AS total_items,
                    SUM(CASE WHEN media_items.media_type = 'video' THEN 1 ELSE 0 END) AS videos,
                    SUM(CASE WHEN media_items.media_type = 'photo' THEN 1 ELSE 0 END) AS photos,
                    SUM(media_items.size_bytes) AS total_size,
                    MAX(media_items.modified_at) AS last_modified
                FROM task_media_links AS links
                INNER JOIN media_items
                    ON media_items.id = links.media_id
                    AND media_items.media_type = links.media_type
                    AND media_items.username = links.username
                GROUP BY links.task_id, links.username
                ORDER BY last_modified DESC, links.task_id DESC
                """
            ).fetchall()

        return {
            'shard_key': shard_meta['shard_key'],
            'shard_type': shard_meta['shard_type'],
            'display_name': shard_meta['label'],
            'username': usernames[0] if usernames else '',
            'usernames': usernames,
            'username_count': len(usernames),
            'db_path': db_path,
            'db_name': os.path.basename(db_path),
            'size_bytes': os.path.getsize(db_path),
            'modified_at': os.path.getmtime(db_path),
            'integrity': integrity[0] if integrity else 'unknown',
            'tables': table_names,
            'schema': schema,
            'recent_media': recent_media,
            'annotation_stats': {
                'favorites': annotation_stats['favorites'] or 0,
                'watched': annotation_stats['watched'] or 0,
                'watch_later': annotation_stats['watch_later'] or 0,
            },
            'user_summary': [
                {
                    'username': row['username'],
                    'total_items': row['total_items'] or 0,
                    'videos': row['videos'] or 0,
                    'photos': row['photos'] or 0,
                    'total_size': row['total_size'] or 0,
                    'last_modified': row['last_modified'] or 0,
                }
                for row in user_summary
            ],
            'task_summary': [
                {
                    'task_id': row['task_id'],
                    'username': row['username'],
                    'total_items': row['total_items'] or 0,
                    'videos': row['videos'] or 0,
                    'photos': row['photos'] or 0,
                    'total_size': row['total_size'] or 0,
                    'last_modified': row['last_modified'] or 0,
                }
                for row in task_summary
            ],
        }

    def health_report(self) -> Dict:
        shards = []
        total_items = 0
        unhealthy = 0

        for shard in self.inspect_shards():
            detail = self.inspect_shard_detail(shard['shard_key'])
            integrity = detail['integrity'] if detail else 'missing'
            health_status = 'healthy' if integrity == 'ok' else 'warning'
            if health_status != 'healthy':
                unhealthy += 1
            total_items += shard.get('total_items', 0)
            shards.append({
                **shard,
                'health_status': health_status,
                'integrity': integrity,
            })

        return {
            'summary': {
                'total_shards': len(shards),
                'healthy_shards': len(shards) - unhealthy,
                'warning_shards': unhealthy,
                'total_items': total_items,
            },
            'shards': shards,
        }

    def search_media(
        self,
        query: str,
        username: str = None,
        media_type: str = None,
        task_id: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        keyword = (query or '').strip()
        if not keyword:
            return []

        task_join = ""
        linked_task_select = "media_items.task_id AS linked_task_id"
        if task_id:
            linked_task_select = "COALESCE(task_media_links.task_id, media_items.task_id) AS linked_task_id"
            task_join = """
            LEFT JOIN task_media_links
                ON media_items.id = task_media_links.media_id
                AND media_items.media_type = task_media_links.media_type
                AND media_items.username = task_media_links.username
            """

        query_sql = f"""
            SELECT
                media_items.id,
                media_items.username,
                {linked_task_select},
                media_items.task_id,
                media_items.media_type,
                media_items.filename,
                media_items.size_bytes,
                media_items.mime_type,
                media_items.modified_at,
                media_items.tweet_id,
                media_items.media_index,
                media_items.tweet_url,
                media_items.source_url,
                media_items.thumbnail_url,
                media_items.thumbnail_path,
                media_annotations.favorite,
                media_annotations.watched,
                media_annotations.watch_later,
                media_annotations.tags,
                media_annotations.note,
                media_annotations.last_position,
                media_annotations.play_count,
                media_annotations.last_played_at,
                media_annotations.updated_at AS annotation_updated_at
            FROM media_items
            {task_join}
            LEFT JOIN media_annotations
                ON media_items.id = media_annotations.media_id
            WHERE (
                media_items.filename LIKE ?
                OR COALESCE(media_items.tweet_id, '') LIKE ?
                OR COALESCE(media_items.tweet_url, '') LIKE ?
                OR COALESCE(media_items.source_url, '') LIKE ?
                OR COALESCE(media_annotations.note, '') LIKE ?
                OR COALESCE(media_annotations.tags, '') LIKE ?
            )
        """

        params = [f'%{keyword}%'] * 6
        normalized = self._normalize_username_key(username)
        if normalized:
            query_sql += " AND media_items.username = ?"
            params.append(normalized)
        if media_type:
            query_sql += " AND media_items.media_type = ?"
            params.append(media_type)
        if task_id:
            query_sql += " AND (task_media_links.task_id = ? OR media_items.task_id = ?)"
            params.extend([task_id, task_id])
        query_sql += " ORDER BY media_items.modified_at DESC, media_items.id DESC LIMIT ?"
        params.append(limit)

        results = []
        paths = self.get_candidate_db_paths(normalized) if normalized else self._iter_db_paths()
        for db_path in paths:
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                rows = conn.execute(query_sql, params).fetchall()
                shard_meta = self._get_shard_meta(conn, db_path)
                results.extend(self._serialize_row(normalized, row, shard_meta.get('shard_key')) for row in rows)

        results = self._dedupe_media_items(results)
        results.sort(key=lambda item: item.get('modified_at', 0), reverse=True)
        return results[:limit]

    def summarize_by_username(self) -> List[Dict]:
        fingerprint = self._usernames_cache_fingerprint()
        cached = getattr(self, '_username_summary_cache', None)
        if (
            isinstance(cached, dict)
            and cached.get('items')
            and cached.get('fingerprint') == fingerprint
            and time.monotonic() - float(cached.get('loaded_at') or 0.0) < self.USERNAMES_CACHE_TTL_SECONDS
        ):
            return [dict(item) for item in cached.get('items') or []]

        disk_cached_items = self._load_username_summary_disk_cache(fingerprint)
        if disk_cached_items is not None:
            self._username_summary_cache = {
                'fingerprint': fingerprint,
                'items': [dict(item) for item in disk_cached_items],
                'loaded_at': time.monotonic(),
            }
            return disk_cached_items

        summary = {}
        for db_path in self._iter_db_paths():
            with self._connect_by_path(db_path) as conn:
                media_rows = conn.execute(
                    """
                    SELECT
                        media_items.username AS username,
                        COUNT(*) AS total_items,
                        SUM(CASE WHEN media_items.media_type = 'video' THEN 1 ELSE 0 END) AS videos,
                        SUM(CASE WHEN media_items.media_type = 'photo' THEN 1 ELSE 0 END) AS photos,
                        SUM(media_items.size_bytes) AS total_size,
                        MAX(media_items.modified_at) AS last_modified
                    FROM media_items
                    GROUP BY media_items.username
                    """
                ).fetchall()
                task_rows = conn.execute(
                    """
                    SELECT username, COUNT(DISTINCT task_id) AS task_count
                    FROM task_media_links
                    GROUP BY username
                    """
                ).fetchall()
                task_count_map = {
                    self._normalize_username(row['username']): row['task_count'] or 0
                    for row in task_rows
                }

                for row in media_rows:
                    username = self._normalize_username(row['username'])
                    existing = summary.setdefault(username, {
                        'username': username,
                        'total_items': 0,
                        'videos': 0,
                        'photos': 0,
                        'total_size': 0,
                        'last_modified': 0,
                        'task_count': 0,
                    })
                    existing['total_items'] += row['total_items'] or 0
                    existing['videos'] += row['videos'] or 0
                    existing['photos'] += row['photos'] or 0
                    existing['total_size'] += row['total_size'] or 0
                    existing['last_modified'] = max(existing['last_modified'], row['last_modified'] or 0)
                    existing['task_count'] += task_count_map.get(username, 0)

        rows = list(summary.values())
        rows.sort(key=lambda item: item.get('last_modified', 0), reverse=True)
        # 用户目录和首页都会反复读取账号媒体统计；缓存按数据库文件指纹失效，避免重复扫 SQLite。
        self._username_summary_cache = {
            'fingerprint': fingerprint,
            'items': [dict(item) for item in rows],
            'loaded_at': time.monotonic(),
        }
        self._save_username_summary_disk_cache(fingerprint, rows)
        return rows

    def summarize_by_task(self) -> List[Dict]:
        summary = {}
        for db_path in self._iter_db_paths():
            with self._connect_by_path(db_path) as conn:
                shard_meta = self._get_shard_meta(conn, db_path)
                rows = conn.execute(
                    """
                    SELECT
                        links.task_id AS task_id,
                        links.username AS username,
                        COUNT(*) AS total_items,
                        SUM(CASE WHEN media_items.media_type = 'video' THEN 1 ELSE 0 END) AS videos,
                        SUM(CASE WHEN media_items.media_type = 'photo' THEN 1 ELSE 0 END) AS photos,
                        SUM(media_items.size_bytes) AS total_size,
                        MAX(media_items.modified_at) AS last_modified
                    FROM task_media_links AS links
                    INNER JOIN media_items
                        ON media_items.id = links.media_id
                        AND media_items.media_type = links.media_type
                        AND media_items.username = links.username
                    GROUP BY links.task_id, links.username
                    ORDER BY last_modified DESC
                    """
                ).fetchall()
                for row in rows:
                    task_id = row['task_id']
                    existing = summary.setdefault(task_id, {
                        'task_id': task_id,
                        'username': row['username'],
                        'total_items': 0,
                        'videos': 0,
                        'photos': 0,
                        'total_size': 0,
                        'last_modified': 0,
                        'shard_keys': set(),
                    })
                    existing['username'] = existing['username'] or row['username']
                    existing['total_items'] += row['total_items'] or 0
                    existing['videos'] += row['videos'] or 0
                    existing['photos'] += row['photos'] or 0
                    existing['total_size'] += row['total_size'] or 0
                    existing['last_modified'] = max(existing['last_modified'], row['last_modified'] or 0)
                    existing['shard_keys'].add(shard_meta['shard_key'])

        task_rows = []
        for row in summary.values():
            shard_keys = sorted(row.pop('shard_keys'))
            task_rows.append({
                **row,
                'shard_keys': shard_keys,
            })
        task_rows.sort(key=lambda item: item.get('last_modified', 0), reverse=True)
        return task_rows

    def delete_task_artifacts(self, task_id: str, username: str = None) -> Dict:
        normalized_task_id = (task_id or '').strip()
        normalized_username = self._normalize_username_key(username) if username else None
        deleted_items = 0
        unlinked_items = 0
        updated_items = 0

        if not normalized_task_id:
            return {
                'deleted_items': 0,
                'unlinked_items': 0,
                'updated_items': 0,
            }

        for db_path in self._iter_db_paths():
            with self._connect_by_path(db_path) as conn:
                params = [normalized_task_id]
                username_sql = ""
                if normalized_username:
                    username_sql = " AND username = ?"
                    params.append(normalized_username)

                linked_rows = conn.execute(
                    f"""
                    SELECT DISTINCT media_id, media_type, username
                    FROM task_media_links
                    WHERE task_id = ?{username_sql}
                    """,
                    params
                ).fetchall()

                for row in linked_rows:
                    media_id = row['media_id']
                    media_type = row['media_type']
                    media_username = self._normalize_username_key(row['username'])

                    conn.execute(
                        """
                        DELETE FROM task_media_links
                        WHERE task_id = ? AND media_id = ? AND media_type = ? AND username = ?
                        """,
                        (normalized_task_id, media_id, media_type, media_username)
                    )
                    unlinked_items += 1

                    replacement = conn.execute(
                        """
                        SELECT task_id
                        FROM task_media_links
                        WHERE media_id = ? AND media_type = ? AND username = ?
                        ORDER BY linked_at DESC
                        LIMIT 1
                        """,
                        (media_id, media_type, media_username)
                    ).fetchone()

                    if replacement:
                        conn.execute(
                            """
                            UPDATE media_items
                            SET task_id = ?, updated_at = ?
                            WHERE id = ? AND media_type = ? AND username = ?
                            """,
                            (
                                replacement['task_id'],
                                datetime.now().isoformat(),
                                media_id,
                                media_type,
                                media_username,
                            )
                        )
                        updated_items += 1
                        continue

                    current_row = conn.execute(
                        """
                        SELECT id
                        FROM media_items
                        WHERE id = ? AND media_type = ? AND username = ?
                          AND (task_id = ? OR task_id IS NULL OR TRIM(task_id) = '')
                        """,
                        (media_id, media_type, media_username, normalized_task_id)
                    ).fetchone()
                    if current_row:
                        conn.execute("DELETE FROM media_annotations WHERE media_id = ?", (media_id,))
                        conn.execute(
                            """
                            DELETE FROM media_items
                            WHERE id = ? AND media_type = ? AND username = ?
                            """,
                            (media_id, media_type, media_username)
                        )
                        deleted_items += 1

                legacy_only_rows = conn.execute(
                    f"""
                    SELECT id, media_type, username
                    FROM media_items
                    WHERE task_id = ?{username_sql}
                      AND NOT EXISTS (
                          SELECT 1
                          FROM task_media_links
                          WHERE task_media_links.media_id = media_items.id
                            AND task_media_links.media_type = media_items.media_type
                            AND task_media_links.username = media_items.username
                      )
                    """,
                    params
                ).fetchall()

                for row in legacy_only_rows:
                    conn.execute("DELETE FROM media_annotations WHERE media_id = ?", (row['id'],))
                    conn.execute(
                        """
                        DELETE FROM media_items
                        WHERE id = ? AND media_type = ? AND username = ?
                        """,
                        (row['id'], row['media_type'], row['username'])
                    )
                    deleted_items += 1

                conn.commit()

        return {
            'deleted_items': deleted_items,
            'unlinked_items': unlinked_items,
            'updated_items': updated_items,
        }

    def update_media_annotation(
        self,
        username: str,
        media_id: int,
        media_type: str,
        payload: Dict,
        shard_key: str = None,
    ) -> Optional[Dict]:
        normalized = self._normalize_username_key(username)
        now = datetime.now().isoformat()

        favorite = 1 if payload.get('favorite') else 0
        watched = 1 if payload.get('watched') else 0
        watch_later = 1 if payload.get('watch_later') else 0
        tags = payload.get('tags') or []
        if isinstance(tags, str):
            tags = [item.strip() for item in tags.split(',') if item.strip()]
        note = (payload.get('note') or '').strip()
        last_position = float(payload.get('last_position') or 0)
        play_count = int(payload.get('play_count') or 0)
        last_played_at = payload.get('last_played_at')

        for db_path in self._get_db_paths_for_lookup(normalized, shard_key):
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                existing = conn.execute(
                    """
                    SELECT id
                    FROM media_items
                    WHERE id = ? AND media_type = ? AND username = ?
                    """,
                    (media_id, media_type, normalized)
                ).fetchone()
                if not existing:
                    continue

                current = conn.execute(
                    """
                    SELECT favorite, watched, watch_later, tags, note, last_position, play_count, last_played_at
                    FROM media_annotations
                    WHERE media_id = ?
                    """,
                    (media_id,)
                ).fetchone()

                if current:
                    favorite = favorite if 'favorite' in payload else current['favorite']
                    watched = watched if 'watched' in payload else current['watched']
                    watch_later = watch_later if 'watch_later' in payload else current['watch_later']
                    tags = tags if 'tags' in payload else json.loads(current['tags'] or '[]')
                    note = note if 'note' in payload else (current['note'] or '')
                    last_position = last_position if 'last_position' in payload else float(current['last_position'] or 0)
                    play_count = play_count if 'play_count' in payload else int(current['play_count'] or 0)
                    last_played_at = last_played_at if 'last_played_at' in payload else current['last_played_at']

                conn.execute(
                    """
                    INSERT INTO media_annotations (
                        media_id, media_type, favorite, watched, watch_later,
                        tags, note, last_position, play_count, last_played_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(media_id) DO UPDATE SET
                        media_type = excluded.media_type,
                        favorite = excluded.favorite,
                        watched = excluded.watched,
                        watch_later = excluded.watch_later,
                        tags = excluded.tags,
                        note = excluded.note,
                        last_position = excluded.last_position,
                        play_count = excluded.play_count,
                        last_played_at = excluded.last_played_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        media_id,
                        media_type,
                        favorite,
                        watched,
                        watch_later,
                        json.dumps(tags, ensure_ascii=False),
                        note,
                        last_position,
                        play_count,
                        last_played_at,
                        now,
                    )
                )
                conn.commit()
                shard_meta = self._get_shard_meta(conn, db_path)
                return self.get_media(normalized, media_id, media_type, shard_key=shard_meta.get('shard_key'))

        return None

    def _archive_legacy_db(self, db_path: str) -> str:
        os.makedirs(config.MEDIA_SHARD_ARCHIVE_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = os.path.basename(db_path)
        archive_name = f'{base_name}.{timestamp}.archived'
        archive_path = os.path.join(config.MEDIA_SHARD_ARCHIVE_DIR, archive_name)
        shutil.move(db_path, archive_path)
        return archive_path

    def _upsert_media_into_bucket(self, conn, row, annotations: Dict) -> Tuple[int, str]:
        username = self._normalize_username(row['username'])
        now = datetime.now().isoformat()
        media_index = self._row_get(row, 'media_index')
        if media_index is None:
            media_index = self._infer_media_index(row['filename'])
        existing = conn.execute(
            """
            SELECT id
            FROM media_items
            WHERE username = ?
              AND media_type = ?
              AND (
                (tweet_id IS NOT NULL AND tweet_id != '' AND tweet_id = ? AND media_index = ?)
                OR sha256 = ?
              )
            ORDER BY
              CASE WHEN tweet_id = ? AND media_index = ? THEN 0 ELSE 1 END,
              id ASC
            LIMIT 1
            """,
            (
                username,
                row['media_type'],
                row['tweet_id'],
                media_index,
                row['sha256'],
                row['tweet_id'],
                media_index,
            )
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE media_items
                SET filename = ?,
                    size_bytes = ?,
                    mime_type = ?,
                    source_url = ?,
                    tweet_id = ?,
                    media_index = COALESCE(media_index, ?),
                    tweet_url = ?,
                    thumbnail_url = ?,
                    thumbnail_path = ?,
                    updated_at = ?,
                    modified_at = ?,
                    content = ?
                WHERE id = ? AND username = ? AND media_type = ?
                """,
                (
                    row['filename'],
                    row['size_bytes'],
                    row['mime_type'],
                    row['source_url'],
                    row['tweet_id'],
                    media_index,
                    row['tweet_url'],
                    self._row_get(row, 'thumbnail_url'),
                    self._row_get(row, 'thumbnail_path'),
                    now,
                    row['modified_at'],
                    sqlite3.Binary(row['content']),
                    existing['id'],
                    username,
                    row['media_type'],
                )
            )
            media_id = existing['id']
            action = 'updated'
        else:
            cursor = conn.execute(
                """
                INSERT INTO media_items (
                    username, media_type, filename, sha256, size_bytes, mime_type,
                    source_url, tweet_id, media_index, tweet_url, thumbnail_url, thumbnail_path, created_at, updated_at,
                    modified_at, content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    row['media_type'],
                    row['filename'],
                    row['sha256'],
                    row['size_bytes'],
                    row['mime_type'],
                    row['source_url'],
                    row['tweet_id'],
                    media_index,
                    row['tweet_url'],
                    self._row_get(row, 'thumbnail_url'),
                    self._row_get(row, 'thumbnail_path'),
                    row['created_at'] or now,
                    now,
                    row['modified_at'],
                    sqlite3.Binary(row['content']),
                )
            )
            media_id = cursor.lastrowid
            action = 'created'

        conn.execute(
            """
            INSERT INTO media_annotations (
                media_id, media_type, favorite, watched, watch_later,
                tags, note, last_position, play_count, last_played_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(media_id) DO UPDATE SET
                media_type = excluded.media_type,
                favorite = excluded.favorite,
                watched = excluded.watched,
                watch_later = excluded.watch_later,
                tags = excluded.tags,
                note = excluded.note,
                last_position = excluded.last_position,
                play_count = excluded.play_count,
                last_played_at = excluded.last_played_at,
                updated_at = excluded.updated_at
            """,
            (
                media_id,
                row['media_type'],
                annotations['favorite'],
                annotations['watched'],
                annotations['watch_later'],
                annotations['tags'],
                annotations['note'],
                annotations['last_position'],
                annotations['play_count'],
                annotations['last_played_at'],
                now,
            )
        )

        return media_id, action

    def migrate_legacy_shard(self, identifier: str) -> Dict:
        resolved = self._resolve_shard_reference(identifier)
        if not resolved:
            raise ValueError('找不到要迁移的旧版数据库')
        if resolved['shard_type'] != 'legacy':
            raise ValueError('只有旧版账号库才需要迁移')

        db_path = resolved['db_path']
        with self._connect_by_path(db_path) as legacy_conn:
            rows = legacy_conn.execute(
                """
                SELECT
                    media_items.id,
                    media_items.username,
                    media_items.media_type,
                    media_items.filename,
                    media_items.sha256,
                    media_items.size_bytes,
                    media_items.mime_type,
                    media_items.source_url,
                    media_items.tweet_id,
                    media_items.media_index,
                    media_items.thumbnail_url,
                    media_items.thumbnail_path,
                    media_items.tweet_url,
                    media_items.created_at,
                    media_items.updated_at,
                    media_items.modified_at,
                    media_items.content,
                    media_annotations.favorite,
                    media_annotations.watched,
                    media_annotations.watch_later,
                    media_annotations.tags,
                    media_annotations.note,
                    media_annotations.last_position,
                    media_annotations.play_count,
                    media_annotations.last_played_at
                FROM media_items
                LEFT JOIN media_annotations
                    ON media_items.id = media_annotations.media_id
                ORDER BY media_items.id ASC
                """
            ).fetchall()

        if not rows:
            archive_path = self._archive_legacy_db(db_path)
            return {
                'migrated': True,
                'source_shard_key': resolved['shard_key'],
                'source_db_path': db_path,
                'archived_to': archive_path,
                'total_items': 0,
                'created': 0,
                'updated': 0,
                'usernames': [],
            }

        bucket_connections = {}
        created = 0
        updated = 0
        usernames = set()

        try:
            for row in rows:
                username = self._normalize_username(row['username'])
                usernames.add(username)
                if username not in bucket_connections:
                    bucket_connections[username] = self._connect_bucket_for_username(username)

                annotations = {
                    'favorite': row['favorite'] or 0,
                    'watched': row['watched'] or 0,
                    'watch_later': row['watch_later'] or 0,
                    'tags': row['tags'] or '[]',
                    'note': row['note'] or '',
                    'last_position': row['last_position'] or 0,
                    'play_count': row['play_count'] or 0,
                    'last_played_at': row['last_played_at'],
                }

                _, action = self._upsert_media_into_bucket(bucket_connections[username], row, annotations)
                if action == 'created':
                    created += 1
                else:
                    updated += 1

            for conn in bucket_connections.values():
                conn.commit()
        finally:
            for conn in bucket_connections.values():
                conn.close()

        archive_path = self._archive_legacy_db(db_path)
        return {
            'migrated': True,
            'source_shard_key': resolved['shard_key'],
            'source_db_path': db_path,
            'archived_to': archive_path,
            'total_items': len(rows),
            'created': created,
            'updated': updated,
            'usernames': sorted(usernames),
        }

    def migrate_all_legacy_shards(self) -> Dict:
        legacy_shards = [item for item in self.inspect_shards() if item.get('shard_type') == 'legacy']
        results = []
        for shard in legacy_shards:
            results.append(self.migrate_legacy_shard(shard['shard_key']))

        return {
            'migrated_count': len(results),
            'results': results,
        }
