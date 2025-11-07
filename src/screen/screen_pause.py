# screen_pause.py
import pygame as pg
from src.config import CFG

class PauseScreen:
    """
    Pause overlay displayed on top of the game.
    ESC: Continue (pop)
    Enter: Retry (replace('game'))
    H: Home (goto('home'))
    Mouse clicks on any of the three button areas also work.
    """
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # Three button rectangles
        y = self.H // 2 + 28
        self.rect_continue = pg.Rect(self.W//2 - 260, y, 160, 54)
        self.rect_retry    = pg.Rect(self.W//2 -  80, y, 160, 54)
        self.rect_home     = pg.Rect(self.W//2 + 100, y, 160, 54)

        # font
        self.font_btn  = self.m.fonts["mid"]
        self.font_hint = self.m.fonts["sml"]

        # Button Text
        self.labels = [
            ("Continue", self.rect_continue),
            ("Retry",    self.rect_retry),
            ("Home",     self.rect_home)
        ]

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                self.m.pop()            # Continue the Game
            elif e.key == pg.K_RETURN:
                self.m.replace("game")  # retry
            elif e.key == pg.K_h:
                self.m.goto("home")     # back home page

        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            mx, my = e.pos
            if self.rect_continue.collidepoint(mx, my):
                self.m.pop()
            elif self.rect_retry.collidepoint(mx, my):
                self.m.replace("game")
            elif self.rect_home.collidepoint(mx, my):
                self.m.goto("home")

    def update(self, dt):
        pass

    def draw(self):
        s = self.m.screen
        # Semi-transparent Background
        overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        s.blit(overlay, (0, 0))

        # title
        title = self.m.fonts["title"].render("Paused", True, CFG.TEXT)
        s.blit(title, title.get_rect(center=(self.W//2, self.H//2 - 80)))

        # draw button
        for text, rect in self.labels:
            pg.draw.rect(s, (200, 200, 210), rect, width=2, border_radius=10)
            # --- Center text inside the button ---
            img = self.font_btn.render(text, True, (240, 240, 240))
            img_rect = img.get_rect(center=rect.center)
            s.blit(img, img_rect)

        # hint
        hint = self.font_hint.render(
            "[Esc] Continue   [Enter] Retry the game   [H] back Home", True, CFG.TEXT
        )
        s.blit(hint, hint.get_rect(center=(self.W//2, self.H//2 + 200)))
