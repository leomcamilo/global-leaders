"""Resolver — applies the Judge's proposal to the World State with all guardrails
(GAME_RULES.md §2, §2.1, §3, §3.1). The model proposes; this code decides.

Pipeline (§7.4 post-processing):
  1. plausibility gate (impossible -> no-op; absurd -> catastrophic)
  2. clamp each delta to the magnitude range
  3. "no free lunch": major/radical must carry a trade-off
  4. uncertainty dice
  5. apply + clamp 0..100 (indicators and faction meters)
  6. country faction/coup hooks (China)
  7. update agent stances (game theory)
  8. history digest + game-over checks
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.agents import update_agent_stances
from engine.countries import CountryDef
from engine.dice import Dice
from engine.events import Event
from engine.schemas import Effect, JudgeOutput
from engine.state import INDICATOR_LABELS, WorldState

MAGNITUDE_RANGE = {
    "minor": (1, 3),
    "moderate": (3, 6),
    "major": (6, 10),
    "radical": (10, 15),
}
MAX_INDICATORS_PER_DECISION = 3
# Where to charge the default cost when a big move has no trade-off (§2 rule 1).
NATURAL_COST = "fiscal_health"

PLA_CLIQUE_EVENT = "cn_2025_04_pla_clique"


@dataclass
class ResolveResult:
    applied: dict[str, int] = field(default_factory=dict)
    mode: str = "normal"  # normal | backfire | windfall | rejected | catastrophic
    stance_changes: dict[str, bool] = field(default_factory=dict)
    note: str = ""


def resolve(
    state: WorldState,
    country: CountryDef,
    event: Event,
    judge: JudgeOutput,
    dice: Dice,
    turn: int,
    decision_idx: int = 0,
) -> ResolveResult:
    # 1. Plausibility gate.
    if judge.plausibility == "impossible":
        state.history.append(f"M{turn:02d}: attempted the impossible — nothing happened")
        return ResolveResult(mode="rejected", note="Impossible action; the world shrugs.")

    magnitude = judge.magnitude
    catastrophic = judge.plausibility == "absurd"
    if catastrophic:
        magnitude = "radical"
    lo, hi = MAGNITUDE_RANGE[magnitude]

    # 2. Clamp each proposed delta into the magnitude range; cap how many indicators move.
    effects: dict[str, int] = {}
    for e in judge.effects[:MAX_INDICATORS_PER_DECISION]:
        mag = max(lo, min(hi, abs(e.proposed_delta)))
        sign = 1 if e.direction == "+" else -1
        effects[e.indicator] = sign * mag

    # Absurd actions are forced catastrophic: invert any gains, guarantee real pain.
    if catastrophic:
        effects = {k: -abs(v) for k, v in effects.items()}
        effects.setdefault("approval", -hi)
        effects.setdefault("institutional_stability", -hi)

    # 3. No free lunch: major/radical must include at least one negative trade-off.
    if magnitude in ("major", "radical") and not any(v < 0 for v in effects.values()):
        cost_key = NATURAL_COST if NATURAL_COST not in effects else "approval"
        effects[cost_key] = effects.get(cost_key, 0) - lo

    # 4. Uncertainty dice (one roll governs the whole decision).
    roll = dice.roll(turn, decision_idx)

    # 5. Apply, clamped to 0..100.
    applied: dict[str, int] = {}
    for key, delta in effects.items():
        final = round(roll.apply(delta))
        before = state.get(key)
        state.apply(key, final)
        applied[key] = state.get(key) - before

    # 6. Country-specific faction / coup hooks.
    if country.key == "china":
        _china_hooks(state, event, applied)

    # 7. Update agent stances from the realised deltas (game theory, §0.2).
    stance_changes = update_agent_stances(state, country.agents, {k: float(v) for k, v in applied.items()})

    # 8. History line + game over.
    state.history.append(_history_line(turn, judge, applied, roll.mode))
    check_game_over(state, country)

    return ResolveResult(applied=applied, mode=roll.mode, stance_changes=stance_changes)


def _china_hooks(state: WorldState, event: Event, applied: dict[str, int]) -> None:
    """PLA clique arc (§3.1). A decisive pro-control move on any PLA event (one that touches
    pla_loyalty) defuses the clique; otherwise the plot keeps maturing (see upkeep)."""
    pla_event = "pla_loyalty" in event.touches or "pla_loyalty" in event.faction_touches
    if pla_event and applied.get("pla_loyalty", 0) >= 6:
        state.flags["pla_clique_handled"] = True
        state.factions["coup_plot_progress"] = 0


def _elite_pressure(state: WorldState, country: CountryDef) -> None:
    """The elite's mood moves markets each month, scaled by its country-specific influence.
    Happy elite -> +economy/+fiscal; hostile elite (and the media it owns) -> -economy/-fiscal/-approval.
    Strong in USA/Brazil (influence ~0.8-0.9), weak in China (~0.3)."""
    elite = next((f for f in country.roster if f.faction == "elite"), None)
    if not elite or elite.influence <= 0:
        return
    favor = state.agent_favor.get(elite.key, 0.0)  # -100..100
    mag = round((favor / 100.0) * elite.influence * 4)
    if mag == 0:
        return
    state.apply("economy", mag)
    state.apply("fiscal_health", mag)
    if mag < 0:  # a hostile elite — and the outlets it controls — also drags approval down
        state.apply("approval", mag // 2)


def _resilience(state: WorldState) -> None:
    """Gentle mean-reversion so a battered nation doesn't spiral straight to zero: indicators in
    extreme lows recover a little each month (economies stabilize, institutions regroup); very high
    ones drift down (political gravity). Softens death-spirals without erasing the difficulty."""
    for ind, v in list(state.indicators.items()):
        if v < 20:
            state.apply(ind, 3)
        elif v < 30:
            state.apply(ind, 2)
        elif v < 40:
            state.apply(ind, 1)
        elif v > 88:
            state.apply(ind, -1)


def end_of_month_upkeep(state: WorldState, country: CountryDef, dice: Dice, turn: int) -> None:
    """Run once after all of a month's events are resolved (§3 universal rule, §3.1 maturation)."""
    _elite_pressure(state, country)
    _resilience(state)

    # Universal terminal crisis: any key indicator below the floor for 2 consecutive months.
    floor = country.collapse.universal_floor
    for ind, value in state.indicators.items():
        if value < floor:
            state.low_streak[ind] = state.low_streak.get(ind, 0) + 1
        else:
            state.low_streak[ind] = 0
    for ind, streak in state.low_streak.items():
        if streak >= 2 and state.game_over is None:
            state.game_over = "terminal_crisis"
            state.ending_text = (
                f"{INDICATOR_LABELS.get(ind, ind)} has been in free-fall for months. "
                f"The state can no longer function. Your government collapses."
            )

    # China: the coup plot matures while the clique is unhandled and the PLA is disaffected.
    # Meio-termo: still fairly fast, but the player gets narrative warnings (§ polish) to react.
    if country.key == "china" and not state.flags.get("pla_clique_handled"):
        pla = state.factions.get("pla_loyalty", 100)
        if pla < 50:
            growth = round((50 - pla) * 0.5) + 7
            jitter = dice.roll(turn, 99).factor  # 0.4..1.6, reproducible
            state.factions["coup_plot_progress"] = min(
                100, state.factions.get("coup_plot_progress", 0) + round(growth * jitter))
        plot = state.factions.get("coup_plot_progress", 0)
        if plot >= 70 and not state.flags.get("pla_warn2"):
            state.flags["pla_warn2"] = True
            state.pending_alert = ("Credible intelligence points to an advanced plot brewing inside the PLA "
                                   "high command. Move against the clique now — or lose the army.")
        elif plot >= 40 and not state.flags.get("pla_warn1"):
            state.flags["pla_warn1"] = True
            state.pending_alert = ("Whispers reach you of disquiet and fraying loyalty in the PLA's senior ranks.")
    check_game_over(state, country)


def check_game_over(state: WorldState, country: CountryDef) -> None:
    if state.game_over is not None:
        return
    ind = state.indicators
    rule = country.collapse

    # China faction endings come first (§3.1).
    if country.key == "china":
        if state.factions.get("party_loyalty", 100) < 25:
            state.game_over = "party_ouster"
            state.ending_text = (
                "A closed-door plenum strips you of your titles. The Party has decided you are "
                "a liability; a successor is announced before you finish your tea."
            )
            return
        if state.factions.get("coup_plot_progress", 0) >= 100 or state.factions.get("pla_loyalty", 100) < 20:
            state.game_over = "pla_coup"
            state.ending_text = (
                "The clique you failed to control moves first. Tanks ring Zhongnanhai at dawn; "
                "the PLA announces a 'rectification'. You never controlled the gun — and it turned."
            )
            return

    if rule.gov == "dem":
        if ind["approval"] < rule.approval_min and ind["institutional_stability"] < rule.inst_min:
            state.game_over = "removed_from_office"
            state.ending_text = (
                "With your approval gutted and institutions turning on you, the machinery of removal "
                "grinds into motion. Impeachment / a no-confidence vote ends your government."
            )
            return
        if ind["economy"] < rule.eco_min and ind["approval"] < rule.approval_min:
            state.game_over = "economic_meltdown"
            state.ending_text = "An economic collapse and a furious public force you out."
            return
    else:  # autocracy
        if ind["institutional_stability"] < rule.inst_min and (
            ind["economy"] < rule.eco_min or ind["social_cohesion"] < rule.coh_min
        ):
            state.game_over = "palace_collapse"
            state.ending_text = (
                "Cracks in the inner circle widen into a chasm. Your grip fails and the regime "
                "convulses into a leadership struggle."
            )
            return


def _history_line(turn: int, judge: JudgeOutput, applied: dict[str, int], mode: str) -> str:
    moves = ", ".join(
        f"{INDICATOR_LABELS.get(k, k)} {('+' if v >= 0 else '')}{v}" for k, v in applied.items() if v
    )
    tag = {"backfire": " [BACKFIRED]", "windfall": " [windfall]"}.get(mode, "")
    summary = (judge.interpretation or "acted")[:60]
    return f"M{turn:02d}: {summary} -> {moves or 'no net change'}{tag}"
