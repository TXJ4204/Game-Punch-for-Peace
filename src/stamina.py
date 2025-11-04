# src/stamina.py
from __future__ import annotations

class StaminaBar:
    """
    通用条：可当体力/生命使用。
    - max: 最大值（int）
    - cur: 当前值（float，允许小数累加/扣减）
    """
    def __init__(self, max_value: int):
        self.max = int(max_value)
        self.cur = float(max_value)

    def reset(self):
        self.cur = float(self.max)

    def lose(self, amount: float):
        self.cur = max(0.0, self.cur - float(amount))

    def gain(self, amount: float):
        self.cur = min(float(self.max), self.cur + float(amount))

    def is_depleted(self) -> bool:
        return self.cur <= 0.0

    @property
    def pct(self) -> float:
        return 0.0 if self.max <= 0 else self.cur / float(self.max)
