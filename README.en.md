# Qingye X Console

<p align="center">
  <img src="docs/assets/qingye-logo.svg" alt="Qingye X Console" width="860" />
</p>

<p align="center">
  <a href="./README.md">Home</a>
  ·
  <a href="./README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img alt="Source Available" src="https://img.shields.io/badge/license-source--available-245C39?style=for-the-badge" />
  <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3-42b883?style=for-the-badge&logo=vuedotjs&logoColor=white" />
  <img alt="Flask" src="https://img.shields.io/badge/Flask-API-111827?style=for-the-badge&logo=flask&logoColor=white" />
  <img alt="Selenium" src="https://img.shields.io/badge/Selenium-Crawler-43B02A?style=for-the-badge&logo=selenium&logoColor=white" />
</p>

Qingye X Console is a local-first web console for collecting, managing, and reviewing X/Twitter account timelines, media, crawl tasks, and local archives.

It combines a Vue 3 admin interface with a Flask backend, Selenium-based crawling, task orchestration, media downloads, and SQLite-based local storage.

> This repository is prepared for public source release. It does not include private crawl data, cookies, local databases, output files, or environment secrets.

<p align="center">
  <img src="docs/assets/qingye-console-ai-hero.png" alt="Qingye X Console AI generated hero banner" width="960" />
</p>

## Highlights

- Create focused crawl tasks for X/Twitter accounts.
- Track running, paused, completed, failed, and cancelled tasks.
- Browse collected accounts in a user timeline sorted by latest collection time.
- Open standalone timeline, post detail, and video playback pages.
- Review local videos, photos, post text, screenshots, logs, and task artifacts.
- Manage display names and hide/restored accounts from the timeline directory.
- Configure runtime settings and Twitter Bearer Token from the admin console.
- Switch the interface between Simplified Chinese and English.
- Run locally with Python, Flask, Vue 3, Ant Design Vue, and optional Docker.

## Product Areas

| Area | Purpose |
| --- | --- |
| New Crawl Task | A focused task creation page for account, count, media options, and Selenium behavior. |
| Task Workbench | Card-based task management with filters, retry, pause, resume, cancel, and delete actions. |
| User Timeline | Standalone account browser sorted by latest collection time. |
| Post Detail | Single-post reading page with text, media, original publish time, and local collection time. |
| Video Player | Dedicated local video playback page with playlist, resume position, and media context. |
| Media Library | Local archive for videos, photos, annotations, and media review. |
| Database Admin | Local storage and shard visibility for maintenance and migration. |

## Architecture

<p align="center">
  <img src="docs/assets/qingye-architecture.svg" alt="Qingye X Console architecture" width="960" />
</p>

```text
Browser
  -> Vue 3 SPA
  -> Flask API
  -> Task Engine
  -> Selenium / API Crawler
  -> Downloader
  -> SQLite + JSON + Local Files
```

## Tech Stack

- Backend: Python, Flask, Flask-SocketIO
- Crawling: Selenium, optional Tweepy API mode
- Frontend: Vue 3, Vue Router, Ant Design Vue, Vite
- Storage: local JSON state plus SQLite media shard databases
- Runtime: local macOS development first, Docker deployment supported

## Repository Structure

```text
.
├── app.py                    # Flask application entry point
├── core/                     # auth, runtime, config
├── routes/                   # Flask routes and API endpoints
├── services/                 # media store, downloader, timeline, artifacts
├── scrapers/                 # Selenium and API scrapers
├── tasks/                    # task models, persistence, control, execution
├── frontend/                 # Vue 3 source code
├── static/                   # static assets served by Flask
├── tools/                    # local helper scripts
├── data/                     # runtime data directory, ignored by git
└── output/                   # generated crawl output, ignored by git
```

## What Is Not Included

The GitHub release intentionally excludes:

- `.env`
- `twitter_cookies.json` or `cookies/twitter_cookies.json`
- `frontend/node_modules/`
- `__pycache__/`
- local `data/` contents
- local `output/` and `oldoutput/`
- generated frontend build assets under `static/vue/assets/`
- real collected media, screenshots, and databases

## Requirements

- Python 3.10+
- Node.js 18+
- Chrome or Chromium
- ChromeDriver compatible with your browser
- Optional: Docker and Docker Compose

## Quick Start

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

Open:

```text
http://localhost:5001
```

Default admin login:

```text
username: admin
password: admin123
```

Change the password after first login.

## Docker

```bash
cp .env.example .env

cd frontend
npm install
npm run build
cd ..

docker compose up --build
```

## Environment Variables

See [.env.example](./.env.example).

Common values:

- `PORT`: Flask port, default `5001`
- `SECRET_KEY`: Flask session secret
- `TWITTER_BEARER_TOKEN`: optional X/Twitter API Bearer Token
- `TWITTER_USERNAME`: optional account username for Selenium login flow
- `TWITTER_PASSWORD`: optional account password for Selenium login flow
- `SELENIUM_HEADLESS`: run Selenium in headless mode
- `SELENIUM_MANUAL_LOGIN`: allow manual browser login flow

Do not commit `.env`, cookies, local databases, or collected media.

## Language

The admin console supports Simplified Chinese and English.

```text
Settings -> Language & Display
```

The selection is saved in browser local storage.

## Data And Privacy

This application is designed for local operation. Crawl outputs, cookies, task history, local media, screenshots, and SQLite files may contain sensitive or copyrighted information.

Before publishing, sharing, or deploying this repository:

- Review `.gitignore`.
- Keep `.env` private.
- Keep `twitter_cookies.json` or `cookies/twitter_cookies.json` private.
- Do not commit `data/`, `output/`, `oldoutput/`, or local media shards.
- Ensure your usage complies with X/Twitter terms, local laws, and applicable platform rules.

## Commercial Licensing

This project is **source-available**, not open-source under MIT/Apache/GPL.

Commercial use, SaaS use, resale, paid hosting, white-label distribution, or integration into a paid product requires a separate written commercial license from the copyright owner.

See [LICENSE](./LICENSE) and [COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md).

## Disclaimer

This software is provided without warranty. You are responsible for how you configure and use it, including compliance with platform terms, copyright, privacy, and data protection requirements.
