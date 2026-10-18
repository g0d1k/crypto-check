"""
Builds every icon size the app needs from packaging/icon-source.png.

    python packaging/make_icon.py

The source image has a solid black background around its rounded frame, so
we flood-fill that background from the four corners and make it transparent.
Otherwise the icon would show up as a black square on desktops and taskbars.

Outputs:
  crypto_check/assets/icon.png   256px, used as the window icon on Linux/macOS
  crypto_check/assets/icon.ico   multi-size, used by Windows (window, .exe, installer)
  packaging/linux/icons/<size>/io.github.g0d1k.CryptoCheck.png   for the Linux desktop menu
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "packaging" / "icon-source.png"
APP_ID = "io.github.g0d1k.CryptoCheck"
DARK = 70  # channel values below this (in R, G and B) count as background


def remove_background(image):
    """Make the dark area outside the icon's rounded frame transparent."""
    r, g, b = image.convert("RGB").split()
    is_dark = lambda channel: channel.point(lambda v: 255 if v < DARK else 0)
    dark = ImageChops.multiply(ImageChops.multiply(is_dark(r), is_dark(g)), is_dark(b))

    # Only dark pixels connected to a corner are background (the icon's inside is dark too).
    w, h = dark.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if dark.getpixel(corner) == 255:
            ImageDraw.floodfill(dark, corner, 128)
    background = dark.point(lambda v: 255 if v == 128 else 0)

    # A slight blur anti-aliases the cut-out edge.
    alpha = ImageChops.invert(background).filter(ImageFilter.GaussianBlur(1.2))
    result = image.convert("RGBA")
    result.putalpha(alpha)
    return result


def main():
    icon = remove_background(Image.open(SOURCE))

    def sized(size):
        return icon.resize((size, size), Image.LANCZOS)

    assets = ROOT / "crypto_check" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    sized(256).save(assets / "icon.png", optimize=True)
    sized(256).save(assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    for size in (48, 64, 128, 256, 512):
        folder = ROOT / "packaging" / "linux" / "icons" / f"{size}x{size}"
        folder.mkdir(parents=True, exist_ok=True)
        sized(size).save(folder / f"{APP_ID}.png", optimize=True)

    print("Icons written.")


if __name__ == "__main__":
    main()
