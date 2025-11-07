# src/screen/screen_result.py
import pygame as pg
from src.config import CFG


WHITE = (250, 250, 250)
GRID_LINE = (250, 250, 250)


def draw_bold_text(surface: pg.Surface, font: pg.font.Font, text: str, color, center):
    """Fake bold by drawing the same text twice with 1px offset."""
    img1 = font.render(text, True, color)
    img2 = font.render(text, True, color)
    r1 = img1.get_rect(center=center)
    r2 = img2.get_rect(center=(center[0] + 1, center[1]))
    surface.blit(img1, r1)
    surface.blit(img2, r2)


class RoundResultScreen:
    def __init__(
        self,
        manager,
        kind: str,                    # 'win' | 'lose' | 'tie'
        round_idx: int,               # 1..3
        round_results,                # ['human'|'roo'|'tie'|None] * 3
        on_continue,                  # callback on Continue / Esc
        is_match_over: bool = False,  # True if final round finished
    ):
        self.m = manager
        self.W, self.H = manager.size

        self.kind = kind
        self.round_idx = round_idx
        self.round_results = list(round_results) if round_results else [None, None, None]
        self.on_continue = on_continue
        self.is_match_over = is_match_over

        # Fonts from manager (keep style consistent)
        self.font_title = self.m.fonts["title"]   # big (T1)
        self.font_mid   = self.m.fonts["mid"]     # medium (T2 / buttons)
        self.font_sml   = self.m.fonts["sml"]     # small  (cells)

        # Colored semi-transparent tint
        self.tint = {
            "win":  (46, 204, 113, 120),
            "lose": (231, 76, 60, 120),
            "tie":  (90, 110, 140, 120),
        }.get(self.kind, (0, 0, 0, 120))

        # Buttons (bottom area)
        btn_y = self.H // 2 + 190
        self.rect_continue = pg.Rect(self.W // 2 - 280, btn_y, 180, 56)
        self.rect_retry    = pg.Rect(self.W // 2 -   90, btn_y, 180, 56)
        self.rect_home     = pg.Rect(self.W // 2 +  100, btn_y, 180, 56)
        self.labels = [
            ("Finish" if self.is_match_over else "Continue", self.rect_continue),
            ("Retry",  self.rect_retry),
            ("Home",   self.rect_home),
        ]

    # ---------------- input ---------------- #

    def _do_continue(self):
        if callable(self.on_continue):
            self.on_continue()
        self.m.pop()

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                self._do_continue()
            elif e.key == pg.K_RETURN:
                self.m.replace("game")
            elif e.key == pg.K_h:
                self.m.goto("home")
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            mx, my = e.pos
            if self.rect_continue.collidepoint(mx, my):
                self._do_continue()
            elif self.rect_retry.collidepoint(mx, my):
                self.m.replace("game")
            elif self.rect_home.collidepoint(mx, my):
                self.m.goto("home")

    def update(self, dt):
        pass

    # ---------------- draw ----------------- #

    def _draw_title_block(self, surface: pg.Surface):
        """Title area. One line for non-final rounds; two lines for final round."""
        result_word = "WIN" if self.kind == "win" else "LOSE" if self.kind == "lose" else "TIE"
        if self.is_match_over:
            # Two lines: T2 then T1
            l1 = self.font_mid.render(f"ROUND {self.round_idx}/3: YOU {result_word}", True, WHITE)
            l2 = self.font_title.render(f"RESULTS OF THIS MATCH: YOU {result_word}", True, WHITE)
            y0 = self.H // 2 - 180
            surface.blit(l1, l1.get_rect(center=(self.W // 2, y0)))
            surface.blit(l2, l2.get_rect(center=(self.W // 2, y0 + 58)))
        else:
            l = self.font_title.render(f"ROUND {self.round_idx}/3: YOU {result_word}", True, WHITE)
            surface.blit(l, l.get_rect(center=(self.W // 2, self.H // 2 - 170)))

    def _draw_scoreboard(self, surface: pg.Surface):
        """
        Pure rectangular table (no fill, no rounded corners), white lines.
        Header ("Human"/"Roo") and first column ("round n") are bold.
        """
        # Layout
        tbl_w, tbl_h = 520, 190
        x = self.W // 2 - tbl_w // 2
        y = self.H // 2 - 80
        rect = pg.Rect(x, y, tbl_w, tbl_h)

        # Outer rectangle
        pg.draw.rect(surface, GRID_LINE, rect, 2)

        # Sizes
        header_h = 36
        left_w = 120
        col_w = (rect.w - left_w) // 2
        row_h = (rect.h - header_h) // 3

        # Header baselines (no fill)
        # Vertical separators
        x_c1 = rect.x + left_w
        x_c2 = rect.x + left_w + col_w
        pg.draw.line(surface, GRID_LINE, (x_c1, rect.y), (x_c1, rect.bottom), 2)
        pg.draw.line(surface, GRID_LINE, (x_c2, rect.y), (x_c2, rect.bottom), 2)
        # Horizontal header line
        pg.draw.line(surface, GRID_LINE, (rect.x, rect.y + header_h), (rect.right, rect.y + header_h), 2)
        # Row lines
        for i in range(1, 3):
            y_line = rect.y + header_h + i * row_h
            pg.draw.line(surface, GRID_LINE, (rect.x, y_line), (rect.right, y_line), 2)

        # Header texts (bold)
        draw_bold_text(surface, self.font_mid, "Human", WHITE,
                       (rect.x + left_w + col_w * 0.5, rect.y + header_h // 2))
        draw_bold_text(surface, self.font_mid, "Roo", WHITE,
                       (rect.x + left_w + col_w * 1.5, rect.y + header_h // 2))

        # Rows
        for i in range(3):
            cy = rect.y + header_h + i * row_h + row_h // 2

            # First column label (bold)
            draw_bold_text(surface, self.font_mid, f"round {i+1}", WHITE,
                           (rect.x + left_w // 2, cy))

            # Values
            res = self.round_results[i] if i < len(self.round_results) else None
            v_h = v_r = ""
            if res == "human":
                v_h, v_r = "1", "0"
            elif res == "roo":
                v_h, v_r = "0", "1"
            elif res == "tie":
                v_h, v_r = "0", "0"

            if v_h:
                img = self.font_mid.render(v_h, True, WHITE)
                surface.blit(img, img.get_rect(center=(rect.x + left_w + col_w * 0.5, cy)))
            if v_r:
                img = self.font_mid.render(v_r, True, WHITE)
                surface.blit(img, img.get_rect(center=(rect.x + left_w + col_w * 1.5, cy)))

    def draw(self):
        s = self.m.screen

        # Colored tint
        overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
        overlay.fill(self.tint)
        s.blit(overlay, (0, 0))

        # Title and scoreboard
        self._draw_title_block(s)
        self._draw_scoreboard(s)

        # Buttons (simple stroked rectangles)
        for text, rect in self.labels:
            pg.draw.rect(s, (200, 200, 210), rect, width=2)  # no radius -> pure rectangle
            img = self.font_mid.render(text, True, WHITE)
            s.blit(img, img.get_rect(center=rect.center))
