#!/usr/bin/env python3
"""
endless_runner_platformer.py

Endless side-scrolling platformer prototype:
- Parallax background (3 layers)
- Procedurally spawns new platforms and stompable enemies as you move right
- World scrolls via camera; player can move left/right, jump
- Enemies patrol on their platform; jump on them to kill
- Simple rectangles for platforms; sprites for player (front/back/side) from:
    game/assets/sprites/player/{front.png,back.png,side.png}

Folder layout:
game/
├─ main.py  (you can name this file main.py)
├─ assets/
│  └─ sprites/
│     └─ player/
│        ├─ front.png
│        ├─ back.png
│        └─ side.png
"""

import os
import sys
import random
import pygame

# ----------------------------
# Config
# ----------------------------
WIN_W, WIN_H = 960, 540
FPS = 60

# Feel
MOVE_SPEED = 260.0
ACCEL_GROUND = 2600.0
ACCEL_AIR = 1500.0
FRICTION_GROUND = 4200.0
GRAVITY = 2200.0
JUMP_VELOCITY = -760.0
MAX_FALL_SPEED = 1600.0

# Player sprites
TARGET_HEIGHT = 56
SIDE_SPRITE_FACES = "left"  # set "right" if your side.png faces right

# Camera / scrolling
DEADZONE_W = 240
DEADZONE_H = 140

# Generation
TILE = 48
GROUND_ROWS = 3
WORLD_H = WIN_H

SPAWN_AHEAD_PX = 1400         # keep content ahead of the camera
DESPAWN_BEHIND_PX = 500       # remove old content behind camera
MIN_PLATFORM_GAP = 170
MAX_PLATFORM_GAP = 380
MIN_PLATFORM_W = 3 * TILE
MAX_PLATFORM_W = 8 * TILE
PLATFORM_H = 18

# Platform vertical placement range (top-left y)
MIN_PLATFORM_Y = 180
MAX_PLATFORM_Y = WIN_H - 160

# Enemy
ENEMY_W = 28
ENEMY_H = 36
ENEMY_SPEED = 60.0
STOMP_BOUNCE_VY = -520.0
STOMP_VY_THRESHOLD = 120.0     # must be falling at least this fast to count as stomp
PLAYER_DAMAGE_KNOCK_VX = 320.0
PLAYER_DAMAGE_KNOCK_VY = -420.0
INVULN_TIME = 0.9

# ----------------------------
# Paths (relative to this file)
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITE_DIR = os.path.join(BASE_DIR, "assets", "sprites", "player")
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

def rect_to_screen(r: pygame.Rect, cam_x: float, cam_y: float = 0.0) -> pygame.Rect:
    return pygame.Rect(r.x - cam_x, r.y - cam_y, r.w, r.h)


# ----------------------------
# Camera
# ----------------------------
class Camera:
    def __init__(self, view_w, view_h, world_h):
        self.view_w = view_w
        self.view_h = view_h
        self.world_h = world_h
        self.x = 0.0
        self.y = 0.0
        self.deadzone = pygame.Rect(
            (view_w - DEADZONE_W) // 2,
            (view_h - DEADZONE_H) // 2,
            DEADZONE_W,
            DEADZONE_H,
        )

    def update(self, target_x: float, target_y: float):
        sx = target_x - self.x
        sy = target_y - self.y

        if sx < self.deadzone.left:
            self.x -= (self.deadzone.left - sx)
        elif sx > self.deadzone.right:
            self.x += (sx - self.deadzone.right)

        # No vertical follow for classic feel; keep y = 0
        self.x = max(0.0, self.x)
        self.y = 0.0


# ----------------------------
# Player
# ----------------------------
class Player:
    def __init__(self, x, y, spr_front, spr_back, spr_side):
        self.x = float(x)   # feet x (world)
        self.y = float(y)   # feet y (world)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False

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

        # Hitbox slimmer than sprite
        self.w = int(spr_side.get_width() * 0.55)
        self.h = int(spr_side.get_height() * 0.95)

        # Damage / invuln
        self.invuln = 0.0
        self.hp = 3

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

    def draw(self, screen: pygame.Surface, cam: Camera):
        spr = self.sprite()

        # Blink when invulnerable
        if self.invuln > 0:
            # simple blink
            if int(pygame.time.get_ticks() / 80) % 2 == 0:
                return

        sx = self.x - cam.x
        sy = self.y - cam.y

        # Shadow
        shadow_w = spr.get_width() * 0.65
        shadow_h = 10
        shadow = pygame.Surface((int(shadow_w), shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        screen.blit(shadow, (sx - shadow_w / 2, sy - shadow_h / 2))

        screen.blit(spr, (sx - spr.get_width() / 2, sy - spr.get_height()))


# ----------------------------
# Enemy
# ----------------------------
class Enemy:
    def __init__(self, platform_rect: pygame.Rect, x: int):
        # Enemy stands on top of platform
        self.platform = platform_rect
        self.x = float(x)
        self.y = float(platform_rect.top)  # top of platform (we'll compute rect bottom)

        self.vx = ENEMY_SPEED * random.choice([-1, 1])
        self.alive = True

    def rect(self) -> pygame.Rect:
        # Enemy rect bottom sits on platform top
        return pygame.Rect(int(self.x - ENEMY_W / 2), int(self.platform.top - ENEMY_H), ENEMY_W, ENEMY_H)

    def update(self, dt: float):
        if not self.alive:
            return
        self.x += self.vx * dt

        # Patrol within platform bounds
        left_bound = self.platform.left + ENEMY_W / 2
        right_bound = self.platform.right - ENEMY_W / 2
        if self.x < left_bound:
            self.x = left_bound
            self.vx *= -1
        elif self.x > right_bound:
            self.x = right_bound
            self.vx *= -1

    def draw(self, screen: pygame.Surface, cam: Camera):
        if not self.alive:
            return
        r = self.rect()
        sr = rect_to_screen(r, cam.x, cam.y)
        # Simple 90s-style silhouette enemy
        pygame.draw.rect(screen, (110, 30, 30), sr, border_radius=6)
        pygame.draw.rect(screen, (20, 10, 10), sr, 2, border_radius=6)
        # little "eyes"
        eye_y = sr.y + 10
        pygame.draw.circle(screen, (240, 240, 240), (sr.centerx - 5, eye_y), 2)
        pygame.draw.circle(screen, (240, 240, 240), (sr.centerx + 5, eye_y), 2)


# ----------------------------
# Collision (player vs platforms)
# ----------------------------
def move_and_collide_player(player: Player, platforms: list[pygame.Rect], dx: float, dy: float):
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


def check_player_enemy(player: Player, enemies: list[Enemy]):
    """Return (stomped_enemy: bool, damaged: bool)."""
    pr = player.rect()
    stomped = False
    damaged = False

    for e in enemies:
        if not e.alive:
            continue
        er = e.rect()
        if not pr.colliderect(er):
            continue

        # Determine if stomp: player is falling and player's previous bottom was above enemy top
        # We'll approximate using current vy and overlap geometry
        if player.vy > STOMP_VY_THRESHOLD and (pr.bottom - er.top) < 14:
            e.alive = False
            player.vy = STOMP_BOUNCE_VY
            player.on_ground = False
            stomped = True
        else:
            damaged = True

    return stomped, damaged


# ----------------------------
# Procedural level generation
# ----------------------------
def build_initial_platforms(world_right: int):
    """Create ground and a few starter platforms. Return platforms list and 'last_x' marker."""
    platforms = []

    # Ground: infinite-ish; we keep chunks. We'll start with a big ground span.
    ground_top = WIN_H - (GROUND_ROWS * TILE)
    ground = pygame.Rect(0, ground_top, world_right, GROUND_ROWS * TILE)
    platforms.append(ground)

    # Starter platforms near beginning
    start = [
        pygame.Rect(160, ground_top - 80, 260, PLATFORM_H),
        pygame.Rect(520, ground_top - 150, 220, PLATFORM_H),
        pygame.Rect(830, ground_top - 60, 180, PLATFORM_H),
    ]
    platforms.extend(start)

    last_x = max(p.right for p in platforms)
    return platforms, last_x, ground_top


def spawn_next_platform(last_x: int, ground_top: int):
    gap = random.randint(MIN_PLATFORM_GAP, MAX_PLATFORM_GAP)
    w = random.randint(MIN_PLATFORM_W, MAX_PLATFORM_W)
    x = last_x + gap
    y = random.randint(MIN_PLATFORM_Y, MAX_PLATFORM_Y)

    # Keep it above ground
    y = min(y, ground_top - 30)
    return pygame.Rect(x, y, w, PLATFORM_H)


def maybe_spawn_enemy_for_platform(platform: pygame.Rect):
    # 60% chance on non-ground platforms that are wide enough
    if platform.y >= WIN_H - (GROUND_ROWS * TILE) - 2:
        return None
    if platform.w < 4 * TILE:
        return None
    if random.random() > 0.6:
        return None
    x = random.randint(platform.left + 30, platform.right - 30)
    return Enemy(platform, x)


def ensure_content_ahead(platforms, enemies, last_x, cam_x, ground_top):
    """Spawn platforms until we have content ahead of camera."""
    target_right = int(cam_x) + SPAWN_AHEAD_PX
    while last_x < target_right:
        p = spawn_next_platform(last_x, ground_top)
        platforms.append(p)
        last_x = max(last_x, p.right)

        e = maybe_spawn_enemy_for_platform(p)
        if e is not None:
            enemies.append(e)

    return last_x


def despawn_behind(platforms, enemies, cam_x):
    """Remove platforms/enemies far behind camera to keep lists small."""
    cutoff = cam_x - DESPAWN_BEHIND_PX

    # Keep ground (index 0) always, but trim its left edge forward to reduce rect size
    if platforms:
        ground = platforms[0]
        if ground.x < cutoff:
            # Slide ground chunk forward (like endless ground)
            new_left = int(cutoff)
            ground.width = max(ground.right - new_left, TILE)
            ground.x = new_left

    # Remove non-ground platforms behind
    platforms[:] = [platforms[0]] + [p for p in platforms[1:] if p.right >= cutoff]

    # Remove enemies behind or dead for a while
    enemies[:] = [e for e in enemies if e.alive and e.rect().right >= cutoff]


# ----------------------------
# Parallax background
# ----------------------------
def draw_parallax(screen: pygame.Surface, cam_x: float):
    # Sky gradient-ish blocks
    screen.fill((18, 18, 26))
    pygame.draw.rect(screen, (20, 20, 30), (0, 0, WIN_W, WIN_H // 2))

    # Layer 1: far stars (slow)
    offset1 = -(cam_x * 0.08) % WIN_W
    for i in range(40):
        x = int((i * 97 + offset1) % WIN_W)
        y = int((i * 53) % (WIN_H // 2))
        screen.set_at((x, y), (180, 180, 200))

    # Layer 2: distant hills silhouette
    offset2 = int(-(cam_x * 0.18) % (WIN_W + 400)) - 200
    for k in range(0, WIN_W + 400, 120):
        x = offset2 + k
        pygame.draw.circle(screen, (12, 12, 18), (x, WIN_H // 2 + 120), 160)

    # Layer 3: mid silhouettes (faster)
    offset3 = int(-(cam_x * 0.35) % (WIN_W + 500)) - 250
    for k in range(0, WIN_W + 500, 90):
        x = offset3 + k
        pygame.draw.rect(screen, (14, 14, 22), (x, WIN_H // 2 + 110, 40, 220))

    # Moon (medium slow)
    moon_x = int(780 - cam_x * 0.15) % (WIN_W + 200) - 100
    pygame.draw.circle(screen, (240, 240, 255), (moon_x, 90), 26)


# ----------------------------
# Main
# ----------------------------
def main():
    pygame.init()

    if not os.path.isdir(SPRITE_DIR):
        raise RuntimeError(f"Sprite directory not found: {SPRITE_DIR}")

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Endless Parallax Platformer")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 22)

    # Sprites
    try:
        spr_front = load_and_scale(FRONT_PATH, TARGET_HEIGHT)
        spr_back  = load_and_scale(BACK_PATH, TARGET_HEIGHT)
        spr_side  = load_and_scale(SIDE_PATH, TARGET_HEIGHT)
    except FileNotFoundError as e:
        print(f"Missing sprite: {e}")
        pygame.quit()
        sys.exit(1)

    # Level state
    platforms, last_x, ground_top = build_initial_platforms(world_right=3000)
    enemies = []
    # Seed enemies on starter platforms
    for p in platforms[1:]:
        e = maybe_spawn_enemy_for_platform(p)
        if e is not None:
            enemies.append(e)

    # Player start on ground
    player = Player(x=120, y=ground_top, spr_front=spr_front, spr_back=spr_back, spr_side=spr_side)
    cam = Camera(view_w=WIN_W, view_h=WIN_H, world_h=WORLD_H)

    # Input
    moving_left = False
    moving_right = False
    facing_up = False
    facing_down = False
    want_jump = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 1/30)

        # timers
        if player.invuln > 0:
            player.invuln = max(0.0, player.invuln - dt)

        # Events
        want_jump = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    moving_left = moving_right = False
                    facing_up = facing_down = False

                elif event.key in (pygame.K_a, pygame.K_LEFT):
                    moving_left = True
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    moving_right = True

                elif event.key in (pygame.K_w, pygame.K_UP):
                    facing_up = True
                elif event.key in (pygame.K_s, pygame.K_DOWN):
                    facing_down = True

                elif event.key == pygame.K_SPACE:
                    want_jump = True

            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_a, pygame.K_LEFT):
                    moving_left = False
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    moving_right = False
                elif event.key in (pygame.K_w, pygame.K_UP):
                    facing_up = False
                elif event.key in (pygame.K_s, pygame.K_DOWN):
                    facing_down = False

        move_dir = (1 if moving_right else 0) - (1 if moving_left else 0)

        # Horizontal velocity
        target_vx = move_dir * MOVE_SPEED
        if player.on_ground:
            player.vx = approach(player.vx, target_vx, ACCEL_GROUND * dt)
            if move_dir == 0:
                player.vx = approach(player.vx, 0.0, FRICTION_GROUND * dt)
                if abs(player.vx) < 5.0:
                    player.vx = 0.0
        else:
            player.vx = approach(player.vx, target_vx, ACCEL_AIR * dt)

        # Facing
        if move_dir < 0:
            player.facing = "left"
        elif move_dir > 0:
            player.facing = "right"
        else:
            if facing_up and not facing_down:
                player.facing = "back"
            elif facing_down and not facing_up:
                player.facing = "front"

        # Jump
        if want_jump and player.on_ground:
            player.vy = JUMP_VELOCITY
            player.on_ground = False

        # Gravity
        player.vy += GRAVITY * dt
        player.vy = min(player.vy, MAX_FALL_SPEED)

        # Move + collide
        dx = player.vx * dt
        dy = player.vy * dt
        move_and_collide_player(player, platforms, dx, dy)

        # Enemies update
        for e in enemies:
            e.update(dt)

        # Player vs enemies
        stomped, damaged = check_player_enemy(player, enemies)
        if damaged and player.invuln <= 0:
            player.hp -= 1
            player.invuln = INVULN_TIME
            # knockback based on relative position to nearest enemy collided (approx)
            player.vy = PLAYER_DAMAGE_KNOCK_VY
            player.vx = -PLAYER_DAMAGE_KNOCK_VX if move_dir >= 0 else PLAYER_DAMAGE_KNOCK_VX
            player.on_ground = False
            if player.hp <= 0:
                # simple reset
                player.hp = 3
                player.x, player.y = 120, ground_top
                player.vx = player.vy = 0
                cam.x = 0

        # Camera update (scrolls with player)
        cam.update(player.x, player.y)

        # Ensure content ahead + despawn behind
        last_x = ensure_content_ahead(platforms, enemies, last_x, cam.x, ground_top)
        despawn_behind(platforms, enemies, cam.x)

        # Draw parallax
        draw_parallax(screen, cam.x)

        # Draw platforms
        for p in platforms:
            sp = rect_to_screen(p, cam.x, cam.y)
            if sp.right < 0 or sp.left > WIN_W:
                continue
            col = (35, 45, 35) if p.y >= ground_top else (55, 75, 55)
            pygame.draw.rect(screen, col, sp)
            pygame.draw.rect(screen, (20, 25, 20), sp, 2)

        # Draw enemies
        for e in enemies:
            e.draw(screen, cam)

        # Draw player
        player.draw(screen, cam)

        # HUD
        hud = f"x={int(player.x)} cam={int(cam.x)} platforms={len(platforms)} enemies={len(enemies)} hp={player.hp} vx={player.vx:.0f} vy={player.vy:.0f} facing={player.facing}"
        screen.blit(font.render(hud, True, (230, 230, 230)), (10, 10))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
