---
title: Global Leaders
emoji: 🌍
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
pinned: false
license: mit
short_description: Govern a real 2025 world leader for 12 months — a small model narrates, judges and roleplays your cabinet.
---

<div align="center">

# 🌍 GLOBAL LEADERS

### *Take the chair. Hold the line. Survive 2025.*

**A political-strategy game where a small language model runs the world —**
**and you govern a real leader through the real headlines of 2025.**

`🇺🇸 Trump` · `🇧🇷 Lula` · `🇷🇺 Putin` · `🇨🇳 Xi` · `🇦🇷 Milei` · `🇫🇷 Macron`

![hackathon](https://img.shields.io/badge/Build_Small-Thousand_Token_Wood-33ff88?style=for-the-badge)
![model](https://img.shields.io/badge/NVIDIA_Nemotron-≤32B-76b900?style=for-the-badge&logo=nvidia&logoColor=white)
![gradio](https://img.shields.io/badge/Gradio-5.x-ffb000?style=for-the-badge&logo=gradio&logoColor=black)
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

**🛰️ Off the grid — fully local, no key, nothing leaves your machine** *(the recommended way to see
the real ≤32B experience — and the hackathon's "Off the Grid" quest):*

```bash
ollama pull nemotron-mini          # or any ≤32B model you have: qwen3, gemma3, llama3.2 …
```
```ini
# .env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=nemotron-mini         # exactly what you pulled
```
No API key needed. On startup the app **pre-checks** that Ollama is running and the model is pulled,
and tells you exactly what to fix otherwise (no silent fallback). The header shows
`🛰️ local Ollama` so you know the real model is driving the game.

**☁️ Ollama Cloud** — same code, hosted Nemotron:

```ini
OLLAMA_API_KEY=...                 # https://ollama.com/settings/keys
```

**🎭 No setup at all** — with no key and no local Ollama, the app runs the deterministic `FakeLLM`
stub so the demo still plays end to end (great for a quick look; not the real model).

> ⚠️ **On the hosted Hugging Face Space** there's no GPU, so the Space can't run a ≤32B model itself —
> it uses Ollama Cloud (or the FakeLLM demo). **To experience the real local model, clone this repo and
> run it with your own Ollama** as above. It's the same code either way.

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
| [`scripts/`](scripts) | research/curation harness, persona generator, headless playtest, sfx generator |
| [`app.py`](app.py) | the Situation-Room Gradio UI |
| `GAME_DESIGN.md` · `GAME_RULES.md` · `COUNTRY_SCENARIOS.md` | design docs |

<div align="center">

---

*The model proposes. The code decides. History is yours to rewrite.*

</div>
