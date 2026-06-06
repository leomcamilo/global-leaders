"""Global Leaders — headless game engine.

Deterministic core: the World State is the source of truth; the SLM only proposes
(narration, options, judgement). Everything here is stdlib-only and testable without
a model via the FakeLLM stub in `engine.llm`.

See GAME_DESIGN.md and GAME_RULES.md at the repo root for the design.
"""

from engine.state import INDICATORS, FACTION_KEYS, WorldState
from engine.game import Game

__all__ = ["INDICATORS", "FACTION_KEYS", "WorldState", "Game"]
