# screen_mode.py
import pygame as pg
from src.config import CFG
from src.widgets import Button

# ====================== 基础绘制 ======================
def draw_panel(surf, rect, *, highlight=False):
    """模式卡片；选中高亮（背景变蓝、白色描边）"""
    fill_normal = (55, 60, 70)
    outline_normal = (25, 28, 34)
    fill_hi = (70, 130, 200)
    outline_hi = (240, 245, 255)

    fill = fill_hi if highlight else fill_normal
    outline = outline_hi if highlight else outline_normal
    border_w = 3 if highlight else 2

    pg.draw.rect(surf, fill, rect, border_radius=16)
    pg.draw.rect(surf, outline, rect, width=border_w, border_radius=16)

# 你提供的原始图标绘制（比例不改）
def icon_single(surf, box: pg.Rect, color=(80, 160, 240)):
    body_w = int(box.width * 0.22)
    body_h = int(box.height * 0.46)
    body = pg.Rect(0, 0, body_w, body_h)
    body.centerx = box.centerx
    body.bottom = box.bottom
    pg.draw.rect(surf, color, body, border_radius=10)
    r = int(body_w * 0.55)
    pg.draw.circle(surf, color, (body.centerx, body.top - int(r * 0.6)), r)

def icon_multi(surf, box: pg.Rect, color=(150, 150, 160)):
    w = int(box.width * 0.18)
    h = int(box.height * 0.38)
    gap = int(box.width * 0.06)
    left = pg.Rect(0, 0, w, h)
    right = pg.Rect(0, 0, w, h)
    left.right = box.centerx - gap // 2
    right.left = box.centerx + gap // 2
    left.bottom = right.bottom = box.bottom
    for rct in (left, right):
        pg.draw.rect(surf, color, rct, border_radius=10)
        head_r = int(w * 0.55)
        pg.draw.circle(surf, color, (rct.centerx, rct.top - int(head_r * 0.6)), head_r)

# 将“整体 a”裁剪并等比缩放到同高、底对齐
def draw_icon_scaled(target: pg.Surface, baseline_y: int, center_x: int,
                     draw_func, color, target_height: int):
    temp = pg.Surface((400, 400), pg.SRCALPHA)
    temp.fill((0, 0, 0, 0))
    draw_func(temp, pg.Rect(0, 0, 400, 400), color)
    bbox = temp.get_bounding_rect(min_alpha=1)
    if bbox.width == 0 or bbox.height == 0:
        return
    img = temp.subsurface(bbox).copy()
    scale = target_height / bbox.height
    new_size = (max(1, int(img.get_width() * scale)),
                max(1, int(img.get_height() * scale)))
    img = pg.transform.smoothscale(img, new_size)
    dst = img.get_rect(centerx=center_x, bottom=baseline_y)
    target.blit(img, dst)

# ====================== 主界面 ======================
class ModeScreen:
    # ---- 可调布局参数 ----
    PANEL_TOP = 120
    PANEL_MARGINS = 80
    PANEL_GAP_X = 50
    PANEL_BOTTOM_PAD = 160

    ICON_TARGET_H_RATIO = 0.48  # 图标目标高度占卡片高度的比例
    ICON_BASELINE_GAP = 72      # 图标底边距“按钮顶”的距离
    GAP_ICON_TO_TIP = 16

    # 确认按钮
    CONFIRM_PAD_X = 22
    CONFIRM_PAD_Y = 12

    TIP_COLOR = (190, 190, 195)
    DARK_ICON = (55, 60, 70)      # 选中时图标反转成深灰（原面板色）
    BLUE_SINGLE = (80, 160, 240)  # 单人默认蓝
    GREY_MULTI = (150, 150, 160)  # 双人默认灰

    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # 面板区域（布局 A）
        usable_w = self.W - self.PANEL_MARGINS * 2
        col_w = (usable_w - self.PANEL_GAP_X) // 2
        col_h = self.H - self.PANEL_TOP - self.PANEL_BOTTOM_PAD
        self.left = pg.Rect(self.PANEL_MARGINS, self.PANEL_TOP, col_w, col_h)
        self.right = pg.Rect(self.PANEL_MARGINS + col_w + self.PANEL_GAP_X,
                             self.PANEL_TOP, col_w, col_h)

        # 标题
        self.title_img = self.m.fonts["title"].render("Choose Mode", True, CFG.TEXT)
        self.title_pos = self.title_img.get_rect(center=(self.W // 2, 66))

        # 文案
        self.head_left  = self.m.fonts["big"].render("Single Player", True, CFG.TEXT)
        self.head_right = self.m.fonts["big"].render("Multiplayer",  True, CFG.TEXT)
        self.tip_img    = self.m.fonts["mid"].render("Coming soon",  True, self.TIP_COLOR)

        # 图标尺寸几何
        self.icon_target_h = int(col_h * self.ICON_TARGET_H_RATIO)
        # 基线以“布局 A 的按钮顶”为参考；我们稍后创建 Confirm 后再赋值
        self.icon_baseline = None

        # 统一确认按钮（在布局 A 下方）
        self._create_confirm_button()

        # 版本号
        self.version_img = self.m.fonts["sml"].render("version 3.2", True, (200, 200, 205))
        self.version_pos = self.version_img.get_rect(bottom=self.H - 12, right=self.W - 12)

        # 选择状态
        self.selected = "left"  # "left" or "right"

    def _create_confirm_button(self):
        # 布局 A 的下边界：取左右面板的最大 bottom
        layoutA_bottom = max(self.left.bottom, self.right.bottom)
        # Confirm 按钮位置：在布局 A 的正下方居中
        label = "Start Single PvE"
        f = self.m.fonts["mid"]
        tw, th = f.size(label)
        w = tw + self.CONFIRM_PAD_X * 2
        h = th + self.CONFIRM_PAD_Y * 2
        r = pg.Rect(0, 0, w, h)
        r.center = (self.W // 2, layoutA_bottom + 48)
        self.btn_confirm = Button(r, label, f, enabled=True)

        # 确认 icon 基线（图标底边）= 卡片内部按钮“理论顶”：
        # 这里以确认按钮的 top 作为参考，往上留 ICON_BASELINE_GAP
        self.icon_baseline = self.btn_confirm.rect.top - self.ICON_BASELINE_GAP
        self.tip_pos = (self.right.centerx, self.icon_baseline + self.GAP_ICON_TO_TIP)

    # =============== 事件 ===============
    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_LEFT:
                self.selected = "left"
            elif e.key == pg.K_RIGHT:
                self.selected = "right"
            elif e.key in (pg.K_RETURN, pg.K_KP_ENTER):
                # 只有 Confirm 可用时才进入
                if self.btn_confirm.enabled and self.selected == "left":
                    self.m.goto("single_info")
            elif e.key == pg.K_BACKSPACE:
                self.m.goto("home")

        # 面板点击只改变选择，不跳转
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if self.left.collidepoint(e.pos):
                self.selected = "left"
            elif self.right.collidepoint(e.pos):
                self.selected = "right"

        # Confirm 按钮
        if self.btn_confirm.handle_event(e):
            if self.btn_confirm.enabled and self.selected == "left":
                self.m.goto("single_info")

    def update(self, dt):
        # 动态更新 Confirm 按钮的文案和启用状态
        if self.selected == "left":
            self.btn_confirm.enabled = True
            self.btn_confirm.label = "Start Single PvE"
        else:
            self.btn_confirm.enabled = False
            self.btn_confirm.label = "Coming soon"

    # =============== 绘制 ===============
    def _draw_grid(self, s: pg.Surface):
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

        # 标题
        s.blit(self.title_img, self.title_pos)

        # 面板（选中高亮 + 图标颜色反转）
        left_hi  = (self.selected == "left")
        right_hi = (self.selected == "right")
        draw_panel(s, self.left,  highlight=left_hi)
        draw_panel(s, self.right, highlight=right_hi)

        # 面板标题
        s.blit(self.head_left,  self.head_left.get_rect(center=(self.left.centerx,  self.left.top  + 28)))
        s.blit(self.head_right, self.head_right.get_rect(center=(self.right.centerx, self.right.top + 28)))

        # 图标：未选中=默认颜色；选中=深灰（反转）
        left_icon_col  = self.DARK_ICON if left_hi  else self.BLUE_SINGLE
        right_icon_col = self.DARK_ICON if right_hi else self.GREY_MULTI

        draw_icon_scaled(s, self.icon_baseline, self.left.centerx,  icon_single, left_icon_col,  self.icon_target_h)
        draw_icon_scaled(s, self.icon_baseline, self.right.centerx, icon_multi,  right_icon_col, self.icon_target_h)

        # 右侧“Coming soon”
        tip_img = self.tip_img
        s.blit(tip_img, tip_img.get_rect(center=self.tip_pos))

        # Confirm 按钮（启用=蓝底白字；禁用=灰底黑字）
        # 复用 Button 本身的绘制，但我们改一下它的配色：在 widgets.Button 里是蓝/灰
        # 这里直接绘制覆盖：禁用态我们重画一层
        self.btn_confirm.draw(s)
        if not self.btn_confirm.enabled:
            # 覆盖为灰底黑字
            r = self.btn_confirm.rect
            pg.draw.rect(s, (120, 120, 125), r, border_radius=12)
            pg.draw.rect(s, (35, 35, 38), r, width=2, border_radius=12)
            txt = self.m.fonts["mid"].render(self.btn_confirm.label, True, (15, 15, 18))
            s.blit(txt, txt.get_rect(center=r.center))

        # 版本号（右下角）
        s.blit(self.version_img, self.version_pos)
