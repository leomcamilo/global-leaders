#!/usr/bin/env python3
"""Author one persona .md per figure, per country, on Ollama Cloud (glm-5.1).

For each country we send the whole roster (so the model can write coherent, cross-
referencing personas) and ask for one rich persona per figure. We then write
    engine/prompts/countries/<country>/<figure_key>.md
with DETERMINISTIC frontmatter (the mechanical truth: utility, themes, influence,
start_favor — pulled straight from the Figure) and the model's PROSE below it.

    python scripts/generate_personas.py            # all six countries
    python scripts/generate_personas.py france      # just one
    python scripts/generate_personas.py --model glm-5.1

Needs OLLAMA_API_KEY (read from .env). Review the files before relying on them.
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

from engine.countries import COUNTRIES, get_country  # noqa: E402
from engine.llm_remote import extract_json  # noqa: E402

OLLAMA = os.environ.get("OLLAMA_HOST", "https://ollama.com").rstrip("/")
OUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "engine", "prompts", "countries")


def load_dotenv() -> None:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def chat(model: str, system: str, user: str, temperature: float = 0.75) -> str:
    key = os.environ["OLLAMA_API_KEY"]
    req = urllib.request.Request(
        OLLAMA + "/api/chat",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False, "format": "json", "think": False,
            "options": {"temperature": temperature, "num_ctx": 32768, "num_predict": 16384},
        }).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))["message"]["content"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}") from e


SYSTEM = (
    "You are the casting director and character writer for 'Global Leaders', a serious "
    "political-strategy game set across the real events of 2025. For each real political "
    "figure in a leader's orbit you write a compact, vivid persona grounded in who the real "
    "person actually is. Game-theory matters: every figure pursues its OWN interests, which "
    "may align or clash with the leader's. Stay credible and specific; avoid caricature and "
    "avoid inventing fake scandals as fact. Output ONLY a single JSON object, no prose, no fences."
)


def roster_block(country) -> str:
    lines = []
    for f in country.roster:
        util = ", ".join(f"{k} {v:+.1f}" for k, v in f.utility.items())
        infl = f", influence={f.influence:.1f}" if f.influence else ""
        lines.append(
            f"  - {f.key}: {f.name} — {f.role} ({f.faction}{infl}); "
            f"cares about {', '.join(f.themes) or 'general'}; "
            f"rewards/punishes the leader on: {util}"
        )
    return "\n".join(lines)


def user_prompt(country) -> str:
    return (
        f"COUNTRY: {country.name} | LEADER (the player): {country.leader} | Year: 2025.\n"
        f"The full cast (use these EXACT keys):\n{roster_block(country)}\n\n"
        f"For EVERY figure above, write a persona. The 'rewards/punishes' line is its mechanical "
        f"utility vector — explain that motivation in human terms (what outcomes make it happy or "
        f"furious), without quoting numbers.\n\n"
        f"Return JSON: {{\"personas\": [{{"
        f"\"key\": \"<exact key>\", "
        f"\"summary\": \"1-2 sentences: who they are and their role in {country.leader}'s 2025\", "
        f"\"true_wants\": \"2-3 sentences: what they REALLY want this year, tied to their interests\", "
        f"\"red_lines\": [\"2-4 things that would turn them against the leader\"], "
        f"\"relationship_with_leader\": \"1-2 sentences on how they regard {country.leader} right now\", "
        f"\"speaks_like\": \"1 sentence on their tone/diction\", "
        f"\"at_lunch\": \"1-2 sentences: in a private, off-the-record lunch, how candid vs guarded are "
        f"they, and what do they let slip\", "
        f"\"hidden_angle\": \"1 sentence: a private agenda or tension not obvious in public\"}}, "
        f"... one per figure, EXACTLY {len(country.roster)} entries]}}"
    )


def frontmatter(country, fig) -> str:
    util = ", ".join(f"{k}: {v}" for k, v in fig.utility.items())
    themes = ", ".join(fig.themes)
    return (
        "---\n"
        f"key: {fig.key}\n"
        f"name: {fig.name}\n"
        f"role: {fig.role}\n"
        f"faction: {fig.faction}\n"
        f"country: {country.key}\n"
        f"influence: {fig.influence}\n"
        f"start_favor: {fig.start_favor}\n"
        f"adjustable: {fig.adjustable}\n"
        f"base_utility: {{ {util} }}\n"
        f"themes: [{themes}]\n"
        "---\n"
    )


def render_md(country, fig, p: dict) -> str:
    red = "\n".join(f"- {r}" for r in p.get("red_lines", []) if r) or "- (none recorded)"
    return (
        frontmatter(country, fig)
        + f"\n# {fig.name} — {fig.role}\n\n"
        f"**Who they are.** {p.get('summary', '').strip()}\n\n"
        f"**What they truly want (2025).** {p.get('true_wants', '').strip()}\n\n"
        f"**Red lines.**\n{red}\n\n"
        f"**Relationship with {country.leader}.** {p.get('relationship_with_leader', '').strip()}\n\n"
        f"**How they talk.** {p.get('speaks_like', '').strip()}\n\n"
        f"**Across the lunch table.** {p.get('at_lunch', '').strip()}\n\n"
        f"**The private angle.** {p.get('hidden_angle', '').strip()}\n"
    )


def generate_country(country_key: str, model: str) -> None:
    country = get_country(country_key)
    out_dir = os.path.join(OUT_ROOT, country_key)
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n=== {country.name} ({len(country.roster)} figures) via {model} ===")
    t0 = time.time()
    raw = chat(model, SYSTEM, user_prompt(country))
    data = extract_json(raw)
    by_key = {p.get("key"): p for p in data.get("personas", [])}
    print(f"  model returned {len(by_key)} personas in {time.time() - t0:.0f}s")

    written, missing = 0, []
    for fig in country.roster:
        p = by_key.get(fig.key)
        if not p:
            missing.append(fig.key)
            continue
        path = os.path.join(out_dir, f"{fig.key}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_md(country, fig, p))
        written += 1
    print(f"  wrote {written} files -> {out_dir}")
    if missing:
        print(f"  MISSING (model skipped, rerun): {missing}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("country", nargs="?", choices=list(COUNTRIES), default=None)
    ap.add_argument("--model", default="glm-5.1")
    args = ap.parse_args()

    load_dotenv()
    if not os.environ.get("OLLAMA_API_KEY"):
        sys.exit("Set OLLAMA_API_KEY in .env")

    targets = [args.country] if args.country else list(COUNTRIES)
    for ck in targets:
        try:
            generate_country(ck, args.model)
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED {ck}: {e}")


if __name__ == "__main__":
    main()
