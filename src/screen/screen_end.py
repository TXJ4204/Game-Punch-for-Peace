# screen_end.py
import pygame as pg
from config import CFG

class EndScreen:
    def __init__(self, manager, result_text: str):
        self.m = manager
        self.W, self.H = manager.size
        self.result = result_text

    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_RETURN:     # Retry
                self.m.goto("game")
            elif e.key == pg.K_h:        # Home
                self.m.goto("home")

    def update(self, dt):
        pass  # Do not auto-exit or auto-jump

    def draw(self):
        s = self.m.screen
        s.fill((24,24,28))
        title = self.m.fonts["title"].render(self.result, True, (220,220,230))
        s.blit(title, title.get_rect(center=(self.W//2, self.H//2 - 20)))

        hint = "[Enter] Retry    [H] Back to Home    Esc to Quit"
        tip = self.m.fonts["mid"].render(hint, True, (200,200,210))
        s.blit(tip, tip.get_rect(center=(self.W//2, self.H//2 + 40)))
