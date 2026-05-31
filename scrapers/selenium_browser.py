"""
Selenium 爬虫的浏览器初始化与基础工具
"""
import os
import random
import time

import core.config as config
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class SeleniumBrowserMixin:
    """浏览器初始化、截图和基础工具方法"""

    @staticmethod
    def _is_task_stop_exception(error: Exception) -> bool:
        """识别由外部任务管理器抛出的暂停/取消异常"""
        return error.__class__.__name__ == 'TaskInterruptedError'

    def _check_for_stop(self):
        """检查外部是否请求暂停或取消"""
        if self.stop_callback:
            self.stop_callback()

    @staticmethod
    def _find_existing_binary(candidates):
        """返回第一个存在的二进制路径"""
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _get_cookie_file(self):
        """返回可用的 Cookie 文件路径"""
        candidates = [
            os.getenv('COOKIE_FILE'),
            getattr(config, 'COOKIE_FILE', None),
            'twitter_cookies.json',
            'cookies/twitter_cookies.json',
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _init_driver(self):
        """初始化浏览器驱动（增强反反爬）"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument('--headless=new')
            print("🤖 无头模式（后台运行）")
        else:
            print("👀 有头模式（显示浏览器窗口）")

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        chrome_options.add_argument(f'user-agent={self.user_agent}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--log-level=3')

        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        chrome_options.add_argument('--window-size=1920,1080')

        chrome_binary = self._find_existing_binary([
            os.getenv('CHROME_BIN'),
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/usr/bin/google-chrome',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        ])
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            print(f"使用浏览器二进制: {chrome_binary}")

        try:
            try:
                from selenium.webdriver.chrome.service import Service
                system_driver = self._find_existing_binary([
                    os.getenv('CHROMEDRIVER_BIN'),
                    '/usr/bin/chromedriver',
                    '/usr/local/bin/chromedriver',
                ])

                if system_driver:
                    print(f"使用系统 ChromeDriver: {system_driver}")
                    service = Service(system_driver)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    print("✅ 系统 ChromeDriver 启动成功")
                else:
                    from webdriver_manager.chrome import ChromeDriverManager

                    print("使用 webdriver-manager 自动管理 ChromeDriver...")
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    print("✅ ChromeDriver 自动安装/更新成功")
            except ImportError:
                print("webdriver-manager 未安装，使用 Selenium 默认 ChromeDriver...")
                self.driver = webdriver.Chrome(options=chrome_options)

            self._inject_anti_detection_js()
            return True

        except Exception as e:
            print(f"❌ 初始化浏览器失败: {e}")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("解决方案:")
            print("1. 安装 webdriver-manager (推荐):")
            print("   pip3 install webdriver-manager")
            print("")
            print("2. 或手动安装 Chrome 和 ChromeDriver:")
            print("   bash install_chrome.sh")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            return False

    def _inject_anti_detection_js(self):
        """注入JavaScript代码移除自动化检测痕迹"""
        anti_detection_js = """
        // 移除webdriver属性
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // 伪装Chrome对象
        window.chrome = {
            runtime: {}
        };

        // 覆盖权限查询
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // 伪装插件
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // 伪装语言
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en-US', 'en']
        });
        """
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': anti_detection_js
        })
        print("✅ 已注入反检测JavaScript代码")

    def _random_delay(self, min_sec=1.5, max_sec=4.0):
        """随机延迟（模拟人类行为）"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _take_screenshot(self, description=""):
        """截取浏览器截图"""
        try:
            screenshot_dir = os.path.join(config.SCREENSHOTS_DIR, self.task_id)
            os.makedirs(screenshot_dir, exist_ok=True)

            screenshot_path = os.path.join(screenshot_dir, "latest.png")
            self.driver.save_screenshot(screenshot_path)
            self.screenshot_count += 1

            if self.screenshot_count % 5 == 0:
                timestamp_path = os.path.join(screenshot_dir, f"screenshot_{self.screenshot_count}.png")
                self.driver.save_screenshot(timestamp_path)
                print(f"📸 截图已保存: {description} (最新: {screenshot_path}, 历史: {timestamp_path})")
            else:
                print(f"📸 截图已保存: {description} ({screenshot_path})")

        except Exception as e:
            print(f"⚠️ 截图失败: {e}")
            import traceback
            traceback.print_exc()

    def _human_like_scroll(self, element=None):
        """人性化滚动（模拟真实用户）"""
        if element:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
        else:
            scroll_distance = random.randint(300, 800)
            self.driver.execute_script(
                f"window.scrollBy({{top: {scroll_distance}, behavior: 'smooth'}});"
            )

        time.sleep(random.uniform(0.5, 1.5))
