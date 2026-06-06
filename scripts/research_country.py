#!/usr/bin/env python3
"""Curate a country's 2025 event deck entirely on Ollama Cloud (no Claude tokens).

Pipeline: web_search (grounding) -> glm-5.1 extracts events as seed JSON -> validate.
    python scripts/research_country.py russia
    python scripts/research_country.py france --model glm-5.1 --out seeds/seeds_france.json

Needs OLLAMA_API_KEY (read from .env). Output is a draft seeds file to review before use.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.countries import get_country  # noqa: E402
from engine.llm_remote import extract_json  # noqa: E402
from engine.seeds import event_from_dict  # noqa: E402
from engine.state import FACTION_KEYS, INDICATORS  # noqa: E402

OLLAMA = os.environ.get("OLLAMA_HOST", "https://ollama.com").rstrip("/")


def load_dotenv() -> None:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _post(path: str, payload: dict, timeout: int = 180) -> dict:
    key = os.environ["OLLAMA_API_KEY"]
    req = urllib.request.Request(
        OLLAMA + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}") from e


def web_search(query: str, max_results: int = 5) -> list[dict]:
    r = _post("/api/web_search", {"query": query, "max_results": max_results})
    return r.get("results", r if isinstance(r, list) else [])


def chat(model: str, system: str, user: str) -> str:
    r = _post("/api/chat", {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.4, "num_ctx": 32768, "num_predict": 8192},
    }, timeout=600)
    return r["message"]["content"]


# --- Search angles per country --------------------------------------------------

# Eight angles per country covering the categories the deck must span:
# disasters/emergencies, politics/institutions, security/crime, education, health,
# economy/fiscal, detailed diplomacy, and global/shared shocks.
QUERIES = {
    "usa": [
        "United States 2025 natural disasters hurricanes wildfires floods Texas emergencies",
        "United States Trump 2025 politics institutions Epstein shutdown executive orders",
        "United States 2025 immigration ICE crime National Guard protests security",
        "United States 2025 education department dismantle school funding student loans",
        "United States 2025 health RFK MAHA vaccines measles outbreak Medicaid cuts",
        "United States Trump 2025 tariffs economy inflation Federal Reserve deficit",
        "United States Trump 2025 diplomacy Iran Israel Ukraine Russia China Venezuela",
        "United States 2025 global trade war oil price shock allies NATO",
    ],
    "brazil": [
        "Brazil 2025 natural disasters floods drought Amazon fires blackout metanol emergencies",
        "Brazil Lula 2025 politics Bolsonaro trial IOF Congress INSS scandal",
        "Brazil 2025 security Rio police operation factions PCC Comando Vermelho",
        "Brazil 2025 education university ENEM students funding reform",
        "Brazil 2025 health SUS dengue outbreak Mais Medicos hospitals",
        "Brazil Lula 2025 economy fiscal Haddad tax income exemption",
        "Brazil Lula 2025 diplomacy Trump tariff China Xi BRICS COP30 Venezuela",
        "Brazil 2025 global oil price Petrobras grains fertilizers trade war",
    ],
    "russia": [
        "Russia 2025 natural disasters floods wildfires Black Sea oil spill emergencies",
        "Russia Putin 2025 domestic politics elites repression major events",
        "Russia 2025 security terrorism attacks Ukraine drones refineries Kursk",
        "Russia 2025 education schools militarization patriotic youth curriculum",
        "Russia 2025 health demographics mortality healthcare system",
        "Russia 2025 economy sanctions oil gas revenue inflation ruble interest rate",
        "Russia Putin Trump 2025 Ukraine peace negotiations Alaska summit ceasefire",
        "Russia China Iran North Korea 2025 CRINK relations oil global BRICS",
    ],
    "argentina": [
        "Argentina 2025 natural disasters Bahia Blanca floods storms emergencies",
        "Argentina Milei 2025 politics LIBRA scandal decrees midterm elections",
        "Argentina Milei 2025 security protests crime Bullrich repression",
        "Argentina Milei 2025 education university funding CONICET protests march",
        "Argentina Milei 2025 health Garrahan children hospital funding cuts protests",
        "Argentina Milei 2025 economy inflation peso IMF reserves austerity",
        "Argentina Milei 2025 United States Trump Bessent currency swap diplomacy",
        "Argentina 2025 Mercosur Brazil China Venezuela relations global trade",
    ],
    "france": [
        "France 2025 natural disasters floods storms heatwave wildfires emergencies",
        "France Macron 2025 government collapse Bayrou Lecornu no confidence politics",
        "France 2025 security terrorism crime riots prison attacks",
        "France 2025 education school reform teachers students universities protests",
        "France 2025 health hospital system funding crisis doctors",
        "France 2025 budget deficit debt austerity bond market pension",
        "France Macron 2025 Palestine recognition Ukraine European defense diplomacy",
        "France 2025 EU global trade tariffs Mercosur Iran connections",
    ],
    "china": [
        "China 2025 natural disasters floods earthquakes typhoons emergencies",
        "China Xi 2025 PLA purge generals He Weidong Miao Hua military commission loyalty",
        "China 2025 security protests public mass attacks censorship unrest",
        "China 2025 education youth unemployment graduates universities reform",
        "China 2025 health public system population aging healthcare",
        "China 2025 economy property crisis deflation stimulus rare earths exports",
        "China US 2025 trade war tariffs Geneva truce Taiwan diplomacy Wang Yi",
        "China Russia Iran 2025 oil Strait of Hormuz BRICS global",
    ],
}


def system_prompt(country) -> str:
    indicators = list(INDICATORS) + list(country.factions.keys())
    return (
        f"You are a meticulous political-history researcher building a 2025 event deck for the country "
        f"{country.name} (leader: {country.leader}) for a strategy game. Use ONLY the provided search "
        f"material as ground truth; do not invent facts. Output a single JSON object, no prose.\n\n"
        f"Each event is a 'case': a real, dated 2025 fact that forced the leader into a hard decision with "
        f"trade-offs and no single right answer.\n\n"
        f"Valid indicator keys for 'touches': {indicators}.\n"
        f"Valid figure keys (use ONLY these for 'figures' and 'stakeholder_positions'): {figkeys_block(country)}.\n\n"
        f"Schema: {{\"events\": [{{"
        f"\"id\": \"{country.key}_2025_<mm>_<slug>\", "
        f"\"type\": \"anchored\" (dated) or \"conditional\" (state-triggered, no month), "
        f"\"month\": 1-12 or null, "
        f"\"title_seed\": \"short headline\", "
        f"\"fact\": \"1-3 factual sentences with the date\", "
        f"\"touches\": [\"<indicator>\", ...], "
        f"\"dilemma\": \"the choice with trade-offs\", "
        f"\"hidden_info\": \"what was uncertain at the time\", "
        f"\"figures\": [\"<key>\", ...], "
        f"\"stakeholder_positions\": {{\"<key>\": \"their stance quote\"}}, "
        f"\"preconditions\": {{}} (for conditional, e.g. {{\"economy\": \"<40\"}}), "
        f"\"branchable\": true/false}}, ...]}}\n\n"
        f"Produce 11-15 events: mostly anchored across different months (Jan->Dec), plus 2-3 conditional. "
        f"Prefer events with clear dates and named figures from the list.\n\n"
        f"IMPORTANT — span ALL of these categories wherever real 2025 facts exist (not just politics): "
        f"(1) disasters & emergencies (natural disasters, accidents, public-health emergencies), "
        f"(2) domestic politics & institutions, (3) security & crime, (4) education, (5) health, "
        f"(6) economy & fiscal, (7) detailed diplomacy (named foreign leaders, summits, bilateral deals), "
        f"(8) global/shared shocks (trade war, Iran war/oil, Ukraine war). Aim for variety across these."
    )


# International/diplomatic angles — to rebalance decks that under-represent the leader's
# real 2025 foreign-policy decisions (esp. Russia's Ukraine war and France's EU/defense role).
INTL_QUERIES = {
    "usa": [
        "Trump 2025 Greenland Panama Canal Canada annexation diplomacy",
        "Trump 2025 Gaza ceasefire Israel Netanyahu hostage deal plan",
        "Trump 2025 NATO summit Hague 5 percent defense spending allies",
        "Ukraine 2025 minerals deal Trump Zelensky Oval Office clash ceasefire",
        "Trump 2025 India Pakistan ceasefire Modi tariffs trade deal",
    ],
    "brazil": [
        "Brazil Lula 2025 BRICS summit Rio July de-dollarization",
        "Trump 50 percent tariff Brazil August 2025 Bolsonaro Moraes sanctions",
        "Brazil Lula 2025 COP30 Belem climate summit hosting",
        "Brazil Lula 2025 Venezuela Maduro Essequibo Celac diplomacy",
        "Brazil Mercosur EU trade agreement 2025 France resistance",
    ],
    "russia": [
        "Russia Ukraine 2025 ceasefire negotiations Istanbul talks Putin Zelensky",
        "Trump Putin 2025 ultimatum sanctions deadline peace deal pressure",
        "Russia 2025 drone war escalation strikes Ukraine energy Kursk offensive",
        "Russia North Korea 2025 troops Kim Jong Un Kursk deployment treaty",
        "Russia China 2025 Power of Siberia 2 gas deal India oil sanctions",
        "Russia 2025 prisoner exchange territory negotiation frozen assets EU",
    ],
    "china": [
        "China US 2025 trade war Geneva London truce tariff de-escalation",
        "China 2025 rare earth export controls leverage magnets global",
        "China Taiwan 2025 military drills Lai Ching-te pressure reunification",
        "China Putin 2025 SCO summit Tianjin Global South leaders",
        "China EU 2025 electric vehicle tariffs trade tensions summit",
    ],
    "argentina": [
        "Milei Trump 2025 Mar-a-Lago meeting alignment United States",
        "Argentina US 2025 20 billion currency swap Bessent Treasury bailout",
        "Argentina IMF 2025 program agreement disbursement reserves Georgieva",
        "Milei 2025 Israel Jerusalem embassy move foreign policy alignment",
        "Argentina Mercosur 2025 Brazil Lula tension China relations",
    ],
    "france": [
        "Macron 2025 Ukraine coalition of the willing reassurance force troops",
        "Macron 2025 Palestine state recognition September UN General Assembly",
        "France 2025 European defense rearmament EU 800 billion ReArm Europe",
        "Macron Trump 2025 tariffs EU trade response transatlantic tension",
        "France 2025 Mercosur EU trade deal opposition farmers protests",
        "Macron 2025 Iran nuclear snapback sanctions E3 diplomacy",
    ],
}


def international_user(country, material: str, existing_titles: list[str]) -> str:
    covered = "\n".join(f"- {t}" for t in existing_titles)
    return (
        f"SEARCH MATERIAL (2025 — foreign policy & diplomacy):\n\n{material}\n\n"
        f"The deck ALREADY covers these events (do NOT duplicate them):\n{covered}\n\n"
        f"Add 6-9 NEW *international* events: summits, wars, ceasefire talks, bilateral deals, "
        f"tariffs/sanctions, and decisions involving FOREIGN leaders. EVERY new event MUST include "
        f"\"international_power\" in its 'touches', and should name the relevant foreign/diplomat figures "
        f"from the roster in 'figures'/'stakeholder_positions'. These are the leader's hard FOREIGN-POLICY "
        f"choices in 2025, with real trade-offs. Same JSON schema. Output only the new events."
    )


def complement_user(country, material: str, existing_titles: list[str]) -> str:
    covered = "\n".join(f"- {t}" for t in existing_titles)
    return (
        f"SEARCH MATERIAL (2025):\n\n{material}\n\n"
        f"The deck ALREADY covers these events (do NOT duplicate them):\n{covered}\n\n"
        f"Add 5-8 NEW events that fill UNDER-COVERED categories — especially disasters & emergencies, "
        f"education, and health — plus any other major 2025 gaps not in the list above. "
        f"Same JSON schema. Output only the new events."
    )


def figkeys_block(country) -> str:
    return "; ".join(f"{f.key}={f.name} ({f.faction})" for f in country.roster)


def build_material(country_key: str, per_query: int, queries: list[str] | None = None) -> str:
    blocks = []
    for q in (queries if queries is not None else QUERIES[country_key]):
        print(f"  search: {q}")
        try:
            for res in web_search(q, per_query):
                title = res.get("title", "")
                url = res.get("url", "")
                content = (res.get("content") or "")[:900]
                blocks.append(f"## {title}\n{url}\n{content}")
        except Exception as e:  # noqa: BLE001
            print(f"    (search failed: {e})")
        time.sleep(0.5)
    return "\n\n".join(blocks)


# The model sometimes uses category names as indicator keys; map them to the real 8.
TOUCH_ALIASES = {
    "diplomacy": "international_power", "foreign_policy": "international_power",
    "education": "public_services", "health": "public_services", "healthcare": "public_services",
    "military": "security", "climate": "public_services", "environment": "international_power",
    "fiscal": "fiscal_health", "inflation": "economy",
}


def sanitize(country, data: dict) -> None:
    """Remap aliased 'touches' to real indicator keys; drop unknown figure keys/touches."""
    valid = set(INDICATORS) | set(country.factions.keys())
    roster = set(country.agents.keys())
    for e in data.get("events", []):
        fixed = []
        for t in e.get("touches", []):
            t = TOUCH_ALIASES.get(t, t)
            if t in valid and t not in fixed:
                fixed.append(t)
        e["touches"] = fixed
        e["figures"] = [k for k in e.get("figures", []) if k in roster]
        e["stakeholder_positions"] = {k: v for k, v in e.get("stakeholder_positions", {}).items() if k in roster}


def validate(country, data: dict) -> list[str]:
    roster = set(country.agents.keys())
    valid = set(INDICATORS) | set(FACTION_KEYS)
    issues = []
    events = data.get("events", [])
    for e in events:
        try:
            event_from_dict(e)
        except Exception as ex:  # noqa: BLE001
            issues.append(f"{e.get('id', '?')}: bad shape ({ex})")
            continue
        for k in list(e.get("stakeholder_positions", {})) + e.get("figures", []):
            if k not in roster:
                issues.append(f"{e.get('id')}: unknown figure key '{k}'")
        for t in e.get("touches", []):
            if t not in valid:
                issues.append(f"{e.get('id')}: bad touch '{t}'")
    return issues


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("country", choices=list(QUERIES))
    ap.add_argument("--model", default="glm-5.1")
    ap.add_argument("--per-query", type=int, default=5)
    ap.add_argument("--out", default=None)
    ap.add_argument("--complement", action="store_true",
                    help="add NEW events (disasters/education/health gaps) to the existing seeds file")
    ap.add_argument("--international", action="store_true",
                    help="add NEW international/diplomatic events (foreign-policy decisions) to the seeds file")
    args = ap.parse_args()

    load_dotenv()
    if not os.environ.get("OLLAMA_API_KEY"):
        sys.exit("Set OLLAMA_API_KEY in .env")

    country = get_country(args.country)
    existing_path = f"seeds/seeds_{args.country}.json"

    append_mode = args.complement or args.international
    tag = " [international]" if args.international else " [complement]" if args.complement else ""
    print(f"Researching {country.name} via Ollama ({args.model}){tag}...")
    queries = INTL_QUERIES.get(args.country) if args.international else None
    material = build_material(args.country, args.per_query, queries)
    print(f"  collected {len(material)} chars of search material; asking {args.model}...")

    if append_mode:
        existing = json.load(open(existing_path, encoding="utf-8"))
        titles = [e.get("title_seed", "") for e in existing.get("events", [])]
        user = (international_user(country, material, titles) if args.international
                else complement_user(country, material, titles))
    else:
        existing = None
        user = f"SEARCH MATERIAL (2025):\n\n{material}\n\nNow produce the events JSON."

    t0 = time.time()
    raw = chat(args.model, system_prompt(country), user)
    data = extract_json(raw)
    new_events = data.get("events", [])
    print(f"  model returned {len(new_events)} events in {time.time() - t0:.0f}s")

    sanitize(country, data)
    if append_mode:
        existing_ids = {e["id"] for e in existing["events"]}
        added = [e for e in new_events if e.get("id") not in existing_ids]
        existing["events"].extend(added)
        data = existing
        out = args.out or existing_path
        print(f"  appended {len(added)} new events -> {len(existing['events'])} total")
    else:
        out = args.out or f"seeds/seeds_{args.country}.draft.json"

    issues = validate(country, data)
    print("  validation:", "OK" if not issues else f"{len(issues)} issues")
    for i in issues[:20]:
        print("   -", i)

    data.setdefault("_note", f"{country.name} 2025 deck via Ollama {args.model} + web_search. REVIEW before use.")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
