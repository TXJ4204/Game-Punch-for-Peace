# src/screen/screen_single_info.py
from pathlib import Path
import pygame as pg
from src.config import CFG
from src.widgets import Button


class L:
    # —— 整体布局 —— #
    PANEL_TOP        = 120
    PANEL_MARGINS    = 80
    PANEL_GAP_X      = 50
    PANEL_BOTTOM_PAD = 160
    INNER_PAD        = 22

    # 左右比例：左:右 = 1:2
    LEFT_RIGHT_RATIO = (1, 2.5)

    # 边框
    PANEL_RADIUS     = 14
    PANEL_BORDER_W   = 3

    # 页面左上“Single Player”小标题
    PAGE_TITLE_POS   = (28, 24)   # topleft
    PAGE_TITLE_FONT  = "mid"      # 用较小字号

    # 左卡内部
    LEFT_TITLE_GAP   = 18          # 左卡 Mode 标题离内框顶的距离
    IMG_REL_PATH     = "assets/animation/people01.png"
    IMG_MAX_H_RATIO  = 0.58        # 左卡内框高的比例
    IMG_SCALE        = 1.00
    IMG_BASELINE_GAP = 120         # 人物底边距 Enter 顶部的距离（越大越靠上）

    # 右卡标题（放在外框外！）
    HOWTO_TITLE_FONT = "big"
    HOWTO_TITLE_GAP  = 38          # 标题到底下外框顶的距离

    # 右卡两列
    COL_GUTTER       = 40          # 列间距
    COL_TOP_PAD      = 18          # 内容区顶部内边距（inside panel）
    COL_SIDE_PAD     = 20          # 内容左右内边距
    HEADING_FONT     = "mid"       # “# Game Rules #” 这行
    BODY_FONT        = "sml"       # 子弹行
    LINE_SPACING     = 1.20        # 行距
    BULLET_GAP       = 6           # 同一段落相邻子弹的额外间距

    # 按钮
    ENTER_SIZE       = (300, 58)
    BACK_POS         = (24, -64)


def draw_panel(surf, rect):
    pg.draw.rect(surf, CFG.COL_PANEL_BG, rect, border_radius=L.PANEL_RADIUS)
    pg.draw.rect(surf, CFG.COL_PANEL_OUTLINE, rect, width=L.PANEL_BORDER_W, border_radius=L.PANEL_RADIUS)


def wrap_text(text, font, max_width):
    words, lines, cur = text.split(' '), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_width:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


class SingleInfoScreen:
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # —— 外框：左:右=1:2 —— #
        usable_w = self.W - L.PANEL_MARGINS * 2
        left_r, right_r = L.LEFT_RIGHT_RATIO
        w_unit = (usable_w - L.PANEL_GAP_X) / (left_r + right_r)
        left_w  = int(w_unit * left_r)
        right_w = int(w_unit * right_r)
        col_h   = self.H - L.PANEL_TOP - L.PANEL_BOTTOM_PAD

        self.left_outer  = pg.Rect(L.PANEL_MARGINS, L.PANEL_TOP, left_w, col_h)
        self.right_outer = pg.Rect(L.PANEL_MARGINS + left_w + L.PANEL_GAP_X, L.PANEL_TOP, right_w, col_h)

        # 内框（内容用）
        self.left_inner  = self.left_outer.inflate(-L.INNER_PAD * 2, -L.INNER_PAD * 2)
        self.right_inner = self.right_outer.inflate(-L.INNER_PAD * 2, -L.INNER_PAD * 2)

        # 页面左上小标题
        self.page_title = self.m.fonts[L.PAGE_TITLE_FONT].render("Single Player", True, CFG.COL_TEXT)

        # 左卡标题
        self.left_head  = self.m.fonts["big"].render("Mode", True, CFG.COL_TEXT)

        # 右卡外部标题
        self.howto_head = self.m.fonts[L.HOWTO_TITLE_FONT].render("How to Play", True, CFG.COL_TEXT)

        # 两列文本
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

        # 图片
        try:
            here = Path(__file__).resolve().parent
            img_path = (here.parent.parent / L.IMG_REL_PATH).resolve()
            self._img = pg.image.load(str(img_path)).convert_alpha()
        except Exception:
            self._img = None

        # 按钮
        ew, eh = L.ENTER_SIZE
        self.btn_enter = Button(pg.Rect(self.W // 2 - ew // 2, self.H - 84, ew, eh),
                                "Enter", self.m.fonts["big"])
        bx, by = L.BACK_POS
        self.btn_back = Button(pg.Rect(24, self.H + by, 140, 40),
                               "Back", self.m.fonts["mid"])

        # 左图几何
        self.img_target_h = int(self.left_inner.height * L.IMG_MAX_H_RATIO)
        self.img_baseline = self.btn_enter.rect.top - L.IMG_BASELINE_GAP

    def _draw_grid(self, s):
        COLS, ROWS = 16, 9
        cw, ch = self.W // COLS, self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                col = CFG.GRID_LIGHT if (r + c) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(s, col, (c * cw, r * ch, cw, ch))

    def _draw_img_bottom(self, surf, img, cx, baseline_y, target_h, scale=1.0):
        if not img: return
        w, h = img.get_size()
        th = int(target_h * scale)
        sc = th / h
        simg = pg.transform.smoothscale(img, (int(w * sc), th))
        surf.blit(simg, simg.get_rect(centerx=cx, bottom=baseline_y))

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

        # 页面左上小标题
        s.blit(self.page_title, self.page_title.get_rect(topleft=L.PAGE_TITLE_POS))

        # 外框
        draw_panel(s, self.left_outer)
        draw_panel(s, self.right_outer)

        # 右侧 “How to Play” 在外框上方
        howto_pos = self.howto_head.get_rect(center=(self.right_outer.centerx,
                                                     self.right_outer.top - L.HOWTO_TITLE_GAP))
        s.blit(self.howto_head, howto_pos)

        # 左卡标题：放左上角
        s.blit(self.left_head, self.left_head.get_rect(
            topleft=(self.left_inner.left + L.INNER_PAD, self.left_inner.top + L.LEFT_TITLE_GAP))
        )
        # 左卡人物
        self._draw_img_bottom(
            s, self._img,
            self.left_inner.centerx,
            self.img_baseline,
            self.img_target_h,
            L.IMG_SCALE
        )

        # 右卡两列内容排版
        font_head = self.m.fonts[L.HEADING_FONT]
        font_body = self.m.fonts[L.BODY_FONT]
        line_h = int(font_body.get_linesize() * L.LINE_SPACING)

        # 列区域
        content = self.right_inner.inflate(-L.COL_SIDE_PAD * 2, -L.COL_TOP_PAD * 2)
        col_w = (content.width - L.COL_GUTTER) // 2
        col_left  = pg.Rect(content.left,  content.top, col_w, content.height)
        col_right = pg.Rect(content.left + col_w + L.COL_GUTTER, content.top, col_w, content.height)

        # 画一列
        def draw_column(rect, heading_text, items):
            y = rect.top
            # heading
            head_img = font_head.render(heading_text, True, CFG.COL_TEXT)
            s.blit(head_img, head_img.get_rect(topleft=(rect.left, y)))
            y += head_img.get_height() + 12
            # bullets
            wrap_w = rect.width
            for t in items:
                lines = wrap_text(t, font_body, wrap_w)
                if lines:
                    # dot + first line
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

        # 按钮
        self.btn_back.draw(s)
        self.btn_enter.draw(s)
