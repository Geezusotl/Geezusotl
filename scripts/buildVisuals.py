"""Generate self contained vector animations for the profile."""

import html
import math
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

root = Path(__file__).resolve().parents[1]
fonts = [
    ("Monospace", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ("Sans serif", "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf"),
    ("Serif", "/usr/share/fonts/opentype/urw-base35/NimbusRoman-Bold.otf"),
    ("Script", "/usr/share/fonts/opentype/urw-base35/Z003-MediumItalic.otf"),
]


def outline(text, fontPath, size, x, baseline):
    font = TTFont(fontPath)
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    paths = []
    positions = [x]
    for char in text:
        name = cmap[ord(char)]
        pen = SVGPathPen(glyphs)
        transform = TransformPen(pen, (scale, 0, 0, -scale, x, baseline))
        glyphs[name].draw(transform)
        commands = pen.getCommands()
        if commands:
            paths.append('<path d="' + commands + '"/>')
        x += font["hmtx"].metrics[name][0] * scale
        positions.append(x)
    font.close()
    return "".join(paths), positions


def animation(attribute, timeline, duration, discrete=False):
    times = ";".join(f"{time / duration:.6f}" for time, value in timeline)
    values = ";".join(f"{value:.3f}" for time, value in timeline)
    return f'<animate attributeName="{attribute}" dur="{duration}s" keyTimes="{times}" values="{values}" calcMode="{"discrete" if discrete else "linear"}" repeatCount="indefinite"/>'


def header():
    pieces = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 72" role="img" aria-labelledby="title desc">',
              '<title id="title">About Me:</title>',
              '<desc id="desc">The heading types and erases in monospace, sans serif, serif, and script fonts.</desc>',
              '<style>.still{display:none}@media(prefers-reduced-motion:reduce){.motion{display:none}.still{display:inline}}</style>']
    typing = 2.0 / 1.15
    erasing = typing / 2
    delay = 0.2
    hold = 1.5
    gap = 0.3
    slot = delay + typing + hold + erasing + gap
    duration = slot * len(fonts)
    firstPaths = None
    for index, (name, path) in enumerate(fonts):
        size = 37 if index != 3 else 43
        textX = 2
        paths, positions = outline("About Me:", path, size, textX, 48)
        if firstPaths is None:
            firstPaths = paths
        start = index * slot
        eraseStart = start + delay + typing + hold
        timeline = [(0, 0)]
        if start:
            timeline.append((start, 0))
        timeline.append((start + delay, 0))
        for i, pos in enumerate(positions[1:], 1):
            timeline.append((start + delay + typing * i / 9, pos - textX + 2))
        timeline.append((eraseStart, positions[-1] - textX + 2))
        for i in range(8, -1, -1):
            timeline.append((eraseStart + erasing * (9 - i) / 9, positions[i] - textX))
        timeline.append((duration, 0))
        clip = f'<clipPath id="clip{index}"><rect x="{textX}" y="0" height="72" width="{positions[-1] - textX if index == 0 else 0}">{animation("width", timeline, duration, True)}</rect></clipPath>'
        opacityTimeline = [(0, 1 if index == 0 else 0)]
        if start:
            opacityTimeline.append((start, 1))
        opacityTimeline.append((eraseStart + erasing, 0))
        opacityTimeline.append((duration, 1 if index == 0 else 0))
        pieces.append(clip)
        pieces.append(f'<g class="motion" fill="#ffffff" opacity="{1 if index == 0 else 0}"><title>{html.escape(name)}</title>{animation("opacity", opacityTimeline, duration, True)}<g clip-path="url(#clip{index})">{paths}</g></g>')
    pieces.append('<g class="still" fill="#ffffff">' + firstPaths + '</g></svg>')
    return "".join(pieces)


def illusion():
    pieces = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 440" role="img" aria-labelledby="title desc">',
              '<title id="title">Straight paths, rolling circle</title>',
              '<desc id="desc">Eight dots slide along straight diameter paths. Together they appear to trace a rolling circle. Follow one dot to see its straight path.</desc>',
              '<style>.still{display:none}@media(prefers-reduced-motion:reduce){.motion{display:none}.still{display:inline}}</style>',
              '<defs><linearGradient id="backdrop" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#102633"/><stop offset="1" stop-color="#081823"/></linearGradient><radialGradient id="ambient"><stop stop-color="#30616c" stop-opacity=".45"/><stop offset="1" stop-color="#102532" stop-opacity="0"/></radialGradient><filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4"/></filter></defs>',
              '<rect x="1" y="1" width="838" height="438" rx="24" fill="url(#backdrop)" stroke="#2d4c59"/>',
              '<circle cx="226" cy="220" r="192" fill="url(#ambient)"/>',
              '<circle cx="226" cy="220" r="162" fill="none" stroke="#5d929c" stroke-width="1.2"/>',
              '<circle cx="226" cy="220" r="166" fill="none" stroke="#274651" stroke-width="1"/>']
    for index in range(8):
        angle = index * math.pi / 8
        rotation = index * 22.5
        color = "#ffc4a3" if index % 2 else "#8be0db"
        pieces.append(f'<g transform="translate(226 220) rotate({rotation})"><line x1="-162" x2="162" y1="0" y2="0" stroke="#42626d" stroke-width=".8" opacity=".55"/>')
        motion = [(12 * n / 160, 162 * math.cos(2 * math.pi * n / 160 - angle)) for n in range(161)]
        initial = motion[0][1]
        for radius, opacity, useGlow in [(11, 0.42, True), (5.6, 1, False)]:
            filterPart = ' filter="url(#glow)"' if useGlow else ''
            pieces.append(f'<circle class="motion" cx="{initial:.3f}" cy="0" r="{radius}" fill="{color}" opacity="{opacity}"{filterPart}>{animation("cx", motion, 12)}</circle>')
        pieces.append(f'<circle class="still" cx="{initial:.3f}" cy="0" r="5.6" fill="{color}"/></g>')
    pieces.append('<line x1="453" x2="453" y1="76" y2="364" stroke="#294651"/>')
    font = fonts[1][1]
    labels = [("A LITTLE PERSPECTIVE", 14, 497, 105, "#86aeb7"),
              ("Follow one dot.", 28, 497, 162, "#ffc4a3"),
              ("Then watch", 28, 497, 204, "#e5f4f3"),
              ("the whole group.", 28, 497, 241, "#e5f4f3"),
              ("Straight paths.", 17, 497, 302, "#91c6ce"),
              ("One rolling circle.", 17, 497, 328, "#91c6ce")]
    for text, size, x, baseline, color in labels:
        paths, positions = outline(text, font, size, x, baseline)
        pieces.append(f'<g fill="{color}">{paths}</g>')
    pieces.append('</svg>')
    return "".join(pieces)


if __name__ == "__main__":
    (root / "assets" / "about-me.svg").write_text(header())
    (root / "assets" / "rolling-circle.svg").write_text(illusion())
    print("Built two self contained animated SVGs.")
