"""Scraper implementations."""

from .tweepy_scraper import TweepyTwitterScraper

SELENIUM_IMPORT_ERROR = None

try:
    from .selenium_scraper import SeleniumTwitterScraper
    SELENIUM_AVAILABLE = True
except ImportError as exc:
    SELENIUM_IMPORT_ERROR = exc
    SELENIUM_AVAILABLE = False

    class SeleniumTwitterScraper:  # type: ignore[override]
        """在 selenium 依赖缺失时提供延迟报错，占位保证应用可启动。"""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Selenium 依赖未安装，无法使用浏览器模式。"
            ) from SELENIUM_IMPORT_ERROR

__all__ = [
    'SeleniumTwitterScraper',
    'TweepyTwitterScraper',
    'SELENIUM_AVAILABLE',
    'SELENIUM_IMPORT_ERROR',
]
