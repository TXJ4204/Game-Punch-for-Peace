# ==== A) imports / constants / helpers / __init__ ====
from __future__ import annotations
import pygame as pg
from src.config import CFG
from src.entities import Human, Kangaroo
from src.stamina import StaminaBar
from src.ui.board import compute_play_rect, draw_board, grid_center
from src.ui.hud import draw_top_hud, HUD_H
from src.sprites import make_people_sprite, make_roo_sprite

# ---- feature switches（便于分步联调） ----
DEBUG_LOG = True
AI_FACE_ONLY = True        # 先只做“面向对齐”；确认无误再关掉它
AI_FOLLOW_ENABLED = True   # 允许追随移动
AI_PUNCH_ENABLED = True    # 允许出拳全流程（含蓄力→命中判定）

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

    def human_rect(self):
        return self._rect_at(self.human.pos)

    def roo_rect(self):
        return self._rect_at(self.roo.pos)

    def roo_fist_point(self):
        r = self.roo_rect()
        y = int(r.top + 0.40 * r.height)
        pad = max(2, int(0.05 * r.width))
        x = r.right - pad if self.r_face == R_FACE_RIGHT else r.left + pad
        return (x, y)

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
        if now - self.last_move_ms >= MOVE_COOLDOWN_MS:
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

            # 命中条件：同一行相邻 + 面向正确 + 拳点进命中盒
            hit_ok = can_punch(self.roo.pos, self.human.pos, self.r_face)
            if hit_ok:
                hit_ok = self.human_rect().collidepoint(self.roo_fist_point())

            # 闪避保护
            if hit_ok and (now - getattr(self, "last_human_step_ms", -999999)) <= CFG.EVADE_GRACE_MS:
                hit_ok = False
                self._dbg("Hit test: evaded by recent move")

            if not hit_ok:
                self.ai_pause_until = now + 220
                self._dbg("Punch result: whiff -> short pause")
                return

            # 命中三分支
            parry = self.blocking and (0 <= (now - self.last_block_down_ms) <= CFG.PARRY_WINDOW_MS)
            if parry:
                self._dbg("Punch result: PARRY")
                try: self.sfx.get("block", None) and self.sfx["block"].play()
                except: pass
                self._set_center_msg("PARRY!", (240,255,240))
                self.st_r.lose(CFG.PUNCH_DAMAGE * 0.6)
                self.hitstop_until = now + HITSTOP_MS
                self._roo_step_back()
                self.ai_pause_until = now + (CFG.BLOCK_RECOVER_MS + 160)
                return

            if self.blocking:
                self._dbg("Punch result: BLOCK")
                try: self.sfx.get("block", None) and self.sfx["block"].play()
                except: pass
                self.hp_h.lose(CFG.PUNCH_BLOCKED_DAMAGE)
                self.st_r.lose(CFG.BLOCK_SHARED_LOSS)
                self.st_h.lose(CFG.BLOCK_SHARED_LOSS * 0.5)
                self._set_center_msg("BLOCK!", (230,230,230))
                self.hitstop_until = now + HITSTOP_MS
                self._roo_step_back()
                self.ai_pause_until = now + CFG.BLOCK_RECOVER_MS
                self.score_r += 1
                return

            # 直击
            self._dbg("Punch result: HIT")
            try: self.sfx.get("hit", None) and self.sfx["hit"].play()
            except: pass
            self.hp_h.lose(CFG.PUNCH_DAMAGE)
            self._set_center_msg(f"-{CFG.PUNCH_DAMAGE} HP", (240,120,120))
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

    def _ai_decide(self, now):
        # 命中硬直/被格挡暂停 → 不行动
        if now < self.hitstop_until or now < self.ai_pause_until:
            return

        # 体力不足 → 休息
        if self.st_r.cur < CFG.ROO_REST_THRESHOLD:
            return

        if now - self.last_ai_ms < CFG.AI_DECIDE_EVERY_MS:
            return
        self.last_ai_ms = now

        rx, ry = self.roo.pos
        hx, hy = self.human.pos
        dx, dy = hx - rx, hy - ry

        # 1) 先转向（仅看 X；哪怕相等也不妨再次对齐一次）
        need_face = R_FACE_RIGHT if dx >= 0 else R_FACE_LEFT
        if self.r_face != need_face:
            self._set_face(need_face)
            # 面向调整后立即可见（draw 会逐帧翻转）
            if AI_FACE_ONLY:
                self._dbg(f"AI face-only: to {self._face_str(self.r_face)}")
                return  # face-only 模式下直接返回

        # 2) 移动（可开关）
        if AI_FOLLOW_ENABLED and (dx != 0 or dy != 0):
            # 优先 X 轴移动 2 格；失败再尝试 Y
            moved = False
            if dx != 0:
                step = 2 if dx > 0 else -2
                moved = self._safe_move_roo(rx + step, ry)
                if moved:
                    self.st_r.lose(CFG.ROO_JUMP_ST_DRAIN)
                    self.sprite_r.set_state("jump")
                else:
                    # 试试 Y
                    if dy != 0:
                        step_y = 2 if dy > 0 else -2
                        moved = self._safe_move_roo(rx, ry + step_y)
                        if moved:
                            self.st_r.lose(CFG.ROO_JUMP_ST_DRAIN)
                            self.sprite_r.set_state("jump")
            else:
                # dx==0，尝试 Y
                step_y = 2 if dy > 0 else -2
                moved = self._safe_move_roo(rx, ry + step_y)
                if moved:
                    self.st_r.lose(CFG.ROO_JUMP_ST_DRAIN)
                    self.sprite_r.set_state("jump")

        # 3) 进入蓄力（仅当相邻、朝向正确、冷却好）
        if AI_PUNCH_ENABLED:
            rx, ry = self.roo.pos
            hx, hy = self.human.pos
            dx, dy = hx - rx, hy - ry
            if dy == 0 and abs(dx) == 1 and (now - self.last_punch_ms >= CFG.PUNCH_COOLDOWN_MS):
                need = R_FACE_RIGHT if dx > 0 else R_FACE_LEFT
                if self.r_face != need:
                    self._set_face(need)
                self.intend_punch = True
                self.punch_windup_until = now + CFG.PUNCH_WINDUP_MS
                self._dbg(f"Windup: {CFG.PUNCH_WINDUP_MS}ms")

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

        # 逐帧翻转（立即可见）
        self.sprite_h.draw(
            s, grid_center(self.play_rect, *self.human.pos),
            flip_h=(self.h_face == R_FACE_LEFT),
        )
        self.sprite_r.draw(
            s, grid_center(self.play_rect, *self.roo.pos),
            flip_h=(self.r_face == R_FACE_LEFT),
        )

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
