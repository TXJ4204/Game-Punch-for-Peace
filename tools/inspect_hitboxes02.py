# tools/inspect_hitboxes02.py
import json
import sys
from pathlib import Path

import pygame as pg

# --------- paths ---------
ROOT   = Path(__file__).resolve().parents[1]     # project root
ASSETS = ROOT / "assets" / "animation"
OUT_JS = ASSETS / "hitbox_suggestion.json"

# --------- view layout ---------
COLS, ROWS = 3, 3               # up to 9 thumbs per page
CELL_W, CELL_H = 420, 260       # per-slot size in window
PADDING = 24
TITLE_H = 52

WIN_W = COLS * CELL_W + PADDING * 2
WIN_H = ROWS * CELL_H + PADDING * 2 + TITLE_H

BG_DARK   = (20, 22, 26)
INK       = (235, 235, 235)
YELLOW    = (250, 210, 60)      # tight bbox
CYAN      = (220,120,255)      # mask outline
GREEN     = (60, 220, 160)      # suggested hit rect
RED       = (240, 90, 90)       # fist point

# Alpha threshold: ignore semi-transparent glow
ALPHA_THR = 180  # try 160~220 if needed

# Hitbox shrink factors (relative to tight bbox) as a starting guess
SHRINK_X = 0.10
SHRINK_Y = 0.06

FONT_NAME_CAND = [
    "Microsoft YaHei UI","Microsoft YaHei","Segoe UI","Noto Sans CJK SC",
    "Source Han Sans SC","Arial Unicode MS",None
]

def pick_font(size):
    for n in FONT_NAME_CAND:
        try:
            f = pg.font.SysFont(n, size)
            _ = f.render("Aa", True, (255,255,255))
            return f
        except Exception:
            continue
    return pg.font.SysFont(None, size)

def list_pngs():
    # auto list (guarantees roo03.png included)
    return sorted([p for p in ASSETS.glob("*.png")])

def blit_center(surf, img, rect):
    img_r = img.get_rect()
    img_r.center = rect.center
    surf.blit(img, img_r.topleft)
    return img_r

def draw_rect(surf, color, rect, width=2):
    pg.draw.rect(surf, color, rect, width)

def draw_cross(surf, color, pos, size=6, width=2):
    x,y = pos
    pg.draw.line(surf, color, (x-size,y), (x+size,y), width)
    pg.draw.line(surf, color, (x,y-size), (x,y+size), width)

def mask_tight_bbox(img):
    m = pg.mask.from_surface(img, ALPHA_THR)
    rects = m.get_bounding_rects()
    if not rects:
        return None, None
    tight = rects[0]  # bounding rect of mask
    outline = m.outline()
    return tight, outline

def rel_from(inner: pg.Rect, outer: pg.Rect):
    """return [x,y,w,h] relative to outer (0..1)"""
    return [
        (inner.x - outer.x) / outer.w,
        (inner.y - outer.y) / outer.h,
        inner.w / outer.w,
        inner.h / outer.h
    ]

def abs_from(rel, outer: pg.Rect):
    x = outer.x + rel[0]*outer.w
    y = outer.y + rel[1]*outer.h
    w = rel[2]*outer.w
    h = rel[3]*outer.h
    return pg.Rect(int(x), int(y), int(w), int(h))

def clamp01(v):
    return max(0.0, min(1.0, float(v)))

def run():
    pg.init(); pg.font.init()
    screen = pg.display.set_mode((WIN_W, WIN_H))
    pg.display.set_caption("Inspect Hitboxes")
    f_title = pick_font(26)
    f_small = pick_font(18)

    names = list_pngs()
    if not names:
        print("No PNG found under assets/images")
        pg.quit(); sys.exit(1)

    # preload
    images = {p.name: pg.image.load(p.as_posix()).convert_alpha() for p in names}

    results = {}
    clock = pg.time.Clock()
    page = 0
    per_page = COLS*ROWS

    while True:
        clock.tick(60)
        screen.fill(BG_DARK)

        # header
        title = f"assets/images  |  {len(names)} images  |  Page {page+1}/{(len(names)-1)//per_page+1}   (S=save JSON, ←/→ page, Esc=quit)"
        img = f_title.render(title, True, INK)
        screen.blit(img, (PADDING, PADDING))

        # grid rect
        grid = pg.Rect(PADDING, PADDING+TITLE_H, WIN_W-2*PADDING, WIN_H-2*PADDING-TITLE_H)

        # draw items
        view_items = names[page*per_page:(page+1)*per_page]
        for idx, path in enumerate(view_items):
            cx = idx % COLS
            cy = idx // COLS
            cell = pg.Rect(
                grid.x + cx*CELL_W,
                grid.y + cy*CELL_H,
                CELL_W, CELL_H
            )

            # mini canvas for each slot
            slot = cell.inflate(-32, -32)
            name = path.name
            img_surf = images[name]

            # scale-down big sprites to fit (keep ratio, but we only need target rect)
            scale = min(slot.w/img_surf.get_width(), slot.h/img_surf.get_height(), 1.0)
            view_w = int(img_surf.get_width()*scale)
            view_h = int(img_surf.get_height()*scale)
            view_img = pg.transform.smoothscale(img_surf, (view_w, view_h))
            view_rect = view_img.get_rect(center=slot.center)
            screen.blit(view_img, view_rect.topleft)

            # filename
            lab = f_small.render(name, True, INK)
            screen.blit(lab, (slot.x, slot.y-22))

            # tight bbox in image coords (unscaled), then map into view_rect
            tight, outline = mask_tight_bbox(img_surf)
            if tight:
                # map tight -> view coords
                sx = view_rect.w / img_surf.get_width()
                sy = view_rect.h / img_surf.get_height()
                tight_view = pg.Rect(
                    int(view_rect.x + tight.x * sx),
                    int(view_rect.y + tight.y * sy),
                    int(tight.w * sx),
                    int(tight.h * sy)
                )
                draw_rect(screen, YELLOW, tight_view, 2)

                # suggest hit-rect: shrink inside tight
                hit_view = tight_view.inflate(
                    -int(tight_view.w*SHRINK_X*2),
                    -int(tight_view.h*SHRINK_Y*2)
                )
                draw_rect(screen, GREEN, hit_view, 2)

                # outline (cyan) from mask
                if outline and len(outline) > 2:
                    pts = [(int(view_rect.x + x*sx), int(view_rect.y + y*sy)) for (x,y) in outline]
                    try:
                        pg.draw.lines(screen, CYAN, True, pts, 2)
                    except:
                        pass

                # default fist points (relative) if missing
                if name not in results:
                    # fist near front glove: right-facing assume right side,
                    # left-facing mirror horizontally
                    # We'll store RELATIVE to hit_view
                    fist_r = (0.82, 0.40)   # x,y in 0..1 of hit rect
                    fist_l = (1.0 - fist_r[0], fist_r[1])
                    results[name] = {
                        "tight_bbox_rel": rel_from(tight_view, view_rect),
                        "hit_rect_rel":   rel_from(hit_view,   view_rect),
                        "fist_rel": {
                            "right": [fist_r[0], fist_r[1]],
                            "left":  [fist_l[0], fist_l[1]]
                        }
                    }

                # draw fists
                meta = results[name]
                hit_rect = abs_from(meta["hit_rect_rel"], view_rect)
                for side in ("left","right"):
                    fx = clamp01(meta["fist_rel"][side][0])
                    fy = clamp01(meta["fist_rel"][side][1])
                    px = int(hit_rect.x + fx*hit_rect.w)
                    py = int(hit_rect.y + fy*hit_rect.h)
                    draw_cross(screen, RED, (px,py), size=6, width=2)

        pg.display.flip()

        # events
        for e in pg.event.get():
            if e.type == pg.QUIT:
                pg.quit(); sys.exit()
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    pg.quit(); sys.exit()
                if e.key == pg.K_s:
                    # save JSON
                    OUT_JS.write_text(json.dumps(results, indent=2, ensure_ascii=False))
                    print(f"[saved] {OUT_JS}")
                if e.key == pg.K_RIGHT:
                    if (page+1)*per_page < len(names):
                        page += 1
                if e.key == pg.K_LEFT:
                    if page > 0:
                        page -= 1

if __name__ == "__main__":
    run()
