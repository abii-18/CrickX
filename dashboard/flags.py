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
    elif team == "England":
        shapes = '<rect width="64" height="64" fill="white"/><path d="M32 0V64M0 32H64" stroke="#ce1124" stroke-width="12"/>'
    elif team == "Pakistan":
        shapes = '<rect width="64" height="64" fill="#01411c"/><rect width="14" height="64" fill="white"/><circle cx="39" cy="32" r="15" fill="white"/><circle cx="44" cy="28" r="13" fill="#01411c"/>' + star(47, 22, 6, 5)
    elif team == "South Africa":
        shapes = '<rect width="64" height="32" fill="#de3831"/><rect y="32" width="64" height="32" fill="#002395"/><path d="M0 0L32 32L64 32M0 64L32 32" fill="none" stroke="white" stroke-width="22"/><path d="M0 0L32 32L64 32M0 64L32 32" fill="none" stroke="#007a4d" stroke-width="14"/><path d="M0 15L19 32L0 49" fill="black" stroke="#ffb612" stroke-width="4"/>'
    else:
        shapes = '<rect width="64" height="64" fill="#012169"/><svg width="34" height="28" viewBox="0 0 60 30"><path d="M0 0L60 30M60 0L0 30" stroke="white" stroke-width="7"/><path d="M0 0L60 30M60 0L0 30" stroke="#c8102e" stroke-width="2"/><path d="M30 0V30M0 15H60" stroke="white" stroke-width="10"/><path d="M30 0V30M0 15H60" stroke="#c8102e" stroke-width="6"/></svg>'
        if team == "New Zealand":
            shapes += ''.join(star(x, y, size, 5) + star(x, y, size*.65, 5).replace('fill="white"', 'fill="#c8102e"') for x, y, size in [(48, 15, 5), (40, 33, 5), (56, 30, 5), (48, 51, 5)])
        else:
            shapes += ''.join(star(x, y, size) for x, y, size in [(17, 45, 7), (48, 15, 4), (40, 33, 4), (56, 30, 4), (48, 51, 4)])
            shapes += star(49, 38, 2, 5)
    identifier = team.replace(" ", "")
    return f'<svg viewBox="0 0 64 64" width="64" height="64"><defs><clipPath id="{identifier}"><circle cx="32" cy="32" r="32"/></clipPath></defs><g clip-path="url(#{identifier})">{shapes}</g></svg>'
