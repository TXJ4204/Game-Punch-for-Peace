# screen_mode.py
import pygame as pg
from src.config import CFG
from src.widgets import Button

# ------------- Panel border (selected: thicker blue; unselected: dark gray) -------------
def draw_panel(surf, rect, *, highlight=False, bw_normal=3, bw_highlight=5):
    pg.draw.rect(surf, CFG.COL_PANEL_BG, rect, border_radius=16)
    if highlight:
        pg.draw.rect(surf, CFG.COL_PANEL_OUTLINE_HI, rect, width=bw_highlight, border_radius=16)
    else:
        pg.draw.rect(surf, CFG.COL_PANEL_OUTLINE,    rect, width=bw_normal,   border_radius=16)

# ------------- Icons (using your given proportions, unchanged) -------------
def icon_single(surf, box: pg.Rect, color):
    body_w = int(box.width * 0.22)
    body_h = int(box.height * 0.46)
    body = pg.Rect(0, 0, body_w, body_h)
    body.centerx = box.centerx
    body.bottom = box.bottom
    pg.draw.rect(surf, color, body, border_radius=10)
    r = int(body_w * 0.55)
    pg.draw.circle(surf, color, (body.centerx, body.top - int(r * 0.6)), r)

def icon_multi(surf, box: pg.Rect, color):
    w = int(box.width * 0.18)
    h = int(box.height * 0.38)
    gap = int(box.width * 0.06)
    left = pg.Rect(0, 0, w, h)
    right = pg.Rect(0, 0, w, h)
    left.right = box.centerx - gap // 2
    right.left  = box.centerx + gap // 2
    left.bottom = right.bottom = box.bottom
    for rct in (left, right):
        pg.draw.rect(surf, color, rct, border_radius=10)
        head_r = int(w * 0.55)
        pg.draw.circle(surf, color, (rct.centerx, rct.top - int(head_r * 0.6)), head_r)

# ------------- Crop + scale proportionally + bottom align (based on target height) -------------
def draw_icon_scaled(surf, baseline_y, center_x, draw_func, color, target_h, scale=1.0):
    tmp = pg.Surface((400, 400), pg.SRCALPHA)
    draw_func(tmp, pg.Rect(0, 0, 400, 400), color)
    bbox = tmp.get_bounding_rect(min_alpha=1)
    if bbox.w == 0 or bbox.h == 0:
        return
    img = tmp.subsurface(bbox).copy()
    th = max(1, int(target_h * scale))
    sc = th / bbox.h
    img = pg.transform.smoothscale(img, (max(1, int(img.get_width()*sc)),
                                         max(1, int(img.get_height()*sc))))
    rect = img.get_rect(centerx=center_x, bottom=baseline_y)
    surf.blit(img, rect)

# ------------- Confirm button (custom drawn, keeps Button event) -------------
def draw_confirm_button(surf, btn: Button, enabled: bool, border_w: int):
    r = btn.rect
    if enabled:
        fill, txt, bd = CFG.COL_CONFIRM_FILL, CFG.COL_CONFIRM_TEXT, CFG.COL_CONFIRM_BORDER
    else:
        fill, txt, bd = CFG.COL_CONFIRM_FILL_DIS, CFG.COL_CONFIRM_TEXT_DIS, CFG.COL_CONFIRM_BORDER_DIS
    pg.draw.rect(surf, fill, r, border_radius=12)
    pg.draw.rect(surf, bd,   r, width=border_w, border_radius=12)
    timg = btn.font.render(btn.label, True, txt)
    surf.blit(timg, timg.get_rect(center=r.center))

# ====================== Main Screen ======================
class ModeScreen:
    # —— Layout parameters (you can directly adjust values manually) —— #
    PANEL_TOP        = 120
    PANEL_MARGINS    = 80
    PANEL_GAP_X      = 50
    PANEL_BOTTOM_PAD = 160

    # Padding inside each card (all card content arranged relative to the “inner frame”)
    INNER_PAD        = 20         # ← inner padding of selection box
    HEAD_GAP         = 36         # ← distance between card title and inner frame top

    # Border thickness
    PANEL_BORDER_W    = 3         # unselected
    PANEL_BORDER_W_HI = 10        # selected
    CONFIRM_BORDER_W  = 2         # confirm button border

    # Icon and vertical spacing
    ICON_TARGET_H_RATIO    = 0.48       # icon target height = card height * ratio
    ICON_EXTRA_SCALE       = 1.00       # overall extra scaling
    ICON_BASELINE_GAP      = 120        # distance between icon bottom and confirm top (larger = higher icon)
    ICON_TO_TIP_GAP        = 60         # distance from icon to bottom “Coming soon”
    LAYOUTA_TO_CONFIRM_GAP = 60         # distance between layout A (two cards) and confirm button

    VERSION_TEXT           = "version 3.3"

    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # —— Layout A: two cards (outer frame for border, inner frame for content layout) —— #
        usable_w = self.W - self.PANEL_MARGINS * 2
        col_w = (usable_w - self.PANEL_GAP_X) // 2
        col_h = self.H - self.PANEL_TOP - self.PANEL_BOTTOM_PAD
        self.left  = pg.Rect(self.PANEL_MARGINS, self.PANEL_TOP, col_w, col_h)
        self.right = pg.Rect(self.PANEL_MARGINS + col_w + self.PANEL_GAP_X, self.PANEL_TOP, col_w, col_h)

        # Inner frame (leave uniform padding for content)
        self.left_inner  = self.left.inflate(-self.INNER_PAD*2, -self.INNER_PAD*2)
        self.right_inner = self.right.inflate(-self.INNER_PAD*2, -self.INNER_PAD*2)

        # Text
        self.title_img  = self.m.fonts["title"].render("Choose Mode", True, CFG.COL_TEXT)
        self.title_pos  = self.title_img.get_rect(center=(self.W // 2, 66))
        self.head_left  = self.m.fonts["big"].render("Single Player", True, CFG.COL_TEXT)
        self.head_right = self.m.fonts["big"].render("Multiplayer",  True, CFG.COL_TEXT)
        self.tip_img    = self.m.fonts["mid"].render("Coming soon",  True, CFG.COL_TIP)

        # Version number
        self.version_img = self.m.fonts["sml"].render(self.VERSION_TEXT, True, CFG.COL_TIP)
        self.version_pos = self.version_img.get_rect(bottom=self.H - 12, right=self.W - 12)

        # Confirm button (below layout A, centered)
        self._create_confirm()

        # Back
        self.btn_back = Button(pg.Rect(20, self.H - 64, 140, 40), "Back", self.m.fonts["mid"], True)

        # Selection state
        self.selected = "left"

        # Icon geometry (based on inner frame height for better visual sense)
        self.icon_target_h = int(self.left_inner.height * self.ICON_TARGET_H_RATIO)
        # Icon baseline: use confirm button top as reference, move up ICON_BASELINE_GAP; also consider padding for closer visual alignment
        self.icon_baseline = self.btn_confirm.rect.top - self.ICON_BASELINE_GAP - self.INNER_PAD // 2
        self.tip_pos = (self.right_inner.centerx, self.icon_baseline + self.ICON_TO_TIP_GAP)

    def _create_confirm(self):
        layoutA_bottom = max(self.left.bottom, self.right.bottom)
        f = self.m.fonts["mid"]
        r = pg.Rect(0, 0, 260, 68)            # fixed size for consistency
        r.center = (self.W // 2, layoutA_bottom + self.LAYOUTA_TO_CONFIRM_GAP)
        self.btn_confirm = Button(r, "Start Single PvE", f, enabled=True)

    # ---------------- Events ----------------
    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_LEFT:  self.selected = "left"
            if e.key == pg.K_RIGHT: self.selected = "right"
            if e.key in (pg.K_RETURN, pg.K_KP_ENTER):
                if self.btn_confirm.enabled and self.selected == "left":
                    self.m.goto("single_info")
            if e.key == pg.K_BACKSPACE:
                self.m.goto("home")

        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if self.left.collidepoint(e.pos):   self.selected = "left"
            elif self.right.collidepoint(e.pos): self.selected = "right"

        if self.btn_confirm.handle_event(e):
            if self.btn_confirm.enabled and self.selected == "left":
                self.m.goto("single_info")

        if self.btn_back.handle_event(e):
            self.m.goto("home")

    def update(self, dt):
        if self.selected == "left":
            self.btn_confirm.enabled = True
            self.btn_confirm.label = "Start Single PvE"
        else:
            self.btn_confirm.enabled = False
            self.btn_confirm.label = "Coming soon"

    # ---------------- Drawing ----------------
    def _draw_grid(self, s):
        COLS, ROWS = 16, 9
        cw, ch = self.W // COLS, self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                rect = pg.Rect(c * cw, r * ch, cw, ch)
                col = CFG.GRID_LIGHT if (c + r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(s, col, rect)

    def draw(self):
        s = self.m.screen
        s.fill(CFG.BG)
        self._draw_grid(s)

        # Page title
        s.blit(self.title_img, self.title_pos)

        # Outer frame border (only border highlight)
        draw_panel(s, self.left,
                   highlight=(self.selected == "left"),
                   bw_normal=self.PANEL_BORDER_W,
                   bw_highlight=self.PANEL_BORDER_W_HI)
        draw_panel(s, self.right,
                   highlight=(self.selected == "right"),
                   bw_normal=self.PANEL_BORDER_W,
                   bw_highlight=self.PANEL_BORDER_W_HI)

        # Card titles (relative to “inner frame top” + HEAD_GAP)
        s.blit(self.head_left,  self.head_left.get_rect(center=(self.left_inner.centerx,
                                                                self.left_inner.top + self.HEAD_GAP)))
        s.blit(self.head_right, self.head_right.get_rect(center=(self.right_inner.centerx,
                                                                 self.right_inner.top + self.HEAD_GAP)))

        # Icons (equal height + bottom alignment; use “inner frame center x”, shared baseline)
        draw_icon_scaled(s, self.icon_baseline, self.left_inner.centerx,
                         icon_single, CFG.COL_ICON_SINGLE, self.icon_target_h, self.ICON_EXTRA_SCALE)
        draw_icon_scaled(s, self.icon_baseline, self.right_inner.centerx,
                         icon_multi,  CFG.COL_ICON_MULTI,  self.icon_target_h, self.ICON_EXTRA_SCALE)

        # “Coming soon” on the right card
        s.blit(self.tip_img, self.tip_img.get_rect(center=self.tip_pos))

        # Confirm (custom drawn, thick border)
        draw_confirm_button(s, self.btn_confirm, self.btn_confirm.enabled, self.CONFIRM_BORDER_W)

        # Back
        self.btn_back.draw(s)

        # Version number
        s.blit(self.version_img, self.version_pos)
