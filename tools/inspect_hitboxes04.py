# tools/inspect_hitboxes02.py — v0.4
# 手动校准拳点：点击/拖动红(右拳)蓝(左拳)，选中有高亮；S保存JSON
import json
from pathlib import Path
import pygame as pg

# ---------- paths ----------
ROOT   = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "animation"
OUT_JS = ASSETS / "hitbox_meta.json"

# ---------- layout ----------
COLS, ROWS = 3, 3
CELL_W, CELL_H = 420, 260
PADDING, TITLE_H = 24, 52
WIN_W = COLS * CELL_W + PADDING * 2
WIN_H = ROWS * CELL_H + PADDING * 2 + TITLE_H

# ---------- colors ----------
BG_DARK   = (18, 19, 22)
INK       = (235, 235, 235)
YELLOW    = (250, 210, 60)   # tight bbox
GREEN     = (60, 220, 160)   # suggested hitbox
MAGENTA   = (240, 110, 255)  # mask outline
RED       = (240, 90, 90)    # right fist
BLUE      = (90, 150, 255)   # left fist
CYAN_HL   = (0, 255, 255)    # selection ring

# ---------- params ----------
ALPHA_THR = 170
SHRINK_X, SHRINK_YU, SHRINK_YD = 0.18, 0.06, 0.14
FONT_CAND = ["Microsoft YaHei UI","Segoe UI","Arial Unicode MS",None]

def pick_font(size):
    for n in FONT_CAND:
        try:
            f = pg.font.SysFont(n, size)
            f.render("Aa", True, (255,255,255))
            return f
        except: continue
    return pg.font.SysFont(None, size)

def list_pngs():
    return sorted(p for p in ASSETS.glob("*.png"))

def mask_and_tight_bbox(img: pg.Surface):
    m = pg.mask.from_surface(img, ALPHA_THR)
    rects = m.get_bounding_rects()
    tight = rects[0] if rects else None
    outline = m.outline() if m else None
    return tight, outline

def make_hit_rect_from_bbox(b: pg.Rect):
    hit = b.copy()
    hit.x += int(hit.w * SHRINK_X)
    hit.w  = int(hit.w * (1.0 - SHRINK_X*2))
    hit.y += int(hit.h * SHRINK_YU)
    hit.h  = int(hit.h * (1.0 - SHRINK_YU - SHRINK_YD))
    return hit

def default_fists(b: pg.Rect):
    pad_x = int(b.w * 0.07)
    y     = b.y + int(b.h * 0.40)
    right = [b.right - pad_x, y]
    left  = [b.left  + pad_x, y]
    return left, right

def compute_slot_rect(grid_rect, idx):
    """网格中第 idx 个 cell 的展示区域（留边）"""
    cx, cy = idx % COLS, idx // COLS
    cell = pg.Rect(
        grid_rect.x + cx*CELL_W,
        grid_rect.y + cy*CELL_H,
        CELL_W, CELL_H
    )
    return cell.inflate(-32, -32)

def compute_view(img: pg.Surface, slot: pg.Rect):
    """返回缩放后的图像和其在屏幕中的 rect，以及缩放比例"""
    scale = min(slot.w/img.get_width(), slot.h/img.get_height(), 1.0)
    img2 = pg.transform.smoothscale(
        img, (int(img.get_width()*scale), int(img.get_height()*scale))
    )
    rect2 = img2.get_rect(center=slot.center)
    return img2, rect2, scale

def run():
    pg.init(); pg.font.init()
    screen = pg.display.set_mode((WIN_W, WIN_H))
    pg.display.set_caption("Inspect Hitboxes — v0.4")
    f_title, f_small = pick_font(18), pick_font(18)

    names = list_pngs()
    images = {p.name: pg.image.load(p.as_posix()).convert_alpha() for p in names}

    # 生成/加载结果
    results = {}
    for name, img in images.items():
        bbox, outline = mask_and_tight_bbox(img)
        if not bbox: continue
        hit = make_hit_rect_from_bbox(bbox)
        l, r = default_fists(bbox)
        results[name] = {
            "bbox": [bbox.x, bbox.y, bbox.w, bbox.h],
            "parts": [{"x": hit.x, "y": hit.y, "w": hit.w, "h": hit.h}],
            "maskPoly": [[int(x), int(y)] for (x,y) in (outline or [])],
            "fist": {"left": l, "right": r},
        }

    clock = pg.time.Clock()
    page = 0; per_page = COLS * ROWS
    dragging = None   # (name, 'left'|'right', scale, view_rect)
    selected = None   # (name, 'left'|'right')
    running = True

    while running:
        clock.tick(60)
        screen.fill(BG_DARK)

        title = f"{ASSETS.as_posix()}  |  {len(names)} images  |  Page {page+1}/{(len(names)-1)//per_page+1}   (S=save JSON, ←/→, Esc=quit)"
        screen.blit(f_title.render(title, True, INK), (PADDING, PADDING))

        grid = pg.Rect(PADDING, PADDING + TITLE_H, WIN_W - 2*PADDING, WIN_H - 2*PADDING - TITLE_H)
        items = names[page*per_page:(page+1)*per_page]

        # ——— 绘制 ———
        for idx, path in enumerate(items):
            name = path.name
            img0 = images[name]

            slot = compute_slot_rect(grid, idx)
            img, view_rect, scale = compute_view(img0, slot)

            # 标题
            screen.blit(f_small.render(name, True, INK), (slot.x, slot.y-22))
            # 图像
            screen.blit(img, view_rect)

            data = results[name]
            bx, by, bw, bh = data["bbox"]
            hx, hy, hw, hh = data["parts"][0].values()

            # 坐标映射
            def R(x,y,w,h):
                return pg.Rect(
                    int(view_rect.x + x*scale),
                    int(view_rect.y + y*scale),
                    int(w*scale), int(h*scale)
                )

            # 紧外接框 / 建议命中盒
            pg.draw.rect(screen, YELLOW, R(bx,by,bw,bh), 2)
            pg.draw.rect(screen, GREEN,  R(hx,hy,hw,hh), 2)

            # 轮廓
            pts = data.get("maskPoly", [])
            if pts and len(pts) > 2:
                sc = [(int(view_rect.x + x*scale), int(view_rect.y + y*scale)) for (x,y) in pts]
                pg.draw.lines(screen, MAGENTA, True, sc, 2)

            # 拳点
            fists = data["fist"]
            for tag, color in [("left", BLUE), ("right", RED)]:
                fx, fy = fists[tag]
                fxv, fyv = int(view_rect.x + fx*scale), int(view_rect.y + fy*scale)
                # 十字
                pg.draw.line(screen, color, (fxv-6, fyv), (fxv+6, fyv), 2)
                pg.draw.line(screen, color, (fxv, fyv-6), (fxv, fyv+6), 2)
                # 选中高亮
                if selected == (name, tag):
                    pg.draw.circle(screen, CYAN_HL, (fxv, fyv), 10, 2)
                    lab = f_small.render(tag, True, CYAN_HL)
                    screen.blit(lab, (fxv+12, fyv-10))

        pg.display.flip()

        # ——— 输入 ———
        for e in pg.event.get():
            if e.type == pg.QUIT:
                running = False

            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    running = False
                elif e.key == pg.K_RIGHT and (page+1)*per_page < len(names):
                    page += 1
                    selected = None
                elif e.key == pg.K_LEFT and page > 0:
                    page -= 1
                    selected = None
                elif e.key == pg.K_s:
                    OUT_JS.write_text(json.dumps(results, indent=2, ensure_ascii=False))
                    print(f"[saved] {OUT_JS}")

            elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                # 命中拳点（使用与绘制完全一致的 view_rect/scale）
                hit_any = False
                for idx, path in enumerate(items):
                    name = path.name
                    slot = compute_slot_rect(grid, idx)
                    _, view_rect, scale = compute_view(images[name], slot)
                    data = results[name]
                    for tag in ("left", "right"):
                        fx, fy = data["fist"][tag]
                        fxv = int(view_rect.x + fx*scale)
                        fyv = int(view_rect.y + fy*scale)
                        if abs(mx-fxv) <= 8 and abs(my-fyv) <= 8:
                            dragging = (name, tag, scale, view_rect)
                            selected = (name, tag)
                            hit_any = True
                            pg.mouse.set_cursor(pg.SYSTEM_CURSOR_SIZEALL)
                            break
                    if hit_any: break
                if not hit_any:
                    selected = None

            elif e.type == pg.MOUSEBUTTONUP and e.button == 1:
                dragging = None
                pg.mouse.set_cursor(pg.SYSTEM_CURSOR_ARROW)

            elif e.type == pg.MOUSEMOTION and dragging:
                name, tag, scale, view_rect = dragging
                mx, my = e.pos
                ix = int((mx - view_rect.x) / scale)
                iy = int((my - view_rect.y) / scale)
                results[name]["fist"][tag] = [ix, iy]

    pg.quit()

if __name__ == "__main__":
    run()
