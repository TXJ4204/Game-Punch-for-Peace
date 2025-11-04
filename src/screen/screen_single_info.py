# src/screen/screen_single_info.py
from pathlib import Path
import pygame as pg
from src.config import CFG
from src.widgets import Button


class L:
    # —— Outer layout —— #
    PANEL_TOP        = 120
    PANEL_MARGINS    = 80
    PANEL_GAP_X      = 50
    PANEL_BOTTOM_PAD = 160
    INNER_PAD        = 22
    LEFT_RIGHT_RATIO = (1, 2.5)

    PANEL_RADIUS     = 14
    PANEL_BORDER_W   = 3

    # Page top-left small title
    PAGE_TITLE_POS   = (28, 24)
    PAGE_TITLE_FONT  = "mid"

    # —— Left card (title + ultra-minimal image knob) —— #
    LEFT_TITLE_TEXT  = "Human"
    LEFT_TITLE_GAP   = 0          # distance from title to inner frame top
    TITLE_TO_IMG_GAP = 0          # vertical spacing between title and image area

    IMG_REL_PATH     = "assets/animation/people01.png"
    IMG_SCALE        = 0.5        # your target scaling ratio
    IMG_GAP_TOP      = 0           # extra: additional top padding for image area (tweak yourself)
    IMG_GAP_BOTTOM   = 24          # extra: bottom padding from image to card bottom (tweak yourself)
    IMG_X_OFFSET     = 10           # horizontal offset (+right / -left)
    IMG_Y_OFFSET     = -20           # vertical offset (+down / -up)

    # —— Right card (instructions) —— #
    HOWTO_TITLE_FONT = "big"
    HOWTO_TITLE_GAP  = 38
    COL_GUTTER       = 40
    COL_TOP_PAD      = 18
    COL_SIDE_PAD     = 20
    HEADING_FONT     = "mid"
    BODY_FONT        = "sml"
    LINE_SPACING     = 1.20
    BULLET_GAP       = 6

    # —— Bottom buttons —— #
    ENTER_SIZE       = (300, 58)
    BACK_POS         = (24, -64)


def draw_panel(surf, rect):
    pg.draw.rect(surf, CFG.COL_PANEL_BG, rect, border_radius=L.PANEL_RADIUS)
    pg.draw.rect(surf, CFG.COL_PANEL_OUTLINE, rect, width=L.PANEL_BORDER_W, border_radius=L.PANEL_RADIUS)


def wrap_text(text, font, max_width):
    words, lines, cur = text.split(' '), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.size(t)[0] <= max_width:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


class SingleInfoScreen:
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # —— Outer frames: left:right —— #
        usable_w = self.W - L.PANEL_MARGINS * 2
        lr = sum(L.LEFT_RIGHT_RATIO)
        unit = (usable_w - L.PANEL_GAP_X) / lr
        left_w  = int(unit * L.LEFT_RIGHT_RATIO[0])
        right_w = int(unit * L.LEFT_RIGHT_RATIO[1])
        col_h   = self.H - L.PANEL_TOP - L.PANEL_BOTTOM_PAD

        self.left_outer  = pg.Rect(L.PANEL_MARGINS, L.PANEL_TOP, left_w, col_h)
        self.right_outer = pg.Rect(L.PANEL_MARGINS + left_w + L.PANEL_GAP_X, L.PANEL_TOP, right_w, col_h)

        self.left_inner  = self.left_outer.inflate(-L.INNER_PAD*2, -L.INNER_PAD*2)
        self.right_inner = self.right_outer.inflate(-L.INNER_PAD*2, -L.INNER_PAD*2)

        # Page top-left small title
        self.page_title = self.m.fonts[L.PAGE_TITLE_FONT].render("Single Player", True, CFG.COL_TEXT)

        # Left card title
        self.left_head  = self.m.fonts["big"].render(L.LEFT_TITLE_TEXT, True, CFG.COL_TEXT)

        # Right card external title
        self.howto_head = self.m.fonts[L.HOWTO_TITLE_FONT].render("How to Play", True, CFG.COL_TEXT)

        # Two-column text
        self.rules_heading = "# Game Rules #"
        self.rules_lines = [
            "Kangaroo jumps 2 steps fast but tires quickly.",
            "Human walks 1 step and can only defend.",
            "When Roo is within 1 tile, it punches automatically.",
            "Round lasts 3 min; 2 hearts; lose half when knocked down.",
            "Out of stamina → lose.",
        ]
        self.core_heading = "# Core Mechanics #"
        self.core_lines = [
            "Duel of walking vs jumping.",
            "Block reduces damage but drains both sides.",
            "Roo’s jump consumes extra stamina.",
            "Keep >1 tile to dodge punches.",
            "[Arrow] Move   [Space] Block",
        ]

        # Image
        try:
            here = Path(__file__).resolve().parent
            img_path = (here.parent.parent / L.IMG_REL_PATH).resolve()
            self._img = pg.image.load(str(img_path)).convert_alpha()
        except Exception:
            self._img = None

        # Buttons
        ew, eh = L.ENTER_SIZE
        self.btn_enter = Button(pg.Rect(self.W//2 - ew//2, self.H - 130, ew, eh), "Enter", self.m.fonts["big"])
        bx, by = L.BACK_POS
        self.btn_back  = Button(pg.Rect(bx, self.H + by, 140, 40), "Back", self.m.fonts["mid"])

        # —— Precompute the “available height” and placement baseline (bottom) for the left card image —— #
        title_h   = self.left_head.get_height()
        top_limit = self.left_inner.top + L.LEFT_TITLE_GAP + title_h + L.TITLE_TO_IMG_GAP + L.IMG_GAP_TOP
        bot_limit = self.left_inner.bottom - L.IMG_GAP_BOTTOM
        self.img_area_h = max(1, bot_limit - top_limit)
        self.img_bottom = bot_limit                                # bottom alignment baseline
        self.img_centerx = self.left_inner.centerx                 # horizontal centering baseline

    # Background grid
    def _draw_grid(self, s):
        COLS, ROWS = 16, 9
        cw, ch = self.W // COLS, self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                col = CFG.GRID_LIGHT if (r + c) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(s, col, (c*cw, r*ch, cw, ch))

    # —— Minimal: scale according to your IMG_SCALE; if it would exceed available height, clamp to just not exceed —— #
    def _blit_image_simple(self, surf, img):
        if not img:
            return
        iw, ih = img.get_size()
        # first use your provided scale
        scale = L.IMG_SCALE
        # if too tall, apply a safeguard shrink to avoid cropping (simple and safe)
        max_scale = self.img_area_h / ih
        if scale > max_scale:
            scale = max_scale

        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        simg = pg.transform.smoothscale(img, (nw, nh))

        dst = simg.get_rect(centerx=self.img_centerx + L.IMG_X_OFFSET,
                            bottom=self.img_bottom + L.IMG_Y_OFFSET)
        surf.blit(simg, dst)

    def handle_event(self, e):
        if self.btn_enter.handle_event(e) or (e.type == pg.KEYDOWN and e.key == pg.K_RETURN):
            self.m.goto("game")
        if self.btn_back.handle_event(e) or (e.type == pg.KEYDOWN and e.key == pg.K_BACKSPACE):
            self.m.goto("mode")

    def update(self, dt):
        pass

    def draw(self):
        s = self.m.screen
        s.fill(CFG.BG)
        self._draw_grid(s)

        # Page top-left small title
        s.blit(self.page_title, self.page_title.get_rect(topleft=L.PAGE_TITLE_POS))

        # Outer frames
        draw_panel(s, self.left_outer)
        draw_panel(s, self.right_outer)

        # “How to Play” above the right outer frame
        howto_pos = self.howto_head.get_rect(
            center=(self.right_outer.centerx, self.right_outer.top - L.HOWTO_TITLE_GAP)
        )
        s.blit(self.howto_head, howto_pos)

        # Left card title: centered at top
        s.blit(self.left_head, self.left_head.get_rect(
            midtop=(self.left_inner.centerx, self.left_inner.top + L.LEFT_TITLE_GAP))
        )

        # Left card image: minimal scaling + bottom alignment + offsets
        self._blit_image_simple(s, self._img)

        # Right card two-column content
        font_head = self.m.fonts[L.HEADING_FONT]
        font_body = self.m.fonts[L.BODY_FONT]
        line_h    = int(font_body.get_linesize() * L.LINE_SPACING)

        content   = self.right_inner.inflate(-L.COL_SIDE_PAD*2, -L.COL_TOP_PAD*2)
        col_w     = (content.width - L.COL_GUTTER)//2
        col_left  = pg.Rect(content.left, content.top, col_w, content.height)
        col_right = pg.Rect(content.left + col_w + L.COL_GUTTER, content.top, col_w, content.height)

        def draw_column(rect, heading_text, items):
            y = rect.top
            # Simple “fake bold” via overdraw
            head_img  = font_head.render(heading_text, True, CFG.COL_TEXT)
            rect_head = head_img.get_rect(topleft=(rect.left, y))
            for dx, dy in [(0,0),(1,0),(0,1),(1,1)]:
                s.blit(head_img, rect_head.move(dx, dy))
            y += head_img.get_height() + 12

            wrap_w = rect.width
            for t in items:
                lines = wrap_text(t, font_body, wrap_w)
                if lines:
                    dot = font_body.render("• ", True, CFG.COL_TEXT)
                    s.blit(dot, (rect.left, y))
                    x0 = rect.left + dot.get_width()
                    s.blit(font_body.render(lines[0], True, CFG.COL_TEXT), (x0, y))
                    y += line_h
                    for cont in lines[1:]:
                        s.blit(font_body.render(cont, True, CFG.COL_TEXT), (x0, y))
                        y += line_h
                y += L.BULLET_GAP

        draw_column(col_left,  self.rules_heading, self.rules_lines)
        draw_column(col_right, self.core_heading,  self.core_lines)

        # Buttons
        self.btn_back.draw(s)
        self.btn_enter.draw(s)
