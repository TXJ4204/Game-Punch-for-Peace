# src/screen/screen_single_info.py
import pygame as pg
from src.config import CFG
from src.widgets import Button

def draw_panel(surf, rect, fill=(55, 60, 70), outline=(25, 28, 34)):
    pg.draw.rect(surf, fill, rect, border_radius=14)
    pg.draw.rect(surf, outline, rect, 2, border_radius=14)

def human_icon(surf, rect, color=(80, 160, 240)):
    cx, cy = rect.centerx, rect.centery
    bw, bh = rect.width * 0.22, rect.height * 0.45
    body = pg.Rect(0, 0, bw, bh); body.center = (cx, cy + rect.height * 0.06)
    head_r = int(bw * 0.55)
    pg.draw.rect(surf, color, body, border_radius=10)
    pg.draw.circle(surf, color, (int(cx), int(body.top - head_r * 0.6)), head_r)

def wrap_text(text, font, max_width):
    """
    Return a list of lines wrapped to max_width using font metrics.
    Keeps words; falls back to char-split if a single word exceeds width.
    """
    words = text.split(' ')
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_width:
            cur = test
        else:
            if cur: lines.append(cur)
            # a single super-long word: hard wrap
            if font.size(w)[0] > max_width:
                buf = ""
                for ch in w:
                    if font.size(buf + ch)[0] <= max_width:
                        buf += ch
                    else:
                        lines.append(buf)
                        buf = ch
                cur = buf
            else:
                cur = w
    if cur: lines.append(cur)
    return lines

class SingleInfoScreen:
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        self.btn_enter = Button(pg.Rect(self.W // 2 - 140, self.H - 84, 280, 54),
                                "Enter", self.m.fonts["big"])
        self.btn_back  = Button(pg.Rect(24, self.H - 64, 140, 40),
                                "Back", self.m.fonts["mid"])

    def _draw_full_grid(self):
        COLS, ROWS = 16, 9
        cell_w = self.W // COLS
        cell_h = self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                rect = pg.Rect(c * cell_w, r * cell_h, cell_w, cell_h)
                col = CFG.GRID_LIGHT if (c + r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(self.m.screen, col, rect)

    def handle_event(self, e):
        if self.btn_enter.handle_event(e) or (e.type == pg.KEYDOWN and e.key == pg.K_RETURN):
            self.m.goto("game")
        if self.btn_back.handle_event(e) or (e.type == pg.KEYDOWN and e.key == pg.K_BACKSPACE):
            self.m.goto("mode")

    def update(self, dt):
        pass

    def draw(self):
        s = self.m.screen
        s.fill(CFG.BG)
        self._draw_full_grid()

        # Title
        title = self.m.fonts["title"].render("Single Player", True, CFG.TEXT)
        s.blit(title, title.get_rect(center=(self.W // 2, 72)))

        # Panels
        left  = pg.Rect(48, 120, self.W // 2 - 72, self.H - 220)
        right = pg.Rect(self.W // 2 + 24, 120, self.W // 2 - 72, self.H - 220)
        draw_panel(s, left); draw_panel(s, right)

        # Left: Mode + icon
        hdr = self.m.fonts["big"].render("Mode", True, CFG.TEXT)
        s.blit(hdr, hdr.get_rect(center=(left.centerx, left.top + 26)))
        # Ensure proper padding for the graphic within the panel
        icon_rect = left.inflate(-left.width * 0.5, -left.height * 0.45)
        human_icon(s, icon_rect)

        # Right: How to Play (wrapped bullets)
        hdr2 = self.m.fonts["big"].render("How to Play", True, CFG.TEXT)
        s.blit(hdr2, hdr2.get_rect(center=(right.centerx, right.top + 26)))

        pad = 24
        wrap_width = right.width - pad * 2
        y = right.top + 74
        line_h = int(self.m.fonts["mid"].get_linesize() * 1.15)

        bullets = [
            "Move with Arrow keys (1 cell each).",
            "Hold Space to Block (both lose a bit of stamina; reduced damage).",
            "Stay more than 1 cell away to avoid punches.",
            "Exploit Roo's 2-cell jump to bait whiffs.",
            "[Backspace] Back to Mode    [Enter] Start Game",
        ]

        for t in bullets:
            lines = wrap_text(t, self.m.fonts["mid"], wrap_width)
            # Draw a bullet dot at the start of each item (dot on the first wrapped line only)
            if lines:
                dot = self.m.fonts["mid"].render("• ", True, CFG.TEXT)
                s.blit(dot, (right.left + pad, y))
                x0 = right.left + pad + dot.get_width()
                # First line
                img = self.m.fonts["mid"].render(lines[0], True, CFG.TEXT)
                s.blit(img, (x0, y)); y += line_h
                # Continuation lines (no dot; align with text)
                for cont in lines[1:]:
                    img2 = self.m.fonts["mid"].render(cont, True, CFG.TEXT)
                    s.blit(img2, (right.left + pad + dot.get_width(), y))
                    y += line_h
            y += 6  # Add small spacing between bullet items

            # Prevent overflow: stop rendering when reaching panel bottom
            if y > right.bottom - pad:
                break

        # Buttons
        self.btn_back.draw(s)
        self.btn_enter.draw(s)
