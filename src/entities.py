from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

GridPos = Tuple[int, int]

# --------- Utilities ---------
def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def manhattan(a: GridPos, b: GridPos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def in_bounds(p: GridPos, cols: int, rows: int) -> bool:
    return 0 <= p[0] < cols and 0 <= p[1] < rows

def adjacent_for_punch(a: GridPos, b: GridPos) -> bool:
    """Eligible to punch: Manhattan distance = 1 (adjacent up/down/left/right)"""
    return manhattan(a, b) == 1

# --------- Abstract base class (position) ---------
@dataclass
class Entity:
    pos: GridPos

    def move_to(self, x: int, y: int) -> None:
        self.pos = (x, y)

# --------- Human: one step per move, 4-connected ---------
@dataclass
class Human(Entity):
    def can_move(self, x: int, y: int, roo_pos: GridPos, cols: int, rows: int) -> bool:
        """Human can only move 1 tile in up/down/left/right; cannot go out of bounds; cannot occupy the same tile as the kangaroo."""
        nx, ny = x, y
        # Must move exactly 1 tile and not diagonally
        dx, dy = nx - self.pos[0], ny - self.pos[1]
        if (abs(dx) + abs(dy)) != 1:
            return False
        # Bounds
        if not in_bounds((nx, ny), cols, rows):
            return False
        # Cannot overlap with kangaroo
        if (nx, ny) == roo_pos:
            return False
        return True

# --------- Kangaroo: jumps 2 tiles each time, 4-connected; cannot pass through or land on human ---------
@dataclass
class Kangaroo(Entity):
    def can_jump(self, x: int, y: int, human_pos: GridPos, cols: int, rows: int) -> bool:
        """
        Jump rules:
        - One orthogonal jump of 2 tiles (dx=±2, dy=0 or dx=0, dy=±2)
        - Cannot go out of bounds
        - Cannot land on the human's position
        - The middle tile cannot be occupied by the human (no passing through)
        """
        nx, ny = x, y
        dx, dy = nx - self.pos[0], ny - self.pos[1]

        # Orthogonal two tiles
        is_orth_two = ((abs(dx) == 2 and dy == 0) or (abs(dy) == 2 and dx == 0))
        if not is_orth_two:
            return False

        if not in_bounds((nx, ny), cols, rows):
            return False

        # Cannot land on the player
        if (nx, ny) == human_pos:
            return False

        # Middle tile cannot be the player (prevent passing through)
        mid = (self.pos[0] + (1 if dx > 0 else (-1 if dx < 0 else 0)),
               self.pos[1] + (1 if dy > 0 else (-1 if dy < 0 else 0)))
        if mid == human_pos:
            return False

        return True

    def ai_jump_towards(self, human_pos: GridPos, block_pos: GridPos,
                        cols: int, rows: int) -> None:
        """
        Minimal AI: first approach the player along x-axis, trying a 2-tile jump each time;
        if invalid, then try the y-axis; otherwise stay still.
        block_pos passes in the player's position (same as human_pos) to unify the interface.
        """
        hx, hy = human_pos
        rx, ry = self.pos

        cand: list[GridPos] = []

        # Approach along x-direction (2 tiles)
        if hx != rx:
            step = 2 if hx > rx else -2
            cand.append((rx + step, ry))
        # Then try y-direction
        if hy != ry:
            step = 2 if hy > ry else -2
            cand.append((rx, ry + step))

        # If x/y are already aligned, pick an arbitrary 'watching' direction (non-strict)
        if not cand:
            cand = [(rx + 2, ry), (rx - 2, ry), (rx, ry + 2), (rx, ry - 2)]

        for nx, ny in cand:
            if self.can_jump(nx, ny, human_pos, cols, rows):
                self.move_to(nx, ny)
                return
        # Otherwise do nothing (rest/wait for stamina)
        return