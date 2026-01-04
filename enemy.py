import pygame

from physics import move_and_collide

ENEMY_SPEED = 120.0


class Enemy:
    def __init__(self, platform: pygame.Rect, direction: int = 1):
        self.platform = platform
        self.x = float(platform.centerx)
        self.y = float(platform.top)  # feet y (bottom)
        self.vx = ENEMY_SPEED * direction
        self.vy = 0.0
        self.w = 40
        self.h = 28
        self.on_ground = False

    def rect(self) -> pygame.Rect:
        left = int(self.x - self.w / 2)
        top = int(self.y - self.h)
        return pygame.Rect(left, top, self.w, self.h)

    def update(self, platforms: list[pygame.Rect], dt: float, gravity: float, max_fall_speed: float):
        desired_dir = 1 if self.vx >= 0 else -1
        self.vy += gravity * dt
        self.vy = min(self.vy, max_fall_speed)

        dx = self.vx * dt
        dy = self.vy * dt

        prev_x = self.x
        move_and_collide(self, platforms, dx, dy)

        # Patrol reversal: if we hit a wall, fell off, or failed to move much, flip direction
        moved_x = self.x - prev_x
        fallen_off = not self.platform.collidepoint(self.x, self.platform.top - 1)
        at_edge = (self.x < self.platform.left + 8) or (self.x > self.platform.right - 8)
        if abs(moved_x) < abs(dx) * 0.5 or fallen_off or at_edge:
            desired_dir *= -1

        self.vx = ENEMY_SPEED * desired_dir
        self.y = float(self.platform.top)

    def draw(self, screen, camera_x: float = 0.0):
        r = self.rect()
        display_rect = r.move(-camera_x, 0)
        pygame.draw.rect(screen, (180, 70, 70), display_rect)
        pygame.draw.rect(screen, (30, 20, 20), display_rect, 2)
