"""
基于Selenium的Twitter爬虫（无需API）
"""
import json
import os
import random
import time

import core.config as config
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scrapers.selenium_browser import SeleniumBrowserMixin
from scrapers.selenium_media import SeleniumMediaMixin
from scrapers.selenium_profile import SeleniumProfileMixin
from scrapers.selenium_scrape import SeleniumScrapeMixin


class SeleniumTwitterScraper(
    SeleniumBrowserMixin,
    SeleniumProfileMixin,
    SeleniumMediaMixin,
    SeleniumScrapeMixin,
):
    """使用Selenium的Twitter爬虫（无需API - 增强反反爬机制）"""

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    ]

    BEHAVIOR_PROFILES = {
        'balanced': {
            'label': '均衡',
            'scroll_steps': (2, 4),
            'delay_range': (2, 4),
            'same_height_limit': 4,
            'same_height_with_no_new_limit': 2,
            'no_new_limit': 5,
        },
        'stable': {
            'label': '稳定',
            'scroll_steps': (3, 5),
            'delay_range': (3, 5),
            'same_height_limit': 7,
            'same_height_with_no_new_limit': 3,
            'no_new_limit': 8,
        },
        'human': {
            'label': '拟人',
            'scroll_steps': (1, 4),
            'delay_range': (4, 8),
            'same_height_limit': 5,
            'same_height_with_no_new_limit': 3,
            'no_new_limit': 6,
        },
    }

    def __init__(
        self,
        username: str,
        twitter_login: dict = None,
        headless: bool = True,
        task_id: str = None,
        stop_callback=None,
        behavior_mode: str = 'balanced',
    ):
        self.username = username
        self.tweets_data = []
        self.driver = None
        self.user_agent = random.choice(self.USER_AGENTS)
        self.twitter_login = twitter_login
        self.headless = headless
        self.task_id = task_id or f"task_{int(time.time())}"
        self.screenshot_count = 0
        self.stop_callback = stop_callback

        self._popup_dismissed_count = 0
        self._max_popup_attempts = 2
        self._profile_initialized = False
        self._seen_tweet_ids = set()
        self._tweet_index_by_id = {}
        self._tweet_sources_by_id = {}
        self.behavior_mode = behavior_mode if behavior_mode in self.BEHAVIOR_PROFILES else 'balanced'
        self.behavior_profile = self.BEHAVIOR_PROFILES[self.behavior_mode]

    def _login_with_cookies(self):
        """使用Cookie登录（最轻量方案）"""
        cookie_file = self._get_cookie_file()

        try:
            import os

            if not cookie_file:
                print("⚠️ 未找到可用的 Cookie 文件")
                return False

            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            print(f"🍪 使用Cookie登录: {cookie_file}")

            self.driver.get("https://x.com")
            time.sleep(2)

            success_count = 0
            for cookie in cookies:
                try:
                    clean_cookie = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'path': cookie.get('path', '/'),
                    }

                    domain = cookie['domain']
                    if domain.startswith('.'):
                        domain = domain[1:]
                    clean_cookie['domain'] = domain

                    if 'expirationDate' in cookie:
                        expiry = int(cookie['expirationDate'])
                        if expiry > time.time():
                            clean_cookie['expiry'] = expiry

                    if 'secure' in cookie:
                        clean_cookie['secure'] = cookie['secure']
                    if 'httpOnly' in cookie:
                        clean_cookie['httpOnly'] = cookie['httpOnly']

                    if cookie.get('sameSite'):
                        same_site = cookie['sameSite']
                        if same_site == 'no_restriction':
                            clean_cookie['sameSite'] = 'None'
                        elif same_site in ['lax', 'strict']:
                            clean_cookie['sameSite'] = same_site.capitalize()

                    self.driver.add_cookie(clean_cookie)
                    success_count += 1
                except Exception as e:
                    print(f"   ⚠️ 添加Cookie失败: {cookie.get('name')} - {str(e)[:50]}")

            print(f"   ✓ Cookie已加载 ({success_count}/{len(cookies)} 成功)")

            self.driver.refresh()
            time.sleep(3)

            current_url = self.driver.current_url
            print(f"   当前URL: {current_url}")

            logged_in = False
            if "home" in current_url or "timeline" in current_url:
                logged_in = True
                print("   ✓ URL验证：已登录")

            if not logged_in:
                try:
                    page_source = self.driver.page_source.lower()
                    if "log out" in page_source or "settings" in page_source:
                        logged_in = True
                        print("   ✓ 页面内容验证：已登录")
                except Exception:
                    pass

            if logged_in:
                print("✅ Cookie登录成功！")
                self._take_screenshot("Cookie登录成功")

                target_url = f"https://twitter.com/{self.username}"
                print(f"   正在跳转到目标用户主页: {target_url}")
                self.driver.get(target_url)
                self._random_delay(3, 5)
                self._take_screenshot(f"已跳转到 @{self.username} 主页")
                print(f"✅ 已成功跳转到 @{self.username} 主页")
                return True

            print("⚠️ Cookie可能已过期，请重新获取")
            self._take_screenshot("Cookie登录失败")
            return False

        except Exception as e:
            print(f"❌ Cookie登录失败: {e}")
            return False

    def _login_twitter(self):
        """登录Twitter账号（支持Cookie/自动/手动模式）"""
        if self._login_with_cookies():
            return True

        if not self.twitter_login:
            print("⚠️ 未提供Twitter登录信息，且 Cookie 登录不可用，将以游客模式爬取")
            return False

        print("⚠️ Cookie登录失败，尝试账号密码登录...")
        manual_login = config.SELENIUM_MANUAL_LOGIN

        try:
            if manual_login:
                print("👤 手动登录模式已启用")
                print(f"   账号: {self.twitter_login['username']}")
                print("   密码: 已提供（日志中隐藏）")
            else:
                print("🤖 自动登录模式")
                print(f"   账号: {self.twitter_login['username']}")

            self.driver.get("https://twitter.com/i/flow/login")
            print("   ⏳ 等待页面和JavaScript加载...")

            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.ID, "react-root"))
                )
                print("   ✓ React根节点已加载")
            except Exception:
                print("   ⚠️ React根节点加载超时")

            self._random_delay(8, 12)
            self._take_screenshot("登录页面JavaScript渲染后")

            if manual_login:
                print("\n" + "=" * 60)
                print("👤 手动登录模式")
                print("=" * 60)
                print("请在浏览器窗口中手动完成登录：")
                print(f"  1. 输入用户名: {self.twitter_login['username']}")
                print("  2. 点击 Next")
                print("  3. 输入密码: 使用你自己的账号密码")
                print("  4. 点击 Log in")
                print("  5. 完成任何额外验证（如果需要）")
                print("=" * 60)

                print("⏳ 等待登录完成...")
                login_success = False
                for i in range(120):
                    time.sleep(1)
                    current_url = self.driver.current_url
                    if "home" in current_url or "timeline" in current_url or "/home" in current_url:
                        login_success = True
                        break
                    if (i + 1) % 10 == 0:
                        print(f"   还在等待... ({i+1}秒，当前URL: {current_url[:50]}...)")

                if login_success:
                    print("✅ 检测到登录成功！")
                    self._take_screenshot("手动登录成功")
                    return True

                print("⚠️ 等待超时，将以游客模式继续...")
                return False

            print("   🔍 正在分析登录页面结构...")
            try:
                page_html = self.driver.page_source
                debug_dir = os.path.join(config.SCREENSHOTS_DIR, self.task_id)
                os.makedirs(debug_dir, exist_ok=True)
                html_file = os.path.join(debug_dir, "login_page.html")
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(page_html)
                print(f"   📄 登录页面HTML已保存: {html_file}")

                all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                print(f"   📋 页面共有 {len(all_inputs)} 个input元素:")
                for index, input_element in enumerate(all_inputs):
                    try:
                        input_type = input_element.get_attribute("type") or "无"
                        input_name = input_element.get_attribute("name") or "无"
                        input_autocomplete = input_element.get_attribute("autocomplete") or "无"
                        input_placeholder = input_element.get_attribute("placeholder") or "无"
                        is_visible = input_element.is_displayed()
                        print(
                            f"      Input{index+1}: type={input_type}, name={input_name}, "
                            f"autocomplete={input_autocomplete}, placeholder={input_placeholder}, 可见={is_visible}"
                        )
                    except Exception:
                        pass

                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, '[role="button"]')
                print(f"   🔘 页面共有 {len(all_buttons)} 个role=button元素:")
                for index, button in enumerate(all_buttons[:10]):
                    try:
                        btn_text = button.text.strip()[:30]
                        is_visible = button.is_displayed()
                        if btn_text:
                            print(f"      Button{index+1}: text='{btn_text}', 可见={is_visible}")
                    except Exception:
                        pass

            except Exception as e:
                print(f"   ⚠️ 页面分析失败: {e}")

            print("   [1/4] 等待并查找用户名输入框...")
            try:
                username_input = None

                print("   等待input[autocomplete='username']渲染...")
                try:
                    username_input = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
                    )
                    username_input = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
                    )
                    print("   ✓ 找到用户名输入框（autocomplete='username'）")
                except Exception as e:
                    print(f"   ⚠️ 方法1失败: {e}")

                if not username_input:
                    try:
                        username_input = self.driver.find_element(By.CSS_SELECTOR, 'input[name="text"]')
                        if username_input.is_displayed():
                            print("   ✓ 找到用户名输入框（name=text）")
                    except Exception:
                        pass

                if not username_input:
                    try:
                        inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="text"]')
                        for input_element in inputs:
                            if input_element.is_displayed():
                                username_input = input_element
                                print("   ✓ 找到第一个可见文本输入框")
                                break
                    except Exception:
                        pass

                if not username_input:
                    raise Exception("找不到用户名输入框")

                username_input.click()
                self._random_delay(0.5, 1)
                username_input.clear()
                self._random_delay(0.3, 0.5)

                for char in self.twitter_login['username']:
                    username_input.send_keys(char)
                    time.sleep(0.05)

                self._random_delay(0.5, 1)
                actual_value = username_input.get_attribute('value')
                print(f"   ✓ 已输入用户名: {actual_value}")

                if actual_value != self.twitter_login['username']:
                    print(
                        f"   ⚠️ 输入值不匹配！预期: {self.twitter_login['username']}, "
                        f"实际: {actual_value}"
                    )
                    print("   正在重新输入...")
                    username_input.clear()
                    self._random_delay(0.3, 0.5)
                    username_input.send_keys(self.twitter_login['username'])
                    self._random_delay(0.5, 1)
                    actual_value = username_input.get_attribute('value')
                    print(f"   重新输入后的值: {actual_value}")

                self._random_delay(1, 2)
                self._take_screenshot("已输入用户名-准备提交")

            except Exception as e:
                print(f"   ❌ 输入用户名失败: {e}")
                raise

            print("   [2/4] 点击Next按钮提交...")
            try:
                url_before = self.driver.current_url
                print(f"   提交前URL: {url_before}")

                current_value = username_input.get_attribute('value')
                print(f"   确认输入框内容: {current_value}")

                print("   正在查找Next按钮...")
                next_button = None

                xpaths = [
                    '//span[text()="Next"]/..',
                    '//div[@role="button" and .//span[text()="Next"]]',
                    '//button[.//span[text()="Next"]]',
                    '//span[text()="下一步"]/..',
                    '//div[@role="button" and contains(., "Next")]'
                ]

                for xpath in xpaths:
                    try:
                        button = self.driver.find_element(By.XPATH, xpath)
                        if button.is_displayed() and button.is_enabled():
                            next_button = button
                            print("   ✓ 找到Next按钮（XPath）")
                            break
                    except Exception:
                        continue

                if not next_button:
                    print("   XPath未找到，尝试遍历所有按钮...")
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, '[role="button"]')
                    print(f"   页面共有 {len(buttons)} 个按钮")
                    for index, button in enumerate(buttons):
                        try:
                            btn_text = button.text.strip()
                            if btn_text.lower() == 'next' or '下一步' in btn_text.lower():
                                if button.is_displayed() and button.is_enabled():
                                    next_button = button
                                    print(f"   ✓ 找到Next按钮（按钮{index+1}，文本: '{btn_text}'）")
                                    break
                        except Exception:
                            continue

                if not next_button:
                    raise Exception("找不到Next按钮")

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                self._random_delay(0.5, 1)
                self._take_screenshot("点击Next前-用户名已输入")

                print("   准备点击Next按钮...")
                try:
                    next_button.click()
                    print("   ✓ 已点击Next按钮")
                except Exception:
                    self.driver.execute_script("arguments[0].click();", next_button)
                    print("   ✓ 已用JS点击Next按钮")

                print("   ⏳ 等待密码输入框出现...")
                password_appeared = False
                try:
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
                    )
                    password_appeared = True
                    print("   ✅ 密码输入框已出现！")
                except Exception as e:
                    print(f"   ⚠️ 等待密码框超时: {e}")

                url_after = self.driver.current_url
                print(f"   提交后URL: {url_after}")
                self._take_screenshot("点击Next后-页面状态")

                if not password_appeared:
                    print("   ⚠️ 密码框未出现，正在详细分析...")
                    try:
                        page_source = self.driver.page_source
                        debug_dir = os.path.join(config.SCREENSHOTS_DIR, self.task_id)
                        os.makedirs(debug_dir, exist_ok=True)
                        html_path = os.path.join(debug_dir, "page_after_next.html")
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(page_source)
                        print(f"   📄 页面HTML已保存: {html_path}")

                        page_text = page_source.lower()
                        if "doesn't belong to an account" in page_text or "doesn't exist" in page_text:
                            print("   ❌ 错误：用户名不存在或错误！")
                        elif "suspended" in page_text and "account" in page_text:
                            print("   ⚠️ 警告：页面包含'suspended'关键词（可能是账号冻结或其他警告）")
                        elif "unusual" in page_text or "verify" in page_text or "challenge" in page_text:
                            print("   ⚠️ 检测到验证请求：Twitter要求额外验证（可能是检测到自动化）")
                        elif "something went wrong" in page_text:
                            print("   ❌ 错误：页面提示出错")
                        elif 'autocomplete="username"' in page_source:
                            print("   ⚠️ 页面仍在用户名输入页（Next按钮点击可能无效）")
                        elif "phone" in page_text or "email" in page_text or "verification" in page_text:
                            print("   ⚠️ 可能进入了额外验证流程（手机/邮箱验证）")
                        else:
                            print("   ⚠️ 无法确定具体原因，请查看截图和HTML")

                        print(f"   当前URL: {self.driver.current_url}")
                        try:
                            print(f"   页面标题: {self.driver.title}")
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"   ⚠️ 分析页面时出错: {e}")

                    print("   ⚠️ 密码框未找到，将以游客模式继续...")
                    return False

            except Exception as e:
                print(f"   ❌ 点击Next失败: {e}")
                raise

            print("   [3/4] 输入密码...")
            try:
                current_url = self.driver.current_url
                print(f"   当前URL: {current_url}")

                try:
                    old_username_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[autocomplete="username"]')
                    if len(old_username_inputs) > 0 and old_username_inputs[0].is_displayed():
                        print("   ⚠️ 警告：用户名输入框仍然可见，页面可能未跳转！")
                        self._take_screenshot("用户名框仍存在-异常")
                    else:
                        print("   ✓ 用户名输入框已消失（正常，页面已跳转）")
                except Exception:
                    print("   ✓ 用户名输入框已消失（正常，页面已跳转）")

                print("   正在查找密码输入框...")
                password_input = None
                selectors = [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[autocomplete="current-password"]'
                ]

                for selector in selectors:
                    try:
                        password_input = WebDriverWait(self.driver, 20).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if password_input and password_input.is_displayed():
                            print(f"   ✓ 找到密码输入框（{selector}）")
                            break
                    except Exception:
                        continue

                if not password_input:
                    raise Exception("找不到密码输入框")

                password_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="password"]'))
                )

                self.driver.execute_script("arguments[0].scrollIntoView(true);", password_input)
                self._random_delay(0.5, 1)

                try:
                    password_input.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", password_input)

                self._random_delay(0.5, 1)
                password_input.clear()
                self._random_delay(0.3, 0.5)

                for char in self.twitter_login['password']:
                    password_input.send_keys(char)
                    time.sleep(0.05)

                print("   ✓ 已输入密码")
                self._random_delay(1, 2)
                self._take_screenshot("已输入密码")

            except Exception as e:
                print(f"   ❌ 输入密码失败: {e}")
                self._take_screenshot("密码输入失败")
                raise

            print("   [4/4] 提交登录...")
            try:
                from selenium.webdriver.common.keys import Keys

                try:
                    password_input.send_keys(Keys.RETURN)
                    print("   ✓ 已按回车键提交登录")
                    self._random_delay(5, 7)
                    self._take_screenshot("提交登录后")
                except Exception as e1:
                    print(f"   ⚠️ 回车提交失败: {e1}，尝试点击登录按钮...")
                    login_button = None

                    xpaths = [
                        '//span[text()="Log in"]/..',
                        '//span[text()="登录"]/..',
                        '//div[@role="button" and contains(., "Log in")]',
                        '//button[contains(., "Log in")]'
                    ]

                    for xpath in xpaths:
                        try:
                            button = self.driver.find_element(By.XPATH, xpath)
                            if button.is_displayed() and button.is_enabled():
                                login_button = button
                                print("   ✓ 找到登录按钮")
                                break
                        except Exception:
                            continue

                    if not login_button:
                        try:
                            login_button = self.driver.find_element(
                                By.CSS_SELECTOR,
                                '[data-testid="LoginForm_Login_Button"]'
                            )
                            if login_button.is_displayed():
                                print("   ✓ 找到登录按钮（data-testid）")
                        except Exception:
                            pass

                    if not login_button:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, '[role="button"]')
                        for button in buttons:
                            if 'log in' in button.text.lower() or '登录' in button.text.lower():
                                if button.is_displayed():
                                    login_button = button
                                    print(f"   ✓ 找到按钮: {button.text}")
                                    break

                    if not login_button:
                        raise Exception("找不到登录按钮且回车失败")

                    self.driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
                    self._random_delay(0.5, 1)

                    try:
                        login_button.click()
                        print("   ✓ 已点击登录按钮")
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", login_button)
                        print("   ✓ 已用JS点击登录按钮")

                    self._random_delay(5, 7)
                    self._take_screenshot("点击登录后")

                print("   ⏳ 等待登录完成...")
                self._random_delay(5, 7)

            except Exception as e:
                print(f"   ❌ 提交登录失败: {e}")
                self._take_screenshot("登录提交失败")
                raise

            current_url = self.driver.current_url
            print(f"   当前URL: {current_url}")

            if "home" in current_url or "timeline" in current_url or "/home" in current_url:
                print("✅ Twitter登录成功！")
                self._take_screenshot("登录成功")
                return True

            print(f"⚠️ 登录可能失败，当前URL: {current_url}")
            self._take_screenshot("登录状态未知")
            return True

        except Exception as e:
            print(f"❌ Twitter登录失败: {e}")
            self._take_screenshot("登录失败")
            print("⚠️ 将以游客模式继续爬取...")
            return False
