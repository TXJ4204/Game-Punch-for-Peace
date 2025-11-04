# src/sprites.py
from __future__ import annotations
from pathlib import Path
import pygame as pg

_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "images"

def _load(name: str) -> pg.Surface:
    path = _ASSET_DIR / name
    img = pg.image.load(str(path)).convert_alpha()
    return img

def _fit_to_cell(img: pg.Surface, cell_w: int, cell_h: int, ratio: float = 1.30) -> pg.Surface:
    w, h = img.get_size()
    maxw, maxh = int(cell_w * ratio), int(cell_h * ratio)
    s = min(maxw / max(w, 1), maxh / max(h, 1))
    new_size = (max(1, int(w * s)), max(1, int(h * s)))
    return pg.transform.smoothscale(img, new_size)

class SimpleSprite:
    def __init__(self, frames_map: dict[str, list[pg.Surface]], fps: float = 6):
        self._frames = frames_map
        self.state = "idle"
        self._idx = 0
        self._acc = 0.0
        self.fps = fps

    def set_state(self, state: str):
        if state != self.state:
            self.state = state
            self._idx = 0
            self._acc = 0.0

    def update(self, dt_ms: float):
        frames = self._frames.get(self.state, [])
        if len(frames) <= 1:
            return
        self._acc += dt_ms
        frame_ms = 1000.0 / max(self.fps, 1e-6)
        while self._acc >= frame_ms:
            self._acc -= frame_ms
            self._idx = (self._idx + 1) % len(frames)

    def draw(self, surface: pg.Surface, center_xy: tuple[int, int], flip_h: bool = False):
        frames = self._frames.get(self.state)
        if not frames:
            return
        img = frames[self._idx]
        if flip_h:
            img = pg.transform.flip(img, True, False)
        rect = img.get_rect(center=center_xy)
        surface.blit(img, rect)

def make_people_sprite(cell_w: int, cell_h: int, fps_idle: float = 3) -> SimpleSprite:
    idle1 = _fit_to_cell(_load("people01.png"), cell_w, cell_h, 1.30)
    idle2 = _fit_to_cell(_load("people02.png"), cell_w, cell_h, 1.30)
    block = _fit_to_cell(_load("people03.png"), cell_w, cell_h, 1.30)
    frames = {"idle": [idle1, idle2], "block": [block]}
    return SimpleSprite(frames, fps=fps_idle)

def make_roo_sprite(cell_w: int, cell_h: int, fps_idle: float = 4) -> SimpleSprite:
    idle  = _fit_to_cell(_load("roo01.png"), cell_w, cell_h, 1.30)
    jump  = _fit_to_cell(_load("roo02.png"), cell_w, cell_h, 1.30)
    punch = _fit_to_cell(_load("roo04.png"), cell_w, cell_h, 1.30)
    frames = {"idle": [idle], "jump": [jump], "punch": [punch]}
    return SimpleSprite(frames, fps=fps_idle)
