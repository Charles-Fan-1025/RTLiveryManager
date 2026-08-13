# -*- coding: utf-8 -*-

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit(
        "This script requires Pillow. Install it with: pip install pillow"
    ) from exc


APP_DIR_NAME = "RunningTrainLivery"
DATA_DIR_NAME = "Data"
LIVERY_DIR_NAME = "Livery"
SETTINGS_FILE_NAME = "settings.json"
LIVERIES_FILE_NAME = "liveries.json"

SUPPORTED_MODELS = ("1100", "1500", "DC85", "KR5000")
GAME_TEXTURE_RELATIVE_PATHS = (
    Path("RunningTrain") / "Content" / "UGC" / "Textures",
    Path("RunningTrain") / "RunningTrain" / "Content" / "UGC" / "Textures",
    Path("Content") / "UGC" / "Textures",
)
GAME_SLOT_COUNT = 5
LIVERY_IMAGE_SIZE = (2048, 2048)
THUMBNAIL_SIZE = (1000, 800)
DEFAULT_SETTINGS = {
    "game_path": "",
    "editor_only_mode": False,
    "show_startup_disclaimer": True,
    "show_dc85_warning": True,
}
IGNORED_SHA256_HASHES = {
    "A37FEB4C9B507DC4E3C15E6297E85A1F9C8659CC38535B54F868BC82750493AA",
    "A3ADBF2A20D56E17847586E0EFFC638FB15EB8C719419E7A11E091BAD9437974",
    "EB399CE9C3486F7CAA1E24EAD22A79AD16C3EF35C850452692A2A58A772D37A3",
}


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    data: Path
    livery: Path
    settings: Path
    liveries: Path


def get_documents_dir() -> Path:
    documents_dir = Path.home() / "Documents"
    return documents_dir if documents_dir.exists() else Path.home()


def get_storage_paths(app_root: str | Path | None = None) -> StoragePaths:
    root = Path(app_root) if app_root is not None else get_documents_dir() / APP_DIR_NAME
    data_dir = root / DATA_DIR_NAME
    livery_dir = root / LIVERY_DIR_NAME
    return StoragePaths(
        root=root,
        data=data_dir,
        livery=livery_dir,
        settings=data_dir / SETTINGS_FILE_NAME,
        liveries=data_dir / LIVERIES_FILE_NAME,
    )


def initialize_storage(app_root: str | Path | None = None) -> StoragePaths:
    paths = get_storage_paths(app_root)
    paths.data.mkdir(parents=True, exist_ok=True)
    paths.livery.mkdir(parents=True, exist_ok=True)

    for model in SUPPORTED_MODELS:
        get_model_library_dir(model, app_root=paths.root).mkdir(parents=True, exist_ok=True)

    if not paths.settings.exists():
        save_settings(DEFAULT_SETTINGS.copy(), app_root=paths.root)

    if not paths.liveries.exists():
        save_liveries({"version": 1, "liveries": []}, app_root=paths.root)

    return paths


def load_json_file(path: Path, default_value: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default_value.copy()

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_settings(app_root: str | Path | None = None) -> dict[str, Any]:
    paths = initialize_storage(app_root)
    settings = load_json_file(paths.settings, DEFAULT_SETTINGS)
    merged_settings = DEFAULT_SETTINGS.copy()
    merged_settings.update(settings)
    return merged_settings


def save_settings(settings: dict[str, Any], app_root: str | Path | None = None) -> None:
    paths = get_storage_paths(app_root)
    save_json_file(paths.settings, settings)


def get_game_path(app_root: str | Path | None = None) -> str:
    return str(load_settings(app_root).get("game_path", ""))


def set_game_path(game_path: str | Path, app_root: str | Path | None = None) -> None:
    settings = load_settings(app_root)
    settings["game_path"] = str(Path(game_path))
    save_settings(settings, app_root)


def load_liveries(app_root: str | Path | None = None) -> dict[str, Any]:
    paths = initialize_storage(app_root)
    data = load_json_file(paths.liveries, {"version": 1, "liveries": []})
    data.setdefault("version", 1)
    data.setdefault("liveries", [])
    return data


def save_liveries(data: dict[str, Any], app_root: str | Path | None = None) -> None:
    paths = get_storage_paths(app_root)
    data.setdefault("version", 1)
    data.setdefault("liveries", [])
    save_json_file(paths.liveries, data)


def normalize_model(model: str) -> str:
    for supported_model in SUPPORTED_MODELS:
        if supported_model.upper() == model.upper():
            return supported_model
    raise ValueError(f"Unsupported model: {model}.")


def get_model_library_dir(model: str, app_root: str | Path | None = None) -> Path:
    paths = get_storage_paths(app_root)
    return paths.livery / normalize_model(model)


def get_livery_dir(
    model: str,
    livery_id: str,
    app_root: str | Path | None = None,
) -> Path:
    return get_model_library_dir(model, app_root=app_root) / livery_id


def get_resampling_filter() -> int:
    return getattr(Image, "Resampling", Image).LANCZOS


def calculate_file_hash(path: str | Path) -> str:
    sha256 = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest().upper()


def is_ignored_hash(file_hash: str) -> bool:
    return file_hash.upper() in IGNORED_SHA256_HASHES


def calculate_livery_hash(livery_path: Path) -> str:
    return calculate_file_hash(livery_path)


def make_livery_id(name: str) -> str:
    safe_name = "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in name.strip()
    ).strip("_")
    prefix = safe_name or "livery"
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def relative_to_storage(path: Path, app_root: str | Path | None = None) -> str:
    root = get_storage_paths(app_root).root
    return str(path.relative_to(root)).replace("\\", "/")


def get_absolute_livery_file(
    livery_record: dict[str, Any],
    file_key: str,
    app_root: str | Path | None = None,
) -> Path | None:
    paths = get_storage_paths(app_root)
    relative_path = livery_record.get("files", {}).get(file_key)
    if not relative_path:
        return None
    return paths.root / relative_path


def save_image_standardized(
    source_path: str | Path,
    target_path: str | Path,
    size: tuple[int, int],
) -> Path:
    source_path = Path(source_path)
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as image:
        prepared_image = image.convert("RGBA")
        prepared_image.putalpha(255)
        if prepared_image.size != size:
            prepared_image = prepared_image.resize(size, get_resampling_filter())
        prepared_image.convert("RGB").save(target_path, format="JPEG", quality=95)

    return target_path


def create_thumbnail_from_livery(livery_path: str | Path, target_path: str | Path) -> Path:
    return save_image_standardized(livery_path, target_path, THUMBNAIL_SIZE)


def build_livery_record(
    livery_id: str,
    name: str,
    model: str,
    target_livery: Path,
    target_thumbnail: Path | None,
    source: str,
    app_root: str | Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    livery_hash = calculate_livery_hash(target_livery)
    files = {"livery": relative_to_storage(target_livery, app_root=app_root)}
    file_hashes = {"livery": livery_hash}
    if target_thumbnail is not None:
        files["thumbnail"] = relative_to_storage(target_thumbnail, app_root=app_root)
        file_hashes["thumbnail"] = calculate_file_hash(target_thumbnail)

    record = {
        "id": livery_id,
        "name": name,
        "model": normalize_model(model),
        "hash": livery_hash,
        "file_hashes": file_hashes,
        "files": files,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }
    if extra:
        record.update(extra)
    return record


def upsert_livery_record(record: dict[str, Any], app_root: str | Path | None = None) -> None:
    data = load_liveries(app_root)
    records = data.get("liveries", [])
    data["liveries"] = [
        record if item.get("id") == record["id"] else item for item in records
    ]
    if not any(item.get("id") == record["id"] for item in records):
        data["liveries"].append(record)
    save_liveries(data, app_root)


def add_livery_from_files(
    model: str,
    name: str,
    livery_path: str | Path,
    thumbnail_path: str | Path | None = None,
    app_root: str | Path | None = None,
    source: str = "imported",
    standardize: bool = True,
) -> dict[str, Any]:
    initialize_storage(app_root)
    normalized_model = normalize_model(model)
    source_livery = Path(livery_path)
    source_thumbnail = Path(thumbnail_path) if thumbnail_path else None

    if not source_livery.is_file():
        raise FileNotFoundError(f"Livery file not found: {source_livery}")
    if source_thumbnail is not None and not source_thumbnail.is_file():
        raise FileNotFoundError(f"Thumbnail file not found: {source_thumbnail}")

    source_hash = calculate_livery_hash(source_livery)
    if is_ignored_hash(source_hash):
        raise ValueError("This livery is ignored by configured SHA256 filter.")

    livery_id = make_livery_id(name)
    target_dir = get_livery_dir(normalized_model, livery_id, app_root=app_root)
    target_dir.mkdir(parents=True, exist_ok=True)

    target_livery = target_dir / "livery.jpg"
    target_thumbnail = target_dir / "thumbnail.jpg"
    if standardize:
        save_image_standardized(source_livery, target_livery, LIVERY_IMAGE_SIZE)
        if source_thumbnail is not None:
            save_image_standardized(source_thumbnail, target_thumbnail, THUMBNAIL_SIZE)
    else:
        shutil.copy2(source_livery, target_livery)
        if source_thumbnail is not None:
            shutil.copy2(source_thumbnail, target_thumbnail)

    stored_thumbnail = target_thumbnail if source_thumbnail is not None else None

    record = build_livery_record(
        livery_id=livery_id,
        name=name,
        model=normalized_model,
        target_livery=target_livery,
        target_thumbnail=stored_thumbnail,
        source=source,
        app_root=app_root,
        extra={"source_hash": source_hash},
    )
    upsert_livery_record(record, app_root)
    return record


def update_livery(
    livery_id: str,
    name: str | None = None,
    livery_path: str | Path | None = None,
    thumbnail_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> dict[str, Any]:
    record = get_livery_record(livery_id, app_root=app_root)
    target_livery = get_absolute_livery_file(record, "livery", app_root=app_root)
    target_thumbnail = get_absolute_livery_file(record, "thumbnail", app_root=app_root)
    if target_livery is None:
        raise ValueError("Livery record has no livery file.")

    if livery_path is not None:
        source_hash = calculate_livery_hash(livery_path)
        if is_ignored_hash(source_hash):
            raise ValueError("This livery is ignored by configured SHA256 filter.")
        save_image_standardized(livery_path, target_livery, LIVERY_IMAGE_SIZE)
        record["source_hash"] = source_hash

    if thumbnail_path is not None:
        if target_thumbnail is None:
            target_thumbnail = get_livery_dir(
                record["model"],
                record["id"],
                app_root=app_root,
            ) / "thumbnail.jpg"
        save_image_standardized(thumbnail_path, target_thumbnail, THUMBNAIL_SIZE)
        record.setdefault("files", {})["thumbnail"] = relative_to_storage(
            target_thumbnail,
            app_root=app_root,
        )

    record["name"] = name if name is not None else record["name"]
    record["hash"] = calculate_livery_hash(target_livery)
    record.setdefault("file_hashes", {})["livery"] = calculate_file_hash(target_livery)
    if target_thumbnail is not None and target_thumbnail.exists():
        record["file_hashes"]["thumbnail"] = calculate_file_hash(target_thumbnail)
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    upsert_livery_record(record, app_root)
    return record


def list_liveries(
    model: str | None = None,
    app_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    data = load_liveries(app_root)
    records = []
    for record in data.get("liveries", []):
        known_hashes = {
            str(record.get("hash", "")).upper(),
            str(record.get("source_hash", "")).upper(),
            str(record.get("file_hashes", {}).get("livery", "")).upper(),
        }
        if not known_hashes.intersection(IGNORED_SHA256_HASHES):
            records.append(record)
    if model is None:
        return records

    normalized_model = normalize_model(model)
    return [record for record in records if record.get("model") == normalized_model]


def get_livery_record(
    livery_id: str,
    app_root: str | Path | None = None,
) -> dict[str, Any]:
    for record in list_liveries(app_root=app_root):
        if record.get("id") == livery_id:
            return record
    raise ValueError(f"Livery not found: {livery_id}.")


def resolve_textures_root(game_path: str | Path) -> Path:
    base_path = Path(game_path)
    candidates = [base_path, *(base_path / relative for relative in GAME_TEXTURE_RELATIVE_PATHS)]

    for candidate in candidates:
        if all((candidate / model).is_dir() for model in SUPPORTED_MODELS):
            return candidate

    raise FileNotFoundError(
        f"Could not find game texture folder under: {base_path}. "
        "Expected folders: 1100, 1500, DC85, KR5000."
    )


def get_configured_textures_root(app_root: str | Path | None = None) -> Path:
    game_path = get_game_path(app_root)
    if not game_path:
        raise ValueError("Game path has not been set.")
    return resolve_textures_root(game_path)


def validate_slot(slot_index: int) -> int:
    if not 0 <= slot_index < GAME_SLOT_COUNT:
        raise ValueError(f"Slot must be between 0 and {GAME_SLOT_COUNT - 1}.")
    return slot_index


def get_game_livery_paths(
    model: str,
    slot_index: int,
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> tuple[Path, Path]:
    normalized_model = normalize_model(model)
    slot_index = validate_slot(slot_index)
    textures_root = (
        resolve_textures_root(game_path)
        if game_path is not None
        else get_configured_textures_root(app_root)
    )
    model_dir = textures_root / normalized_model
    return model_dir / f"tex{slot_index}.jpg", model_dir / "thumb" / f"thumb{slot_index}.jpg"


def find_library_livery_by_hash(
    livery_hash: str,
    model: str | None = None,
    app_root: str | Path | None = None,
) -> dict[str, Any] | None:
    normalized_hash = livery_hash.upper()
    for record in list_liveries(model=model, app_root=app_root):
        known_hashes = {
            str(record.get("hash", "")).upper(),
            str(record.get("source_hash", "")).upper(),
            str(record.get("file_hashes", {}).get("livery", "")).upper(),
        }
        if normalized_hash in known_hashes:
            return record
    return None


def get_game_slot_info(
    model: str,
    slot_index: int,
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> dict[str, Any] | None:
    texture_path, thumbnail_path = get_game_livery_paths(
        model=model,
        slot_index=slot_index,
        game_path=game_path,
        app_root=app_root,
    )
    if not texture_path.exists():
        return None

    livery_hash = calculate_livery_hash(texture_path)
    if is_ignored_hash(livery_hash):
        return None

    matched_record = find_library_livery_by_hash(
        livery_hash,
        model=model,
        app_root=app_root,
    )
    return {
        "slot": slot_index,
        "model": normalize_model(model),
        "hash": livery_hash,
        "name": matched_record["name"] if matched_record else f"Slot {slot_index + 1}",
        "library_id": matched_record["id"] if matched_record else None,
        "texture_path": str(texture_path),
        "thumbnail_path": str(thumbnail_path) if thumbnail_path.exists() else "",
    }


def get_game_slots(
    model: str,
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> list[dict[str, Any] | None]:
    return [
        get_game_slot_info(
            model=model,
            slot_index=slot_index,
            game_path=game_path,
            app_root=app_root,
        )
        for slot_index in range(GAME_SLOT_COUNT)
    ]


def backup_game_livery(
    model: str,
    slot_index: int,
    name: str | None = None,
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> dict[str, Any] | None:
    texture_path, thumbnail_path = get_game_livery_paths(
        model=model,
        slot_index=slot_index,
        game_path=game_path,
        app_root=app_root,
    )
    livery_hash = calculate_livery_hash(texture_path)
    if is_ignored_hash(livery_hash):
        return None

    existing_record = find_library_livery_by_hash(
        livery_hash,
        model=model,
        app_root=app_root,
    )
    if existing_record is not None:
        return existing_record

    backup_name = name or f"{normalize_model(model)}-涂装{slot_index + 1}"
    record = add_livery_from_files(
        model=model,
        name=backup_name,
        livery_path=texture_path,
        thumbnail_path=thumbnail_path if thumbnail_path.exists() else None,
        app_root=app_root,
        source="game_backup",
        standardize=True,
    )
    record["game_slot"] = slot_index
    upsert_livery_record(record, app_root)
    return record


def backup_all_game_liveries(
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    records = []
    for model in SUPPORTED_MODELS:
        for slot_index in range(GAME_SLOT_COUNT):
            record = backup_game_livery(
                model=model,
                slot_index=slot_index,
                game_path=game_path,
                app_root=app_root,
            )
            if record is not None:
                records.append(record)
    return records


def install_livery_to_game(
    livery_id: str,
    slot_index: int,
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> tuple[Path, Path]:
    record = get_livery_record(livery_id, app_root=app_root)
    texture_target, thumbnail_target = get_game_livery_paths(
        model=record["model"],
        slot_index=slot_index,
        game_path=game_path,
        app_root=app_root,
    )
    source_livery = get_absolute_livery_file(record, "livery", app_root=app_root)
    source_thumbnail = get_absolute_livery_file(record, "thumbnail", app_root=app_root)
    if source_livery is None:
        raise ValueError("Livery record has no livery file.")

    texture_target.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_livery, texture_target)
    if source_thumbnail is not None and source_thumbnail.exists():
        shutil.copy2(source_thumbnail, thumbnail_target)
    else:
        create_thumbnail_from_livery(source_livery, thumbnail_target)
    return texture_target, thumbnail_target


def find_empty_slot_template(
    model: str,
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> tuple[Path, Path] | None:
    for slot_index in range(GAME_SLOT_COUNT):
        texture_path, thumbnail_path = get_game_livery_paths(
            model=model,
            slot_index=slot_index,
            game_path=game_path,
            app_root=app_root,
        )
        if texture_path.exists() and is_ignored_hash(calculate_livery_hash(texture_path)):
            return texture_path, thumbnail_path
    return None


def clear_game_livery_slot(
    model: str,
    slot_index: int,
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> tuple[Path, Path]:
    template_paths = find_empty_slot_template(
        model=model,
        game_path=game_path,
        app_root=app_root,
    )
    if template_paths is None:
        raise ValueError(
            f"No ignored-hash empty livery template was found for {normalize_model(model)}."
        )

    template_texture, template_thumbnail = template_paths
    texture_target, thumbnail_target = get_game_livery_paths(
        model=model,
        slot_index=slot_index,
        game_path=game_path,
        app_root=app_root,
    )

    texture_target.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_texture, texture_target)
    if template_thumbnail.exists():
        shutil.copy2(template_thumbnail, thumbnail_target)
    return texture_target, thumbnail_target


def apply_slots_to_game(
    model: str,
    slot_livery_ids: list[str | None],
    game_path: str | Path | None = None,
    app_root: str | Path | None = None,
) -> list[tuple[Path, Path]]:
    applied = []
    for slot_index, livery_id in enumerate(slot_livery_ids[:GAME_SLOT_COUNT]):
        if livery_id:
            applied.append(
                install_livery_to_game(
                    livery_id=livery_id,
                    slot_index=slot_index,
                    game_path=game_path,
                    app_root=app_root,
                )
            )
        else:
            applied.append(
                clear_game_livery_slot(
                    model=model,
                    slot_index=slot_index,
                    game_path=game_path,
                    app_root=app_root,
                )
            )
    return applied


def export_livery(
    livery_id: str,
    output_dir: str | Path,
    app_root: str | Path | None = None,
) -> list[Path]:
    record = get_livery_record(livery_id, app_root=app_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported = []
    for file_key, suffix in (("livery", "livery"), ("thumbnail", "thumbnail")):
        source_path = get_absolute_livery_file(record, file_key, app_root=app_root)
        if source_path is None or not source_path.exists():
            continue
        target_path = output_dir / f"{record['name']}_{suffix}{source_path.suffix}"
        shutil.copy2(source_path, target_path)
        exported.append(target_path)
    return exported


def delete_livery(livery_id: str, app_root: str | Path | None = None) -> None:
    record = get_livery_record(livery_id, app_root=app_root)
    data = load_liveries(app_root)
    data["liveries"] = [
        item for item in data.get("liveries", []) if item.get("id") != livery_id
    ]
    save_liveries(data, app_root)

    livery_dir = get_livery_dir(record["model"], record["id"], app_root=app_root)
    if livery_dir.exists():
        shutil.rmtree(livery_dir)
