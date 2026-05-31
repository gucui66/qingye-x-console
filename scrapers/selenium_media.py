"""
Selenium 爬虫的媒体相关交互
"""
import json
import time

from selenium.webdriver.common.by import By


class SeleniumMediaMixin:
    """视频/图片遮罩与媒体加载逻辑"""

    def _capture_video_urls_with_cdp(self, tweet_element, video_elements):
        """使用 Chrome DevTools Protocol 捕获真实视频 URL"""
        video_urls = []

        try:
            try:
                self.driver.get_log('performance')
            except Exception:
                pass

            played = False

            try:
                play_buttons = tweet_element.find_elements(
                    By.CSS_SELECTOR,
                    '[aria-label*="Play"], [aria-label*="播放"], [data-testid="playButton"]'
                )
                if play_buttons:
                    self.driver.execute_script("arguments[0].click();", play_buttons[0])
                    print("    ✓ 已点击播放按钮")
                    played = True
                    time.sleep(2)
            except Exception as e:
                print(f"    ⚠️ 点击播放失败: {e}")

            if not played and len(video_elements) > 0:
                try:
                    from selenium.webdriver.common.action_chains import ActionChains

                    actions = ActionChains(self.driver)
                    actions.move_to_element(video_elements[0]).perform()
                    time.sleep(1.5)
                    print("    ✓ 已触发鼠标悬停")
                except Exception:
                    pass

            try:
                logs = self.driver.get_log('performance')
                print(f"    📊 获取到 {len(logs)} 条性能日志")

                for log in logs:
                    try:
                        message = json.loads(log['message'])
                        method = message.get('message', {}).get('method', '')

                        if method == 'Network.responseReceived':
                            params = message['message']['params']
                            response = params.get('response', {})
                            url = response.get('url', '')

                            if 'video.twimg.com' in url and ('.mp4' in url or '.m3u8' in url):
                                if 'thumb' not in url and url not in video_urls:
                                    video_urls.append(url)
                                    print(f"    ✅ 捕获视频URL: {url[:80]}...")
                    except Exception:
                        continue
            except Exception as e:
                print(f"    ⚠️ 解析性能日志失败: {e}")

            video_urls.sort(key=len, reverse=True)

        except Exception as e:
            print(f"    ⚠️ CDP捕获失败: {e}")

        return video_urls

    def _click_video_to_load(self, tweet_element):
        """点击视频预览图/播放按钮，确保 video 元素加载"""
        try:
            clicked = False

            existing_videos = tweet_element.find_elements(By.TAG_NAME, 'video')
            if existing_videos:
                print(f"    ℹ️ 已存在 {len(existing_videos)} 个video元素，尝试点击以确保加载完整")

            try:
                play_selectors = [
                    '[aria-label*="Play"]',
                    '[data-testid="playButton"]',
                    '[aria-label*="播放"]',
                    'div[role="button"][aria-label*="video"]',
                    '[aria-label*="Playback"]'
                ]
                for selector in play_selectors:
                    buttons = tweet_element.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        print(f"    🔍 找到 {len(buttons)} 个匹配 '{selector}' 的按钮")
                    for btn in buttons:
                        if btn.is_displayed():
                            try:
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView({block: 'center'});",
                                    btn
                                )
                                time.sleep(0.3)
                                btn.click()
                                clicked = True
                                print(f"    ✓ 已点击播放按钮: {selector}")
                                time.sleep(1.5)
                                break
                            except Exception as e:
                                print(f"    ⚠️ 点击失败: {e}")
                    if clicked:
                        break
            except Exception as e:
                print(f"    ⚠️ 方法1失败: {e}")

            if not clicked:
                try:
                    video_containers = tweet_element.find_elements(
                        By.CSS_SELECTOR,
                        '[data-testid="videoPlayer"], [data-testid="card.layoutLarge.media"]'
                    )
                    if video_containers:
                        print(f"    🔍 找到 {len(video_containers)} 个视频容器")
                    for container in video_containers:
                        if container.is_displayed():
                            try:
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView({block: 'center'});",
                                    container
                                )
                                time.sleep(0.3)
                                self.driver.execute_script("arguments[0].click();", container)
                                clicked = True
                                print("    ✓ 已点击视频容器 (JS)")
                                time.sleep(1.5)
                                break
                            except Exception as e:
                                print(f"    ⚠️ 点击容器失败: {e}")
                except Exception as e:
                    print(f"    ⚠️ 方法2失败: {e}")

            if not clicked:
                try:
                    clickable_divs = tweet_element.find_elements(By.CSS_SELECTOR, 'div[tabindex="0"]')
                    video_divs = []
                    for div in clickable_divs:
                        aria_label = div.get_attribute('aria-label') or ''
                        if 'video' in aria_label.lower() or 'play' in aria_label.lower():
                            video_divs.append((div, aria_label))

                    if video_divs:
                        print(f"    🔍 找到 {len(video_divs)} 个视频相关可点击区域")

                    for div, label in video_divs:
                        try:
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center'});",
                                div
                            )
                            time.sleep(0.3)
                            div.click()
                            clicked = True
                            print(f"    ✓ 已点击视频区域: {label[:50]}")
                            time.sleep(1.5)
                            break
                        except Exception as e:
                            print(f"    ⚠️ 点击失败: {e}")
                except Exception as e:
                    print(f"    ⚠️ 方法3失败: {e}")

            if clicked:
                time.sleep(1)
                new_videos = tweet_element.find_elements(By.TAG_NAME, 'video')
                print(f"    📊 点击后video元素数量: {len(new_videos)}")
            else:
                print("    ⚠️ 未能点击任何视频相关元素")

        except Exception as e:
            print(f"    ❌ _click_video_to_load 异常: {e}")

    def _click_sensitive_overlay_in_tweet(self, tweet_element):
        """点击单条推文内的敏感内容遮罩"""
        try:
            texts = ['查看', '显示', 'View', 'Show', '查看媒体', '显示敏感媒体', 'View media', 'Show sensitive media']
            clicked = False

            for text in texts:
                try:
                    buttons = tweet_element.find_elements(
                        By.XPATH,
                        f'.//span[contains(normalize-space(text()), "{text}")]/..'
                    )
                    for btn in buttons:
                        try:
                            if btn.is_displayed():
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView({block: 'center'});",
                                    btn
                                )
                                time.sleep(0.2)
                                try:
                                    btn.click()
                                except Exception:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                clicked = True
                                time.sleep(0.5)
                                break
                        except Exception:
                            continue
                    if clicked:
                        break
                except Exception:
                    continue

            if clicked:
                time.sleep(1)

        except Exception:
            pass

    def _click_all_sensitive_media_overlays(self, verbose: bool = False):
        """点击页面上所有推文媒体的敏感内容遮罩按钮"""
        try:
            articles = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            total_clicked = 0
            for article in articles:
                try:
                    texts = ['查看', '显示', 'View', 'Show', '查看媒体', '显示敏感媒体', 'View media', 'Show sensitive media']
                    clicked_local = 0
                    for text in texts:
                        try:
                            buttons = article.find_elements(
                                By.XPATH,
                                f'.//span[contains(normalize-space(text()), "{text}")]/..'
                            )
                            for btn in buttons:
                                try:
                                    if btn.is_displayed():
                                        try:
                                            btn.click()
                                        except Exception:
                                            self.driver.execute_script("arguments[0].click();", btn)
                                        clicked_local += 1
                                        total_clicked += 1
                                        time.sleep(0.2)
                                except Exception:
                                    continue
                        except Exception:
                            continue

                    if clicked_local == 0:
                        try:
                            overlays = article.find_elements(
                                By.CSS_SELECTOR,
                                '[aria-label*="View"], [aria-label*="查看"], [aria-label*="显示"]'
                            )
                            for overlay in overlays:
                                try:
                                    if overlay.is_displayed():
                                        try:
                                            overlay.click()
                                        except Exception:
                                            self.driver.execute_script("arguments[0].click();", overlay)
                                        total_clicked += 1
                                        time.sleep(0.2)
                                except Exception:
                                    continue
                        except Exception:
                            pass
                except Exception:
                    continue

            if verbose and total_clicked > 0:
                print(f"🔓 已点击 {total_clicked} 个媒体敏感内容覆盖按钮")
            if total_clicked > 0:
                self._random_delay(1.5, 2.2)
        except Exception:
            pass
