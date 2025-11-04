# tools/inspect_hitboxes.py
import json, sys
from pathlib import Path
import pygame as pg

# === 配置 ===
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "animation"
OUT_JSON = ASSETS / "hitbox_suggestion.json"

WIN_W, WIN_H = 1200, 700
GRID_W, GRID_H = 8, 5                # 跟 config 里的棋盘一致
RATIO = 1.30                         # 和你 sprites._fit_to_cell 的 ratio 一致
CELL_W, CELL_H = WIN_W // GRID_W, (WIN_H - 100) // GRID_H  # 100 当成 HUD 预留，可自行改

NAMES = [
    "people01.png", "people02.png", "people03.png",
    "roo01.png", "roo02.png", "roo04.png", "roo03.png"
]

def fit_to_cell(img, cw, ch, ratio):
    w, h = img.get_size()
    maxw, maxh = int(cw * ratio), int(ch * ratio)
    s = min(maxw / max(w,1), maxh / max(h,1))
    return pg.transform.smoothscale(img, (max(1,int(w*s)), max(1,int(h*s))))

def rel_rect(rect, base):
    # 输出相对 [x0, y0, w, h]，坐标原点是贴图绘制 rect 的左上角
    return [
        round((rect.x - base.x) / base.w, 4),
        round((rect.y - base.y) / base.h, 4),
        round(rect.w / base.w, 4),
        round(rect.h / base.h, 4),
    ]

def main():
    pg.init()
    screen = pg.display.set_mode((WIN_W, WIN_H))
    pg.display.set_caption("Inspect Hitboxes")
    font = pg.font.SysFont("Segoe UI", 18)

    rows, cols = 3, 3
    pad = 24
    cellW = (WIN_W - pad*(cols+1)) // cols
    cellH = (WIN_H - pad*(rows+1)) // rows

    results = {}
    running = True
    while running:
        screen.fill((18,19,22))
        i = 0
        for name in NAMES:
            p = ASSETS / name
            if not p.exists():
                continue
            img_raw = pg.image.load(str(p)).convert_alpha()
            img = fit_to_cell(img_raw, CELL_W, CELL_H, RATIO)

            # 放到格子里居中
            r = img.get_rect()
            c = i % cols
            r_ = i // cols
            slot = pg.Rect(
                pad + c*(cellW+pad),
                pad + r_*(cellH+pad),
                cellW, cellH
            )
            r.center = slot.center
            screen.blit(img, r)

            # alpha mask → 可见像素外接框（tight bbox）
            m = pg.mask.from_surface(img)
            bbox = m.get_bounding_rects()
            if bbox:
                b = bbox[0].move(r.topleft)  # 转成屏幕坐标
                pg.draw.rect(screen, (255, 200, 0), b, 2)  # 黄色：可见像素外接框

                # 建议命中盒：对外接框再缩一点，垂直上缩 10%，下方略伸，左右各缩 20%
                hit = b.copy()
                hit.x += int(hit.w * 0.18)
                hit.w  = int(hit.w * 0.64)
                hit.y += int(hit.h * 0.06)
                hit.h  = int(hit.h * 0.86)
                pg.draw.rect(screen, (0, 230, 140), hit, 2)  # 绿色：建议命中盒

                # 建议拳头点（相对外接框）：高度 40%，左右贴近 7% 内边距
                def fist_pt(side):
                    padx = int(b.w * 0.07)
                    x = b.right - padx if side == "right" else b.left + padx
                    y = b.top + int(b.h * 0.40)
                    return (x, y)
                pg.draw.circle(screen, (255, 80, 80), fist_pt("right"), 4)  # 右
                pg.draw.circle(screen, (80, 160, 255), fist_pt("left"), 4)   # 左

                # 文本
                txt = font.render(name, True, (220, 220, 220))
                screen.blit(txt, (slot.x+8, slot.y+8))

                # 记录相对数据（相对 img 的绘制 rect）
                results[name] = {
                    "bbox_rel": rel_rect(b, r),
                    "hit_rel":  rel_rect(hit, r),
                    "fist_rel": {
                        "right": [
                            round((b.right - int(b.w*0.07) - r.x) / r.w, 4),
                            round((b.top + int(b.h*0.40) - r.y) / r.h, 4)
                        ],
                        "left": [
                            round((b.left + int(b.w*0.07) - r.x) / r.w, 4),
                            round((b.top + int(b.h*0.40) - r.y) / r.h, 4)
                        ],
                    }
                }

            i += 1

        tip = font.render("Press S to save JSON, Esc to quit.", True, (200,200,200))
        screen.blit(tip, (10, WIN_H-28))
        pg.display.flip()

        for e in pg.event.get():
            if e.type == pg.QUIT: running = False
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE: running = False
                if e.key == pg.K_s:
                    OUT_JSON.write_text(json.dumps(results, indent=2))
                    print(f"Saved: {OUT_JSON}")
    pg.quit()

if __name__ == "__main__":
    sys.exit(main())
