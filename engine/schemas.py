"""Validated JSON contracts for the 4 SLM roles (GAME_RULES.md §7).

The real model path would parse + validate + retry. The FakeLLM produces dicts that
pass these same validators, so the engine code is identical for fake and real models.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.state import EFFECT_TARGETS, INDICATORS, Objective

MAGNITUDES = ("minor", "moderate", "major", "radical")
PLAUSIBILITY = ("ok", "absurd", "impossible")
OPS = (">=", "<=", ">", "<")
STANCES = ("hostile", "neutral", "allied")


class SchemaError(ValueError):
    """Raised when an SLM output violates its contract (triggers a retry in the real path)."""


# --- 7.1 Setup: Objective Generator ---------------------------------------------

def parse_objectives(data: dict) -> list[Objective]:
    raw = data.get("objectives")
    if not isinstance(raw, list) or len(raw) != 8:
        raise SchemaError("expected exactly 8 objectives")
    out: list[Objective] = []
    for i, o in enumerate(raw):
        m = o.get("metric", {})
        ind = m.get("indicator")
        if ind not in EFFECT_TARGETS:
            raise SchemaError(f"objective {i}: bad indicator {ind!r}")
        if m.get("op") not in OPS:
            raise SchemaError(f"objective {i}: bad op {m.get('op')!r}")
        target = m.get("target")
        if not isinstance(target, int) or not (0 <= target <= 100):
            raise SchemaError(f"objective {i}: target must be int 0..100")
        out.append(
            Objective(
                id=o.get("id", f"obj_{i + 1}"),
                title=o["title"],
                description=o.get("description", ""),
                category=o.get("category", "general"),
                indicator=ind,
                op=m["op"],
                target=target,
                by_month=int(m.get("by_month", 12)),
                difficulty=o.get("difficulty", "medium"),
            )
        )
    return out


# --- 7.5 Cast Designer (personas at game start) ---------------------------------

def parse_cast(data: dict) -> dict:
    """Validate the SLM's per-figure personas. Returns {figure_key: persona}.
    utility_shift indicators must be valid; values are clamped later (agents.SHIFT_BOUND)."""
    raw = data.get("cast")
    if not isinstance(raw, list) or not raw:
        raise SchemaError("cast must be a non-empty list")
    out: dict[str, dict] = {}
    for c in raw:
        key = c.get("key")
        if not key:
            raise SchemaError("cast entry missing 'key'")
        shift = c.get("utility_shift") or {}
        if not isinstance(shift, dict):
            raise SchemaError(f"cast {key}: utility_shift must be an object")
        for ind in shift:
            if ind not in EFFECT_TARGETS:
                raise SchemaError(f"cast {key}: bad utility_shift indicator {ind!r}")
        out[key] = {
            "traits": list(c.get("traits", []))[:4],
            "core_value": c.get("core_value", ""),
            "hidden_agenda": c.get("hidden_agenda", ""),
            "utility_shift": {k: float(v) for k, v in shift.items()},
        }
    return out


# --- 7.2 Narrator ---------------------------------------------------------------

@dataclass
class AgentReaction:
    agent: str
    stance: str
    quote: str
    stance_changed: bool = False


@dataclass
class NarratorOutput:
    headline: str
    narrative: str
    agent_reactions: list[AgentReaction] = field(default_factory=list)
    stakes: str = ""

    @staticmethod
    def parse(data: dict) -> "NarratorOutput":
        if not data.get("headline") or not data.get("narrative"):
            raise SchemaError("narrator: headline and narrative required")
        reactions = [
            AgentReaction(r["agent"], r.get("stance", "neutral"), r.get("quote", ""))
            for r in data.get("agent_reactions", [])
        ]
        return NarratorOutput(data["headline"], data["narrative"], reactions, data.get("stakes", ""))


# --- 7.3 Option Generator -------------------------------------------------------

@dataclass
class Option:
    id: str
    label: str
    summary: str
    tone: str


def parse_options(data: dict) -> list[Option]:
    raw = data.get("options", [])
    if not (2 <= len(raw) <= 4):
        raise SchemaError("expected 2..4 options")
    return [Option(o["id"], o["label"], o.get("summary", ""), o.get("tone", "cautious")) for o in raw]


# --- 7.4 Judge / Resolver -------------------------------------------------------

@dataclass
class Effect:
    indicator: str
    direction: str  # "+" | "-"
    proposed_delta: int
    reason: str = ""

    @property
    def signed(self) -> int:
        return abs(self.proposed_delta) * (1 if self.direction == "+" else -1)


@dataclass
class JudgeOutput:
    interpretation: str
    magnitude: str
    plausibility: str
    effects: list[Effect] = field(default_factory=list)
    agent_reactions: list[AgentReaction] = field(default_factory=list)
    consequence_narrative: str = ""
    spawns_followup: bool = False

    @staticmethod
    def parse(data: dict) -> "JudgeOutput":
        if data.get("magnitude") not in MAGNITUDES:
            raise SchemaError(f"judge: bad magnitude {data.get('magnitude')!r}")
        if data.get("plausibility") not in PLAUSIBILITY:
            raise SchemaError(f"judge: bad plausibility {data.get('plausibility')!r}")
        effects = []
        for e in data.get("effects", []):
            if e.get("indicator") not in EFFECT_TARGETS:
                raise SchemaError(f"judge: bad effect indicator {e.get('indicator')!r}")
            if e.get("direction") not in ("+", "-"):
                raise SchemaError("judge: effect direction must be + or -")
            effects.append(
                Effect(e["indicator"], e["direction"], int(e.get("proposed_delta", 0)), e.get("reason", ""))
            )
        reactions = [
            AgentReaction(
                r["agent"], r.get("stance", "neutral"), r.get("quote", ""), r.get("stance_changed", False)
            )
            for r in data.get("agent_reactions", [])
        ]
        return JudgeOutput(
            interpretation=data.get("interpretation", ""),
            magnitude=data["magnitude"],
            plausibility=data["plausibility"],
            effects=effects,
            agent_reactions=reactions,
            consequence_narrative=data.get("consequence_narrative", ""),
            spawns_followup=bool(data.get("spawns_followup", False)),
        )


# --- 7.6 Lunch / private conversation -------------------------------------------

def parse_chat_reply(data: dict) -> str:
    """The figure's in-character reply to a private question. One short JSON field."""
    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise SchemaError("conversation: non-empty 'reply' string required")
    return reply.strip()


# Convenience for tests / sanity:
ALL_INDICATORS = set(INDICATORS)
