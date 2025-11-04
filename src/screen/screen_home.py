# screen_home.py
import pygame as pg
from src.config import CFG
from src.widgets import Button

class HomeScreen:
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size
        self.title = "Kangaroo vs Human"
        self.btn_start = Button(pg.Rect(self.W//2 - 160, self.H//2 + 80, 320, 64),
                                "Start", self.m.fonts["big"])

    def _draw_full_grid(self):
        COLS, ROWS = 16, 9
        CELL_W = self.W // COLS
        CELL_H = self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                rect = pg.Rect(c*CELL_W, r*CELL_H, CELL_W, CELL_H)
                col = CFG.GRID_LIGHT if (c+r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(self.m.screen, col, rect)

    def handle_event(self, e):
        if self.btn_start.handle_event(e):
            self.m.goto("mode")

    def update(self, dt): pass

    def draw(self):
        s = self.m.screen
        s.fill(CFG.BG)
        self._draw_full_grid()
        # Title
        img = self.m.fonts["title"].render(self.title, True, CFG.TEXT)
        s.blit(img, img.get_rect(center=(self.W//2, 72)))
        # Button
        self.btn_start.draw(s)
        # # Bottom hint
        # tip = self.m.fonts["sml"].render("Esc to quit", True, CFG.TEXT)
        # s.blit(tip, (16, self.H-28))
