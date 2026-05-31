"""
媒体下载模块
负责下载视频和图片
支持多线程并发下载
"""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import json  # ✅ 添加json导入（cookies转换需要）
from pathlib import Path
import shlex
import subprocess
import time
from typing import List, Dict, Optional, Tuple

import core.config as config
import requests
from services.downloader_helpers import (
    cleanup_ytdlp_temp_files,
    convert_cookies_to_netscape,
    extract_direct_video_urls,
    extract_ytdlp_error_message,
    get_file_extension,
    is_retryable_ytdlp_error,
    pick_thumbnail_url,
    safe_int,
    unique_urls,
)

try:
    from services.thumbnail_generator import ThumbnailGenerator
    THUMBNAIL_AVAILABLE = True
except ImportError:
    THUMBNAIL_AVAILABLE = False
    print("⚠️  缩略图生成模块未找到，将跳过缩略图生成")


class MediaDownloader:
    """媒体下载器"""

    YTDLP_MAX_RETRIES = 3
    YTDLP_RETRY_DELAY_SECONDS = 3
    DIRECT_MAX_RETRIES = 3
    DIRECT_RETRY_DELAY_SECONDS = 2
    
    def __init__(self, max_workers=5):
        """
        初始化下载器
        :param max_workers: 最大并发下载数（默认5个）
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://x.com/',
            'Origin': 'https://x.com',
            'Accept': '*/*',
        })
        self.max_workers = max_workers
        self._video_entry_metadata_cache = {}
    
    def __enter__(self):
        """支持with上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时关闭session"""
        self.close()
    
    def close(self):
        """关闭session，释放资源"""
        if self.session:
            self.session.close()

    def _build_ytdlp_base_command(self) -> Tuple[List[str], Optional[str]]:
        """构建 yt-dlp 基础命令，并按需附带 cookies。"""
        cmd = [
            'yt-dlp',
            '--no-warnings',
            '--quiet',
        ]
        netscape_cookies = None

        cookies_file = str(Path(config.COOKIE_FILE))
        if os.path.exists(cookies_file):
            try:
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                netscape_cookies = convert_cookies_to_netscape(cookies_file, cookies)
            except Exception as e:
                print(f"     ⚠️ cookies读取失败: {e}")
            if netscape_cookies:
                cmd.extend(['--cookies', netscape_cookies])

        return cmd, netscape_cookies

    def _build_expanded_video_entry(self, payload: dict, tweet_url: str, fallback_index: int) -> Optional[Dict]:
        if not isinstance(payload, dict):
            return None

        direct_url, alternative_urls = extract_direct_video_urls(payload)
        playlist_item = safe_int(
            payload.get('playlist_index') or payload.get('playlist_autonumber'),
            fallback_index + 1,
        )
        media_index = max(0, (playlist_item or (fallback_index + 1)) - 1)
        entry_webpage_url = payload.get('webpage_url') or payload.get('original_url') or tweet_url
        cdp_urls = unique_urls([direct_url] + alternative_urls)

        return {
            'type': 'video_ytdlp',
            'tweet_url': entry_webpage_url or tweet_url,
            'entry_webpage_url': entry_webpage_url or tweet_url,
            'playlist_item': playlist_item,
            'media_index': media_index,
            'direct_url': direct_url,
            'alternative_urls': alternative_urls,
            'cdp_urls': cdp_urls,
            'thumbnail_url': pick_thumbnail_url(payload),
        }

    def _extract_video_entries_with_ytdlp(self, tweet_url: str, description: str = "视频") -> List[Dict]:
        """用 yt-dlp 元数据展开一条推文中的所有视频条目。"""
        if not tweet_url:
            return []

        cached = self._video_entry_metadata_cache.get(tweet_url)
        if cached is not None:
            return [dict(item) for item in cached]

        netscape_cookies = None
        try:
            base_cmd, netscape_cookies = self._build_ytdlp_base_command()
            cmd = base_cmd + [
                '--dump-single-json',
                '--skip-download',
                tweet_url,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                error_msg = extract_ytdlp_error_message(result.stderr or result.stdout or '')
                if error_msg:
                    print(f"  ⚠️ {description} 元数据读取失败: {error_msg[:120]}")
                return []

            raw_output = (result.stdout or '').strip()
            if not raw_output:
                return []

            try:
                payload = json.loads(raw_output)
            except json.JSONDecodeError:
                last_json_line = next(
                    (line for line in reversed(raw_output.splitlines()) if line.strip().startswith('{')),
                    '',
                )
                payload = json.loads(last_json_line) if last_json_line else {}

            source_entries = payload.get('entries') if isinstance(payload, dict) else None
            if not isinstance(source_entries, list) or not source_entries:
                source_entries = [payload]

            expanded_entries = []
            for index, entry in enumerate(source_entries):
                built = self._build_expanded_video_entry(entry, tweet_url, index)
                if built:
                    if not built.get('thumbnail_url'):
                        built['thumbnail_url'] = pick_thumbnail_url(payload)
                    expanded_entries.append(built)

            deduped_entries = []
            seen = set()
            for entry in expanded_entries:
                dedupe_key = (
                    entry.get('entry_webpage_url') or entry.get('tweet_url') or tweet_url,
                    entry.get('playlist_item'),
                    entry.get('direct_url'),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                deduped_entries.append(entry)

            self._video_entry_metadata_cache[tweet_url] = [dict(item) for item in deduped_entries]
            return [dict(item) for item in deduped_entries]
        except FileNotFoundError:
            print("  ⚠️ 未找到 yt-dlp，无法展开多视频元数据")
            return []
        except Exception as e:
            print(f"  ⚠️ {description} 元数据展开失败: {str(e)[:120]}")
            return []
        finally:
            if netscape_cookies and os.path.exists(netscape_cookies):
                try:
                    os.remove(netscape_cookies)
                except Exception:
                    pass

    def _normalize_existing_video_entry(self, video: dict, index: int, tweet_url: str) -> Dict:
        direct_candidates = unique_urls([
            video.get('direct_url'),
            *(video.get('alternative_urls') or []),
            *(video.get('cdp_urls') or []),
        ])

        media_index = safe_int(video.get('media_index'), index)
        playlist_item = safe_int(video.get('playlist_item'))
        if playlist_item is None and media_index is not None:
            playlist_item = media_index + 1

        return {
            **video,
            'type': video.get('type') or 'video_ytdlp',
            'tweet_url': video.get('tweet_url') or tweet_url,
            'entry_webpage_url': video.get('entry_webpage_url') or video.get('tweet_url') or tweet_url,
            'media_index': media_index,
            'playlist_item': playlist_item,
            'direct_url': direct_candidates[0] if direct_candidates else video.get('direct_url'),
            'alternative_urls': direct_candidates[1:] if direct_candidates else (video.get('alternative_urls') or []),
            'cdp_urls': direct_candidates if direct_candidates else (video.get('cdp_urls') or []),
        }

    def _expand_tweet_video_entries(self, tweet: dict) -> List[Dict]:
        tweet_url = tweet.get('url') or ''
        original_videos = tweet.get('videos') or []
        normalized_entries = [
            self._normalize_existing_video_entry(video, index, tweet_url)
            for index, video in enumerate(original_videos)
        ]
        metadata_entries = self._extract_video_entries_with_ytdlp(
            tweet_url,
            description=f"推文 {tweet.get('id')}",
        )

        if not metadata_entries:
            return normalized_entries

        if len(metadata_entries) < len(normalized_entries):
            return normalized_entries

        merged_entries = []
        fallback_base = normalized_entries[0] if normalized_entries else {}
        for index, entry in enumerate(metadata_entries):
            base = normalized_entries[index] if index < len(normalized_entries) else fallback_base
            merged_urls = unique_urls([
                entry.get('direct_url'),
                base.get('direct_url'),
                *(entry.get('alternative_urls') or []),
                *(base.get('alternative_urls') or []),
                *(base.get('cdp_urls') or []),
                *(entry.get('cdp_urls') or []),
            ])
            media_index = safe_int(entry.get('media_index'))
            if media_index is None:
                media_index = safe_int(base.get('media_index'), index)
            playlist_item = safe_int(entry.get('playlist_item'))
            if playlist_item is None and media_index is not None:
                playlist_item = media_index + 1

            merged_entries.append({
                **base,
                **entry,
                'tweet_url': entry.get('tweet_url') or base.get('tweet_url') or tweet_url,
                'entry_webpage_url': entry.get('entry_webpage_url') or base.get('entry_webpage_url') or tweet_url,
                'media_index': media_index,
                'playlist_item': playlist_item,
                'direct_url': merged_urls[0] if merged_urls else entry.get('direct_url') or base.get('direct_url'),
                'alternative_urls': merged_urls[1:],
                'cdp_urls': merged_urls,
                'thumbnail_url': entry.get('thumbnail_url') or base.get('thumbnail_url'),
            })

        if len(merged_entries) > len(normalized_entries):
            print(
                f"  🔎 推文 {tweet.get('id')} 从 {len(normalized_entries)} 个视频位展开到 "
                f"{len(merged_entries)} 个视频位"
            )

        return merged_entries
    
    def download_videos(self, tweets_with_videos: List[Dict], output_dir: str = None, should_stop=None) -> List[Dict]:
        """
        下载所有视频（并发下载加速）
        :param tweets_with_videos: 包含视频的推文列表
        :param output_dir: 输出目录，默认使用配置中的视频目录
        :param should_stop: 停止检查回调，返回True时不再提交新的下载任务
        :return: 下载结果列表
        """
        print(f"\n🚀 并发下载视频 (最多{self.max_workers}线程)，共 {len(tweets_with_videos)} 条推文...")

        output_dir = output_dir or config.VIDEOS_DIR
        os.makedirs(output_dir, exist_ok=True)

        results = []
        video_count = 0
        download_tasks = []
        
        # 准备所有下载任务
        for tweet in tweets_with_videos:
            tweet_id = tweet['id']

            expanded_videos = self._expand_tweet_video_entries(tweet)

            for j, video in enumerate(expanded_videos):
                video_count += 1
                video_type = video.get('type', 'video')  # 获取类型
                # ✅ 修复：direct_url是CDP捕获的直连URL，tweet_url是用于yt-dlp的
                direct_url = video.get('direct_url')  # CDP捕获的直连URL
                tweet_url_for_ytdlp = video.get('tweet_url') or tweet.get('url')  # yt-dlp专用URL
                alternative_urls = video.get('alternative_urls', [])  # 获取备选URL
                cdp_urls = video.get('cdp_urls', [])  # CDP捕获的所有URL
                thumbnail_url = video.get('thumbnail_url')
                media_index = safe_int(video.get('media_index'), j)
                playlist_item = safe_int(video.get('playlist_item'))
                
                # 视频文件名
                video_filename = f"video_{video_count:04d}_tweet_{tweet_id}_{media_index}.mp4"
                video_path = os.path.join(output_dir, video_filename)
                
                # 缩略图文件名
                thumb_ext = get_file_extension(thumbnail_url) if thumbnail_url else 'jpg'
                if thumb_ext not in {'jpg', 'jpeg', 'png', 'webp'}:
                    thumb_ext = 'jpg'
                thumbnail_filename = f"video_{video_count:04d}_tweet_{tweet_id}_{media_index}_thumb.{thumb_ext}"
                thumbnail_path = os.path.join(output_dir, thumbnail_filename)
                if thumbnail_url:
                    thumbnail_path = os.path.join(output_dir, thumbnail_filename)
                
                download_tasks.append({
                    'number': video_count,
                    'tweet_id': tweet_id,
                    'media_index': media_index,
                    'playlist_item': playlist_item,
                    'tweet_url': tweet['url'],
                    'tweet_content': tweet['content'],
                    'direct_url': direct_url,  # ✅ CDP捕获的直连URL
                    'video_type': video_type,
                    'tweet_url_for_ytdlp': tweet_url_for_ytdlp,  # yt-dlp专用URL
                    'entry_webpage_url': video.get('entry_webpage_url') or tweet_url_for_ytdlp,
                    'alternative_urls': alternative_urls,  # CDP捕获的备选URL
                    'cdp_urls': cdp_urls,  # CDP捕获的所有URL
                    'video_path': video_path,
                    'video_filename': video_filename,
                    'thumbnail_url': thumbnail_url,
                    'thumbnail_path': thumbnail_path,
                    'thumbnail_filename': thumbnail_filename,
                    'date': tweet['date']
                })
        
        # 并发下载，按批次提交，方便在暂停/取消后尽快停住
        completed = 0
        next_index = 0
        stop_requested = False

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}

            while next_index < len(download_tasks) and len(future_to_task) < self.max_workers:
                task = download_tasks[next_index]
                future = executor.submit(
                    self._download_video_progressive,
                    task,
                    f"视频 {task['number']}"
                )
                future_to_task[future] = task
                next_index += 1

            while future_to_task:
                if should_stop and should_stop():
                    stop_requested = True

                done, _ = wait(list(future_to_task.keys()), timeout=0.5, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                for future in done:
                    task = future_to_task.pop(future)
                    success = future.result()
                    task['success'] = success
                    results.append(task)
                    
                    # 下载缩略图
                    if task['thumbnail_url'] and success:
                        self._download_file(task['thumbnail_url'], task['thumbnail_path'], f"缩略图 {task['number']}")
                    
                    completed += 1
                    if completed % 5 == 0:
                        print(f"  进度: {completed}/{len(download_tasks)}")

                while not stop_requested and next_index < len(download_tasks) and len(future_to_task) < self.max_workers:
                    task = download_tasks[next_index]
                    future = executor.submit(
                        self._download_video_progressive,
                        task,
                        f"视频 {task['number']}"
                    )
                    future_to_task[future] = task
                    next_index += 1

            if stop_requested and next_index < len(download_tasks):
                skipped = len(download_tasks) - next_index
                print(f"⏹️ 检测到任务停止请求，剩余 {skipped} 个视频下载未再提交")
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\n✅ 视频下载完成！成功 {success_count}/{video_count} 个")
        
        # 生成视频缩略图
        if THUMBNAIL_AVAILABLE and success_count > 0:
            print(f"\n🖼️  生成视频缩略图...")
            thumb_count = 0
            for result in results:
                if result['success'] and os.path.exists(result['video_path']):
                    generated_path = ThumbnailGenerator.generate_video_thumbnail(
                        result['video_path'],
                        result.get('thumbnail_path'),
                    )
                    if generated_path:
                        result['thumbnail_path'] = generated_path
                        thumb_count += 1
            print(f"✅ 缩略图生成完成！{thumb_count}/{success_count} 个")
        
        return results
    
    def download_photos(self, tweets_with_photos: List[Dict]) -> List[Dict]:
        """
        下载所有照片（并发下载加速）
        :param tweets_with_photos: 包含照片的推文列表
        :return: 下载结果列表
        """
        print(f"\n🚀 并发下载照片 (最多{self.max_workers}线程)，共 {len(tweets_with_photos)} 条推文...")
        
        results = []
        photo_count = 0
        download_tasks = []
        
        # 准备所有下载任务
        for tweet in tweets_with_photos:
            tweet_id = tweet['id']
            
            for j, photo in enumerate(tweet['photos']):
                photo_count += 1
                photo_url = photo['url']
                
                # 获取文件扩展名
                ext = get_file_extension(photo_url) or 'jpg'
                
                # 照片文件名
                photo_filename = f"photo_{photo_count:04d}_tweet_{tweet_id}_{j}.{ext}"
                photo_path = os.path.join(config.PHOTOS_DIR, photo_filename)
                
                download_tasks.append({
                    'number': photo_count,
                    'tweet_id': tweet_id,
                    'tweet_url': tweet['url'],
                    'tweet_content': tweet['content'],
                    'photo_url': photo_url,
                    'photo_path': photo_path,
                    'photo_filename': photo_filename,
                    'date': tweet['date']
                })
        
        # 并发下载
        completed = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._download_file, task['photo_url'], task['photo_path'], f"照片 {task['number']}"): task
                for task in download_tasks
            }
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                success = future.result()
                task['success'] = success
                results.append(task)
                
                completed += 1
                if completed % 10 == 0:
                    print(f"  进度: {completed}/{len(download_tasks)}")
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\n✅ 照片下载完成！成功 {success_count}/{photo_count} 张")
        
        # 生成照片缩略图
        if THUMBNAIL_AVAILABLE and success_count > 0:
            print(f"\n🖼️  生成照片缩略图...")
            thumb_count = 0
            for result in results:
                if result['success'] and os.path.exists(result['photo_path']):
                    if ThumbnailGenerator.generate_photo_thumbnail(result['photo_path']):
                        thumb_count += 1
            print(f"✅ 缩略图生成完成！{thumb_count}/{success_count} 张")
        
        return results
    
    def _download_file_with_fallback(self, url: str, alternative_urls: list, save_path: str, description: str = "文件") -> bool:
        """
        尝试下载文件，如果主URL失败则尝试备选URL
        :param url: 主URL
        :param alternative_urls: 备选URL列表
        :param save_path: 保存路径
        :param description: 文件描述
        :return: 是否成功
        """
        # 调试：显示收到的备选URL数量
        alt_count = len(alternative_urls) if alternative_urls else 0
        print(f"  📥 {description}: 主URL + {alt_count} 个备选URL")
        
        # 先尝试主URL
        if self._download_file(url, save_path, description, allow_resume=True):
            return True
        
        # 如果主URL失败，尝试备选URL
        if alternative_urls and len(alternative_urls) > 0:
            print(f"  ⚠️ 主URL失败，尝试 {len(alternative_urls)} 个备选URL...")
            for i, alt_url in enumerate(alternative_urls, 1):
                print(f"    尝试备选URL {i}/{len(alternative_urls)}: {alt_url[:60]}...")
                # 备选URL可能指向不同变体，不能复用上一个URL留下的.part续传。
                if self._download_file(alt_url, save_path, f"{description} (备选{i})", allow_resume=False):
                    print(f"  ✅ 备选URL {i} 成功！")
                    return True
        else:
            print(f"  ⚠️ 没有备选URL可尝试")
        
        print(f"  ✗ 所有URL都失败")
        return False
    
    def _download_file(self, url: str, save_path: str, description: str = "文件", allow_resume: bool = True) -> bool:
        """
        下载单个文件（优化版：大buffer + 断点续传 + 速度显示）
        :param url: 文件URL
        :param save_path: 保存路径
        :param description: 文件描述
        :return: 是否成功
        """
        temp_path = save_path + '.part'

        for attempt in range(1, self.DIRECT_MAX_RETRIES + 1):
            try:
                downloaded_size = 0

                if not allow_resume and os.path.exists(temp_path):
                    os.remove(temp_path)

                # 检查是否有未完成的下载
                if os.path.exists(temp_path):
                    downloaded_size = os.path.getsize(temp_path)
                elif os.path.exists(save_path):
                    # 文件已存在且完整，跳过
                    return True

                # 断点续传：设置Range请求头
                headers = {}
                if allow_resume and downloaded_size > 0:
                    headers['Range'] = f'bytes={downloaded_size}-'
                    print(f"  ↻ {description} 断点续传，已下载 {downloaded_size / 1024 / 1024:.1f}MB")
                elif downloaded_size > 0:
                    downloaded_size = 0

                start_time = time.time()
                response = self.session.get(url, headers=headers, stream=True, timeout=60)

                # 206表示断点续传成功，200表示重新下载
                if response.status_code not in [200, 206]:
                    response.raise_for_status()

                # 获取文件总大小
                if response.status_code == 206:
                    # 断点续传模式
                    content_range = response.headers.get('content-range', '')
                    if '/' in content_range:
                        total_size = int(content_range.split('/')[-1])
                    else:
                        total_size = int(response.headers.get('content-length', 0)) + downloaded_size
                else:
                    # 全新下载模式
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0  # 重新开始

                # 使用大buffer加速下载 (1MB chunks)
                mode = 'ab' if downloaded_size > 0 else 'wb'
                with open(temp_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=1048576):  # 1MB
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                # 下载完成，重命名文件
                if os.path.exists(save_path):
                    os.remove(save_path)
                os.rename(temp_path, save_path)

                # 计算速度
                elapsed = time.time() - start_time
                if elapsed > 0:
                    speed_mbps = (downloaded_size / 1024 / 1024) / elapsed
                    size_mb = total_size / 1024 / 1024
                    print(f"  ✓ {description} ({size_mb:.1f}MB, {speed_mbps:.1f}MB/s)")
                else:
                    print(f"  ✓ {description} 下载成功")

                return True

            except Exception as e:
                status_code = getattr(getattr(e, 'response', None), 'status_code', None)
                retryable = (
                    isinstance(e, (
                        requests.exceptions.Timeout,
                        requests.exceptions.ConnectionError,
                        requests.exceptions.ChunkedEncodingError,
                    ))
                    or status_code in {403, 408, 409, 425, 429, 500, 502, 503, 504}
                )
                print(f"  ✗ {description} 下载失败: {e}")
                if attempt < self.DIRECT_MAX_RETRIES and retryable:
                    print(f"  ↻ {description} {self.DIRECT_RETRY_DELAY_SECONDS} 秒后重试 ({attempt}/{self.DIRECT_MAX_RETRIES})")
                    time.sleep(self.DIRECT_RETRY_DELAY_SECONDS)
                    continue
                # 保留.part文件供下次断点续传
                return False
    
    def _download_video_progressive(self, task: dict, description: str = "文件") -> bool:
        """
        渐进式降级视频下载
        1. 优先尝试 yt-dlp（带cookies支持）
        2. 备用尝试 CDP捕获的直连URL
        3. 再试备选URL列表
        4. 最后降级到只保存缩略图
        
        :param task: 下载任务字典
        :param description: 描述信息
        :return: 是否成功
        """
        save_path = task['video_path']
        tweet_url = task.get('tweet_url_for_ytdlp')
        playlist_item = task.get('playlist_item')
        video_type = task.get('video_type', 'video')
        
        # 如果文件已存在，跳过
        if os.path.exists(save_path):
            print(f"  ⊙ {description} 已存在，跳过")
            return True
        
        print(f"  🎬 {description} 开始下载...")
        
        # 方法1: 尝试 yt-dlp（主要方法）
        if video_type == 'video_ytdlp' and tweet_url:
            print(f"  ├─ 方法1: yt-dlp下载")
            if self._download_with_ytdlp(tweet_url, save_path, description, playlist_item=playlist_item):
                print(f"  ✅ {description} yt-dlp下载成功")
                return True
            print(f"  ├─ yt-dlp失败，尝试备用方案...")
        
        # 方法2: 尝试CDP捕获的直连URL
        direct_url = task.get('direct_url')  # ✅ 直接从task获取
        alternative_urls = task.get('alternative_urls', [])
        if direct_url or alternative_urls:
            print(f"  ├─ 方法2: 直连URL兜底")
            primary_url = direct_url or alternative_urls[0]
            fallback_urls = alternative_urls if direct_url else alternative_urls[1:]
            if self._download_file_with_fallback(primary_url, fallback_urls, save_path, description):
                print(f"  ✅ {description} 直连URL下载成功")
                return True
            print(f"  ├─ 所有直连URL均失败...")
        
        # 方法4: 降级 - 只保存缩略图
        thumbnail_url = task.get('thumbnail_url')
        if thumbnail_url:
            print(f"  ├─ 方法4: 降级到保存缩略图")
            thumb_path = save_path.replace('.mp4', '_thumb.jpg')
            if self._download_file(thumbnail_url, thumb_path, f"{description}(缩略图)"):
                print(f"  ⚠️ {description} 仅保存缩略图 (视频下载失败)")
                # 创建一个说明文件
                info_path = save_path.replace('.mp4', '_INFO.txt')
                with open(info_path, 'w', encoding='utf-8') as f:
                    f.write(f"视频下载失败\n")
                    f.write(f"推文链接: {tweet_url}\n")
                    f.write(f"缩略图: {os.path.basename(thumb_path)}\n")
                return False  # 标记为失败，但至少保存了缩略图
        
        print(f"  ✗ {description} 所有下载方法均失败")
        return False
    
    def _download_with_ytdlp(self, tweet_url: str, save_path: str, description: str = "文件", playlist_item: int = None) -> bool:
        """
        使用yt-dlp下载Twitter视频（带cookies支持）
        :param tweet_url: 推文URL
        :param save_path: 保存路径
        :param description: 描述信息
        :param playlist_item: 指定下载第几个媒体位（1-based）
        :return: 是否成功
        """
        # 如果文件已存在，跳过
        if os.path.exists(save_path):
            return True

        for attempt in range(1, self.YTDLP_MAX_RETRIES + 1):
            netscape_cookies = None

            try:
                # 准备yt-dlp命令（下载最高画质）
                base_cmd, netscape_cookies = self._build_ytdlp_base_command()
                cmd = base_cmd + [
                    # 格式选择：优先最高画质视频+音频，失败则降级
                    '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
                    '--merge-output-format', 'mp4',  # 合并为MP4
                    '--no-progress',                 # 不显示进度条
                    '--concurrent-fragments', '4',
                    '--socket-timeout', '30',
                    '-o', save_path,                 # 输出文件路径
                ]

                if playlist_item:
                    cmd.extend(['--playlist-items', str(playlist_item)])
                else:
                    cmd.append('--no-playlist')

                if netscape_cookies:
                    print(f"     ├─ 使用cookies登录状态")

                cmd.append(tweet_url)

                if attempt > 1:
                    print(f"     ├─ 第 {attempt}/{self.YTDLP_MAX_RETRIES} 次重试")

                # 执行命令
                start_time = time.time()
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )

                # 检查是否成功
                if result.returncode == 0 and os.path.exists(save_path):
                    elapsed = time.time() - start_time
                    file_size = os.path.getsize(save_path)
                    size_mb = file_size / 1024 / 1024
                    print(f"     ✓ 成功 ({size_mb:.1f}MB, {elapsed:.1f}s)")
                    return True

                error_msg = extract_ytdlp_error_message(result.stderr or result.stdout or '')
                if error_msg:
                    print(f"     ✗ {error_msg[:100]}")
                else:
                    print(f"     ✗ 失败 (returncode={result.returncode})")

                if attempt < self.YTDLP_MAX_RETRIES and is_retryable_ytdlp_error(error_msg):
                    cleanup_ytdlp_temp_files(save_path)
                    print(
                        f"     ↻ 检测到临时网络错误，"
                        f"{self.YTDLP_RETRY_DELAY_SECONDS} 秒后自动重试..."
                    )
                    time.sleep(self.YTDLP_RETRY_DELAY_SECONDS)
                    continue
                return False

            except subprocess.TimeoutExpired:
                print(f"     ✗ 超时 (>5分钟)")
                if attempt < self.YTDLP_MAX_RETRIES:
                    cleanup_ytdlp_temp_files(save_path)
                    print(
                        f"     ↻ 下载超时，"
                        f"{self.YTDLP_RETRY_DELAY_SECONDS} 秒后自动重试..."
                    )
                    time.sleep(self.YTDLP_RETRY_DELAY_SECONDS)
                    continue
                return False
            except FileNotFoundError:
                print(f"     ✗ 未找到yt-dlp命令")
                return False
            except Exception as e:
                error_msg = str(e)
                print(f"     ✗ 异常: {error_msg[:100]}")
                if attempt < self.YTDLP_MAX_RETRIES and is_retryable_ytdlp_error(error_msg):
                    cleanup_ytdlp_temp_files(save_path)
                    print(
                        f"     ↻ 检测到临时异常，"
                        f"{self.YTDLP_RETRY_DELAY_SECONDS} 秒后自动重试..."
                    )
                    time.sleep(self.YTDLP_RETRY_DELAY_SECONDS)
                    continue
                return False
            finally:
                if netscape_cookies and os.path.exists(netscape_cookies):
                    try:
                        os.remove(netscape_cookies)
                    except Exception:
                        pass

        return False
