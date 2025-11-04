# src/sprites.py
from __future__ import annotations
from pathlib import Path
import pygame as pg
import json, os
from typing import Dict, List, Tuple, Union
from src.config import CFG

HITBOX_JSON: str = "assets/animation/hitbox_meta.json"

# -----------------------------------------------------------------------------
# Image loading & scale helpers
# -----------------------------------------------------------------------------
def _load(name: str) -> pg.Surface:
    path = _ASSET_DIR / name
    img = pg.image.load(str(path)).convert_alpha()
    return img

def _fit_to_cell(img: pg.Surface, cell_w: int, cell_h: int, ratio: float = 1.30) -> pg.Surface:
    """Scale an image to fit a grid cell with a multiplier ratio."""
    w, h = img.get_size()
    maxw, maxh = int(cell_w * ratio), int(cell_h * ratio)
    s = min(maxw / max(w, 1), maxh / max(h, 1))
    new_size = (max(1, int(w * s)), max(1, int(h * s)))
    return pg.transform.smoothscale(img, new_size)

# -----------------------------------------------------------------------------
# Hitbox meta loader
# -----------------------------------------------------------------------------
_HIT_META = None

def _hitbox_mode() -> str:
    return getattr(CFG, "HITBOX_MODE", _HITBOX_MODE_DEFAULT).lower()

def _hitbox_json_path() -> str:
    return getattr(CFG, "HITBOX_JSON", _HITBOX_JSON_DEFAULT)

def load_hit_meta() -> dict:
    global _HIT_META
    if _HIT_META is None:
        p = _hitbox_json_path()
        _HIT_META = {}
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    _HIT_META = json.load(f)
            except Exception:
                _HIT_META = {}
    return _HIT_META

def get_hit_shape(img_name: str, surf: pg.Surface) -> dict:
    """
    Return active hit shape under mode:
      - {"type":"rects","rects":[(x,y,w,h), ...]}    (image space)
      - {"type":"poly", "pts":[(x,y), ...]}          (image space)
    """
    meta = load_hit_meta().get(img_name, None)
    if not meta:
        w, h = surf.get_size()
        return {"type": "rects", "rects": [(0, 0, w, h)]}

    mode = _hitbox_mode()
    if mode == "mask" and meta.get("maskPoly"):
        return {"type": "poly", "pts": [tuple(p) for p in meta["maskPoly"]]}

    if mode == "bbox" and meta.get("bbox"):
        x, y, w, h = meta["bbox"]
        return {"type": "rects", "rects": [(x, y, w, h)]}

    # default -> parts
    rects = []
    if meta.get("parts"):
        for r in meta["parts"]:
            rects.append((r["x"], r["y"], r["w"], r["h"]))
        return {"type": "rects", "rects": rects}

    # last fallback
    w, h = surf.get_size()
    return {"type": "rects", "rects": [(0, 0, w, h)]}

# -----------------------------------------------------------------------------
# SimpleSprite: stores frames with names, provides draw & hit-rect helpers
# -----------------------------------------------------------------------------
FrameType = Tuple[pg.Surface, str]  # (surface, image_name)

class SimpleSprite:
    def __init__(self, frames_map: Dict[str, List[FrameType]], fps: float = 6):
        """
        frames_map: { state: [ (Surface, 'file.png'), ... ] }
        """
        self._frames: Dict[str, List[FrameType]] = frames_map
        self.state = "idle"
        self._idx = 0
        self._acc = 0.0
        self.fps = fps
        self._last_draw_rect: pg.Rect | None = None

    # --- state & animation ---
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

    # --- current frame info ---
    def current_surface(self) -> pg.Surface:
        frames = self._frames.get(self.state)
        if not frames:
            raise RuntimeError(f"No frames for state '{self.state}'")
        return frames[self._idx][0]

    def current_image_name(self) -> str:
        frames = self._frames.get(self.state)
        if not frames:
            raise RuntimeError(f"No frames for state '{self.state}'")
        return frames[self._idx][1]

    def get_draw_rect(self, center_xy: Tuple[int, int]) -> pg.Rect:
        img = self.current_surface()
        return img.get_rect(center=center_xy)

    # --- drawing ---
    def draw(self, surface: pg.Surface, center_xy: Tuple[int, int], flip_h: bool = False):
        frames = self._frames.get(self.state)
        if not frames:
            return
        img = frames[self._idx][0]
        if flip_h:
            img = pg.transform.flip(img, True, False)
        rect = img.get_rect(center=center_xy)
        self._last_draw_rect = rect
        surface.blit(img, rect)

    # --- hit rectangles in SCREEN space ---
    def hit_rects(self, center_xy: Tuple[int, int]) -> List[pg.Rect]:
        """
        Convert image-space hit shapes to screen-space rectangles based
        on the draw rect for current frame.
        """
        img = self.current_surface()
        name = self.current_image_name()
        draw_rect = img.get_rect(center=center_xy)
        left, top = draw_rect.x, draw_rect.y

        shape = get_hit_shape(name, img)
        rects: List[pg.Rect] = []

        if shape["type"] == "rects":
            for (x, y, w, h) in shape["rects"]:
                rects.append(pg.Rect(int(left + x), int(top + y), int(w), int(h)))
        elif shape["type"] == "poly":
            # fallback as bounding rect; later can implement precise mask collide if needed
            pts = [(int(left + px), int(top + py)) for (px, py) in shape["pts"]]
            if pts:
                minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
                miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
                rects.append(pg.Rect(minx, miny, maxx - minx, maxy - miny))
        return rects

# -----------------------------------------------------------------------------
# Sprite factories
# -----------------------------------------------------------------------------
def make_people_sprite(cell_w: int, cell_h: int, fps_idle: float = 3) -> SimpleSprite:
    # keep names for hitbox lookup
    p1_name, p2_name, pb_name = "people01.png", "people02.png", "people03.png"
    idle1 = _fit_to_cell(_load(p1_name), cell_w, cell_h, 1.30)
    idle2 = _fit_to_cell(_load(p2_name), cell_w, cell_h, 1.30)
    block = _fit_to_cell(_load(pb_name), cell_w, cell_h, 1.30)
    frames: Dict[str, List[FrameType]] = {
        "idle":  [(idle1, p1_name), (idle2, p2_name)],
        "block": [(block, pb_name)],
    }
    return SimpleSprite(frames, fps=fps_idle)

def make_roo_sprite(cell_w: int, cell_h: int, fps_idle: float = 4) -> SimpleSprite:
    # roo01 idle, roo02 jump, roo04 punch  (roo03 作为备用帧可后续加入)
    r1_name, r2_name, r4_name = "roo01.png", "roo02.png", "roo04.png"
    idle  = _fit_to_cell(_load(r1_name), cell_w, cell_h, 1.30)
    jump  = _fit_to_cell(_load(r2_name), cell_w, cell_h, 1.30)
    punch = _fit_to_cell(_load(r4_name), cell_w, cell_h, 1.30)
    frames: Dict[str, List[FrameType]] = {
        "idle":  [(idle,  r1_name)],
        "jump":  [(jump,  r2_name)],
        "punch": [(punch, r4_name)],
    }
    return SimpleSprite(frames, fps=fps_idle)
