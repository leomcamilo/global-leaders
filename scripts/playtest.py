#!/usr/bin/env python3
"""Headless 12-month playtest with the real model (polish Frente 3).

Plays a country with a simple policy and logs the indicator trajectory + faction meters +
outcome, so we can validate the Nemotron's real deltas and calibrate balance.

    python scripts/playtest.py usa
    python scripts/playtest.py china --policy bold --seed 7

Uses Ollama (Nemotron) if OLLAMA_API_KEY is set, else FakeLLM.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.game import Game  # noqa: E402
from engine.llm import FakeLLM  # noqa: E402
from engine.schemas import Option  # noqa: E402
from engine.state import INDICATOR_LABELS  # noqa: E402
from scripts.research_country import load_dotenv  # noqa: E402

PREF = {
    "cautious": ["cautious", "technocratic", "conciliatory"],
    "bold": ["bold", "defiant", "populist"],
}


def make_llm():
    load_dotenv()
    if os.environ.get("OLLAMA_API_KEY"):
        from engine.llm_remote import OllamaCloudLLM
        return OllamaCloudLLM(fallback=FakeLLM(), verbose=False), "Nemotron"
    return FakeLLM(), "FakeLLM"


def pick(options, tones):
    for t in tones:
        for o in options:
            if o.tone == t:
                return o
    return options[len(options) // 2]


def snapshot(state) -> str:
    return " ".join(f"{k[:3]}{state.indicators[k]:>3}" for k in INDICATOR_LABELS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("country")
    ap.add_argument("--policy", default="cautious", choices=list(PREF))
    ap.add_argument("--seed", type=int, default=2025)
    args = ap.parse_args()

    llm, backend = make_llm()
    g = Game(args.country, llm, seed=args.seed)
    g.start()
    print(f"=== PLAYTEST {g.country.name} · {backend} · policy={args.policy} · seed={args.seed} ===")
    print("start:", snapshot(g.state))
    if g.state.factions:
        print("factions:", g.state.factions)
    print("objectives:", " | ".join(f"{o.indicator}{o.op}{o.target}" for o in g.state.objectives))

    months = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    while not g.is_over and g.state.month <= 12:
        m = g.state.month
        for ev in g.month_events():
            _narr, opts = g.present(ev)
            choice = pick(opts, PREF[args.policy])
            judge, result = g.act(ev, choice)
            label = choice.label if isinstance(choice, Option) else str(choice)
            tag = {"backfire": " 💥", "windfall": " ✨", "rejected": " ✗"}.get(result.mode, "")
            dl = ",".join(f"{k[:3]}{'+' if v >= 0 else ''}{v}" for k, v in result.applied.items() if v)
            print(f"  {months[m]} [{ev.title_seed[:40]:40}] -> {label[:28]:28}{tag} {dl}")
            if g.is_over:
                break
        g.end_month()
        if not g.is_over:
            line = snapshot(g.state)
            fac = (" | " + " ".join(f"{k.split('_')[0]}{v}" for k, v in g.state.factions.items())) if g.state.factions else ""
            print(f"  -- end {months[m]}: {line}{fac}")

    print(f"\nOUTCOME: {g.state.game_over} | objectives {g.state.objectives_met()}/8 | "
          f"{'survived' if g.state.month >= 12 else 'fell ' + months[min(g.state.month,12)]}")
    print("final:", snapshot(g.state))


if __name__ == "__main__":
    main()
