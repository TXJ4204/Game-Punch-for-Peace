# src/screen/screen_pause.py
from __future__ import annotations
import pygame as pg

class PauseScreen:
    """
    Minimal pause screen. Esc/Enter/Space resumes.
    If ScreenManager has pop(), use it; otherwise fall back to goto(return_to).
    """
    def __init__(self, manager, **kwargs):
        self.m = manager
        self.return_to = kwargs.get("return_to", "game")
        self.W, self.H = manager.size
        self.title = "Paused"

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_ESCAPE, pg.K_RETURN, pg.K_SPACE):
                if hasattr(self.m, "pop"):
                    self.m.pop()
                else:
                    self.m.goto(self.return_to)

    def update(self, dt):  # nothing to update
        pass

    def draw(self):
        s = self.m.screen
        overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        s.blit(overlay, (0, 0))

        big = self.m.fonts["title"].render(self.title, True, (255, 255, 255))
        tip = self.m.fonts["mid"].render("Press Esc/Enter/Space to resume", True, (220, 220, 220))
        s.blit(big, big.get_rect(center=(self.W//2, self.H//2 - 20)))
        s.blit(tip, tip.get_rect(center=(self.W//2, self.H//2 + 28)))
