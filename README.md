# 🤖 GuildPilot

![CI/CD — Build & Test](https://github.com/20ArmstrongD/guildpilot/actions/workflows/ci.yml/badge.svg)
![CI/CD — Code Quality](https://github.com/20ArmstrongD/guildpilot/actions/workflows/lint.yml/badge.svg)
![Security — Secret Detection](https://github.com/20ArmstrongD/guildpilot/actions/workflows/gitleaks.yml/badge.svg)
![Security — Code Analysis](https://github.com/20ArmstrongD/guildpilot/actions/workflows/codeql.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)

A modular, production-ready Discord bot ecosystem built with Python and py-cord, featuring CI/CD, automated testing, and security-first workflows.

# 🛩️ GuildPilot  
### Modular Discord Automation, Intelligence & Governance Platform

GuildPilot is a **production-grade, modular Discord bot platform** designed for automation, role governance, analytics, and intelligent interaction.  
Built with **scalability, multi-environment deployments, and real engineering discipline**, GuildPilot is intended for both **community servers** and **professional organizations**.

GuildPilot is not a single-purpose bot — it is a **platform**.

---

## ✨ Core Features

### 🤖 AI Interaction (PilotAI)
- `/ask-the-pilot` — AI-powered assistant for server members  
- Context-aware responses  
- Modular AI backend designed for future expansion  

---

### 🛡️ RoleCop — Role Governance & Approval System
A structured governance framework for role management:

- Role promotions & demotions  
- Approval-based workflows  
- Multi-approver support  
- Admin override mode  
- Safe-mode transparency  
- Audit-friendly approval visibility  
- Permission hierarchy enforcement  

> Built for accountability, not chaos.

---

### 📊 StatWrangler — Analytics & Data Tools
- Server activity tracking  
- Structured JSON analytics pipelines  
- User engagement metrics  
- Expandable data-collection architecture  

---

### 🧭 Community & Utility Commands
- `/who_has_role` — Query role membership  
- `/user_roles` — Inspect user role assignments  
- `/game_stats` — Game/player lookups  
- `/kick` — Moderation support  
- `/promote` / `/demote` — Governance-controlled role actions  

---

## 🧠 Architecture Highlights

GuildPilot is engineered like a **real system**, not a hobby script.

---

### 🧪 Dual-Environment Deployment
- **Dev Bot**
  - Fast guild-sync iteration  
  - Experimental testing  
- **Public Bot**
  - Controlled production rollout  
  - Registry-based deployment  
  - Stability-focused runtime  

---

### 📂 Guild Registry System
- Automatically tracks servers  
- Separate registries for Dev & Public environments  
- JSON-backed deployment model  
- Controlled command propagation  
- Server-aware configuration loading  

---

### 🧩 Modular Feature Architecture

GuildPilot is structured as a modular platform, with each system isolated into a dedicated feature domain:

- **modules/bot/** — Multi-bot runtime & startup orchestration  
- **modules/core/** — Guild registry, configuration, and environment management  
- **modules/pilotai/** — AI interaction engine and response handling  
- **modules/rolecop/** — Role governance, approvals, and moderation workflows  
- **modules/statwrangler/** — Analytics, tracking, and metrics processing  
- **utils/** — Command sync utilities and shared helper logic  
