#!/usr/bin/env python3
"""Give the elite a voice in the events where it matters (polish Frente 1).

The `elites` figure exists in every roster and presses markets mechanically, but the curated
decks were written before it. This adds the elite as a stakeholder (a short in-character line)
to events that touch economy / fiscal_health / international_power — weighted by the country's
elite influence — via one glm-5.1 call per country, leaving everything else untouched.

    python scripts/enrich_elites.py            # all six countries
    python scripts/enrich_elites.py brazil usa  # specific ones

Needs OLLAMA_API_KEY (.env). Edits seeds/seeds_<country>.json in place.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.countries import COUNTRIES, get_country  # noqa: E402
from engine.llm_remote import extract_json  # noqa: E402
from scripts.research_country import chat, load_dotenv  # noqa: E402

ELITE_TOUCHES = {"economy", "fiscal_health", "international_power"}
MODEL = os.environ.get("OLLAMA_MODEL", "glm-5.1")


def _influence_label(v: float) -> str:
    return "very high" if v >= 0.85 else "high" if v >= 0.7 else "moderate" if v >= 0.45 else "low"


def enrich(country_key: str) -> None:
    country = get_country(country_key)
    elite = next((f for f in country.roster if f.faction == "elite"), None)
    if elite is None:
        print(f"  {country_key}: no elite figure, skipping")
        return
    path = f"seeds/seeds_{country_key}.json"
    deck = json.load(open(path, encoding="utf-8"))

    # Pick events where the elite plausibly has a stake and isn't already quoted.
    targets = [
        e for e in deck["events"]
        if "elites" not in e.get("stakeholder_positions", {})
        and (ELITE_TOUCHES & set(e.get("touches", []))
             or any(t in (e.get("title_seed", "") + e.get("fact", "")).lower()
                    for t in ("market", "media", "press", "scandal", "tax", "budget", "trade", "tariff")))
    ]
    if not targets:
        print(f"  {country_key}: nothing to enrich")
        return

    listing = "\n".join(f'- {e["id"]}: {e["title_seed"]} — {e["fact"][:160]}' for e in targets)
    system = (
        f"You write one short in-character line (max ~20 words) for a political-strategy game, spoken by "
        f"the elite bloc of {country.name}: {elite.name} ({elite.role}). Their influence here is "
        f"{_influence_label(elite.influence)} — they care about {', '.join(elite.themes)}. Speak as that bloc "
        f"reacting to each event, advancing their own interests. Output ONLY JSON, no prose."
    )
    user = (
        f"Events:\n{listing}\n\n"
        'Return JSON: {"quotes": {"<event_id>": "their one-line reaction", ...}} — one entry per event id above.'
    )
    raw = chat(MODEL, system, user)
    quotes = extract_json(raw).get("quotes", {})

    n = 0
    by_id = {e["id"]: e for e in deck["events"]}
    for eid, line in quotes.items():
        ev = by_id.get(eid)
        if not ev or not line:
            continue
        ev.setdefault("stakeholder_positions", {})["elites"] = line
        if "elites" not in ev.get("figures", []):
            ev.setdefault("figures", []).append("elites")
        n += 1

    json.dump(deck, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  {country_key}: added elite voice to {n}/{len(targets)} events (influence={elite.influence})")


def main() -> None:
    load_dotenv()
    if not os.environ.get("OLLAMA_API_KEY"):
        sys.exit("Set OLLAMA_API_KEY in .env")
    countries = sys.argv[1:] or list(COUNTRIES)
    for c in countries:
        print(f"Enriching {c} via {MODEL}...")
        enrich(c)


if __name__ == "__main__":
    main()
