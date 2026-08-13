# -*- coding: utf-8 -*-

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit(
        "This script requires Pillow. Install it with: pip install pillow"
    ) from exc


@dataclass(frozen=True)
class ImageRule:
    name: str
    crop_box: tuple[int, int, int, int]
    output_size: tuple[int, int] | None
    flip_horizontal: bool = False


@dataclass(frozen=True)
class ProcessingProfile:
    rule_name: str
    mode_name: str
    expected_size: tuple[int, int]
    rules: list[ImageRule]
    default_output_suffix: str


@dataclass(frozen=True)
class RuleSet:
    name: str
    process: ProcessingProfile
    restore: ProcessingProfile


ORIGINAL_SIZE = (2048, 2048)
BACKGROUND_COLOR = (255, 255, 255)
SUPPORTED_INPUT_SUFFIXES = {".jpg", ".png"}

RULE_SETS = {
    "1100": RuleSet(
        name="1100",
        process=ProcessingProfile(
            rule_name="1100",
            mode_name="process",
            expected_size=ORIGINAL_SIZE,
            rules=[
                ImageRule("upper_part_stretched", (0, 0, 2048, 723), (2813, 723)),
                ImageRule(
                    "middle_part_stretched_and_flipped",
                    (0, 723, 2048, 1410),
                    (2813, 687),
                    flip_horizontal=True,
                ),
                ImageRule("lower_part_cropped", (0, 1410, 2048, 2048), None),
            ],
            default_output_suffix="processed",
        ),
        restore=ProcessingProfile(
            rule_name="1100",
            mode_name="restore",
            expected_size=(2813, 2048),
            rules=[
                ImageRule("upper_part_restored", (0, 0, 2813, 723), (2048, 723)),
                ImageRule(
                    "middle_part_restored",
                    (0, 723, 2813, 1410),
                    (2048, 687),
                    flip_horizontal=True,
                ),
                ImageRule("lower_part_restored", (0, 1410, 2048, 2048), None),
            ],
            default_output_suffix="restored",
        ),
    ),
    "DC85": RuleSet(
        name="DC85",
        process=ProcessingProfile(
            rule_name="DC85",
            mode_name="process",
            expected_size=ORIGINAL_SIZE,
            rules=[
                ImageRule("upper_part_stretched", (0, 0, 2048, 670), (5638, 670)),
                ImageRule("middle_part_stretched", (0, 670, 2048, 1300), (5166, 630)),
                ImageRule("lower_part_cropped", (0, 1300, 2048, 2048), None),
            ],
            default_output_suffix="processed",
        ),
        restore=ProcessingProfile(
            rule_name="DC85",
            mode_name="restore",
            expected_size=(5638, 2048),
            rules=[
                ImageRule("upper_part_restored", (0, 0, 5638, 670), (2048, 670)),
                ImageRule("middle_part_restored", (0, 670, 5166, 1300), (2048, 630)),
                ImageRule("lower_part_restored", (0, 1300, 2048, 2048), None),
            ],
            default_output_suffix="restored",
        ),
    ),
    "KR5000": RuleSet(
        name="KR5000",
        process=ProcessingProfile(
            rule_name="KR5000",
            mode_name="process",
            expected_size=ORIGINAL_SIZE,
            rules=[
                ImageRule(
                    "upper_part_stretched_and_flipped",
                    (0, 0, 2048, 730),
                    (3848, 730),
                    flip_horizontal=True,
                ),
                ImageRule("middle_part_stretched", (0, 730, 2048, 1400), (3848, 670)),
                ImageRule("lower_part_cropped", (0, 1400, 2048, 2048), None),
            ],
            default_output_suffix="processed",
        ),
        restore=ProcessingProfile(
            rule_name="KR5000",
            mode_name="restore",
            expected_size=(3848, 2048),
            rules=[
                ImageRule(
                    "upper_part_restored",
                    (0, 0, 3848, 730),
                    (2048, 730),
                    flip_horizontal=True,
                ),
                ImageRule("middle_part_restored", (0, 730, 3848, 1400), (2048, 670)),
                ImageRule("lower_part_restored", (0, 1400, 2048, 2048), None),
            ],
            default_output_suffix="restored",
        ),
    ),
}


def get_resampling_filter() -> int:
    return getattr(Image, "Resampling", Image).LANCZOS


def is_supported_input_file(source_path: Path) -> bool:
    return source_path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES


def has_matching_aspect_ratio(
    image_size: tuple[int, int],
    expected_size: tuple[int, int],
) -> bool:
    image_width, image_height = image_size
    expected_width, expected_height = expected_size
    return image_width * expected_height == image_height * expected_width


def crop_and_resize_image(
    image: Image.Image,
    crop_box: tuple[int, int, int, int],
    output_size: tuple[int, int] | None = None,
    flip_horizontal: bool = False,
) -> Image.Image:
    processed_image = image.crop(crop_box)

    if output_size is not None:
        processed_image = processed_image.resize(output_size, get_resampling_filter())

    if flip_horizontal:
        flip_operation = getattr(Image, "Transpose", Image).FLIP_LEFT_RIGHT
        processed_image = processed_image.transpose(flip_operation)

    return processed_image


def build_images_from_rules(
    image: Image.Image,
    rules: list[ImageRule],
) -> list[Image.Image]:
    return [
        crop_and_resize_image(
            image=image,
            crop_box=rule.crop_box,
            output_size=rule.output_size,
            flip_horizontal=rule.flip_horizontal,
        )
        for rule in rules
    ]


def compose_images_vertically(
    images: list[Image.Image],
    background_color: tuple[int, int, int] = BACKGROUND_COLOR,
) -> Image.Image:
    if not images:
        raise ValueError("No images to compose.")

    canvas_width = max(image.width for image in images)
    canvas_height = sum(image.height for image in images)
    canvas = Image.new("RGB", (canvas_width, canvas_height), background_color)

    current_y = 0
    for image in images:
        canvas.paste(image.convert("RGB"), (0, current_y))
        current_y += image.height

    return canvas


def prepare_source_image(
    image: Image.Image,
    source_path: Path,
    profile: ProcessingProfile,
) -> Image.Image:
    if source_path.suffix.lower() == ".png":
        prepared_image = image.convert("RGBA")
        prepared_image.putalpha(255)
    else:
        prepared_image = image.copy()

    if prepared_image.size != profile.expected_size:
        prepared_image = prepared_image.resize(
            profile.expected_size,
            get_resampling_filter(),
        )

    return prepared_image


def get_rule_set(rule_name: str) -> RuleSet:
    normalized_name = rule_name.upper()
    for configured_name, rule_set in RULE_SETS.items():
        if configured_name.upper() == normalized_name:
            return rule_set

    supported_rules = ", ".join(RULE_SETS)
    raise ValueError(f"Unknown rule: {rule_name}. Supported rules: {supported_rules}.")


def get_processing_profile(rule_name: str, restore: bool = False) -> ProcessingProfile:
    rule_set = get_rule_set(rule_name)
    return rule_set.restore if restore else rule_set.process


def process_image(
    source_path: Path,
    output_path: Path,
    profile: ProcessingProfile,
) -> Path:
    source_path = Path(source_path)
    output_path = Path(output_path)

    if not is_supported_input_file(source_path):
        raise ValueError("Please choose a .jpg or .png image.")

    if output_path.suffix.lower() != ".jpg":
        output_path = output_path.with_suffix(".jpg")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as image:
        if not has_matching_aspect_ratio(image.size, profile.expected_size):
            raise ValueError(
                f"{profile.rule_name} {profile.mode_name} requires an image with "
                f"{profile.expected_size[0]}:{profile.expected_size[1]} aspect ratio. "
                f"Current size: {image.size[0]}*{image.size[1]}."
            )

        prepared_image = prepare_source_image(
            image=image,
            source_path=source_path,
            profile=profile,
        )
        result_images = build_images_from_rules(prepared_image, profile.rules)
        final_image = compose_images_vertically(result_images)
        final_image.save(output_path, format="JPEG", quality=95)

    return output_path


def process_livery_image(
    source_path: str | Path,
    output_path: str | Path,
    rule_name: str,
    restore: bool = False,
) -> Path:
    profile = get_processing_profile(rule_name, restore=restore)
    return process_image(Path(source_path), Path(output_path), profile)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="RTLivery",
        description="Running Train Livery image conversion tool",
        epilog=(
            'Example: RTLivery.exe -p -m 1100 -i "d:/path/to/input/image.jpg" '
            '-o "d:/path/to/output/image.jpg"'
        ),
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("-p", "--process", action="store_true", help="process image")
    mode_group.add_argument("-r", "--restore", action="store_true", help="restore image")
    parser.add_argument(
        "-m",
        "--mode",
        required=True,
        metavar="RULE",
        help="rule name: 1100, DC85, KR5000",
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        metavar="INPUT",
        help="input image path, supports .jpg or .png",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        metavar="OUTPUT",
        help="output JPG image path",
    )
    return parser


def run_cli_mode(argv: list[str]) -> int:
    parser = create_argument_parser()
    args = parser.parse_args(argv)

    try:
        saved_path = process_livery_image(
            source_path=args.input,
            output_path=args.output,
            rule_name=args.mode,
            restore=args.restore,
        )
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    action = "restored" if args.restore else "processed"
    print(f"{args.mode} {action}: {saved_path}")
    return 0


def prompt_for_rule_set() -> RuleSet:
    options = list(RULE_SETS.values())
    print("请选择规则：")
    for index, rule_set in enumerate(options, start=1):
        print(f"{index}. {rule_set.name}")

    while True:
        choice = input("请输入规则编号或规则名：").strip()

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(options):
                return options[index]

        try:
            return get_rule_set(choice)
        except ValueError:
            print("输入无效，请重新输入。")


def prompt_for_profile(rule_set: RuleSet) -> ProcessingProfile:
    modes = {
        "1": rule_set.process,
        "2": rule_set.restore,
        "PROCESS": rule_set.process,
        "RESTORE": rule_set.restore,
        "P": rule_set.process,
        "R": rule_set.restore,
        "处理": rule_set.process,
        "处理图片": rule_set.process,
        "还原": rule_set.restore,
        "还原图片": rule_set.restore,
    }

    print("\n请选择操作：")
    print("1. 处理图片")
    print("2. 还原图片")

    while True:
        choice = input("请输入操作编号或名称：").strip()
        upper_choice = choice.upper()

        if choice in modes:
            return modes[choice]
        if upper_choice in modes:
            return modes[upper_choice]

        print("输入无效，请重新输入。")


def choose_source_image() -> Path | None:
    selected_file = filedialog.askopenfilename(
        title="请选择一张 JPG 或 PNG 图片",
        filetypes=[
            ("支持的图片", "*.jpg *.png"),
            ("JPG 图片", "*.jpg"),
            ("PNG 图片", "*.png"),
        ],
    )
    return Path(selected_file) if selected_file else None


def choose_output_path(default_name: str) -> Path | None:
    selected_file = filedialog.asksaveasfilename(
        title="请选择输出图片保存位置",
        defaultextension=".jpg",
        initialfile=default_name,
        filetypes=[("JPG 图片", "*.jpg")],
    )
    return Path(selected_file) if selected_file else None


def run_interactive_mode() -> None:
    rule_set = prompt_for_rule_set()
    profile = prompt_for_profile(rule_set)

    root = Tk()
    root.withdraw()

    try:
        source_path = choose_source_image()
        if source_path is None:
            return

        output_path = choose_output_path(
            f"{source_path.stem}_{profile.default_output_suffix}.jpg"
        )
        if output_path is None:
            return

        saved_path = process_image(source_path, output_path, profile)

        messagebox.showinfo(
            "处理完成",
            f"{profile.rule_name} {profile.mode_name} 已完成：\n{saved_path}",
        )
    except Exception as exc:
        messagebox.showerror("处理失败", str(exc))
    finally:
        root.destroy()


def main() -> int:
    if len(sys.argv) == 1:
        run_interactive_mode()
        return 0

    return run_cli_mode(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
