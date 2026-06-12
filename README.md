---
title: Global Leaders
emoji: 🌍
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 6.17.3
app_file: app.py
pinned: false
license: mit
short_description: Govern a real 2025 world leader; a small model runs it all
tags:
  - build-small-hackathon
  - thousand-token-wood
  - track:wood
  - nemotron
  - nvidia
  - sponsor:nvidia
  - off-brand
  - off-the-grid
  - achievement:offbrand
  - achievement:offgrid
  - best-agent
  - best-demo
  - community-choice
---

<div align="center">

# 🌍 GLOBAL LEADERS

### *Take the chair. Hold the line. Survive 2025.*

**A political-strategy game where a small language model runs the world —**
**and you govern a real leader through the real headlines of 2025.**

`🇺🇸 Trump` · `🇧🇷 Lula` · `🇷🇺 Putin` · `🇨🇳 Xi` · `🇦🇷 Milei` · `🇫🇷 Macron`

![hackathon](https://img.shields.io/badge/Build_Small-Thousand_Token_Wood-33ff88?style=for-the-badge)
![model](https://img.shields.io/badge/NVIDIA_Nemotron-≤32B-76b900?style=for-the-badge&logo=nvidia&logoColor=white)
![gradio](https://img.shields.io/badge/Gradio-6.x-ffb000?style=for-the-badge&logo=gradio&logoColor=black)
![local](https://img.shields.io/badge/Runs-100%25_Local_capable-7fd1ff?style=for-the-badge)

</div>

---

```
╔══════════════════════════════════════════════════════════════════════╗
║  ● GLOBAL LEADERS            FRANCE · EMMANUEL MACRON         JUL 2025  ║
╠══════════════════════════════════════════════════════════════════════╣
║  ▸ EU-US TRADE DEAL COLLAPSES AMID TARIFFS                             ║
║    Washington slaps 20% on European exports. Brussels wants you to     ║
║    retaliate; your industries want a deal; the markets want calm.      ║
║                                                                        ║
║    🔴 Le Pen: "Let his government crumble — we inherit the wreckage."  ║
║    🟡 EU Commission: "Hold the line, or the bloc fractures."           ║
║                                                                        ║
║    ▶ Pivot to strategic autonomy   ▶ Seek a US exemption   ✎ your move ║
╚══════════════════════════════════════════════════════════════════════╝
```

You take over a **real world leader on 1 January 2025** and govern for **twelve months**, reacting to
the real events of that year. A small model (**NVIDIA Nemotron**, ≤32B) is the game master: it writes
your objectives, voices your cabinet and your rivals, narrates each crisis and judges your decisions.
Pick a suggested move **or type your own** — it interprets anything you throw at it.

> 🏆 Built for the **Build Small / Thousand Token Wood** hackathon. The whole point: do something rich,
> reliable and *fun* with a small, cheap, **local-capable** model.

---

## ⚙️ Why this is a *small-model* project (the secret sauce)

LLM games usually fail because the model has to *be* the rules engine — and small models are bad at
arithmetic, state and consistency. **We invert it:**

| | |
|---|---|
| 🧠 **The code is the source of truth** | A deterministic Python engine owns the 8 indicators, hidden faction meters, the dice, win/lose logic and every guardrail. |
| ✍️ **The model only narrates & proposes** | Always through a **validated JSON schema** — parsed, validated, **retried** on failure. |
| 🛡️ **Guardrails clamp creativity** | The engine clamps proposed effects to legal ranges, enforces a *no-free-lunch* trade-off, rolls an uncertainty die, then applies. The model can be wild; it can't break the game. |
| 🪶 **Token-frugal by design** | Reasoning off (`think:false`), history compressed to a rolling digest, tight role-specific prompts. The header shows your live **token count**. |
| 🔌 **Never crashes** | No key? A deterministic `FakeLLM` produces schema-valid output, so the demo always runs — perfect for offline judging. |

The payoff: a **≤32B model reliably runs a 6-country political sim** with named real figures, branching
consequences, hidden coups and early game-overs.

---

## 🎮 What you can do

- **🪑 Pick your chair** — 6 leaders, each with a curated deck of **real 2025 events** (domestic *and*
  international) and an 8–12 person cast of real figures.
- **⚖️ Make case-method calls** — no single right answer, incomplete information, conflicting stakeholders.
- **♟️ Play the game theory** — every figure has its own utility vector and a written persona (in
  [`engine/prompts/countries/`](engine/prompts/countries)); they reward or punish you based on *their*
  interests, not yours.
- **🍽️ Take rivals to lunch** — pull any figure off the record and ask what they really want before you
  commit. They're franker in private… but still themselves.
- **💀 Fall in more ways than one** — democracies face impeachment, autocracies a palace collapse, China
  a **PLA coup** if you lose the army. Misread who truly holds power and your term ends early.
- **🏅 Win the term** — reach December having met **6 / 8 objectives** for *a defining term*.

### Choose your difficulty

| Leader | Nation | Difficulty |
|---|---|---|
| Donald Trump | 🇺🇸 United States | 🟢 Approachable |
| Luiz Inácio Lula da Silva | 🇧🇷 Brazil | 🟢 Approachable |
| Vladimir Putin | 🇷🇺 Russia | 🟡 Challenging |
| Xi Jinping | 🇨🇳 China | 🔴 Brutal *(hidden coup)* |
| Javier Milei | 🇦🇷 Argentina | 🔴 Brutal |
| Emmanuel Macron | 🇫🇷 France | 🔴 Brutal |

---

## 🚀 Run it

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -r requirements.txt
python app.py            # → http://127.0.0.1:7860
```

### 🔌 Model backend — three ways to run

Copy `.env.example` → `.env` and pick one:

**🛰️ Off the grid — the real way to play: local NVIDIA Nemotron, no key, nothing leaves your machine**
*(this is the hackathon's "Off the Grid" quest — a ≤32B model running entirely on your own hardware):*

```bash
ollama pull nemotron-3-nano:30b    # the 30B NVIDIA Nemotron this game is tuned for
```
```ini
# .env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=nemotron-3-nano:30b   # (any ≤32B model works too: qwen3, gemma3 …)
```
No API key. On startup the app **pre-checks** that Ollama is running and the model is pulled, and tells
you exactly what to fix otherwise (no silent fallback). The header shows `🛰️ local Ollama` so you know
the real model is driving the game.

**🎭 No setup at all** — with no local Ollama, the app runs the deterministic `FakeLLM` stub so the demo
still plays end to end (great for a quick look; not the real model).

> ▶️ **The hosted Hugging Face Space runs the real game** — NVIDIA Nemotron 30B-A3B on a **dedicated
> L40S GPU we self-host on [Modal](https://modal.com)** ([`modal_ollama.py`](modal_ollama.py): the
> stock Ollama image + the model in a persistent Volume, per-second billing, scale-to-zero). The Space
> itself stays on free CPU hardware and just points `OLLAMA_HOST` at that endpoint — the engine can't
> tell it apart from a local Ollama. Prefer to play **off the grid**? Clone the repo and point it at
> your own local Ollama (no key, nothing leaves your machine) as above.

---

## 🧪 Tests

```bash
python -m unittest discover -s tests        # 28 tests, no third-party deps
```

## 🗂️ Project layout

| Path | What |
|------|------|
| [`engine/`](engine) | deterministic engine: state, dice, resolver, schemas, agents, events, seeds |
| [`engine/llm*.py`](engine) | the model boundary (Protocol, Nemotron/OpenRouter backends, FakeLLM) |
| [`engine/prompts/countries/`](engine/prompts/countries) | every figure's canonical persona — interests + voice |
| [`seeds/`](seeds) | curated real-2025 event decks per country + shared global events |
| [`app.py`](app.py) | the Situation-Room Gradio UI |
| `GAME_DESIGN.md` · `GAME_RULES.md` · `COUNTRY_SCENARIOS.md` | design docs |

<div align="center">

---

*The model proposes. The code decides. History is yours to rewrite.*

</div>
