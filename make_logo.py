"""Generate Duccky rubber-duck logo. Outputs logo.png + logo.ico (multi-res)."""

from PIL import Image, ImageDraw


def make_logo(size: int = 512) -> Image.Image:
    # Supersample 2x then downscale for smooth edges
    s = size * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── Palette ────────────────────────────────────────────────────────────
    Y_LIGHT  = (255, 230, 110)
    Y_MAIN   = (255, 205,  60)
    Y_SHADE  = (235, 170,  25)
    ORANGE   = (255, 140,  10)
    ORANGE_D = (215,  95,   0)
    BLACK    = ( 18,  18,  28)
    WHITE    = (255, 255, 255)

    cx = s / 2

    # ── Body (lower ellipse) ──────────────────────────────────────────────
    bw = s * 0.72
    bh = s * 0.50
    by = s * 0.62
    d.ellipse([cx - bw/2, by - bh/2, cx + bw/2, by + bh/2], fill=Y_SHADE)
    d.ellipse([cx - bw/2 + s*0.012, by - bh/2 - s*0.005,
               cx + bw/2 - s*0.005, by + bh/2 - s*0.025], fill=Y_MAIN)

    # ── Tail (small triangle behind-left) ─────────────────────────────────
    tail = [
        (cx - bw*0.42, by - bh*0.05),
        (cx - bw*0.62, by - bh*0.30),
        (cx - bw*0.40, by - bh*0.18),
    ]
    d.polygon(tail, fill=Y_SHADE)

    # ── Head (upper circle, slight offset right) ──────────────────────────
    hr = s * 0.235
    hx = cx + s * 0.04
    hy = s * 0.34
    d.ellipse([hx - hr - s*0.006, hy - hr + s*0.012,
               hx + hr + s*0.006, hy + hr + s*0.014], fill=Y_SHADE)
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=Y_MAIN)

    # ── Cheek highlight ──────────────────────────────────────────────────
    hl_w = hr * 0.85
    hl_h = hr * 0.55
    hl_x = hx - hr * 0.30
    hl_y = hy - hr * 0.32
    d.ellipse([hl_x - hl_w/2, hl_y - hl_h/2,
               hl_x + hl_w/2, hl_y + hl_h/2], fill=Y_LIGHT)

    # ── Beak (rounded rectangle, points right) ────────────────────────────
    bk_w = s * 0.21
    bk_h = s * 0.085
    bk_x = hx + hr * 0.55
    bk_y = hy + s * 0.018
    # Drop shadow
    d.rounded_rectangle(
        [bk_x - s*0.022, bk_y - bk_h/2 + s*0.006,
         bk_x + bk_w,    bk_y + bk_h/2 + s*0.006],
        radius=bk_h/2, fill=ORANGE_D)
    # Main beak
    d.rounded_rectangle(
        [bk_x - s*0.022, bk_y - bk_h/2,
         bk_x + bk_w,    bk_y + bk_h/2],
        radius=bk_h/2, fill=ORANGE)
    # Beak split line
    line_y = bk_y + s * 0.004
    d.line([(bk_x + s*0.005, line_y),
            (bk_x + bk_w - s*0.012, line_y)],
           fill=ORANGE_D, width=max(2, int(s*0.005)))

    # ── Eye (black + white shine) ─────────────────────────────────────────
    er = s * 0.042
    ex = hx + hr * 0.15
    ey = hy - hr * 0.08
    d.ellipse([ex - er - s*0.005, ey - er - s*0.005,
               ex + er + s*0.005, ey + er + s*0.005], fill=WHITE)
    d.ellipse([ex - er, ey - er, ex + er, ey + er], fill=BLACK)
    sh = er * 0.42
    d.ellipse([ex + er*0.05 - sh, ey - er*0.45 - sh,
               ex + er*0.05 + sh, ey - er*0.45 + sh], fill=WHITE)

    # ── Wing (small curve on body) ────────────────────────────────────────
    ww = bw * 0.45
    wh = bh * 0.55
    wx = cx + bw * 0.02
    wy = by + bh * 0.05
    d.chord([wx - ww/2, wy - wh/2, wx + ww/2, wy + wh/2],
            start=200, end=355, fill=Y_SHADE)

    # ── Water dot beneath (small) ─────────────────────────────────────────
    d.ellipse([cx - bw*0.55, by + bh*0.42,
               cx - bw*0.42, by + bh*0.50], fill=(120, 170, 220))
    d.ellipse([cx + bw*0.30, by + bh*0.38,
               cx + bw*0.45, by + bh*0.46], fill=(120, 170, 220))

    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    big = make_logo(512)
    big.save("logo.png", "PNG")

    # Multi-res ICO (Windows expects nested sizes, biggest first)
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    big.save("logo.ico", format="ICO", sizes=ico_sizes)

    print("logo.png and logo.ico generated")
