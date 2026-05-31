#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地测试脚本 - 手动登录模式
在本地Mac上运行，可以看到浏览器窗口并手动登录
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 设置环境变量（在导入config之前）
os.environ['SELENIUM_HEADLESS'] = 'false'  # 显示浏览器窗口
os.environ['SELENIUM_MANUAL_LOGIN'] = 'true'  # 启用手动登录

# 导入模块
import core.config as config
from scrapers.selenium_scraper import SeleniumTwitterScraper

print("=" * 60)
print("本地手动登录测试")
print("=" * 60)
print(f"账号: {config.TWITTER_USERNAME}")
password_mask = "*" * len(config.TWITTER_PASSWORD) if config.TWITTER_PASSWORD else "(未设置)"
print(f"密码: {password_mask}")
print(f"无头模式: {config.SELENIUM_HEADLESS}")
print(f"手动登录: {config.SELENIUM_MANUAL_LOGIN}")
print("=" * 60)

# 要爬取的用户
target_user = "ZK1332689"  # 可以改成你想测试的用户

try:
    # 创建爬虫实例
    scraper = SeleniumTwitterScraper(
        headless=False,  # 显示浏览器
        twitter_login={
            'username': config.TWITTER_USERNAME,
            'password': config.TWITTER_PASSWORD
        },
        task_id=f"manual_test_{target_user}"
    )
    
    print(f"\n开始爬取用户: @{target_user}")
    print("浏览器窗口将会打开，请在窗口中手动完成登录！\n")
    
    # 执行爬取
    tweets = scraper.scrape_user_tweets(max_tweets=10)
    
    print(f"\n✅ 爬取完成！")
    print(f"共爬取 {len(tweets)} 条推文")
    
    if tweets:
        print(f"\n示例推文：")
        for i, tweet in enumerate(tweets[:3]):
            print(f"\n推文 {i+1}:")
            print(f"  内容: {tweet.get('content', '')[:50]}...")
            print(f"  图片: {len(tweet.get('photos', []))} 张")
            print(f"  视频: {len(tweet.get('videos', []))} 个")
    
except KeyboardInterrupt:
    print("\n\n⚠️ 用户中断")
except Exception as e:
    print(f"\n\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
finally:
    print("\n测试结束")
