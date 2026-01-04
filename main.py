#!/usr/bin/env python3
"""
platformer_demo.py

True platformer: gravity, jump, platforms, collision (simple rectangles)
3-pose character: front / back / side (side gets flipped for left/right)

Fixes:
- Idle now resets to FRONT (no more “stuck” on back/side)
- Left/Right always use side sprite (flipped appropriately)
- BACK is only shown when you hold UP/W (optional “walk away” intent)

Nice-to-have:
- Portable sprite paths (relative to this file)
- Optional suppression of pygame pkg_resources deprecation warning

✨ Secret upgrade (just for you):
- Type the hidden key sequence: J A N E W A Y
  -> toggles "Janeway Mode" (speed + jump boost) and shows an indicator
"""

import os
import sys
import time
import warnings

# Optional: hide pygame's pkg_resources deprecation warning noise
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.*")

import pygame  # noqa: E402


# ----------------------------
# Config
# ----------------------------
WIN_W, WIN_H = 960, 540
FPS = 60

MOVE_SPEED = 260.0
ACCEL_GROUND = 2600.0
ACCEL_AIR = 1500.0
FRICTION_GROUND = 4200.0
GRAVITY = 2200.0
JUMP_VELOCITY = -760.0
MAX_FALL_SPEED = 1600.0

# IMPORTANT: set this correctly based on your art.
# If your side.png shows the character facing RIGHT, leave as "right".
# If your side.png shows the character facing LEFT, change to "left".
SIDE_SPRITE_FACES = "left"  # or "right"

TARGET_HEIGHT = 56

# --- Portable paths relative to this file ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITE_DIR = os.path.join(BASE_DIR, "assets", "images", "sprites", "player")
FRONT_PATH = os.path.join(SPRITE_DIR, "front.png")
BACK_PATH  = os.path.join(SPRITE_DIR, "back.png")
SIDE_PATH  = os.path.join(SPRITE_DIR, "side.png")


# ----------------------------
# Helpers
# ----------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def load_and_scale(path: str, target_h: int) -> pygame.Surface:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    img = pygame.image.load(path).convert_alpha()
    scale = target_h / img.get_height()
    new_w = max(1, int(img.get_width() * scale))
    new_h = max(1, int(img.get_height() * scale))
    return pygame.transform.smoothscale(img, (new_w, new_h))

def approach(current: float, target: float, max_delta: float) -> float:
    if current < target:
        return min(current + max_delta, target)
    return max(current - max_delta, target)


# ----------------------------
# Secret upgrade: Janeway Mode
# ----------------------------
class SecretSequence:
    def __init__(self, sequence: str, timeout_s: float = 2.0):
        self.sequence = sequence.upper()
        self.timeout_s = timeout_s
        self.buffer = ""
        self.last_time = 0.0

    def feed(self, ch: str) -> bool:
        now = time.time()
        ch = ch.upper()

        if now - self.last_time > self.timeout_s:
            self.buffer = ""

        self.last_time = now
        self.buffer += ch

        # keep buffer small
        if len(self.buffer) > len(self.sequence):
            self.buffer = self.buffer[-len(self.sequence):]

        return self.buffer == self.sequence


# ----------------------------
# Player
# ----------------------------
class Player:
    def __init__(self, x, y, spr_front, spr_back, spr_side):
        self.x = float(x)
        self.y = float(y)     # feet y (bottom)
        self.vx = 0.0
        self.vy = 0.0

        self.spr_front = spr_front
        self.spr_back = spr_back
        self.spr_side = spr_side

        flipped = pygame.transform.flip(spr_side, True, False)
        if SIDE_SPRITE_FACES == "right":
            self.spr_right = spr_side
            self.spr_left = flipped
        else:
            self.spr_left = spr_side
            self.spr_right = flipped

        self.facing = "front"  # front/back/left/right

        # Simple hitbox (slightly narrower than sprite)
        self.w = int(spr_side.get_width() * 0.55)
        self.h = int(spr_side.get_height() * 0.95)

        self.on_ground = False

    def rect(self) -> pygame.Rect:
        left = int(self.x - self.w / 2)
        top = int(self.y - self.h)
        return pygame.Rect(left, top, self.w, self.h)

    def sprite(self) -> pygame.Surface:
        if self.facing == "back":
            return self.spr_back
        if self.facing == "left":
            return self.spr_left
        if self.facing == "right":
            return self.spr_right
        return self.spr_front

    def draw(self, screen):
        spr = self.sprite()

        # shadow under feet
        shadow_w = spr.get_width() * 0.65
        shadow_h = 10
        shadow = pygame.Surface((int(shadow_w), shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        screen.blit(shadow, (self.x - shadow_w / 2, self.y - shadow_h / 2))

        # sprite anchored at feet (bottom-center)
        screen.blit(spr, (self.x - spr.get_width() / 2, self.y - spr.get_height()))


# ----------------------------
# Collision
# ----------------------------
def move_and_collide(player: Player, platforms: list[pygame.Rect], dx: float, dy: float):
    r = player.rect()

    # Horizontal
    r.x += int(round(dx))
    for p in platforms:
        if r.colliderect(p):
            if dx > 0:
                r.right = p.left
            elif dx < 0:
                r.left = p.right
            player.vx = 0.0

    # Vertical
    r.y += int(round(dy))
    landed = False
    for p in platforms:
        if r.colliderect(p):
            if dy > 0:  # falling
                r.bottom = p.top
                player.vy = 0.0
                landed = True
            elif dy < 0:  # rising
                r.top = p.bottom
                player.vy = 0.0

    player.x = float(r.centerx)
    player.y = float(r.bottom)
    player.on_ground = landed


# ----------------------------
# Main
# ----------------------------
def main():
    pygame.init()

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("True Platformer Demo")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 22)

    # Load sprites
    try:
        spr_front = load_and_scale(FRONT_PATH, TARGET_HEIGHT)
        spr_back  = load_and_scale(BACK_PATH, TARGET_HEIGHT)
        spr_side  = load_and_scale(SIDE_PATH, TARGET_HEIGHT)
    except FileNotFoundError as e:
        print(f"Missing sprite: {e}")
        print(f"Looked in: {SPRITE_DIR}")
        pygame.quit()
        sys.exit(1)

    # Platforms
    GROUND_Y = WIN_H - 90
    platforms = [
        pygame.Rect(0, GROUND_Y, WIN_W, 200),
        pygame.Rect(140, GROUND_Y - 80, 220, 18),
        pygame.Rect(430, GROUND_Y - 150, 200, 18),
        pygame.Rect(700, GROUND_Y - 230, 180, 18),
        pygame.Rect(560, GROUND_Y - 40, 140, 18),
    ]

    player = Player(x=120, y=GROUND_Y, spr_front=spr_front, spr_back=spr_back, spr_side=spr_side)

    # --- Event-based input flags (prevents phantom drift)
    moving_left = False
    moving_right = False
    holding_up = False   # optional: show BACK when held
    holding_down = False # optional: force FRONT when held
    want_jump = False

    # Secret upgrade state
    seq = SecretSequence("JANEWAY", timeout_s=2.0)
    janeway_mode = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 1/30)

        # Janeway Mode boosts
        speed_mult = 1.35 if janeway_mode else 1.0
        jump_mult = 1.10 if janeway_mode else 1.0

        want_jump = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # clear stuck keys if focus changes
            elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWLEAVE):
                moving_left = moving_right = False
                holding_up = holding_down = False

            elif event.type == pygame.KEYDOWN:
                # Secret sequence detection (letters only)
                if event.unicode and event.unicode.isalpha():
                    if seq.feed(event.unicode):
                        janeway_mode = not janeway_mode

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_r:
                    moving_left = moving_right = False
                    holding_up = holding_down = False

                elif event.key in (pygame.K_a, pygame.K_LEFT):
                    moving_left = True
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    moving_right = True
                elif event.key in (pygame.K_w, pygame.K_UP):
                    holding_up = True
                elif event.key in (pygame.K_s, pygame.K_DOWN):
                    holding_down = True
                elif event.key == pygame.K_SPACE:
                    want_jump = True

            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_a, pygame.K_LEFT):
                    moving_left = False
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    moving_right = False
                elif event.key in (pygame.K_w, pygame.K_UP):
                    holding_up = False
                elif event.key in (pygame.K_s, pygame.K_DOWN):
                    holding_down = False

        move_dir = (1 if moving_right else 0) - (1 if moving_left else 0)

        # Horizontal movement
        target_vx = move_dir * (MOVE_SPEED * speed_mult)
        if player.on_ground:
            player.vx = approach(player.vx, target_vx, ACCEL_GROUND * dt)
            if move_dir == 0:
                player.vx = approach(player.vx, 0.0, FRICTION_GROUND * dt)
                if abs(player.vx) < 5.0:
                    player.vx = 0.0
        else:
            player.vx = approach(player.vx, target_vx, ACCEL_AIR * dt)

        # ✅ Facing logic (fixed)
        # Priority:
        # - If moving left/right -> side sprite
        # - Else if holding UP -> back sprite (optional intent)
        # - Else -> front sprite (idle / down)
        if move_dir < 0:
            player.facing = "left"
        elif move_dir > 0:
            player.facing = "right"
        else:
            if holding_up and not holding_down:
                player.facing = "back"
            else:
                player.facing = "front"

        # Jump
        if want_jump and player.on_ground:
            player.vy = JUMP_VELOCITY * jump_mult
            player.on_ground = False

        # Gravity
        player.vy += GRAVITY * dt
        player.vy = min(player.vy, MAX_FALL_SPEED)

        # Move + collide
        dx = player.vx * dt
        dy = player.vy * dt
        move_and_collide(player, platforms, dx, dy)

        # Clamp within screen
        player.x = clamp(player.x, player.w // 2, WIN_W - player.w // 2)

        # Draw
        screen.fill((18, 18, 26))
        pygame.draw.rect(screen, (20, 20, 30), (0, 0, WIN_W, WIN_H // 2))
        pygame.draw.circle(screen, (240, 240, 255), (780, 90), 26)

        for p in platforms:
            col = (35, 45, 35) if p.y >= GROUND_Y else (55, 75, 55)
            pygame.draw.rect(screen, col, p)
            pygame.draw.rect(screen, (20, 25, 20), p, 2)

        player.draw(screen)

        hud = (
            f"move_dir={move_dir} vx={player.vx:.1f} vy={player.vy:.1f} "
            f"on_ground={player.on_ground} facing={player.facing} side_faces={SIDE_SPRITE_FACES}"
        )
        screen.blit(font.render(hud, True, (230, 230, 230)), (10, 10))

        if janeway_mode:
            screen.blit(font.render("🛸 JANEWAY MODE: engaged", True, (255, 255, 255)), (10, 32))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
