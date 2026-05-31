"""
Selenium 爬虫的抓取主流程与推文提取
"""
import json
import os
import random
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import core.config as config
from selenium.webdriver.common.by import By


class SeleniumScrapeMixin:
    """抓取主流程与数据提取"""

    @staticmethod
    def _extract_tweet_id_from_url(tweet_url: str) -> str:
        """从任意 status URL 中提取标准 tweet id。"""
        if not tweet_url:
            return ""

        path = urlparse(tweet_url).path or tweet_url
        if '/status/' not in path:
            return ""

        suffix = path.split('/status/', 1)[1]
        return suffix.split('/')[0].split('?')[0].strip()

    def _normalize_tweet_url(self, tweet_url: str) -> str:
        """将 photo/video 子路径归一为标准推文 URL。"""
        if not tweet_url:
            return ""

        parsed = urlparse(tweet_url)
        tweet_id = self._extract_tweet_id_from_url(tweet_url)
        if not tweet_id:
            return tweet_url

        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/{self.username}/status/{tweet_id}"

        return f"/{self.username}/status/{tweet_id}"

    def _peek_tweet_identity(self, element) -> Dict[str, str]:
        """在正式提取前快速读取 tweet id/url，用于去重和重试。"""
        try:
            time_nodes = element.find_elements(By.TAG_NAME, 'time')
            if time_nodes:
                try:
                    time_link = time_nodes[0].find_element(By.XPATH, './ancestor::a[1]')
                    href = (time_link.get_attribute('href') or '').strip()
                    tweet_id = self._extract_tweet_id_from_url(href)
                    if tweet_id:
                        normalized_url = self._normalize_tweet_url(href)
                        return {
                            'id': tweet_id,
                            'url': normalized_url
                        }
                except Exception:
                    pass

            links = element.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
            for link in links:
                href = (link.get_attribute('href') or '').strip()
                tweet_id = self._extract_tweet_id_from_url(href)
                if tweet_id:
                    normalized_url = self._normalize_tweet_url(href)
                    return {
                        'id': tweet_id,
                        'url': normalized_url
                    }
        except Exception:
            pass

        return {}

    def _find_tweet_element_by_id(self, tweet_id: str):
        """当 DOM 重绘导致元素失效时，按 tweet id 重新定位元素。"""
        if not tweet_id:
            return None

        try:
            matches = self.driver.find_elements(
                By.XPATH,
                f'//article[@data-testid="tweet"][.//a[contains(@href, "/status/{tweet_id}")]]'
            )
            return matches[0] if matches else None
        except Exception:
            return None

    def _tweet_element_may_have_video(self, element) -> bool:
        """仅在疑似视频推文时再触发点击，减少无效交互。"""
        selectors = [
            'video',
            '[data-testid="videoPlayer"]',
            '[data-testid="playButton"]',
            '[aria-label*="Play"]',
            '[aria-label*="播放"]',
            'div[aria-label*="Video"]',
            'div[aria-label*="视频"]'
        ]

        try:
            for selector in selectors:
                if element.find_elements(By.CSS_SELECTOR, selector):
                    return True
        except Exception:
            return False

        return False

    @staticmethod
    def _unique_preserve_order(values: List[str]) -> List[str]:
        seen = set()
        result = []
        for value in values or []:
            text = str(value or '').strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    @staticmethod
    def _has_merge_value(value) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    @staticmethod
    def _parse_metric_count(text: str) -> Optional[int]:
        raw = str(text or '').strip()
        if not raw:
            return None

        normalized = raw.replace(',', '').replace('，', '').replace('次', '')
        match = re.search(r'(\d+(?:\.\d+)?)\s*([KMBkmb]|千|万|亿)?', normalized)
        if not match:
            return None

        base = float(match.group(1))
        suffix = (match.group(2) or '').upper()
        multiplier = 1
        if suffix == 'K' or suffix == '千':
            multiplier = 1_000
        elif suffix == 'M' or suffix == '万':
            multiplier = 1_000_000 if suffix == 'M' else 10_000
        elif suffix == 'B' or suffix == '亿':
            multiplier = 1_000_000_000 if suffix == 'B' else 100_000_000

        return int(round(base * multiplier))

    def _extract_action_metric(self, element, selectors: List[str]) -> int:
        candidates = []

        for selector in selectors:
            try:
                candidates.extend(element.find_elements(By.CSS_SELECTOR, selector))
            except Exception:
                continue

        for node in candidates:
            text_candidates = [
                node.text,
                node.get_attribute('aria-label'),
                node.get_attribute('title'),
            ]
            try:
                text_candidates.extend(child.text for child in node.find_elements(By.CSS_SELECTOR, 'span'))
            except Exception:
                pass

            for text in text_candidates:
                value = self._parse_metric_count(text)
                if value is not None:
                    return value

        return 0

    @staticmethod
    def _prefer_large_profile_image(url: str) -> str:
        text = str(url or '').strip()
        if not text:
            return ''
        return text.replace('_normal.', '_400x400.')

    def _extract_tweet_author_avatar_url(self, element) -> str:
        try:
            for img in element.find_elements(By.CSS_SELECTOR, 'img[src*="profile_images"]'):
                src = self._prefer_large_profile_image(img.get_attribute('src'))
                if src:
                    return src
        except Exception:
            pass
        return ''

    def _extract_video_thumbnail_url(self, element, video_elements=None) -> str:
        for video in video_elements or []:
            try:
                poster = video.get_attribute('poster') or ''
                if poster and not poster.startswith('blob:'):
                    return poster
            except Exception:
                pass

        selectors = [
            'img[src*="amplify_video_thumb"]',
            'img[src*="ext_tw_video_thumb"]',
            'img[src*="pbs.twimg.com/media"]',
        ]
        try:
            for selector in selectors:
                for img in element.find_elements(By.CSS_SELECTOR, selector):
                    src = img.get_attribute('src') or ''
                    if src and 'profile_images' not in src:
                        return src
        except Exception:
            pass
        return ''

    def _extract_node_text(self, node) -> str:
        try:
            text = (node.text or '').strip()
            if text:
                return text
        except Exception:
            pass

        try:
            text = self.driver.execute_script(
                "return (arguments[0].innerText || arguments[0].textContent || '').trim();",
                node,
            )
            return str(text or '').strip()
        except Exception:
            return ''

    def _is_probable_tweet_content_line(self, line: str) -> bool:
        import re

        text = str(line or '').strip()
        if not text:
            return False

        compact = text.replace(' ', '')
        lower = text.lower()
        blocked_exact = {
            'follow', 'following', '关注', '正在关注', '订阅', '更多', '显示更多', 'show more',
            'translate post', '翻译帖子', 'view', 'views', '查看', '回复', '转帖', '喜欢',
            'share', 'bookmark', 'image', 'video', 'gif', '广告', 'promoted',
        }
        if lower in blocked_exact or compact in blocked_exact:
            return False
        if lower.startswith('replying to') or text.startswith(('回复给', '回复 @')):
            return False
        if lower.startswith(('promoted', 'ad ')) or 'promoted by' in lower:
            return False
        if text.startswith('@') and len(text.split()) <= 2:
            return False
        if len(text) <= 2 and re.match(r'^[A-Za-z]+$', text):
            return False
        if f"@{self.username.lower()}" in lower and ('·' in text or len(text.splitlines()) == 1):
            return False
        if len(text) <= 2 and (text.isdigit() or text in {'·', '…'}):
            return False
        if text.replace(' ', '').replace(',', '').replace('.', '').isdigit():
            return False

        metric_pattern = r'^[\d,.]+([KMBkmb万亿])?$'
        date_pattern = r'^(\d{1,4}[年/-]\d{1,2}|\d{1,2}[月/-]\d{1,2}|\d{1,2}:\d{2})'
        if re.match(metric_pattern, text) or re.match(date_pattern, text):
            return False
        if re.match(r'^[\d,.]+\s*(回复|转帖|喜欢|views|观看|次观看)$', text, re.I):
            return False
        return True

    def _extract_tweet_text_content(self, element) -> str:
        content_parts = []
        selectors = [
            '[data-testid="tweetText"]',
            'div[lang]:not([data-testid])',
        ]

        for selector in selectors:
            try:
                for node in element.find_elements(By.CSS_SELECTOR, selector):
                    text = self._extract_node_text(node)
                    if text and text not in content_parts:
                        content_parts.append(text)
            except Exception:
                continue

        if content_parts:
            return '\n'.join(content_parts).strip()

        try:
            fallback_text = self.driver.execute_script(
                "return (arguments[0].innerText || arguments[0].textContent || '').trim();",
                element,
            )
        except Exception:
            fallback_text = ''

        filtered_lines = []
        for line in str(fallback_text or '').splitlines():
            normalized = line.strip()
            if self._is_probable_tweet_content_line(normalized) and normalized not in filtered_lines:
                filtered_lines.append(normalized)

        return '\n'.join(filtered_lines[:6]).strip()

    def _merge_media_item(self, existing: Dict, incoming: Dict) -> Dict:
        merged = {**(existing or {})}
        incoming = incoming or {}

        for key in (
            'type', 'url', 'tweet_url', 'entry_webpage_url', 'direct_url', 'thumbnail_url',
            'playlist_item', 'media_index'
        ):
            incoming_value = incoming.get(key)
            if self._has_merge_value(incoming_value) and not self._has_merge_value(merged.get(key)):
                merged[key] = incoming_value

        merged['cdp_urls'] = self._unique_preserve_order([
            *(merged.get('cdp_urls') or []),
            *(incoming.get('cdp_urls') or []),
        ])
        merged['alternative_urls'] = self._unique_preserve_order([
            *(merged.get('alternative_urls') or []),
            *(incoming.get('alternative_urls') or []),
        ])

        if incoming.get('direct_url') and merged.get('direct_url') != incoming.get('direct_url'):
            merged['direct_url'] = incoming.get('direct_url')

        if incoming.get('thumbnail_url') and not merged.get('thumbnail_url'):
            merged['thumbnail_url'] = incoming.get('thumbnail_url')

        return merged

    def _build_media_identity(self, media: Dict, fallback_index: int = 0):
        media_type = media.get('type') or 'unknown'
        media_index = media.get('media_index')
        if media_index is not None:
            return (media_type, media_index)

        return (
            media_type,
            media.get('url') or media.get('tweet_url') or media.get('entry_webpage_url')
            or media.get('direct_url') or fallback_index,
        )

    def _merge_media_lists(self, existing_list: List[Dict], incoming_list: List[Dict]) -> List[Dict]:
        merged = []
        index_by_key = {}

        for media_list in (existing_list or [], incoming_list or []):
            for index, media in enumerate(media_list or []):
                item = dict(media or {})
                key = self._build_media_identity(item, fallback_index=index)
                if key in index_by_key:
                    merged[index_by_key[key]] = self._merge_media_item(merged[index_by_key[key]], item)
                else:
                    index_by_key[key] = len(merged)
                    merged.append(item)

        return merged

    def _merge_tweet_data(self, existing: Dict, incoming: Dict, tab_name: str) -> Dict:
        merged = {**(existing or {})}
        incoming = incoming or {}

        existing_content = str(merged.get('content') or '').strip()
        incoming_content = str(incoming.get('content') or '').strip()
        if incoming_content and (not existing_content or len(incoming_content) > len(existing_content)):
            merged['content'] = incoming_content
            if tab_name == '所有内容/Posts':
                merged['tab_source'] = tab_name

        for key in ('date', 'url', 'author_username', 'author_avatar_url', 'user', 'reply_context'):
            if incoming.get(key) and not merged.get(key):
                merged[key] = incoming.get(key)

        merged['is_reply'] = bool(merged.get('is_reply') or incoming.get('is_reply'))

        for key in ('likes', 'retweets', 'replies'):
            merged[key] = max(int(merged.get(key) or 0), int(incoming.get(key) or 0))

        merged['videos'] = self._merge_media_lists(merged.get('videos') or [], incoming.get('videos') or [])
        merged['photos'] = self._merge_media_lists(merged.get('photos') or [], incoming.get('photos') or [])
        merged['media'] = list(merged['videos']) + list(merged['photos'])

        tab_sources = merged.get('tab_sources') or []
        if merged.get('tab_source') and merged['tab_source'] not in tab_sources:
            tab_sources.append(merged['tab_source'])
        if tab_name and tab_name not in tab_sources:
            tab_sources.append(tab_name)
        if incoming.get('tab_source') and incoming['tab_source'] not in tab_sources:
            tab_sources.append(incoming['tab_source'])
        merged['tab_sources'] = tab_sources

        return merged

    def scrape_user_tweets(self, max_tweets=None, progress_callback=None):
        """爬取推文"""
        if max_tweets is None:
            max_tweets = 999999

        if not self._init_driver():
            raise Exception("浏览器初始化失败，请确保已安装Chrome和ChromeDriver")

        try:
            self._check_for_stop()
            print(f"开始使用Selenium爬取用户 @{self.username} 的推文...")
            print(f"🎭 User-Agent: {self.user_agent[:50]}...")
            behavior_profile = getattr(self, 'behavior_profile', {})
            behavior_label = behavior_profile.get('label') or getattr(self, 'behavior_mode', 'balanced')
            print(f"🧭 抓取行为模式: {behavior_label}")

            if self.twitter_login or self._get_cookie_file():
                self._take_screenshot("开始登录前")
                self._login_twitter()
                self._take_screenshot("登录完成后")
            else:
                print("ℹ️ 未配置账号密码或 Cookie，将以游客模式访问")

            if not self._profile_initialized:
                print("正在初始化用户主页...")
                if not self._ensure_on_target_profile(tab_type="posts"):
                    print(f"⚠️ 未能确认在 @{self.username} 的主页，尝试直接访问...")
                    try:
                        self.driver.get(f"https://twitter.com/{self.username}")
                        self._random_delay(4, 6)
                        self._ensure_on_target_profile(tab_type="posts")
                    except Exception:
                        pass

                self._dismiss_profile_sensitive_overlay()
                self._dismiss_generic_popups()
                self._dismiss_white_modal_overlay()
                self._click_all_sensitive_media_overlays(verbose=True)
                if self._report_blocking_popup_if_any("主页初始化"):
                    self._dismiss_profile_sensitive_overlay(max_attempts=5)
                    self._dismiss_generic_popups(check_url_after=True)
                    self._dismiss_white_modal_overlay()
                    self._click_all_sensitive_media_overlays(verbose=True)
                self._profile_initialized = True
                print("✅ 主页初始化完成")

            tabs_to_scrape = [
                ('posts', '所有内容/Posts'),
                ('media', '照片/Media'),
                ('videos', '视频/Videos'),
            ]

            total_tabs = len(tabs_to_scrape)
            for index, (tab_type, tab_name) in enumerate(tabs_to_scrape):
                self._check_for_stop()

                remaining_total = max_tweets - len(self.tweets_data)
                if remaining_total <= 0:
                    print(f"✅ 已达到总爬取上限 {max_tweets} 条，停止后续标签")
                    break

                remaining_tabs = total_tabs - index
                if max_tweets >= 999999:
                    tab_limit = remaining_total
                else:
                    tab_limit = max(1, (remaining_total + remaining_tabs - 1) // remaining_tabs)

                print(f"\n{'='*60}")
                print(f"开始爬取 {tab_name} 标签")
                print(f"{'='*60}")

                if not self._ensure_on_target_profile(tab_type=tab_type):
                    print(f"⚠️ 切换到 {tab_name} 标签失败，跳过")
                    continue

                self._dismiss_profile_sensitive_overlay()
                self._dismiss_generic_popups()
                self._dismiss_white_modal_overlay()
                self._click_all_sensitive_media_overlays(verbose=False)
                if self._report_blocking_popup_if_any(f"{tab_name} 标签切换后"):
                    self._dismiss_profile_sensitive_overlay(max_attempts=5)
                    self._dismiss_generic_popups(check_url_after=False)
                    self._dismiss_white_modal_overlay()
                    self._click_all_sensitive_media_overlays(verbose=True)

                self._scrape_current_tab(tab_limit, max_tweets, progress_callback, tab_name)

            self._print_final_summary()
            return self.tweets_data

        finally:
            if self.driver:
                self.driver.quit()

    def _scrape_current_tab(self, tab_limit, total_limit, progress_callback, tab_name: str):
        """爬取当前标签的推文"""
        print(f"开始爬取 {tab_name} 的内容...")

        initial_count = len(self.tweets_data)

        try:
            os.makedirs('debug', exist_ok=True)
            with open(f'debug/{self.username}_{tab_name}_page.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print(f"📄 页面HTML已保存: debug/{self.username}_{tab_name}_page.html")
        except Exception:
            pass

        last_height = self.driver.execute_script("return document.body.scrollHeight")
        tweets_collected_in_tab = 0
        no_new_tweets_count = 0
        same_height_rounds = 0

        tab_max = tab_limit if tab_limit else 999999

        while tweets_collected_in_tab < tab_max and len(self.tweets_data) < total_limit:
            self._check_for_stop()

            if tweets_collected_in_tab % 10 == 0:
                self._dismiss_generic_popups()
                self._dismiss_white_modal_overlay()
                self._report_blocking_popup_if_any(f"{tab_name} 抓取中")
            self._click_all_sensitive_media_overlays(verbose=False)

            if tweets_collected_in_tab % 5 == 0:
                self._take_screenshot(f"{tab_name}: 已爬取 {tweets_collected_in_tab} 条")

            tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            newly_collected_this_round = 0

            for tweet_elem in tweet_elements:
                self._check_for_stop()
                if tweets_collected_in_tab >= tab_max or len(self.tweets_data) >= total_limit:
                    break

                try:
                    preview = self._peek_tweet_identity(tweet_elem)
                    preview_id = preview.get('id')
                    existing_sources = self._tweet_sources_by_id.get(preview_id, set()) if preview_id else set()
                    if preview_id and preview_id in self._seen_tweet_ids and tab_name in existing_sources:
                        continue

                    author = self._get_tweet_author_username(tweet_elem).lower()
                    if author and author != self.username.lower():
                        continue

                    self._click_sensitive_overlay_in_tweet(tweet_elem)
                    if self._tweet_element_may_have_video(tweet_elem):
                        self._click_video_to_load(tweet_elem)

                    tweet_data = self._extract_tweet_from_element(tweet_elem, preview=preview)
                    if not tweet_data and preview_id:
                        refound_elem = self._find_tweet_element_by_id(preview_id)
                        if refound_elem is not None:
                            self._click_sensitive_overlay_in_tweet(refound_elem)
                            if self._tweet_element_may_have_video(refound_elem):
                                self._click_video_to_load(refound_elem)
                            tweet_data = self._extract_tweet_from_element(refound_elem, preview=preview)
                            if not author:
                                author = self._get_tweet_author_username(refound_elem).lower()

                    if tweet_data:
                        tweet_id = tweet_data.get('id') or preview_id
                        if not tweet_id:
                            continue
                        if tweet_id in self._seen_tweet_ids:
                            existing_index = self._tweet_index_by_id.get(tweet_id)
                            if existing_index is None:
                                continue

                            tweet_data['id'] = tweet_id
                            tweet_data['author_username'] = author or self.username
                            tweet_data['author_avatar_url'] = tweet_data.get('author_avatar_url') or self._extract_tweet_author_avatar_url(tweet_elem)
                            tweet_data['tab_source'] = tab_name
                            self.tweets_data[existing_index] = self._merge_tweet_data(
                                self.tweets_data[existing_index],
                                tweet_data,
                                tab_name,
                            )
                            self._tweet_sources_by_id.setdefault(tweet_id, set()).add(tab_name)
                            if str(tweet_data.get('content') or '').strip():
                                print(f"  ♻️ [{tab_name}] 已补全重复推文正文: {tweet_id}")
                            continue

                        tweet_data['id'] = tweet_id
                        self._seen_tweet_ids.add(tweet_id)
                        tweet_data['author_username'] = author or self.username
                        tweet_data['author_avatar_url'] = tweet_data.get('author_avatar_url') or self._extract_tweet_author_avatar_url(tweet_elem)
                        tweet_data['tab_source'] = tab_name
                        tweet_data['tab_sources'] = [tab_name]
                        self._tweet_index_by_id[tweet_id] = len(self.tweets_data)
                        self._tweet_sources_by_id.setdefault(tweet_id, set()).add(tab_name)
                        self.tweets_data.append(tweet_data)
                        tweets_collected_in_tab += 1
                        newly_collected_this_round += 1

                        total_collected = len(self.tweets_data)
                        if tweet_data.get('videos'):
                            print(f"  ✅ [{tab_name}] 推文 #{total_collected} 包含 {len(tweet_data['videos'])} 个视频")
                        if tweet_data.get('photos'):
                            print(f"  ✅ [{tab_name}] 推文 #{total_collected} 包含 {len(tweet_data['photos'])} 张照片")

                        if progress_callback:
                            progress_callback(total_collected, total_limit)
                except Exception as e:
                    if self._is_task_stop_exception(e):
                        raise
                    print(f"提取推文失败: {e}")
                    continue

            if tweets_collected_in_tab >= tab_max or len(self.tweets_data) >= total_limit:
                break

            behavior_profile = getattr(self, 'behavior_profile', {})
            scroll_min, scroll_max = behavior_profile.get('scroll_steps', (2, 4))
            delay_min, delay_max = behavior_profile.get('delay_range', (2, 4))
            same_height_limit = behavior_profile.get('same_height_limit', 4)
            same_height_with_no_new_limit = behavior_profile.get('same_height_with_no_new_limit', 2)
            no_new_limit = behavior_profile.get('no_new_limit', 5)

            for _ in range(random.randint(scroll_min, scroll_max)):
                self._human_like_scroll()

            self._random_delay(delay_min, delay_max)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if newly_collected_this_round == 0:
                no_new_tweets_count += 1
            else:
                no_new_tweets_count = 0

            if new_height == last_height:
                same_height_rounds += 1
                if same_height_rounds >= same_height_limit or (
                    same_height_rounds >= same_height_with_no_new_limit
                    and no_new_tweets_count >= no_new_limit
                ):
                    print(f"[{tab_name}] 已到达页面底部")
                    break
            else:
                same_height_rounds = 0
                last_height = new_height

            if tweets_collected_in_tab % 10 == 0:
                print(f"[{tab_name}] 已爬取 {tweets_collected_in_tab} 条推文...")

        tab_collected = len(self.tweets_data) - initial_count
        print(f"\n✅ {tab_name} 标签爬取完成！共 {tab_collected} 条推文")

    def _print_final_summary(self):
        """打印最终统计信息"""
        total_videos = sum(len(t.get('videos', [])) for t in self.tweets_data)
        total_photos = sum(len(t.get('photos', [])) for t in self.tweets_data)

        from collections import Counter
        tab_stats = Counter(t.get('tab_source', 'unknown') for t in self.tweets_data)

        print(f"\n{'='*60}")
        print("✅ 全部爬取完成！")
        print(f"{'='*60}")
        print(f"📝 推文总数: {len(self.tweets_data)}")
        print(f"📹 视频总数: {total_videos}")
        print(f"📸 照片总数: {total_photos}")
        print("\n按标签统计:")
        for tab, count in tab_stats.items():
            print(f"  - {tab}: {count} 条")
        print(f"{'='*60}")

    def _extract_tweet_from_element(self, element, preview: Optional[Dict[str, str]] = None) -> Dict:
        """从网页元素提取推文数据"""
        try:
            self._check_for_stop()
            preview = preview or {}

            content = self._extract_tweet_text_content(element)

            tweet_url = preview.get('url', '')
            tweet_id = preview.get('id', '')
            date = ''
            try:
                time_elem = element.find_element(By.TAG_NAME, 'time')
                date = time_elem.get_attribute('datetime') or ''
                try:
                    time_link = time_elem.find_element(By.XPATH, './ancestor::a[1]')
                    href = (time_link.get_attribute('href') or '').strip()
                    candidate_id = self._extract_tweet_id_from_url(href)
                    if candidate_id:
                        tweet_id = candidate_id
                        tweet_url = self._normalize_tweet_url(href)
                except Exception:
                    pass
            except Exception:
                pass

            if not tweet_id:
                link_candidates = element.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
                for link_elem in link_candidates:
                    href = (link_elem.get_attribute('href') or '').strip()
                    candidate_id = self._extract_tweet_id_from_url(href)
                    if candidate_id:
                        tweet_id = candidate_id
                        tweet_url = self._normalize_tweet_url(href)
                        break

            if not tweet_id:
                return None

            likes = self._extract_action_metric(
                element,
                ['[data-testid="like"]', '[data-testid="unlike"]']
            )
            retweets = self._extract_action_metric(
                element,
                ['[data-testid="retweet"]', '[data-testid="unretweet"]', '[data-testid="repost"]', '[data-testid="unrepost"]']
            )
            replies = self._extract_action_metric(
                element,
                ['[data-testid="reply"]']
            )

            videos = []
            photos = []
            is_reply = False
            reply_context = None

            try:
                reply_candidates = []
                xpath_candidates = [
                    './/*[contains(text(), "Replying to")]',
                    './/*[contains(text(), "回复给")]',
                    './/*[contains(text(), "回复 @")]'
                ]

                for xpath in xpath_candidates:
                    for node in element.find_elements(By.XPATH, xpath):
                        text = (node.text or '').strip()
                        if text and text not in reply_candidates:
                            reply_candidates.append(text)

                if not reply_candidates:
                    full_text = (element.text or '').splitlines()
                    for line in full_text:
                        normalized = line.strip()
                        if normalized.startswith('Replying to') or normalized.startswith('回复给') or normalized.startswith('回复 @'):
                            reply_candidates.append(normalized)
                            break

                if not reply_candidates and content.startswith('@'):
                    reply_candidates.append(content.splitlines()[0][:120])

                if reply_candidates:
                    is_reply = True
                    reply_context = reply_candidates[0]
            except Exception:
                pass

            try:
                media_tweet_url = tweet_url
                if not media_tweet_url:
                    tweet_links = element.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
                    if tweet_links:
                        media_tweet_url = self._normalize_tweet_url(tweet_links[0].get_attribute('href'))

                has_video = False
                video_elements = []

                video_elements = element.find_elements(By.TAG_NAME, 'video')
                if video_elements:
                    has_video = True
                    print(f"  🎬 检测到视频 (发现 {len(video_elements)} 个video标签)")

                if not has_video:
                    video_players = element.find_elements(By.CSS_SELECTOR, '[data-testid="videoPlayer"]')
                    if video_players:
                        has_video = True
                        try:
                            video_elements = video_players[0].find_elements(By.TAG_NAME, 'video')
                        except Exception:
                            pass
                        print("  🎬 检测到视频 (发现videoPlayer)")

                if not has_video:
                    video_containers = element.find_elements(By.CSS_SELECTOR, 'div[aria-label*="Video"], div[aria-label*="视频"]')
                    if video_containers:
                        has_video = True
                        try:
                            video_elements = video_containers[0].find_elements(By.TAG_NAME, 'video')
                        except Exception:
                            pass
                        print("  🎬 检测到视频 (发现视频容器)")

                if not has_video:
                    play_buttons = element.find_elements(By.CSS_SELECTOR, '[aria-label*="Play"], [aria-label*="播放"]')
                    if play_buttons:
                        has_video = True
                        print("  🎬 检测到视频 (发现播放按钮)")

                cdp_video_urls = []
                if has_video and len(video_elements) > 0:
                    print("  🔍 尝试用CDP捕获真实视频URL...")
                    cdp_video_urls = self._capture_video_urls_with_cdp(element, video_elements)
                    if cdp_video_urls:
                        print(f"  ✅ CDP捕获到 {len(cdp_video_urls)} 个视频URL")
                thumbnail_url = self._extract_video_thumbnail_url(element, video_elements)

                if has_video and media_tweet_url:
                    video_data = {
                        'tweet_url': media_tweet_url,
                        'type': 'video_ytdlp',
                        'media_index': 0,
                        'playlist_item': 1,
                        'cdp_urls': cdp_video_urls,
                        'thumbnail_url': thumbnail_url or None
                    }

                    if cdp_video_urls:
                        video_data['direct_url'] = cdp_video_urls[0]
                        video_data['alternative_urls'] = cdp_video_urls[1:]

                    videos.append(video_data)
                    print(f"  ✅ 已记录视频推文: {media_tweet_url}")
                    if cdp_video_urls:
                        print(f"     └─ 备用直连URL: {cdp_video_urls[0][:80]}...")
                elif has_video and not media_tweet_url:
                    print("  ⚠️ 检测到视频但未找到推文URL")

            except Exception as e:
                print(f"  ⚠️ 视频检测失败: {e}")

            try:
                img_elements = []

                method1 = element.find_elements(By.CSS_SELECTOR, 'img[src*="pbs.twimg.com/media"]')
                print(f"  🔍 方法1找到 {len(method1)} 个媒体图片")
                img_elements.extend(method1)

                if not img_elements:
                    method2 = element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
                    print(f"  🔍 方法2找到 {len(method2)} 个tweetPhoto图片")
                    img_elements.extend(method2)

                if not img_elements:
                    all_imgs = element.find_elements(By.TAG_NAME, 'img')
                    print(f"  🔍 方法3: 推文内共有 {len(all_imgs)} 个img标签")
                    for index, img in enumerate(all_imgs):
                        src = img.get_attribute('src') or ''
                        alt = img.get_attribute('alt') or ''
                        if 'pbs.twimg.com/media' in src:
                            img_elements.append(img)
                            print(f"    ✓ img[{index}]是媒体图片: {src[:60]}...")
                        elif 'profile_images' in src:
                            print(f"    ✗ img[{index}]是头像，跳过")
                        else:
                            print(f"    ? img[{index}]: src={src[:60]}... alt={alt[:30]}")

                seen_urls = set()
                unique_imgs = []
                for img in img_elements:
                    url = img.get_attribute('src')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        unique_imgs.append(img)
                img_elements = unique_imgs

                for img in img_elements:
                    img_url = img.get_attribute('src')
                    if img_url and 'profile_images' not in img_url and 'pbs.twimg.com' in img_url:
                        try:
                            parsed = urlparse(img_url)
                            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                            qs = parse_qs(parsed.query or '')
                            fmt = qs.get('format', [None])[0]
                            if not fmt:
                                path_ext = os.path.splitext(os.path.basename(parsed.path))[1].lstrip('.')
                                fmt = path_ext if path_ext else 'jpg'
                            img_url = f"{base_url}?format={fmt}&name=orig"
                        except Exception:
                            if '?' in img_url:
                                img_url = img_url.split('?')[0] + '?name=orig'
                            else:
                                img_url = img_url + '?name=orig'

                        photos.append({
                            'url': img_url,
                            'type': 'photo'
                        })
                        print(f"  📸 发现图片: {img_url[:60]}...")
            except Exception as e:
                print(f"提取媒体失败: {e}")

            return {
                'id': tweet_id,
                'url': tweet_url,
                'date': date,
                'content': content,
                'user': self.username,
                'author_avatar_url': self._extract_tweet_author_avatar_url(element),
                'likes': likes,
                'retweets': retweets,
                'replies': replies,
                'is_reply': is_reply,
                'reply_context': reply_context,
                'videos': videos,
                'photos': photos,
                'media': videos + photos
            }

        except Exception as e:
            if self._is_task_stop_exception(e):
                raise
            return None

    def get_videos(self) -> List[Dict]:
        """获取所有包含视频的推文"""
        videos = [tweet for tweet in self.tweets_data if tweet['videos']]
        print(f"📹 找到 {len(videos)} 条包含视频的推文")
        return videos

    def get_photos(self) -> List[Dict]:
        """获取所有包含照片的推文"""
        photos = [tweet for tweet in self.tweets_data if tweet['photos']]
        print(f"📸 找到 {len(photos)} 条包含照片的推文")
        return photos

    def get_replies(self) -> List[Dict]:
        """获取所有回复推文"""
        return [tweet for tweet in self.tweets_data if tweet['is_reply']]

    def save_raw_data(self, filename="tweets_raw_selenium.json", output_dir=None):
        """保存原始数据"""
        target_dir = output_dir or config.OUTPUT_DIR
        os.makedirs(target_dir, exist_ok=True)
        filepath = os.path.join(target_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.tweets_data, f, ensure_ascii=False, indent=2)
        print(f"原始数据已保存至: {filepath}")
