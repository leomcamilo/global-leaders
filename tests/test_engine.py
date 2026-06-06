"""Engine unit tests — run with:  python -m unittest discover -s tests
No third-party deps; uses stdlib unittest. Variance is pinned with FixedDice."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.countries import get_country  # noqa: E402
from engine.dice import Dice, Roll  # noqa: E402
from engine.events import Event, event_weight, meets_preconditions  # noqa: E402
from engine.game import Game  # noqa: E402
from engine.llm import FakeLLM  # noqa: E402
from engine.resolver import check_game_over, end_of_month_upkeep, resolve  # noqa: E402
from engine.schemas import JudgeOutput, SchemaError, parse_objectives  # noqa: E402
from engine.state import WorldState  # noqa: E402


class FixedDice(Dice):
    """Deterministic dice for tests: always the same factor/mode."""

    def __init__(self, factor: float = 1.0, mode: str = "normal"):
        super().__init__(0)
        self._factor, self._mode = factor, mode

    def roll(self, turn: int, idx: int = 0) -> Roll:
        return Roll(self._factor, self._mode)


def fresh_china() -> tuple[WorldState, object]:
    c = get_country("china")
    s = WorldState(country="china", month=4, indicators=dict(c.indicators), factions=dict(c.factions))
    for k, a in c.agents.items():
        s.agent_favor[k] = a.start_favor
    return s, c


def clique_event() -> Event:
    from engine.events import CHINA_EVENTS

    return next(e for e in CHINA_EVENTS if e.id == "cn_2025_04_pla_clique")


class TestDeltasAndGuardrails(unittest.TestCase):
    def test_magnitude_clamp(self):
        s, c = fresh_china()
        judge = JudgeOutput.parse({
            "interpretation": "huge econ push", "magnitude": "major", "plausibility": "ok",
            "effects": [{"indicator": "economy", "direction": "+", "proposed_delta": 50}],
        })
        res = resolve(s, c, clique_event(), judge, FixedDice(1.0), turn=4)
        # |50| clamped to major hi (10); factor 1.0 -> +10.
        self.assertEqual(res.applied["economy"], 10)

    def test_no_free_lunch_injects_cost(self):
        s, c = fresh_china()
        judge = JudgeOutput.parse({
            "interpretation": "all upside", "magnitude": "major", "plausibility": "ok",
            "effects": [{"indicator": "economy", "direction": "+", "proposed_delta": 10}],
        })
        res = resolve(s, c, clique_event(), judge, FixedDice(1.0), turn=4)
        self.assertTrue(any(v < 0 for v in res.applied.values()), "major move must carry a trade-off")

    def test_impossible_is_noop(self):
        s, c = fresh_china()
        before = dict(s.indicators)
        judge = JudgeOutput.parse({
            "interpretation": "turn rivers to gold", "magnitude": "minor",
            "plausibility": "impossible", "effects": [],
        })
        res = resolve(s, c, clique_event(), judge, FixedDice(1.0), turn=4)
        self.assertEqual(res.mode, "rejected")
        self.assertEqual(s.indicators, before)

    def test_clamped_to_0_100(self):
        s, c = fresh_china()
        s.indicators["fiscal_health"] = 3
        judge = JudgeOutput.parse({
            "interpretation": "spend big", "magnitude": "radical", "plausibility": "ok",
            "effects": [{"indicator": "fiscal_health", "direction": "-", "proposed_delta": 20}],
        })
        resolve(s, c, clique_event(), judge, FixedDice(1.0), turn=4)
        self.assertGreaterEqual(s.indicators["fiscal_health"], 0)


class TestDice(unittest.TestCase):
    def test_reproducible(self):
        d1, d2 = Dice(123), Dice(123)
        for t in range(1, 13):
            r1, r2 = d1.roll(t, 1), d2.roll(t, 1)
            self.assertEqual((r1.factor, r1.mode), (r2.factor, r2.mode))

    def test_backfire_inverts_sign(self):
        roll = Roll(1.0, "backfire")
        self.assertLess(roll.apply(10), 0)


class TestSchemas(unittest.TestCase):
    def test_bad_magnitude_rejected(self):
        with self.assertRaises(SchemaError):
            JudgeOutput.parse({"magnitude": "huge", "plausibility": "ok", "effects": []})

    def test_objectives_must_be_eight(self):
        with self.assertRaises(SchemaError):
            parse_objectives({"objectives": [{"title": "x", "metric": {"indicator": "economy",
                                                                       "op": ">=", "target": 50}}]})

    def test_fake_llm_objectives_valid(self):
        s, c = fresh_china()
        objs = parse_objectives(FakeLLM().setup_objectives(c, s))
        self.assertEqual(len(objs), 8)


class TestGameOver(unittest.TestCase):
    def test_dem_removal(self):
        c = get_country("usa")
        s = WorldState(country="usa", indicators=dict(c.indicators))
        s.indicators["approval"] = 10
        s.indicators["institutional_stability"] = 20
        check_game_over(s, c)
        self.assertEqual(s.game_over, "removed_from_office")

    def test_china_party_ouster(self):
        s, c = fresh_china()
        s.factions["party_loyalty"] = 10
        check_game_over(s, c)
        self.assertEqual(s.game_over, "party_ouster")

    def test_china_coup_when_pla_collapses(self):
        s, c = fresh_china()
        s.factions["pla_loyalty"] = 15
        check_game_over(s, c)
        self.assertEqual(s.game_over, "pla_coup")

    def test_china_coup_plot_matures_when_neglected(self):
        s, c = fresh_china()
        s.flags["pla_clique_handled"] = False
        s.factions["pla_loyalty"] = 35
        for t in range(4, 13):
            end_of_month_upkeep(s, c, FixedDice(1.0), turn=t)
            if s.game_over:
                break
        self.assertEqual(s.game_over, "pla_coup")


class TestElites(unittest.TestCase):
    def test_every_country_has_an_elite(self):
        from engine.countries import COUNTRIES
        for key, c in COUNTRIES.items():
            elites = [f for f in c.roster if f.faction == "elite"]
            self.assertEqual(len(elites), 1, f"{key} should have exactly one elite figure")
            self.assertGreater(elites[0].influence, 0)

    def test_elite_influence_differs_by_country(self):
        from engine.countries import get_country
        br = next(f for f in get_country("brazil").roster if f.faction == "elite")
        cn = next(f for f in get_country("china").roster if f.faction == "elite")
        self.assertGreater(br.influence, cn.influence)  # Brazil elite >> China elite

    def test_hostile_elite_drags_economy(self):
        from engine.countries import get_country
        from engine.resolver import _elite_pressure
        c = get_country("brazil")
        s = WorldState(country="brazil", indicators=dict(c.indicators))
        s.agent_favor["elites"] = -80.0  # furious elite
        eco0, fis0 = s.indicators["economy"], s.indicators["fiscal_health"]
        _elite_pressure(s, c)
        self.assertLess(s.indicators["economy"], eco0)
        self.assertLess(s.indicators["fiscal_health"], fis0)


class TestCalibration(unittest.TestCase):
    def test_resilience_lifts_extreme_lows(self):
        from engine.resolver import _resilience
        s = WorldState(country="usa", indicators={"economy": 20, "approval": 50, "security": 90})
        _resilience(s)
        self.assertEqual(s.indicators["economy"], 22)   # <25 -> +2
        self.assertEqual(s.indicators["approval"], 50)  # mid -> unchanged
        self.assertEqual(s.indicators["security"], 89)  # >88 -> -1

    def test_pla_coup_warning_fires_before_the_coup(self):
        s, c = fresh_china()
        s.flags["pla_clique_handled"] = False
        s.factions["pla_loyalty"] = 35
        warned = False
        for t in range(4, 12):
            end_of_month_upkeep(s, c, FixedDice(1.0), turn=t)
            if s.pending_alert:
                warned = True
            if s.game_over:
                break
        self.assertTrue(warned, "the player must be warned before the PLA coup")


class TestChinaArc(unittest.TestCase):
    def test_purge_defuses_plot(self):
        s, c = fresh_china()
        ev = clique_event()
        from engine.schemas import parse_options

        options = parse_options(FakeLLM().options(ev, s))
        purge = next(o for o in options if o.id == "A")
        judge = JudgeOutput.parse(FakeLLM().judge(ev, purge, s))
        resolve(s, c, ev, judge, FixedDice(1.0), turn=4)
        self.assertTrue(s.flags.get("pla_clique_handled"))
        self.assertEqual(s.factions["coup_plot_progress"], 0)


class TestPersonas(unittest.TestCase):
    def test_every_figure_has_a_persona_file(self):
        from engine.countries import COUNTRIES
        from engine.personas import load_persona
        for key, c in COUNTRIES.items():
            for f in c.roster:
                self.assertIsNotNone(load_persona(key, f.key),
                                     f"missing persona file for {key}/{f.key}")

    def test_persona_strips_frontmatter(self):
        from engine.personas import load_persona
        body = load_persona("france", "opposition_rn")
        self.assertFalse(body.startswith("---"))
        self.assertIn("#", body)  # has the markdown heading / prose

    def test_converse_records_transcript(self):
        game = Game("france", FakeLLM(), seed=7)
        game.start()
        r1 = game.converse("opposition_rn", "Will you back me?")
        self.assertTrue(r1)
        game.converse("opposition_rn", "And on immigration?")
        self.assertEqual(len(game.conversations["opposition_rn"]), 2)

    def test_converse_reply_schema(self):
        from engine.schemas import SchemaError, parse_chat_reply
        self.assertEqual(parse_chat_reply({"reply": "hi"}), "hi")
        with self.assertRaises(SchemaError):
            parse_chat_reply({"reply": ""})


class TestEventSelection(unittest.TestCase):
    def test_preconditions(self):
        ev = Event(id="x", type="conditional", title_seed="t", fact="f",
                   touches=["security"], preconditions={"security": "<35"})
        s = WorldState(country="china", indicators={"security": 30})
        self.assertTrue(meets_preconditions(ev, s))
        s.indicators["security"] = 60
        self.assertFalse(meets_preconditions(ev, s))

    def test_weakness_raises_weight(self):
        ev = Event(id="x", type="conditional", title_seed="t", fact="f", touches=["economy"])
        weak = WorldState(country="china", indicators={"economy": 10})
        strong = WorldState(country="china", indicators={"economy": 90})
        self.assertGreater(event_weight(ev, weak), event_weight(ev, strong))


class TestSeeds(unittest.TestCase):
    def test_global_event_hook_manifests_per_country(self):
        from engine.seeds import GlobalEvent, manifest_hook

        ge = GlobalEvent(
            id="iran_war", title="Israel-Iran war", fact="Strikes escalate.", month=6,
            hooks={"usa": {"touches": ["international_power", "security"],
                           "dilemma": "Intervene or stay out?", "figures": ["sec_state"]}},
        )
        ev = manifest_hook(ge, "usa")
        self.assertEqual(ev.id, "iran_war__usa")
        self.assertEqual(ev.month, 6)
        self.assertIn("international_power", ev.touches)
        self.assertIsNone(manifest_hook(ge, "brazil"))  # no hook for brazil

    def test_world_modifier_applies_and_decays(self):
        from engine.seeds import GlobalEvent, WorldModifier, apply_active_modifiers, fire_global_events
        from engine.countries import get_country

        c = get_country("russia")
        s = WorldState(country="russia", indicators=dict(c.indicators))
        eco0 = s.indicators["economy"]
        ge = GlobalEvent(id="oil_shock", title="Oil spikes", fact="Prices jump.", month=6,
                         world_modifier=WorldModifier("oil_shock", "Oil price spike", months=2,
                                                      deltas={"russia": {"economy": +5}}))
        injected = fire_global_events([ge], s, month=6)
        self.assertEqual(injected, [])  # russia has no hook -> background modifier instead
        self.assertEqual(len(s.active_modifiers), 1)
        apply_active_modifiers(s)
        self.assertEqual(s.indicators["economy"], eco0 + 5)
        apply_active_modifiers(s)  # second (last) month
        self.assertEqual(s.active_modifiers, [])  # expired


def run_neglect(seed: int) -> Game:
    """Inline 'always tolerate / stand down' playthrough (no CLI dependency)."""
    game = Game("china", FakeLLM(), seed=seed)
    game.start()
    while not game.is_over and game.state.month <= 12:
        for ev in game.month_events():
            _narr, options = game.present(ev)
            choice = next((o for o in options if o.id == "B"), options[0])
            game.act(ev, choice)
            if game.is_over:
                break
        game.end_month()
    return game


class TestFullPlaythrough(unittest.TestCase):
    def test_neglect_china_runs_to_an_ending(self):
        game = run_neglect(seed=2025)
        self.assertTrue(game.is_over)
        self.assertIsNotNone(game.state.game_over)


if __name__ == "__main__":
    unittest.main(verbosity=2)
