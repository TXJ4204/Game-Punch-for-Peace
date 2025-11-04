# tools/inspect_hitboxes02.py
# Fixed "02" inspector: saves JSON that matches sprites.py expectations
# - tight bbox   -> "bbox": [x,y,w,h]   (image-space)
# - hit rect     -> "parts": [{"x":...,"y":...,"w":...,"h":...}]   (image-space)
# - mask outline -> "maskPoly": [[x,y], ...]  (image-space)
# - fist points  -> "fist": {"right":[x,y], "left":[x,y]} (image-space)
#
# Keys in JSON: per-image filename, e.g. "roo02.png": {...}

import json
from pathlib import Path
import pygame as pg

# ---------- paths ----------
ROOT   = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "animation"         # <-- 放你 7 张 PNG 的目录
OUT_JS = ASSETS / "hitbox_meta.json"           # <-- sprites.py 将会读取这个

# ---------- UI layout ----------
COLS, ROWS = 3, 3
CELL_W, CELL_H = 420, 260
PADDING = 24
TITLE_H = 52

WIN_W = COLS * CELL_W + PADDING * 2
WIN_H = ROWS * CELL_H + PADDING * 2 + TITLE_H

# ---------- colors ----------
BG_DARK   = (18, 19, 22)
INK       = (235, 235, 235)
YELLOW    = (250, 210, 60)     # tight bbox
GREEN     = (60, 220, 160)     # suggested hit rect
MAGENTA   = (240, 110, 255)    # mask outline
RED       = (240, 90, 90)      # fist (right)
BLUE      = (90, 150, 255)     # fist (left)

# ---------- params ----------
ALPHA_THR = 170      # 忽略浅色边缘/发光的透明像素
SHRINK_X  = 0.18     # 命中盒相对 bbox 的水平收缩（左右各 18%）
SHRINK_YU = 0.06     # 命中盒相对 bbox 的上方收缩（6%）
SHRINK_YD = 0.14     # 命中盒相对 bbox 的下方收缩（下留一点脚部）

FONT_CAND = [
    "Microsoft YaHei UI","Microsoft YaHei","Segoe UI",
    "Noto Sans CJK SC","Source Han Sans SC","Arial Unicode MS", None
]

def pick_font(size):
    for n in FONT_CAND:
        try:
            f = pg.font.SysFont(n, size)
            _ = f.render("Aa", True, (255,255,255))
            return f
        except Exception:
            continue
    return pg.font.SysFont(None, size)

def list_pngs():
    # 自动列举（确保 roo03.png 会被包含）
    return sorted(p for p in ASSETS.glob("*.png"))

def draw_rect(surf, color, r, w=2):
    pg.draw.rect(surf, color, r, w)

def draw_cross(surf, color, pos, size=6, width=2):
    x, y = pos
    pg.draw.line(surf, color, (x-size, y), (x+size, y), width)
    pg.draw.line(surf, color, (x, y-size), (x, y+size), width)

def mask_and_tight_bbox(img_surf: pg.Surface):
    # 全都在“原始图片坐标系（image-space）”完成
    m = pg.mask.from_surface(img_surf, ALPHA_THR)
    rects = m.get_bounding_rects()
    tight = rects[0] if rects else None
    outline = m.outline() if m else None
    return tight, outline  # pg.Rect, [(x,y),...]

def make_hit_rect_from_bbox(b: pg.Rect):
    hit = b.copy()
    hit.x += int(hit.w * SHRINK_X)
    hit.w  = int(hit.w * (1.0 - SHRINK_X*2))
    hit.y += int(hit.h * SHRINK_YU)
    hit.h  = int(hit.h * (1.0 - SHRINK_YU - SHRINK_YD))
    return hit

def fist_points_from_bbox(b: pg.Rect):
    # 在 bbox 上确定拳点（右/左）
    pad_x = int(b.w * 0.07)
    y     = b.y + int(b.h * 0.40)
    right = (b.right - pad_x, y)
    left  = (b.left  + pad_x, y)
    return left, right

def run():
    pg.init(); pg.font.init()
    screen = pg.display.set_mode((WIN_W, WIN_H))
    pg.display.set_caption("Inspect Hitboxes — v02 fixed")
    f_title = pick_font(18)
    f_small = pick_font(18)

    names = list_pngs()
    if not names:
        print("No PNG found under", ASSETS)
        pg.quit(); return

    # 预载原图（保持原始尺寸，不缩放；缩放只用于预览）
    images = {p.name: pg.image.load(p.as_posix()).convert_alpha() for p in names}

    results = {}
    clock = pg.time.Clock()
    page = 0
    per_page = COLS * ROWS
    running = True

    while running:
        clock.tick(60)
        screen.fill(BG_DARK)

        title = f"{ASSETS.as_posix()}  |  {len(names)} images  |  Page {page+1}/{(len(names)-1)//per_page+1}  (S=save JSON, ←/→ page, Esc=quit)"
        screen.blit(f_title.render(title, True, INK), (PADDING, PADDING))

        grid = pg.Rect(PADDING, PADDING + TITLE_H, WIN_W - 2*PADDING, WIN_H - 2*PADDING - TITLE_H)

        view_items = names[page*per_page:(page+1)*per_page]
        for idx, path in enumerate(view_items):
            name = path.name
            img0 = images[name]                           # 原图（image-space）
            # 仅用于预览的缩放
            cx, cy = idx % COLS, idx // COLS
            cell = pg.Rect(grid.x + cx*CELL_W, grid.y + cy*CELL_H, CELL_W, CELL_H)
            slot = cell.inflate(-32, -32)
            scale = min(slot.w/img0.get_width(), slot.h/img0.get_height(), 1.0)
            img = pg.transform.smoothscale(img0, (int(img0.get_width()*scale), int(img0.get_height()*scale)))
            view_rect = img.get_rect(center=slot.center)
            screen.blit(img, view_rect)

            # 文件名
            screen.blit(f_small.render(name, True, INK), (slot.x, slot.y-22))

            # —— 在原图上算 bbox/outline/hit/fist ——（保存到 JSON 用）
            bbox_img, outline_img = mask_and_tight_bbox(img0)
            if bbox_img:
                hit_img = make_hit_rect_from_bbox(bbox_img)
                fist_l_img, fist_r_img = fist_points_from_bbox(bbox_img)

                # 映射到预览坐标（只为展示）
                sx = view_rect.w / img0.get_width()
                sy = view_rect.h / img0.get_height()

                def map_rect(r_img: pg.Rect):
                    return pg.Rect(
                        int(view_rect.x + r_img.x * sx),
                        int(view_rect.y + r_img.y * sy),
                        int(r_img.w * sx),
                        int(r_img.h * sy)
                    )

                bbox_view = map_rect(bbox_img)
                hit_view  = map_rect(hit_img)
                draw_rect(screen, YELLOW, bbox_view, 2)
                draw_rect(screen, GREEN,  hit_view,  2)

                if outline_img and len(outline_img) > 2:
                    pts = [(int(view_rect.x + x*sx), int(view_rect.y + y*sy)) for (x,y) in outline_img]
                    try: pg.draw.lines(screen, MAGENTA, True, pts, 2)
                    except: pass

                # 拳点也画出来看看
                fx_r = (int(view_rect.x + fist_r_img[0]*sx), int(view_rect.y + fist_r_img[1]*sy))
                fx_l = (int(view_rect.x + fist_l_img[0]*sx), int(view_rect.y + fist_l_img[1]*sy))
                draw_cross(screen, RED,  fx_r, size=7, width=2)
                draw_cross(screen, BLUE, fx_l, size=7, width=2)

                # —— 保存为 image-space 的数值（sprites.py 直接可用）——
                results[name] = {
                    "bbox": [bbox_img.x, bbox_img.y, bbox_img.w, bbox_img.h],
                    "parts": [{"x": hit_img.x, "y": hit_img.y, "w": hit_img.w, "h": hit_img.h}],
                    "maskPoly": [[int(x), int(y)] for (x,y) in (outline_img or [])],
                    "fist": {
                        "left":  [int(fist_l_img[0]), int(fist_l_img[1])],
                        "right": [int(fist_r_img[0]), int(fist_r_img[1])],
                    }
                }

        pg.display.flip()

        # 事件
        for e in pg.event.get():
            if e.type == pg.QUIT:
                running = False
            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    running = False
                elif e.key == pg.K_RIGHT:
                    if (page+1)*per_page < len(names): page += 1
                elif e.key == pg.K_LEFT:
                    if page > 0: page -= 1
                elif e.key == pg.K_s:
                    OUT_JS.write_text(json.dumps(results, indent=2, ensure_ascii=False))
                    print(f"[saved] {OUT_JS}")

    pg.quit()

if __name__ == "__main__":
    run()
