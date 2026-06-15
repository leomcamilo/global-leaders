"""Global Leaders — Gradio app (HuggingFace Space entrypoint).

Situation-Room UI over the headless engine. Backend: Ollama Cloud (Nemotron) if
OLLAMA_API_KEY is set, otherwise the deterministic FakeLLM so the demo always runs.

Handlers return {component: gr.update(...)} dicts (robust with this many components) and
the slow ones are generators that first yield a "deliberating" state, then the result.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

import gradio as gr

from engine.countries import COUNTRIES, get_country
from engine.game import Game
from engine.llm import FakeLLM
from engine.schemas import Option
from engine.state import INDICATOR_LABELS

BASE = os.path.dirname(os.path.abspath(__file__))
SFX = {k: os.path.join(BASE, "assets", "sfx", f"{k}.wav")
       for k in ("blip", "backfire", "windfall", "gameover", "victory")}

MONTHS = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
STANCE_DOT = {"hostile": "🔴", "neutral": "🟡", "allied": "🟢"}
FACTION_LABELS = {"party_loyalty": "Party loyalty", "pla_loyalty": "PLA loyalty",
                  "coup_plot_progress": "Coup plot"}
DIFF = {"approachable": ("🟢", "Approachable"), "challenging": ("🟡", "Challenging"),
        "brutal": ("🔴", "Brutal")}
CAB_MAX = 12  # largest roster (USA); we build this many buttons and show/hide per country


def load_dotenv() -> None:
    path = os.path.join(BASE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _ollama_models(host: str):
    """Models installed on a local Ollama, or None if it isn't reachable. Lets us label clearly
    instead of silently dropping to FakeLLM when Ollama is down or the model wasn't pulled."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=2.0) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:  # noqa: BLE001
        return None


def make_llm():
    load_dotenv()
    host = os.environ.get("OLLAMA_HOST", "")
    is_local = bool(host) and "ollama.com" not in host
    # Our Modal endpoint (modal_ollama.py) scales to zero and wakes on demand, so the
    # quick preflight below would flunk it while asleep — skip it and let the backend's
    # retries absorb the one slow wake-up call.
    is_modal = "modal.run" in host
    has_cloud = bool(os.environ.get("OLLAMA_API_KEY"))
    if has_cloud or is_local:
        try:
            from engine.llm_remote import OLLAMA_DEFAULT_MODEL, OllamaCloudLLM
            model = os.environ.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
            if is_local and not is_modal:  # preflight: catch "Ollama not running" / "model not pulled"
                installed = _ollama_models(host)
                if installed is None:
                    return FakeLLM(), f"FakeLLM — local Ollama not reachable at {host} (is it running?)"
                if not any(m.split(":")[0] == model.split(":")[0] for m in installed):
                    return FakeLLM(), f"FakeLLM — model '{model}' not pulled (run: ollama pull {model})"
            where = ("dedicated GPU · Modal ⚡" if is_modal
                     else "local Ollama 🛰️" if is_local else "Ollama Cloud ☁️")
            tag = f"{model} · {where} · ≤32B"
            # Modal cold boot can take ~80s; give one call enough room to ride it out
            # (the warm-up usually beats it) before any retry/fallback kicks in.
            timeout = 180 if is_modal else 120
            return OllamaCloudLLM(model=model, fallback=FakeLLM(), verbose=False, timeout=timeout), tag
        except Exception:  # noqa: BLE001
            pass
    return FakeLLM(), "FakeLLM (offline demo)"


# --- HTML renderers -------------------------------------------------------------

def _bar_color(v: int) -> str:
    if v < 30:
        return "#ff4d4d"
    if v < 55:
        return "#ffb000"
    return "#33ff88"


def render_header(g: Game) -> str:
    s = g.state
    tok = getattr(g.llm, "total_tokens", 0)
    tok_txt = f"<span class='hdr-tok'>⛁ {tok:,} tok</span>" if tok else ""
    return (f"<div class='hdr'><span class='glow'>● GLOBAL LEADERS</span>"
            f"<span class='hdr-mid'>{g.country.name.upper()} · {g.country.leader}</span>"
            f"<span class='hdr-r'>{MONTHS[min(s.month,12)]} 2025 {tok_txt}</span></div>")


def render_indicators(g: Game) -> str:
    s = g.state
    rows = []
    for key, label in INDICATOR_LABELS.items():
        v = s.indicators[key]
        rows.append(
            f"<div class='ind'><span class='lbl'>{label}</span>"
            f"<div class='bar'><div class='fill' style='width:{v}%;background:{_bar_color(v)}'></div></div>"
            f"<span class='val'>{v}</span></div>")
    extra = ""
    if s.factions:
        fr = []
        for key, lab in FACTION_LABELS.items():
            if key in s.factions:
                v = s.factions[key]
                fr.append(f"<div class='ind faint'><span class='lbl'>{lab}</span>"
                          f"<div class='bar'><div class='fill' style='width:{v}%;background:{_bar_color(v)}'></div></div>"
                          f"<span class='val'>{v}</span></div>")
        extra = "<div class='sec-title'>// classified</div>" + "".join(fr)
    return f"<div class='panel'><div class='sec-title'>// nation status</div>{''.join(rows)}{extra}</div>"


def render_cabinet_title(g: Game) -> str:
    return ("<div class='panel pad-b0'><div class='sec-title'>// the room — click a name</div>"
            "<div class='hint'>Each button below takes that figure to a private, off-the-record lunch. "
            "🟢 allied · 🟡 neutral · 🔴 hostile.</div></div>")


def render_lunch_header(g: Game, f) -> str:
    stance = g.state.agent_stances.get(f.key, "neutral")
    cv = g.state.cast.get(f.key, {}).get("core_value", "")
    return (f"<div class='event lunch'><div class='headline'>🍽 Lunch with {STANCE_DOT[stance]} {f.name}</div>"
            f"<div class='narr'><b>{f.role}</b>"
            + (f" — <span class='cv'>“{cv}”</span>" if cv else "") + "<br>"
            "Off the record. Ask what they really want, where they stand, what they'd trade. "
            "They'll be franker here than in public — but they're still themselves.</div></div>")


def render_objectives(g: Game) -> str:
    rows = []
    for o in g.state.objectives:
        met = o.is_met(g.state)
        mark = "<span class='ok'>✓</span>" if met else "<span class='no'>○</span>"
        rows.append(f"<div class='obj'>{mark} {o.title} <span class='diff'>{o.difficulty}</span></div>")
    n = g.state.objectives_met()
    return (f"<div class='panel'><div class='sec-title'>// mandate — {n}/8</div>{''.join(rows)}</div>")


def render_event(g: Game, narration) -> str:
    quotes = "".join(
        f"<div class='quote'>{STANCE_DOT.get(r.stance,'🟡')} "
        f"<b>{g.country.agents[r.agent].name if r.agent in g.country.agents else r.agent}:</b> "
        f"“{r.quote}”</div>" for r in narration.agent_reactions)
    return (f"<div class='event'><div class='headline'>▸ {narration.headline}</div>"
            f"<div class='narr'>{narration.narrative}</div>{quotes}"
            f"<div class='stakes'>⚠ {narration.stakes}</div></div>")


def render_result(g: Game, judge, result) -> str:
    if result.mode == "rejected":
        return f"<div class='event result'><div class='headline'>↳ outcome</div><div class='narr'>{result.note}</div></div>"
    deltas = " ".join(
        f"<span class='{'up' if v>=0 else 'dn'}'>{INDICATOR_LABELS.get(k,k)} {'+' if v>=0 else ''}{v}</span>"
        for k, v in result.applied.items() if v)
    tag = {"backfire": "<span class='bf'>💥 BACKFIRED</span>",
           "windfall": "<span class='wf'>✨ WINDFALL</span>"}.get(result.mode, "")
    cls = {"backfire": " shake", "windfall": " glow"}.get(result.mode, "")
    return (f"<div class='event result{cls}'><div class='headline'>↳ outcome</div>"
            f"<div class='narr'>{judge.consequence_narrative} {tag}</div>"
            f"<div class='deltas'>{deltas}</div></div>")


ENDINGS = {"victory": "A DEFINING TERM", "mixed_term": "A DIVIDED LEGACY",
           "failed_term": "A WASTED MANDATE", "pla_coup": "THE GUN TURNED",
           "party_ouster": "PURGED BY THE PARTY", "removed_from_office": "REMOVED FROM OFFICE",
           "palace_collapse": "THE REGIME CONVULSES", "terminal_crisis": "THE STATE COLLAPSES",
           "economic_meltdown": "ECONOMIC MELTDOWN"}


def render_over(g: Game) -> str:
    s = g.state
    title = ENDINGS.get(s.game_over, s.game_over.upper())
    fate = "survived to December" if s.month >= 12 else f"fell in {MONTHS[min(s.month,12)]}"
    return (f"<div class='event over'><div class='headline big'>☠ {title}</div>"
            f"<div class='narr'>{s.ending_text}</div>"
            f"<div class='stakes'>Objectives met: {s.objectives_met()}/8 · {fate}</div></div>")


def share_text(g: Game) -> str:
    s = g.state
    title = ENDINGS.get(s.game_over, s.game_over.upper())
    fate = "survived to December" if s.month >= 12 else f"fell in {MONTHS[min(s.month,12)]}"
    return (f"🌍 GLOBAL LEADERS — I governed {g.country.name} as {g.country.leader} in 2025.\n"
            f"Result: {title} · {s.objectives_met()}/8 objectives · {fate}.\n"
            f"A ≤32B model ran the world. Play your own term 👉 [your Space URL]")


# --- session ----------------------------------------------------------------

def present_next(sess: dict) -> None:
    g: Game = sess["game"]
    while not sess["queue"]:
        g.end_month()
        if g.is_over:
            sess["phase"] = "over"
            return
        sess["queue"] = g.month_events()
    ev = sess["queue"].pop(0)
    narr, opts = g.present(ev)
    sess.update(current=ev, narration=narr, options=opts, phase="decide")


def new_session(country_key: str):
    llm, _ = make_llm()
    g = Game(country_key, llm, seed=2025)
    g.start()
    sess = {"game": g, "queue": g.month_events(), "current": None, "narration": None,
            "options": [], "phase": "decide", "judge": None, "result": None,
            "mode": "event", "lunch_target": None}
    present_next(sess)
    return sess


# --- unified render (returns {component: update}) -------------------------------

def _sound_for(sess) -> str | None:
    phase = sess["phase"]
    if phase == "over":
        return SFX["victory"] if sess["game"].state.game_over == "victory" else SFX["gameover"]
    if phase == "result":
        return SFX.get(sess["result"].mode, SFX["blip"]) if sess.get("result") else SFX["blip"]
    return None


def render_screen(sess: dict, screen: str, busy: str | None = None, pending_q: str | None = None):
    """Full set of component updates for a screen. Always sets every UI component so state never
    goes stale. `busy` shows the deliberating banner and hides action buttons; `pending_q` shows a
    just-asked lunch question with a typing bubble."""
    u = {
        onboarding_group: gr.update(visible=screen == "onboarding"),
        setup_group: gr.update(visible=screen == "setup"),
        game_group: gr.update(visible=screen == "game"),
        status_html: (gr.update(value=f"<div class='busy'>◌ {busy}</div>", visible=True)
                      if busy else gr.update(value="", visible=False)),
        sfx_audio: gr.update(value=None),
        # event widgets default hidden; filled below for the game screen
        event_html: gr.update(visible=False),
        options_radio: gr.update(visible=False),
        freetext: gr.update(visible=False),
        decide_btn: gr.update(visible=False),
        result_html: gr.update(visible=False),
        continue_btn: gr.update(visible=False),
        share_box: gr.update(visible=False),
        lunch_panel: gr.update(visible=False),
        lunch_header_html: gr.update(),
        lunch_chat: gr.update(),
        lunch_q: gr.update(),
        lunch_send: gr.update(visible=False),
        lunch_back: gr.update(visible=False),
        header_html: gr.update(),
        indicators_html: gr.update(),
        objectives_html: gr.update(),
        cabinet_title_html: gr.update(),
    }
    for b in cab_btns:
        u[b] = gr.update(visible=False)

    if screen != "game" or not sess:
        return u

    g: Game = sess["game"]
    phase, mode = sess["phase"], sess.get("mode", "event")
    u[header_html] = gr.update(value=render_header(g))
    u[indicators_html] = gr.update(value=render_indicators(g))
    u[objectives_html] = gr.update(value=render_objectives(g))
    u[cabinet_title_html] = gr.update(value=render_cabinet_title(g))
    roster = g.country.roster
    for i, b in enumerate(cab_btns):
        if i < len(roster):
            f = roster[i]
            stance = g.state.agent_stances.get(f.key, "neutral")
            u[b] = gr.update(value=f"{STANCE_DOT[stance]} {f.name}", visible=True)
        else:
            u[b] = gr.update(visible=False)

    # Event-mode widgets.
    if phase == "over":
        u[event_html] = gr.update(value=render_over(g), visible=True)
        u[result_html] = gr.update(value="", visible=False)
        u[continue_btn] = gr.update(value="↻ New game", visible=True)
        u[share_box] = gr.update(value=share_text(g), visible=True)
    elif phase == "result":
        u[event_html] = gr.update(value=render_event(g, sess["narration"]), visible=True)
        u[result_html] = gr.update(value=render_result(g, sess["judge"], sess["result"]), visible=True)
        u[continue_btn] = gr.update(value="Continue →", visible=True)
    else:  # decide
        choices = [f"{o.id}) {o.label}" for o in sess["options"]]
        u[event_html] = gr.update(value=render_event(g, sess["narration"]), visible=True)
        u[options_radio] = gr.update(choices=choices, value=None, visible=True)
        u[freetext] = gr.update(value="", visible=True)
        u[decide_btn] = gr.update(visible=True)

    # Lunch panel takes over the centre column while dining.
    if mode == "lunch" and sess.get("lunch_target"):
        target = sess["lunch_target"]
        f = g.country.agents[target]
        msgs = []
        for h in g.conversations.get(target, []):
            msgs += [{"role": "user", "content": h["q"]}, {"role": "assistant", "content": h["a"]}]
        if pending_q:
            msgs += [{"role": "user", "content": pending_q}, {"role": "assistant", "content": "…"}]
        u[lunch_panel] = gr.update(visible=True)
        u[lunch_header_html] = gr.update(value=render_lunch_header(g, f))
        u[lunch_chat] = gr.update(value=msgs)
        u[lunch_q] = gr.update(value="")
        u[lunch_send] = gr.update(visible=not busy)
        u[lunch_back] = gr.update(visible=not busy)
        for w in (event_html, options_radio, freetext, decide_btn, result_html, continue_btn):
            u[w] = gr.update(visible=False)

    # Sound + busy gating.
    if busy:
        for w in (decide_btn, continue_btn, lunch_send):
            u[w] = gr.update(visible=False)
    else:
        snd = _sound_for(sess)
        if snd:
            u[sfx_audio] = gr.update(value=snd)
    return u


# --- backend warm-up ------------------------------------------------------------

_last_warm = [0.0]  # monotonic timestamp of the last warm-up nudge (debounce)


def warm_backend():
    """Fire-and-forget: wake the scale-to-zero Modal GPU endpoint and preload the
    model into VRAM, so it's hot by the time the player's first move is judged.
    A cold boot can take ~80s; firing this on page load and on BEGIN buys that time
    while the player reads the briefing and picks a nation. No-op unless we're
    pointed at the remote Modal endpoint. Debounced to at most once per 60s."""
    host = os.environ.get("OLLAMA_HOST", "")
    if "modal.run" not in host:  # only the scale-to-zero endpoint needs waking
        return
    now = time.monotonic()
    if now - _last_warm[0] < 60:
        return
    _last_warm[0] = now
    model = os.environ.get("OLLAMA_MODEL", "nemotron-3-nano:30b")

    def _go():
        try:
            req = urllib.request.Request(
                host.rstrip("/") + "/api/generate",
                data=json.dumps({"model": model, "keep_alive": -1}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=180)  # holds during the cold boot; result ignored
        except Exception:  # noqa: BLE001 — best-effort; the real call will retry if needed
            pass

    threading.Thread(target=_go, daemon=True).start()


# --- handlers (slow ones are generators: yield busy -> yield result) ------------

def on_begin(sess):
    warm_backend()  # nudge the GPU awake while the player reads the setup screen
    return {state_box: None, **render_screen(None, "setup")}


def on_start(country_key, sess):
    yield {state_box: sess, **render_loading("Briefing the Situation Room — drafting your mandate, "
                                             "cabinet and first crisis…")}
    sess = new_session(country_key)
    yield {state_box: sess, **render_screen(sess, "game")}


def render_loading(msg: str):
    """A standalone loading view on the game screen (used before a session exists)."""
    u = render_screen(None, "game", busy=msg)
    u[game_group] = gr.update(visible=True)
    return u


def on_decide(choice, free_text, sess):
    if not sess or sess["phase"] != "decide" or sess.get("mode") == "lunch":
        yield {state_box: sess, **render_screen(sess, "game")}
        return
    g: Game = sess["game"]
    action = None
    if free_text and free_text.strip():
        action = free_text.strip()
    elif choice:
        oid = choice.split(")")[0]
        action = next((o for o in sess["options"] if o.id == oid), None)
    if action is None:
        yield {state_box: sess, **render_screen(sess, "game")}
        return
    yield {state_box: sess, **render_screen(sess, "game", busy="The room weighs your move…")}
    judge, result = g.act(sess["current"], action)
    sess.update(judge=judge, result=result, phase="over" if g.is_over else "result")
    yield {state_box: sess, **render_screen(sess, "game")}


def on_continue(sess):
    if not sess:
        yield {state_box: None, **render_screen(None, "onboarding")}
        return
    if sess["phase"] == "over":
        yield {state_box: None, **render_screen(None, "setup")}
        return
    yield {state_box: sess, **render_screen(sess, "game", busy="The month turns — the world moves…")}
    present_next(sess)
    yield {state_box: sess, **render_screen(sess, "game")}


def on_lunch_open(i, sess):
    if not sess or sess["phase"] == "over" or i >= len(sess["game"].country.roster):
        return {state_box: sess, **render_screen(sess, "game")}
    sess["mode"] = "lunch"
    sess["lunch_target"] = sess["game"].country.roster[i].key
    return {state_box: sess, **render_screen(sess, "game")}


def on_lunch_send(question, sess):
    q = (question or "").strip()
    if not sess or sess.get("mode") != "lunch" or not sess.get("lunch_target") or not q:
        yield {state_box: sess, **render_screen(sess, "game")}
        return
    yield {state_box: sess, **render_screen(sess, "game", busy="They consider you across the table…",
                                            pending_q=q)}
    sess["game"].converse(sess["lunch_target"], q)
    yield {state_box: sess, **render_screen(sess, "game")}


def on_lunch_back(sess):
    if sess:
        sess["mode"] = "event"
        sess["lunch_target"] = None
    return {state_box: sess, **render_screen(sess, "game")}


# --- CSS (Situation Room) -------------------------------------------------------

CSS = """
:root { --grn:#33ff88; --amb:#ffb000; --bg:#070b09; --panel:#0d140f; --dim:#7da78c; }
/* dark fills the WHOLE viewport at any size (not just the centred column) */
html, body, gradio-app, .gradio-container, .main, .wrap, .contain, .app {
  background:var(--bg)!important; }
gradio-app { display:block; min-height:100vh; }
body { margin:0!important; }
.gradio-container { font-family:'JetBrains Mono','Courier New',monospace!important;
  color:var(--grn)!important; max-width:1180px!important; width:100%!important; margin:0 auto!important;
  padding:0 14px 40px!important; box-sizing:border-box; position:relative; }
.gradio-container::after { content:''; position:fixed; inset:0; pointer-events:none; z-index:50;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,0) 0,rgba(0,0,0,0) 2px,rgba(0,0,0,.18) 3px,rgba(0,0,0,0) 4px);
  opacity:.35; }
#sfx { display:none!important; }
#title { text-align:center; color:var(--amb); letter-spacing:3px; font-size:13px; opacity:.7; }
.hdr { display:flex; justify-content:space-between; align-items:center; border:1px solid #1d2a20; background:#0a110c;
  padding:8px 14px; letter-spacing:2px; }
.hdr .glow { color:var(--grn); text-shadow:0 0 8px var(--grn); animation:pulse 2.4s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }
.hdr-mid { color:#cfe; } .hdr-r { color:var(--amb); }
.hdr-tok { color:var(--dim); font-size:11px; margin-left:8px; }
.busy { color:var(--amb); border:1px dashed #3a4d2f; background:#0a110c; padding:10px 14px; letter-spacing:1px;
  font-size:13px; animation:blink 1s steps(2,start) infinite; }
@keyframes blink { 50%{opacity:.4} }
.panel { background:var(--panel); border:1px solid #1d2a20; padding:10px 12px; margin-bottom:8px; }
.panel.pad-b0 { padding-bottom:4px; margin-bottom:2px; }
.sec-title { color:var(--dim); font-size:11px; letter-spacing:2px; margin-bottom:6px; text-transform:uppercase; }
.hint { color:var(--dim); font-size:11px; line-height:1.4; margin-bottom:4px; }
.legend { color:var(--dim); font-size:11px; margin-top:6px; }
.ind { display:flex; align-items:center; gap:8px; margin:3px 0; font-size:12px; }
.ind.faint { opacity:.85; }
.ind .lbl { width:110px; color:#bfe; } .ind .val { width:26px; text-align:right; color:#fff; }
.bar { flex:1; height:9px; background:#11251a; border:1px solid #1d3a2a; }
.fill { height:100%; box-shadow:0 0 6px currentColor; transition:width .5s ease; }
.cv { color:var(--amb); font-style:italic; }
.obj { font-size:12px; margin:3px 0; color:#cfe; } .obj .ok { color:var(--grn); } .obj .no { color:var(--dim); }
.obj .diff { color:var(--dim); font-size:10px; float:right; }
.event { background:#0a110c; border:1px solid #243a2b; border-left:3px solid var(--amb); padding:14px 16px;
  animation:slidein .35s ease; }
@keyframes slidein { from{opacity:0; transform:translateY(6px)} to{opacity:1; transform:none} }
.event.result { border-left-color:var(--grn); } .event.over { border-left-color:#ff4d4d; text-align:center; }
.event.lunch { border-left-color:#7fd1ff; }
.event.result.shake { animation:shake .4s ease; border-left-color:#ff6b6b; }
@keyframes shake { 0%,100%{transform:none} 20%{transform:translateX(-5px)} 40%{transform:translateX(5px)}
  60%{transform:translateX(-3px)} 80%{transform:translateX(3px)} }
.event.result.glow { animation:glowpulse 1.2s ease; }
@keyframes glowpulse { 0%,100%{box-shadow:none} 50%{box-shadow:0 0 22px rgba(51,255,136,.5)} }
.headline { color:var(--amb); font-size:17px; margin-bottom:10px; text-shadow:0 0 6px rgba(255,176,0,.4); }
.headline.big { font-size:24px; color:#ff6b6b; }
.narr { color:#dfeee6; line-height:1.55; font-size:13px; }
.narr b, .narr strong, .event b, .event strong { color:#ffffff!important; font-weight:700; }
.quote { margin:8px 0; padding-left:10px; border-left:1px solid #2a4030; color:#bcd; font-size:12px; }
.stakes { margin-top:10px; color:var(--amb); font-size:12px; }
.deltas { margin-top:10px; } .deltas .up{color:var(--grn);margin-right:10px;} .deltas .dn{color:#ff6b6b;margin-right:10px;}
.bf{color:#ff6b6b;} .wf{color:var(--grn);}
.cabbtn button { background:#0e1812!important; border:1px solid #244033!important; color:#dfeee6!important;
  text-align:left!important; font-size:12px!important; padding:7px 10px!important; margin:3px 0!important;
  font-family:inherit!important; justify-content:flex-start!important; cursor:pointer!important;
  width:100%!important; border-radius:0!important; transition:all .15s; }
.cabbtn button:hover { border-color:var(--amb)!important; color:#fff!important; background:#15241a!important;
  box-shadow:0 0 8px rgba(255,176,0,.25); transform:translateX(2px); }
@media (max-width:760px){ .gradio-container .gap > div { flex-direction:column!important; } }
/* Safety net: if the visitor's browser is in LIGHT mode, Gradio's native widgets
   (the move input, the leader picker, the dropdown, the lunch chat) would render
   DARK text on our always-dark panels and vanish. Force their colours light here,
   regardless of mode — this backs up the force-dark JS in case JS is blocked. */
.gradio-container, gradio-app {
  /* text */
  --body-text-color:#dfeee6!important; --body-text-color-subdued:#bcd9c9!important;
  --input-text-color:#eafff4!important; --input-placeholder-color:#6f8d7b!important;
  --block-title-text-color:#cfe!important; --block-label-text-color:#cfe!important;
  --button-secondary-text-color:#eafff4!important; --checkbox-label-text-color:#eafff4!important;
  /* backgrounds — force dark in BOTH modes so native widgets (the options Radio,
     the move box, the Room buttons, labels) stop rendering light-on-light */
  --background-fill-primary:#070b09!important; --background-fill-secondary:#0a110c!important;
  --block-background-fill:#0d140f!important; --panel-background-fill:#0d140f!important;
  --block-label-background-fill:#0a110c!important;
  --input-background-fill:#0a110c!important; --input-background-fill-focus:#0e1812!important;
  --button-secondary-background-fill:#0e1812!important; --button-secondary-background-fill-hover:#15241a!important;
  --checkbox-background-color:#0a110c!important; --checkbox-background-color-selected:#15241a!important;
  --checkbox-label-background-fill:#0d140f!important; --checkbox-label-background-fill-hover:#15241a!important;
  --checkbox-label-background-fill-selected:#15241a!important;
  /* borders */
  --border-color-primary:#1d2a20!important; --border-color-secondary:#1d2a20!important; }
.gradio-container textarea, .gradio-container input[type="text"], .gradio-container input:not([type]),
.gradio-container select { color:#eafff4!important; background:#0a110c!important; }
.gradio-container label, .gradio-container fieldset span, .gradio-container .prose,
.gradio-container .message, .gradio-container .message-row { color:#dfeee6!important; }
.gradio-container input::placeholder, .gradio-container textarea::placeholder { color:#5f7d6b!important; }
/* Country dropdown: lock dark bg + light text on the box AND the options popup, in
   BOTH light & dark modes. The popup can render in a portal OUTSIDE .gradio-container,
   so these selectors are deliberately NOT scoped to it. */
ul.options { background:#0a110c!important; border:1px solid #1d2a20!important; }
ul.options li, [data-testid="dropdown-option"] { background:#0a110c!important; color:#eafff4!important; }
ul.options li .item-name, [data-testid="dropdown-option"] .item-name { color:#eafff4!important; }
ul.options li.active, ul.options li[aria-selected="true"], ul.options li:hover,
[data-testid="dropdown-option"].active, [data-testid="dropdown-option"]:hover {
  background:#15241a!important; color:#fff!important; }
"""

# Force Gradio's dark theme so its native widgets use light text on our dark panels,
# no matter the visitor's browser light/dark preference (one-time redirect on load).
FORCE_DARK_JS = """
() => {
  const u = new URL(window.location);
  if (u.searchParams.get('__theme') !== 'dark') {
    u.searchParams.set('__theme', 'dark');
    window.location.replace(u.href);
  }
}
"""

COUNTRY_CHOICES = [
    (f"{c.name} — {c.leader}   ·   {DIFF[c.difficulty][0]} {DIFF[c.difficulty][1]}", k)
    for k, c in COUNTRIES.items()
]
_, BACKEND_NAME = make_llm()


with gr.Blocks(title="Global Leaders") as demo:
    state_box = gr.State(None)
    sfx_audio = gr.Audio(visible=True, autoplay=True, show_label=False, elem_id="sfx",
                         interactive=False)
    gr.HTML(f"<div id='title'>━━ GLOBAL LEADERS · take office in 2025 · engine: {BACKEND_NAME} ━━</div>")

    with gr.Group(visible=True) as onboarding_group:
        gr.HTML(
            "<div class='event'>"
            "<div class='headline big'>▸ MISSION BRIEFING</div>"
            "<div class='narr'>You take over a <b>real world leader</b> on <b>1 January 2025</b> and govern "
            "for <b>12 months</b>, reacting to the real headlines of that year. A small AI model (≤32B) runs "
            "the world, voices your cabinet and rivals, judges your decisions, and moves the nation's numbers.</div>"
            "<div class='sec-title'>// how it works</div>"
            "<div class='narr'>▪ Each month brings real events (and fallout from your past moves). For each, "
            "pick a suggested option <b>or write your own decision</b> — the AI interprets it.<br>"
            "▪ Between calls, take any figure in <b>the Room</b> to a private lunch — ask what they really "
            "want and where they stand before you commit.<br>"
            "▪ Eight indicators — Economy, Approval, Security, Social cohesion, Public services, Fiscal health, "
            "International power, Institutions — rise and fall. There is <b>no single right answer</b>; every "
            "choice has trade-offs.<br>"
            "▪ Outcomes are <b>uncertain</b>: a decision can backfire 💥 or pay off beyond expectations ✨.</div>"
            "<div class='sec-title'>// how you win</div>"
            "<div class='narr'>You start with <b>8 personalized objectives</b>. Reach December having met "
            "<b>6+ → a defining term</b>; 3–5 → a divided legacy; fewer → a wasted mandate.</div>"
            "<div class='sec-title'>// how you fall — before December</div>"
            "<div class='narr'>▪ Democracies: approval <b>and</b> institutions in the gutter → impeachment / "
            "no-confidence / removal.<br>"
            "▪ Autocracies: a fracturing inner circle → palace collapse.<br>"
            "▪ Any key indicator in free-fall for two months → the state collapses.<br>"
            "▪ Country specials — every nation hides its own ways to fall: forces that never appear on the "
            "dashboard and rivals who move in the shadows. Misread who truly holds power and your term ends early.</div>"
            "<div class='stakes'>Your ministers, opposition and the public each pursue their own interests — "
            "keep the room on your side.</div></div>")
        begin_btn = gr.Button("▶ BEGIN", variant="primary")

    with gr.Group(visible=False) as setup_group:
        gr.HTML("<div class='event'><div class='headline'>▸ Choose the chair you'll take</div>"
                "<div class='narr'>Eight objectives, twelve months, real headlines. Govern — or fall before "
                "December.</div>"
                "<div class='legend'>Difficulty: 🟢 Approachable (USA, Brazil) · 🟡 Challenging (Russia) · "
                "🔴 Brutal (China, Argentina, France — can collapse early). First time? Take the USA or Brazil.</div></div>")
        country_dd = gr.Dropdown(COUNTRY_CHOICES, label="Nation", value="usa")
        start_btn = gr.Button("◉ TAKE OFFICE", variant="primary")

    with gr.Group(visible=False) as game_group:
        header_html = gr.HTML()
        status_html = gr.HTML(visible=False)
        with gr.Row():
            with gr.Column(scale=2):
                event_html = gr.HTML()
                options_radio = gr.Radio(label="Your options", choices=[], visible=False)
                freetext = gr.Textbox(label="…or write your own move", lines=2, visible=False,
                                      placeholder="e.g. Order a covert operation and address the nation tonight…")
                decide_btn = gr.Button("▶ DECIDE", variant="primary", visible=False)
                result_html = gr.HTML(visible=False)
                continue_btn = gr.Button("Continue →", visible=False)
                share_box = gr.Textbox(label="📋 Share your term (copy this)", lines=3, visible=False,
                                       interactive=True, buttons=["copy"])
                with gr.Group(visible=False) as lunch_panel:
                    lunch_header_html = gr.HTML()
                    lunch_chat = gr.Chatbot(label="The lunch", height=300, show_label=False)
                    lunch_q = gr.Textbox(label="Ask them", lines=1,
                                         placeholder="e.g. What would it take for you to back me on this?")
                    with gr.Row():
                        lunch_send = gr.Button("Say it →", variant="primary")
                        lunch_back = gr.Button("← Back to the Situation Room")
            with gr.Column(scale=1):
                indicators_html = gr.HTML()
                objectives_html = gr.HTML()
                cabinet_title_html = gr.HTML()
                cab_btns = [gr.Button(visible=False, elem_classes=["cabbtn"]) for _ in range(CAB_MAX)]

    OUT = [state_box, onboarding_group, setup_group, game_group, header_html, status_html,
           indicators_html, objectives_html, cabinet_title_html, event_html, options_radio,
           freetext, decide_btn, result_html, continue_btn, share_box, lunch_panel,
           lunch_header_html, lunch_chat, lunch_q, lunch_send, lunch_back, sfx_audio] + cab_btns

    demo.load(warm_backend)  # start waking the GPU the moment the page opens
    begin_btn.click(on_begin, [state_box], OUT)
    start_btn.click(on_start, [country_dd, state_box], OUT)
    decide_btn.click(on_decide, [options_radio, freetext, state_box], OUT)
    continue_btn.click(on_continue, [state_box], OUT)
    lunch_send.click(on_lunch_send, [lunch_q, state_box], OUT)
    lunch_q.submit(on_lunch_send, [lunch_q, state_box], OUT)
    lunch_back.click(on_lunch_back, [state_box], OUT)
    for _i, _btn in enumerate(cab_btns):
        _btn.click(lambda sess, i=_i: on_lunch_open(i, sess), [state_box], OUT)


if __name__ == "__main__":
    demo.launch(allowed_paths=[os.path.join(BASE, "assets")],
                css=CSS, theme=gr.themes.Base(), js=FORCE_DARK_JS)
