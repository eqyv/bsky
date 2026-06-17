<div align="center">

<!-- ─────────────  LOGO  ───────────── -->
<img src="assets/logo.png" alt="bsky crosspost logo" width="160" height="160">

# **bsky crosspost**

##### _Automatically mirror your Bluesky posts to X (Twitter) and Instagram._

<br>

[![Stars](https://img.shields.io/github/stars/eqyv/bsky?style=for-the-badge&logo=github&color=8b5cf6&logoColor=white)](https://github.com/eqyv/bsky/stargazers)
[![Forks](https://img.shields.io/github/forks/eqyv/bsky?style=for-the-badge&logo=github&color=6366f1&logoColor=white)](https://github.com/eqyv/bsky/network/members)
[![Issues](https://img.shields.io/github/issues/eqyv/bsky?style=for-the-badge&logo=github&color=ec4899&logoColor=white)](https://github.com/eqyv/bsky/issues)
[![License](https://img.shields.io/github/license/eqyv/bsky?style=for-the-badge&color=0ea5e9)](LICENSE)

![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Bluesky](https://img.shields.io/badge/Bluesky-0285FF?style=for-the-badge&logo=bluesky&logoColor=white)
![X](https://img.shields.io/badge/X-000000?style=for-the-badge&logo=x&logoColor=white)
![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)

</div>

---

## Overview

**bsky crosspost** watches a Bluesky account and re-publishes each new post — text **and** media — to your other social platforms. It runs as a lightweight polling loop with per-platform adapters, so you can enable only the targets you need.

| Platform | Role | Library | Auth |
| :-- | :-- | :-- | :-- |
| 🦋 Bluesky | Source | `atproto` | App password |
| ✖️ X (Twitter) | Target | `twikit` | Cookies _(recommended)_ or login |
| 📸 Instagram | Target | `instagrapi` | Session / login |

## Features

- **Multi-target fan-out** — one Bluesky post → many platforms in a single pass.
- **Media-aware** — downloads and re-uploads images attached to the source post.
- **Resilient state** — tracks the last processed post; only advances state when a target succeeds, so nothing is silently dropped.
- **Drop-in adapters** — each platform is isolated behind a common interface; missing credentials simply skip that target.
- **Cookie-based X auth** — sidesteps X's Cloudflare-protected login (essential on VPS/datacenter IPs).

## Installation

```bash
git clone https://github.com/eqyv/bsky.git
cd bsky

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## Configuration

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Required | Description |
| :-- | :--: | :-- |
| `BSKY_HANDLE` | ✅ | Your Bluesky handle (`name.bsky.social`) |
| `BSKY_APP_PASSWORD` | ✅ | Bluesky **app password** (not your login password) |
| `X_AUTH_TOKEN` / `X_CT0` | ▶️ | Browser-exported X cookies — **preferred** auth |
| `X_USERNAME` / `X_EMAIL` / `X_PASSWORD` | ▶️ | X login fallback (blocked on datacenter IPs) |
| `X_TOTP_SECRET` | ⬜ | X 2FA base32 secret, if enabled |
| `IG_USERNAME` / `IG_PASSWORD` | ▶️ | Instagram credentials |
| `POLL_INTERVAL_SECONDS` | ⬜ | How often to check Bluesky (default `180`) |

> ▶️ = required only for that target. Enable any subset of X / Instagram.

**Getting your X cookies:** log into X in a browser → DevTools → **Application → Cookies → `https://x.com`** → copy the `auth_token` and `ct0` values into `.env`. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for why this is recommended.

## Usage

```bash
python main.py
```

On first run the bot **seeds** its state with your latest existing post, so only posts created *after* startup are mirrored. Press `Ctrl+C` to stop.

## Project structure

```
bsky/
├── adapters/        # Per-platform source & target adapters
│   ├── bluesky_source.py
│   ├── twitter.py / twitter_patch.py
│   └── instagram.py
├── core/            # Detector, orchestrator, state manager
├── utils/           # Logger, media downloader
├── storage/         # Session cookies & state (gitignored)
├── config.py        # Env-backed configuration
└── main.py          # Entry point & polling loop
```

## Troubleshooting

X (Twitter) relies on `twikit`, an unofficial client that occasionally drifts from X's changing internals. Common errors and their fixes are documented in **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

## Disclaimer

This project uses **unofficial** clients for X and Instagram. Automating these platforms may violate their Terms of Service and can put your account at risk. Use responsibly, at your own risk, and prefer dedicated/secondary accounts.

---

<div align="center">
<sub>um :)</sub>
</div>
