"""Generate application icons (icon.icns for macOS, icon.ico for Windows).

Run from the project root:
    python build/make_icons.py

Requires: Pillow  (pip install Pillow)
On macOS the ICNS file is created with iconutil (built in).
On Windows the ICO file is created directly by Pillow.
"""
import os
import sys
import struct
import shutil
import subprocess
import tempfile

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Pillow is required: pip install Pillow")

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(HERE, "icons")
os.makedirs(ICONS_DIR, exist_ok=True)


def make_base_image(size: int) -> Image.Image:
    """Draw the app icon: dark globe with a satellite orbit arc."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size // 16

    # Background circle — deep space blue
    d.ellipse([pad, pad, size - pad, size - pad], fill=(12, 18, 48, 255))

    # Globe latitude/longitude lines
    cx, cy, r = size // 2, size // 2, size // 2 - pad
    line_col = (40, 80, 160, 180)
    lw = max(1, size // 64)
    # Equator
    d.arc([cx - r, cy - r, cx + r, cy + r], 0, 360, fill=line_col, width=lw)
    # Two latitude bands
    for frac in (0.5, 0.75):
        rb = int(r * frac)
        yb = int(cy - r * (1 - frac * 2) * 0.5)
        d.arc([cx - rb, yb - rb // 3, cx + rb, yb + rb // 3],
              0, 360, fill=line_col, width=max(1, lw - 1))

    # Outer orbit ring
    ro = int(r * 1.35)
    orbit_col = (100, 200, 100, 200)
    lw2 = max(1, size // 48)
    d.arc([cx - ro, cy - ro, cx + ro, cy + ro], -30, 150, fill=orbit_col, width=lw2)

    # Satellite dot on the orbit
    angle_rad = __import__("math").radians(-30)
    sx = int(cx + ro * __import__("math").cos(angle_rad))
    sy = int(cy - ro * __import__("math").sin(angle_rad))
    dot = max(3, size // 18)
    d.ellipse([sx - dot, sy - dot, sx + dot, sy + dot], fill=(80, 220, 80, 255))

    # Thin border
    d.arc([pad, pad, size - pad, size - pad], 0, 360,
          fill=(60, 120, 220, 160), width=max(1, size // 32))

    return img


def build_icns(base_images: dict) -> str:
    """Create a .icns file from multiple sized images using iconutil (macOS only)."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "AppIcon.iconset")
        os.makedirs(iconset)
        for size, img in base_images.items():
            img.save(os.path.join(iconset, f"icon_{size}x{size}.png"))
            # Retina (@2x) version for standard sizes
            if size <= 512:
                img2 = base_images.get(size * 2)
                if img2:
                    img2.save(os.path.join(iconset, f"icon_{size}x{size}@2x.png"))
        dest = os.path.join(ICONS_DIR, "icon.icns")
        subprocess.run(["iconutil", "-c", "icns", "-o", dest, iconset], check=True)
        return dest


def build_ico(images: list) -> str:
    """Create a multi-resolution .ico file."""
    dest = os.path.join(ICONS_DIR, "icon.ico")
    images[0].save(dest, format="ICO", sizes=[(img.width, img.height) for img in images])
    return dest


def main():
    sizes = [16, 32, 48, 64, 128, 256, 512, 1024]
    imgs = {s: make_base_image(s) for s in sizes}

    # Always save a PNG for reference
    imgs[256].save(os.path.join(ICONS_DIR, "icon.png"))
    print("  icon.png saved")

    # macOS ICNS
    if sys.platform == "darwin":
        try:
            path = build_icns(imgs)
            print(f"  {path} saved")
        except Exception as e:
            print(f"  ICNS creation failed ({e}); PNG only")

    # Windows ICO (works on any platform via Pillow)
    try:
        ico_imgs = [imgs[s] for s in (16, 32, 48, 64, 128, 256) if s in imgs]
        path = build_ico(ico_imgs)
        print(f"  {path} saved")
    except Exception as e:
        print(f"  ICO creation failed: {e}")


if __name__ == "__main__":
    print("Generating icons …")
    main()
    print("Done.")
