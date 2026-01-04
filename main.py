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
import random
import sys
import time
import warnings

# Optional: hide pygame's pkg_resources deprecation warning noise
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.*")

import pygame  # noqa: E402

from enemy import Enemy
from physics import move_and_collide


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

ENEMY_BOUNCE = -520.0
INVULN_DURATION = 1.0

# IMPORTANT: set this correctly based on your art.
# If your side.png shows the character facing RIGHT, leave as "right".
# If your side.png shows the character facing LEFT, change to "left".
SIDE_SPRITE_FACES = "left"  # or "right"

TARGET_HEIGHT = 56

SPAWN_AHEAD_PX = 1200
DESPAWN_BEHIND_PX = 400
GROUND_CHUNK_W = 620
PLATFORM_HEIGHTS = [0, 80, 120, 170, 220]
PLATFORM_WIDTHS = [140, 180, 220, 260]
PLATFORM_GAPS = (90, 170)

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

    def draw(self, screen, camera_x: float = 0.0):
        spr = self.sprite()

        # shadow under feet
        shadow_w = spr.get_width() * 0.65
        shadow_h = 10
        shadow = pygame.Surface((int(shadow_w), shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        screen.blit(shadow, (self.x - shadow_w / 2 - camera_x, self.y - shadow_h / 2))

        # sprite anchored at feet (bottom-center)
        screen.blit(spr, (self.x - spr.get_width() / 2 - camera_x, self.y - spr.get_height()))


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

    # Platforms + endless generation state
    GROUND_Y = WIN_H - 90
    rng = random.Random(1234)

    ground_chunks: list[pygame.Rect] = [pygame.Rect(0, GROUND_Y, WIN_W, 200)]
    floating_platforms: list[pygame.Rect] = []
    platforms: list[pygame.Rect] = ground_chunks + floating_platforms

    next_ground_x = GROUND_CHUNK_W
    next_platform_x = WIN_W + 180

    player = Player(x=120, y=GROUND_Y, spr_front=spr_front, spr_back=spr_back, spr_side=spr_side)
    enemies: list[Enemy] = []

    camera_x = 0.0
    invuln_timer = 0.0

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
        prev_player_bottom = player.y
        invuln_timer = max(0.0, invuln_timer - dt)

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

        # Camera follows player with light smoothing
        target_cam_x = max(player.x - WIN_W * 0.35, 0)
        camera_x += (target_cam_x - camera_x) * 0.12

        # World generation: extend ground seamlessly
        while next_ground_x < camera_x + SPAWN_AHEAD_PX:
            chunk = pygame.Rect(next_ground_x, GROUND_Y, GROUND_CHUNK_W, 200)
            ground_chunks.append(chunk)
            next_ground_x += GROUND_CHUNK_W

        # Floating platforms and enemies
        while next_platform_x < camera_x + SPAWN_AHEAD_PX:
            gap = rng.randint(*PLATFORM_GAPS)
            next_platform_x += gap
            width = rng.choice(PLATFORM_WIDTHS)
            height = rng.choice(PLATFORM_HEIGHTS)
            plat_y = max(GROUND_Y - height, 120)
            platform = pygame.Rect(next_platform_x, plat_y, width, 18)
            floating_platforms.append(platform)

            if rng.random() < 0.45:
                enemies.append(Enemy(platform=platform, direction=rng.choice([-1, 1])))

            next_platform_x = platform.right

        platforms = ground_chunks + floating_platforms

        # Despawn behind camera
        keep_from_x = camera_x - DESPAWN_BEHIND_PX
        ground_chunks = [g for g in ground_chunks if g.right > keep_from_x]
        floating_platforms = [p for p in floating_platforms if p.right > keep_from_x]
        alive_platforms = set(ground_chunks + floating_platforms)
        enemies = [e for e in enemies if e.platform in alive_platforms and e.platform.right > keep_from_x]
        platforms = ground_chunks + floating_platforms

        # Enemies
        for enemy in enemies:
            enemy.update(platforms, dt, GRAVITY, MAX_FALL_SPEED)

        # Player vs enemies (stomp to defeat)
        player_rect = player.rect()
        surviving_enemies = []
        for enemy in enemies:
            e_rect = enemy.rect()
            if player_rect.colliderect(e_rect):
                stomped = prev_player_bottom <= e_rect.top and player.vy >= 0
                if stomped:
                    player.y = e_rect.top
                    player.vy = ENEMY_BOUNCE
                    player.on_ground = False
                    continue
                if invuln_timer <= 0.0:
                    knock_dir = -1 if player.x < enemy.x else 1
                    player.vx = knock_dir * MOVE_SPEED * 0.9
                    player.vy = JUMP_VELOCITY * 0.6
                    player.on_ground = False
                    invuln_timer = INVULN_DURATION
            surviving_enemies.append(enemy)
        enemies = surviving_enemies

        # Draw
        draw_parallax(screen, camera_x)

        for p in ground_chunks:
            display_rect = p.move(-camera_x, 0)
            pygame.draw.rect(screen, (40, 40, 50), display_rect)
            pygame.draw.rect(screen, (25, 25, 30), display_rect, 2)

        for p in floating_platforms:
            display_rect = p.move(-camera_x, 0)
            col = (70, 90, 70)
            pygame.draw.rect(screen, col, display_rect)
            pygame.draw.rect(screen, (30, 40, 30), display_rect, 2)

        for enemy in enemies:
            enemy.draw(screen, camera_x)

        player.draw(screen, camera_x)

        hud = (
            f"x={player.x:.1f} cam={camera_x:.1f} vx={player.vx:.1f} vy={player.vy:.1f} "
            f"ground={player.on_ground} invuln={invuln_timer:.2f}"
        )
        screen.blit(font.render(hud, True, (230, 230, 230)), (10, 10))

        if janeway_mode:
            screen.blit(font.render("🛸 JANEWAY MODE: engaged", True, (255, 255, 255)), (10, 32))

        pygame.display.flip()

    pygame.quit()


def draw_parallax(screen, camera_x: float):
    sky = (12, 14, 20)
    horizon = (24, 26, 36)
    screen.fill(sky)
    pygame.draw.rect(screen, horizon, (0, 0, WIN_W, WIN_H // 2))

    # layer speeds
    moon_x = (800 - camera_x * 0.05) % (WIN_W + 200) - 100
    pygame.draw.circle(screen, (240, 240, 255), (int(moon_x), 90), 26)

    # stars
    rng = random.Random(42)
    for i in range(36):
        star_x = (rng.randint(0, WIN_W) - camera_x * 0.1 + i * 40) % (WIN_W + 80) - 40
        star_y = rng.randint(10, WIN_H // 2 - 40)
        pygame.draw.circle(screen, (210, 210, 230), (int(star_x), star_y), 2)

    # distant silhouettes
    base_x = - (camera_x * 0.25) % (WIN_W + 140)
    for i in range(-1, 4):
        hill_rect = pygame.Rect(base_x + i * 320, WIN_H // 2 + 40, 240, 120)
        pygame.draw.ellipse(screen, (28, 34, 44), hill_rect)

    mid_x = - (camera_x * 0.45) % (WIN_W + 200)
    for i in range(-1, 5):
        mound = pygame.Rect(mid_x + i * 220, WIN_H // 2 + 70, 180, 90)
        pygame.draw.ellipse(screen, (34, 44, 58), mound)


if __name__ == "__main__":
    main()
