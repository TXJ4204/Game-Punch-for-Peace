# src/ui/board.py
import pygame as pg
from src.config import CFG

HUD_H = 96

def compute_play_rect(W, H, hud_h=HUD_H, margin=8):
    return pg.Rect(margin, hud_h + margin, W - margin * 2, H - hud_h - margin * 2)

def draw_board(surf, rect):
    cols, rows = CFG.GRID_W, CFG.GRID_H
    cw = rect.width // cols
    ch = rect.height // rows
    for y in range(rows):
        for x in range(cols):
            r = pg.Rect(rect.x + x * cw, rect.y + y * ch, cw, ch)
            col = CFG.COL_GRID_LIGHT if (x + y) % 2 == 0 else CFG.COL_GRID_DARK
            pg.draw.rect(surf, col, r)
    # 外框
    pg.draw.rect(surf, (0, 0, 0), rect, 2, border_radius=8)

def grid_center(play_rect, gx, gy):
    cw = play_rect.width // CFG.GRID_W
    ch = play_rect.height // CFG.GRID_H
    cx = play_rect.left + gx * cw + cw // 2
    cy = play_rect.top + gy * ch + ch // 2
    return (cx, cy)
