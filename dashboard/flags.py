"""Self-contained vector flags; no image downloads or browser emoji dependency."""
import math


def star(x, y, size, points=7):
    vertices = []
    for index in range(points * 2):
        angle = -math.pi / 2 + index * math.pi / points
        radius = size if index % 2 == 0 else size * .42
        vertices.append(f"{x+math.cos(angle)*radius:.2f},{y+math.sin(angle)*radius:.2f}")
    return '<polygon fill="white" points="' + ' '.join(vertices) + '"/>'


def flag_svg(team):
    if team == "India":
        shapes = '<rect width="64" height="22" fill="#ff9933"/><rect y="22" width="64" height="21" fill="white"/><rect y="43" width="64" height="21" fill="#138808"/><circle cx="32" cy="32" r="9" fill="none" stroke="#000080" stroke-width="1"/>'
        for index in range(24):
            angle = index * math.pi / 12
            shapes += f'<path d="M32 32L{32+8.5*math.cos(angle):.2f} {32+8.5*math.sin(angle):.2f}" stroke="#000080" stroke-width=".55"/>'
    else:
        shapes = '<rect width="64" height="64" fill="#012169"/><svg width="34" height="28" viewBox="0 0 60 30"><path d="M0 0L60 30M60 0L0 30" stroke="white" stroke-width="7"/><path d="M0 0L60 30M60 0L0 30" stroke="#c8102e" stroke-width="2"/><path d="M30 0V30M0 15H60" stroke="white" stroke-width="10"/><path d="M30 0V30M0 15H60" stroke="#c8102e" stroke-width="6"/></svg>'
        shapes += ''.join(star(x, y, size) for x, y, size in [(17, 45, 7), (48, 15, 4), (40, 33, 4), (56, 30, 4), (48, 51, 4)])
        shapes += star(49, 38, 2, 5)
    return f'<svg viewBox="0 0 64 64" width="64" height="64"><defs><clipPath id="{team}"><circle cx="32" cy="32" r="32"/></clipPath></defs><g clip-path="url(#{team})">{shapes}</g></svg>'
