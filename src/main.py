# src/main.py
import sys
import pygame as pg
from src.config import CFG
from src.screen.screens import ScreenManager  # 统一使用 src.*

WIN_W, WIN_H = 1280, 720

def pick_font(size):
    candidates = [
        "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI",
        "Noto Sans CJK SC", "Source Han Sans SC", "Arial Unicode MS", None
    ]
    for name in candidates:
        try:
            f = pg.font.SysFont(name, size)
            _ = f.render("Aa", True, (255, 255, 255))
            return f
        except Exception:
            continue
    return pg.font.SysFont(None, size)

def main():
    pg.init()
    pg.font.init()

    # 事件白名单（避免 IME 的 TEXTINPUT 干扰）
    pg.event.set_allowed([pg.QUIT, pg.KEYDOWN, pg.KEYUP, pg.MOUSEBUTTONDOWN, pg.MOUSEMOTION])
    # 允许窗口捕获输入
    pg.event.set_grab(True)
    try:
        pg.key.stop_text_input()
    except Exception:
        pass

    screen = pg.display.set_mode((WIN_W, WIN_H), pg.SCALED)
    pg.display.set_caption("Kangaroo vs Human — MVP")
    clock = pg.time.Clock()

    fonts = {
        "title": pick_font(52),
        "big":   pick_font(32),
        "mid":   pick_font(22),
        "sml":   pick_font(18),
        # 可选：HUD/计时器等独立字号
        "hud":   pick_font(20),
        "timer": pick_font(28),
    }

    # 关键：按 screens.py 的签名传入 clock
    manager = ScreenManager(screen, clock, fonts, (WIN_W, WIN_H))
    manager.goto("home")  # 需要在 screens.py 的 routes 中注册 "home"

    while True:
        dt = clock.tick(CFG.FPS)

        # 无焦点提示层（仅响应点击/关闭）
        if not pg.key.get_focused():
            overlay = pg.Surface((WIN_W, WIN_H), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            tip = fonts["big"].render("Click to focus the game window", True, (230, 230, 230))
            screen.blit(overlay, (0, 0))
            screen.blit(tip, tip.get_rect(center=(WIN_W // 2, WIN_H // 2)))
            pg.display.flip()

            for e in pg.event.get():
                if e.type == pg.QUIT:
                    pg.quit(); sys.exit()
                if e.type == pg.MOUSEBUTTONDOWN:
                    pass
            continue

        for e in pg.event.get():
            if e.type == pg.QUIT:
                pg.quit(); sys.exit()
            manager.handle_event(e)

        manager.update(dt)

        # 先用背景色清屏，避免某个 screen 没有绘制导致纯黑
        screen.fill(CFG.BG)
        manager.draw()
        pg.display.flip()

if __name__ == "__main__":
    main()
