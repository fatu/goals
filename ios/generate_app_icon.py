"""Generate a kawaii matcha cup app icon."""
from PIL import Image, ImageDraw
import math, os

SIZE = 1024
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background - soft matcha gradient
for y in range(SIZE):
    t = y / SIZE
    r = int(166 + (120 - 166) * t)
    g = int(214 + (185 - 214) * t)
    b = int(170 + (140 - 170) * t)
    draw.line([(0, y), (SIZE, y)], fill=(r, g, b))

cx, cy = SIZE // 2, SIZE // 2

# === Saucer ===
saucer_y = cy + 210
draw.ellipse([cx - 260, saucer_y, cx + 260, saucer_y + 55], fill=(220, 215, 205))
draw.ellipse([cx - 240, saucer_y + 5, cx + 240, saucer_y + 45], fill=(240, 235, 225))

# === Cup body ===
cup_w, cup_h = 400, 340
cup_l = cx - cup_w // 2
cup_t = cy - cup_h // 2 + 30
cup_r = cx + cup_w // 2
cup_b = cy + cup_h // 2 + 30

# Shadow
draw.rounded_rectangle([cup_l + 6, cup_t + 8, cup_r + 6, cup_b + 8], radius=50, fill=(80, 130, 80, 60))
# Body
draw.rounded_rectangle([cup_l, cup_t, cup_r, cup_b], radius=50, fill=(255, 252, 245))

# Matcha liquid top
m_top = cup_t + 8
m_bot = cup_t + 140
draw.rounded_rectangle([cup_l + 8, m_top, cup_r - 8, m_bot], radius=42, fill=(150, 195, 115))
# Foam lighter
draw.ellipse([cx - 70, m_top + 25, cx + 70, m_top + 85], fill=(185, 218, 155))
# Tiny latte art heart
hx, hy = cx, m_top + 55
for off in [-14, 14]:
    draw.ellipse([hx + off - 12, hy - 12, hx + off + 12, hy + 6], fill=(255, 252, 245))
draw.polygon([(hx - 26, hy), (hx, hy + 22), (hx + 26, hy)], fill=(255, 252, 245))

# === Kawaii face ===
face_y = cup_t + 230

# Eyes
ey = face_y - 10
for ex in [cx - 65, cx + 65]:
    draw.ellipse([ex - 28, ey - 34, ex + 28, ey + 34], fill=(55, 50, 50))
    draw.ellipse([ex + 0, ey - 26, ex + 16, ey - 10], fill=(255, 255, 255))
    draw.ellipse([ex - 12, ey + 2, ex - 4, ey + 12], fill=(255, 255, 255))

# Blush
by = face_y + 18
for bx in [cx - 100, cx + 100]:
    draw.ellipse([bx - 28, by - 16, bx + 28, by + 16], fill=(248, 165, 165, 120))

# Mouth - w shape cat smile
my = face_y + 25
for side in [-1, 1]:
    pts = []
    for i in range(25):
        t = i / 24
        x = cx + side * t * 30
        y = my + math.sin(t * math.pi) * 14
        pts.append((x, y))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=(90, 70, 70), width=5)

# === Cup handle ===
for angle_d in range(-55, 56):
    a = math.radians(angle_d)
    for thick in range(36, 48):
        px = int(cup_r - 12 + math.cos(a) * thick)
        py = int(cy + 65 + math.sin(a) * 60 * thick / 42)
        if 0 <= px < SIZE and 0 <= py < SIZE:
            img.putpixel((px, py), (255, 252, 245, 255))

# === Leaf decoration ===
lx, ly = cx + 50, m_top - 8
leaf = [(lx, ly - 35), (lx + 22, ly - 12), (lx + 18, ly + 8), (lx, ly + 4), (lx - 18, ly + 8), (lx - 22, ly - 12)]
draw.polygon(leaf, fill=(105, 175, 85))
draw.line([(lx, ly - 30), (lx, ly + 4)], fill=(75, 145, 65), width=3)

# === Steam wisps ===
for (sx, offset) in [(cx - 60, 0), (cx, -15), (cx + 60, -5)]:
    steam_pts = []
    for i in range(30):
        t = i / 29
        x = sx + math.sin(t * math.pi * 2 + offset) * 12
        y = m_top - 20 - t * 80
        steam_pts.append((x, y))
    for i in range(len(steam_pts) - 1):
        alpha = int(100 * (1 - i / 29))
        draw.line([steam_pts[i], steam_pts[i + 1]], fill=(255, 255, 255, alpha), width=4)

# === Sparkles ===
for (sx, sy) in [(170, 150), (840, 180), (160, 720), (860, 680), (cx, 80)]:
    s = 14
    draw.line([(sx - s, sy), (sx + s, sy)], fill=(255, 255, 255, 180), width=3)
    draw.line([(sx, sy - s), (sx, sy + s)], fill=(255, 255, 255, 180), width=3)

output = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "GoalsApp", "Assets.xcassets", "AppIcon.appiconset", "AppIcon.png"
)
img.save(output, "PNG")
print(f"Saved to {output}")
