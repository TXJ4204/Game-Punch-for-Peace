# src/ui/hud.py
import pygame as pg
from src.config import CFG

HUD_H = 96  # 顶栏高度（与 screen_game.py 保持一致）

def _text(surf, font, txt, color):
    return font.render(txt, True, color)

def _blit_center_y(surf, img, x, y_center):
    r = img.get_rect()
    r.midleft = (x, y_center)
    surf.blit(img, r)
    return r

def _draw_bar(surf, rect, pct, fill_col=(80, 180, 255), bg_col=(40, 45, 55)):
    # 背景
    pg.draw.rect(surf, bg_col, rect, border_radius=8)
    # 前景
    fill_w = int(rect.width * max(0.0, min(1.0, pct)))
    if fill_w > 0:
        pg.draw.rect(surf, fill_col, pg.Rect(rect.x, rect.y, fill_w, rect.height), border_radius=8)
    # 描边
    pg.draw.rect(surf, (0, 0, 0), rect, 1, border_radius=8)

def _draw_hearts_row(surf, left_x, mid_y, count, align="left", img=None, gap=6):
    # 支持位图爱心（50x50）或圆角矩形占位
    w = img.get_width() if img else 18
    h = img.get_height() if img else 16
    total_w = count * w + (count - 1) * gap if count > 0 else 0
    if align == "right":
        x = left_x - total_w
    else:
        x = left_x
    for i in range(count):
        if img:
            r = img.get_rect()
            r.midleft = (x, mid_y)
            surf.blit(img, r)
        else:
            r = pg.Rect(0, 0, w, h)
            r.midleft = (x, mid_y)
            pg.draw.rect(surf, (220, 80, 90), r, border_radius=6)
            pg.draw.rect(surf, (0, 0, 0), r, 1, border_radius=6)
        x += w + gap

def draw_top_hud(
    surf, W, H,
    halves_left_human: int,
    halves_left_roo: int,
    secs_left: int,
    fonts,
    st_pct_h: float,
    st_pct_r: float,
    round_idx: int,
    round_total: int = 3,
    heart_img_left=None,
    heart_img_right=None,
):
    # 背景条
    pg.draw.rect(surf, CFG.COL_BG, pg.Rect(0, 0, W, HUD_H))

    # 统一行高/留白
    pad = 12
    mid_y = HUD_H // 2

    # ====== 中间：上下两行（Round / Timer） ======
    round_txt = f"Round {round_idx}/{round_total}"
    timer_txt = f"{secs_left:02d}s"
    img_round = _text(surf, fonts["mid"], round_txt, CFG.COL_TEXT)
    img_timer = _text(surf, fonts["title"], timer_txt, CFG.COL_TEXT)

    # 垂直布局：round 在上，timer 在下，整体水平居中
    total_h = img_round.get_height() + 6 + img_timer.get_height()
    top_y = mid_y - total_h // 2
    r1 = img_round.get_rect(center=(W // 2, top_y + img_round.get_height() // 2))
    r2 = img_timer.get_rect(center=(W // 2, r1.bottom + 6 + img_timer.get_height() // 2))
    surf.blit(img_round, r1)
    surf.blit(img_timer, r2)

    # ====== 左侧：头像 | (心/耐力条/数值) 右对齐到头像右侧 ======
    # 头像占位（或你自己的头像贴图）
    ava_size = HUD_H - pad * 2
    ava_rect_L = pg.Rect(pad, pad, ava_size, ava_size)
    pg.draw.rect(surf, (70, 75, 85), ava_rect_L, border_radius=16)
    pg.draw.rect(surf, (0, 0, 0), ava_rect_L, 1, border_radius=16)

    # 左侧文字列的起点（从头像右侧开始）
    left_col_x = ava_rect_L.right + 10

    # 上：心（左对齐）
    _draw_hearts_row(surf, left_col_x, mid_y - 18, halves_left_human // 2, align="left", img=heart_img_left)

    # 中：耐力条（左对齐）
    bar_rect_L = pg.Rect(left_col_x, mid_y - 6, 160, 12)
    _draw_bar(surf, bar_rect_L, st_pct_h)

    # 下：数值（左对齐、同一水平线）
    st_txt_L = f"{int(st_pct_h * 100)}/100"
    img_st_L = _text(surf, fonts["sml"], st_txt_L, CFG.COL_TEXT)
    _blit_center_y(surf, img_st_L, left_col_x, mid_y + 16)

    # ====== 右侧：头像 | (心/耐力条/数值) 左对齐到头像左侧（整体右对齐） ======
    ava_rect_R = pg.Rect(W - pad - ava_size, pad, ava_size, ava_size)
    pg.draw.rect(surf, (70, 75, 85), ava_rect_R, border_radius=16)
    pg.draw.rect(surf, (0, 0, 0), ava_rect_R, 1, border_radius=16)

    # 右侧内容列右对齐到头像左边
    right_col_right = ava_rect_R.left - 10

    # 上：心（右对齐）
    _draw_hearts_row(surf, right_col_right, mid_y - 18, halves_left_roo // 2, align="right", img=heart_img_right)

    # 中：耐力条（右对齐）
    bar_w = 160
    bar_rect_R = pg.Rect(right_col_right - bar_w, mid_y - 6, bar_w, 12)
    _draw_bar(surf, bar_rect_R, st_pct_r)

    # 下：数值（右对齐，同一水平线）
    st_txt_R = f"{int(st_pct_r * 100)}/100"
    img_st_R = _text(surf, fonts["sml"], st_txt_R, CFG.COL_TEXT)
    r = img_st_R.get_rect()
    r.midright = (right_col_right, mid_y + 16)
    surf.blit(img_st_R, r)
