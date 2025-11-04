# screens.py
import pygame as pg

# Import only the classes needed by the “factory” (avoid circular imports)
from .screen_home import HomeScreen
from .screen_mode import ModeScreen
from .screen_single_info import SingleInfoScreen
from .screen_game import GameScreen
from .screen_end import EndScreen
from .screen_pause import PauseScreen  # ← new

class ScreenManager:
    """
    Manage a stack of screens:
      - goto(name): clear the stack and enter the screen
      - push(name): push an overlay screen (e.g., pause)
      - pop(): exit the overlay and return to the underlying screen
      - replace(name): replace the top with a new screen (e.g., Retry)
    Draw order: render from bottom to top; overlays draw only a translucent layer + UI.
    Event dispatch: send events only to the top-of-stack (current) screen.
    """
    def __init__(self, screen, clock, fonts, size):
        self.screen = screen
        self.clock = clock
        self.fonts = fonts
        self.size = size

        self._routes = {
            "home":         lambda m, **kw: HomeScreen(m, **kw),
            "mode":         lambda m, **kw: ModeScreen(m, **kw),
            "single_info":  lambda m, **kw: SingleInfoScreen(m, **kw),
            "game":         lambda m, **kw: GameScreen(m, **kw),
            "end":          lambda m, **kw: EndScreen(m, **kw),
            "pause":        lambda m, **kw: PauseScreen(m, **kw),  # ← new
        }
        self.stack = []

    # --- helpers ---
    def _make(self, name, **kwargs):
        return self._routes[name](self, **kwargs)

    def current(self):
        return self.stack[-1] if self.stack else None

    # --- APIs ---
    def goto(self, name, **kwargs):
        self.stack = [self._make(name, **kwargs)]

    def push(self, name, **kwargs):
        self.stack.append(self._make(name, **kwargs))

    def pop(self):
        if self.stack:
            self.stack.pop()

    def replace(self, name, **kwargs):
        if self.stack:
            self.stack.pop()
        self.push(name, **kwargs)

    # --- main loop hooks ---
    def handle_event(self, e):
        cur = self.current()
        if cur:
            cur.handle_event(e)

    def update(self, dt):
        cur = self.current()
        if cur:
            cur.update(dt)

    def draw(self):
        # Draw from bottom to top; the top layer may overlay with translucency
        for view in self.stack:
            view.draw()
        pg.display.flip()
