# src/screen/screen_game.py
from __future__ import annotations
import pygame as pg
from src.config import CFG
from src.entities import Human, Kangaroo
from src.stamina import StaminaBar
from src.ui.board import compute_play_rect, draw_board, grid_center
from src.ui.hud import draw_top_hud, HUD_H
from src.sprites import make_people_sprite, make_roo_sprite

# ---- feature toggles from CFG ----
DEBUG_LOG = getattr(CFG, "DEBUG", False)
AI_FACE_ONLY       = getattr(CFG, "AI_TURN_ONLY_MODE", False)
AI_FOLLOW_ENABLED  = (getattr(CFG, "AI_ALLOW_MOVE", True)  and not AI_FACE_ONLY)
AI_PUNCH_ENABLED   = (getattr(CFG, "AI_ALLOW_PUNCH", True) and not AI_FACE_ONLY)

# ---- facing enum ----
R_FACE_LEFT  = -1
R_FACE_RIGHT =  1

# ---- timing aliases ----
MOVE_COOLDOWN_MS = getattr(CFG, "MOVE_COOLDOWN_MS", 110)
HITSTOP_MS       = getattr(CFG, "HITSTOP_MS", 120)

# ---- snap/spacing defaults (safe fallbacks) ----
CONTACT_MIN_Y_OVERLAP = getattr(CFG, "CONTACT_MIN_Y_OVERLAP", 24)
CONTACT_MAX_GAP_X     = getattr(CFG, "CONTACT_MAX_GAP_X", 0)       # allow tiny negative slit
SNAP_VERT_SLOP        = getattr(CFG, "SNAP_VERT_SLOP", 6)          # treat “same row” slack
SNAP_EXTRA_X          = getattr(CFG, "SNAP_EXTRA_X", 1)            # extra stickiness on X
BASELINE_MARGIN       = getattr(CFG, "BASELINE_MARGIN", 5)         # floor margin inside a cell
ROW_GAP_Y             = getattr(CFG, "ROW_GAP_Y", 6)               # min gap between two rows
ROW_TOP_PADDING       = getattr(CFG, "ROW_TOP_PADDING", 8)         # padding above top row

PUNCH_ANIM_MS         = getattr(CFG, "PUNCH_ANIM_MS", 320)
PUNCH_COOLDOWN_MS     = getattr(CFG, "PUNCH_COOLDOWN_MS", 650)
PUNCH_WINDUP_MS       = getattr(CFG, "PUNCH_WINDUP_MS", 200)
PUNCH_DAMAGE          = getattr(CFG, "PUNCH_DAMAGE", 12)
PUNCH_BLOCKED_DAMAGE  = getattr(CFG, "PUNCH_BLOCKED_DAMAGE", 3)

BLOCK_DRAIN_PER_SEC   = getattr(CFG, "BLOCK_DRAIN_PER_SEC", 22)
BLOCK_MIN_STAMINA     = getattr(CFG, "BLOCK_MIN_STAMINA", 8)
BLOCK_RECOVER_MS      = getattr(CFG, "BLOCK_RECOVER_MS", 260)
BLOCK_SHARED_LOSS     = getattr(CFG, "BLOCK_SHARED_LOSS", 6)

ST_REGEN_PER_SEC_H    = getattr(CFG, "ST_REGEN_PER_SEC_H", 12)
ST_REGEN_PER_SEC_R    = getattr(CFG, "ST_REGEN_PER_SEC_R", 12)
WALK_COST             = getattr(CFG, "WALK_COST", 3)
ROO_JUMP_ST_DRAIN     = getattr(CFG, "ROO_JUMP_ST_DRAIN", 5)
ROO_REST_THRESHOLD    = getattr(CFG, "ROO_REST_THRESHOLD", 12)

ROUND_SECONDS         = getattr(CFG, "ROUND_SECONDS", 45)

def _clamp(v, lo, hi): return max(lo, min(hi, v))


class GameScreen:
    """
    Grid-based duel (Human vs Roo).
    Key rules:
      - Human walks 1 cell; Roo jumps 2 cells (no pass-through, cannot land on human).
      - All collisions, fist anchors and rendering use the SAME baseline-aligned centers.
      - Visual adjacency uses tight yellow bboxes, not the old green/blue rectangles.
    """

    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # Entities
        self.human = Human(pos=(1, CFG.GRID_H // 2))
        self.roo   = Kangaroo(pos=(CFG.GRID_W - 2, CFG.GRID_H // 2))

        # HP / stamina
        self.hp_h = StaminaBar(getattr(CFG, "HUMAN_STAMINA", 100)); self.hp_h.reset()
        self.st_h = StaminaBar(getattr(CFG, "HUMAN_STAMINA", 100))
        self.st_r = StaminaBar(getattr(CFG, "ROO_STAMINA", 100))

        # Lives (half hearts)
        self.lives_halves = getattr(CFG, "HUMAN_HEARTS", 2) * 2
        self.roo_halves   = getattr(CFG, "ROO_HEARTS", 3)   * 2

        # Round/Timer
        self.round_idx   = 1
        self.round_start = pg.time.get_ticks()
        self.overtime_started = None

        # Runtime states
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

        # Logs
        self._dbg(f"Flags | face_only={AI_FACE_ONLY}  move={AI_FOLLOW_ENABLED}  punch={AI_PUNCH_ENABLED}")
        self.score_h = 0
        self.score_r = 0
        self.msg_text, self.msg_color, self.msg_until = "", (255,255,255), 0
        self.popup_kind, self.popup_until = None, 0

        # Layout & sprites
        self.play_rect = compute_play_rect(self.W, self.H, hud_h=HUD_H, margin=8)
        cell_w = self.play_rect.width  // CFG.GRID_W
        cell_h = self.play_rect.height // CFG.GRID_H
        self.sprite_h = make_people_sprite(cell_w, cell_h)
        self.sprite_r = make_roo_sprite(cell_w, cell_h)

        # Facing
        self.h_face = R_FACE_RIGHT
        self.r_face = R_FACE_LEFT
        self.roo_prev = self.roo.pos

        # Cached
        self._cell_w = cell_w
        self._cell_h = cell_h

        # SFX (optional)
        self.sfx = {}
        try: pg.mixer.init()
        except: pass

        # floating damage messages
        #self.float_msgs: list[dict] = []  # each: {"text": str, "color": (r,g,b), "pos": (x,y), "born": ms}

        self.float_msgs = []  # top-over-head popups
        self.debug_events = []  # bottom-right short logs

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

    def _spawn_float_msg(self, text, color, pos, ms=900):
        t = pg.time.get_ticks()
        self.float_msgs.append({
            # 新结构（上面的“rise and fade”用）
            "text": text,
            "color": color,
            "x": float(pos[0]),
            "y": float(pos[1]),
            "until": t + ms,
            # 兼容旧结构（避免 KeyError: 'born' / 'pos'）
            "born": t,
            "pos": (int(pos[0]), int(pos[1])),
        })

    # def _font(self, key: str, fallback_px: int = 24) -> pg.font.Font:
    #     """Safe font getter for HUD/float texts."""
    #     try:
    #         fdict = getattr(self.m, "fonts", {}) or {}
    #         if key in fdict and fdict[key]:
    #             return fdict[key]
    #     except Exception:
    #         pass
    #     # soft fallback
    #     try:
    #         return pg.font.SysFont(None, fallback_px)
    #     except Exception:
    #         # last resort: reuse title if present
    #         return getattr(self.m, "fonts", {}).get("title", pg.font.SysFont(None, 28))

    def _font(self, name, size_fallback=18):
        f = self.m.fonts.get(name)
        if f: return f
        return pg.font.SysFont(None, size_fallback)

    def _log_event(self, text, color=(230, 230, 230), ms=1400):
        self.debug_events.append({
            "text": text, "color": color,
            "until": pg.time.get_ticks() + ms
        })

    # -- hit test: only check horizontal adjacency (ignore Y) --
    def x_adjacent_touch(h_rect: pg.Rect, r_rect: pg.Rect, r_face: int) -> bool:
        """
        Return True if roo is facing human and their yellow boxes touch along X
        with a small tolerance. Y overlap is NOT required by design.
        - r_face < 0 : roo faces left  -> check human.right ~ roo.left
        - r_face > 0 : roo faces right -> check roo.right ~ human.left
        """
        tol = getattr(CFG, "CONTACT_MAX_GAP_X", 10)
        if r_face < 0:
            # roo looking left: human on roo's left side
            return abs(h_rect.right - r_rect.left) <= tol
        else:
            # roo looking right: human on roo's right side
            return abs(r_rect.right - h_rect.left) <= tol

    # =====================  Tight yellow bbox helpers  =====================

    def _frame_tight_bbox(self, sprite, center_xy, *, flip_h: bool) -> pg.Rect:
        """
        Tight bounding rect (non-transparent) of sprite's *current frame* in screen coords.
        """
        frame = sprite.current_frame()
        img = frame[0] if isinstance(frame, tuple) else frame
        if img is None:
            return pg.Rect(center_xy[0] - 1, center_xy[1] - 1, 2, 2)
        if flip_h:
            img = pg.transform.flip(img, True, False)
        blit = img.get_rect(center=center_xy)
        tight = img.get_bounding_rect(min_alpha=10)  # local
        tight.move_ip(blit.topleft)                  # -> screen
        return tight

    def _row_baseline_y(self, row: int) -> int:
        """Visual 'floor' Y for a given grid row."""
        cell_h = self.play_rect.height // CFG.GRID_H
        top = self.play_rect.top + row * cell_h
        return top + cell_h - BASELINE_MARGIN

    def _row_ceiling_y(self, row: int) -> int:
        """
        Visual ceiling Y for a given grid row so that two adjacent rows never overlap.
        For row 0 we use top padding; for others we keep a minimum ROW_GAP_Y from
        the previous row's baseline.
        """
        if row <= 0:
            return self.play_rect.top + ROW_TOP_PADDING
        return self._row_baseline_y(row - 1) - ROW_GAP_Y

    def _center_on_row_baseline(self, sprite, grid_pos: tuple[int, int], face_lr: int, *, is_roo: bool) -> tuple[int,int]:
        """
        Compute a screen center so the *tight* bbox:
          - bottom sits exactly on the row's baseline, and
          - top never crosses the row ceiling (prevents vertical overlap with the row above).
        This is used universally for: rendering, hit tests, and fist anchors.
        """
        cx, cy = grid_center(self.play_rect, *grid_pos)
        flip_h = (face_lr > 0) if is_roo else (face_lr < 0)

        # First align bottom to baseline
        rect0 = self._frame_tight_bbox(sprite, (cx, cy), flip_h=flip_h)
        baseline = self._row_baseline_y(grid_pos[1])
        dy = baseline - rect0.bottom
        cy1 = cy + dy

        # Then enforce ceiling constraint (no overlap with upper row)
        ceil_y = self._row_ceiling_y(grid_pos[1])
        rect1 = self._frame_tight_bbox(sprite, (cx, cy1), flip_h=flip_h)
        if rect1.top < ceil_y:
            cy1 += (ceil_y - rect1.top)  # push down just enough

        return (cx, cy1)

    # Public getters that optionally accept an override center (in screen space)
    def human_rect(self, center_override: tuple[int,int] | None = None) -> pg.Rect:
        cxy = center_override or self._center_on_row_baseline(self.sprite_h, self.human.pos, self.h_face, is_roo=False)
        return self._frame_tight_bbox(self.sprite_h, cxy, flip_h=(self.h_face < 0))

    def roo_rect(self, center_override: tuple[int,int] | None = None) -> pg.Rect:
        cxy = center_override or self._center_on_row_baseline(self.sprite_r, self.roo.pos, self.r_face, is_roo=True)
        return self._frame_tight_bbox(self.sprite_r, cxy, flip_h=(self.r_face > 0))

    def roo_fist_point(self) -> tuple[int,int]:
        """Pixel-accurate fist anchor (from JSON) using baseline-aligned center + proper flip."""
        center = self._center_on_row_baseline(self.sprite_r, self.roo.pos, self.r_face, is_roo=True)
        return self.sprite_r.fist_point(center, flip_h=(self.r_face > 0))

    def _human_yellow_rect_at(self, center_xy) -> pg.Rect:
        return self._frame_tight_bbox(self.sprite_h, center_xy, flip_h=(self.h_face < 0))

    def _roo_yellow_rect_at(self, center_xy) -> pg.Rect:
        return self._frame_tight_bbox(self.sprite_r, center_xy, flip_h=(self.r_face > 0))

    # Snap two characters along X so their yellow bboxes touch (no slit)
    def _centers_face_to_face_snap(self, base_h: tuple[int, int], base_r: tuple[int, int]):
        """
        Align yellow bboxes along X and Y to ensure:
          - If on same row → touch horizontally (like before)
          - If one above the other → touch vertically (no overlap)
        """
        h_rect = self._human_yellow_rect_at(base_h)
        r_rect = self._roo_yellow_rect_at(base_r)

        new_h = list(base_h)
        new_r = list(base_r)

        # --- horizontal snap ---
        horiz_gap = r_rect.left - h_rect.right if h_rect.centerx < r_rect.centerx else h_rect.left - r_rect.right
        if abs(h_rect.centery - r_rect.centery) <= getattr(CFG, "SNAP_VERT_SLOP", 6):
            # same row -> snap X (existing logic)
            if horiz_gap > 0:
                move = max(0, (horiz_gap - 1) // 2) + getattr(CFG, "SNAP_EXTRA_X", 1)
                if h_rect.centerx < r_rect.centerx:
                    new_h[0] += move
                    new_r[0] -= move
                else:
                    new_h[0] -= move
                    new_r[0] += move

        # --- vertical snap ---
        else:
            # human below roo → push human down
            if h_rect.top < r_rect.bottom and h_rect.centery > r_rect.centery:
                overlap = r_rect.bottom - h_rect.top
                if overlap > 0:
                    new_h[1] += overlap + 1
            # human above roo → push human up
            elif r_rect.top < h_rect.bottom and r_rect.centery > h_rect.centery:
                overlap = h_rect.bottom - r_rect.top
                if overlap > 0:
                    new_h[1] -= overlap + 1

        return tuple(new_h), tuple(new_r)

    def _centers_screen(self) -> tuple[tuple[int,int], tuple[int,int]]:
        """Return (human_center, roo_center) — baseline-aligned, ceiling-safe, then snapped along X."""
        base_h = self._center_on_row_baseline(self.sprite_h, self.human.pos, self.h_face, is_roo=False)
        base_r = self._center_on_row_baseline(self.sprite_r, self.roo.pos, self.r_face, is_roo=True)
        return self._centers_face_to_face_snap(base_h, base_r)

    # =====================  Facing helpers  =====================
    def _face_str(self, f): return "Right" if f == R_FACE_RIGHT else "Left"

    def _set_face(self, face):
        if face != self.r_face:
            self._dbg(f"Face: {self._face_str(self.r_face)} -> {self._face_str(face)}")
        self.r_face = face

    def _face_towards_player_x(self):
        rx, ry = self.roo.pos
        hx, hy = self.human.pos
        self._set_face(R_FACE_RIGHT if (hx - rx) >= 0 else R_FACE_LEFT)

    def _face_after_player_moved(self):
        rx, _ = self.roo.pos
        hx, _ = self.human.pos
        if hx > rx: self._set_face(R_FACE_RIGHT)
        elif hx < rx: self._set_face(R_FACE_LEFT)

    # =====================  Safe move for Roo  =====================
    def _safe_move_roo(self, tx, ty) -> bool:
        """No overlap, no pass-through; also updates facing by X."""
        rx, ry = self.roo.pos
        tx = _clamp(tx, 0, CFG.GRID_W - 1)
        ty = _clamp(ty, 0, CFG.GRID_H - 1)

        mid = (rx + (1 if tx > rx else -1 if tx < rx else 0),
               ry + (1 if ty > ry else -1 if ty < ry else 0))

        if mid == self.human.pos or (tx, ty) == self.human.pos:
            tx, ty = mid
            if (tx, ty) == self.human.pos:
                self._dbg("SafeMove: blocked by human, cancel")
                return False

        self.roo_prev = self.roo.pos
        self.roo.pos = (tx, ty)
        if tx > rx: self._set_face(R_FACE_RIGHT)
        if tx < rx: self._set_face(R_FACE_LEFT)
        self._dbg(f"SafeMove: to ({tx},{ty}), face {self._face_str(self.r_face)}")
        return True

    # =====================  Input  =====================
    def handle_event(self, e):
        """
        Handle only the keys we care about; ignore the rest safely.
        ESC -> push PauseScreen; SPACE -> hold block.
        """
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                self.m.push("pause")   # PauseScreen must be registered in manager
                return
            if e.key == pg.K_SPACE:
                self._set_blocking(True); return
            # ignore others
        elif e.type == pg.KEYUP:
            if e.key == pg.K_SPACE:
                self._set_blocking(False); return
            # ignore others

    def _set_blocking(self, on: bool):
        self.blocking = bool(on)
        # if on:
        #     self.last_block_down_ms = pg.time.get_ticks()
        if on:
            self.last_block_down_ms = pg.time.get_ticks()
            # 右下角提示（与 debug 分开显示）
            self.debug_events.append({
                "text": "You: BLOCK (holding)",
                "color": (210, 230, 255),
                "until": pg.time.get_ticks() + 1200,
                "kind": "hint",
            })
        else:
            self.debug_events.append({
                "text": "You: BLOCK release",
                "color": (210, 230, 255),
                "until": pg.time.get_ticks() + 900,
                "kind": "hint",
            })

    # =====================  Update  =====================
    def update(self, dt_ms: int):
        now = pg.time.get_ticks()

        # —— 回合弹窗期间：完全冻结逻辑 —— #
        if self.popup_until > now:
            return

        # —— 弹窗刚结束：启动下一回合/或结束比赛 —— #
        if self.popup_kind and self.popup_until <= now:
            # 清除弹窗标志
            self.popup_kind, self.popup_until = None, 0
            if self.round_idx < 3:
                # 进入下一回合
                self.round_idx += 1
                # 血量/体力恢复
                self.hp_h.reset()
                self.st_h.reset();
                self.st_r.reset()
                # 位置与朝向复位
                self.human.pos = (1, CFG.GRID_H // 2)
                self.roo.pos = (CFG.GRID_W - 2, CFG.GRID_H // 2)
                self.h_face = R_FACE_RIGHT
                self.r_face = R_FACE_LEFT
                # 清理临时渲染 & 重新计时
                self.float_msgs.clear()
                self.debug_events.clear()
                self.round_start = now
                self.overtime_started = None
                # 可选：给个开场短提示
                self._set_center_msg(f"Round {self.round_idx}", (255, 255, 255), ms=800)
            else:
                # 3 回合结束：比赛结束（先停住；如需跳转 EndScreen 可在此处调用）
                self._set_center_msg("Match Over", (255, 255, 255), ms=1800)
                # 停在“结束”状态：给一个很久的冻结
                self.popup_until = now + 10_000_000
                return

        # Hitstop keeps animation running via draw()
        if now < self.hitstop_until:
            return

        # Human stamina drain/regen
        dt_sec = dt_ms / 1000.0
        if self.blocking:
            self.st_h.lose(BLOCK_DRAIN_PER_SEC * dt_sec)
            if self.st_h.cur <= BLOCK_MIN_STAMINA:
                self._set_blocking(False)
        else:
            self.st_h.cur = min(self.st_h.max, self.st_h.cur + ST_REGEN_PER_SEC_H * dt_sec)

        # —— 回合倒计时判定 —— #
        elapsed_sec = (now - self.round_start) // 1000
        if elapsed_sec >= ROUND_SECONDS and self.popup_kind is None:
            # 简单胜负：人类还活着 → Win；否则 Lose；（你后续有人类出拳后可再细化判定）
            winner = "human" if (self.hp_h.cur > 0 and self.lives_halves > 0) else "roo"
            self._end_round(winner)
            return

        # Human move (continuous keyboard + cooldown + stamina)
        keys = pg.key.get_pressed()
        if now - self.last_move_ms >= MOVE_COOLDOWN_MS:
            hx, hy = self.human.pos
            nx, ny = hx, hy
            if keys[pg.K_UP]:    ny -= 1
            elif keys[pg.K_DOWN]: ny += 1
            elif keys[pg.K_LEFT]: nx -= 1; self.h_face = R_FACE_LEFT
            elif keys[pg.K_RIGHT]:nx += 1; self.h_face = R_FACE_RIGHT

            if (nx, ny) != (hx, hy) and self.human.can_move(nx, ny, roo_pos=self.roo.pos, cols=CFG.GRID_W, rows=CFG.GRID_H):
                if self.st_h.cur >= WALK_COST:
                    self.human.move_to(nx, ny)
                    self.st_h.lose(WALK_COST)
                    self.last_move_ms = now
                    self.last_human_step_ms = now
                    self._face_after_player_moved()

        # AI tick
        self._ai_decide(now, dt_sec)

        # Punch commit (single hit-check moment)
        if AI_PUNCH_ENABLED and getattr(self, "intend_punch", False) and now >= self.punch_windup_until:
            self.intend_punch = False

            prev = self.r_face
            self._face_towards_player_x()
            self._dbg(f"Punch commit face: {self._face_str(prev)} -> {self._face_str(self.r_face)}")

            self.sprite_r.set_state("punch")
            self.roo_punch_until = now + PUNCH_ANIM_MS
            self.last_punch_ms = now

            # Use the same snapped centers as drawing
            h_center, r_center = self._centers_screen()
            h_rect = self.human_rect(h_center)
            r_rect = self.roo_rect(r_center)

            hit_ok = can_punch_yellow(h_rect, r_rect, self.r_face)

            # Optional: also require the fist anchor to be inside target bbox
            if hit_ok and getattr(CFG, "REQUIRE_FIST_POINT", False):
                hit_ok = h_rect.collidepoint(self.sprite_r.fist_point(r_center, flip_h=(self.r_face > 0)))

            if not hit_ok:
                self.ai_pause_until = now + 220
                self._dbg("Punch result: WHIFF")
                self._log_event("Roo punch: miss", (200, 200, 200))
                return

            # BLOCK or HIT
            if self.blocking:
                self._dbg("Punch result: BLOCK")
                try:
                    self.sfx.get("block") and self.sfx["block"].play()
                except:
                    pass

                self.hp_h.lose(PUNCH_BLOCKED_DAMAGE)
                self.st_r.lose(BLOCK_SHARED_LOSS)
                self.st_h.lose(BLOCK_SHARED_LOSS * 0.5)

                pos = h_rect.midtop
                self._spawn_float_msg("BLOCK!", (230, 230, 230), (pos[0], pos[1] - 26))
                self._log_event("Roo punch → BLOCK", (230, 230, 230))

                self.hitstop_until = now + HITSTOP_MS
                self._roo_step_back()
                self.ai_pause_until = now + BLOCK_RECOVER_MS
                self.score_r += 1
                return

            # HIT
            self._dbg("Punch result: HIT")
            try:
                self.sfx.get("hit") and self.sfx["hit"].play()
            except:
                pass

            self.hp_h.lose(PUNCH_DAMAGE)
            pos = h_rect.midtop
            self._spawn_float_msg(f"-{PUNCH_DAMAGE} HP", (240, 80, 80), (pos[0], pos[1] - 20))
            self._log_event(f"Roo punch → HIT (-{PUNCH_DAMAGE})", (240, 120, 120))

            self.hitstop_until = now + HITSTOP_MS
            self.score_r += 1

            if self.hp_h.cur <= 0:
                self.lives_halves = max(0, self.lives_halves - 1)
                self.hp_h.reset()
                self._set_center_msg("- 1/2 ♥", (245, 120, 120), ms=900)
                self._dbg(f"Half-heart lost -> {self.lives_halves}")
                if self.lives_halves == 0:
                    self._end_round("roo")
                    return

        # Auto reset punch anim
        if getattr(self, "roo_punch_until", 0) and now >= self.roo_punch_until:
            self.sprite_r.set_state("idle")
            self.roo_punch_until = 0

    # =====================  AI & round/timer  =====================
    def _roo_step_back(self):
        """Step back after being blocked (prefer opposite X, fallback Y)."""
        rx, ry = self.roo.pos
        step_x = -1 if self.r_face == R_FACE_RIGHT else 1
        if not self._safe_move_roo(rx + step_x, ry):
            if not self._safe_move_roo(rx, ry - 1):
                self._safe_move_roo(rx, ry + 1)

    def _ai_decide(self, now, dt_sec: float):
        """AI every frame: face → (maybe) wind-up punch → (else) follow."""
        if now < self.hitstop_until or now < getattr(self, "ai_pause_until", 0):
            return

        if self.st_r.cur < ROO_REST_THRESHOLD:
            self.st_r.cur = min(self.st_r.max, self.st_r.cur + ST_REGEN_PER_SEC_R * dt_sec)
            return

        rx, ry = self.roo.pos
        hx, hy = self.human.pos
        dx, dy = hx - rx, hy - ry

        need_face = R_FACE_RIGHT if dx >= 0 else R_FACE_LEFT
        if self.r_face != need_face:
            self._set_face(need_face)

        if AI_FACE_ONLY:
            return

        # Wind-up if visually adjacent on same row (guard: do not re-start if already winding)
        if (AI_PUNCH_ENABLED
                and (now - self.last_punch_ms >= PUNCH_COOLDOWN_MS)
                and not getattr(self, "intend_punch", False)
                and now >= getattr(self, "ai_pause_until", 0)):
            h_center, r_center = self._centers_screen()
            h_rect = self.human_rect(h_center)
            r_rect = self.roo_rect(r_center)
            if can_punch_yellow(h_rect, r_rect, self.r_face):
                self.intend_punch = True
                self.punch_windup_until = now + PUNCH_WINDUP_MS
                self._dbg("Wind-up start")
                self._log_event("Roo wind-up", (200, 200, 255))
                return

        # Follow (prefer X, else Y)
        if AI_FOLLOW_ENABLED and (now - self.last_ai_ms >= getattr(CFG, "AI_DECIDE_EVERY_MS", 120)):
            self.last_ai_ms = now
            moved = False
            if dx != 0:
                moved = self._safe_move_roo(rx + (2 if dx > 0 else -2), ry)
            elif dy != 0:
                moved = self._safe_move_roo(rx, ry + (2 if dy > 0 else -2))
            if moved:
                self.st_r.lose(ROO_JUMP_ST_DRAIN)
                self.sprite_r.set_state("jump")

    def _end_round(self, winner: str):
        self.popup_kind = {"roo": "lose", "human": "win"}.get(winner, "tie")
        self.popup_until = pg.time.get_ticks() + 1200

    # =====================  Draw  =====================
    def draw(self):
        s = self.m.screen
        now = pg.time.get_ticks()

        # Timer (incl. overtime)
        secs_left = max(0, ROUND_SECONDS - (now - self.round_start) // 1000)
        if secs_left == 0 and self.overtime_started is not None:
            secs_left = max(0, 15 - (now - self.overtime_started) // 1000)

        # HUD
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

        # Board
        full_rect = pg.Rect(0, HUD_H, self.W, self.H - HUD_H)
        draw_board(s, full_rect)

        # Play rect (recompute in case of resize)
        self.play_rect = compute_play_rect(self.W, self.H, hud_h=HUD_H, margin=8)

        # Advance sprites
        dt_ani = now - getattr(self, "_last_draw_tick", now)
        self._last_draw_tick = now
        self.sprite_h.set_state("block" if self.blocking else "idle")
        self.sprite_h.update(dt_ani)
        self.sprite_r.update(dt_ani)

        # Centers: baseline-aligned then snapped along X
        h_center, r_center = self._centers_screen()

        # Draw with row-order painter's algorithm
        entities = [
            ("human", h_center, self.sprite_h, (self.h_face < 0)),
            ("roo",   r_center, self.sprite_r, (self.r_face > 0)),
        ]
        entities.sort(key=lambda it: it[1][1])  # lower first
        for _, cxy, spr, flip in entities:
            spr.draw(s, cxy, flip_h=flip)

        # floating texts (rise and fade)
        now = pg.time.get_ticks()
        small = self._font("small", 18)
        alive = []
        for itm in self.float_msgs:
            if now >= itm["until"]:
                continue
            itm["y"] -= 0.25  # drift up
            img = small.render(itm["text"], True, itm["color"])
            self.m.screen.blit(img, img.get_rect(center=(int(itm["x"]), int(itm["y"]))))
            alive.append(itm)
        self.float_msgs = alive

        # Debug overlays (always use same centers as rendering)
        if getattr(CFG, "DEBUG", False):
            h_bbox = self.human_rect(h_center)
            r_bbox = self.roo_rect(r_center)
            pg.draw.rect(s, (47, 213, 102), h_bbox, 2)   # human (greenish)
            pg.draw.rect(s, (244, 204, 47),  r_bbox, 2)  # roo (yellow)
            fx, fy = self.sprite_r.fist_point(r_center, flip_h=(self.r_face > 0))
            pg.draw.circle(s, (230, 80, 80), (fx, fy), 5, 0)

        # Center message（含 ♥ 的回退字库）
        if now < self.msg_until and self.msg_text:
            text = self.msg_text
            font = self.m.fonts["title"]
            # 如果包含 ♥，尝试用包含符号的系统字库临时渲染
            if "♥" in text:
                try:
                    # 取与 title 大致相同字号
                    size_guess = font.get_height()
                    sym = pg.font.SysFont("Segoe UI Symbol", size_guess) or pg.font.SysFont("Arial Unicode MS",
                                                                                            size_guess)
                    img = sym.render(text, True, self.msg_color)
                except Exception:
                    img = font.render(text, True, self.msg_color)
            else:
                img = font.render(text, True, self.msg_color)
            s.blit(img, img.get_rect(center=self.play_rect.center))

        # bottom-right debug event log
        alive = []
        x = self.W - 18
        y = self.H - 14
        for itm in reversed(self.debug_events[-6:]):  # last few lines
            if now < itm["until"]:
                img = small.render(itm["text"], True, itm["color"])
                r = img.get_rect(bottomright=(x, y))
                self.m.screen.blit(img, r)
                y -= r.height + 4
                alive.append(itm)
        self.debug_events = [e for e in self.debug_events if now < e["until"]]

        # Round popup
        if self.popup_until > now and self.popup_kind:
            overlay = pg.Surface((self.W, self.H), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            s.blit(overlay, (0, 0))
            txt = {"tie": "Round Over", "win": "You Win", "lose": "You Lose"}.get(self.popup_kind, "Round")
            img = self.m.fonts["title"].render(txt, True, (255, 255, 255))
            s.blit(img, img.get_rect(center=self.play_rect.center))


# =====================  Helpers  =====================
def can_punch_yellow(h_rect: pg.Rect, r_rect: pg.Rect, r_face: int) -> bool:
    """
    X-only adjacency for hit confirm.
    We only require that the two tight yellow boxes *touch* horizontally
    in the facing direction, with a small tolerance. No Y-overlap check.
      - r_face > 0 (right): roo.right ~ human.left
      - r_face < 0 (left) : human.right ~ roo.left
    Tolerance can be tuned with CFG.CONTACT_MAX_GAP_X (default 8).
    """
    tol = getattr(CFG, "CONTACT_MAX_GAP_X", 8)  # allow tiny slit/overdraw

    if r_face > 0:
        # Roo faces right -> human must be on its right side
        gap = h_rect.left - r_rect.right
        return abs(gap) <= tol
    else:
        # Roo faces left -> human must be on its left side
        gap = r_rect.left - h_rect.right
        return abs(gap) <= tol

