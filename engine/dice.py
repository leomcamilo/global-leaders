"""Uncertainty dice (GAME_RULES.md §2.1).

Δ_final = round(Δ * roll), roll ~ clamp(Normal(1.0, 0.25), 0.4, 1.6).
Tail events per decision: backfire 7% (invert sign, 0.5x), windfall 7% (1.5x).

Seeded per (seed, turn, decision_index) so a whole playthrough is reproducible —
same seed => same rolls (replay fairness, GAME_RULES.md §8).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

P_BACKFIRE = 0.07
P_WINDFALL = 0.07


@dataclass
class Roll:
    factor: float
    mode: str  # "normal" | "backfire" | "windfall"

    def apply(self, delta: float) -> float:
        if self.mode == "backfire":
            return -delta * self.factor * 0.5
        if self.mode == "windfall":
            return delta * self.factor * 1.5
        return delta * self.factor


class Dice:
    def __init__(self, seed: int):
        self.seed = seed

    def _rng(self, turn: int, idx: int) -> random.Random:
        # Stable, order-independent mix of (seed, turn, idx).
        return random.Random((self.seed * 1_000_003) ^ (turn * 9176) ^ (idx * 31 + 7))

    def roll(self, turn: int, idx: int = 0) -> Roll:
        r = self._rng(turn, idx)
        factor = max(0.4, min(1.6, r.gauss(1.0, 0.25)))
        u = r.random()
        if u < P_BACKFIRE:
            return Roll(factor, "backfire")
        if u < P_BACKFIRE + P_WINDFALL:
            return Roll(factor, "windfall")
        return Roll(factor, "normal")
