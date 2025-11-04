# src/screen/__init__.py
from .screen_home import HomeScreen
from .screen_mode import ModeScreen
from .screen_single_info import SingleInfoScreen
from .screen_game import GameScreen
from .screen_end import EndScreen

REGISTRY = {
    "home": HomeScreen,
    "mode": ModeScreen,
    "single_info": SingleInfoScreen,
    "game": GameScreen,
    "end": EndScreen,
}