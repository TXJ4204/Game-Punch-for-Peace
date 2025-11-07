# src/sprites.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
import pygame as pg
import json, os

from src.config import CFG

# -----------------------------------------------------------------------------
# Paths & defaults
# -----------------------------------------------------------------------------
# Resource directory: unified to assets/animation
_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "animation"

# Default hitbox mode
_HITBOX_MODE_DEFAULT = "parts"  # "bbox" | "parts" | "mask"
# Default hitbox JSON path
_HITBOX_JSON_DEFAULT = str(_ASSET_DIR / "hitbox_meta.json")


def _hitbox_mode() -> str:
    """Active hitbox mode from CFG or default."""
    return getattr(CFG, "HITBOX_MODE", _HITBOX_MODE_DEFAULT).lower()


def _hitbox_json_path() -> str:
    """Hitbox json path from CFG or default."""
    return getattr(CFG, "HITBOX_JSON", _HITBOX_JSON_DEFAULT)


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
_HIT_META: dict | None = None


def load_hit_meta() -> dict:
    """Load (and cache) hitbox metadata JSON."""
    global _HIT_META
    if _HIT_META is None:
        _HIT_META = {}
        p = _hitbox_json_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    _HIT_META = json.load(f)
            except Exception:
                _HIT_META = {}
    return _HIT_META


def get_hit_shape(img_name: str, surf: pg.Surface) -> dict:
    """
    Return active hit shape under the mode:
      - {"type":"rects","rects":[(x,y,w,h), ...]}    (image space)
      - {"type":"poly", "pts":[(x,y), ...]}          (image space)
    Fallbacks exist when items are missing.
    """
    meta = load_hit_meta().get(img_name, None)
    if not meta:
        # fallback: full image bbox
        w, h = surf.get_size()
        return {"type": "rects", "rects": [(0, 0, w, h)]}

    mode = _hitbox_mode()

    # Pixel/contour polygon (the editor stores it as maskPoly)
    if mode == "mask" and meta.get("maskPoly"):
        return {"type": "poly", "pts": [tuple(p) for p in meta["maskPoly"]]}

    # Single tight bbox
    if mode == "bbox" and meta.get("bbox"):
        x, y, w, h = meta["bbox"]
        return {"type": "rects", "rects": [(x, y, w, h)]}

    # Default -> multiple small parts
    if meta.get("parts"):
        rects = []
        for r in meta["parts"]:
            rects.append((r["x"], r["y"], r["w"], r["h"]))
        return {"type": "rects", "rects": rects}

    # Last fallback: full image
    w, h = surf.get_size()
    return {"type": "rects", "rects": [(0, 0, w, h)]}


# -----------------------------------------------------------------------------
# SimpleSprite: frames with names & original sizes; draw/hit helpers
# -----------------------------------------------------------------------------
# Frame tuple: (scaled_surface, filename, (orig_w, orig_h))
FrameType = Tuple[pg.Surface, str, Tuple[int, int]]


class SimpleSprite:
    def __init__(self, frames_map: Dict[str, List[FrameType]], fps: float = 6):
        """
        frames_map: { state: [ (scaled_surface, 'file.png', (orig_w, orig_h)), ... ] }
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

    def current_frame(self) -> pg.Surface | None:
        """Return the current image surface of this state."""
        frames = self._frames.get(self.state)
        if not frames:
            return None
        return frames[self._idx]


    # --- current frame info ---
    def _cur(self) -> FrameType:
        frames = self._frames.get(self.state)
        if not frames:
            raise RuntimeError(f"No frames for state '{self.state}'")
        return frames[self._idx]

    def current_surface(self) -> pg.Surface:
        return self._cur()[0]

    def current_image_name(self) -> str:
        return self._cur()[1]

    def current_orig_size(self) -> Tuple[int, int]:
        return self._cur()[2]

    # --- draw ---
    def get_draw_rect(self, center_xy: Tuple[int, int], flip_h: bool = False) -> pg.Rect:
        img = self.current_surface()
        if flip_h:
            img = pg.transform.flip(img, True, False)
        return img.get_rect(center=center_xy)

    def draw(self, surface: pg.Surface, center_xy: Tuple[int, int], flip_h: bool = False):
        img = self.current_surface()
        if flip_h:
            img = pg.transform.flip(img, True, False)
        rect = img.get_rect(center=center_xy)
        self._last_draw_rect = rect
        surface.blit(img, rect)

    # --- precise mask (current frame) ---
    def mask_and_rect(self, center_xy: Tuple[int, int], flip_h: bool = False) -> tuple[pg.mask.Mask, pg.Rect]:
        """
        Return (mask, draw_rect) of current frame at given screen center,
        respecting horizontal flip.
        """
        surf = self.current_surface()
        if flip_h:
            surf = pg.transform.flip(surf, True, False)
        rect = surf.get_rect(center=center_xy)
        m = pg.mask.from_surface(surf)
        return m, rect

    # --- fist anchor (screen space) ---
    def fist_point(self, center_xy: Tuple[int, int], flip_h: bool = False) -> Tuple[int, int]:
        """
        Compute fist anchor (screen space) from JSON meta:
          - For "unflipped" image coordinates: people use punchR, roo uses punchL
          - When flip_h=True, apply mirroring conversion
        If not provided, fall back to current frame center.
        """
        name = self.current_image_name()
        meta = load_hit_meta().get(name, {})

        # Convention: when the human faces right, the punch point is on the right; when the roo faces left, the punch point is on the left
        # Use punchR by default when not flipped; use mirrored (or punchL) when flipped
        # To avoid missing data, try punchR first, otherwise punchL
        pt = meta.get("punchR", None)
        if pt is None:
            pt = meta.get("punchL", None)

        surf = self.current_surface()
        sw, sh = surf.get_size()

        if pt is None:
            # No anchor → use draw center
            draw_rect = self.get_draw_rect(center_xy, flip_h=flip_h)
            return draw_rect.center

        # Scaling from original image to current image (based on recorded original size)
        ow, oh = self.current_orig_size()
        sx = sw / max(1, ow)
        sy = sh / max(1, oh)
        px, py = pt[0] * sx, pt[1] * sy

        # If horizontally flipped → mirror X
        if flip_h:
            px = sw - px

        draw_rect = self.get_draw_rect(center_xy, flip_h=flip_h)
        return (int(draw_rect.left + px), int(draw_rect.top + py))

    # --- hit rectangles in SCREEN space ---
    def hit_rects(self, center_xy: Tuple[int, int], flip_h: bool = False) -> List[pg.Rect]:
        """
        Map image-space hit shapes to screen-space rectangles using
        current frame draw rect. (poly mode currently degrades to its bounding box)
        """
        img = self.current_surface()
        name = self.current_image_name()
        # Note: flip has minimal effect on parts/bbox (can be ignored if left-right symmetric)
        draw_rect = self.get_draw_rect(center_xy, flip_h=flip_h)
        left, top = draw_rect.x, draw_rect.y

        shape = get_hit_shape(name, img)
        rects: List[pg.Rect] = []

        if shape["type"] == "rects":
            for (x, y, w, h) in shape["rects"]:
                if flip_h:
                    x = img.get_width() - x - w
                rects.append(pg.Rect(int(left + x), int(top + y), int(w), int(h)))
        elif shape["type"] == "poly":
            pts = shape["pts"]
            if pts:
                # If flipped: mirror polygon points
                if flip_h:
                    sw = img.get_width()
                    pts = [(sw - px, py) for (px, py) in pts]
                minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
                miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
                rects.append(pg.Rect(int(left + minx), int(top + miny), int(maxx - minx), int(maxy - miny)))
        return rects

    def bbox_rect(self, center_xy: tuple[int, int], flip_h: bool = False) -> pg.Rect:
        """
        Return the current frame’s “yellow tight bounding box” in screen coordinates (a single Rect).
        If JSON has no bbox, fall back to the full image bounding box.
        """
        img = self.current_surface()
        name = self.current_image_name()
        draw_rect = self.get_draw_rect(center_xy, flip_h=flip_h)
        left, top = draw_rect.x, draw_rect.y

        meta = load_hit_meta().get(name, {})
        # Prefer bbox from JSON
        if meta.get("bbox"):
            x, y, w, h = meta["bbox"]
            if flip_h:
                x = img.get_width() - x - w
            return pg.Rect(int(left + x), int(top + y), int(w), int(h))

        # Fallback: full image
        return draw_rect.copy()



# -----------------------------------------------------------------------------
# Sprite factories
# -----------------------------------------------------------------------------
def _make_frame_tuple(img: pg.Surface, name: str, cell_w: int, cell_h: int, ratio: float) -> FrameType:
    """Helper to build (scaled_surface, filename, (orig_w,orig_h))."""
    ow, oh = img.get_size()
    scaled = _fit_to_cell(img, cell_w, cell_h, ratio)
    return (scaled, name, (ow, oh))


def make_people_sprite(cell_w: int, cell_h: int, fps_idle: float = 3) -> SimpleSprite:
    # people01, people02 idle; people03 block
    p1_name, p2_name, pb_name = "people01.png", "people02.png", "people03.png"

    p1 = _make_frame_tuple(_load(p1_name), p1_name, cell_w, cell_h, 1.30)
    p2 = _make_frame_tuple(_load(p2_name), p2_name, cell_w, cell_h, 1.30)
    pb = _make_frame_tuple(_load(pb_name), pb_name, cell_w, cell_h, 1.30)

    frames: Dict[str, List[FrameType]] = {
        "idle":  [p1, p2],
        "block": [pb],
    }
    return SimpleSprite(frames, fps=fps_idle)


def make_roo_sprite(cell_w: int, cell_h: int, fps_idle: float = 4) -> SimpleSprite:
    # roo01 idle, roo02 jump, roo04 punch (roo03 can be added later)
    r1_name, r2_name, r4_name = "roo01.png", "roo02.png", "roo04.png"

    r1 = _make_frame_tuple(_load(r1_name), r1_name, cell_w, cell_h, 1.30)
    r2 = _make_frame_tuple(_load(r2_name), r2_name, cell_w, cell_h, 1.30)
    r4 = _make_frame_tuple(_load(r4_name), r4_name, cell_w, cell_h, 1.30)

    frames: Dict[str, List[FrameType]] = {
        "idle":  [r1],
        "jump":  [r2],
        "punch": [r4],
    }
    return SimpleSprite(frames, fps=fps_idle)
