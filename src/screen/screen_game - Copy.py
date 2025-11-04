# screen_game.py
import pygame as pg
from src.config import CFG
from src.entities import Human, Kangaroo, adjacent_for_punch
from src.sprites import make_people_sprite, make_roo_sprite
from src.ui.board import board_rect, draw_board, grid_center, cell_size
from src.ui.hud import draw_timer, draw_hearts_text
from src.stamina import StaminaBar

# ==== Game tuning constants ====

# Input / cadence
MOVE_COOLDOWN_MS = 120   # 每次移动之间的最小间隔，避免长按连走
PARRY_WINDOW_MS  = 150   # 完美格挡窗口（在对方出拳前/刚出拳时按下）

# Stamina / HP
ROO_REST_THRESHOLD = 22  # 袋鼠低于该体力时不再移动，只回蓝
ST_REGEN_PER_SEC_H = 10  # 人类非格挡时每秒回蓝
ST_REGEN_PER_SEC_R = 14  # 袋鼠休息时每秒回蓝

# 体力与格挡
BLOCK_DRAIN_PER_SEC = 18   # 按住格挡时每秒体力消耗（原BLOCK_CONT_DRAIN_S）
# BLOCK_CONT_DRAIN_S = 18  # 连续按住格挡每秒耗蓝
BLOCK_MIN_STAMINA  = 8   # 低于该体力强制放下格挡
BLOCK_COOLDOWN_MS  = 600 # 放下后格挡冷却时间(ms)

# === FX / Anim ===
HITSTOP_MS    = 80       # 受击停顿
FLASH_MS      = 120      # 颜色闪烁时长

# ===== center message & popup =====
MSG_FADE_MS = 900          # 中央战斗提示显示时长
POPUP_MS    = 1800         # 回合结果弹窗显示时长
POPUP_ALPHA = 220          # 弹窗半透明度(0-255)

# 加时赛
OVERTIME_SECONDS = 15  # 加时 15s

# === Hearts & countdown ===
HEARTS_TOTAL = 2            # 共 2 颗心
KNOCKDOWN_HITS = 3          # 连续被命中 3 次 = 掉半颗心
COUNTDOWN_RADIUS = 42       # 中央倒计时圆半径
COUNTDOWN_STROKE = 4
COUNTDOWN_OVERTIME = 15     # 进入加时的秒数（你说“时间到→15s加时”）

HEART_UI = (78, 118, 197)   # 心/UI 主色（蓝）
HEART_LOST = (212, 52, 52)  # 丢失半心的红色
HEART_OUTLINE = (40, 60, 110)

# -------- HUD & 颜色常量 --------
HUD_H = 120                      # 顶部状态栏高度
MARGIN = 8                      # 四周留白
HUD_BG = (236, 236, 238)         # 顶部灰条背景
HUD_EDGE = (210, 210, 214)       # 顶部灰条描边
ACCENT = (64, 102, 183)          # 蓝色主色（圆环/心/文本）
TIMER_TEXT = ACCENT
TIMER_CIRCLE_BG = (255, 255, 255)  # 计时器白色底
TIMER_RING_W = 10
AVATAR_SIZE = 64                 # 左右迷你头像占位尺寸
HEART_SIZE = 34                  # 心形占位方块尺寸（以后换贴图）
HEART_GAP = 10                   # 两个心之间间距






# ===============================

class GameScreen:
    """
    Single-player game screen.
    - Full 16:9 board as playable area (no half tiles).
    - Human walks 1 cell; Roo jumps 2 cells; Roo punches at <=1 cell.
    - Block with Space; R to Home; Esc handled by main.
    """
    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # Grid = whole window: 16 x 9
        self.COLS, self.ROWS = CFG.GRID_W, CFG.GRID_H
        self.CELL_W = self.W // self.COLS
        self.CELL_H = self.H // self.ROWS

        # Entities
        self.human = Human(pos=(1, self.ROWS // 2))
        self.roo   = Kangaroo(pos=(self.COLS - 2, self.ROWS // 2))

        # Stamina
        self.st_h = StaminaBar(CFG.HUMAN_STAMINA)  # human
        self.st_r = StaminaBar(CFG.ROO_STAMINA)    # roo

        # Runtime state
        self.blocking = False
        self.round_start = pg.time.get_ticks()
        self.last_ai_ms = 0
        self.last_punch_ms = -10_000
        self.hitstop_until = 0
        self.msg_text = ""
        self.msg_until = 0

        # “人物可重叠 + 长按格挡无敌” 的机制修正
        self.blocking = False
        self.block_cd_until = 0  # 冷却结束时间戳(ms)

        # 游戏玩法修复：
        '''
        ESC=暂停：显示半透明菜单：C=Continue，H=Home，Enter=Retry
        禁止重叠（人/袋鼠不会站在同一格）
        格挡不是无敌：
        按住会持续掉体力；体力过低会强制放下并进入冷却
        增加体力（Stamina）回复：不格挡时每秒缓慢回蓝
        双条显示（HP/STM）：人类 HP 会被打掉，STM 走路/格挡消耗且回蓝；袋鼠 HP 固定不动，STM 跳跃消耗、间歇回蓝
        '''
        self.paused = False
        self.blocking = False
        self.block_cd_until = 0

        # 把“耐力条”一拆为二：HP 与 STM
        # 直接复用 StaminaBar 作为通用条
        self.hp_h = StaminaBar(CFG.HUMAN_STAMINA)  # Human HP
        self.st_h = StaminaBar(CFG.HUMAN_STAMINA)  # Human Stamina

        self.hp_r = StaminaBar(CFG.ROO_STAMINA)  # Roo HP（不动）
        self.st_r = StaminaBar(CFG.ROO_STAMINA)  # Roo Stamina

        # ==== v2.1 =====
        # 输入节流
        self.last_move_ms = 0

        # 格挡&parry
        self.blocking = False
        self.block_cd_until = 0
        self.last_block_down_ms = -10_000  # 记录最近一次按下space时间，用于parry窗口

        # 简易动画状态
        self.flash_h_until = 0  # human 被击中/格挡闪烁
        self.flash_r_until = 0  # roo   出拳/被“弹反”闪烁

        # 命中提示
        self.msg_text = ""
        self.msg_until = 0
        self.hitstop_until = 0

        # 中央战斗提示
        self.msg_text  = ""
        self.msg_color = (255, 255, 255)
        self.msg_until = 0

        # 回合/比分（Bo3）
        self.score_h = 0
        self.score_r = 0

        # 回合结束弹窗
        self.popup_kind  = None   # "tie" | "lose" | None
        self.popup_until = 0

        # ----- 加时赛状态 -----
        self.in_overtime = False
        self.ot_start = 0  # 加时开始时间戳（ms）

        # === lives/knockdown tracking ===
        self.lives_halves = HEARTS_TOTAL * 2  # 4 半心
        self.hits_taken = 0  # 本局累计被命中次数（仅未格挡的直击）
        self.overtime_started = None  # 加时开始时间戳（ms）或 None

        # 计算布局：顶部 HUD + 下方可玩 16x9 棋盘区域
        self._recalc_layout()

        # ====== 动画：人物精灵（按棋盘单元格大小缩放） ======
        # 注意：_recalc_layout() 已经算好了 self.CELL_W / self.CELL_H
        self.cell_w = self.CELL_W
        self.cell_h = self.CELL_H

        # widgets.py 里的签名是 make_people_sprite(cell_w, cell_h)
        self.sprite_h = make_people_sprite(self.cell_w, self.cell_h)
        self.sprite_r = make_roo_sprite(self.cell_w, self.cell_h)

        # 初始状态
        self.sprite_h.set_state("idle")
        self.sprite_r.set_state("idle")

        self.h_face = 1  # Human 初始朝右（1 右，-1 左）
        self.r_face = -1  # Roo   初始朝左（面对人类）

        # 用于把“AI跳跃/出拳瞬间”映射到精灵状态的小计时
        self.roo_state_until = 0  # 这之前保持 jump/punch 外观
        self.roo_state_name = "idle"

        self.human_state_until = 0  # 人类 block 外观维持时间（松开后回落）

        # === 简易音效（运行时合成） ===
        self.sfx = self._make_sfx_bank()  # {'punch':Sound, 'hit':Sound, 'block':Sound}


    # ----------运行时合成音效的工具-----------------
    def _make_sfx_bank(self):
        import math, array
        pg.mixer.init(frequency=22050, size=-16, channels=1)
        sr = 22050

        def tone(freq, ms, vol=0.4, kind="sine"):
            n = int(sr * ms / 1000)
            buf = array.array("h")
            for i in range(n):
                t = i / sr
                if kind == "sine":
                    v = math.sin(2 * math.pi * freq * t)
                elif kind == "square":
                    v = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
                else:  # noise
                    import random
                    v = (random.random() * 2 - 1)
                # 轻微衰减避免爆音
                a = 1.0 - i / n
                buf.append(int(v * vol * a * 32767))
            return pg.mixer.Sound(buffer=buf)

        try:
            sfx = {
                "punch": tone(900, 90, 0.35, "square"),  # “滴”
                "hit": tone(180, 110, 0.45, "sine"),  # “哒”
                "block": tone(2600, 50, 0.30, "noise"),  # “刷”
            }
        except Exception:
            # mixer 若初始化失败，回退为静音哑音效
            class _Mute:
                def play(self): pass

            sfx = {"punch": _Mute(), "hit": _Mute(), "block": _Mute()}
        return sfx

    # ---------------- helpers ----------------
    def _layout(self):
        W, H = self.W, self.H
        hud_h = int(H * 0.14)  # 顶部栏高度
        self.hud_rect = pg.Rect(0, 0, W, hud_h)
        margin = 48
        ph = H - hud_h - margin * 2  # 棋盘区高度
        pw = int(ph * 16 / 9)  # 保持 16:9 棋盘比例
        px = (W - pw) // 2
        py = hud_h + margin
        self.play_rect = pg.Rect(px, py, pw, ph)

        # 棋盘网格尺寸（仍 16x9）
        self.COLS, self.ROWS = 16, 9
        self.CELL_W = self.play_rect.width // self.COLS
        self.CELL_H = self.play_rect.height // self.ROWS

    def _grid_rect(self, gx, gy, pad=0):
        x = self.play_rect.x + gx * self.CELL_W + pad
        y = self.play_rect.y + gy * self.CELL_H + pad
        w = self.CELL_W - pad * 2
        h = self.CELL_H - pad * 2
        return pg.Rect(x, y, w, h)

    def _draw_board(self):
        s = self.m.screen
        # 不再全屏黑底，只画棋盘格（全屏范围）
        COLS, ROWS = 16, 9
        CELL_W = self.W // COLS
        CELL_H = (self.H - self.hud_rect.height) // ROWS  # HUD以下全是棋盘

        # 棋盘起点（顶栏下方）
        y0 = self.hud_rect.bottom
        for r in range(ROWS):
            for c in range(COLS):
                rect = pg.Rect(c * CELL_W, y0 + r * CELL_H, CELL_W, CELL_H)
                col = CFG.GRID_LIGHT if (c + r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(s, col, rect)

    def _grid_center(self, gx, gy):
        cx = self.play_rect.left + gx * self.CELL_W + self.CELL_W // 2
        cy = self.play_rect.top + gy * self.CELL_H + self.CELL_H // 2
        return (cx, cy)

    # demo character
    # def _draw_piece(self, pos, color):
    #     """在棋盘坐标 pos=(gx,gy) 处画一个圆角方块。"""
    #     gx, gy = pos
    #     rect = self._grid_rect(gx, gy, pad=8)  # 用你的 play_rect 对齐棋盘
    #     pg.draw.rect(self.m.screen, color, rect, border_radius=12)

    def _recalc_layout(self):
        """根据窗口尺寸计算 HUD 与棋盘区域、以及单元格大小与起点。"""
        W, H = self.W, self.H

        # 顶部 HUD 全宽灰条
        self.hud_rect = pg.Rect(0, 0, W, HUD_H)

        # 可玩区域：在 HUD 下方，四周留白，并保持 16×9
        avail = pg.Rect(MARGIN, HUD_H + MARGIN, W - MARGIN*2, H - HUD_H - MARGIN*2)

        # 以 cell 尺寸整除 16×9，求最大整数 cell
        cell = min(avail.width // 16, avail.height // 9)
        grid_w, grid_h = cell * 16, cell * 9

        # 居中到 avail
        gx = avail.left + (avail.width - grid_w) // 2
        gy = avail.top  + (avail.height - grid_h) // 2

        self.play_rect = pg.Rect(gx, gy, grid_w, grid_h)
        self.CELL_W = cell
        self.CELL_H = cell


        # HUD 左右元素位置（头像与心位）
        self.left_avatar  = pg.Rect(MARGIN+8, (HUD_H-AVATAR_SIZE)//2, AVATAR_SIZE, AVATAR_SIZE)
        self.right_avatar = pg.Rect(self.W - MARGIN - 8 - AVATAR_SIZE, (HUD_H-AVATAR_SIZE)//2, AVATAR_SIZE, AVATAR_SIZE)

        # 两个“心”占位方块：头像旁边水平排布（左侧）
        hx = self.left_avatar.right + 20
        hy = (HUD_H - HEART_SIZE) // 2 + 4
        self.left_hearts = [
            pg.Rect(hx, hy, HEART_SIZE, HEART_SIZE),
            pg.Rect(hx + HEART_SIZE + HEART_GAP, hy, HEART_SIZE, HEART_SIZE)
        ]

        # 右侧心位在头像左边
        hx2 = self.right_avatar.left - HEART_SIZE*2 - HEART_GAP - 20
        self.right_hearts = [
            pg.Rect(hx2, hy, HEART_SIZE, HEART_SIZE),
            pg.Rect(hx2 + HEART_SIZE + HEART_GAP, hy, HEART_SIZE, HEART_SIZE)
        ]

        # 顶部中央大圆计时器
        self.timer_center = (self.W//2, HUD_H//2)
        # 一个舒适的尺寸：取 HUD 高度的 70% 作为半径
        self.timer_radius = int(HUD_H * 0.35)

    def _grid_rect(self, gx, gy, pad=8):
        """把棋盘坐标(gx,gy)转换到屏幕矩形（带圆角方块）。"""
        x = self.play_rect.left + gx * self.CELL_W + pad
        y = self.play_rect.top  + gy * self.CELL_H + pad
        w = self.CELL_W - pad*2
        h = self.CELL_H - pad*2
        return pg.Rect(x, y, w, h)

    def _draw_heart(self, surf, center, size, halves_filled: int, halves_index: int):
        """
        画一颗心的某个半区。
        halves_filled: 剩余的“已填充”半心数量（全局累计）
        halves_index : 当前要画的是第几个半心（从0开始）
        规则：若 halves_index < halves_filled -> 蓝色；否则 -> 红色（表示已丢失）
        """
        cx, cy = center
        w = h = size
        # 心形：两个上圆 + 底部三角
        heart_surface = pg.Surface((w, h), pg.SRCALPHA)
        r = int(w * 0.28)
        left_c = (int(w * 0.35), int(h * 0.35))
        right_c = (int(w * 0.65), int(h * 0.35))
        tri = [(int(w * 0.10), int(h * 0.40)), (int(w * 0.90), int(h * 0.40)), (int(w * 0.50), int(h * 0.90))]

        # 先整体填充为“剩余 or 丢失”的颜色
        fill_col = HEART_UI if halves_index < halves_filled else HEART_LOST
        pg.draw.circle(heart_surface, fill_col, left_c, r)
        pg.draw.circle(heart_surface, fill_col, right_c, r)
        pg.draw.polygon(heart_surface, fill_col, tri)

        # 只保留“半边”：左半或右半
        mask = pg.Surface((w, h), pg.SRCALPHA)
        if halves_index % 2 == 0:
            pg.draw.rect(mask, (255, 255, 255, 255), (0, 0, w // 2, h))  # 左半
        else:
            pg.draw.rect(mask, (255, 255, 255, 255), (w // 2, 0, w // 2, h))  # 右半
        heart_surface.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)

        # 外轮廓
        outline = pg.Surface((w, h), pg.SRCALPHA)
        pg.draw.circle(outline, HEART_OUTLINE, left_c, r, width=2)
        pg.draw.circle(outline, HEART_OUTLINE, right_c, r, width=2)
        pg.draw.polygon(outline, HEART_OUTLINE, tri, width=2)
        heart_surface.blit(outline, (0, 0))

        surf.blit(heart_surface, (cx - w // 2, cy - h // 2))

    def _draw_hearts_row(self, x_left, y, halves_filled: int, heart_size: int = 38, gap: int = 10):
        """
        在 (x_left, y) 从左往右画 HEARTS_TOTAL 颗心（4 半心）。
        halves_filled = 当前剩余的半心数量（0..4）
        """
        halves_total = HEARTS_TOTAL * 2
        x = x_left
        for i in range(HEARTS_TOTAL):
            # 每颗心包含两个半心：i*2, i*2+1
            cx = x + heart_size // 2
            self._draw_heart(self.m.screen, (cx, y), heart_size, halves_filled, i * 2)  # 左半
            self._draw_heart(self.m.screen, (cx, y), heart_size, halves_filled, i * 2 + 1)  # 右半
            x += heart_size + gap

    def _draw_center_countdown(self, now_ms: int):
        # 计算剩余时间（含加时）
        elapsed = (now_ms - self.round_start) // 1000
        base_left = max(0, CFG.ROUND_SECONDS - elapsed)

        if base_left > 0:
            secs = base_left
        else:
            # 进入加时
            if self.overtime_started is None:
                self.overtime_started = now_ms
            ot_elapsed = (now_ms - self.overtime_started) // 1000
            secs = max(0, COUNTDOWN_OVERTIME - ot_elapsed)

        # 画圆 + 数字
        cx, cy = self.W // 2, 78
        pg.draw.circle(self.m.screen, HEART_UI, (cx, cy), COUNTDOWN_RADIUS, COUNTDOWN_STROKE)
        txt = self.m.fonts["title"].render(str(int(secs)), True, HEART_UI)
        self.m.screen.blit(txt, txt.get_rect(center=(cx, cy)))

    def _hud_bar(self, pos, width, height, cur, maxv):
        """顶栏用的细长耐力条"""
        s = self.m.screen
        x, y = pos
        # 背景
        pg.draw.rect(s, (215, 220, 230), (x, y, width, height), border_radius=6)
        # 填充
        fill_w = int(width * max(0.0, min(1.0, cur / max(1, maxv))))
        pg.draw.rect(s, (86, 124, 192), (x, y, fill_w, height), border_radius=6)
        # 外框
        pg.draw.rect(s, (90, 100, 120), (x, y, width, height), 2, border_radius=6)

    # def _draw_hud(self):
    #     s = self.m.screen
    #     hud = self.hud_rect  # 便捷别名
    #
    #     # 顶栏背景
    #     pg.draw.rect(s, (235, 235, 238), hud)
    #
    #     pad = 18
    #     box = 56
    #
    #     # 左头像（Human）
    #     left_avt = pg.Rect(hud.left + pad, hud.top + pad, box, box)
    #     pg.draw.rect(s, CFG.UI, left_avt, border_radius=12)
    #
    #     # 右头像（Roo）
    #     right_avt = pg.Rect(hud.right - pad - box, hud.top + pad, box, box)
    #     pg.draw.rect(s, CFG.UI, right_avt, border_radius=12)
    #
    #     # 左侧（Human）耐力条：头像右侧
    #     self._hud_bar(
    #         pos=(hud.left + 96, hud.top + 52), width=360, height=12,
    #         cur=self.st_h.cur, maxv=self.st_h.max
    #     )
    #
    #     # 右侧（Roo）耐力条：头像左侧（靠右对齐）
    #     self._hud_bar(
    #         pos=(hud.right - 96 - 360, hud.top + 52), width=360, height=12,
    #         cur=self.st_r.cur, maxv=self.st_r.max
    #     )
    #
    #     # ===== 文本❤ =====
    #     total_hearts = HEARTS_TOTAL  # 例如 2
    #     human_hearts_filled = max(0, self.lives_halves // 2)  # 4 半心 -> 2 整心
    #
    #     # 左侧：从头像右边 20px 处开始，左对齐
    #     self._draw_hearts_text(
    #         x_anchor=left_avt.right + 20,
    #         y_center=hud.top + pad + 20,
    #         total=total_hearts,
    #         filled=human_hearts_filled,
    #         align="left"
    #     )
    #
    #     # 右侧：从头像左边 16px 处“向左对齐”（整体右对齐）
    #     self._draw_hearts_text(
    #         x_anchor=right_avt.left - 16,
    #         y_center=hud.top + pad + 20,
    #         total=total_hearts,
    #         filled=total_hearts,  # 袋鼠这边如果只是装饰就满❤；如需可改为自己的变量
    #         align="right"
    #     )
    #
    #     # 中央计时圈（白底）
    #     self._draw_timer()

    # def _draw_timer(self):
    #     s = self.m.screen
    #     cx = self.hud_rect.centerx
    #     cy = self.hud_rect.centery + 4
    #     R_out, R_in = 52, 46
    #     # 白底圆
    #     pg.draw.circle(s, (255, 255, 255), (cx, cy), R_out)
    #     # 外圈描边
    #     pg.draw.circle(s, CFG.UI, (cx, cy), R_out, width=6)
    #     # 数字
    #     secs = max(0, self.round_time_left())
    #     txt = self.m.fonts["big"].render(str(secs), True, CFG.UI)
    #     s.blit(txt, txt.get_rect(center=(cx, cy)))

    def round_time_left(self):
        now = pg.time.get_ticks()
        total = CFG.ROUND_SECONDS + (CFG.OT_SECONDS if getattr(self, "overtime", False) else 0)
        return total - int((now - self.round_start) / 1000)

    def _draw_top_hud(self, now_ms: int):
        # 左：Human 的两颗心（按半心显示）
        self._draw_hearts_row(28, 40, self.lives_halves)

        # 右：Roo 也画两颗心但不扣（如果你想做，也可以给 self.lives_roo_halves）
        # 这里就画满作为装饰
        heart_size = 38
        total_w = HEARTS_TOTAL * heart_size + (HEARTS_TOTAL - 1) * 10
        x_right = self.W - 28 - total_w
        self._draw_hearts_row(x_right, 40, HEARTS_TOTAL * 2)

        # 中央：超大倒计时
        self._draw_center_countdown(now_ms)

    def _draw_full_grid(self):
        for r in range(self.ROWS):
            for c in range(self.COLS):
                rect = pg.Rect(c * self.CELL_W, r * self.CELL_H, self.CELL_W, self.CELL_H)
                col = CFG.GRID_LIGHT if (c + r) % 2 == 0 else CFG.GRID_DARK
                pg.draw.rect(self.m.screen, col, rect)




    def _set_blocking(self, on: bool):
        now = pg.time.get_ticks()
        if on:
            # 冷却中或体力太低，不能抬起
            if now < self.block_cd_until or self.st_h.cur <= BLOCK_MIN_STAMINA:
                self.blocking = False
            else:
                self.blocking = True
        else:
            if self.blocking:
                self.blocking = False
                self.block_cd_until = now + BLOCK_COOLDOWN_MS

    def _gain(self, bar, amt):
        bar.cur = min(bar.max, bar.cur + amt)

    # fix: 解决“袋鼠穿越人类”——补上中间格阻挡（两格跳不能越人）








    # ------- 中央战斗提示 -------
    def _set_center_msg(self, text, color=(255,255,255)):
        now = pg.time.get_ticks()
        self.msg_text  = text
        self.msg_color = color
        self.msg_until = now + MSG_FADE_MS

    # ------- 回合弹窗（占位样式）-------
    def _show_round_popup(self, kind: str):
        """kind: 'tie' 平局(按袋鼠胜) | 'lose' 人类输"""
        now = pg.time.get_ticks()
        self.popup_kind  = kind
        self.popup_until = now + POPUP_MS

    # ------- 回合结束（Bo3）-------
    def _end_round(self, result: str):
        """
        result: 'human' 人类胜 | 'roo' 袋鼠胜 | 'tie' 平局(按袋鼠胜)
        """
        if result == "human":
            self.score_h += 1
        elif result in ("roo", "tie"):
            self.score_r += 1

        # 弹窗：平局用 tie；人类输用 lose；人类赢暂不弹
        if result == "tie":
            self._show_round_popup("tie")
        elif result == "roo":
            self._show_round_popup("lose")

        # 回合清场：重置位置与体力/状态
        self.human.pos = (1, self.ROWS // 2)
        self.roo.pos   = (self.COLS - 2, self.ROWS // 2)
        self.blocking  = False
        self.block_cd_until = 0

        # 体力/生命回满
        self.hp_h.cur = self.hp_h.max
        self.st_h.cur = self.st_h.max
        self.st_r.cur = self.st_r.max
        # 袋鼠 HP 按你的设定不动，但这里保持为 max

        # 回合计时刷新
        self.round_start = pg.time.get_ticks()
        self.last_ai_ms = 0
        self.last_punch_ms = -10_000


        # 判断是否有人先到 2 分
        if self.score_h >= 2:
            self.m.goto("end", result_text="You Win!")
        elif self.score_r >= 2:
            self.m.goto("end", result_text="You Lose!")

    def _start_overtime(self):
        """进入加时赛：重置计时并给出提示。"""
        self.in_overtime = True
        self.ot_start = pg.time.get_ticks()
        # 中央提示
        if hasattr(self, "_set_center_msg"):
            self._set_center_msg(f"Overtime +{OVERTIME_SECONDS}s!", (220, 220, 255))

    def _peace_ending(self):
        """和平结局：人类胜利。"""
        # 你已有的回合收尾入口，如果有三局两胜就在 _end_round 里累计
        self._set_center_msg("Peace Ending — Human Wins!", (230, 245, 255))
        self._end_round("human")  # 记为人类赢

    # ---------------- events ----------------
    def handle_event(self, e):
        now = pg.time.get_ticks()

        # ==== Esc：暂停 ====
        if e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
            self.m.push("pause")
            return

        if e.type == pg.KEYDOWN:
            if e.key == pg.K_SPACE:
                self.last_block_down_ms = now
                self._set_blocking(True)
                return

            if now - self.last_move_ms < MOVE_COOLDOWN_MS:
                return

            hx, hy = self.human.pos
            moved = False
            if e.key == pg.K_UP:
                hy -= 1;
                moved = True
            elif e.key == pg.K_DOWN:
                hy += 1;
                moved = True
            elif e.key == pg.K_LEFT:
                hx -= 1;
                moved = True
                self.h_face = -1  # ← 左
            elif e.key == pg.K_RIGHT:
                hx += 1;
                moved = True
                self.h_face = 1  # → 右

            if moved and self._can_move(hx, hy):
                self.human.pos = (hx, hy)
                self.st_h.lose(CFG.WALK_COST)
                self.last_move_ms = now

        elif e.type == pg.KEYUP and e.key == pg.K_SPACE:
            # 松开空格 -> 退出格挡（仍然会受到低体力强制放下/冷却机制影响）
            self._set_blocking(False)

    # ---------------- logic ----------------
    def update(self, dt):
        """
        每帧更新：
        - 暂停/受击停顿
        - 人类格挡持续消耗 & 回蓝
        - 袋鼠低体力休息回蓝 / 正常时AI跳跃
        - 出拳结算（含 Parry、格挡、直击；命中计分与掉半心）
        - 回合与加时（15s）结束判定：加时后平局按人类赢
        """
        now = pg.time.get_ticks()

        # ===== 1) 暂停/受击停顿 =====
        if getattr(self, "paused", False):
            return
        if now < getattr(self, "hitstop_until", 0):
            return

        # ===== 2) 人类格挡持续消耗 & 回蓝 =====
        if getattr(self, "blocking", False):
            # 持续消耗，过低强制放下
            self.st_h.lose(BLOCK_DRAIN_PER_SEC * (dt / 1000.0))
            if self.st_h.cur <= BLOCK_MIN_STAMINA:
                self._set_blocking(False)
        else:
            # 不格挡时回蓝
            self.st_h.cur = min(self.st_h.max, self.st_h.cur + ST_REGEN_PER_SEC_H * (dt / 1000.0))

        # ===== 3) 袋鼠体力：低于阈值休息回蓝，否则允许行动 =====
        if self.st_r.cur < ROO_REST_THRESHOLD:
            self.st_r.cur = min(self.st_r.max, self.st_r.cur + ST_REGEN_PER_SEC_R * (dt / 1000.0))
            can_act = False
        else:
            can_act = True

        # 标记用于动画（draw 里读后决定状态帧）
        self.just_jumped = False
        self.just_punched = False

        # ===== 4) AI 跳跃（两格；不穿越/不重叠；移动成功才扣跳跃体力）=====
        if can_act and now - getattr(self, "last_ai_ms", 0) >= CFG.AI_DECIDE_EVERY_MS:
            self.last_ai_ms = now
            pre = self.roo.pos
            self._ai_jump_towards(self.human.pos)  # 你已有的带中间格校验版本
            if self.roo.pos != pre:
                self.st_r.lose(CFG.JUMP_COST)
                self.just_jumped = True

        # ===== 5) 出拳结算（相邻即打；命中即给 Roo 计分）=====
        if adjacent_for_punch(self.roo.pos, self.human.pos) and \
                (now - getattr(self, "last_punch_ms", 0)) >= CFG.PUNCH_COOLDOWN_MS:

            if self.human.pos[0] != self.roo.pos[0]:
                self.r_face = 1 if (self.human.pos[0] > self.roo.pos[0]) else -1

            # handle_event 按下 SPACE 处（_set_blocking(True) 之后）
            if self.human.pos[0] != self.roo.pos[0]:
                self.h_face = 1 if (self.roo.pos[0] > self.human.pos[0]) else -1

            self.last_punch_ms = now
            self.just_punched = True

            # 视觉与音效（容错）
            self.flash_r_until = now + FLASH_MS
            try:
                if hasattr(self, "sfx") and self.sfx.get("punch"):
                    self.sfx["punch"].play()
            except Exception:
                pass

            # 本拳是否让 Human 掉血（用于 Roo +1 分）
            scored_this_punch = False

            # Parry 判定（按你之前的“按下瞬间窗口”逻辑）
            parry = getattr(self, "blocking", False) and \
                    hasattr(self, "last_block_down_ms") and \
                    (0 <= (now - self.last_block_down_ms) <= PARRY_WINDOW_MS)

            if parry:
                # 完美格挡：不掉血不计分，反震袋鼠体力
                try:
                    if hasattr(self, "sfx") and self.sfx.get("block"):
                        self.sfx["block"].play()
                except Exception:
                    pass
                self._set_center_msg("PARRY!", (240, 255, 240))
                self.st_r.lose(CFG.PUNCH_DAMAGE * 0.6)
                self.flash_h_until = now + FLASH_MS
                self.hitstop_until = now + HITSTOP_MS

            elif getattr(self, "blocking", False):
                # 普通格挡：人类掉少量 HP → 计分
                try:
                    if hasattr(self, "sfx") and self.sfx.get("block"):
                        self.sfx["block"].play()
                except Exception:
                    pass
                self.hp_h.lose(CFG.PUNCH_BLOCKED_DAMAGE)
                self.st_r.lose(CFG.BLOCK_SHARED_LOSS)
                self.st_h.lose(CFG.BLOCK_SHARED_LOSS * 0.5)
                self._set_center_msg("BLOCK!", (230, 230, 230))
                self.flash_h_until = now + FLASH_MS
                self.hitstop_until = now + HITSTOP_MS
                scored_this_punch = True  # 计分

            else:
                # 直击：人类掉正常 HP → 计分 + 直击累计掉半心
                try:
                    if hasattr(self, "sfx") and self.sfx.get("hit"):
                        self.sfx["hit"].play()
                except Exception:
                    pass
                self.hp_h.lose(CFG.PUNCH_DAMAGE)
                self._set_center_msg(f"-{CFG.PUNCH_DAMAGE} HP", (240, 120, 120))
                self.flash_h_until = now + FLASH_MS
                self.hitstop_until = now + HITSTOP_MS
                scored_this_punch = True

                # 直击次数累计 → 每 KNOCKDOWN_HITS 次掉半心
                self.hits_taken = getattr(self, "hits_taken", 0) + 1
                if self.hits_taken % KNOCKDOWN_HITS == 0:
                    self.lives_halves = max(0, getattr(self, "lives_halves", 4) - 1)
                    self._set_center_msg("Knockdown! (-1/2 ♥)", (245, 120, 120))
                    if self.lives_halves == 0:
                        self.m.goto("end", result_text="You Lose!")
                        return

            # 只要人类这拳掉血（直击或格挡），Roo 就 +1 分
            if scored_this_punch:
                self.score_r = getattr(self, "score_r", 0) + 1

        # ===== 6) 人类 HP 见底：本回合结束（Roo胜）=====
        if self.hp_h.is_depleted():
            self._end_round("roo")
            return

        # ===== 7) 倒计时与加时：到时→进入 15s 加时；加时后平局按人类赢 =====
        elapsed = (now - self.round_start) // 1000
        if elapsed >= CFG.ROUND_SECONDS:
            if getattr(self, "overtime_started", None) is None:
                self.overtime_started = now  # 开始加时
            else:
                ot = (now - self.overtime_started) // 1000
                if ot >= COUNTDOWN_OVERTIME:
                    # 加时结束：若仍存活则和平胜
                    if self.hp_h.cur > 0:
                        self.m.goto("end", result_text="Peace Ending — You Win!")
                    else:
                        self.m.goto("end", result_text="You Lose!")
                    return

    # ---------------- draw ----------------
    def _draw_hearts_text(self, x_anchor: int, y_center: int, total: int, filled: int, align: str = "left"):
        """
        用纯文本 ❤ 绘制爱心。
        x_anchor: 参考锚点 x；align='left' 视为左起点，'right' 视为右终点
        """
        f = self.m.fonts["big"]
        total = max(0, total)
        filled = max(0, min(total, filled))

        s_full = "❤" * filled
        s_empty = "❤" * (total - filled)

        img_full = f.render(s_full, True, (220, 80, 80)) if filled else None
        img_empty = f.render(s_empty, True, (210, 210, 220)) if total - filled > 0 else None

        w_full = img_full.get_width() if img_full else 0
        w_empty = img_empty.get_width() if img_empty else 0
        gap = 8 if (img_full and img_empty) else 0
        total_w = w_full + gap + w_empty

        surf = self.m.screen
        x = x_anchor - total_w if align == "right" else x_anchor

        if img_full:
            rect = img_full.get_rect(midleft=(x, y_center))
            surf.blit(img_full, rect)
            x = rect.right + gap
        if img_empty:
            rect = img_empty.get_rect(midleft=(x, y_center))
            surf.blit(img_empty, rect)

    def _draw_bar(self, label, cur, maxv, topleft, width=340):
        x, y = topleft;
        H = 16
        pg.draw.rect(self.m.screen, CFG.UI_BACK, (x, y, width, H), border_radius=4)
        fill = int(width * (cur / max(1, maxv)))
        pg.draw.rect(self.m.screen, CFG.UI, (x, y, fill, H), border_radius=4)
        cap = f"{label}: {int(cur)}/{int(maxv)}"
        self.m.screen.blit(self.m.fonts["sml"].render(cap, True, CFG.TEXT), (x, y - 20))

    def draw(self):
        s = self.m.screen
        now = pg.time.get_ticks()

        # 供精灵动画用的 dt（与 update 独立，避免 draw 里用到未定义 dt）
        dt_ani = now - getattr(self, "_last_draw_tick", now)
        self._last_draw_tick = now

        # ===== 1) 顶栏（计时圈/头像占位/体力条）=====
        self._draw_hud()

        # ===== 2) 棋盘格（顶栏下方铺满）=====
        self._draw_board()

        # ===== 3) 角色动画状态 & 切帧 =====
        # Human：是否格挡
        self.sprite_h.set_state("block" if getattr(self, "blocking", False) else "idle")
        self.sprite_h.update(dt_ani)

        # Roo：刚跳/刚出拳优先，否则 idle
        if getattr(self, "just_punched", False):
            self.sprite_r.set_state("punch")
        elif getattr(self, "just_jumped", False):
            self.sprite_r.set_state("jump")
        else:
            self.sprite_r.set_state("idle")
        self.sprite_r.update(dt_ani)

        # ===== 4) 精灵绘制（按棋盘格中心对齐）=====
        # 你的 SimpleSprite.draw 当前签名是 draw(surface, center_xy)（若是 size 版本，请改为三参）
        # self.sprite_h.draw(s, self._grid_center(*self.human.pos))
        # self.sprite_r.draw(s, self._grid_center(*self.roo.pos))
        # screen_game.py -> draw()
        self.sprite_h.set_state("block" if getattr(self, "blocking", False) else "idle")
        self.sprite_h.update(dt_ani)
        if getattr(self, "just_punched", False):
            self.sprite_r.set_state("punch")
        elif getattr(self, "just_jumped", False):
            self.sprite_r.set_state("jump")
        else:
            self.sprite_r.set_state("idle")
        self.sprite_r.update(dt_ani)

        # === 绘制（加 flip_h）===
        self.sprite_h.draw(s, self._grid_center(*self.human.pos), flip_h=(self.h_face == -1))
        self.sprite_r.draw(s, self._grid_center(*self.roo.pos), flip_h=(self.r_face == -1))

        # ===== 5) 中央战斗提示（Blocked/Parry/伤害数字等）=====
        if now < getattr(self, "msg_until", 0) and getattr(self, "msg_text", ""):
            color = getattr(self, "msg_color", (240, 240, 250))
            img = self.m.fonts["title"].render(self.msg_text, True, color)
            s.blit(img, img.get_rect(center=self.play_rect.center))

        # ===== 6) 记分（左下角，上移避免与右下提示重叠）=====
        score_img = self.m.fonts["mid"].render(
            f"Score  You {getattr(self, 'score_h', 0)} : {getattr(self, 'score_r', 0)} Roo", True, CFG.TEXT
        )
        s.blit(score_img, (16, self.H - 52))

        # ===== 7) 回合弹窗（半透明遮罩 + 卡片）=====
        if getattr(self, "popup_kind", None) and now < getattr(self, "popup_until", 0):
            overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            s.blit(overlay, (0, 0))

            box_w, box_h = int(self.W * 0.64), int(self.H * 0.5)
            box = pg.Rect(0, 0, box_w, box_h);
            box.center = (self.W // 2, self.H // 2)
            pg.draw.rect(s, (45, 49, 58), box, border_radius=18)
            pg.draw.rect(s, (28, 31, 38), box, 3, border_radius=18)

            if self.popup_kind == "tie":
                title, sub = "Round Draw", "Peace achieved — Human prevails."
            elif self.popup_kind == "win":
                title, sub = "You Win!", "Nice spacing. Keep baiting the jump."
            else:
                title, sub = "You Got Hit!", "Time your BLOCK right before the punch."

            t_img = self.m.fonts["title"].render(title, True, (235, 235, 235))
            s_img = self.m.fonts["big"].render(sub, True, (210, 210, 215))
            s.blit(t_img, t_img.get_rect(center=(self.W // 2, self.H // 2 - 40)))
            s.blit(s_img, s_img.get_rect(center=(self.W // 2, self.H // 2 + 28)))
        else:
            self.popup_kind = None  # 过时清空

        # ===== 8) 操作提示（右下角）=====
        hint_img = self.m.fonts["sml"].render("Arrows=Move  Space=Block  ESC=Pause", True, CFG.TEXT)
        s.blit(hint_img, hint_img.get_rect(bottomright=(self.W - 16, self.H - 12)))

        # ===== 9) 暂停层 =====
        if getattr(self, "paused", False):
            overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 130))
            s.blit(overlay, (0, 0))
            title = self.m.fonts["title"].render("Paused", True, CFG.TEXT)
            s.blit(title, title.get_rect(center=(self.W // 2, self.H // 2 - 40)))
            tip = self.m.fonts["mid"].render("[C] Continue   [Enter] Retry   [H] Home", True, CFG.TEXT)
            s.blit(tip, tip.get_rect(center=(self.W // 2, self.H // 2 + 20)))
