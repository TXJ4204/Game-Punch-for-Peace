# src/screen/screen_mode.py
import pygame as pg
from src.config import CFG
from src.widgets import Button

def draw_panel(surf, rect, fill=(55,60,70), outline=(25,28,34)):
    pg.draw.rect(surf, fill, rect, border_radius=14)
    pg.draw.rect(surf, outline, rect, 2, border_radius=14)

def human_icon(surf, rect, color=(80,160,240)):
    cx, cy = rect.centerx, rect.centery
    bw, bh = rect.width*0.22, rect.height*0.45
    body = pg.Rect(0,0,bw,bh); body.center = (cx, cy+rect.height*0.06)
    head_r = int(bw*0.55)
    pg.draw.rect(surf, color, body, border_radius=10)
    pg.draw.circle(surf, color, (int(cx), int(body.top - head_r*0.6)), head_r)

def two_humans_icon(surf, rect, color=(150,150,160)):
    w = rect.width*0.18; h = rect.height*0.38; gap = rect.width*0.05
    x0 = rect.centerx - w - gap/2; x1 = rect.centerx + gap/2
    yb = rect.centery + rect.height*0.08
    for x in (x0, x1):
        body = pg.Rect(x, yb - h, w, h)
        pg.draw.rect(surf, color, body, border_radius=10)
        pg.draw.circle(surf, color, (int(x+w/2), int(body.top - w*0.55)), int(w*0.55))

class ModeScreen:
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size
        # Layout
        gap = 48
        col_w = (self.W - gap*3)//2
        col_h = self.H - 220
        self.left  = pg.Rect(gap, 140, col_w, col_h)
        self.right = pg.Rect(gap*2 + col_w, 140, col_w, col_h)

        self.btn_single = Button(
            pg.Rect(self.left.centerx-120, self.left.bottom-72, 240, 48),
            "Single Player", self.m.fonts["mid"], enabled=True
        )
        self.btn_multi  = Button(
            pg.Rect(self.right.centerx-120, self.right.bottom-72, 240, 48),
            "Multiplayer", self.m.fonts["mid"], enabled=False
        )
        # New: clickable Back button (bottom-left)
        self.btn_back = Button(
            pg.Rect(20, self.H - 64, 140, 40),
            "Back", self.m.fonts["mid"], enabled=True
        )

    def _draw_full_grid(self):
        COLS, ROWS = 16, 9
        CELL_W = self.W // COLS; CELL_H = self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                rect = pg.Rect(c*CELL_W, r*CELL_H, CELL_W, CELL_H)
                col = CFG.GRID_LIGHT if (c+r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(self.m.screen, col, rect)

    def handle_event(self, e):
        if self.btn_single.handle_event(e):
            self.m.goto("single_info")
            return
        self.btn_multi.handle_event(e)

        # Click Back button
        if self.btn_back.handle_event(e):
            self.m.goto("home")
            return

        # Backspace also returns
        if e.type == pg.KEYDOWN and e.key == pg.K_BACKSPACE:
            self.m.goto("home")

    def update(self, dt):
        pass

    def draw(self):
        s = self.m.screen
        s.fill(CFG.BG); self._draw_full_grid()

        title = self.m.fonts["title"].render("Choose Mode", True, CFG.TEXT)
        s.blit(title, title.get_rect(center=(self.W//2, 72)))

        # Two cards
        for rect in (self.left, self.right):
            draw_panel(s, rect)

        # Left: Single
        human_icon(s, self.left.inflate(-self.left.width*0.3, -self.left.height*0.3))
        img = self.m.fonts["big"].render("Single Player", True, CFG.TEXT)
        s.blit(img, img.get_rect(center=(self.left.centerx, self.left.top+28)))

        # Right: Multi (placeholder)
        two_humans_icon(s, self.right.inflate(-self.right.width*0.3, -self.right.height*0.3))
        img = self.m.fonts["big"].render("Multiplayer", True, CFG.TEXT)
        s.blit(img, img.get_rect(center=(self.right.centerx, self.right.top+28)))
        tip = self.m.fonts["mid"].render("Coming soon", True, CFG.TEXT)
        s.blit(tip, tip.get_rect(center=(self.right.centerx, self.right.top+64)))

        # Buttons
        self.btn_single.draw(s)
        self.btn_multi.draw(s)
        self.btn_back.draw(s)
