# screen_pause.py
import pygame as pg
from src.config import CFG

class PauseScreen:
    """
    Pause overlay displayed on top of the game. Handled by ScreenManager as the "top-of-stack" screen.
    Esc: Continue (you could also only trigger push in GameScreen and not handle Esc here)
    C: Continue (pop)
    Enter: Retry (replace('game'))
    H: Home (goto('home'))
    Mouse clicks on any of the three button areas also work.
    """
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # Three clickable rectangles
        y = self.H // 2 + 28
        self.rect_continue = pg.Rect(self.W//2 - 260, y, 160, 54)
        self.rect_retry    = pg.Rect(self.W//2 -  80, y, 160, 54)
        self.rect_home     = pg.Rect(self.W//2 + 100, y, 160, 54)

    # Input is only handled on the pause screen; do not pass down to the underlying game
    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_c:
                self.m.pop()            # Continue
            elif e.key == pg.K_RETURN:
                self.m.replace("game")  # Restart
            elif e.key == pg.K_h:
                self.m.goto("home")     # Go to Home

        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            mx, my = e.pos
            if self.rect_continue.collidepoint(mx, my):
                self.m.pop()
            elif self.rect_retry.collidepoint(mx, my):
                self.m.replace("game")
            elif self.rect_home.collidepoint(mx, my):
                self.m.goto("home")

    def update(self, dt): pass

    def draw(self):
        s = self.m.screen
        # Translucent overlay drawn on top of the "underlying game screen"
        overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        s.blit(overlay, (0, 0))

        title = self.m.fonts["title"].render("Paused", True, CFG.TEXT)
        s.blit(title, title.get_rect(center=(self.W//2, self.H//2 - 60)))

        # Copy/text
        opts = self.m.fonts["mid"].render("[C] Continue   [Enter] Retry   [H] Home", True, CFG.TEXT)
        s.blit(opts, opts.get_rect(center=(self.W//2, self.H//2 + -2)))

        # Visible button frames to facilitate mouse clicks
        for rect in (self.rect_continue, self.rect_retry, self.rect_home):
            pg.draw.rect(s, (200, 200, 210), rect, width=2, border_radius=10)
