import pygame


def move_and_collide(entity, platforms: list[pygame.Rect], dx: float, dy: float):
    r = entity.rect()

    # Horizontal
    r.x += int(round(dx))
    for p in platforms:
        if r.colliderect(p):
            if dx > 0:
                r.right = p.left
            elif dx < 0:
                r.left = p.right
            entity.vx = 0.0

    # Vertical
    r.y += int(round(dy))
    landed = False
    for p in platforms:
        if r.colliderect(p):
            if dy > 0:  # falling
                r.bottom = p.top
                entity.vy = 0.0
                landed = True
            elif dy < 0:  # rising
                r.top = p.bottom
                entity.vy = 0.0

    entity.x = float(r.centerx)
    entity.y = float(r.bottom)
    entity.on_ground = landed
