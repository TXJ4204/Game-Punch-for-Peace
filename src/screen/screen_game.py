# ==== A) imports / constants / helpers / __init__ ====
from __future__ import annotations
import pygame as pg
from src.config import CFG
from src.entities import Human, Kangaroo
from src.stamina import StaminaBar
from src.ui.board import compute_play_rect, draw_board, grid_center
from src.ui.hud import draw_top_hud, HUD_H
from src.sprites import make_people_sprite, make_roo_sprite

# ---- feature switches: read from global CFG ----
DEBUG_LOG = CFG.DEBUG
# “只转身模式”优先生效；一旦开启，移动/出拳都应被抑制
AI_FACE_ONLY       = CFG.AI_TURN_ONLY_MODE
AI_FOLLOW_ENABLED  = (CFG.AI_ALLOW_MOVE  and not CFG.AI_TURN_ONLY_MODE)
AI_PUNCH_ENABLED   = (CFG.AI_ALLOW_PUNCH and not CFG.AI_TURN_ONLY_MODE)


# ---- facing enum ----
R_FACE_LEFT  = -1
R_FACE_RIGHT =  1

# ---- small timing aliases（避免硬编码散落） ----
MOVE_COOLDOWN_MS = CFG.MOVE_COOLDOWN_MS
HITSTOP_MS       = CFG.HITSTOP_MS

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

class GameScreen:
    """
    Game screen: grid-based duel (Human vs Roo).
    Rule: Human walk 1 cell, Roo jump 2 cells; punch only at adjacent cell, facing must be correct.
    """

    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # Entities
        self.human = Human(pos=(1, CFG.GRID_H // 2))
        self.roo   = Kangaroo(pos=(CFG.GRID_W - 2, CFG.GRID_H // 2))

        # Bars
        self.hp_h = StaminaBar(CFG.HUMAN_STAMINA)  # 作为 HP（100）
        self.st_h = StaminaBar(CFG.HUMAN_STAMINA)  # 人类体力
        self.hp_h.reset()

        self.st_r = StaminaBar(CFG.ROO_STAMINA)    # 袋鼠体力

        # Hearts (half-heart system)
        self.lives_halves = CFG.HUMAN_HEARTS * 2   # 人：2心=4半心
        self.roo_halves   = CFG.ROO_HEARTS * 2     # Roo 展示 3心=6半心

        # Round/Timer
        self.round_idx   = 1
        self.round_start = pg.time.get_ticks()
        self.overtime_started = None

        # Runtime state
        self.blocking = False
        self.last_block_down_ms = -10_000

        self.last_move_ms = 0
        self.last_human_step_ms = -10_000

        self.hitstop_until = 0
        self.ai_pause_until = 0
        self.last_ai_ms = 0
        self.last_punch_ms = -10_000
        self.intend_punch = False
        self.punch_windup_until = 0
        self.roo_punch_until = 0

        # Messages
        self._dbg(f"Flags | face_only={AI_FACE_ONLY}  move={AI_FOLLOW_ENABLED}  punch={AI_PUNCH_ENABLED}")
        self.msg_text, self.msg_color, self.msg_until = "", (255,255,255), 0
        self.popup_kind, self.popup_until = None, 0

        # Score
        self.score_h = 0
        self.score_r = 0

        # Layout & sprites
        self.play_rect = compute_play_rect(self.W, self.H, hud_h=HUD_H, margin=8)
        cell_w = self.play_rect.width  // CFG.GRID_W
        cell_h = self.play_rect.height // CFG.GRID_H
        self.sprite_h = make_people_sprite(cell_w, cell_h)
        self.sprite_r = make_roo_sprite(cell_w, cell_h)

        # facing
        self.h_face = R_FACE_RIGHT
        self.r_face = R_FACE_LEFT
        self.roo_prev = self.roo.pos

        # hit-box size（相对格子）
        self._cell_w = cell_w
        self._cell_h = cell_h
        self._hit_w  = int(cell_w * 0.70)
        self._hit_h  = int(cell_h * 0.90)

        # sfx bank（失败忽略）
        self.sfx = {}
        try:
            pg.mixer.init()
        except:
            pass

    # ---------- debug print ----------
    def _dbg(self, msg: str):
        if DEBUG_LOG:
            t = pg.time.get_ticks()
            rx, ry = self.roo.pos
            hx, hy = self.human.pos
            print(f"[{t:7d}ms] H({hx},{hy}) R({rx},{ry}) | {msg}")

    # ---------- messages ----------
    def _set_center_msg(self, text, color=(255,255,255), ms=900):
        self.msg_text = text
        self.msg_color = color
        self.msg_until = pg.time.get_ticks() + ms

    # ---------- rects & fist ----------
    def _rect_at(self, grid_pos):
        cx = self.play_rect.left + (grid_pos[0] + 0.5) * self._cell_w
        cy = self.play_rect.top  + (grid_pos[1] + 0.5) * self._cell_h
        r = pg.Rect(0, 0, self._hit_w, self._hit_h)
        r.center = (int(cx), int(cy))
        return r

    def human_rect(self, center_xy: tuple[int, int] | None = None):
        """Return human's yellow bbox (screen-space) of current frame."""
        if center_xy is None:
            center_xy = grid_center(self.play_rect, *self.human.pos)
        flip = (self.h_face < 0)
        return self.sprite_h.bbox_rect(center_xy, flip_h=flip)

    def roo_rect(self, center_xy: tuple[int, int] | None = None):
        """Return roo's yellow bbox (screen-space) of current frame."""
        if center_xy is None:
            center_xy = grid_center(self.play_rect, *self.roo.pos)
        flip = (self.r_face > 0)  # 我们袋鼠朝右要翻转
        return self.sprite_r.bbox_rect(center_xy, flip_h=flip)

    def roo_fist_point(self):
        """
        Pixel-accurate fist anchor from JSON (punchL/punchR), scaled & flipped.
        """
        center = grid_center(self.play_rect, *self.roo.pos)
        flip = (self.r_face > 0)  # 我们的袋鼠朝右时翻转绘制
        return self.sprite_r.fist_point(center, flip_h=flip)

    def _centers_screen(self) -> tuple[tuple[int,int], tuple[int,int]]:
        """
        Return (human_center, roo_center) in screen coords.
        Centers are snapped (using yellow bbox) to eliminate visual gap
        when they stand adjacent on the same row.
        """
        base_h = grid_center(self.play_rect, *self.human.pos)
        base_r = grid_center(self.play_rect, *self.roo.pos)
        h_c, r_c = self._centers_face_to_face_snap(base_h, base_r)
        self._last_centers = (h_c, r_c)
        return h_c, r_c


    # ---------- facing helpers ----------
    def _face_str(self, f): return "Right" if f == R_FACE_RIGHT else "Left"

    def _set_face(self, face):
        if face != self.r_face:
            self._dbg(f"Face: {self._face_str(self.r_face)} -> {self._face_str(face)}")
        self.r_face = face

    def _face_towards_player_x(self):
        rx, ry = self.roo.pos
        hx, hy = self.human.pos
        need = R_FACE_RIGHT if (hx - rx) >= 0 else R_FACE_LEFT
        self._set_face(need)

    def _face_after_player_moved(self):
        # 玩家移动后的一次对齐（仅看 X；X 相等不改）
        rx, ry = self.roo.pos
        hx, hy = self.human.pos
        dx = hx - rx
        if dx > 0:
            self._set_face(R_FACE_RIGHT)
        elif dx < 0:
            self._set_face(R_FACE_LEFT)

    # ---------- safe move for roo (no overlap, no pass-through) ----------
    def _safe_move_roo(self, tx, ty):
        rx, ry = self.roo.pos
        tx = _clamp(tx, 0, CFG.GRID_W - 1)
        ty = _clamp(ty, 0, CFG.GRID_H - 1)

        # mid cell (for jump-2)
        if tx != rx:
            mid = (rx + (1 if tx > rx else -1), ry)
        else:
            mid = (rx, ry + (1 if ty > ry else -1))

        # If mid or target hits human → shrink to 1 step; if still hit → cancel
        if mid == self.human.pos or (tx, ty) == self.human.pos:
            tx, ty = mid
            if (tx, ty) == self.human.pos:
                self._dbg("SafeMove: blocked by human, cancel")
                return False

        self.roo_prev = self.roo.pos
        self.roo.pos = (tx, ty)
        # update facing by X immediately
        if tx > rx: self._set_face(R_FACE_RIGHT)
        if tx < rx: self._set_face(R_FACE_LEFT)
        self._dbg(f"SafeMove: to ({tx},{ty}), face {self._face_str(self.r_face)}")
        return True

# ==== B) human input & stamina, punch-commit block ====
    def handle_event(self, e):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_SPACE:
                # begin blocking（允许长按）
                self._set_blocking(True)
        elif e.type == pg.KEYUP:
            if e.key == pg.K_SPACE:
                self._set_blocking(False)

    def _set_blocking(self, on: bool):
        self.blocking = bool(on)
        if on:
            self.last_block_down_ms = pg.time.get_ticks()

    # ---- 主更新（上半：玩家输入/体力；蓄力到点结算） ----
    def update(self, dt_ms: int):
        now = pg.time.get_ticks()

        # 受击停顿（保持动画推进在 draw）
        if now < self.hitstop_until:
            return

        # === stamina：人类格挡消耗 / 回蓝 ===
        dt_sec = dt_ms / 1000.0
        if self.blocking:
            self.st_h.lose(CFG.BLOCK_DRAIN_PER_SEC * dt_sec)
            if self.st_h.cur <= CFG.BLOCK_MIN_STAMINA:
                self._set_blocking(False)
        else:
            self.st_h.cur = min(self.st_h.max, self.st_h.cur + CFG.ST_REGEN_PER_SEC_H * dt_sec)

        # === 人类移动（连续读键，带冷却与体力） ===
        keys = pg.key.get_pressed()
        if now - self.last_move_ms >= CFG.MOVE_COOLDOWN_MS:
            hx, hy = self.human.pos
            nx, ny = hx, hy
            moved = False

            if keys[pg.K_UP]:
                ny -= 1
            elif keys[pg.K_DOWN]:
                ny += 1
            elif keys[pg.K_LEFT]:
                nx -= 1; self.h_face = R_FACE_LEFT
            elif keys[pg.K_RIGHT]:
                nx += 1; self.h_face = R_FACE_RIGHT

            if (nx, ny) != (hx, hy) and self.human.can_move(
                nx, ny, roo_pos=self.roo.pos, cols=CFG.GRID_W, rows=CFG.GRID_H
            ):
                if self.st_h.cur >= CFG.WALK_COST:
                    self.human.move_to(nx, ny)
                    self.st_h.lose(CFG.WALK_COST)
                    self.last_move_ms = now
                    self.last_human_step_ms = now
                    moved = True
                    # 玩家移动后立即对齐面向
                    self._face_after_player_moved()

        # --- AI tick every frame ---
        self._ai_decide(now, dt_sec)

        # === 蓄力到点（唯一命中结算点） ===
        if AI_PUNCH_ENABLED and getattr(self, "intend_punch", False) and now >= self.punch_windup_until:
            self.intend_punch = False

            # 到点前兜底强制面向
            prev = self.r_face
            self._face_towards_player_x()
            self._dbg(f"Punch commit face: {self._face_str(prev)} -> {self._face_str(self.r_face)}")

            # 动画与时间戳
            self.sprite_r.set_state("punch")
            self.roo_punch_until = now + CFG.PUNCH_ANIM_MS
            self.last_punch_ms = now

            # 命中条件：同一行相邻 + 面向正确 + 拳点落在人像素mask上
            # 命中条件：同一行相邻 + 面向正确 + 拳点落在人像素mask上
            hit_ok = can_punch(self.roo.pos, self.human.pos, self.r_face)
            if hit_ok:
                # 用与 draw 完全一致的“贴边后中心”
                h_center, r_center = self._centers_screen()
                # 人物像素掩码（含翻转）
                h_flip = (self.h_face < 0)
                h_mask, h_rect = self.sprite_h.mask_and_rect(h_center, flip_h=h_flip)
                # 拳点（基于当前帧、r_center、含翻转）
                fx, fy = self.sprite_r.fist_point(r_center, flip_h=(self.r_face > 0))
                # 拳点是否打在人像素（mask=1）
                if 0 <= (fx - h_rect.x) < h_rect.w and 0 <= (fy - h_rect.y) < h_rect.h:
                    hit_ok = bool(h_mask.get_at((fx - h_rect.x, fy - h_rect.y)))
                else:
                    hit_ok = False

            # 闪避保护
            if hit_ok and (now - getattr(self, "last_human_step_ms", -999999)) <= CFG.EVADE_GRACE_MS:
                hit_ok = False
                self._dbg("Hit test: evaded by recent move")

            if not hit_ok:
                self.ai_pause_until = now + 220
                self._dbg("Punch result: whiff -> short pause")
                return

            # 命中两分支（简化）：BLOCK or HIT
            if self.blocking:
                self._dbg("Punch result: BLOCK")
                try:
                    self.sfx.get("block", None) and self.sfx["block"].play()
                except:
                    pass
                self.hp_h.lose(CFG.PUNCH_BLOCKED_DAMAGE)
                self.st_r.lose(CFG.BLOCK_SHARED_LOSS)
                self.st_h.lose(CFG.BLOCK_SHARED_LOSS * 0.5)
                self._set_center_msg("BLOCK!", (230, 230, 230))
                self.hitstop_until = now + HITSTOP_MS
                self._roo_step_back()
                self.ai_pause_until = now + CFG.BLOCK_RECOVER_MS
                self.score_r += 1
                return

            # 直击
            self._dbg("Punch result: HIT")
            try:
                self.sfx.get("hit", None) and self.sfx["hit"].play()
            except:
                pass
            self.hp_h.lose(CFG.PUNCH_DAMAGE)
            self._set_center_msg(f"-{CFG.PUNCH_DAMAGE} HP", (240, 120, 120))
            self.hitstop_until = now + HITSTOP_MS
            self.score_r += 1

            # HP 清零 → 掉半心
            if self.hp_h.cur <= 0:
                self.lives_halves = max(0, self.lives_halves - 1)
                self.hp_h.reset()
                self._set_center_msg("- 1/2 ♥", (245,120,120), ms=900)
                self._dbg(f"Half-heart lost -> {self.lives_halves}")
                if self.lives_halves == 0:
                    self._end_round("roo")
                    return

        # 出拳动画自动复位
        if getattr(self, "roo_punch_until", 0) and now >= self.roo_punch_until:
            self.sprite_r.set_state("idle")
            self.roo_punch_until = 0

# ==== C) AI decide (face -> move -> windup) & round/timer ====

    def _roo_step_back(self):
        # 被格挡后后撤一格（优先与面向相反的 X；不行则尝试 Y；再不行就不动）
        rx, ry = self.roo.pos
        step_x = -1 if self.r_face == R_FACE_RIGHT else 1
        tx, ty = rx + step_x, ry
        if not self._safe_move_roo(tx, ty):
            # try Y up/down
            if not self._safe_move_roo(rx, ry - 1):
                self._safe_move_roo(rx, ry + 1)

    def _ai_decide(self, now, dt_sec: float):
        """AI runs every frame: face -> (optionally) punch wind-up or follow."""
        # hitstop / block-stun pause
        if now < self.hitstop_until or now < getattr(self, "ai_pause_until", 0):
            return

        # stamina rest
        if self.st_r.cur < CFG.ROO_REST_THRESHOLD:
            self.st_r.cur = min(self.st_r.max, self.st_r.cur + CFG.ST_REGEN_PER_SEC_R * dt_sec)
            return

        rx, ry = self.roo.pos
        hx, hy = self.human.pos
        dx, dy = hx - rx, hy - ry

        # 1) always fix facing by X first
        need_face = R_FACE_RIGHT if dx >= 0 else R_FACE_LEFT
        if self.r_face != need_face:
            self._dbg(f"Face: {self._face_str(self.r_face)} -> {self._face_str(need_face)}")
            self._set_face(need_face)

        # respect toggles from config
        AI_FACE_ONLY = CFG.AI_TURN_ONLY_MODE
        AI_FOLLOW_EN = CFG.AI_ALLOW_MOVE
        AI_PUNCH_EN = CFG.AI_ALLOW_PUNCH

        # only-facing mode: stop here
        if AI_FACE_ONLY:
            return

        # 2) punch wind-up when adjacent on same row
        if (AI_PUNCH_EN and dy == 0 and abs(dx) == 1
                and now - self.last_punch_ms >= CFG.PUNCH_COOLDOWN_MS
                and not getattr(self, "intend_punch", False)):
            self.intend_punch = True
            self.punch_windup_until = now + CFG.PUNCH_WINDUP_MS
            self._dbg("Wind-up start")
            return  # hit check will be handled in the 'commit' section already in update()

        # 3) follow (try X first, else Y) every AI_DECIDE_EVERY_MS
        if AI_FOLLOW_EN and (now - self.last_ai_ms >= CFG.AI_DECIDE_EVERY_MS):
            self.last_ai_ms = now
            moved = False

            if dx != 0:
                tx = rx + (2 if dx > 0 else -2)
                self._dbg(f"FollowX: try ({tx},{ry})")
                moved = self._safe_move_roo(tx, ry)
                self._dbg("FollowX: moved" if moved else "FollowX: blocked")
                if not moved and dy != 0:
                    ty = ry + (2 if dy > 0 else -2)
                    self._dbg(f"FollowY(bk): try ({rx},{ty})")
                    moved = self._safe_move_roo(rx, ty)
                    self._dbg("FollowY: moved" if moved else "FollowY: blocked")
            elif dy != 0:
                ty = ry + (2 if dy > 0 else -2)
                self._dbg(f"FollowY: try ({rx},{ty})")
                moved = self._safe_move_roo(rx, ty)
                self._dbg("FollowY: moved" if moved else "FollowY: blocked")

            if moved:
                self.st_r.lose(CFG.ROO_JUMP_ST_DRAIN)
                self.sprite_r.set_state("jump")

    def _post_ai_regen(self, dt_sec):
        # 体力回蓝（Roo）
        if self.st_r.cur < self.st_r.max:
            self.st_r.cur = min(self.st_r.max, self.st_r.cur + CFG.ST_REGEN_PER_SEC_R * dt_sec)

    def _check_overlap_fix(self):
        # 避免同格重叠（如果发生，强制还原 Roo）
        if self.roo.pos == self.human.pos and self.roo_prev is not None:
            self.roo.pos = self.roo_prev

    def _end_round(self, winner: str):
        # winner: "roo" | "human" | "tie"
        if winner == "roo":
            self.popup_kind = "lose"
        elif winner == "human":
            self.popup_kind = "win"
        else:
            self.popup_kind = "tie"
        self.popup_until = pg.time.get_ticks() + 1200
        # 这里你可以路由到 end/score 屏；暂保持在本屏

    def _tick_round_timer(self, now):
        # 倒计时/加时 & 结束
        elapsed = (now - self.round_start) // 1000
        if elapsed >= CFG.ROUND_SECONDS:
            if self.overtime_started is None:
                self.overtime_started = now
            else:
                ot = (now - self.overtime_started) // 1000
                if ot >= 15:  # 固定 15s 加时
                    if self.hp_h.cur > 0:
                        self._end_round("human")
                    else:
                        self._end_round("roo")

    # === 更新（下半：AI & 计时） ===
    def update_after(self, dt_ms: int):
        now = pg.time.get_ticks()
        dt_sec = dt_ms / 1000.0

        # 体力阈值/暂停窗口检查在 _ai_decide 内
        self._ai_decide(now)
        self._post_ai_regen(dt_sec)
        self._check_overlap_fix()
        self._tick_round_timer(now)

    def _centers_face_to_face_snap(self, base_h_cxy, base_r_cxy):
        """
        输入：按 grid_center 得到的人与袋鼠中心 (cx,cy)
        输出：在同排相邻时，沿 X 方向把两者的“黄色 bbox”贴近（消掉视觉缝隙）的中心点。
        """
        hx, hy = self.human.pos
        rx, ry = self.roo.pos

        # 只处理同一行 & 相邻格
        if hy != ry or abs(hx - rx) != 1:
            return base_h_cxy, base_r_cxy

        # 计算当前帧下的 bbox（屏幕坐标）
        h_bbox = self.sprite_h.bbox_rect(base_h_cxy, flip_h=(self.h_face < 0))
        r_bbox = self.sprite_r.bbox_rect(base_r_cxy, flip_h=(self.r_face < 0))

        # 计算间隙：左人右roo 或 左roo右人
        # 约定 idx：左侧实体的 bbox.right 与 右侧实体的 bbox.left
        if hx < rx:
            gap = r_bbox.left - h_bbox.right
            left_is_human = True
        else:
            gap = h_bbox.left - r_bbox.right
            left_is_human = False

        # 仅在“gap>0（有缝）”时贴近；重叠或刚好相切不动
        if gap > 0:
            # 平分移动，留 1px 余量防止闪烁
            move_each = max(0, (gap - 1) // 2)
            if move_each > 0:
                if left_is_human:
                    base_h_cxy = (base_h_cxy[0] + move_each, base_h_cxy[1])
                    base_r_cxy = (base_r_cxy[0] - move_each, base_r_cxy[1])
                else:
                    base_h_cxy = (base_h_cxy[0] - move_each, base_h_cxy[1])
                    base_r_cxy = (base_r_cxy[0] + move_each, base_r_cxy[1])

        return base_h_cxy, base_r_cxy


# ==== D) draw ====
    def draw(self):
        s = self.m.screen
        now = pg.time.get_ticks()

        # 倒计时（含加时）
        secs_left = max(0, CFG.ROUND_SECONDS - (now - self.round_start) // 1000)
        if secs_left == 0 and self.overtime_started is not None:
            secs_left = max(0, 15 - (now - self.overtime_started) // 1000)

        # 顶栏
        draw_top_hud(
            s, self.W, self.H,
            halves_left_human=self.lives_halves,
            halves_left_roo=self.roo_halves,
            secs_left=secs_left,
            fonts=self.m.fonts,
            st_pct_h=self.st_h.pct,
            st_pct_r=self.st_r.pct,
            round_idx=self.round_idx, round_total=3,
        )

        # 棋盘
        full_rect = pg.Rect(0, HUD_H, self.W, self.H - HUD_H)
        draw_board(s, full_rect)

        # 可玩区域
        self.play_rect = compute_play_rect(self.W, self.H, hud_h=HUD_H, margin=8)

        # 精灵进度
        dt_ani = now - getattr(self, "_last_draw_tick", now)
        self._last_draw_tick = now

        self.sprite_h.set_state("block" if self.blocking else "idle")
        self.sprite_h.update(dt_ani)
        self.sprite_r.update(dt_ani)

        # 逐帧：先取“贴边后中心”，保证视觉无缝
        h_center, r_center = self._centers_screen()

        # 行排序（谁在下面谁在前）
        entities = [
            ("human", h_center, self.sprite_h, (self.h_face < 0)),
            ("roo",   r_center, self.sprite_r, (self.r_face > 0)),
        ]
        # 仍按网格的 y 排序（不变）
        entities.sort(key=lambda it: it[1][1])

        for _, cxy, spr, flip in entities:
            spr.draw(s, cxy, flip_h=flip)

        # Debug：看 bbox 与拳点
        if CFG.DEBUG:
            pg.draw.rect(s, (60, 200, 120), self.human_rect(h_center), 2)  # human bbox
            pg.draw.rect(s, (200, 170, 60),  self.roo_rect(r_center),   2)  # roo bbox
            fx, fy = self.sprite_r.fist_point(r_center, flip_h=(self.r_face > 0))
            pg.draw.circle(s, (230, 80, 80), (fx, fy), 5, 0)

        # 中央提示
        if now < getattr(self, "msg_until", 0) and getattr(self, "msg_text", ""):
            img = self.m.fonts["title"].render(self.msg_text, True, self.msg_color)
            s.blit(img, img.get_rect(center=self.play_rect.center))

        # 回合弹窗
        if getattr(self, "popup_until", 0) > now and getattr(self, "popup_kind", None):
            overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            s.blit(overlay, (0, 0))
            txt = {
                "tie": "Round Over",
                "win": "You Win",
                "lose": "You Lose",
            }.get(self.popup_kind, "Round")
            img = self.m.fonts["title"].render(txt, True, (255, 255, 255))
            s.blit(img, img.get_rect(center=self.play_rect.center))

# ==== helpers (punch condition) ====
def can_punch(roo_pos, human_pos, r_face) -> bool:
    rx, ry = roo_pos
    hx, hy = human_pos
    if ry != hy:
        return False
    dx = hx - rx
    if abs(dx) != 1:
        return False
    need = R_FACE_RIGHT if dx > 0 else R_FACE_LEFT
    return r_face == need
