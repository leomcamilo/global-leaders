"""Events (GAME_RULES.md §5). Each event is a *case* (§0.1): a dilemma with incomplete
info and conflicting stakeholders.

Three types: `anchored` (real dated 2025 fact, fires on its month), `conditional`
(state-triggered), `branching` (SLM follow-up). Selection weights crises toward the
player's weak indicators (§5.1).

The pools here are PLACEHOLDER seeds to drive the headless demo. Real per-country
curation (news + rumours) is the `deep-research` step, done after this prototype.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine.state import WorldState

WEAKNESS_SENSITIVITY = 0.6


@dataclass
class Event:
    id: str
    type: str  # "anchored" | "conditional" | "branching"
    title_seed: str
    fact: str
    touches: list[str]
    month: int | None = None  # required for anchored
    dilemma: str = ""
    hidden_info: str = ""
    stakeholder_positions: dict[str, str] = field(default_factory=dict)
    preconditions: dict[str, str] = field(default_factory=dict)  # {"security": "<35"}
    military: bool = False
    faction_touches: list[str] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)  # figure keys involved (COUNTRY_SCENARIOS.md §2.3)
    base_weight: float = 1.0
    branchable: bool = False


def _cmp(value: int, expr: str) -> bool:
    op, num = expr[0], expr[1:]
    if expr[1] in "=<>":  # ">=", "<="
        op, num = expr[:2], expr[2:]
    n = int(num)
    return {
        "<": value < n, ">": value > n, "<=": value <= n,
        ">=": value >= n, "=": value == n,
    }[op]


def meets_preconditions(event: Event, state: WorldState) -> bool:
    return all(_cmp(state.get(ind), expr) for ind, expr in event.preconditions.items())


def event_weight(event: Event, state: WorldState) -> float:
    w = event.base_weight
    for ind in event.touches:
        if ind in state.indicators:
            w *= 1 + ((50 - state.indicators[ind]) / 50) * WEAKNESS_SENSITIVITY
    return max(0.05, w)


def select_events(pool: list[Event], state: WorldState, rng: random.Random, n: int = 2) -> list[Event]:
    available = [
        e for e in pool if e.id not in state.consumed_events and meets_preconditions(e, state)
    ]
    # All anchored facts dated to this month fire (a busy month shows its real events).
    chosen: list[Event] = [e for e in available if e.type == "anchored" and e.month == state.month]

    # Fill remaining slots from conditional/branching, weighted toward weakness.
    rest = [e for e in available if e not in chosen and e.type != "anchored"]
    while len(chosen) < n and rest:
        weights = [event_weight(e, state) for e in rest]
        pick = rng.choices(rest, weights=weights, k=1)[0]
        chosen.append(pick)
        rest.remove(pick)
    return chosen


# ---------------------------------------------------------------------------------
# China pool — enough to drive the demo, including the PLA clique arc (§3.1).
# ---------------------------------------------------------------------------------

CHINA_EVENTS: list[Event] = [
    Event(
        id="cn_2025_q1_property",
        type="anchored", month=2,
        title_seed="Another major property developer teeters",
        fact="A large real-estate developer misses bond payments, reviving fears about the housing slump.",
        touches=["economy", "fiscal_health", "social_cohesion"],
        dilemma="Bail out the developer (moral hazard, fiscal cost) or let it fail (contagion risk)?",
        hidden_info="How exposed local-government financing vehicles really are.",
        stakeholder_positions={
            "econ_czar": "Warns a bailout blows the budget.",
            "voice": "Millions fear for their unfinished apartments.",
        },
    ),
    Event(
        id="cn_2025_04_pla_clique",
        type="anchored", month=4,
        title_seed="Whispers of a corrupt clique at the top of the PLA",
        fact=("Investigators flag that senior generals around the Central Military Commission have been "
              "selling promotions and forming an autonomous network — echoing the real 2025 purge of "
              "He Weidong and Miao Hua."),
        touches=["institutional_stability", "security"],
        military=True,
        faction_touches=["pla_loyalty"],
        dilemma="Purge the clique now (risky, destabilising, no clean proof yet) or wait and keep them close?",
        hidden_info="Whether the clique is already planning to move against you.",
        stakeholder_positions={
            "military_chief": "Bristles at any purge of the brass.",
            "opposition": "Sees a chance if you overreach.",
        },
        base_weight=2.0,
        branchable=True,
    ),
    Event(
        id="cn_2025_summer_taiwan",
        type="anchored", month=7,
        title_seed="A tense standoff in the Taiwan Strait",
        fact="A naval incident near Taiwan forces a decision on how hard to push.",
        touches=["international_power", "security", "approval"],
        military=True,
        faction_touches=["pla_loyalty"],
        dilemma="Escalate to look strong, or de-escalate to avoid a war you may not control?",
        hidden_info="How loyal the commanders executing your orders actually are.",
        stakeholder_positions={
            "military_chief": "Wants to demonstrate resolve.",
            "foreign_leader": "Watches for any pretext.",
        },
        base_weight=1.5,
    ),
    Event(
        id="cn_unrest",
        type="conditional",
        title_seed="Scattered protests over jobs and wages",
        fact="Youth unemployment frustration spills into the streets of several cities.",
        touches=["social_cohesion", "approval", "security"],
        preconditions={"social_cohesion": "<45"},
        dilemma="Crack down hard (security up, cohesion down) or concede (cohesion up, looks weak)?",
        hidden_info="How far the anger will spread if mishandled.",
        base_weight=1.2,
    ),
    Event(
        id="cn_export_curbs",
        type="conditional",
        title_seed="New foreign tech export controls bite",
        fact="Partners tighten chip and equipment controls, squeezing key industries.",
        touches=["economy", "international_power"],
        preconditions={},
        dilemma="Retaliate (escalation) or invest in self-sufficiency (slow, costly)?",
        hidden_info="How quickly domestic substitutes can scale.",
        base_weight=1.0,
    ),
    Event(
        id="cn_military_budget",
        type="conditional",
        title_seed="The PLA presses for a bigger budget",
        fact="The high command lobbies hard for more funding and modernisation.",
        touches=["fiscal_health", "international_power"],
        military=True,
        faction_touches=["pla_loyalty"],
        preconditions={},
        dilemma="Fund them (keeps the brass happy, strains the budget) or hold the line (risks resentment)?",
        hidden_info="Whether generous funding buys loyalty or just emboldens the clique.",
        base_weight=1.0,
    ),
]

# Curated decks now live in seeds/seeds_<country>.json (loaded by Game). CHINA_EVENTS is
# kept only for the mechanic tests; the live China deck is seeds_china.json.
POOLS: dict[str, list[Event]] = {}


def pool_for(country_key: str) -> list[Event]:
    return POOLS.get(country_key, [])
