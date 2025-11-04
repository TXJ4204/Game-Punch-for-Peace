# src/entities.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

GridPos = Tuple[int, int]

# --------- 小工具 ---------
def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def manhattan(a: GridPos, b: GridPos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def in_bounds(p: GridPos, cols: int, rows: int) -> bool:
    return 0 <= p[0] < cols and 0 <= p[1] < rows

def adjacent_for_punch(a: GridPos, b: GridPos) -> bool:
    """是否可出拳：曼哈顿距离=1（上下左右相邻）"""
    return manhattan(a, b) == 1

# --------- 抽象基类（位置）---------
@dataclass
class Entity:
    pos: GridPos

    def move_to(self, x: int, y: int) -> None:
        self.pos = (x, y)

# --------- 人类：一步一格，4 连通 ---------
@dataclass
class Human(Entity):
    def can_move(self, x: int, y: int, roo_pos: GridPos, cols: int, rows: int) -> bool:
        """人类只能上下左右移动 1 格；不可越界；不可与袋鼠同格。"""
        nx, ny = x, y
        # 只能移动 1 格且非对角
        dx, dy = nx - self.pos[0], ny - self.pos[1]
        if (abs(dx) + abs(dy)) != 1:
            return False
        # 边界
        if not in_bounds((nx, ny), cols, rows):
            return False
        # 不可重叠袋鼠
        if (nx, ny) == roo_pos:
            return False
        return True

# --------- 袋鼠：每次跳 2 格，4 连通；不可穿人/落人 ---------
@dataclass
class Kangaroo(Entity):
    def can_jump(self, x: int, y: int, human_pos: GridPos, cols: int, rows: int) -> bool:
        """
        跳跃规则：
        - 一次正交跳 2 格（dx=±2,dy=0 或 dx=0,dy=±2）
        - 不可越界
        - 不可“落在”人类位置
        - 中间格不能被人类占据（不可穿人）
        """
        nx, ny = x, y
        dx, dy = nx - self.pos[0], ny - self.pos[1]

        # 正交两格
        is_orth_two = ((abs(dx) == 2 and dy == 0) or (abs(dy) == 2 and dx == 0))
        if not is_orth_two:
            return False

        if not in_bounds((nx, ny), cols, rows):
            return False

        # 不可落在玩家身上
        if (nx, ny) == human_pos:
            return False

        # 中间格不能是玩家（防止穿越）
        mid = (self.pos[0] + (1 if dx > 0 else (-1 if dx < 0 else 0)),
               self.pos[1] + (1 if dy > 0 else (-1 if dy < 0 else 0)))
        if mid == human_pos:
            return False

        return True

    def ai_jump_towards(self, human_pos: GridPos, block_pos: GridPos,
                        cols: int, rows: int) -> None:
        """
        极简 AI：优先沿 x 方向靠近玩家，每次尝试一记 2 格跳；
        如不合法，再尝试 y 方向；否则保持不动。
        block_pos 传入玩家位置（与 human_pos 相同），用于统一接口。
        """
        hx, hy = human_pos
        rx, ry = self.pos

        cand: list[GridPos] = []

        # 朝 x 方向靠近（2 格）
        if hx != rx:
            step = 2 if hx > rx else -2
            cand.append((rx + step, ry))
        # 再试 y 方向
        if hy != ry:
            step = 2 if hy > ry else -2
            cand.append((rx, ry + step))

        # 如果 x/y 都对齐，随意找一个“观望”方向（不强求）
        if not cand:
            cand = [(rx + 2, ry), (rx - 2, ry), (rx, ry + 2), (rx, ry - 2)]

        for nx, ny in cand:
            if self.can_jump(nx, ny, human_pos, cols, rows):
                self.move_to(nx, ny)
                return
        # 否则不动（休息/等体力）
        return
