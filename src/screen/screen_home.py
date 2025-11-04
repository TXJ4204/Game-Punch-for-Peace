# screen_home.py
import pygame as pg
from src.config import CFG
from src.widgets import Button

class HomeScreen:
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # ---- Text ----
        self.title    = "PUNCH for PEACE"
        self.subtitle = "- human VS kangaroo -"

        # ---- Font: larger title + bold ----
        self.title_font = self.m.fonts.get("title", self.m.fonts["big"])
        try:
            self.title_font.set_bold(True)   # some fonts support this
        except Exception:
            pass

        # Enlarge title a bit more (when no separate large font is available)
        self.title_font_big = self.title_font
        try:
            # Try to generate a larger title font using system font
            size = int(self.title_font.get_height() * 2)
            self.title_font_big = pg.font.SysFont(None, size, bold=True)
        except Exception:
            pass

        self.sub_font = self.m.fonts.get("subtitle", self.m.fonts.get("big"))
        self.sub_col  = (170, 170, 170)

        # ---- Button: smaller, thinner border ----
        self.btn_size = (220, 60)   # previously 360x84, now smaller
        btn_rect = pg.Rect(0, 0, *self.btn_size)
        self.btn_start = Button(btn_rect, "start", self.m.fonts["big"])
        # If Button supports custom border/radius, make it thinner
        for attr, val in [("border_w", 0), ("radius", 14)]:
            if hasattr(self.btn_start, attr):
                setattr(self.btn_start, attr, val)

        # ---- Calculate vertical layout a (centered) ----
        self._layout_a()

    def _layout_a(self):
        # Measure heights of three blocks
        title_h = self.title_font_big.size(self.title)[1]
        sub_h   = self.sub_font.size(self.subtitle)[1]
        btn_h   = self.btn_start.rect.height

        gap1, gap2 = 18, 120  # spacing between title-subtitle and subtitle-button
        total_h = title_h + gap1 + sub_h + gap2 + btn_h

        start_y = (self.H - total_h) // 2 + 40  # “layout a” top y (vertically centered) + offset
        cx = self.W // 2 + 0                   # center alignment

        # Position each element
        self.title_pos = (cx, start_y + title_h // 2)
        self.sub_pos   = (cx, self.title_pos[1] + title_h // 2 + gap1 + sub_h // 2)

        self.btn_start.rect.centerx = cx
        self.btn_start.rect.centery = self.sub_pos[1] + sub_h // 2 + gap2 + btn_h // 2

    def _draw_full_grid(self):
        COLS, ROWS = 16, 9
        CELL_W = self.W // COLS
        CELL_H = self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                rect = pg.Rect(c * CELL_W, r * CELL_H, CELL_W, CELL_H)
                col = CFG.GRID_LIGHT if (c + r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(self.m.screen, col, rect)

    def handle_event(self, e):
        if self.btn_start.handle_event(e):
            self.m.goto("mode")

    def update(self, dt):
        # Recalculate layout when window size changes (if you have adaptive window)
        pass

    def draw(self):
        s = self.m.screen
        s.fill(CFG.BG)
        self._draw_full_grid()

        # Title
        img_title = self.title_font_big.render(self.title, True, CFG.TEXT)
        s.blit(img_title, img_title.get_rect(center=self.title_pos))

        # Subtitle
        img_sub = self.sub_font.render(self.subtitle, True, self.sub_col)
        s.blit(img_sub, img_sub.get_rect(center=self.sub_pos))

        # Button
        self.btn_start.draw(s)
