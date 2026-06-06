#!/usr/bin/env python3
"""Headless playthrough in the terminal — no model, no deps (uses the FakeLLM stub).

Examples:
    python scripts/play_demo.py                      # China, FakeLLM, 'neglect the PLA' -> coup arc
    python scripts/play_demo.py --policy control      # purge the clique early -> survive on that axis
    python scripts/play_demo.py --policy interactive   # you pick the options

    # Live generative narrative via Ollama Cloud (needs OLLAMA_API_KEY in env or .env):
    python scripts/play_demo.py --llm ollama --policy interactive
    python scripts/play_demo.py --llm ollama --model nemotron-3-super
    python scripts/play_demo.py --llm openrouter --model nvidia/nemotron-nano-9b-v2
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.events import Event  # noqa: E402
from engine.game import Game  # noqa: E402
from engine.llm import FakeLLM  # noqa: E402
from engine.schemas import Option  # noqa: E402
from engine.state import INDICATOR_LABELS, WorldState  # noqa: E402

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_dotenv(path: str | None = None) -> None:
    """Tiny stdlib .env loader: KEY=VALUE lines -> os.environ (does not overwrite existing)."""
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def bar(value: int, width: int = 20) -> str:
    filled = round(value / 100 * width)
    return "█" * filled + "·" * (width - filled)


def render_indicators(state: WorldState) -> None:
    for key, label in INDICATOR_LABELS.items():
        v = state.indicators[key]
        print(f"    {label:<14} {bar(v)} {v:>3}")
    if state.factions:
        print("    " + "-" * 38)
        hidden = {"party_loyalty": "Party loyalty", "pla_loyalty": "PLA loyalty",
                  "coup_plot_progress": "Coup plot"}
        for key, label in hidden.items():
            if key in state.factions:
                v = state.factions[key]
                print(f"    {label:<14} {bar(v)} {v:>3}  (hidden)")


# --- scripted policies ----------------------------------------------------------

def policy_neglect(event: Event, options: list[Option]) -> Option:
    """Passive: prefer the cautious/conciliatory line. Lets the PLA plot mature."""
    return _prefer(options, ["cautious", "conciliatory", "technocratic"], default_index=-1)


def policy_control(event: Event, options: list[Option]) -> Option:
    """Assertive: prefer the decisive line (purge the clique, project strength)."""
    return _prefer(options, ["defiant", "bold", "populist"], default_index=0)


def policy_interactive(event: Event, options: list[Option]) -> Option:
    ids = "/".join(o.id for o in options)
    while True:
        choice = input(f"    Your call ({ids} or free text): ").strip()
        match = _by_id(options, choice.upper())
        if match:
            return match
        if choice:
            return choice  # free text -> judged by the SLM
        print("    pick an option or type something.")


def _by_id(options: list[Option], oid: str) -> Option | None:
    return next((o for o in options if o.id.upper() == oid), None)


def _prefer(options: list[Option], tones: list[str], default_index: int) -> Option:
    """Robust against real-model variability: pick by tone, else fall back to position."""
    for tone in tones:
        for o in options:
            if o.tone == tone:
                return o
    return options[default_index]


POLICIES = {"neglect": policy_neglect, "control": policy_control, "interactive": policy_interactive}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="china")
    ap.add_argument("--policy", default="neglect", choices=list(POLICIES))
    ap.add_argument("--seed", type=int, default=2025)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--llm", default="fake", choices=["fake", "ollama", "openrouter"])
    ap.add_argument("--model", default=None, help="model slug; default depends on backend")
    args = ap.parse_args()

    load_dotenv()
    if args.llm == "fake":
        llm = FakeLLM()
    else:
        from engine.llm_remote import BACKENDS

        backend = BACKENDS[args.llm]
        kwargs = {"fallback": FakeLLM(), "verbose": True}
        if args.model:
            kwargs["model"] = args.model
        llm = backend(**kwargs)
        print(f"  [using {args.llm} model: {llm.model}]")

    pick = POLICIES[args.policy]
    game = Game(args.country, llm, seed=args.seed)
    objectives = game.start()

    print("=" * 60)
    print(f"  GLOBAL LEADERS  —  {game.country.name} ({game.country.leader}), 2025")
    print(f"  policy: {args.policy}   seed: {args.seed}")
    print("=" * 60)
    print("\n  YOUR 8 OBJECTIVES FOR THE YEAR:")
    for o in objectives:
        print(f"   • [{o.difficulty:<6}] {o.title}")
    print("\n  YOUR CABINET & RIVALS:")
    for f in game.country.roster:
        persona = game.state.cast.get(f.key, {})
        cv = persona.get("core_value", "")
        traits = ", ".join(persona.get("traits", []))
        tail = f" — {cv}" + (f" [{traits}]" if traits else "") if cv or traits else ""
        print(f"   • {f.name} ({f.role}){tail}")
    print("\n  STARTING STATE:")
    render_indicators(game.state)

    while not game.is_over and game.state.month <= args.months:
        m = game.state.month
        print("\n" + "=" * 60)
        print(f"  {MONTHS[m].upper()} 2025")
        print("=" * 60)
        for event in game.month_events():
            narration, options = game.present(event)
            print(f"\n  ► {narration.headline}")
            print(f"    {narration.narrative}")
            roster = game.country.agents
            for r in narration.agent_reactions:
                who = roster[r.agent].name if r.agent in roster else r.agent
                print(f"      — {who} ({r.stance}): \"{r.quote}\"")
            print(f"    Stakes: {narration.stakes}")
            print("    Options:")
            for o in options:
                print(f"      {o.id}) {o.label}  [{o.tone}]")

            choice = pick(event, options)
            label = choice.label if isinstance(choice, Option) else f'"{choice}"'
            print(f"    → You chose: {label}")

            judge, result = game.act(event, choice)
            if result.mode == "rejected":
                print(f"    ✗ {result.note}")
            else:
                deltas = ", ".join(
                    f"{INDICATOR_LABELS.get(k, k)} {('+' if v >= 0 else '')}{v}"
                    for k, v in result.applied.items() if v
                )
                tag = {"backfire": "  💥 BACKFIRED", "windfall": "  ✨ WINDFALL"}.get(result.mode, "")
                print(f"    ⇒ {judge.consequence_narrative}{tag}")
                print(f"      Effects: {deltas or 'no net change'}")
            if game.is_over:
                break

        game.end_month()
        if not game.is_over:
            print("\n  State after the month:")
            render_indicators(game.state)

    print("\n" + "#" * 60)
    if game.is_over:
        print(f"  GAME OVER — {game.state.game_over}")
        print(f"  {game.state.ending_text}")
    else:
        print(f"  STOPPED after {args.months} month(s) — not a real ending (use --months 12).")
    print(f"  Objectives met: {game.state.objectives_met()}/{len(game.state.objectives)}")
    print("#" * 60)


if __name__ == "__main__":
    main()
