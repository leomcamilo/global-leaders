"""Persona loader — the canonical, human-readable identity of each figure.

Each figure has an authored Markdown file at
    engine/prompts/countries/<country>/<figure_key>.md
with deterministic frontmatter (mechanical facts: utility vector, themes, influence)
and a prose body written by the Cast Designer / glm-5.1 (who they are, what they truly
want, red lines, how they speak, how candid they are at a private lunch).

This file is the BASE truth a human can read and edit. The per-game variation
(utility_shift, hidden_agenda) still layers on top at runtime in state.cast — and any
RARE interest shift during a playthrough is recorded there (session memory), never by
rewriting this shared file. The loader is tolerant: missing files return None so the
engine keeps working without personas.
"""

from __future__ import annotations

import functools
import os

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "countries")


def persona_path(country_key: str, figure_key: str) -> str:
    return os.path.join(PROMPTS_DIR, country_key, f"{figure_key}.md")


@functools.lru_cache(maxsize=256)
def _read(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _strip_frontmatter(text: str) -> str:
    """Drop a leading '---' ... '---' YAML block, returning the prose body."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def persona_doc(country_key: str, figure_key: str) -> str | None:
    """Full file (frontmatter + prose) — for humans / debugging."""
    return _read(persona_path(country_key, figure_key))


def load_persona(country_key: str, figure_key: str) -> str | None:
    """Prose body only (frontmatter stripped) — what the SLM reads in the lunch prompt."""
    text = _read(persona_path(country_key, figure_key))
    return _strip_frontmatter(text).strip() if text else None


def has_personas(country_key: str) -> bool:
    d = os.path.join(PROMPTS_DIR, country_key)
    return os.path.isdir(d) and any(f.endswith(".md") for f in os.listdir(d))
