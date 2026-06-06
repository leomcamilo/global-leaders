"""Figures (named real cast) as game-theoretic players (GAME_RULES.md §0.2;
COUNTRY_SCENARIOS.md §2).

Each figure has a *base utility vector*: the indicators it rewards/punishes you for moving.
At game start the SLM (Cast Designer) gives each figure traits + a hidden agenda and may
nudge its utility within bounds (±SHIFT_BOUND) — stored as the *effective* utility in
state.cast. Stance is then derived deterministically from the effective utility; the SLM
narrates the stance, it does not decide it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.state import WorldState

SHIFT_BOUND = 0.3  # max per-indicator nudge the Cast Designer may apply (§2.2)


@dataclass
class Figure:
    key: str            # STABLE mechanical id, e.g. "sec_state"
    name: str           # "Marco Rubio"
    role: str           # "Secretary of State"
    faction: str        # cabinet | opposition | military | institution | foreign | society | elite
    utility: dict[str, float] = field(default_factory=dict)  # base utility vector
    themes: list[str] = field(default_factory=list)
    start_favor: float = 0.0
    adjustable: bool = True  # institutions are False (the SLM can't reshape them)
    influence: float = 0.0   # mechanical weight (0..1). Used by the elite: how hard their mood
    #                          moves markets/approval each month. High in USA/Brazil, low in China.


# --- Utility presets by archetype (keeps mechanics consistent across countries) -

UTILITY_PRESETS: dict[str, dict[str, float]] = {
    "treasury": {"fiscal_health": 1.0, "economy": 0.7, "public_services": -0.2},
    "loyalist": {"approval": 0.6, "social_cohesion": 0.4, "international_power": 0.3},
    "diplomat": {"international_power": 0.8, "security": 0.3},
    "hawk": {"international_power": 0.6, "security": 0.7, "fiscal_health": -0.2},
    "military": {"security": 0.8, "international_power": 0.5, "fiscal_health": -0.2},
    "pla": {"pla_loyalty": 1.0, "international_power": 0.5, "fiscal_health": -0.2},
    "health": {"public_services": 0.7, "approval": 0.2, "fiscal_health": -0.1},
    "justice": {"security": 0.6, "institutional_stability": 0.5},
    "security": {"security": 0.8, "social_cohesion": -0.1},
    "opposition": {"social_cohesion": 0.9, "approval": -0.6, "institutional_stability": 0.4},
    "media": {"approval": 0.5, "social_cohesion": 0.6, "security": -0.2},
    "elite": {"fiscal_health": 0.7, "economy": 0.6, "international_power": 0.3, "institutional_stability": 0.3},
    "society": {"approval": 0.6, "public_services": 0.7, "economy": 0.6, "fiscal_health": -0.1},
    "institution": {"fiscal_health": 0.8, "economy": 0.4, "institutional_stability": 0.5},
    "foreign": {"international_power": 0.8, "security": 0.2},
}

# Sensible default starting favour by faction.
_START_FAVOR = {"opposition": -45.0, "military": -10.0, "foreign": -15.0}
_NONADJUSTABLE = {"institution"}


def fig(key: str, name: str, role: str, faction: str, preset: str,
        themes: list[str], influence: float = 0.0, **over: float) -> Figure:
    """Build a Figure from a utility preset, with optional per-indicator overrides."""
    utility = dict(UTILITY_PRESETS[preset])
    utility.update(over)
    return Figure(
        key=key, name=name, role=role, faction=faction, utility=utility, themes=themes,
        start_favor=_START_FAVOR.get(faction, 0.0),
        adjustable=faction not in _NONADJUSTABLE,
        influence=influence,
    )


# --- Persona application (bounds the Cast Designer) -----------------------------

def clamp_shift(value: float) -> float:
    return max(-SHIFT_BOUND, min(SHIFT_BOUND, value))


def effective_utility(figure: Figure, shift: dict[str, float] | None) -> dict[str, float]:
    """base utility + clamped shift (only if the figure is adjustable)."""
    if not shift or not figure.adjustable:
        return dict(figure.utility)
    eff = dict(figure.utility)
    for ind, delta in shift.items():
        eff[ind] = eff.get(ind, 0.0) + clamp_shift(delta)
    return eff


# --- Stance dynamics ------------------------------------------------------------

def favor_to_stance(favor: float) -> str:
    if favor <= -30:
        return "hostile"
    if favor >= 30:
        return "allied"
    return "neutral"


def expected_payoff(utility: dict[str, float], applied: dict[str, float]) -> float:
    return sum(weight * applied.get(ind, 0.0) for ind, weight in utility.items())


def update_agent_stances(
    state: WorldState, roster: dict[str, Figure], applied: dict[str, float]
) -> dict[str, bool]:
    """Mutate favor + stance for every figure using its *effective* utility. Returns changes."""
    changed: dict[str, bool] = {}
    for key, figure in roster.items():
        util = effective_utility(figure, state.cast.get(key, {}).get("utility_shift"))
        payoff = expected_payoff(util, applied)
        old = state.agent_stances.get(key, favor_to_stance(state.agent_favor.get(key, figure.start_favor)))
        favor = state.agent_favor.get(key, figure.start_favor)
        favor = max(-100.0, min(100.0, favor * 0.92 + payoff * 1.5))
        state.agent_favor[key] = favor
        state.agent_stances[key] = favor_to_stance(favor)
        changed[key] = state.agent_stances[key] != old
    return changed
