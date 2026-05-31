"""
任务管理器的执行与下载逻辑
"""
from datetime import datetime, timedelta
import os
import queue
import shutil
import time

import core.config as config
from scrapers import SeleniumTwitterScraper, TweepyTwitterScraper
from services import DocumentGenerator, MediaDownloader, media_store
from tasks.models import Task, TaskInterruptedError, TaskStatus


class TaskManagerExecutionMixin:
    """任务执行流程"""

    @staticmethod
    def _build_media_staging_dir(task_id: str, media_type: str) -> str:
        staging_dir = os.path.join(config.MEDIA_STAGING_DIR, task_id, media_type)
        os.makedirs(staging_dir, exist_ok=True)
        return staging_dir

    @staticmethod
    def _cleanup_path(path: str):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    @staticmethod
    def _cleanup_directory(path: str):
        if path and os.path.exists(path):
            try:
                if os.path.isdir(path) and os.listdir(path):
                    return
                shutil.rmtree(path)
            except Exception:
                pass

    @staticmethod
    def _task_documents_dir(username: str, task_id: str) -> str:
        task_docs_dir = os.path.join(config.OUTPUT_DIR, username, 'tasks', task_id, 'documents')
        os.makedirs(task_docs_dir, exist_ok=True)
        return task_docs_dir

    def _copy_task_document_snapshot(self, username: str, task_id: str, source_path: str, document_type: str):
        if not source_path or not os.path.exists(source_path):
            return None

        task_docs_dir = self._task_documents_dir(username, task_id)
        snapshot_name = f"{document_type}_{os.path.basename(source_path)}"
        snapshot_path = os.path.join(task_docs_dir, snapshot_name)
        shutil.copy2(source_path, snapshot_path)
        relative_path = os.path.relpath(snapshot_path, config.OUTPUT_DIR)
        return {
            'name': snapshot_name,
            'username': username,
            'task_id': task_id,
            'path': relative_path,
            'url': f"/output/{relative_path}",
            'size': os.path.getsize(snapshot_path),
            'modified_at': os.path.getmtime(snapshot_path),
            'storage_backend': 'filesystem',
            'document_type': document_type,
        }

    @staticmethod
    def _build_document_candidates(doc_gen, document_type: str):
        candidates = []
        if config.GENERATE_HTML_DOC:
            candidates.append(os.path.join(doc_gen.docs_dir, f"{document_type}_{doc_gen.username}_{doc_gen.timestamp}.html"))
        if config.GENERATE_MD_DOC:
            candidates.append(os.path.join(doc_gen.docs_dir, f"{document_type}_{doc_gen.username}_{doc_gen.timestamp}.md"))
        return candidates

    @staticmethod
    def _serialize_media_artifact(item: dict, key: str):
        stored = item.get(key) or {}
        artifact_path = stored.get('path') or item.get('video_db_path') or item.get('photo_db_path')
        artifact_url = f"/output/{artifact_path}" if artifact_path else item.get('video_app_url') or item.get('photo_app_url')
        return {
            'id': stored.get('id'),
            'name': stored.get('name') or item.get('video_filename') or item.get('photo_filename'),
            'username': stored.get('username') or item.get('username'),
            'task_id': stored.get('task_id') or item.get('task_id'),
            'path': artifact_path,
            'url': artifact_url,
            'size': stored.get('size'),
            'modified_at': stored.get('modified_at'),
            'media_type': stored.get('media_type'),
            'storage_backend': stored.get('storage_backend') or item.get('video_storage_backend') or item.get('photo_storage_backend'),
            'tweet_id': stored.get('tweet_id') or item.get('tweet_id'),
            'media_index': stored.get('media_index') if stored.get('media_index') is not None else item.get('media_index'),
            'tweet_url': stored.get('tweet_url') or item.get('tweet_url'),
            'source_url': stored.get('source_url') or item.get('direct_url') or item.get('photo_url') or item.get('tweet_url_for_ytdlp'),
            'duplicate_saved': stored.get('duplicate_saved', False),
            'duplicate_path': stored.get('duplicate_path'),
            'duplicate_of_id': stored.get('duplicate_of_id'),
        }

    def _persist_video_results_to_store(self, username: str, task_id: str, video_results):
        persisted_results = []

        for item in video_results:
            video_path = item.get('video_path')
            thumbnail_path = item.get('thumbnail_path')
            info_path = video_path.replace('.mp4', '_INFO.txt') if video_path else None
            fallback_thumb_path = video_path.replace('.mp4', '_thumb.jpg') if video_path else None
            should_cleanup_temp = True

            if item.get('success') and video_path and os.path.exists(video_path):
                try:
                    stored = media_store.store_file(
                        username,
                        'video',
                        video_path,
                        item.get('video_filename') or os.path.basename(video_path),
                        task_id=task_id,
                        source_url=item.get('direct_url') or item.get('tweet_url_for_ytdlp'),
                        tweet_id=item.get('tweet_id'),
                        media_index=item.get('media_index'),
                        tweet_url=item.get('tweet_url'),
                        thumbnail_path=thumbnail_path if thumbnail_path and os.path.exists(thumbnail_path) else fallback_thumb_path,
                        thumbnail_url=item.get('thumbnail_url')
                    )
                    if stored:
                        item['stored_media'] = stored
                        item['task_id'] = task_id
                        item['media_index'] = item.get('media_index')
                        item['video_db_path'] = stored['path']
                        item['video_app_url'] = f"/output/{stored['path']}"
                        item['video_storage_backend'] = 'sqlite'
                except Exception as e:
                    should_cleanup_temp = False
                    item['storage_error'] = str(e)
                    print(f"⚠️ 视频写入账号库失败，已保留临时文件: {e}")

            if should_cleanup_temp:
                self._cleanup_path(video_path)
                self._cleanup_path(thumbnail_path)
                self._cleanup_path(fallback_thumb_path)
                self._cleanup_path(info_path)
            persisted_results.append(item)

        return persisted_results

    @staticmethod
    def _enrich_scraped_video_entries(downloader, tweets):
        if not tweets:
            return

        expanded_tweets = 0
        extra_video_slots = 0

        for tweet in tweets:
            videos = tweet.get('videos') or []
            if not videos:
                continue

            try:
                expanded_videos = downloader._expand_tweet_video_entries(tweet)
            except Exception as e:
                print(f"⚠️ 推文 {tweet.get('id')} 的视频位展开失败: {e}")
                continue

            if not expanded_videos or len(expanded_videos) < len(videos):
                continue

            if len(expanded_videos) > len(videos):
                expanded_tweets += 1
                extra_video_slots += len(expanded_videos) - len(videos)

            tweet['videos'] = expanded_videos
            tweet['media'] = expanded_videos + (tweet.get('photos') or [])

        if expanded_tweets > 0:
            print(
                f"🔍 已在原始推文数据中补全 {expanded_tweets} 条多视频推文，"
                f"新增 {extra_video_slots} 个视频位"
            )

    def _worker(self, worker_id):
        print(f"🔧 工作线程 #{worker_id} 已启动")
        while self.is_running:
            try:
                if self.rate_limit_reset_time:
                    now = datetime.now()
                    if now < self.rate_limit_reset_time:
                        wait_seconds = (self.rate_limit_reset_time - now).total_seconds()
                        print(f"⏳ 速率限制中，等待 {int(wait_seconds)} 秒...")
                        time.sleep(min(60, wait_seconds))
                        continue

                    self.rate_limit_reset_time = None
                    print("✅ 速率限制已解除，继续执行任务")

                try:
                    task = self.task_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if task.status in [
                    TaskStatus.CANCELLED,
                    TaskStatus.USER_PAUSED,
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                ]:
                    continue

                if task.status == TaskStatus.PAUSED and task.retry_after:
                    now = datetime.now()
                    if now < task.retry_after:
                        self.rate_limit_reset_time = min(
                            self.rate_limit_reset_time or task.retry_after,
                            task.retry_after
                        )
                        self.task_queue.put(task)
                        time.sleep(min(60, max(1, (task.retry_after - now).total_seconds())))
                        continue

                    task.status = TaskStatus.PENDING
                    task.retry_after = None
                    task.error_message = None

                with self.lock:
                    if task.task_id in self.running_tasks:
                        continue
                    self.running_tasks[task.task_id] = task

                try:
                    self._execute_task(task, worker_id)
                finally:
                    with self.lock:
                        if task.task_id in self.running_tasks:
                            del self.running_tasks[task.task_id]

            except Exception as e:
                print(f"❌ 工作线程错误: {e}")
                time.sleep(5)

    def _execute_task(self, task: Task, worker_id: int):
        try:
            self._raise_if_task_interrupted(task)
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.completed_at = None
            task.error_message = None
            self._save_tasks()

            print(f"🚀 [线程#{worker_id}] 开始执行任务: {task.task_id} - @{task.username}")

            user_dirs = config.get_user_dirs(task.username)
            print(f"📁 用户文件夹: output/{task.username}/")

            if not os.path.exists(user_dirs['output']):
                os.makedirs(user_dirs['output'], exist_ok=True)
                print(f"✅ 创建输出目录: {user_dirs['output']}")

            scrape_method = task.options.get('scrape_method', 'api')
            if scrape_method == 'selenium':
                try:
                    print("使用 Selenium 模式（无需API）")

                    twitter_login = None
                    if config.TWITTER_USERNAME and config.TWITTER_PASSWORD:
                        twitter_login = {
                            'username': config.TWITTER_USERNAME,
                            'password': config.TWITTER_PASSWORD
                        }
                        print(f"🔐 将使用Twitter账号登录: {config.TWITTER_USERNAME}")

                    scraper = SeleniumTwitterScraper(
                        task.username,
                        twitter_login=twitter_login,
                        headless=config.SELENIUM_HEADLESS,
                        task_id=task.task_id,
                        stop_callback=self._build_stop_callback(task),
                        behavior_mode=task.options.get('selenium_behavior_mode', 'balanced')
                    )
                except ImportError:
                    raise Exception("Selenium未安装，请安装：pip install selenium")
            else:
                print("使用 Twitter API 模式")
                scraper = TweepyTwitterScraper(task.username)

            print("步骤 1/4: 爬取推文数据")
            self._raise_if_task_interrupted(task)
            tweets = scraper.scrape_user_tweets(
                max_tweets=task.max_tweets,
                progress_callback=lambda current, total: self._update_progress(task, current, total)
            )
            self._raise_if_task_interrupted(task)

            if not tweets:
                raise Exception("未找到任何推文")

            print(f"成功爬取 {len(tweets)} 条推文")

            video_results = []
            photo_results = []
            successful_video_results = []
            successful_photo_results = []

            with MediaDownloader() as downloader:
                self._enrich_scraped_video_entries(downloader, tweets)
                scraper.save_raw_data(output_dir=user_dirs['output'])

                if task.options.get('download_videos', True):
                    print("步骤 2/4: 下载视频")
                    self._raise_if_task_interrupted(task)
                    tweets_with_videos = scraper.get_videos()
                    if tweets_with_videos:
                        video_results = self._download_videos(downloader, tweets_with_videos, user_dirs, task)
                        successful_video_results = [item for item in video_results if item.get('success')]
                        print(f"视频下载完成: 成功 {len(successful_video_results)}/{len(video_results)} 个")

                if task.options.get('download_photos', True):
                    print("步骤 3/4: 下载照片")
                    self._raise_if_task_interrupted(task)
                    tweets_with_photos = scraper.get_photos()
                    if tweets_with_photos:
                        photo_results = self._download_photos(downloader, tweets_with_photos, user_dirs, task)
                        successful_photo_results = [item for item in photo_results if item.get('success')]
                        print(f"照片下载完成: 成功 {len(successful_photo_results)}/{len(photo_results)} 张")

            print("步骤 4/4: 生成文档")
            self._raise_if_task_interrupted(task)
            doc_gen = DocumentGenerator(task.username, user_dirs['documents'])
            document_artifacts = []

            if video_results:
                doc_gen.generate_video_document(video_results)
                for doc_path in self._build_document_candidates(doc_gen, 'videos'):
                    snapshot = self._copy_task_document_snapshot(task.username, task.task_id, doc_path, 'videos')
                    if snapshot:
                        document_artifacts.append(snapshot)

            if photo_results:
                doc_gen.generate_photo_document(photo_results)
                for doc_path in self._build_document_candidates(doc_gen, 'photos'):
                    snapshot = self._copy_task_document_snapshot(task.username, task.task_id, doc_path, 'photos')
                    if snapshot:
                        document_artifacts.append(snapshot)

            if task.options.get('download_replies', True):
                self._raise_if_task_interrupted(task)
                replies = scraper.get_replies()
                if replies:
                    doc_gen.generate_reply_document(replies)
                    for doc_path in self._build_document_candidates(doc_gen, 'replies'):
                        snapshot = self._copy_task_document_snapshot(task.username, task.task_id, doc_path, 'replies')
                        if snapshot:
                            document_artifacts.append(snapshot)
                task.results['replies'] = len(replies)
            else:
                task.results['replies'] = 0

            task.results['total_tweets'] = len(tweets)
            task.results['videos'] = len(successful_video_results)
            task.results['photos'] = len(successful_photo_results)
            task.results['video_attempts'] = len(video_results)
            task.results['photo_attempts'] = len(photo_results)
            task.results['artifacts'] = {
                'videos': [
                    self._serialize_media_artifact(item, 'stored_media')
                    for item in successful_video_results
                    if item.get('stored_media') or item.get('video_db_path')
                ],
                'photos': [
                    self._serialize_media_artifact(item, 'stored_media')
                    for item in successful_photo_results
                    if item.get('stored_media') or item.get('photo_db_path')
                ],
                'documents': document_artifacts,
            }
            task.scraped_count = len(tweets)
            task.control_action = None

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 100

            self._save_history(task)
            print(
                f"✅ 任务完成: {task.task_id} - "
                f"推文:{len(tweets)} "
                f"视频:{len(successful_video_results)}/{len(video_results)} "
                f"照片:{len(successful_photo_results)}/{len(photo_results)}"
            )

        except TaskInterruptedError as interruption:
            self._handle_task_interruption(task, interruption)
        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'Too Many Requests' in error_str or '速率限制' in error_str:
                print(f"⏸️ 任务暂停（速率限制）: {task.task_id}")
                task.status = TaskStatus.PAUSED
                task.retry_after = datetime.now() + timedelta(minutes=15)
                task.retry_count += 1
                task.control_action = None
                task.error_message = f"速率限制，将在15分钟后自动重试（第{task.retry_count}次）"
                self.rate_limit_reset_time = task.retry_after
                self.task_queue.put(task)
            else:
                print(f"❌ 任务失败: {task.task_id} - {error_str}")
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.control_action = None
                task.error_message = error_str
        finally:
            self._save_tasks()

    def _update_progress(self, task: Task, current: int, total: int):
        task.scraped_count = current
        task.total = total
        task.progress = int((current / total) * 100) if total > 0 else 0

        if current % 10 == 0:
            self._save_tasks()

    def _download_videos(self, downloader, tweets_with_videos, user_dirs, task: Task):
        print(f"🎬 准备下载 {len(tweets_with_videos)} 条推文中的视频...")
        staging_dir = self._build_media_staging_dir(task.task_id, 'videos')

        try:
            self._raise_if_task_interrupted(task)
            results = downloader.download_videos(
                tweets_with_videos,
                output_dir=staging_dir,
                should_stop=lambda: self._get_requested_action(task) is not None
            )
            self._raise_if_task_interrupted(task)
            return self._persist_video_results_to_store(task.username, task.task_id, results)
        except Exception as e:
            print(f"❌ 下载视频时出错: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            self._cleanup_directory(staging_dir)

    def _download_photos(self, downloader, tweets_with_photos, user_dirs, task: Task):
        results = []
        photo_count = 0
        staging_dir = self._build_media_staging_dir(task.task_id, 'photos')

        try:
            for tweet in tweets_with_photos:
                self._raise_if_task_interrupted(task)
                for index, photo in enumerate(tweet['photos']):
                    self._raise_if_task_interrupted(task)
                    photo_count += 1
                    photo_url = photo.get('url')
                    if not photo_url:
                        continue

                    ext = downloader._get_file_extension(photo_url) or 'jpg'
                    photo_filename = f"photo_{photo_count:04d}_tweet_{tweet['id']}_{index}.{ext}"
                    photo_path = os.path.join(staging_dir, photo_filename)

                    try:
                        success = downloader._download_file(photo_url, photo_path, f"照片 {photo_count}")
                    except Exception as e:
                        print(f"下载照片失败: {e}")
                        success = False

                    if success:
                        stored = None
                        should_cleanup_temp = True
                        try:
                            stored = media_store.store_file(
                                task.username,
                                'photo',
                                photo_path,
                                photo_filename,
                                task_id=task.task_id,
                                source_url=photo_url,
                                tweet_id=tweet['id'],
                                media_index=index,
                                tweet_url=tweet['url']
                            )
                        except Exception as e:
                            should_cleanup_temp = False
                            print(f"⚠️ 照片写入账号库失败，已保留临时文件: {e}")
                        results.append({
                            'number': photo_count,
                            'tweet_id': tweet['id'],
                            'media_index': index,
                            'tweet_url': tweet['url'],
                            'tweet_content': tweet['content'],
                            'stored_media': stored,
                            'task_id': task.task_id,
                            'photo_url': photo_url,
                            'photo_path': photo_path,
                            'photo_filename': photo_filename,
                            'photo_db_path': stored['path'] if stored else None,
                            'photo_app_url': f"/output/{stored['path']}" if stored else None,
                            'photo_storage_backend': 'sqlite',
                            'success': True,
                            'date': tweet['date']
                        })
                        if should_cleanup_temp:
                            self._cleanup_path(photo_path)
        except Exception as e:
            print(f"下载照片时出错: {e}")

        self._cleanup_directory(staging_dir)
        return results
