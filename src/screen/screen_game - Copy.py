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
DEBUG_LOG = CFG.DEBUG
AI_FACE_ONLY       = CFG.AI_TURN_ONLY_MODE
AI_FOLLOW_ENABLED  = (CFG.AI_ALLOW_MOVE  and not CFG.AI_TURN_ONLY_MODE)
AI_PUNCH_ENABLED   = (CFG.AI_ALLOW_PUNCH and not CFG.AI_TURN_ONLY_MODE)

# ---- facing enum ----
R_FACE_LEFT  = -1
R_FACE_RIGHT =  1

# ---- timing aliases ----
MOVE_COOLDOWN_MS = CFG.MOVE_COOLDOWN_MS
HITSTOP_MS       = CFG.HITSTOP_MS


def _clamp(v, lo, hi): return max(lo, min(hi, v))


class GameScreen:
    """
    Grid-based duel (Human vs Roo).
    Design rules:
      - Human walks 1 cell (4-neighborhood).
      - Roo jumps 2 cells (no pass-through and cannot land on human).
      - Punch only when on the same row and visually adjacent (using tight yellow bboxes).
      - All collision & fist anchors use the *same* baseline-aligned centers as rendering.
    """

    def __init__(self, manager):
        self.m = manager
        self.W, self.H = manager.size

        # Entities
        self.human = Human(pos=(1, CFG.GRID_H // 2))
        self.roo   = Kangaroo(pos=(CFG.GRID_W - 2, CFG.GRID_H // 2))

        # Bars
        self.hp_h = StaminaBar(CFG.HUMAN_STAMINA)  # reuse as HP
        self.st_h = StaminaBar(CFG.HUMAN_STAMINA)  # stamina (human)
        self.hp_h.reset()
        self.st_r = StaminaBar(CFG.ROO_STAMINA)    # stamina (roo)

        # Lives (half-hearts)
        self.lives_halves = CFG.HUMAN_HEARTS * 2
        self.roo_halves   = CFG.ROO_HEARTS   * 2

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

        # Score / msg
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

        # Cached dims
        self._cell_w = cell_w
        self._cell_h = cell_h

        # SFX (optional)
        self.sfx = {}
        try: pg.mixer.init()
        except: pass

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

    # --- helpers: tight yellow bbox at a given screen center -----------------
    def _human_yellow_rect_at(self, center_xy) -> pg.Rect:
        """Tight yellow bbox of human at a specific screen center (uses current frame)."""
        return self._frame_tight_bbox(self.sprite_h, center_xy, flip_h=(self.h_face < 0))

    def _roo_yellow_rect_at(self, center_xy) -> pg.Rect:
        """Tight yellow bbox of roo at a specific screen center (uses current frame)."""
        return self._frame_tight_bbox(self.sprite_r, center_xy, flip_h=(self.r_face > 0))  # roo faces right => flipped

    # keep the simple "current center" getters (backward compatibility)
    def _human_yellow_rect(self) -> pg.Rect:
        c = grid_center(self.play_rect, *self.human.pos)
        return self._frame_tight_bbox(self.sprite_h, c, flip_h=(self.h_face < 0))

    def _roo_yellow_rect(self) -> pg.Rect:
        c = grid_center(self.play_rect, *self.roo.pos)
        return self._frame_tight_bbox(self.sprite_r, c, flip_h=(self.r_face > 0))  # roo faces right => flipped

    # public helpers used by draw/debug/ai; can receive an override center
    def human_rect(self, center_xy: tuple[int, int] | None = None) -> pg.Rect:
        """Tight yellow bbox of human (optionally at a given screen center)."""
        if center_xy is None:
            center_xy = grid_center(self.play_rect, *self.human.pos)
        return self._frame_tight_bbox(self.sprite_h, center_xy, flip_h=(self.h_face < 0))

    def roo_rect(self, center_xy: tuple[int, int] | None = None) -> pg.Rect:
        """Tight yellow bbox of roo (optionally at a given screen center)."""
        if center_xy is None:
            center_xy = grid_center(self.play_rect, *self.roo.pos)
        return self._frame_tight_bbox(self.sprite_r, center_xy, flip_h=(self.r_face > 0))  # roo faces right => flipped

    # =====================  Tight yellow bbox path  =====================

    def _frame_tight_bbox(self, sprite, center_xy, *, flip_h: bool) -> pg.Rect:
        """
        Return the tight bounding rect (non-transparent) of the sprite's *current frame*
        in screen coordinates, using the given center and horizontal flip.
        """
        frame = sprite.current_frame()
        img = frame[0] if isinstance(frame, tuple) else frame
        if img is None:
            return pg.Rect(center_xy[0] - 1, center_xy[1] - 1, 2, 2)
        if flip_h:
            img = pg.transform.flip(img, True, False)
        blit = img.get_rect(center=center_xy)
        tight = img.get_bounding_rect(min_alpha=10)  # image-local
        tight.move_ip(blit.topleft)                  # to screen space
        return tight

    def _row_baseline_y(self, row: int) -> int:
        """Visual 'floor' Y for a given grid row (keeps vertical collisions consistent)."""
        cell_h = self.play_rect.height // CFG.GRID_H
        top = self.play_rect.top + row * cell_h
        return top + cell_h - CFG.BASELINE_MARGIN  # e.g., 4~6 px

    def _center_on_row_baseline(self, sprite, grid_pos: tuple[int, int], face_lr: int, *, is_roo: bool) -> tuple[int,int]:
        """
        Compute a screen center so the *tight* bbox bottom sits exactly on the row's baseline.
        This is used by: rendering, collisions, and fist anchors.
        """
        cx, cy = grid_center(self.play_rect, *grid_pos)
        flip_h = (face_lr > 0) if is_roo else (face_lr < 0)  # your sprite flip rule
        rect0 = self._frame_tight_bbox(sprite, (cx, cy), flip_h=flip_h)
        baseline = self._row_baseline_y(grid_pos[1])
        dy = baseline - rect0.bottom
        return (cx, cy + dy)

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

    def _centers_face_to_face_snap(self, base_h: tuple[int, int], base_r: tuple[int, int]):
        """
        Snap two characters visually edge-to-edge using their *yellow* tight bboxes.
        - Uses vertical slop to still treat them as same row (CFG.SNAP_VERT_SLOP).
        - Uses extra overlap pixels (CFG.SNAP_EXTRA_X) to remove any tiny gap.
        Returns (human_center, roo_center) in *screen* coords.
        """
        hx, hy = base_h;
        rx, ry = base_r
        h_rect = self._human_yellow_rect_at(base_h)
        r_rect = self._roo_yellow_rect_at(base_r)

        vert_slop = getattr(CFG, "SNAP_VERT_SLOP", 6)
        same_row = abs(h_rect.centery - r_rect.centery) <= vert_slop
        if not same_row:
            return base_h, base_r

        extra = getattr(CFG, "SNAP_EXTRA_X", 1)

        # human on the left
        if h_rect.centerx <= r_rect.centerx:
            gap = r_rect.left - h_rect.right  # >0 means a visible gap
            if gap > 0:
                move_each = max(0, (gap - 1) // 2) + extra
                h_c = (h_rect.centerx + move_each, h_rect.centery)
                r_c = (r_rect.centerx - move_each, r_rect.centery)
                return h_c, r_c
            return base_h, base_r

        # human on the right
        gap = h_rect.left - r_rect.right
        if gap > 0:
            move_each = max(0, (gap - 1) // 2) + extra
            h_c = (h_rect.centerx - move_each, h_rect.centery)
            r_c = (r_rect.centerx + move_each, r_rect.centery)
            return h_c, r_c
        return base_h, base_r

    def _centers_screen(self) -> tuple[tuple[int,int], tuple[int,int]]:
        """Return (human_center, roo_center) — baseline-aligned then snapped along X."""
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
        # Only handle keys we care; ignore all others safely.
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                # push a pause overlay; input will be captured by PauseScreen
                self.m.push("pause")
                return
            if e.key == pg.K_SPACE:
                self._set_blocking(True)
                return
            # ignore all other keys
        elif e.type == pg.KEYUP:
            if e.key == pg.K_SPACE:
                self._set_blocking(False)
                return
            # ignore others

    def _set_blocking(self, on: bool):
        self.blocking = bool(on)
        if on:
            self.last_block_down_ms = pg.time.get_ticks()

    # =====================  Update (upper half)  =====================
    def update(self, dt_ms: int):
        now = pg.time.get_ticks()

        # Hitstop keeps animation running via draw()
        if now < self.hitstop_until:
            return

        # Human stamina drain/regen
        dt_sec = dt_ms / 1000.0
        if self.blocking:
            self.st_h.lose(CFG.BLOCK_DRAIN_PER_SEC * dt_sec)
            if self.st_h.cur <= CFG.BLOCK_MIN_STAMINA:
                self._set_blocking(False)
        else:
            self.st_h.cur = min(self.st_h.max, self.st_h.cur + CFG.ST_REGEN_PER_SEC_H * dt_sec)

        # Human move (continuous keyboard, cooldown + stamina)
        keys = pg.key.get_pressed()
        if now - self.last_move_ms >= MOVE_COOLDOWN_MS:
            hx, hy = self.human.pos
            nx, ny = hx, hy

            if keys[pg.K_UP]:    ny -= 1
            elif keys[pg.K_DOWN]: ny += 1
            elif keys[pg.K_LEFT]: nx -= 1; self.h_face = R_FACE_LEFT
            elif keys[pg.K_RIGHT]:nx += 1; self.h_face = R_FACE_RIGHT

            if (nx, ny) != (hx, hy) and self.human.can_move(nx, ny, roo_pos=self.roo.pos, cols=CFG.GRID_W, rows=CFG.GRID_H):
                if self.st_h.cur >= CFG.WALK_COST:
                    self.human.move_to(nx, ny)
                    self.st_h.lose(CFG.WALK_COST)
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

            # Anim time stamps
            self.sprite_r.set_state("punch")
            self.roo_punch_until = now + CFG.PUNCH_ANIM_MS
            self.last_punch_ms = now

            # Hit test: same-row adjacency by yellow bboxes (+ tiny negative gap allowed)
            h_rect = self.human_rect()
            r_rect = self.roo_rect()
            hit_ok = can_punch_yellow(h_rect, r_rect, self.r_face)
            # Optional extra: fist point must also land inside human yellow bbox
            if hit_ok:
                hit_ok = h_rect.collidepoint(self.roo_fist_point())

            # Evade grace after human just moved
            if hit_ok and (now - getattr(self, "last_human_step_ms", -999999)) <= CFG.EVADE_GRACE_MS:
                hit_ok = False
                self._dbg("Hit test: evaded by recent move")

            if not hit_ok:
                self.ai_pause_until = now + 220
                self._dbg("Punch result: whiff -> short pause")
                return

            # BLOCK or HIT (simplified)
            if self.blocking:
                self._dbg("Punch result: BLOCK")
                try: self.sfx.get("block") and self.sfx["block"].play()
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

            # Direct hit
            self._dbg("Punch result: HIT")
            try: self.sfx.get("hit") and self.sfx["hit"].play()
            except: pass
            self.hp_h.lose(CFG.PUNCH_DAMAGE)
            self._set_center_msg(f"-{CFG.PUNCH_DAMAGE} HP", (240,120,120))
            self.hitstop_until = now + HITSTOP_MS
            self.score_r += 1

            # Half-heart check
            if self.hp_h.cur <= 0:
                self.lives_halves = max(0, self.lives_halves - 1)
                self.hp_h.reset()
                self._set_center_msg("- 1/2 ♥", (245,120,120), ms=900)
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

        # Roo stamina idle regen gate
        if self.st_r.cur < CFG.ROO_REST_THRESHOLD:
            self.st_r.cur = min(self.st_r.max, self.st_r.cur + CFG.ST_REGEN_PER_SEC_R * dt_sec)
            return

        rx, ry = self.roo.pos
        hx, hy = self.human.pos
        dx, dy = hx - rx, hy - ry

        # Always face player by X first
        need_face = R_FACE_RIGHT if dx >= 0 else R_FACE_LEFT
        if self.r_face != need_face:
            self._set_face(need_face)

        if CFG.AI_TURN_ONLY_MODE:
            return

        # Wind-up if visually adjacent on same row
        h_rect = self.human_rect()
        r_rect = self.roo_rect()
        if CFG.AI_ALLOW_PUNCH and can_punch_yellow(h_rect, r_rect, self.r_face) and (now - self.last_punch_ms >= CFG.PUNCH_COOLDOWN_MS):
            self.intend_punch = True
            self.punch_windup_until = now + CFG.PUNCH_WINDUP_MS
            self._dbg("Wind-up start")
            return  # commit in update()

        # Follow (prefer X, else Y)
        if CFG.AI_ALLOW_MOVE and (now - self.last_ai_ms >= CFG.AI_DECIDE_EVERY_MS):
            self.last_ai_ms = now
            moved = False
            if dx != 0:
                moved = self._safe_move_roo(rx + (2 if dx > 0 else -2), ry)
            elif dy != 0:
                moved = self._safe_move_roo(rx, ry + (2 if dy > 0 else -2))
            if moved:
                self.st_r.lose(CFG.ROO_JUMP_ST_DRAIN)
                self.sprite_r.set_state("jump")

    def _end_round(self, winner: str):
        self.popup_kind = {"roo": "lose", "human": "win"}.get(winner, "tie")
        self.popup_until = pg.time.get_ticks() + 1200

    # =====================  Draw  =====================
    def draw(self):
        s = self.m.screen
        now = pg.time.get_ticks()

        # Timer (incl. overtime)
        secs_left = max(0, CFG.ROUND_SECONDS - (now - self.round_start) // 1000)
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

        # Debug overlays (always use same centers as rendering)
        if CFG.DEBUG:
            h_bbox = self.human_rect(h_center)
            r_bbox = self.roo_rect(r_center)
            pg.draw.rect(s, (47, 213, 102), h_bbox, 2)   # human (greenish)
            pg.draw.rect(s, (244, 204, 47),  r_bbox, 2)  # roo (yellow)
            fx, fy = self.sprite_r.fist_point(r_center, flip_h=(self.r_face > 0))
            pg.draw.circle(s, (230, 80, 80), (fx, fy), 5, 0)

        # Center message
        if now < self.msg_until and self.msg_text:
            img = self.m.fonts["title"].render(self.msg_text, True, self.msg_color)
            s.blit(img, img.get_rect(center=self.play_rect.center))

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
    Visual adjacency using *tight* yellow bboxes:
      - Require minimum vertical overlap (CONFIG: CONTACT_MIN_Y_OVERLAP).
      - Allow a tiny negative horizontal gap to remove the visible slit (CONTACT_MAX_GAP_X ≤ 0).
    """
    y_overlap = max(0, min(h_rect.bottom, r_rect.bottom) - max(h_rect.top, r_rect.top))
    if y_overlap < CFG.CONTACT_MIN_Y_OVERLAP:
        return False
    if r_face > 0:   # roo faces right → human must be on roo's right
        gap = h_rect.left - r_rect.right
    else:            # roo faces left → human must be on roo's left
        gap = r_rect.left - h_rect.right
    return gap <= CFG.CONTACT_MAX_GAP_X
