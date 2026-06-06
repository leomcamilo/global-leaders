"""LLM boundary + a deterministic FakeLLM stub.

The engine talks to the model through four calls (GAME_RULES.md §7). The FakeLLM
produces schema-valid dicts with simple heuristics, so the whole loop and every
guardrail can be exercised with no model and no randomness (the Dice owns variance).
Swapping in a real SLM means implementing the same four methods.
"""

from __future__ import annotations

from typing import Protocol, Union

from engine.countries import CountryDef
from engine.schemas import Option
from engine.state import INDICATOR_LABELS, INDICATORS, WorldState
from engine.events import Event

Action = Union[Option, str]


class LLM(Protocol):
    def setup_objectives(self, country: CountryDef, state: WorldState) -> dict: ...
    def cast_design(self, country: CountryDef, state: WorldState) -> dict: ...
    def narrate(self, event: Event, state: WorldState, prev_mode: str | None = None) -> dict: ...
    def options(self, event: Event, state: WorldState) -> dict: ...
    def judge(self, event: Event, action: Action, state: WorldState) -> dict: ...
    def converse(self, figure, persona: str | None, question: str, state: WorldState,
                 history: list[dict]) -> dict: ...


# Tone -> magnitude (the resolver clamps the actual deltas).
_TONE_MAGNITUDE = {
    "defiant": "radical",
    "bold": "major",
    "populist": "major",
    "technocratic": "moderate",
    "cautious": "moderate",
    "conciliatory": "moderate",
}


def _mid(magnitude: str) -> int:
    from engine.resolver import MAGNITUDE_RANGE

    lo, hi = MAGNITUDE_RANGE[magnitude]
    return (lo + hi) // 2


class FakeLLM:
    """Deterministic, no randomness. Good enough to validate the engine end-to-end."""

    # -- 7.1 Objective generator -------------------------------------------------

    def setup_objectives(self, country: CountryDef, state: WorldState) -> dict:
        objs = []
        for i, ind in enumerate(INDICATORS):
            cur = state.indicators[ind]
            label = INDICATOR_LABELS[ind]
            if ind == country.archetype:
                target, op, diff = min(cur + 8, 85), ">=", "hard"
                title = f"Project power: push {label} to {target}"
            elif cur < 45:  # crisis indicator: a modest, winnable gain
                target, op, diff = cur + 5, ">=", "medium"
                title = f"Steady {label} (reach {target})"
            elif cur >= 65:  # strong: maintain
                target, op, diff = max(cur - 3, 0), ">=", "easy"
                title = f"Hold the line on {label} (stay ≥ {target})"
            else:
                target, op, diff = cur + 3, ">=", "medium"
                title = f"Lift {label} a notch (reach {target})"
            objs.append(
                {
                    "id": f"obj_{i + 1}",
                    "title": title,
                    "description": f"By December 2025, get {label} to satisfy {op} {target}.",
                    "category": ind,
                    "metric": {"indicator": ind, "op": op, "target": target, "by_month": 12},
                    "difficulty": diff,
                }
            )
        return {"objectives": objs}

    # -- 7.5 Cast Designer -------------------------------------------------------

    def cast_design(self, country: CountryDef, state: WorldState) -> dict:
        # Deterministic personas with no utility_shift -> mechanics stay on the base vectors.
        cast = []
        for f in country.roster:
            trait = {"opposition": "combative", "military": "proud", "institution": "by-the-book",
                     "society": "anxious", "foreign": "wary"}.get(f.faction, "ambitious")
            cast.append({
                "key": f.key,
                "traits": [trait, f.faction],
                "core_value": (f.themes[0] if f.themes else f.faction),
                "hidden_agenda": "",
                "utility_shift": {},
            })
        return {"cast": cast}

    # -- 7.2 Narrator ------------------------------------------------------------

    def narrate(self, event: Event, state: WorldState, prev_mode: str | None = None) -> dict:
        reactions = []
        for agent_key, line in list(event.stakeholder_positions.items())[:3]:
            stance = state.agent_stances.get(agent_key, "neutral")
            reactions.append({"agent": agent_key, "stance": stance, "quote": line})
        twist = ""
        if prev_mode == "backfire":
            twist = "Last month's move blew up in your face. "
        elif prev_mode == "windfall":
            twist = "Your last gamble paid off better than anyone expected. "
        return {
            "headline": event.title_seed,
            "narrative": f"{twist}{event.fact} {event.dilemma}",
            "agent_reactions": reactions,
            "stakes": event.hidden_info or "The country is watching how you handle this.",
        }

    # -- 7.3 Option generator ----------------------------------------------------

    def options(self, event: Event, state: WorldState) -> dict:
        return {"options": [
            {"id": p["id"], "label": p["label"], "summary": p["summary"], "tone": p["tone"]}
            for p in _playbook(event)
        ]}

    # -- 7.4 Judge ---------------------------------------------------------------

    def judge(self, event: Event, action: Action, state: WorldState) -> dict:
        if isinstance(action, str):
            return self._judge_freetext(event, action)
        # Option chosen: look up its intent in the playbook.
        plays = {p["id"]: p for p in _playbook(event)}
        play = plays.get(action.id) or next(iter(plays.values()))
        return {
            "interpretation": play["label"],
            "magnitude": _TONE_MAGNITUDE[play["tone"]],
            "plausibility": "ok",
            "effects": play["effects"],
            "agent_reactions": [],
            "consequence_narrative": play["summary"],
            "spawns_followup": event.branchable and play["tone"] in ("defiant", "bold"),
        }

    # -- 7.6 Lunch conversation --------------------------------------------------

    def converse(self, figure, persona: str | None, question: str, state: WorldState,
                 history: list[dict]) -> dict:
        stance = state.agent_stances.get(figure.key, "neutral")
        topic = figure.themes[0] if figure.themes else "the country"
        tone = {"hostile": "Let's not pretend we're friends.",
                "allied": "You know I'm with you.",
                "neutral": "I'll be straight with you."}[stance]
        return {"reply": f"{tone} What I care about is {topic} — push that and I'm with you; "
                         f"neglect it and we'll have a problem."}

    def _judge_freetext(self, event: Event, text: str) -> dict:
        low = text.lower()
        absurd_words = ("nuke", "invade everyone", "abolish all", "world war", "exterminate")
        impossible_words = ("turn everyone into", "stop time", "make gold", "teleport")
        if any(w in low for w in impossible_words):
            return {"interpretation": text[:60], "magnitude": "minor",
                    "plausibility": "impossible", "effects": []}
        if any(w in low for w in absurd_words):
            return {"interpretation": text[:60], "magnitude": "radical",
                    "plausibility": "absurd", "effects": []}
        primary = event.touches[0] if event.touches else "approval"
        effects = [{"indicator": primary, "direction": "+", "proposed_delta": 6, "reason": "player initiative"}]
        if len(event.touches) > 1:
            effects.append({"indicator": event.touches[1], "direction": "-",
                            "proposed_delta": 4, "reason": "trade-off"})
        return {"interpretation": text[:60], "magnitude": "moderate", "plausibility": "ok",
                "effects": effects, "consequence_narrative": "You take a measured course.",
                "spawns_followup": False}


# ---------------------------------------------------------------------------------
# Playbooks: option sets + their judged effects. Coupling options<->judge here is fine
# for a stub; a real SLM generates both freely.
# ---------------------------------------------------------------------------------

def _playbook(event: Event) -> list[dict]:
    if event.id == "cn_2025_04_pla_clique":
        return [
            {"id": "A", "label": "Launch a sweeping purge of the clique", "tone": "defiant",
             "summary": "You move first and break the network — destabilising, but the army is yours.",
             "effects": [
                 {"indicator": "pla_loyalty", "direction": "+", "proposed_delta": 12, "reason": "clique broken"},
                 {"indicator": "institutional_stability", "direction": "-", "proposed_delta": 7, "reason": "shock"},
                 {"indicator": "social_cohesion", "direction": "-", "proposed_delta": 5, "reason": "fear"},
                 {"indicator": "security", "direction": "+", "proposed_delta": 6, "reason": "control"},
             ]},
            {"id": "B", "label": "Keep them close and watch quietly", "tone": "cautious",
             "summary": "You bide your time. The clique reads it as weakness.",
             "effects": [
                 {"indicator": "approval", "direction": "+", "proposed_delta": 2, "reason": "no drama"},
                 {"indicator": "pla_loyalty", "direction": "-", "proposed_delta": 4, "reason": "emboldened"},
             ]},
            {"id": "C", "label": "Buy their loyalty with promotions & budget", "tone": "populist",
             "summary": "Gold instead of handcuffs. It buys time, not safety.",
             "effects": [
                 {"indicator": "pla_loyalty", "direction": "+", "proposed_delta": 6, "reason": "patronage"},
                 {"indicator": "fiscal_health", "direction": "-", "proposed_delta": 7, "reason": "payoffs"},
                 {"indicator": "international_power", "direction": "+", "proposed_delta": 2, "reason": "stronger PLA"},
             ]},
        ]
    if event.military and "pla_loyalty" in event.faction_touches:
        primary = event.touches[0]
        return [
            {"id": "A", "label": "Assert strength / escalate", "tone": "bold",
             "summary": "Project resolve and lean on the generals to deliver.",
             "effects": [
                 {"indicator": primary, "direction": "+", "proposed_delta": 9, "reason": "show of force"},
                 {"indicator": "pla_loyalty", "direction": "+", "proposed_delta": 5, "reason": "brass pleased"},
                 {"indicator": "fiscal_health", "direction": "-", "proposed_delta": 6, "reason": "cost"},
             ]},
            {"id": "B", "label": "Stand down / hold the line", "tone": "cautious",
             "summary": "Avoid the risk — and bruise the generals' pride.",
             "effects": [
                 {"indicator": "fiscal_health", "direction": "+", "proposed_delta": 4, "reason": "saved cost"},
                 {"indicator": "pla_loyalty", "direction": "-", "proposed_delta": 5, "reason": "humiliated brass"},
             ]},
            {"id": "C", "label": "Indulge the generals", "tone": "populist",
             "summary": "Give the PLA what it wants and hope it buys loyalty.",
             "effects": [
                 {"indicator": "pla_loyalty", "direction": "+", "proposed_delta": 7, "reason": "lavish funding"},
                 {"indicator": "fiscal_health", "direction": "-", "proposed_delta": 7, "reason": "blank cheque"},
             ]},
        ]
    # Generic case.
    primary = event.touches[0] if event.touches else "approval"
    second = event.touches[1] if len(event.touches) > 1 else "fiscal_health"
    return [
        {"id": "A", "label": "Act decisively", "tone": "bold",
         "summary": "A bold, high-variance move.",
         "effects": [
             {"indicator": primary, "direction": "+", "proposed_delta": 10, "reason": "decisive"},
             {"indicator": second, "direction": "-", "proposed_delta": 6, "reason": "trade-off"},
         ]},
        {"id": "B", "label": "A measured response", "tone": "cautious",
         "summary": "Steady hands, smaller swings.",
         "effects": [
             {"indicator": primary, "direction": "+", "proposed_delta": 6, "reason": "measured"},
         ]},
        {"id": "C", "label": "Play to the crowd", "tone": "populist",
         "summary": "Win the room now, pay later.",
         "effects": [
             {"indicator": "approval", "direction": "+", "proposed_delta": 9, "reason": "crowd-pleaser"},
             {"indicator": "fiscal_health", "direction": "-", "proposed_delta": 7, "reason": "unfunded"},
         ]},
    ]
