# src/config.py
from dataclasses import dataclass

@dataclass
class _CFG:
    # --- Grid & Colors (named) ---
    GRID_W: int = 8
    GRID_H: int = 5

    # global UI palette
    COL_TEXT: tuple = (255, 255, 255)
    COL_BG:   tuple = (230, 233, 238)     # HUD background
    COL_GRID_LIGHT: tuple = (62, 68, 78)  # board light
    COL_GRID_DARK:  tuple = (48, 54, 63)  # board dark

    # config.py 里的 CFG 颜色建议
    COL_PANEL_BG = (55, 60, 70)
    COL_PANEL_OUTLINE = (25, 28, 34)
    COL_PANEL_OUTLINE_HI = (70, 130, 200)  # 选中边框蓝
    COL_TEXT02 = (230, 235, 238)
    COL_TIP = (190, 190, 195)
    COL_ICON_SINGLE = (80, 160, 240)
    COL_ICON_MULTI = (150, 150, 160)

    COL_CONFIRM_FILL = (80, 140, 200)
    COL_CONFIRM_TEXT = (245, 247, 250)
    COL_CONFIRM_BORDER = (22, 30, 38)
    COL_CONFIRM_FILL_DIS = (128, 128, 132)
    COL_CONFIRM_TEXT_DIS = (20, 20, 22)
    COL_CONFIRM_BORDER_DIS = (35, 35, 38)

    # Backward-compat
    TEXT: tuple = COL_TEXT
    BG:   tuple = COL_BG
    GRID_LIGHT: tuple = COL_GRID_LIGHT
    GRID_DARK:  tuple = COL_GRID_DARK

    # --- Hitbox config ---
    HITBOX_MODE = "bbox"  # "bbox" | "parts" | "mask"，本次用 bbox（黄色框）
    HITBOX_JSON = "assets/animation/hitbox_meta.json"

    # --- Debug draw toggles ---
    SHOW_BBOX = True  # 画黄色紧外接框
    SHOW_PARTS = False  # 关掉绿色小块
    SHOW_MASK = False  # 暂不渲染多边形

    # --- Gameplay timing ---
    FPS: int = 60
    ROUND_SECONDS: int = 45

    # Evade & combat
    EVADE_GRACE_MS: int = 120
    PARRY_WINDOW_MS: int = 120
    BLOCK_RECOVER_MS: int = 360
    HITSTOP_MS: int = 120

    # AI pacing
    AI_DECIDE_EVERY_MS: int = 800
    PUNCH_COOLDOWN_MS: int = 1000
    PUNCH_ANIM_MS: int = 300
    PUNCH_WINDUP_MS: int = 500

    # Stamina & costs
    BLOCK_DRAIN_PER_SEC: float = 2.5
    ROO_JUMP_ST_DRAIN: float = 6.0
    WALK_COST: int = 8
    JUMP_COST: int = 16

    # Regen/thresholds
    ROO_REST_THRESHOLD: float = 10.0
    ST_REGEN_PER_SEC_R: float = 12.0
    ST_REGEN_PER_SEC_H: float = 12.0
    BLOCK_MIN_STAMINA: float = 5.0
    MOVE_COOLDOWN_MS: int = 120

    # Hearts / HP
    HUMAN_HEARTS: int = 2
    ROO_HEARTS: int = 3
    HUMAN_HP: int = 100
    PUNCH_DAMAGE: int = 25
    PUNCH_BLOCKED_DAMAGE: int = 6
    BLOCK_SHARED_LOSS: float = 6.0

    # Stamina max values
    HUMAN_STAMINA: int = 100
    ROO_STAMINA: int   = 100

    # Avatars
    AVATAR_HUMAN: str = "ava_human.png"
    AVATAR_ROO:   str = "ava_roo.png"

    # message
    FLOAT_MSG_DURATION_MS = 1200
    FLOAT_MSG_RISE_SPEED = 25

    # ------碰撞检测 fix---------
    CONTACT_MAX_GAP_X = 10  # 允许的“几乎贴脸”负/正间隙，越大越贴
    CONTACT_MIN_Y_OVERLAP = 24  # 认为“同一行”的最小竖向重叠像素，越大越严格
    BASELINE_MARGIN = 4  # 行基线向上留的像素，避免踩线

    # --- snap tuning for face-to-face stick ---
    SNAP_EXTRA_X: int = 1  # extra pixels to "overlap" when snapping two yellow bboxes (visual stickiness)
    SNAP_VERT_SLOP: int = 6  # vertical tolerance (pixels) to allow snap on same row

    # --- Debug & control toggles ---
    DEBUG: bool = True                    # print simple english logs to console
    AI_TURN_ONLY_MODE: bool = False        # <<< TEMP: only face the player, do not move/punch
    AI_ALLOW_MOVE: bool = True            # master switch for moving when we re-enable
    AI_ALLOW_PUNCH: bool = True           # master switch for punch when we re-enable

CFG = _CFG()
