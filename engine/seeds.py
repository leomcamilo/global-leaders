"""Seed ingestion (COUNTRY_SCENARIOS.md §2.3, §2.4, §6).

Loads curated 2025 events from JSON (the deep-research output) into engine objects, and
models cross-country facts: `GlobalEvent` (one fact, per-country hooks) and `WorldModifier`
(background effect on countries without an explicit hook — e.g. an oil-price shock).

Seed file format (per country):  {"events": [ {<Event fields>}, ... ]}
Global seed file format:         {"globals": [ {id, title, fact, month, hooks{...}, world_modifier{...}}, ... ]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from engine.events import Event
from engine.state import WorldState, clamp


@dataclass
class WorldModifier:
    id: str
    label: str
    months: int = 1
    # country_key -> {indicator: per-month delta} (applied while active)
    deltas: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class GlobalEvent:
    id: str
    title: str
    fact: str
    month: int | None = None
    # country_key -> hook dict {title?, touches, dilemma, hidden_info, figures, stakeholder_positions, military?}
    hooks: dict[str, dict] = field(default_factory=dict)
    world_modifier: WorldModifier | None = None


# --- JSON -> objects ------------------------------------------------------------

def event_from_dict(d: dict) -> Event:
    return Event(
        id=d["id"],
        type=d.get("type", "anchored"),
        title_seed=d["title_seed"],
        fact=d["fact"],
        touches=d.get("touches", []),
        month=d.get("month"),
        dilemma=d.get("dilemma", ""),
        hidden_info=d.get("hidden_info", ""),
        stakeholder_positions=d.get("stakeholder_positions", {}),
        preconditions=d.get("preconditions", {}),
        military=d.get("military", False),
        faction_touches=d.get("faction_touches", []),
        figures=d.get("figures", []),
        base_weight=d.get("base_weight", 1.0),
        branchable=d.get("branchable", False),
    )


def load_country_seeds(path: str) -> list[Event]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [event_from_dict(e) for e in data.get("events", [])]


def load_global_seeds(path: str) -> list[GlobalEvent]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    for g in data.get("globals", []):
        wm = g.get("world_modifier")
        out.append(GlobalEvent(
            id=g["id"], title=g["title"], fact=g["fact"], month=g.get("month"),
            hooks=g.get("hooks", {}),
            world_modifier=WorldModifier(**wm) if wm else None,
        ))
    return out


# --- Manifestation & background effects -----------------------------------------

def manifest_hook(ge: GlobalEvent, country_key: str) -> Event | None:
    """Turn a global event's per-country hook into a normal anchored Event for that country."""
    hook = ge.hooks.get(country_key)
    if hook is None:
        return None
    return Event(
        id=f"{ge.id}__{country_key}",
        type="anchored",
        month=ge.month,
        title_seed=hook.get("title", ge.title),
        fact=ge.fact,
        touches=hook.get("touches", []),
        dilemma=hook.get("dilemma", ""),
        hidden_info=hook.get("hidden_info", ""),
        stakeholder_positions=hook.get("stakeholder_positions", {}),
        military=hook.get("military", False),
        faction_touches=hook.get("faction_touches", []),
        figures=hook.get("figures", []),
        base_weight=hook.get("base_weight", 2.0),  # global facts press harder
    )


def fire_global_events(globals_list: list[GlobalEvent], state: WorldState, month: int) -> list[Event]:
    """For the current country/month: inject hooked manifestations as events; queue background
    modifiers for global events that hit this country without an explicit hook. Returns events."""
    injected: list[Event] = []
    for ge in globals_list:
        if ge.month != month or ge.id in state.consumed_events:
            continue
        ev = manifest_hook(ge, state.country)
        if ev is not None:
            injected.append(ev)
        elif ge.world_modifier and state.country in ge.world_modifier.deltas:
            wm = ge.world_modifier
            state.active_modifiers.append({
                "id": wm.id, "label": wm.label, "remaining": wm.months,
                "deltas": dict(wm.deltas[state.country]),
            })
        state.consumed_events.add(ge.id)
    return injected


def apply_active_modifiers(state: WorldState) -> dict[str, int]:
    """Apply one month of every active background modifier; decay and drop expired ones."""
    applied: dict[str, int] = {}
    still: list[dict] = []
    for mod in state.active_modifiers:
        for ind, delta in mod["deltas"].items():
            before = state.get(ind)
            state.apply(ind, delta)
            applied[ind] = applied.get(ind, 0) + (state.get(ind) - before)
        mod["remaining"] -= 1
        if mod["remaining"] > 0:
            still.append(mod)
    state.active_modifiers = still
    return applied
