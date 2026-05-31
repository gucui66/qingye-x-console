"""
Selenium 爬虫的主页定位、弹窗和资料页交互
"""
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class SeleniumProfileMixin:
    """主页定位和弹窗处理"""

    @staticmethod
    def _normalize_dialog_text(text: str) -> str:
        return ' '.join((text or '').split()).strip()

    def _detect_blocking_popup_state(self):
        """检测仍然挡住页面的弹窗，方便日志和截图定位。"""
        selectors = [
            '[role="dialog"]',
            '[aria-modal="true"]',
            '[data-testid="sheetDialog"]',
            '[data-testid="confirmationSheetDialog"]',
            '[data-testid="modal"]',
        ]
        keywords = [
            'view profile', 'yes, view profile', 'sensitive', 'sensitive content',
            'log in', 'sign in', 'create account', 'notifications', 'turn on',
            '查看资料', '查看主页', '敏感', '登录', '注册', '通知', '开启'
        ]
        blockers = []

        try:
            for selector in selectors:
                for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    try:
                        if not element.is_displayed():
                            continue
                        text = self._normalize_dialog_text(element.text)
                        if not text:
                            continue
                        if any(keyword in text.lower() for keyword in keywords):
                            blockers.append(text[:240])
                    except Exception:
                        continue
            deduped = []
            seen = set()
            for item in blockers:
                key = item.lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
            return deduped[:3]
        except Exception:
            return []

    def _report_blocking_popup_if_any(self, stage: str):
        blockers = self._detect_blocking_popup_state()
        if not blockers:
            return False

        print(f"   ⚠️ 检测到仍在阻挡页面的弹窗 [{stage}]")
        for index, text in enumerate(blockers, start=1):
            print(f"      弹窗#{index}: {text}")
        self._take_screenshot(f"检测到阻断弹窗 - {stage}")
        return True

    def _dismiss_white_modal_overlay(self):
        """专门处理截图中这种白底弹层 + 左上角 X 的模态框。"""
        try:
            dialogs = self.driver.find_elements(By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], [data-testid="sheetDialog"]')
        except Exception:
            dialogs = []

        for dialog in dialogs:
            try:
                if not dialog.is_displayed():
                    continue

                rect = dialog.rect or {}
                if rect.get('width', 0) < 250 or rect.get('height', 0) < 150:
                    continue

                close_candidates = []
                try:
                    close_candidates.extend(dialog.find_elements(By.XPATH, './/button'))
                    close_candidates.extend(dialog.find_elements(By.XPATH, './/div[@role="button"]'))
                    close_candidates.extend(dialog.find_elements(By.XPATH, './/*[normalize-space(text())="×" or normalize-space(text())="✕" or normalize-space(text())="X"]'))
                except Exception:
                    pass

                best_candidate = None
                best_score = None
                for candidate in close_candidates:
                    try:
                        if not candidate.is_displayed():
                            continue
                        cand_rect = candidate.rect or {}
                        score = (
                            abs((cand_rect.get('y', 0) - rect.get('y', 0))),
                            abs((cand_rect.get('x', 0) - rect.get('x', 0))),
                            cand_rect.get('width', 0),
                        )
                        if best_score is None or score < best_score:
                            best_candidate = candidate
                            best_score = score
                    except Exception:
                        continue

                if best_candidate is not None:
                    try:
                        best_candidate.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", best_candidate)
                    self._random_delay(0.6, 1.2)
                    print("   ✓ 已关闭白色模态弹窗（左上角关闭按钮）")
                    self._take_screenshot("已关闭白色模态弹窗")
                    return True

                try:
                    body = self.driver.find_element(By.TAG_NAME, 'body')
                    body.send_keys(Keys.ESCAPE)
                    self._random_delay(0.4, 0.8)
                    if not dialog.is_displayed():
                        print("   ✓ 已通过 Esc 关闭白色模态弹窗")
                        self._take_screenshot("已通过Esc关闭白色模态弹窗")
                        return True
                except Exception:
                    pass
            except Exception:
                continue

        return False

    def _ensure_on_target_profile(self, tab_type: str = "posts") -> bool:
        """确保当前在目标用户主页，并切换到指定标签"""
        try:
            target_variants = [
                f"https://twitter.com/{self.username}",
                f"https://x.com/{self.username}"
            ]

            for url in target_variants:
                self.driver.get(url)
                self._random_delay(3, 5)

                profile_ok = False
                try:
                    header = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="UserName"]'))
                    )
                    header_text = header.text or ''
                    if ('@' + self.username.lower()) in header_text.lower():
                        profile_ok = True
                except Exception:
                    profile_ok = False

                if not profile_ok:
                    current_url = (self.driver.current_url or '').lower()
                    title = (self.driver.title or '').lower()
                    if self.username.lower() in current_url and '/home' not in current_url:
                        profile_ok = True
                    if ('@' + self.username.lower()) in title:
                        profile_ok = True

                if profile_ok:
                    tab_texts_map = {
                        'media': {'media', '媒体', 'photos', '照片'},
                        'videos': {'videos', '视频'},
                        'posts': {'posts', '推文', 'tweets', '帖文'}
                    }
                    tab_texts = tab_texts_map.get(tab_type, tab_texts_map['posts'])

                    try:
                        tabs = self.driver.find_elements(By.CSS_SELECTOR, '[role="tab"]')
                        clicked = False
                        for tab in tabs:
                            try:
                                label = (tab.text or '').strip().lower()
                                if label in tab_texts:
                                    self.driver.execute_script(
                                        "arguments[0].scrollIntoView({block: 'center'});",
                                        tab
                                    )
                                    self._random_delay(0.4, 0.8)
                                    try:
                                        tab.click()
                                    except Exception:
                                        self.driver.execute_script("arguments[0].click();", tab)
                                    clicked = True
                                    print(f"   ✓ 已切换到 {tab_type} 标签")
                                    break
                            except Exception:
                                continue
                        if clicked:
                            self._random_delay(2, 3)
                        else:
                            print(f"   ⚠️ 未找到 {tab_type} 标签，使用默认标签")
                    except Exception:
                        pass

                    self._take_screenshot(f"已定位到 @{self.username} 主页 - {tab_type}标签")
                    return True

            return False
        except Exception:
            return False

    def _dismiss_profile_sensitive_overlay(self, max_attempts: int = 3):
        """关闭进入用户主页时的敏感内容覆盖提示"""
        try:
            attempts = 0
            while attempts < max_attempts:
                dismissed = False
                candidates = [
                    'View profile', 'Yes, view profile', 'Go to profile', 'Enter', 'View',
                    '查看资料', '查看个人资料', '查看主页', '进入', '是，查看', '查看'
                ]
                for selector in ['button', 'div[role="button"]', '[data-testid="confirmationSheetConfirm"]']:
                    try:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    except Exception:
                        buttons = []

                    for btn in buttons:
                        try:
                            if not btn.is_displayed():
                                continue
                            btn_text = (btn.text or '').strip().lower()
                            if not btn_text:
                                continue
                            if any(text.lower() in btn_text for text in candidates):
                                try:
                                    btn.click()
                                except Exception:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                dismissed = True
                                print(f"   ✓ 已关闭主页敏感内容覆盖层: {btn_text}")
                                break
                        except Exception:
                            continue
                    if dismissed:
                        break

                if not dismissed:
                    try:
                        confirm_btns = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            '[data-testid="confirmationSheetConfirm"]'
                        )
                        for button in confirm_btns:
                            if button.is_displayed():
                                try:
                                    button.click()
                                except Exception:
                                    self.driver.execute_script("arguments[0].click();", button)
                                dismissed = True
                                print("   ✓ 已点击主页确认按钮")
                                break
                    except Exception:
                        pass

                if dismissed:
                    self._random_delay(1.0, 1.8)
                    self._take_screenshot("已关闭主页敏感内容覆盖层")
                    return

                attempts += 1
                self._random_delay(0.8, 1.5)
        except Exception:
            pass

    def _dismiss_generic_popups(self, check_url_after: bool = True):
        """关闭 Twitter 的通用弹窗"""
        if self._popup_dismissed_count >= self._max_popup_attempts:
            return

        try:
            url_before = self.driver.current_url if check_url_after else None

            clicked = False
            try:
                close_selectors = [
                    '[aria-label="Close"]',
                    '[aria-label="关闭"]',
                    '[data-testid="app-bar-close"]',
                    '[data-testid="sheetDialog"] [aria-label*="Close"]',
                    'button[aria-label*="Close"]',
                    'div[role="button"][aria-label*="Close"]',
                    'svg path[d*="M10.59"]',
                ]

                for selector in close_selectors:
                    try:
                        close_btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in close_btns:
                            if btn.is_displayed():
                                try:
                                    self.driver.execute_script(
                                        "arguments[0].scrollIntoView({block: 'center'});",
                                        btn
                                    )
                                    time.sleep(0.2)
                                    btn.click()
                                    clicked = True
                                    self._popup_dismissed_count += 1
                                    print(f"   ✓ 已点击X关闭按钮 (第{self._popup_dismissed_count}次)")
                                    break
                                except Exception:
                                    pass
                        if clicked:
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            if not clicked:
                dismiss_texts = [
                    'Dismiss', 'Close', 'OK', 'Got it', 'Not now', 'Skip', 'Maybe later',
                    '关闭', '知道了', '确定', '稍后', '跳过', '暂不', '取消'
                ]

                for text in dismiss_texts:
                    try:
                        xpaths = [
                            f'//div[@role="button" and contains(., "{text}")]',
                            f'//button[contains(., "{text}")]',
                            f'//span[normalize-space(text())="{text}"]/..',
                        ]
                        for xpath in xpaths:
                            try:
                                btns = self.driver.find_elements(By.XPATH, xpath)
                                for btn in btns:
                                    if btn.is_displayed():
                                        self.driver.execute_script(
                                            "arguments[0].scrollIntoView({block: 'center'});",
                                            btn
                                        )
                                        time.sleep(0.3)
                                        try:
                                            btn.click()
                                        except Exception:
                                            self.driver.execute_script("arguments[0].click();", btn)
                                        clicked = True
                                        self._popup_dismissed_count += 1
                                        print(f"   ✓ 已关闭弹窗: {text} (第{self._popup_dismissed_count}次)")
                                        break
                                if clicked:
                                    break
                            except Exception:
                                continue
                        if clicked:
                            break
                    except Exception:
                        continue

            if clicked:
                self._random_delay(0.8, 1.5)
                self._take_screenshot("已关闭通用弹窗")

                if check_url_after and url_before and not self._profile_initialized:
                    url_after = self.driver.current_url
                    if self.username.lower() not in url_after.lower() or '/home' in url_after.lower():
                        print(f"   ⚠️ 检测到页面跳转: {url_after}")
                        print("   正在返回目标用户主页...")
                        self.driver.get(f"https://twitter.com/{self.username}")
                        self._random_delay(2, 3)
                        self._take_screenshot("已返回目标用户主页")
                        print(f"   ✓ 已返回 @{self.username} 主页")
                        self._profile_initialized = True
            elif self._dismiss_white_modal_overlay():
                pass
            else:
                self._report_blocking_popup_if_any("通用弹窗处理后")

        except Exception:
            pass

    def _get_tweet_author_username(self, element) -> str:
        """从推文元素中提取作者用户名"""
        try:
            anchors = element.find_elements(By.CSS_SELECTOR, 'div[data-testid="User-Name"] a[href^="/"]')
            for anchor in anchors:
                href = anchor.get_attribute('href') or ''
                try:
                    if 'twitter.com/' in href:
                        handle = href.split('twitter.com/')[-1].split('/')[0]
                    elif 'x.com/' in href:
                        handle = href.split('x.com/')[-1].split('/')[0]
                    else:
                        path = href
                        if '://' not in path:
                            path = path.lstrip('/')
                        handle = path.split('/')[0]
                    handle = handle.strip()
                    if handle:
                        return handle
                except Exception:
                    continue
        except Exception:
            pass
        return ""

    def _click_sensitive_content_warnings(self, verbose=True):
        """点击所有"敏感内容"警告按钮"""
        try:
            time.sleep(1)

            button_texts = [
                '查看', 'View', '显示', 'Show',
                '查看媒体', 'View media',
                '显示敏感媒体', 'Show sensitive media'
            ]

            clicked_count = 0

            for text in button_texts:
                try:
                    buttons = self.driver.find_elements(By.XPATH, f'//span[contains(text(), "{text}")]/..')
                    for btn in buttons:
                        try:
                            btn.click()
                            clicked_count += 1
                            time.sleep(0.5)
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                sensitive_buttons = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="sensitiveMediaSettings"]')
                for btn in sensitive_buttons:
                    try:
                        btn.click()
                        clicked_count += 1
                        time.sleep(0.5)
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, '[role="button"]')
                for btn in all_buttons:
                    try:
                        btn_text = btn.text.lower()
                        if any(keyword in btn_text for keyword in ['view', 'show', '查看', '显示', 'sensitive', '敏感']):
                            btn.click()
                            clicked_count += 1
                            time.sleep(0.5)
                    except Exception:
                        pass
            except Exception:
                pass

            if clicked_count > 0:
                if verbose:
                    print(f"🔓 已点击 {clicked_count} 个敏感内容警告按钮")
                time.sleep(2)

        except Exception as e:
            if verbose:
                print(f"⚠️ 处理敏感内容警告时出错: {e}")
