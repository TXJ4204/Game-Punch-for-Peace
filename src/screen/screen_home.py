# screen_home.py
import pygame as pg
from src.config import CFG
from src.widgets import Button

class HomeScreen:
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # ---- 文案 ----
        self.title    = "PUNCH for PEACE"
        self.subtitle = "- human VS kangaroo -"

        # ---- 字体：标题更大 + 加粗 ----
        # 若你的 Font 支持 set_bold，则直接加粗；否则保持原字体
        self.title_font = self.m.fonts.get("title", self.m.fonts["big"])
        try:
            self.title_font.set_bold(True)   # 有些字体可用
        except Exception:
            pass

        # 标题再放大一点（在没有独立大号字体时）
        self.title_font_big = self.title_font
        try:
            # 尝试用系统字体生成更大的标题字体
            size = int(self.title_font.get_height() * 2)
            self.title_font_big = pg.font.SysFont(None, size, bold=True)
        except Exception:
            pass

        self.sub_font = self.m.fonts.get("subtitle", self.m.fonts.get("big"))
        self.sub_col  = (170, 170, 170)

        # ---- 按钮：更小，边线更细 ----
        self.btn_size = (220, 60)   # 之前 360x84，现在更小
        btn_rect = pg.Rect(0, 0, *self.btn_size)
        self.btn_start = Button(btn_rect, "start", self.m.fonts["big"])
        # 如果 Button 支持自定义边线/圆角，尽量调细
        for attr, val in [("border_w", 0), ("radius", 14)]:
            if hasattr(self.btn_start, attr):
                setattr(self.btn_start, attr, val)

        # ---- 计算垂直布局 a（整体居中）----
        self._layout_a()

    def _layout_a(self):
        # 量一下三块的高度
        title_h = self.title_font_big.size(self.title)[1]
        sub_h   = self.sub_font.size(self.subtitle)[1]
        btn_h   = self.btn_start.rect.height

        gap1, gap2 = 18, 120  # 标题-副标题、 副标题-按钮 的间距
        total_h = title_h + gap1 + sub_h + gap2 + btn_h

        start_y = (self.H - total_h) // 2 + 40  # “布局 a” 顶部 y（垂直居中）  加偏移
        cx = self.W // 2 + 0                   # 居中对齐

        # 逐项定位
        self.title_pos = (cx, start_y + title_h // 2)
        self.sub_pos   = (cx, self.title_pos[1] + title_h // 2 + gap1 + sub_h // 2)

        self.btn_start.rect.centerx = cx
        self.btn_start.rect.centery = self.sub_pos[1] + sub_h // 2 + gap2 + btn_h // 2

    def _draw_full_grid(self):
        COLS, ROWS = 16, 9
        CELL_W = self.W // COLS
        CELL_H = self.H // ROWS
        for r in range(ROWS):
            for c in range(COLS):
                rect = pg.Rect(c * CELL_W, r * CELL_H, CELL_W, CELL_H)
                col = CFG.GRID_LIGHT if (c + r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(self.m.screen, col, rect)

    def handle_event(self, e):
        if self.btn_start.handle_event(e):
            self.m.goto("mode")

    def update(self, dt):
        # 窗口大小变化时可重算布局（如果你有自适应窗口）
        pass

    def draw(self):
        s = self.m.screen
        s.fill(CFG.BG)
        self._draw_full_grid()

        # Title
        img_title = self.title_font_big.render(self.title, True, CFG.TEXT)
        s.blit(img_title, img_title.get_rect(center=self.title_pos))

        # Subtitle
        img_sub = self.sub_font.render(self.subtitle, True, self.sub_col)
        s.blit(img_sub, img_sub.get_rect(center=self.sub_pos))

        # Button
        self.btn_start.draw(s)
