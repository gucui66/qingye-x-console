"""
固定桶分片的 SQLite 媒体存储，兼容旧版按账号单库结构
"""
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import core.config as config
from .media_store_operations import MediaStoreOperationsMixin


def _is_within_directory(base_dir: str, target_path: str) -> bool:
    try:
        return os.path.commonpath([
            os.path.realpath(base_dir),
            os.path.realpath(target_path),
        ]) == os.path.realpath(base_dir)
    except ValueError:
        return False


class MediaStore(MediaStoreOperationsMixin):
    """固定桶分片保存视频和图片的 SQLite 媒体库。"""

    VIRTUAL_PREFIX = '__db__'
    DB_SUFFIX = '.sqlite3'
    BUCKET_DB_PREFIX = 'media_bucket_'
    BUCKET_KEY_PREFIX = 'bucket:'
    LEGACY_KEY_PREFIX = 'legacy:'
    USERNAMES_CACHE_TTL_SECONDS = 15
    USERNAME_SUMMARY_DISK_CACHE_TTL_SECONDS = 300

    def __init__(self, shards_dir: str = None):
        self.shards_dir = shards_dir or config.MEDIA_SHARDS_DIR
        self.bucket_count = max(int(getattr(config, 'MEDIA_SHARD_BUCKETS', 8) or 8), 1)
        self._usernames_cache = {
            'fingerprint': None,
            'items': [],
            'loaded_at': 0.0,
        }
        self._username_summary_cache = {
            'fingerprint': None,
            'items': [],
            'loaded_at': 0.0,
        }
        os.makedirs(self.shards_dir, exist_ok=True)

    @staticmethod
    def _normalize_username(username: str) -> str:
        return (username or '').strip().lstrip('@')

    @classmethod
    def _normalize_username_key(cls, username: str) -> str:
        return cls._normalize_username(username).lower()

    def _bucket_id_for_username(self, username: str) -> int:
        normalized = self._normalize_username(username).lower()
        digest = hashlib.sha1(normalized.encode('utf-8')).hexdigest()
        return int(digest[:8], 16) % self.bucket_count

    def _bucket_key_from_id(self, bucket_id: int) -> str:
        return f'{self.BUCKET_KEY_PREFIX}{bucket_id:02d}'

    def _bucket_label_from_id(self, bucket_id: int) -> str:
        return f'固定桶 {bucket_id:02d}'

    def _bucket_db_filename(self, bucket_id: int) -> str:
        return f'{self.BUCKET_DB_PREFIX}{bucket_id:02d}{self.DB_SUFFIX}'

    def _bucket_db_path(self, bucket_id: int) -> str:
        return os.path.join(self.shards_dir, self._bucket_db_filename(bucket_id))

    def _bucket_db_path_for_username(self, username: str) -> str:
        return self._bucket_db_path(self._bucket_id_for_username(username))

    def _legacy_db_filename(self, username: str) -> str:
        normalized = self._normalize_username(username).lower()
        return f'{normalized}{self.DB_SUFFIX}'

    def _legacy_db_path(self, username: str) -> str:
        return os.path.join(self.shards_dir, self._legacy_db_filename(username))

    def _is_bucket_db_name(self, db_name: str) -> bool:
        return bool(re.fullmatch(rf'{self.BUCKET_DB_PREFIX}\d{{2}}{re.escape(self.DB_SUFFIX)}', db_name))

    def _parse_bucket_id_from_name(self, db_name: str) -> Optional[int]:
        match = re.fullmatch(rf'{self.BUCKET_DB_PREFIX}(\d{{2}}){re.escape(self.DB_SUFFIX)}', db_name)
        if not match:
            return None
        return int(match.group(1))

    def get_db_path(self, username: str) -> str:
        """返回当前账号对应的新分片库路径。"""
        normalized = self._normalize_username(username)
        if not normalized:
            raise ValueError('username is required')
        return self._bucket_db_path_for_username(normalized)

    def get_candidate_db_paths(self, username: str) -> List[str]:
        """返回某个账号可能存在媒体的数据库路径，新桶优先，旧库兜底。"""
        normalized = self._normalize_username(username)
        if not normalized:
            return []

        candidates = []
        bucket_path = self._bucket_db_path_for_username(normalized)
        if os.path.exists(bucket_path):
            candidates.append(bucket_path)

        legacy_path = self._legacy_db_path(normalized)
        if os.path.exists(legacy_path) and legacy_path not in candidates:
            candidates.append(legacy_path)

        if not candidates:
            candidates.append(bucket_path)

        return candidates

    def _iter_db_paths(self) -> List[str]:
        if not os.path.exists(self.shards_dir):
            return []

        bucket_paths = []
        legacy_paths = []
        for db_name in sorted(os.listdir(self.shards_dir)):
            if not db_name.endswith(self.DB_SUFFIX):
                continue
            db_path = os.path.join(self.shards_dir, db_name)
            if not os.path.isfile(db_path):
                continue
            if self._is_bucket_db_name(db_name):
                bucket_paths.append(db_path)
            else:
                legacy_paths.append(db_path)
        return bucket_paths + legacy_paths

    def _usernames_cache_fingerprint(self):
        if not os.path.exists(self.shards_dir):
            return ()

        fingerprint = []
        for db_name in sorted(os.listdir(self.shards_dir)):
            if not db_name.endswith(self.DB_SUFFIX):
                continue
            db_path = os.path.join(self.shards_dir, db_name)
            if not os.path.isfile(db_path):
                continue
            try:
                stat = os.stat(db_path)
            except OSError:
                continue
            # 读连接会执行轻量 schema 自检，部分 SQLite 文件的 mtime 会被触碰。
            # 账号汇总本身有 TTL 兜底，这里只用文件名和大小，避免“读取导致缓存永久失效”。
            fingerprint.append((db_name, int(stat.st_size)))
        return tuple(fingerprint)

    def usernames_fingerprint(self):
        """用户名目录只需要知道分片是否变化，避免为了判断缓存而扫完整 SQLite。"""
        return self._usernames_cache_fingerprint()

    def _connect_by_path(self, db_path: str):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        self._ensure_schema(conn, db_path=db_path)
        return conn

    def _connect_bucket_for_username(self, username: str):
        db_path = self._bucket_db_path_for_username(username)
        conn = self._connect_by_path(db_path)
        self._set_account_meta(conn, username)
        self._set_shard_meta(conn, db_path=db_path)
        conn.commit()
        return conn

    @staticmethod
    def _table_columns(conn, table_name: str) -> Dict[str, sqlite3.Row]:
        try:
            rows = conn.execute(f'PRAGMA table_info({table_name})').fetchall()
        except sqlite3.OperationalError:
            return {}
        return {row['name']: row for row in rows}

    def _ensure_schema(self, conn, db_path: str = None):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shard_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                shard_key TEXT NOT NULL,
                shard_type TEXT NOT NULL,
                bucket_id INTEGER,
                label TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                task_id TEXT,
                media_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                source_url TEXT,
                tweet_id TEXT,
                media_index INTEGER,
                tweet_url TEXT,
                thumbnail_url TEXT,
                thumbnail_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                modified_at REAL NOT NULL,
                content BLOB NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS duplicate_media_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                task_id TEXT,
                media_type TEXT NOT NULL,
                canonical_media_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                source_url TEXT,
                tweet_id TEXT,
                media_index INTEGER,
                tweet_url TEXT,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                deleted_at TEXT,
                FOREIGN KEY(canonical_media_id) REFERENCES media_items(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS media_annotations (
                media_id INTEGER PRIMARY KEY,
                media_type TEXT NOT NULL,
                favorite INTEGER NOT NULL DEFAULT 0,
                watched INTEGER NOT NULL DEFAULT 0,
                watch_later INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]',
                note TEXT NOT NULL DEFAULT '',
                last_position REAL NOT NULL DEFAULT 0,
                play_count INTEGER NOT NULL DEFAULT 0,
                last_played_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_media_links (
                task_id TEXT NOT NULL,
                username TEXT NOT NULL,
                media_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                linked_at TEXT NOT NULL,
                PRIMARY KEY (task_id, username, media_id, media_type),
                FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE
            )
            """
        )

        self._ensure_media_items_username_column(conn)
        self._ensure_task_media_links_username_column(conn)
        self._ensure_duplicate_media_files_username_column(conn)
        self._ensure_media_items_task_id_column(conn)
        self._ensure_media_items_dedupe_columns(conn)

        conn.execute(
            """
            DROP INDEX IF EXISTS idx_media_items_user_hash
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_media_items_user_hash_lookup
            ON media_items(username, media_type, sha256)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_media_items_canonical_key
            ON media_items(username, media_type, tweet_id, media_index)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_media_items_user_type_modified
            ON media_items(username, media_type, modified_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_media_items_type_modified
            ON media_items(media_type, modified_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_media_items_user_tweet
            ON media_items(username, tweet_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_media_items_task_modified
            ON media_items(task_id, modified_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_task_media_links_task
            ON task_media_links(task_id, linked_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_task_media_links_user
            ON task_media_links(username, task_id, media_type)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_duplicate_media_files_active
            ON duplicate_media_files(deleted_at, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_duplicate_media_files_task
            ON duplicate_media_files(task_id, username, media_type)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_media_annotations_flags
            ON media_annotations(favorite, watched, watch_later, updated_at DESC)
            """
        )

        self._set_shard_meta(conn, db_path=db_path)
        conn.commit()

    def _ensure_media_items_username_column(self, conn):
        columns = self._table_columns(conn, 'media_items')
        if not columns:
            return

        if 'username' not in columns:
            conn.execute("ALTER TABLE media_items ADD COLUMN username TEXT")

        account_username = self._account_username_from_connection(conn)
        if account_username:
            conn.execute(
                """
                UPDATE media_items
                SET username = ?
                WHERE username IS NULL OR TRIM(username) = ''
                """,
                (account_username,)
            )

        conn.execute(
            """
            UPDATE media_items
            SET username = LOWER(TRIM(username))
            WHERE username IS NOT NULL
            """
        )

    def _ensure_task_media_links_username_column(self, conn):
        columns = self._table_columns(conn, 'task_media_links')
        if not columns or 'username' not in columns:
            return

        conn.execute(
            """
            UPDATE task_media_links
            SET username = LOWER(TRIM(username))
            WHERE username IS NOT NULL
            """
        )

    def _ensure_duplicate_media_files_username_column(self, conn):
        columns = self._table_columns(conn, 'duplicate_media_files')
        if not columns or 'username' not in columns:
            return

        conn.execute(
            """
            UPDATE duplicate_media_files
            SET username = LOWER(TRIM(username))
            WHERE username IS NOT NULL
            """
        )

    def _ensure_media_items_task_id_column(self, conn):
        columns = self._table_columns(conn, 'media_items')
        if not columns:
            return

        if 'task_id' not in columns:
            conn.execute("ALTER TABLE media_items ADD COLUMN task_id TEXT")

    def _ensure_media_items_dedupe_columns(self, conn):
        columns = self._table_columns(conn, 'media_items')
        if not columns:
            return

        if 'media_index' not in columns:
            conn.execute("ALTER TABLE media_items ADD COLUMN media_index INTEGER")
        if 'thumbnail_url' not in columns:
            conn.execute("ALTER TABLE media_items ADD COLUMN thumbnail_url TEXT")
        if 'thumbnail_path' not in columns:
            conn.execute("ALTER TABLE media_items ADD COLUMN thumbnail_path TEXT")

    def _set_account_meta(self, conn, username: str):
        normalized = self._normalize_username(username)
        if not normalized:
            return
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO account_meta (id, username, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                updated_at = excluded.updated_at
            """,
            (normalized, now)
        )

    def _link_media_to_task(
        self,
        conn,
        username: str,
        media_id: int,
        media_type: str,
        task_id: str = None,
    ):
        normalized = self._normalize_username_key(username)
        normalized_task_id = (task_id or '').strip()
        if not normalized or not normalized_task_id or not media_id:
            return

        conn.execute(
            """
            INSERT INTO task_media_links (task_id, username, media_id, media_type, linked_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id, username, media_id, media_type) DO UPDATE SET
                linked_at = excluded.linked_at
            """,
            (
                normalized_task_id,
                normalized,
                media_id,
                media_type,
                datetime.now().isoformat(),
            )
        )

    @staticmethod
    def _infer_media_index(filename: str) -> Optional[int]:
        match = re.search(r'_tweet_[^_]+_(\d+)(?:\.[^.]+)?$', filename or '')
        if not match:
            return None
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = os.path.basename(filename or '').strip()
        cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', cleaned)
        return cleaned or f'media_{int(time.time())}'

    def _archive_duplicate_file(
        self,
        username: str,
        media_type: str,
        task_id: str,
        source_path: str,
        filename: str,
    ) -> Optional[str]:
        if not source_path or not os.path.exists(source_path):
            return None

        normalized = self._normalize_username(username) or 'unknown'
        folder_name = 'videos' if media_type == 'video' else 'photos'
        duplicate_dir = os.path.join(config.OUTPUT_DIR, normalized, 'duplicates', folder_name)
        os.makedirs(duplicate_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        task_prefix = self._safe_filename(task_id or 'manual')[:80]
        safe_name = self._safe_filename(filename or os.path.basename(source_path))
        target_name = f'{timestamp}_{task_prefix}_{safe_name}'
        target_path = os.path.join(duplicate_dir, target_name)
        shutil.copy2(source_path, target_path)
        return os.path.relpath(target_path, config.OUTPUT_DIR)

    def _archive_duplicate_content(
        self,
        username: str,
        media_type: str,
        task_id: str,
        content: bytes,
        filename: str,
    ) -> Optional[str]:
        if not content:
            return None

        normalized = self._normalize_username(username) or 'unknown'
        folder_name = 'videos' if media_type == 'video' else 'photos'
        duplicate_dir = os.path.join(config.OUTPUT_DIR, normalized, 'duplicates', folder_name)
        os.makedirs(duplicate_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        task_prefix = self._safe_filename(task_id or 'historical')[:80]
        safe_name = self._safe_filename(filename)
        target_path = os.path.join(duplicate_dir, f'{timestamp}_{task_prefix}_{safe_name}')
        with open(target_path, 'wb') as f:
            f.write(content)
        return os.path.relpath(target_path, config.OUTPUT_DIR)

    def _archive_thumbnail_file(
        self,
        username: str,
        media_type: str,
        source_path: str = None,
        filename: str = None,
    ) -> Optional[str]:
        if not source_path or not os.path.exists(source_path):
            return None

        normalized = self._normalize_username(username) or 'unknown'
        folder_name = 'videos' if media_type == 'video' else 'photos'
        thumbnail_dir = os.path.join(config.OUTPUT_DIR, normalized, 'thumbnails', folder_name)
        os.makedirs(thumbnail_dir, exist_ok=True)

        safe_name = self._safe_filename(filename or os.path.basename(source_path))
        target_path = os.path.join(thumbnail_dir, safe_name)
        if os.path.exists(target_path):
            stem, ext = os.path.splitext(safe_name)
            target_path = os.path.join(
                thumbnail_dir,
                f'{stem}_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}{ext or ".jpg"}',
            )
        shutil.copy2(source_path, target_path)
        return os.path.relpath(target_path, config.OUTPUT_DIR)

    def _find_canonical_media(
        self,
        conn,
        username: str,
        media_type: str,
        tweet_id: str = None,
        media_index: int = None,
        sha256: str = None,
    ):
        normalized = self._normalize_username_key(username)
        normalized_tweet_id = str(tweet_id or '').strip()

        if normalized and normalized_tweet_id and media_index is not None:
            row = conn.execute(
                """
                SELECT id, filename, sha256
                FROM media_items
                WHERE username = ?
                  AND media_type = ?
                  AND tweet_id = ?
                  AND media_index = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (normalized, media_type, normalized_tweet_id, int(media_index))
            ).fetchone()
            if row:
                return row, 'same_tweet_media_slot'

            like_pattern = f'%_tweet_{normalized_tweet_id}_{int(media_index)}.%'
            row = conn.execute(
                """
                SELECT id, filename, sha256
                FROM media_items
                WHERE username = ?
                  AND media_type = ?
                  AND tweet_id = ?
                  AND filename LIKE ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (normalized, media_type, normalized_tweet_id, like_pattern)
            ).fetchone()
            if row:
                return row, 'same_tweet_media_slot'

        if normalized and sha256:
            row = conn.execute(
                """
                SELECT id, filename, sha256
                FROM media_items
                WHERE username = ? AND media_type = ? AND sha256 = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (normalized, media_type, sha256)
            ).fetchone()
            if row:
                return row, 'same_file_hash'

        return None, None

    def _record_duplicate_file(
        self,
        conn,
        *,
        username: str,
        task_id: str = None,
        media_type: str,
        canonical_media_id: int,
        filename: str,
        path: str,
        sha256: str,
        size_bytes: int,
        mime_type: str,
        source_url: str = None,
        tweet_id: str = None,
        media_index: int = None,
        tweet_url: str = None,
        reason: str = 'duplicate',
    ) -> Optional[int]:
        if not path:
            return None

        cursor = conn.execute(
            """
            INSERT INTO duplicate_media_files (
                username, task_id, media_type, canonical_media_id, filename, path,
                sha256, size_bytes, mime_type, source_url, tweet_id, media_index,
                tweet_url, reason, created_at, deleted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                self._normalize_username_key(username),
                task_id,
                media_type,
                canonical_media_id,
                filename,
                path,
                sha256,
                size_bytes,
                mime_type,
                source_url,
                tweet_id,
                media_index,
                tweet_url,
                reason,
                datetime.now().isoformat(),
            )
        )
        return cursor.lastrowid

    def _set_shard_meta(self, conn, db_path: str = None):
        db_name = os.path.basename(db_path) if db_path else ''
        bucket_id = self._parse_bucket_id_from_name(db_name) if db_name else None
        now = datetime.now().isoformat()

        if bucket_id is not None:
            shard_key = self._bucket_key_from_id(bucket_id)
            shard_type = 'bucket'
            label = self._bucket_label_from_id(bucket_id)
        else:
            username = self._account_username_from_connection(conn) or os.path.splitext(db_name)[0]
            shard_key = f'{self.LEGACY_KEY_PREFIX}{username}'
            shard_type = 'legacy'
            label = f'旧版账号库 @{username}' if username else '旧版账号库'

        conn.execute(
            """
            INSERT INTO shard_meta (id, shard_key, shard_type, bucket_id, label, updated_at)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                shard_key = excluded.shard_key,
                shard_type = excluded.shard_type,
                bucket_id = excluded.bucket_id,
                label = excluded.label,
                updated_at = excluded.updated_at
            """,
            (shard_key, shard_type, bucket_id, label, now)
        )

    def _get_shard_meta(self, conn, db_path: str = None) -> Dict:
        row = conn.execute(
            """
            SELECT shard_key, shard_type, bucket_id, label, updated_at
            FROM shard_meta
            WHERE id = 1
            """
        ).fetchone()
        if row:
            return dict(row)

        db_name = os.path.basename(db_path) if db_path else ''
        bucket_id = self._parse_bucket_id_from_name(db_name) if db_name else None
        if bucket_id is not None:
            return {
                'shard_key': self._bucket_key_from_id(bucket_id),
                'shard_type': 'bucket',
                'bucket_id': bucket_id,
                'label': self._bucket_label_from_id(bucket_id),
                'updated_at': None,
            }

        username = self._account_username_from_connection(conn) or os.path.splitext(db_name)[0]
        return {
            'shard_key': f'{self.LEGACY_KEY_PREFIX}{username}',
            'shard_type': 'legacy',
            'bucket_id': None,
            'label': f'旧版账号库 @{username}' if username else '旧版账号库',
            'updated_at': None,
        }

    def _resolve_shard_reference(self, identifier: str) -> Optional[Dict]:
        raw = (identifier or '').strip().lstrip('@')
        if not raw:
            return None

        if raw.startswith(self.BUCKET_KEY_PREFIX):
            try:
                bucket_id = int(raw.split(':', 1)[1])
            except (TypeError, ValueError):
                return None
            db_path = self._bucket_db_path(bucket_id)
            if not os.path.exists(db_path):
                return None
            return {
                'db_path': db_path,
                'shard_key': self._bucket_key_from_id(bucket_id),
                'shard_type': 'bucket',
            }

        if raw.startswith(self.LEGACY_KEY_PREFIX):
            username = raw.split(':', 1)[1]
            db_path = self._legacy_db_path(username)
            if not os.path.exists(db_path):
                return None
            return {
                'db_path': db_path,
                'shard_key': f'{self.LEGACY_KEY_PREFIX}{username}',
                'shard_type': 'legacy',
            }

        bucket_path = self._bucket_db_path_for_username(raw)
        if os.path.exists(bucket_path):
            return {
                'db_path': bucket_path,
                'shard_key': self._bucket_key_from_id(self._bucket_id_for_username(raw)),
                'shard_type': 'bucket',
            }

        legacy_path = self._legacy_db_path(raw)
        if os.path.exists(legacy_path):
            return {
                'db_path': legacy_path,
                'shard_key': f'{self.LEGACY_KEY_PREFIX}{raw}',
                'shard_type': 'legacy',
            }

        return None

    def get_shard_backup_paths(self, identifier: str = None) -> List[str]:
        if not identifier:
            return self._iter_db_paths()
        resolved = self._resolve_shard_reference(identifier)
        if not resolved:
            return []
        return [resolved['db_path']]

    @staticmethod
    def _guess_mime_type(media_type: str, filename: str) -> str:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed
        return 'video/mp4' if media_type == 'video' else 'image/jpeg'

    @staticmethod
    def _read_file(source_path: str) -> Tuple[bytes, str, int]:
        with open(source_path, 'rb') as f:
            content = f.read()
        sha256 = hashlib.sha256(content).hexdigest()
        return content, sha256, len(content)

    def _account_username_from_connection(self, conn, fallback: str = '') -> str:
        row = conn.execute("SELECT username FROM account_meta WHERE id = 1").fetchone()
        if row and row['username']:
            return self._normalize_username(row['username'])
        return self._normalize_username(fallback)

    def _build_virtual_path(
        self,
        username: str,
        media_type: str,
        media_id: int,
        filename: str,
        shard_key: str = None,
    ) -> str:
        parts = [self.VIRTUAL_PREFIX]
        if shard_key:
            parts.append(shard_key)
        parts.extend([
            self._normalize_username(username),
            media_type,
            str(media_id),
            filename,
        ])
        return '/'.join(parts)

    @staticmethod
    def _row_get(row, key: str, default=None):
        if row is None:
            return default
        try:
            keys = row.keys()
        except AttributeError:
            return default
        return row[key] if key in keys else default

    def _serialize_annotations(self, row) -> Dict:
        raw_tags = self._row_get(row, 'tags', '[]') or '[]'
        try:
            tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
        except Exception:
            tags = []

        return {
            'favorite': bool(self._row_get(row, 'favorite', 0)),
            'watched': bool(self._row_get(row, 'watched', 0)),
            'watch_later': bool(self._row_get(row, 'watch_later', 0)),
            'tags': tags,
            'note': self._row_get(row, 'note', '') or '',
            'last_position': float(self._row_get(row, 'last_position', 0) or 0),
            'play_count': int(self._row_get(row, 'play_count', 0) or 0),
            'last_played_at': self._row_get(row, 'last_played_at'),
            'annotation_updated_at': self._row_get(row, 'annotation_updated_at'),
        }

    def _serialize_row(self, default_username: str, row, shard_key: str = None) -> Dict:
        username = self._normalize_username(self._row_get(row, 'username', default_username))
        return {
            'id': row['id'],
            'name': row['filename'],
            'username': username,
            'path': self._build_virtual_path(username, row['media_type'], row['id'], row['filename'], shard_key),
            'shard_key': shard_key,
            'size': row['size_bytes'],
            'modified_at': row['modified_at'],
            'mime_type': row['mime_type'],
            'storage_backend': 'sqlite',
            'media_type': row['media_type'],
            'task_id': self._row_get(row, 'linked_task_id', self._row_get(row, 'task_id')),
            'tweet_id': row['tweet_id'],
            'media_index': self._row_get(row, 'media_index'),
            'tweet_url': row['tweet_url'],
            'source_url': self._row_get(row, 'source_url'),
            'thumbnail_url': self._row_get(row, 'thumbnail_url'),
            'thumbnail_path': self._row_get(row, 'thumbnail_path'),
            'annotations': self._serialize_annotations(row),
        }

    @staticmethod
    def _dedupe_media_items(items: List[Dict]) -> List[Dict]:
        deduped = []
        seen = set()
        for item in sorted(items, key=lambda entry: entry.get('modified_at', 0), reverse=True):
            if item.get('tweet_id') and item.get('media_index') is not None:
                dedupe_key = (
                    item.get('username'),
                    item.get('media_type'),
                    str(item.get('tweet_id')),
                    item.get('media_index'),
                )
            else:
                dedupe_key = (
                    item.get('username'),
                    item.get('media_type'),
                    item.get('sha256') or item.get('name'),
                    item.get('size'),
                )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append(item)
        return deduped

    def dedupe_media_items(self, items: List[Dict]) -> List[Dict]:
        return self._dedupe_media_items(items)

    def store_file(
        self,
        username: str,
        media_type: str,
        source_path: str,
        filename: str,
        *,
        task_id: str = None,
        source_url: str = None,
        tweet_id: str = None,
        media_index: int = None,
        tweet_url: str = None,
        thumbnail_path: str = None,
        thumbnail_url: str = None,
        modified_at: float = None,
    ) -> Dict:
        normalized = self._normalize_username(username)
        username_key = self._normalize_username_key(username)
        content, sha256, size_bytes = self._read_file(source_path)
        mime_type = self._guess_mime_type(media_type, filename)
        now = datetime.now().isoformat()
        modified_ts = modified_at if modified_at is not None else time.time()
        if media_index is None:
            media_index = self._infer_media_index(filename)
        archived_thumbnail_path = self._archive_thumbnail_file(
            normalized,
            media_type,
            thumbnail_path,
            os.path.basename(thumbnail_path) if thumbnail_path else None,
        )

        with self._connect_bucket_for_username(normalized) as conn:
            row, duplicate_reason = self._find_canonical_media(
                conn,
                username_key,
                media_type,
                tweet_id=tweet_id,
                media_index=media_index,
                sha256=sha256 if not tweet_id else None,
            )

            duplicate_info = {}
            if row:
                media_id = row['id']
                self._link_media_to_task(conn, username_key, media_id, media_type, task_id)
                duplicate_path = self._archive_duplicate_file(
                    normalized,
                    media_type,
                    task_id,
                    source_path,
                    filename,
                )
                duplicate_id = self._record_duplicate_file(
                    conn,
                    username=normalized,
                    task_id=task_id,
                    media_type=media_type,
                    canonical_media_id=media_id,
                    filename=filename,
                    path=duplicate_path,
                    sha256=sha256,
                    size_bytes=size_bytes,
                    mime_type=mime_type,
                    source_url=source_url,
                    tweet_id=tweet_id,
                    media_index=media_index,
                    tweet_url=tweet_url,
                    reason=duplicate_reason or 'duplicate',
                )
                duplicate_info = {
                    'duplicate_saved': bool(duplicate_path),
                    'duplicate_id': duplicate_id,
                    'duplicate_path': duplicate_path,
                    'duplicate_of_id': media_id,
                    'duplicate_reason': duplicate_reason,
                }
                if archived_thumbnail_path:
                    conn.execute(
                        """
                        UPDATE media_items
                        SET thumbnail_path = COALESCE(NULLIF(thumbnail_path, ''), ?),
                            thumbnail_url = COALESCE(NULLIF(thumbnail_url, ''), ?),
                            updated_at = ?
                        WHERE id = ? AND username = ? AND media_type = ?
                        """,
                        (
                            archived_thumbnail_path,
                            thumbnail_url,
                            now,
                            media_id,
                            username_key,
                            media_type,
                        )
                    )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO media_items (
                        username, task_id, media_type, filename, sha256, size_bytes, mime_type,
                        source_url, tweet_id, media_index, tweet_url, thumbnail_url, thumbnail_path, created_at, updated_at,
                        modified_at, content
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        username_key,
                        task_id,
                        media_type,
                        filename,
                        sha256,
                        size_bytes,
                        mime_type,
                        source_url,
                        tweet_id,
                        media_index,
                        tweet_url,
                        thumbnail_url,
                        archived_thumbnail_path,
                        now,
                        now,
                        modified_ts,
                        sqlite3.Binary(content),
                    )
                )
                media_id = cursor.lastrowid
                self._link_media_to_task(conn, username_key, media_id, media_type, task_id)


            conn.commit()
            shard_meta = self._get_shard_meta(conn, self._bucket_db_path_for_username(normalized))
            stored = self.get_media(username_key, media_id, media_type, shard_key=shard_meta.get('shard_key'))
            if stored and duplicate_info:
                stored.update(duplicate_info)
            return stored

    def _fetch_media_from_connection(self, conn, username: str, media_id: int, media_type: str):
        return conn.execute(
            """
            SELECT
                media_items.id,
                media_items.username,
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
            LEFT JOIN media_annotations
                ON media_items.id = media_annotations.media_id
            WHERE media_items.id = ? AND media_items.media_type = ? AND media_items.username = ?
            """,
            (media_id, media_type, self._normalize_username_key(username))
        ).fetchone()

    def _get_db_paths_for_lookup(self, username: str, shard_key: str = None) -> List[str]:
        normalized = self._normalize_username(username)
        if shard_key:
            resolved = self._resolve_shard_reference(shard_key)
            return [resolved['db_path']] if resolved else []
        return self.get_candidate_db_paths(normalized)

    def get_media(self, username: str, media_id: int, media_type: str, shard_key: str = None) -> Optional[Dict]:
        normalized = self._normalize_username_key(username)
        for db_path in self._get_db_paths_for_lookup(normalized, shard_key):
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                row = self._fetch_media_from_connection(conn, normalized, media_id, media_type)
                if row:
                    shard_meta = self._get_shard_meta(conn, db_path)
                    return self._serialize_row(normalized, row, shard_meta.get('shard_key'))
        return None

    def _list_media_from_connection(self, conn, username: str = None, media_type: str = None, task_id: str = None, db_path: str = None) -> List[Dict]:
        params = []
        select_task_id = "media_items.task_id AS linked_task_id"
        task_join = ""
        if task_id:
            select_task_id = "COALESCE(task_media_links.task_id, media_items.task_id) AS linked_task_id"
            task_join = """
            LEFT JOIN task_media_links
                ON media_items.id = task_media_links.media_id
                AND media_items.media_type = task_media_links.media_type
                AND media_items.username = task_media_links.username
            """

        query = f"""
            SELECT
                media_items.id,
                media_items.username,
                {select_task_id},
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
        """
        conditions = []

        normalized = self._normalize_username_key(username)
        if normalized:
            conditions.append("media_items.username = ?")
            params.append(normalized)

        if media_type:
            conditions.append("media_items.media_type = ?")
            params.append(media_type)

        if task_id:
            conditions.append("(task_media_links.task_id = ? OR media_items.task_id = ?)")
            params.append(task_id)
            params.append(task_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY media_items.modified_at DESC, media_items.id DESC"
        rows = conn.execute(query, params).fetchall()
        shard_meta = self._get_shard_meta(conn, db_path)
        return [self._serialize_row(normalized, row, shard_meta.get('shard_key')) for row in rows]

    def list_media(self, username: str = None, media_type: str = None, task_id: str = None) -> List[Dict]:
        if username:
            items = []
            normalized = self._normalize_username(username)
            for db_path in self.get_candidate_db_paths(normalized):
                if not os.path.exists(db_path):
                    continue
                with self._connect_by_path(db_path) as conn:
                    items.extend(self._list_media_from_connection(conn, normalized, media_type, task_id, db_path))
            return self._dedupe_media_items(items)

        items = []
        for db_path in self._iter_db_paths():
            with self._connect_by_path(db_path) as conn:
                items.extend(self._list_media_from_connection(conn, None, media_type, task_id, db_path))

        items = self._dedupe_media_items(items)
        items.sort(key=lambda item: item.get('modified_at', 0), reverse=True)
        return items

    def _serialize_duplicate_row(self, row, shard_meta: Dict = None) -> Dict:
        path = row['path']
        file_path = os.path.join(config.OUTPUT_DIR, path)
        exists = os.path.exists(file_path)
        shard_meta = shard_meta or {}
        shard_key = shard_meta.get('shard_key')
        return {
            'key': f"{shard_key or 'unknown'}:{row['id']}",
            'id': row['id'],
            'username': self._normalize_username(row['username']),
            'task_id': row['task_id'],
            'media_type': row['media_type'],
            'canonical_media_id': row['canonical_media_id'],
            'filename': row['filename'],
            'name': row['filename'],
            'path': path,
            'url': f'/output/{path}',
            'sha256': row['sha256'],
            'size': row['size_bytes'],
            'size_bytes': row['size_bytes'],
            'mime_type': row['mime_type'],
            'source_url': row['source_url'],
            'tweet_id': row['tweet_id'],
            'media_index': row['media_index'],
            'tweet_url': row['tweet_url'],
            'reason': row['reason'],
            'created_at': row['created_at'],
            'deleted_at': row['deleted_at'],
            'exists': exists,
            'shard_key': shard_key,
        }

    def list_duplicate_files(
        self,
        username: str = None,
        task_id: str = None,
        media_type: str = None,
        include_deleted: bool = False,
        limit: int = 200,
    ) -> Dict:
        normalized = self._normalize_username_key(username) if username else None
        paths = self.get_candidate_db_paths(normalized) if normalized else self._iter_db_paths()
        items = []

        for db_path in paths:
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                query = """
                    SELECT *
                    FROM duplicate_media_files
                """
                conditions = []
                params = []
                if not include_deleted:
                    conditions.append("deleted_at IS NULL")
                if normalized:
                    conditions.append("username = ?")
                    params.append(normalized)
                if task_id:
                    conditions.append("task_id = ?")
                    params.append(task_id)
                if media_type:
                    conditions.append("media_type = ?")
                    params.append(media_type)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                query += " ORDER BY created_at DESC, id DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(query, params).fetchall()
                shard_meta = self._get_shard_meta(conn, db_path)
                items.extend(self._serialize_duplicate_row(row, shard_meta) for row in rows)

        items.sort(key=lambda item: item.get('created_at') or '', reverse=True)
        limited = items[:limit]
        return {
            'items': limited,
            'summary': {
                'total': len(limited),
                'videos': sum(1 for item in limited if item.get('media_type') == 'video'),
                'photos': sum(1 for item in limited if item.get('media_type') == 'photo'),
                'total_size': sum(item.get('size') or 0 for item in limited),
            },
        }

    def delete_duplicate_file(self, duplicate_id: int, shard_key: str = None) -> Optional[Dict]:
        target_id = int(duplicate_id or 0)
        if target_id <= 0:
            return None

        db_paths = []
        if shard_key:
            resolved = self._resolve_shard_reference(shard_key)
            if resolved:
                db_paths.append(resolved['db_path'])
        else:
            db_paths = self._iter_db_paths()

        for db_path in db_paths:
            with self._connect_by_path(db_path) as conn:
                row = conn.execute(
                    """
                    SELECT *
                    FROM duplicate_media_files
                    WHERE id = ?
                    """,
                    (target_id,)
                ).fetchone()
                if not row:
                    continue

                item = self._serialize_duplicate_row(row, self._get_shard_meta(conn, db_path))
                if not row['deleted_at']:
                    file_path = os.path.realpath(os.path.join(config.OUTPUT_DIR, row['path']))
                    output_dir = os.path.realpath(config.OUTPUT_DIR)
                    removed_file = False
                    if _is_within_directory(output_dir, file_path) and os.path.exists(file_path):
                        os.remove(file_path)
                        removed_file = True
                    conn.execute(
                        """
                        UPDATE duplicate_media_files
                        SET deleted_at = ?
                        WHERE id = ?
                        """,
                        (datetime.now().isoformat(), target_id)
                    )
                    conn.commit()
                    item['deleted_at'] = datetime.now().isoformat()
                    item['exists'] = False
                    item['removed_file'] = removed_file
                return item

        return None

    def backfill_video_thumbnails(self, username: str = None, limit: int = 80) -> Dict:
        normalized = self._normalize_username_key(username) if username else None
        paths = self.get_candidate_db_paths(normalized) if normalized else self._iter_db_paths()
        scanned = 0
        generated = 0
        skipped = 0
        failed = 0
        errors = []

        for db_path in paths:
            if scanned >= limit:
                break
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                conditions = ["media_type = 'video'", "(thumbnail_path IS NULL OR TRIM(thumbnail_path) = '')"]
                params = []
                if normalized:
                    conditions.append("username = ?")
                    params.append(normalized)
                query = f"""
                    SELECT id, username, media_type, filename, mime_type, content
                    FROM media_items
                    WHERE {' AND '.join(conditions)}
                    ORDER BY modified_at DESC, id DESC
                    LIMIT ?
                """
                params.append(max(0, limit - scanned))
                rows = conn.execute(query, params).fetchall()

                for row in rows:
                    scanned += 1
                    with tempfile.TemporaryDirectory(prefix='thumb_backfill_') as tmp_dir:
                        video_path = os.path.join(tmp_dir, row['filename'] or f"video_{row['id']}.mp4")
                        stem = os.path.splitext(os.path.basename(row['filename'] or f"video_{row['id']}"))[0]
                        thumb_path = os.path.join(tmp_dir, f'{stem}_thumb.jpg')
                        try:
                            with open(video_path, 'wb') as f:
                                f.write(row['content'])
                            result = subprocess.run(
                                [
                                    'ffmpeg',
                                    '-y',
                                    '-ss',
                                    '00:00:01',
                                    '-i',
                                    video_path,
                                    '-frames:v',
                                    '1',
                                    '-q:v',
                                    '3',
                                    thumb_path,
                                ],
                                capture_output=True,
                                text=True,
                                timeout=30,
                            )
                            if result.returncode != 0 or not os.path.exists(thumb_path):
                                failed += 1
                                if len(errors) < 8:
                                    errors.append({
                                        'id': row['id'],
                                        'name': row['filename'],
                                        'error': (result.stderr or result.stdout or 'ffmpeg failed')[-300:],
                                    })
                                continue

                            archived = self._archive_thumbnail_file(
                                row['username'],
                                'video',
                                thumb_path,
                                os.path.basename(thumb_path),
                            )
                            if not archived:
                                skipped += 1
                                continue
                            conn.execute(
                                """
                                UPDATE media_items
                                SET thumbnail_path = ?, updated_at = ?
                                WHERE id = ? AND username = ? AND media_type = 'video'
                                """,
                                (archived, datetime.now().isoformat(), row['id'], row['username'])
                            )
                            generated += 1
                        except Exception as e:
                            failed += 1
                            if len(errors) < 8:
                                errors.append({'id': row['id'], 'name': row['filename'], 'error': str(e)})
                conn.commit()

        return {
            'scanned': scanned,
            'generated': generated,
            'skipped': skipped,
            'failed': failed,
            'errors': errors,
        }

    def scan_historical_duplicates(self, username: str = None, limit: int = 200) -> Dict:
        normalized = self._normalize_username_key(username) if username else None
        paths = self.get_candidate_db_paths(normalized) if normalized else self._iter_db_paths()
        groups_found = 0
        exported = 0
        skipped = 0

        for db_path in paths:
            if exported >= limit:
                break
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                params = []
                username_sql = ''
                if normalized:
                    username_sql = 'WHERE username = ?'
                    params.append(normalized)

                rows = conn.execute(
                    f"""
                    SELECT id, username, task_id, media_type, filename, sha256, size_bytes,
                           mime_type, source_url, tweet_id, media_index, tweet_url, content
                    FROM media_items
                    {username_sql}
                    ORDER BY modified_at DESC, id DESC
                    """,
                    params
                ).fetchall()

                groups = {}
                for row in rows:
                    if row['tweet_id'] and row['media_index'] is not None:
                        key = (row['username'], row['media_type'], row['tweet_id'], row['media_index'])
                    else:
                        key = (row['username'], row['media_type'], row['sha256'])
                    groups.setdefault(key, []).append(row)

                for group_rows in groups.values():
                    if exported >= limit:
                        break
                    if len(group_rows) <= 1:
                        continue
                    groups_found += 1
                    canonical = sorted(group_rows, key=lambda row: row['id'])[0]
                    for row in sorted(group_rows, key=lambda item: item['id'])[1:]:
                        if exported >= limit:
                            break
                        exists = conn.execute(
                            """
                            SELECT id
                            FROM duplicate_media_files
                            WHERE canonical_media_id = ?
                              AND sha256 = ?
                              AND filename = ?
                              AND deleted_at IS NULL
                            LIMIT 1
                            """,
                            (canonical['id'], row['sha256'], row['filename'])
                        ).fetchone()
                        if exists:
                            skipped += 1
                            continue
                        duplicate_path = self._archive_duplicate_content(
                            row['username'],
                            row['media_type'],
                            row['task_id'],
                            row['content'],
                            row['filename'],
                        )
                        if not duplicate_path:
                            skipped += 1
                            continue
                        self._record_duplicate_file(
                            conn,
                            username=row['username'],
                            task_id=row['task_id'],
                            media_type=row['media_type'],
                            canonical_media_id=canonical['id'],
                            filename=row['filename'],
                            path=duplicate_path,
                            sha256=row['sha256'],
                            size_bytes=row['size_bytes'],
                            mime_type=row['mime_type'],
                            source_url=row['source_url'],
                            tweet_id=row['tweet_id'],
                            media_index=row['media_index'],
                            tweet_url=row['tweet_url'],
                            reason='historical_duplicate',
                        )
                        exported += 1
                conn.commit()

        return {
            'groups_found': groups_found,
            'exported': exported,
            'skipped': skipped,
        }

    def build_maintenance_report(self) -> Dict:
        total_videos = 0
        videos_missing_thumbnails = 0
        duplicate_rows = 0
        total_duplicates_size = 0

        for db_path in self._iter_db_paths():
            with self._connect_by_path(db_path) as conn:
                video_row = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN thumbnail_path IS NULL OR TRIM(thumbnail_path) = '' THEN 1 ELSE 0 END) AS missing
                    FROM media_items
                    WHERE media_type = 'video'
                    """
                ).fetchone()
                total_videos += video_row['total'] or 0
                videos_missing_thumbnails += video_row['missing'] or 0

                duplicate_row = conn.execute(
                    """
                    SELECT COUNT(*) AS total, SUM(size_bytes) AS total_size
                    FROM duplicate_media_files
                    WHERE deleted_at IS NULL
                    """
                ).fetchone()
                duplicate_rows += duplicate_row['total'] or 0
                total_duplicates_size += duplicate_row['total_size'] or 0

        return {
            'videos': {
                'total': total_videos,
                'missing_thumbnails': videos_missing_thumbnails,
                'thumbnail_coverage': round(
                    ((total_videos - videos_missing_thumbnails) / total_videos) * 100,
                    1,
                ) if total_videos else 100,
            },
            'duplicates': {
                'active': duplicate_rows,
                'total_size': total_duplicates_size,
            },
        }

    def list_usernames(self) -> List[str]:
        fingerprint = self._usernames_cache_fingerprint()
        if (
            self._usernames_cache.get('items')
            and self._usernames_cache.get('fingerprint') == fingerprint
            and time.monotonic() - float(self._usernames_cache.get('loaded_at') or 0.0) < self.USERNAMES_CACHE_TTL_SECONDS
        ):
            return list(self._usernames_cache.get('items') or [])

        summary_rows = self.summarize_by_username()
        summary_usernames = sorted({
            self._normalize_username(row.get('username'))
            for row in summary_rows
            if row.get('username')
        })
        if summary_usernames:
            self._usernames_cache = {
                'fingerprint': fingerprint,
                'items': summary_usernames,
                'loaded_at': time.monotonic(),
            }
            return summary_usernames

        usernames = set()
        for db_path in self._iter_db_paths():
            with self._connect_by_path(db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT DISTINCT username
                    FROM media_items
                    WHERE username IS NOT NULL AND TRIM(username) != ''
                    ORDER BY username
                    """
                ).fetchall()
                if rows:
                    usernames.update(self._normalize_username(row['username']) for row in rows if row['username'])
                    continue
                fallback = self._account_username_from_connection(conn)
                if fallback:
                    usernames.add(fallback)
        items = sorted(usernames)
        self._usernames_cache = {
            'fingerprint': fingerprint,
            'items': items,
            'loaded_at': time.monotonic(),
        }
        return items

    def parse_virtual_path(self, virtual_path: str) -> Optional[Dict]:
        normalized = (virtual_path or '').strip().lstrip('/')
        parts = normalized.split('/')
        if len(parts) < 5 or parts[0] != self.VIRTUAL_PREFIX:
            return None

        shard_key = None
        if len(parts) >= 6 and (
            parts[1].startswith(self.BUCKET_KEY_PREFIX)
            or parts[1].startswith(self.LEGACY_KEY_PREFIX)
        ):
            _, shard_key, username, media_type, media_id, *filename_parts = parts
        else:
            _, username, media_type, media_id, *filename_parts = parts
        if media_type not in {'video', 'photo'}:
            return None
        try:
            media_id = int(media_id)
        except (TypeError, ValueError):
            return None

        return {
            'shard_key': shard_key,
            'username': username,
            'media_type': media_type,
            'media_id': media_id,
            'filename': '/'.join(filename_parts) or f'{media_type}_{media_id}',
        }

    def get_media_metadata_from_virtual_path(self, virtual_path: str) -> Optional[Dict]:
        resolved = self.resolve_virtual_media(virtual_path)
        return resolved['metadata'] if resolved else None

    def resolve_virtual_media(self, virtual_path: str) -> Optional[Dict]:
        parsed = self.parse_virtual_path(virtual_path)
        if not parsed:
            return None

        db_paths = self._get_db_paths_for_lookup(parsed['username'], parsed.get('shard_key'))
        exact_filename = parsed.get('filename')
        fallback_match = None

        for db_path in db_paths:
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                row = self._fetch_media_from_connection(
                    conn,
                    parsed['username'],
                    parsed['media_id'],
                    parsed['media_type']
                )
                if not row:
                    continue
                shard_meta = self._get_shard_meta(conn, db_path)
                item = self._serialize_row(parsed['username'], row, shard_meta.get('shard_key'))
                if exact_filename and row['filename'] == exact_filename:
                    resolved_parsed = {
                        **parsed,
                        'shard_key': shard_meta.get('shard_key'),
                    }
                    return {
                        'parsed': resolved_parsed,
                        'db_path': db_path,
                        'metadata': item,
                    }
                fallback_match = {
                    'parsed': {
                        **parsed,
                        'shard_key': shard_meta.get('shard_key'),
                    },
                    'db_path': db_path,
                    'metadata': item,
                }

        return fallback_match

    def read_media_blob(
        self,
        username: str,
        media_id: int,
        media_type: str,
        start: int = None,
        end: int = None,
        shard_key: str = None,
    ):
        normalized = self._normalize_username_key(username)
        for db_path in self._get_db_paths_for_lookup(normalized, shard_key):
            if not os.path.exists(db_path):
                continue
            with self._connect_by_path(db_path) as conn:
                metadata = conn.execute(
                    """
                    SELECT
                        id,
                        username,
                        media_type,
                        filename,
                        size_bytes,
                        mime_type,
                        modified_at,
                        tweet_id,
                        media_index,
                        tweet_url,
                        source_url,
                        thumbnail_url,
                        thumbnail_path
                    FROM media_items
                    WHERE id = ? AND media_type = ? AND username = ?
                    """,
                    (media_id, media_type, normalized)
                ).fetchone()
                if not metadata:
                    continue

                if start is None or end is None:
                    content_row = conn.execute(
                        """
                        SELECT content
                        FROM media_items
                        WHERE id = ? AND media_type = ? AND username = ?
                        """,
                        (media_id, media_type, normalized)
                    ).fetchone()
                    data = content_row['content'] if content_row else None
                else:
                    length = max(0, end - start + 1)
                    content_row = conn.execute(
                        """
                        SELECT substr(content, ?, ?) AS content
                        FROM media_items
                        WHERE id = ? AND media_type = ? AND username = ?
                        """,
                        (start + 1, length, media_id, media_type, normalized)
                    ).fetchone()
                    data = content_row['content'] if content_row else None

                shard_meta = self._get_shard_meta(conn, db_path)
                return self._serialize_row(normalized, metadata, shard_meta.get('shard_key')), data

        return None, None


media_store = MediaStore()
