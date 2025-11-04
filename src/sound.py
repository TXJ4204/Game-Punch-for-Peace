import pygame as pg

class Sfx:
    def __init__(self):
        self.enabled = False
    def load(self):
        self.enabled = False
    def play(self, name: str):
        if not self.enabled:
            return
        # self.sounds[name].play()

SOUND = Sfx()
