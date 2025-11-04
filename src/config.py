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

    # Backward-compat
    TEXT: tuple = COL_TEXT
    BG:   tuple = COL_BG
    GRID_LIGHT: tuple = COL_GRID_LIGHT
    GRID_DARK:  tuple = COL_GRID_DARK

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
    WALK_COST: int = 2
    JUMP_COST: int = 4

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

    # --- Debug & control toggles ---
    DEBUG: bool = True                    # print simple english logs to console
    AI_TURN_ONLY_MODE: bool = True        # <<< TEMP: only face the player, do not move/punch
    AI_ALLOW_MOVE: bool = True            # master switch for moving when we re-enable
    AI_ALLOW_PUNCH: bool = True           # master switch for punch when we re-enable

CFG = _CFG()
