#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter Cookie 获取助手
在本地Mac运行，自动打开浏览器并指导你获取Cookie
"""

import webbrowser
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

print("\n" + "=" * 70)
print("🍪 Twitter Cookie 获取助手")
print("=" * 70)

print("""
为什么需要Cookie？
- 绕过自动化检测
- 零额外内存消耗
- 一次登录，长期使用
- 适合低配置服务器

获取步骤：
""")

print("1️⃣  浏览器将自动打开Twitter登录页")
print("2️⃣  手动登录你自己的 Twitter / X 账号")
print("3️⃣  登录成功后，按 F12 打开开发者工具")
print("4️⃣  点击 Application 标签")
print("5️⃣  左侧展开 Cookies → 点击 https://x.com")
print("6️⃣  找到并复制以下3个Cookie的值：")
print("      • auth_token")
print("      • ct0")
print("      • guest_id")

print("\n" + "=" * 70)
input("按回车打开浏览器...")

webbrowser.open("https://x.com/login")

print("\n✅ 浏览器已打开！")
print("\n请按照上面的步骤操作，获取Cookie后：\n")

# 提供模板
template = [
    {
        "name": "auth_token",
        "value": "在这里粘贴auth_token的值",
        "domain": ".x.com",
        "path": "/",
        "secure": True,
        "httpOnly": True
    },
    {
        "name": "ct0",
        "value": "在这里粘贴ct0的值",
        "domain": ".x.com",
        "path": "/",
        "secure": True,
        "httpOnly": False
    },
    {
        "name": "guest_id",
        "value": "在这里粘贴guest_id的值",
        "domain": ".x.com",
        "path": "/",
        "secure": False,
        "httpOnly": False
    }
]

# 保存模板
template_path = ROOT_DIR / "twitter_cookies_template.json"
with open(template_path, "w", encoding="utf-8") as f:
    json.dump(template, f, indent=2, ensure_ascii=False)

print(f"📄 Cookie模板已保存到: {template_path}")
print(f"\n编辑此文件，填入你的 Cookie 值，然后放到项目根目录作为 `twitter_cookies.json` 使用。")
print("\n" + "=" * 70)





