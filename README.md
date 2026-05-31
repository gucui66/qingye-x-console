# Qingye X Console

Qingye X Console is a local-first web console for collecting, managing, and reviewing X/Twitter account timelines, media, crawl tasks, and local archives.

It combines a Vue 3 admin interface with a Flask backend, Selenium-based crawling, task orchestration, media downloads, and SQLite-based local storage.

> This repository is prepared for public source release. It does not include private crawl data, cookies, local databases, output files, or environment secrets.

## Highlights

- Create focused crawl tasks for X/Twitter accounts.
- Track running, paused, completed, failed, and cancelled tasks.
- Browse collected accounts in a user timeline sorted by latest collection time.
- Open standalone timeline, post detail, and video playback pages.
- Review local videos, photos, post text, screenshots, logs, and task artifacts.
- Manage user display names and hide/restored accounts from the timeline directory.
- Configure runtime settings and Twitter Bearer Token from the admin console.
- Use Chinese or English UI language from Settings.
- Run locally with Python, Flask, Vue 3, Ant Design Vue, and optional Docker.

## Tech Stack

- Backend: Python, Flask, Flask-SocketIO
- Crawling: Selenium, optional Tweepy API mode
- Frontend: Vue 3, Vue Router, Pinia-style store structure, Ant Design Vue, Vite
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
├── static/                   # legacy/static assets served by Flask
├── templates/                # fallback templates
├── tools/                    # local helper scripts
├── data/                     # runtime data directory, ignored by git
└── output/                   # generated crawl output, ignored by git
```

## What Is Not Included

The GitHub release folder intentionally excludes:

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

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables:

```bash
cp .env.example .env
```

Edit `.env` and set the values you need.

4. Install and build the frontend:

```bash
cd frontend
npm install
npm run build
cd ..
```

5. Start the local app:

```bash
python3 app.py
```

6. Open the console:

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

Copy the environment file first:

```bash
cp .env.example .env
```

Build the frontend before running Docker:

```bash
cd frontend
npm install
npm run build
cd ..
```

Then start the service:

```bash
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

The admin console supports Simplified Chinese and English. Open:

```text
Settings -> Language & Display
```

Then choose the UI language. The selection is saved in browser local storage.

## Data And Privacy

This application is designed for local operation. Crawl outputs, cookies, task history, local media, screenshots, and SQLite files may contain sensitive or copyrighted information.

Before publishing, sharing, or deploying this repository:

- Review `.gitignore`.
- Keep `.env` private.
- Keep `twitter_cookies.json` or `cookies/twitter_cookies.json` private.
- Do not commit `data/`, `output/`, `oldoutput/`, or local media shards.
- Ensure your usage complies with X/Twitter terms, local laws, and any applicable platform rules.

## Commercial Licensing

This project is **source-available**, not open-source under MIT/Apache/GPL.

Commercial use, SaaS use, resale, paid hosting, white-label distribution, or integration into a paid product requires a separate written commercial license from the copyright owner.

See [LICENSE](./LICENSE) and [COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md).

## Development Notes

Frontend source lives in `frontend/`. After frontend changes, run:

```bash
cd frontend
npm run build
```

The build output is written to `static/vue/`, which Flask serves as the single-page app.

Backend source lives in `core/`, `routes/`, `services/`, `scrapers/`, and `tasks/`.

## Publish Checklist

Before pushing to GitHub:

- Replace copyright owner placeholders in `LICENSE` and `COMMERCIAL_LICENSE.md`.
- Confirm `.env` does not exist in the repo.
- Confirm `twitter_cookies.json` and real files under `cookies/` do not exist in the repo.
- Confirm `data/`, `output/`, `oldoutput/`, and `frontend/node_modules/` are not tracked.
- Run `npm run build` in `frontend/`.
- Start the app locally and check the browser console.
- Add screenshots or product images only if they do not expose private accounts or collected content.

## Disclaimer

This software is provided without warranty. You are responsible for how you configure and use it, including compliance with platform terms, copyright, privacy, and data protection requirements.
