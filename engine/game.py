"""Game orchestrator — wires state + events + SLM + resolver into a turn loop.

API is deliberately thin so both a scripted demo and an interactive UI (Gradio later)
can drive it: start() -> per month [month_events(), present(e), act(e, choice)] -> end_month().
"""

from __future__ import annotations

import os
import random

from engine.agents import favor_to_stance
from engine.countries import get_country
from engine.dice import Dice
from engine.events import Event, pool_for, select_events
from engine.llm import LLM, Action
from engine.personas import load_persona
from engine.resolver import ResolveResult, end_of_month_upkeep, resolve
from engine.seeds import (
    apply_active_modifiers,
    fire_global_events,
    load_country_seeds,
    load_global_seeds,
)
from engine.schemas import (
    JudgeOutput,
    NarratorOutput,
    Option,
    parse_cast,
    parse_objectives,
    parse_options,
)
from engine.state import WorldState

EVENTS_PER_MONTH = 3
MAX_EVENTS_PER_MONTH = 3  # cap total monthly load (globals + deck); 3 keeps thin decks busier
# Early-game ramp-up: the first months stay light so a fragile nation (e.g. France) can't be
# piled into an economic death-spiral before the player gains traction (validated via Nemotron).
EARLY_GAME_MONTHS = 2
EARLY_GAME_CAP = 2
SEEDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seeds")


class Game:
    def __init__(self, country_key: str, llm: LLM, seed: int = 1):
        self.country = get_country(country_key)
        self.llm = llm
        self.dice = Dice(seed)
        self.rng = random.Random(seed ^ 0xABCD)  # event selection only
        self.pool = list(pool_for(country_key))
        country_seeds = os.path.join(SEEDS_DIR, f"seeds_{country_key}.json")
        if os.path.exists(country_seeds):
            self.pool += load_country_seeds(country_seeds)
        global_seeds = os.path.join(SEEDS_DIR, "seeds_global.json")
        self.globals = load_global_seeds(global_seeds) if os.path.exists(global_seeds) else []
        self.state = WorldState(
            country=country_key,
            month=1,
            indicators=dict(self.country.indicators),
            factions=dict(self.country.factions),
            rng_seed=seed,
        )
        for key, agent in self.country.agents.items():
            self.state.agent_favor[key] = agent.start_favor
            self.state.agent_stances[key] = favor_to_stance(agent.start_favor)
        self._decision_counter = 0
        self._last_mode: str | None = None
        # per-figure private lunch transcripts (session memory): figure_key -> [{"q","a"}]
        self.conversations: dict[str, list[dict]] = {}

    # -- lifecycle ---------------------------------------------------------------

    def start(self):
        self.state.objectives = parse_objectives(self.llm.setup_objectives(self.country, self.state))
        self.state.cast = parse_cast(self.llm.cast_design(self.country, self.state))
        return self.state.objectives

    def month_events(self) -> list[Event]:
        # Shared global facts (hooked for this country) are injected on top of the country deck.
        cap = EARLY_GAME_CAP if self.state.month <= EARLY_GAME_MONTHS else MAX_EVENTS_PER_MONTH
        injected = fire_global_events(self.globals, self.state, self.state.month)
        selected = select_events(self.pool, self.state, self.rng, n=cap)
        return (injected + selected)[:cap]

    def present(self, event: Event) -> tuple[NarratorOutput, list[Option]]:
        narration = NarratorOutput.parse(self.llm.narrate(event, self.state, self._last_mode))
        self.state.pending_alert = ""  # one-shot: consumed by the narrator
        options = parse_options(self.llm.options(event, self.state))
        return narration, options

    def act(self, event: Event, action: Action) -> tuple[JudgeOutput, ResolveResult]:
        judge = JudgeOutput.parse(self.llm.judge(event, action, self.state))
        self._decision_counter += 1
        result = resolve(
            self.state, self.country, event, judge, self.dice, self.state.month, self._decision_counter
        )
        self.state.consumed_events.add(event.id)
        self._last_mode = result.mode
        return judge, result

    def converse(self, figure_key: str, question: str) -> str:
        """A private, off-the-record 'lunch' with one figure. Pure intel: it reveals their
        interests and candid read of the situation but moves no indicators (§ no exploit)."""
        figure = self.country.agents[figure_key]
        persona = load_persona(self.country.key, figure_key)
        history = self.conversations.setdefault(figure_key, [])
        from engine.schemas import parse_chat_reply
        reply = parse_chat_reply(self.llm.converse(figure, persona, question, self.state, history))
        history.append({"q": question, "a": reply})
        return reply

    def end_month(self) -> None:
        apply_active_modifiers(self.state)  # background effects from global shocks (oil, trade)
        end_of_month_upkeep(self.state, self.country, self.dice, self.state.month)
        if self.state.game_over is None and self.state.month >= 12:
            self._final_verdict()
        if self.state.game_over is None:
            self.state.month += 1

    @property
    def is_over(self) -> bool:
        return self.state.game_over is not None

    def _final_verdict(self) -> None:
        met = self.state.objectives_met()
        total = len(self.state.objectives)
        if met >= 6:
            self.state.game_over = "victory"
            self.state.ending_text = f"You survived 2025 and delivered {met}/{total} objectives. A defining term."
        elif met >= 3:
            self.state.game_over = "mixed_term"
            self.state.ending_text = f"You made it to December with {met}/{total} objectives. History will be divided."
        else:
            self.state.game_over = "failed_term"
            self.state.ending_text = f"The year ends with only {met}/{total} objectives met. A wasted mandate."
