# -*- coding: utf-8 -*-

import json
import sys
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import FileManage as fm
from ImageProcess import process_livery_image
from SteamInteract import launch_game as open_steam_game
from SteamInteract import locate_game_folder


APP_DIR = Path(__file__).resolve().parent
LOCALES_DIR = APP_DIR / "locales"
EMPTY_TEMPLATE = APP_DIR / "empty_template"
DEFAULT_LANGUAGE = "zh-cn"
CARD_IMAGE_SIZE = (150, 120)
SLOT_IMAGE_SIZE = (125, 100)
WINDOW_ICON_SIZE = (256, 256)


def set_windows_taskbar_app_id() -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "RunningTrainLivery.Manager"
        )
    except Exception:
        pass


def resource_path(file_name: str) -> Path:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    return Path(bundle_dir) / file_name if bundle_dir else APP_DIR / file_name


def set_window_icon(window: tk.Tk | tk.Toplevel) -> None:
    icon_ico = resource_path("RTL_icon.ico")
    icon_png = resource_path("RTL_icon.png")

    try:
        if sys.platform == "win32" and icon_ico.exists():
            window.iconbitmap(default=str(icon_ico))
            window.iconbitmap(str(icon_ico))
            return

        if icon_png.exists():
            icon_image = Image.open(icon_png).convert("RGBA")
            icon_image.thumbnail(WINDOW_ICON_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(icon_image, master=window)
            window.iconphoto(True, photo)
            window._rtl_icon_photo = photo
            return

        if icon_ico.exists():
            window.iconbitmap(str(icon_ico))
    except tk.TclError as exc:
        print(f"Failed to set window icon: {exc}", file=sys.stderr)


class Localization:
    def __init__(self, language: str, locales_dir: Path = LOCALES_DIR) -> None:
        self.locales_dir = locales_dir
        self.language = language
        self.data = self._load(language)

    def _load(self, language: str) -> dict:
        path = self.locales_dir / f"{language}.json"
        if not path.exists():
            path = self.locales_dir / f"{DEFAULT_LANGUAGE}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def available_languages(self) -> list[str]:
        if not self.locales_dir.exists():
            return [DEFAULT_LANGUAGE]
        languages = sorted(p.stem for p in self.locales_dir.glob("*.json"))
        return languages or [DEFAULT_LANGUAGE]

    def set_language(self, language: str) -> None:
        self.language = language
        self.data = self._load(language)

    def t(self, key: str, **kwargs) -> str:
        value = self.data.get(key, key)
        if kwargs:
            try:
                return value.format(**kwargs)
            except Exception:
                return value
        return value


class LiveryManagerApp(tk.Tk):
    def __init__(self) -> None:
        set_windows_taskbar_app_id()
        super().__init__()

        self.storage_paths = fm.initialize_storage()
        self.settings = fm.load_settings()
        self.locale = Localization(self.settings.get("language", DEFAULT_LANGUAGE))

        self.title(self.t("app_title"))
        set_window_icon(self)
        self.geometry("1120x760")
        self.minsize(980, 640)

        self.slot_assignments: dict[str, list[str | None]] = {
            model: [None] * fm.GAME_SLOT_COUNT for model in fm.SUPPORTED_MODELS
        }
        self.slot_infos: dict[str, list[dict | None]] = {
            model: [None] * fm.GAME_SLOT_COUNT for model in fm.SUPPORTED_MODELS
        }
        self.unloaded_slots: dict[str, set[int]] = {
            model: set() for model in fm.SUPPORTED_MODELS
        }
        self.dirty_models: set[str] = set()
        self.slot_image_labels: dict[tuple[str, int], ttk.Label] = {}
        self.slot_text_labels: dict[tuple[str, int], ttk.Label] = {}
        self.library_frames: dict[str, ttk.Frame] = {}
        self.photo_refs: dict[str, ImageTk.PhotoImage] = {}
        self.current_model = tk.StringVar(value=fm.SUPPORTED_MODELS[0])
        self.game_path_var = tk.StringVar(value=fm.get_game_path())
        self.language_var = tk.StringVar(value=self.locale.language)
        self.backup_var = tk.StringVar()
        self.backup_combo: ttk.Combobox | None = None

        self._build_ui()
        self._startup_checks()
        self.refresh_all()

    def t(self, key: str, **kwargs) -> str:
        return self.locale.t(key, **kwargs)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=0, sticky="nsew")

        self.manage_tab = ttk.Frame(notebook, padding=10)
        self.edit_tab = ttk.Frame(notebook, padding=10)
        self.settings_tab = ttk.Frame(notebook, padding=10)

        notebook.add(self.manage_tab, text=self.t("tab_livery_manage"))
        notebook.add(self.edit_tab, text=self.t("tab_livery_edit"))
        notebook.add(self.settings_tab, text=self.t("tab_settings"))

        self._build_manage_tab()
        self._build_edit_tab()
        self._build_settings_tab()

        bottom_bar = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom_bar.grid(row=1, column=0, sticky="ew")
        ttk.Button(
            bottom_bar,
            text=self.t("button_launch_game"),
            command=self.launch_game,
        ).pack(side="right")

    def _build_manage_tab(self) -> None:
        self.manage_tab.columnconfigure(0, weight=1)
        self.manage_tab.rowconfigure(0, weight=1)

        model_notebook = ttk.Notebook(self.manage_tab)
        model_notebook.grid(row=0, column=0, sticky="nsew")

        for model in fm.SUPPORTED_MODELS:
            frame = ttk.Frame(model_notebook, padding=8)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            model_notebook.add(frame, text=model)

            slot_container = ttk.LabelFrame(frame, text=self.t("label_game_slots"), padding=8)
            slot_container.grid(row=0, column=0, sticky="ew")
            for index in range(fm.GAME_SLOT_COUNT):
                slot_container.columnconfigure(index, weight=1)
                slot = ttk.Frame(slot_container, padding=6, relief="ridge")
                slot.grid(row=0, column=index, padx=5, sticky="nsew")
                image_label = ttk.Label(slot)
                image_label.pack()
                text_label = ttk.Label(slot, anchor="center", justify="center")
                text_label.pack(fill="x", pady=(4, 0))
                slot.bind("<Button-1>", lambda _event, m=model, i=index: self.unload_slot(m, i))
                image_label.bind("<Button-1>", lambda _event, m=model, i=index: self.unload_slot(m, i))
                text_label.bind("<Button-1>", lambda _event, m=model, i=index: self.unload_slot(m, i))
                self.slot_image_labels[(model, index)] = image_label
                self.slot_text_labels[(model, index)] = text_label

            library_area = ttk.LabelFrame(frame, text=self.t("label_livery_list"), padding=8)
            library_area.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
            library_area.columnconfigure(0, weight=1)
            library_area.rowconfigure(0, weight=1)

            canvas = tk.Canvas(library_area, highlightthickness=0)
            scrollbar = ttk.Scrollbar(library_area, orient="vertical", command=canvas.yview)
            inner = ttk.Frame(canvas)
            inner.bind("<Configure>", lambda _event, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            self.library_frames[model] = inner

        button_bar = ttk.Frame(self.manage_tab)
        button_bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(button_bar, text=self.t("button_import_livery"), command=self.import_livery_dialog).pack(side="left")
        ttk.Button(button_bar, text=self.t("button_apply_changes"), command=self.apply_current_slots).pack(side="left", padx=(8, 0))
        ttk.Button(button_bar, text=self.t("button_refresh"), command=self.refresh_all).pack(side="left", padx=(8, 0))

        model_notebook.bind(
            "<<NotebookTabChanged>>",
            lambda event: self.current_model.set(
                fm.SUPPORTED_MODELS[event.widget.index("current")]
            ),
        )

    def _build_edit_tab(self) -> None:
        self.edit_tab.columnconfigure(1, weight=1)

        self.edit_image_var = tk.StringVar()
        self.edit_model_var = tk.StringVar(value="1100")
        self.edit_action_var = tk.StringVar(value="process")

        ttk.Label(self.edit_tab, text=self.t("label_image_file")).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.edit_tab, textvariable=self.edit_image_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(self.edit_tab, text=self.t("button_choose"), command=self.choose_edit_image).grid(row=0, column=2)

        ttk.Label(self.edit_tab, text=self.t("label_model")).grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Combobox(
            self.edit_tab,
            textvariable=self.edit_model_var,
            values=fm.SUPPORTED_MODELS,
            state="readonly",
            width=16,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(12, 0))

        ttk.Label(self.edit_tab, text=self.t("label_action")).grid(row=2, column=0, sticky="w", pady=(12, 0))
        action_frame = ttk.Frame(self.edit_tab)
        action_frame.grid(row=2, column=1, sticky="w", padx=8, pady=(12, 0))
        ttk.Radiobutton(
            action_frame,
            text=self.t("radio_process"),
            value="process",
            variable=self.edit_action_var,
        ).pack(side="left")
        ttk.Radiobutton(
            action_frame,
            text=self.t("radio_restore"),
            value="restore",
            variable=self.edit_action_var,
        ).pack(side="left", padx=(12, 0))

        ttk.Button(self.edit_tab, text=self.t("button_execute"), command=self.run_image_editor).grid(
            row=3,
            column=1,
            sticky="w",
            padx=8,
            pady=(16, 0),
        )

    def _build_settings_tab(self) -> None:
        self.settings_tab.columnconfigure(1, weight=1)

        ttk.Label(self.settings_tab, text=self.t("label_game_path")).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.settings_tab, textvariable=self.game_path_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=8,
        )
        ttk.Button(self.settings_tab, text=self.t("button_choose"), command=self.choose_game_path).grid(row=0, column=2)
        ttk.Button(
            self.settings_tab,
            text=self.t("button_auto_detect_game_path"),
            command=self.auto_detect_game_path,
        ).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(self.settings_tab, text=self.t("button_save"), command=self.save_game_path).grid(row=0, column=4, padx=(8, 0))
        ttk.Label(self.settings_tab, text=self.t("message_choose_game_path_title", hint="D:\\Program Files\\Steam\\steamapps\\common\\RUNNING TRAIN\\")).grid(
            row=1,
            column=1,
            columnspan=4,
            sticky="w",
            padx=8,
            pady=(6, 0),
        )

        ttk.Label(
            self.settings_tab,
            text=self.t("label_backup_restore"),
        ).grid(row=2, column=0, columnspan=5, sticky="w", pady=(18, 0))

        ttk.Button(
            self.settings_tab,
            text=self.t("button_backup"),
            command=self.backup_game_files,
        ).grid(row=3, column=1, sticky="w", padx=8, pady=(8, 0))
        ttk.Label(
            self.settings_tab,
            text=self.t("message_backup_location", path=self.storage_paths.backup),
        ).grid(row=3, column=2, columnspan=3, sticky="w", padx=8, pady=(8, 0))

        ttk.Button(
            self.settings_tab,
            text=self.t("button_restore"),
            command=self.restore_game_files,
        ).grid(row=4, column=1, sticky="w", padx=8, pady=(8, 0))
        self.backup_combo = ttk.Combobox(
            self.settings_tab,
            textvariable=self.backup_var,
            state="readonly",
        )
        self.backup_combo.grid(row=4, column=2, columnspan=3, sticky="ew", padx=8, pady=(8, 0))
        self.refresh_backup_list()

        ttk.Button(
            self.settings_tab,
            text=self.t("button_import_from_game"),
            command=self.import_from_game,
        ).grid(row=5, column=1, sticky="w", padx=8, pady=(16, 0))

        ttk.Label(self.settings_tab, text=self.t("message_language_setting_label")).grid(row=6, column=0, sticky="w", pady=(16, 0))
        self.language_combo = ttk.Combobox(
            self.settings_tab,
            textvariable=self.language_var,
            values=self.locale.available_languages(),
            state="readonly",
            width=16,
        )
        self.language_combo.grid(row=6, column=1, sticky="w", padx=8, pady=(16, 0))
        ttk.Button(
            self.settings_tab,
            text=self.t("button_language_save"),
            command=self.save_language,
        ).grid(row=6, column=2, sticky="w", pady=(16, 0))

        ttk.Label(self.settings_tab, text=self.t("label_storage_path")).grid(row=7, column=0, sticky="w", pady=(24, 0))
        ttk.Label(self.settings_tab, text=str(self.storage_paths.root)).grid(row=7, column=1, columnspan=4, sticky="w", padx=8, pady=(24, 0))

    def refresh_texts(self) -> None:
        self.title(self.t("app_title"))
        tabs = self.winfo_children()[0]
        tabs.tab(0, text=self.t("tab_livery_manage"))
        tabs.tab(1, text=self.t("tab_livery_edit"))
        tabs.tab(2, text=self.t("tab_settings"))

    def save_language(self) -> None:
        language = self.language_var.get().strip()
        if not language:
            return
        self.settings["language"] = language
        fm.save_settings(self.settings)
        self.locale.set_language(language)
        messagebox.showinfo(self.t("message_warning_title"), self.t("message_language_restart_hint"))

    def _startup_checks(self) -> None:
        if self.settings.get("show_startup_disclaimer", True):
            hide_future = ReminderDialog.show(
                parent=self,
                title=self.t("message_startup_disclaimer_title"),
                message=self.t("message_startup_disclaimer_body"),
                checkbox_text=self.t("checkbox_never_remind"),
                confirm_text=self.t("button_confirm"),
            )
            if hide_future:
                self.settings["show_startup_disclaimer"] = False
                fm.save_settings(self.settings)

        if not self.game_path_var.get() and not self.settings.get("editor_only_mode", False):
            choice = GamePathStartupDialog.show(self, self.locale)
            if choice == "full":
                detected_path = locate_game_folder()
                if detected_path is not None:
                    self.game_path_var.set(str(detected_path))
                    self.save_game_path()
                    self.settings = fm.load_settings()
                else:
                    self.choose_game_path()
                    self.settings = fm.load_settings()
            elif choice == "editor_only":
                self.settings["editor_only_mode"] = True
                fm.save_settings(self.settings)

        if (
            self.game_path_var.get()
            and not self.settings.get("editor_only_mode", False)
            and not fm.list_liveries()
        ):
            should_import = messagebox.askyesno(
                self.t("dialog_import_livery"),
                self.t("message_import_game_prompt"),
            )
            if should_import:
                self.import_from_game()

    def choose_game_path(self) -> None:
        selected = filedialog.askdirectory(
            title=self.t("message_choose_game_path_title", hint="D:\\Program Files\\Steam\\steamapps\\common\\RUNNING TRAIN\\")
        )
        if selected:
            self.game_path_var.set(selected)
            self.save_game_path()

    def auto_detect_game_path(self) -> None:
        detected_path = locate_game_folder()
        if detected_path is None:
            messagebox.showwarning(
                self.t("message_auto_detect_failed_title"),
                self.t("message_auto_detect_failed_body"),
                parent=self,
            )
            return

        self.game_path_var.set(str(detected_path))
        self.save_game_path()

    def refresh_backup_list(self) -> None:
        if self.backup_combo is None:
            return

        backup_names = [path.name for path in fm.list_backups()]
        self.backup_combo.configure(values=backup_names)
        if self.backup_var.get() not in backup_names:
            self.backup_var.set(backup_names[0] if backup_names else "")

    def offer_game_backup(self) -> None:
        should_backup = messagebox.askyesno(
            self.t("message_backup_prompt_title"),
            self.t("message_backup_prompt_body"),
            parent=self,
        )
        if should_backup:
            self.backup_game_files()

    def backup_game_files(self) -> None:
        game_path = self.game_path_var.get().strip()
        if not game_path:
            messagebox.showwarning(
                self.t("message_no_game_path_title"),
                self.t("message_no_game_path_body"),
                parent=self,
            )
            return

        try:
            backup_path = fm.backup_game_textures(game_path=game_path)
            messagebox.showinfo(
                self.t("message_warning_title"),
                self.t("message_backup_done", path=backup_path),
                parent=self,
            )
            self.refresh_backup_list()
        except Exception as exc:
            messagebox.showerror(
                self.t("message_backup_failed_title"),
                str(exc),
                parent=self,
            )

    def restore_game_files(self) -> None:
        game_path = self.game_path_var.get().strip()
        if not game_path:
            messagebox.showwarning(
                self.t("message_no_game_path_title"),
                self.t("message_no_game_path_body"),
                parent=self,
            )
            return

        selected_backup_name = self.backup_var.get().strip()
        backup_paths = {path.name: path for path in fm.list_backups()}
        backup_path = backup_paths.get(selected_backup_name)
        if backup_path is None:
            messagebox.showwarning(
                self.t("message_restore_choose_title"),
                self.t("message_restore_choose_body"),
                parent=self,
            )
            return

        should_restore = messagebox.askyesno(
            self.t("message_restore_confirm_title"),
            self.t("message_restore_confirm_body"),
            parent=self,
        )
        if not should_restore:
            return

        try:
            restored_path = fm.restore_game_textures(
                backup_path=backup_path,
                game_path=game_path,
            )
            self.dirty_models.clear()
            self.refresh_all()
            messagebox.showinfo(
                self.t("message_warning_title"),
                self.t("message_restore_done", path=restored_path),
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                self.t("message_restore_failed_title"),
                str(exc),
                parent=self,
            )

    def save_game_path(self) -> None:
        try:
            path = self.game_path_var.get().strip()
            fm.resolve_textures_root(path)
            self.settings["game_path"] = str(Path(path))
            self.settings["editor_only_mode"] = False
            fm.save_settings(self.settings)
            messagebox.showinfo(self.t("message_warning_title"), self.t("message_settings_saved"))
            self.refresh_all()
            self.offer_game_backup()
        except Exception as exc:
            messagebox.showerror(self.t("message_settings_failed_title"), str(exc))

    def choose_edit_image(self) -> None:
        selected = filedialog.askopenfilename(
            title=self.t("label_image_file"),
            filetypes=[
                (self.t("filetype_supported_images"), "*.jpg *.png"),
                (self.t("filetype_jpg"), "*.jpg"),
                (self.t("filetype_png"), "*.png"),
            ],
        )
        if selected:
            self.edit_image_var.set(selected)

    def get_image_preview(self, path: str | Path, size: tuple[int, int]) -> ImageTk.PhotoImage:
        image = Image.open(path).convert("RGB")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, "white")
        x = (size[0] - image.width) // 2
        y = (size[1] - image.height) // 2
        canvas.paste(image, (x, y))
        return ImageTk.PhotoImage(canvas)

    def get_record_preview_path(self, record: dict) -> Path | None:
        thumbnail = fm.get_absolute_livery_file(record, "thumbnail")
        if thumbnail is not None and thumbnail.exists():
            return thumbnail
        livery = fm.get_absolute_livery_file(record, "livery")
        if livery is not None and livery.exists():
            return livery
        return None

    def refresh_all(self) -> None:
        self.photo_refs.clear()
        for model in fm.SUPPORTED_MODELS:
            if model not in self.dirty_models:
                self.load_slots_from_game(model)
            self.refresh_slots(model)
            self.refresh_library(model)

    def load_slots_from_game(self, model: str) -> None:
        try:
            slots = fm.get_game_slots(model)
        except Exception:
            self.slot_assignments[model] = [None] * fm.GAME_SLOT_COUNT
            self.slot_infos[model] = [None] * fm.GAME_SLOT_COUNT
            return

        self.slot_infos[model] = slots
        self.unloaded_slots[model].clear()
        self.slot_assignments[model] = [slot.get("library_id") if slot else None for slot in slots]

    def refresh_slots(self, model: str) -> None:
        for index, livery_id in enumerate(self.slot_assignments[model]):
            image_label = self.slot_image_labels[(model, index)]
            text_label = self.slot_text_labels[(model, index)]
            slot_info = self.slot_infos[model][index]
            if livery_id is None and (slot_info is None or index in self.unloaded_slots[model]):
                image_label.configure(text=f"{self.t('slot_prefix')} {index + 1}", image="")
                text_label.configure(text=self.t("slot_blank"))
                continue

            try:
                if livery_id is not None:
                    record = fm.get_livery_record(livery_id)
                    preview_path = self.get_record_preview_path(record)
                    name = record["name"]
                    livery_hash = record["hash"]
                else:
                    preview_path = slot_info.get("thumbnail_path") or slot_info.get("texture_path")
                    name = slot_info.get("name", f"{self.t('slot_prefix')} {index + 1}")
                    livery_hash = slot_info.get("hash", "")

                if preview_path is not None:
                    photo = self.get_image_preview(preview_path, SLOT_IMAGE_SIZE)
                    key = f"slot:{model}:{index}:{livery_id}"
                    self.photo_refs[key] = photo
                    image_label.configure(image=photo, text="")
                text_label.configure(text=f"{name}\n{livery_hash[:6]}")
            except Exception:
                image_label.configure(text=f"{self.t('slot_prefix')} {index + 1}", image="")
                text_label.configure(text=self.t("slot_blank"))

    def refresh_library(self, model: str) -> None:
        container = self.library_frames[model]
        for child in container.winfo_children():
            child.destroy()

        records = fm.list_liveries(model)
        columns = 5
        for index, record in enumerate(records):
            card = ttk.Frame(container, padding=6, relief="ridge")
            card.grid(row=index // columns, column=index % columns, padx=6, pady=6, sticky="n")
            preview_path = self.get_record_preview_path(record)
            image_label = ttk.Label(card)
            image_label.pack()
            if preview_path is not None:
                photo = self.get_image_preview(preview_path, CARD_IMAGE_SIZE)
                key = f"library:{model}:{record['id']}"
                self.photo_refs[key] = photo
                image_label.configure(image=photo)

            ttk.Label(
                card,
                text=f"{record['name']}\n{record['hash'][:6]}",
                anchor="center",
                justify="center",
            ).pack(fill="x", pady=(4, 0))

            for widget in card.winfo_children():
                widget.bind("<Button-1>", lambda _event, item=record: self.mount_first_empty(item))
                widget.bind("<Button-3>", lambda event, item=record: self.show_livery_menu(event, item))
            card.bind("<Button-1>", lambda _event, item=record: self.mount_first_empty(item))
            card.bind("<Button-3>", lambda event, item=record: self.show_livery_menu(event, item))

    def unload_slot(self, model: str, slot_index: int) -> None:
        self.slot_assignments[model][slot_index] = None
        self.unloaded_slots[model].add(slot_index)
        self.dirty_models.add(model)
        self.refresh_slots(model)

    def mount_first_empty(self, record: dict) -> None:
        model = record["model"]
        available_slots = [
            index
            for index, livery_id in enumerate(self.slot_assignments[model])
            if livery_id is None and (index in self.unloaded_slots[model] or self.slot_infos[model][index] is None)
        ]
        if not available_slots:
            messagebox.showwarning(self.t("warning_slots_full_title"), self.t("warning_slots_full_body", model=model))
            return
        index = available_slots[0]
        self.slot_assignments[model][index] = record["id"]
        self.unloaded_slots[model].discard(index)
        self.dirty_models.add(model)
        self.refresh_slots(model)

    def show_livery_menu(self, event: tk.Event, record: dict) -> None:
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label=self.t("menu_export"), command=lambda: self.export_livery(record))
        menu.add_command(label=self.t("menu_edit"), command=lambda: self.edit_livery_dialog(record))
        menu.add_command(label=self.t("menu_delete"), command=lambda: self.delete_livery(record))
        menu.tk_popup(event.x_root, event.y_root)

    def import_livery_dialog(
        self,
        default_model: str | None = None,
        default_livery_path: str | Path | None = None,
    ) -> None:
        dialog = LiveryEditDialog(
            self,
            title=self.t("dialog_import_livery"),
            models=fm.SUPPORTED_MODELS,
            default_model=default_model or self.current_model.get(),
            default_livery_path=default_livery_path,
            locale=self.locale,
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return

        try:
            fm.add_livery_from_files(**dialog.result)
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror(self.t("message_import_failed_title"), str(exc))

    def edit_livery_dialog(self, record: dict) -> None:
        dialog = LiveryEditDialog(
            self,
            title=self.t("dialog_edit_livery"),
            models=(record["model"],),
            default_model=record["model"],
            default_name=record["name"],
            allow_empty_livery=True,
            locale=self.locale,
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return

        try:
            fm.update_livery(
                livery_id=record["id"],
                name=dialog.result["name"],
                livery_path=dialog.result["livery_path"] or None,
                thumbnail_path=dialog.result["thumbnail_path"] or None,
            )
            for model in fm.SUPPORTED_MODELS:
                if record["id"] in self.slot_assignments[model]:
                    self.dirty_models.add(model)
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror(self.t("message_edit_failed_title"), str(exc))

    def delete_livery(self, record: dict) -> None:
        if not messagebox.askyesno(self.t("dialog_delete_livery"), self.t("message_delete_confirm", name=record["name"])):
            return
        try:
            fm.delete_livery(record["id"])
            for model in fm.SUPPORTED_MODELS:
                for slot_index, item in enumerate(self.slot_assignments[model]):
                    if item == record["id"]:
                        self.dirty_models.add(model)
                        self.slot_assignments[model][slot_index] = None
                        self.unloaded_slots[model].add(slot_index)
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror(self.t("message_delete_failed_title"), str(exc))

    def export_livery(self, record: dict) -> None:
        output_dir = filedialog.askdirectory(title=self.t("dialog_export_folder"))
        if not output_dir:
            return
        try:
            exported = fm.export_livery(record["id"], output_dir)
            messagebox.showinfo(self.t("message_warning_title"), self.t("message_export_done", count=len(exported)))
        except Exception as exc:
            messagebox.showerror(self.t("message_export_failed_title"), str(exc))

    def apply_current_slots(self) -> None:
        model = self.current_model.get()
        if not fm.get_game_path():
            messagebox.showwarning(self.t("message_no_game_path_title"), self.t("message_no_game_path_body"))
            return

        try:
            for slot_index, livery_id in enumerate(self.slot_assignments[model]):
                if livery_id:
                    fm.install_livery_to_game(livery_id, slot_index)
                elif slot_index in self.unloaded_slots[model]:
                    fm.clear_game_livery_slot(model, slot_index, EMPTY_TEMPLATE)
            self.dirty_models.discard(model)
            messagebox.showinfo(self.t("message_warning_title"), self.t("message_apply_done", model=model))
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror(self.t("message_apply_failed_title"), str(exc))

    def launch_game(self) -> None:
        if self.dirty_models:
            models = "、".join(sorted(self.dirty_models))
            should_continue = messagebox.askyesno(
                self.t("message_unsaved_changes_title"),
                self.t("message_unsaved_changes_body", models=models),
                parent=self,
            )
            if not should_continue:
                return

        try:
            if not open_steam_game():
                messagebox.showerror(
                    self.t("message_launch_game_failed_title"),
                    self.t("message_launch_game_failed_body"),
                    parent=self,
                )
        except Exception as exc:
            messagebox.showerror(
                self.t("message_launch_game_failed_title"),
                str(exc),
                parent=self,
            )

    def import_from_game(self) -> None:
        if not fm.get_game_path():
            messagebox.showwarning(self.t("message_no_game_path_title"), self.t("message_no_game_path_body"))
            return

        try:
            records = []
            for model in fm.SUPPORTED_MODELS:
                for slot_index in range(fm.GAME_SLOT_COUNT):
                    record = fm.backup_game_livery(
                        model=model,
                        slot_index=slot_index,
                        name=f"{model}-涂装{slot_index + 1}",
                    )
                    if record is not None:
                        records.append(record)
            self.refresh_all()
            messagebox.showinfo(self.t("message_warning_title"), self.t("message_import_done", count=len(records)))
        except Exception as exc:
            messagebox.showerror(self.t("message_import_failed_title"), str(exc))

    def run_image_editor(self) -> None:
        source = self.edit_image_var.get().strip()
        if not source:
            messagebox.showwarning(self.t("message_warning_title"), self.t("message_select_image"))
            return

        model = self.edit_model_var.get()
        rule_name = "1100" if model == "1500" else model
        restore = self.edit_action_var.get() == "restore"
        if model == "DC85":
            self.settings = fm.load_settings()
            if self.settings.get("show_dc85_warning", True):
                hide_future = ReminderDialog.show(
                    parent=self,
                    title=self.t("message_dc85_title"),
                    message=self.t("message_dc85_body"),
                    checkbox_text=self.t("checkbox_never_remind"),
                    confirm_text=self.t("button_confirm"),
                )
                if hide_future:
                    self.settings["show_dc85_warning"] = False
                    fm.save_settings(self.settings)

        try:
            source_path = Path(source)
            if restore:
                save_to_library = messagebox.askyesno(
                    self.t("message_save_mode_title"),
                    self.t("message_save_to_library"),
                )
                if save_to_library:
                    temp_dir = Path(tempfile.mkdtemp(prefix="rtl_restore_"))
                    temp_output = temp_dir / f"{source_path.stem}_restored.jpg"
                    process_livery_image(source_path, temp_output, rule_name, restore=True)
                    self.import_livery_dialog(
                        default_model=model,
                        default_livery_path=temp_output,
                    )
                    return
                output_path = filedialog.asksaveasfilename(
                    title=self.t("message_no_game_path_title"),
                    defaultextension=".jpg",
                    initialfile=f"{source_path.stem}_restored.jpg",
                    filetypes=[(self.t("filetype_jpg"), "*.jpg")],
                )
            else:
                output_path = filedialog.asksaveasfilename(
                    title=self.t("message_no_game_path_title"),
                    defaultextension=".jpg",
                    initialfile=f"{source_path.stem}_processed.jpg",
                    filetypes=[(self.t("filetype_jpg"), "*.jpg")],
                )

            if not output_path:
                return

            saved_path = process_livery_image(
                source_path=source_path,
                output_path=output_path,
                rule_name=rule_name,
                restore=restore,
            )
            messagebox.showinfo(self.t("message_warning_title"), self.t("message_image_saved", path=saved_path))
        except Exception as exc:
            messagebox.showerror(self.t("message_processing_failed_title"), str(exc))


class LiveryEditDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        models: tuple[str, ...],
        default_model: str,
        default_name: str = "",
        default_livery_path: str | Path | None = None,
        default_thumbnail_path: str | Path | None = None,
        allow_empty_livery: bool = False,
        locale: Localization | None = None,
    ) -> None:
        super().__init__(parent)
        self.locale = locale or Localization(DEFAULT_LANGUAGE)
        self.title(title)
        set_window_icon(self)
        self.resizable(False, False)
        self.result: dict | None = None
        self.models = models
        self.allow_empty_livery = allow_empty_livery

        self.name_var = tk.StringVar(value=default_name)
        self.model_var = tk.StringVar(value=default_model)
        self.livery_path_var = tk.StringVar(value=str(default_livery_path) if default_livery_path else "")
        self.thumbnail_path_var = tk.StringVar()
        if default_thumbnail_path:
            self.thumbnail_path_var.set(str(default_thumbnail_path))

        self._build()
        self.grab_set()
        self.transient(parent)

    def t(self, key: str, **kwargs) -> str:
        return self.locale.t(key, **kwargs)

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text=self.t("label_name")).grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.name_var, width=42).grid(row=0, column=1, sticky="ew", padx=8)

        ttk.Label(frame, text=self.t("label_model")).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(frame, textvariable=self.model_var, values=self.models, state="readonly", width=14).grid(
            row=1, column=1, sticky="w", padx=8, pady=(10, 0)
        )

        ttk.Label(frame, text=self.t("label_livery_file")).grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.livery_path_var, width=42).grid(row=2, column=1, sticky="ew", padx=8, pady=(10, 0))
        ttk.Button(frame, text=self.t("button_choose"), command=self.choose_livery).grid(row=2, column=2, pady=(10, 0))

        ttk.Label(frame, text=self.t("label_thumbnail")).grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.thumbnail_path_var, width=42).grid(row=3, column=1, sticky="ew", padx=8, pady=(10, 0))
        ttk.Button(frame, text=self.t("button_choose"), command=self.choose_thumbnail).grid(row=3, column=2, pady=(10, 0))

        button_bar = ttk.Frame(frame)
        button_bar.grid(row=4, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(button_bar, text=self.t("button_cancel"), command=self.destroy).pack(side="right")
        ttk.Button(button_bar, text=self.t("button_confirm"), command=self.submit).pack(side="right", padx=(0, 8))

    def choose_livery(self) -> None:
        selected = filedialog.askopenfilename(
            title=self.t("label_livery_file"),
            filetypes=[
                (self.t("filetype_supported_images"), "*.jpg *.png"),
                (self.t("filetype_jpg"), "*.jpg"),
                (self.t("filetype_png"), "*.png"),
            ],
        )
        if selected:
            self.livery_path_var.set(selected)

    def choose_thumbnail(self) -> None:
        selected = filedialog.askopenfilename(
            title=self.t("label_thumbnail"),
            filetypes=[
                (self.t("filetype_supported_images"), "*.jpg *.png"),
                (self.t("filetype_jpg"), "*.jpg"),
                (self.t("filetype_png"), "*.png"),
            ],
        )
        if selected:
            self.thumbnail_path_var.set(selected)

    def submit(self) -> None:
        name = self.name_var.get().strip()
        livery_path = self.livery_path_var.get().strip()
        if not name:
            messagebox.showwarning(self.t("message_warning_title"), self.t("message_need_name"), parent=self)
            return
        if not livery_path and not self.allow_empty_livery:
            messagebox.showwarning(self.t("message_warning_title"), self.t("message_need_livery"), parent=self)
            return

        self.result = {
            "model": self.model_var.get(),
            "name": name,
            "livery_path": livery_path,
            "thumbnail_path": self.thumbnail_path_var.get().strip() or None,
        }
        self.destroy()


class ReminderDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        message: str,
        checkbox_text: str,
        confirm_text: str,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        set_window_icon(self)
        self.resizable(False, False)
        self.result = False
        self.hide_future_var = tk.BooleanVar(value=False)

        frame = ttk.Frame(self, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text=message, justify="left", wraplength=520).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(frame, text=checkbox_text, variable=self.hide_future_var).grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Button(frame, text=confirm_text, command=self.submit).grid(row=2, column=0, sticky="e", pady=(14, 0))

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.submit)

    def submit(self) -> None:
        self.result = self.hide_future_var.get()
        self.destroy()

    @classmethod
    def show(cls, parent: tk.Tk, title: str, message: str, checkbox_text: str, confirm_text: str) -> bool:
        dialog = cls(parent, title, message, checkbox_text, confirm_text)
        parent.wait_window(dialog)
        return dialog.result


class GamePathStartupDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, locale: Localization) -> None:
        super().__init__(parent)
        self.locale = locale
        self.title(self.t("message_editor_only_prompt_title"))
        set_window_icon(self)
        self.resizable(False, False)
        self.result = "cancel"

        frame = ttk.Frame(self, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            frame,
            text=self.t("message_editor_only_prompt_body"),
            justify="left",
            wraplength=520,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        button_bar = ttk.Frame(frame)
        button_bar.grid(row=1, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(button_bar, text=self.t("button_editor_only"), command=lambda: self.submit("editor_only")).pack(side="left")
        ttk.Button(button_bar, text=self.t("button_full_function"), command=lambda: self.submit("full")).pack(side="left", padx=(8, 0))
        ttk.Button(button_bar, text=self.t("button_cancel"), command=lambda: self.submit("cancel")).pack(side="left", padx=(8, 0))

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: self.submit("cancel"))

    def t(self, key: str, **kwargs) -> str:
        return self.locale.t(key, **kwargs)

    def submit(self, result: str) -> None:
        self.result = result
        self.destroy()

    @classmethod
    def show(cls, parent: tk.Tk, locale: Localization) -> str:
        dialog = cls(parent, locale)
        parent.wait_window(dialog)
        return dialog.result


def main() -> None:
    app = LiveryManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
