"""Prompt builders for the real-SLM path (GAME_RULES.md §0, §7).

Kept tight and explicit because the target models are small (≤32B). Each role gets:
the exact JSON shape, the allowed enum values, and the design principles (case method:
no right answer; game theory: stakeholders have payoffs). These same prompts are the
basis for the model benchmark later.
"""

from __future__ import annotations

from engine.countries import get_country
from engine.state import FACTION_KEYS, INDICATORS, WorldState
from engine.events import Event

TONES = ["bold", "cautious", "populist", "technocratic", "defiant", "conciliatory"]


def _valid_targets(state: WorldState) -> list[str]:
    keys = list(INDICATORS)
    if state.factions:
        keys += [k for k in FACTION_KEYS if k in state.factions]
    return keys


def _context(state: WorldState) -> str:
    c = get_country(state.country)
    lines = [
        f"Country: {c.name} | Leader: {c.leader} | Month: {state.month}/12 of 2025",
        "Indicators (0-100): " + ", ".join(f"{k}={v}" for k, v in state.indicators.items()),
    ]
    if state.factions:
        lines.append("Hidden faction meters (0-100, never state the numbers aloud): "
                     + ", ".join(f"{k}={v}" for k, v in state.factions.items()))
    if state.objectives:
        lines.append("Your objectives: " + "; ".join(
            f"{o.indicator} {o.op} {o.target}" for o in state.objectives))
    if state.agent_stances:
        agents = c.agents
        bits = []
        for k, stance in state.agent_stances.items():
            a = agents.get(k)
            persona = state.cast.get(k, {})
            extra = f", {persona['core_value']}" if persona.get("core_value") else ""
            if a and a.faction == "elite":
                lvl = "high" if a.influence >= 0.7 else "moderate" if a.influence >= 0.45 else "low"
                extra += f"; ELITE, influence={lvl} — their mood sways markets and the media here"
            bits.append(f"{k} ({a.name if a else k}{extra}): {stance}")
        lines.append("Cast & current stance: " + "; ".join(bits))
    lines.append("Recent history: " + state.history_digest())
    return "\n".join(lines)


def _event_block(event: Event) -> str:
    s = [f"EVENT: {event.title_seed}", f"What happened: {event.fact}"]
    if event.dilemma:
        s.append(f"The dilemma: {event.dilemma}")
    if event.hidden_info:
        s.append(f"Hidden (do NOT reveal as fact, only hint): {event.hidden_info}")
    if event.stakeholder_positions:
        s.append("Stakeholder positions: " + "; ".join(
            f"{k}: {v}" for k, v in event.stakeholder_positions.items()))
    return "\n".join(s)


def _agent_keys(state: WorldState) -> str:
    return ", ".join(get_country(state.country).agents.keys())


# --- System prompts -------------------------------------------------------------

GLOBAL_TONE = (
    "Global Leaders is a political-strategy game: serious and credible, with a dry, "
    "light wit. You never break character. Output ONLY a single JSON object — no markdown, "
    "no code fences, no commentary before or after."
)

OBJECTIVES_SYSTEM = (
    GLOBAL_TONE
    + " You are the game's scenario designer. Generate EXACTLY 8 year-end objectives that "
    "are personalised to this leader's real 2025 situation and measurable against the "
    "indicators. Mix achievable and hard goals. Each metric MUST be code-checkable."
)

CAST_SYSTEM = (
    GLOBAL_TONE
    + " You are the casting director. For each real political figure in this leader's orbit, write a "
    "compact persona: 2-3 vivid traits, a one-line core value, and a hidden agenda. You may nudge how "
    "strongly they react to outcomes via utility_shift (small numbers, each between -0.3 and +0.3, keyed "
    "by indicator). Stay true to the real person, but vary the nuances so no two playthroughs feel "
    "identical. Do NOT shift institutions (e.g. central banks)."
)

CONVERSE_SYSTEM = (
    GLOBAL_TONE
    + " You are ONE political figure, speaking IN CHARACTER to the leader over a private, "
    "off-the-record lunch — no aides, no press, no minutes taken. Because it is private you are "
    "franker than in public: you speak your real interests and read of the situation plainly. But "
    "you never stop being yourself — a hostile rival stays cutting, a loyalist stays warm, a wary "
    "general stays guarded. Stay true to the persona you are given and to your current stance toward "
    "the leader. Keep it to 2-4 sentences, first person, in their voice. Never quote the hidden meters "
    "or numbers; speak like a person, not a dashboard. Reply ONLY with a JSON object: "
    '{"reply": "what you say across the table"}.'
)

NARRATOR_SYSTEM = (
    GLOBAL_TONE
    + " You are the narrator. Present the current event as a case the leader must judge: "
    "a real, ambiguous situation with incomplete information and conflicting stakeholders. "
    "There is no single right answer. Give voice to the relevant cast members."
)

OPTIONS_SYSTEM = (
    GLOBAL_TONE
    + " You propose 2-4 distinct courses of action the leader could take. Each option should "
    "favour different stakeholders' interests (game theory), with real trade-offs."
)

JUDGE_SYSTEM = (
    GLOBAL_TONE
    + " You are the impartial judge. There is NO right answer and you must NEVER punish the "
    "player for diverging from real history — judge the coherence of their decision, how it "
    "fits their objectives, and how they handle the trade-offs. Propose how the decision moves "
    "the indicators. Magnitudes and their per-indicator delta ranges: minor 1-4, moderate 4-8, "
    "major 8-13, radical 13-20. Deltas will be clamped to the magnitude range, so stay within it. "
    "A major or radical decision MUST include at least one negative trade-off. Use plausibility "
    "'impossible' for physically impossible actions (no effect), 'absurd' for catastrophic "
    "overreach, otherwise 'ok'."
)


# --- User prompt builders -------------------------------------------------------

def objectives_user(country, state: WorldState) -> str:
    targets = _valid_targets(state)
    return (
        f"{_context(state)}\n\n"
        f"Valid indicator keys: {targets}\n"
        f"Valid ops: '>=', '<=', '>', '<'. Targets are integers 0-100.\n"
        "Make the 8 objectives WINNABLE but meaningful: about 2 easy, 4 medium, 2 hard. Anchor targets to "
        "the CURRENT values shown above — for an indicator that starts low (a country in crisis), prefer "
        "'hold above X' near its current value rather than a big jump. Do NOT set most targets far above the "
        "current state, and avoid targets above ~85.\n\n"
        'Return JSON: {"objectives": [{"id": "obj_1", "title": "...", "description": "...", '
        '"category": "<one indicator key>", "metric": {"indicator": "<key>", "op": ">=", '
        '"target": 60, "by_month": 12}, "difficulty": "easy|medium|hard"}, ... exactly 8]}'
    )


def cast_user(country, state: WorldState) -> str:
    targets = _valid_targets(state)
    roster = "\n".join(
        f"  - {f.key}: {f.name}, {f.role} ({f.faction}); cares about {', '.join(f.themes) or 'general'}"
        + ("" if f.adjustable else "  [institution — no utility_shift]")
        for f in country.roster
    )
    return (
        f"Country: {country.name} | Leader: {country.leader} | Early 2025.\n"
        f"The cast (use these exact keys):\n{roster}\n\n"
        f"Valid utility_shift indicator keys: {targets} (each value between -0.3 and 0.3).\n"
        f"Return EXACTLY one entry for EVERY figure listed above ({len(country.roster)} total), "
        "including institutions — for an institution just use an empty utility_shift {}.\n\n"
        'Return JSON: {"cast": [{"key": "<key>", "traits": ["...", "..."], "core_value": "one line", '
        '"hidden_agenda": "one line", "utility_shift": {"<indicator>": 0.2}}, ... one per figure]}'
    )


def converse_user(figure, persona: str | None, question: str, state: WorldState,
                  history: list[dict]) -> str:
    c = get_country(state.country)
    stance = state.agent_stances.get(figure.key, "neutral")
    cast = state.cast.get(figure.key, {})
    agenda = cast.get("hidden_agenda", "")
    who = (persona or f"{figure.name}, {figure.role}. Cares about: {', '.join(figure.themes) or 'general'}.")
    prior = ""
    if history:
        prior = "Earlier in this lunch:\n" + "\n".join(
            f"  Leader: {h['q']}\n  You: {h['a']}" for h in history[-4:]) + "\n\n"
    agenda_line = f"Your private agenda this game: {agenda}\n" if agenda else ""
    return (
        f"You are {figure.name} — {figure.role} in {c.name}, {c.leader}'s {state.month}/12 of 2025.\n\n"
        f"WHO YOU ARE:\n{who}\n\n"
        f"{agenda_line}"
        f"Your current stance toward {c.leader}: {stance.upper()} "
        f"(let it colour your warmth, candour and willingness to help).\n"
        f"What has happened lately: {state.history_digest()}\n\n"
        f"{prior}"
        f"The leader, across the table, says: \"{question}\"\n\n"
        f'Reply in character. JSON only: {{"reply": "..."}}'
    )


def narrator_user(event: Event, state: WorldState, prev_mode: str | None) -> str:
    twist = ""
    if prev_mode == "backfire":
        twist = "NOTE: the leader's previous decision backfired — open by acknowledging the fallout.\n"
    elif prev_mode == "windfall":
        twist = "NOTE: the leader's previous decision paid off unexpectedly well — acknowledge it.\n"
    if state.pending_alert:
        twist += f"URGENT INTEL — weave this warning into the narrative: {state.pending_alert}\n"
    return (
        f"{_context(state)}\n\n{_event_block(event)}\n\n{twist}"
        f"Valid agent keys for reactions: {_agent_keys(state)}. Stance is one of "
        "hostile|neutral|allied.\n\n"
        'Return JSON: {"headline": "...", "narrative": "2-4 sentences", "agent_reactions": '
        '[{"agent": "<key>", "stance": "...", "quote": "..."}], "stakes": "one line"}'
    )


def options_user(event: Event, state: WorldState) -> str:
    return (
        f"{_context(state)}\n\n{_event_block(event)}\n\n"
        f"Valid tones: {TONES}. Give each option id A, B, C (D). The label MUST be a concrete "
        "action phrase of 3-6 words (e.g. 'Purge the disloyal generals') — NEVER just the letter.\n\n"
        'Return JSON: {"options": [{"id": "A", "label": "Purge the disloyal generals", '
        '"summary": "one line on the trade-off", "tone": "<tone>"}, ... 2 to 4 options]}'
    )


def judge_user(event: Event, action_text: str, state: WorldState) -> str:
    targets = _valid_targets(state)
    return (
        f"{_context(state)}\n\n{_event_block(event)}\n\n"
        f"THE LEADER'S DECISION: {action_text}\n\n"
        f"Valid indicator/faction keys for effects: {targets}.\n"
        f"Valid agent keys: {_agent_keys(state)}.\n\n"
        'Return JSON: {"interpretation": "restate the decision", "magnitude": '
        '"minor|moderate|major|radical", "plausibility": "ok|absurd|impossible", "effects": '
        '[{"indicator": "<key>", "direction": "+|-", "proposed_delta": 7, "reason": "..."}], '
        '"agent_reactions": [{"agent": "<key>", "stance": "...", "quote": "...", '
        '"stance_changed": false}], "consequence_narrative": "2-4 sentences", '
        '"spawns_followup": false}'
    )
