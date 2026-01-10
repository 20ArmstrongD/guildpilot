# 🤖 GuildPilot

![CI](https://github.com/20ArmstrongD/guildpilot/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/github/license/20ArmstrongD/guildpilot)

**GuildPilot** is an all-in-one Discord bot designed to manage server operations through a modular, scalable architecture.  
It combines member role automation, game stat lookups, AI chat capabilities, and streaming notifications into a single bot identity.

Rather than running multiple bots per server, GuildPilot acts as a **central command hub** with internally separated modules for maintainability and growth.

---

## 🚀 Features

### 🛡️ RoleCop (Member & Role Management)
- Automatic role assignment on member join
- Admin-controlled promotion and demotion
- Role hierarchy validation
- Server-aware logging

### 🎮 StatWrangler (Game Statistics)
- Lookup player stats for supported games
- Modular provider system for adding new games
- Clean, embedded Discord responses

### 🤖 PilotAI (AI Chatbot)
- Slash-command driven AI conversations
- Context-aware responses (per channel / per user)
- Optional conversation reset and logging

### 📡 StreamSentinel (Streaming Notifications)
- Twitch live/offline notifications
- Stream metadata (game, title, duration)
- Support for multiple streamers per server

---

## 🧱 Architecture Overview

GuildPilot uses a **modular monolith** design:

- **One Discord bot**
- **Multiple internal modules**
- Shared configuration, logging, and database layer

```text
guildpilot/
├── bot.py                  # Application entry point
├── core/                   # Bot initialization & shared logic
├── modules/                # Feature modules
│   ├── role_cop/
│   ├── stat_wrangler/
│   ├── pilot_ai/
│   └── stream_sentinel/
├── utils/                  # Helpers, embeds, DB utilities
└── guildpilot.service      # systemd service definition
