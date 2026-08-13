# -*- coding: utf-8 -*-

from pathlib import Path

from PIL import Image


SOURCE_ICON = Path("RTL_icon.png")
OUTPUT_ICON = Path("RTL_icon.ico")
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    if not SOURCE_ICON.exists():
        raise FileNotFoundError(f"Icon source not found: {SOURCE_ICON}")

    image = Image.open(SOURCE_ICON).convert("RGBA")
    OUTPUT_ICON.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT_ICON, format="ICO", sizes=ICON_SIZES)
    print(f"Generated {OUTPUT_ICON} with sizes: {ICON_SIZES}")


if __name__ == "__main__":
    main()
