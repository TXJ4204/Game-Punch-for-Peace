import pygame as pg
from config import CFG
from typing import Tuple, Optional

# ---------- Font helper: fix garbled Chinese ----------
def get_font(size: int, bold: bool=False) -> pg.font.Font:
    """
    Try to load common CJK/Latin fonts; fall back to system default if none found.
    """
    candidates = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
        "Source Han Sans SC", "Arial Unicode MS", "Segoe UI", "Arial"
    ]
    for name in candidates:
        path = pg.font.match_font(name)
        if path:
            return pg.font.Font(path, size)
    return pg.font.SysFont(None, size, bold=bold)

# ---------- Board (centered) ----------
def _grid_origin() -> Tuple[int, int]:
    board_w = CFG.GRID_W * CFG.TILE
    board_h = CFG.GRID_H * CFG.TILE
    x0 = (CFG.WINDOW_W - board_w) // 2
    y0 = (CFG.WINDOW_H - board_h) // 2
    return x0, y0

def draw_grid(surf: pg.Surface):
    x0, y0 = _grid_origin()
    for j in range(CFG.GRID_H):
        for i in range(CFG.GRID_W):
            r = pg.Rect(x0 + i*CFG.TILE, y0 + j*CFG.TILE, CFG.TILE, CFG.TILE)
            color = CFG.GRID_LIGHT if (i+j) % 2 == 0 else CFG.GRID_DARK
            pg.draw.rect(surf, color, r)

def draw_piece(surf: pg.Surface, grid_xy: Tuple[int,int], color: Tuple[int,int,int]):
    x0, y0 = _grid_origin()
    gx, gy = grid_xy
    r = pg.Rect(x0 + gx*CFG.TILE + 8, y0 + gy*CFG.TILE + 8, CFG.TILE-16, CFG.TILE-16)
    pg.draw.rect(surf, color, r, border_radius=12)

def draw_text(surf, font: pg.font.Font, text: str, xy, color=CFG.TEXT, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = xy
        surf.blit(img, rect)
    else:
        surf.blit(img, img.get_rect(topleft=xy))

def draw_stamina_bar(surf: pg.Surface, label: str, cur: int, maxv: int, hearts: int, topleft: Tuple[int,int]):
    x, y = topleft
    W, H = 260, 18
    pg.draw.rect(surf, CFG.UI_BACK, (x, y, W, H), border_radius=4)
    w = int(W * (cur/max(1,maxv)))
    pg.draw.rect(surf, CFG.UI, (x, y, w, H), border_radius=4)
    lab_font = get_font(20)
    draw_text(surf, lab_font, f"{label}: {cur}/{maxv}  ♥{max(0,hearts)}", (x+6, y-2))

# ---------- Simple button ----------
class Button:
    def __init__(self, rect: pg.Rect, label: str, font: pg.font.Font, enabled: bool=True):
        self.rect = rect
        self.label = label
        self.font = font
        self.enabled = enabled
        self.hover = False

    def handle_event(self, e) -> bool:
        if not self.enabled:
            return False
        if e.type == pg.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                return True
        return False

    def draw(self, surf: pg.Surface):
        bg = (80, 180, 250) if (self.enabled and self.hover) else (70, 120, 170)
        if not self.enabled:
            bg = (90, 90, 100)
        pg.draw.rect(surf, bg, self.rect, border_radius=12)
        pg.draw.rect(surf, (20, 20, 24), self.rect, width=2, border_radius=12)
        txt = self.font.render(self.label, True, (250, 250, 255) if self.enabled else (210,210,210))
        surf.blit(txt, txt.get_rect(center=self.rect.center))
