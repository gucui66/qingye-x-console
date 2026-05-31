# 青野 X Console

<p align="center">
  <img src="docs/assets/qingye-logo.svg" alt="Qingye X Console" width="860" />
</p>

<p align="center">
  <a href="./README.md">首页</a>
  ·
  <a href="./README.en.md">English</a>
</p>

<p align="center">
  <img alt="Source Available" src="https://img.shields.io/badge/license-source--available-245C39?style=for-the-badge" />
  <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3-42b883?style=for-the-badge&logo=vuedotjs&logoColor=white" />
  <img alt="Flask" src="https://img.shields.io/badge/Flask-API-111827?style=for-the-badge&logo=flask&logoColor=white" />
  <img alt="Selenium" src="https://img.shields.io/badge/Selenium-Crawler-43B02A?style=for-the-badge&logo=selenium&logoColor=white" />
</p>

青野 X Console 是一套本地优先的 X/Twitter 采集控制台，用来管理账号时间流、媒体资料、爬取任务和本地归档。

它把 Vue 3 后台界面、Flask 后端、Selenium 采集、任务队列、媒体下载和 SQLite 本地存储整合成一个完整应用。

> 这个仓库是为公开发布准备的干净源码版本，不包含真实采集数据、Cookie、本地数据库、输出文件或环境密钥。

<p align="center">
  <img src="docs/assets/qingye-console-ai-hero.png" alt="Qingye X Console AI generated hero banner" width="960" />
</p>

## 核心亮点

- 创建针对某个 X/Twitter 账号的采集任务。
- 跟踪运行、暂停、完成、失败和取消状态。
- 用户时间流首页按最近采集时间排序。
- 支持独立用户时间流、贴文详情页和视频播放页。
- 查看本地视频、图片、正文、截图、日志和任务产物。
- 管理用户显示名，隐藏或恢复不想展示的账号。
- 在后台配置运行参数和 Twitter Bearer Token。
- 支持简体中文和英文界面。
- 支持本地 Python/Flask/Vue 运行，也支持 Docker 部署。

## 功能模块

| 模块 | 用途 |
| --- | --- |
| 新建爬取任务 | 集中设置账号、采集数量、媒体下载选项和 Selenium 行为。 |
| 任务工作台 | 卡片式管理任务，支持筛选、重试、暂停、继续、取消和删除。 |
| 用户时间流 | 独立账号浏览页，按最近采集时间展示已采集账号。 |
| 贴文详情 | 单条贴文阅读页，展示正文、媒体、发布时间和采集时间。 |
| 视频播放页 | 独立本地视频播放，支持播放列表、续播位置和媒体上下文。 |
| 媒体资料库 | 管理本地视频、图片、标注和复核状态。 |
| 数据库管理 | 查看本地存储、分片库和维护迁移信息。 |

## 架构图

<p align="center">
  <img src="docs/assets/qingye-architecture.svg" alt="Qingye X Console architecture" width="960" />
</p>

```text
浏览器
  -> Vue 3 单页应用
  -> Flask API
  -> 任务引擎
  -> Selenium / API 采集器
  -> 下载器
  -> SQLite + JSON + 本地文件
```

## 技术栈

- 后端：Python, Flask, Flask-SocketIO
- 采集：Selenium，可选 Tweepy API 模式
- 前端：Vue 3, Vue Router, Ant Design Vue, Vite
- 存储：本地 JSON 状态 + SQLite 媒体分片库
- 运行：优先本地 macOS 开发，支持 Docker 部署

## 目录结构

```text
.
├── app.py                    # Flask 应用入口
├── core/                     # 认证、运行时、配置
├── routes/                   # Flask 路由和 API
├── services/                 # 媒体库、下载器、时间流、产物服务
├── scrapers/                 # Selenium 和 API 采集器
├── tasks/                    # 任务模型、持久化、控制和执行
├── frontend/                 # Vue 3 前端源码
├── static/                   # Flask 静态资源
├── tools/                    # 本地辅助脚本
├── data/                     # 本地运行数据，默认不提交
└── output/                   # 采集输出目录，默认不提交
```

## 公开仓库不包含什么

这个 GitHub 版本会刻意排除：

- `.env`
- `twitter_cookies.json` 或 `cookies/twitter_cookies.json`
- `frontend/node_modules/`
- `__pycache__/`
- 本地 `data/` 真实内容
- 本地 `output/` 和 `oldoutput/`
- `static/vue/assets/` 下的前端构建产物
- 真实采集媒体、截图和数据库

## 运行要求

- Python 3.10+
- Node.js 18+
- Chrome 或 Chromium
- 与浏览器匹配的 ChromeDriver
- 可选：Docker 和 Docker Compose

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env

cd frontend
npm install
npm run build
cd ..

python3 app.py
```

打开：

```text
http://localhost:5001
```

默认管理员账号：

```text
username: admin
password: admin123
```

首次登录后请立刻修改密码。

## Docker

```bash
cp .env.example .env

cd frontend
npm install
npm run build
cd ..

docker compose up --build
```

## 环境变量

参考 [.env.example](./.env.example)。

常用配置：

- `PORT`：Flask 端口，默认 `5001`
- `SECRET_KEY`：Flask Session 密钥
- `TWITTER_BEARER_TOKEN`：可选 X/Twitter API Bearer Token
- `TWITTER_USERNAME`：可选 Selenium 登录账号
- `TWITTER_PASSWORD`：可选 Selenium 登录密码
- `SELENIUM_HEADLESS`：是否无头运行 Selenium
- `SELENIUM_MANUAL_LOGIN`：是否允许手动登录流程

不要提交 `.env`、Cookie、本地数据库或真实采集媒体。

## 语言切换

后台支持简体中文和英文。

```text
系统设置 -> 语言与显示
```

选择结果会保存在浏览器本地存储中。

## 数据与隐私

这个应用的设计目标是本地运行。采集输出、Cookie、任务历史、本地媒体、截图和 SQLite 文件都可能包含敏感信息或版权内容。

公开、分享或部署前请确认：

- 检查 `.gitignore`。
- 不提交 `.env`。
- 不提交 `twitter_cookies.json` 或 `cookies/twitter_cookies.json`。
- 不提交 `data/`、`output/`、`oldoutput/` 或本地媒体分片。
- 确认你的使用方式符合 X/Twitter 条款、本地法律和相关平台规则。

## 商业授权

本项目是 **source-available**，不是 MIT/Apache/GPL 开源授权。

商业使用、SaaS 使用、转售、付费托管、白标分发或集成到付费产品中，都需要获得版权方单独书面授权。

详见 [LICENSE](./LICENSE) 和 [COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md)。

## 免责声明

本软件按“现状”提供，不附带任何担保。你需要自行负责配置和使用方式，并确保遵守平台条款、版权、隐私和数据保护要求。
