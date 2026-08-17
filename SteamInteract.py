import webbrowser
from pathlib import Path
import re

try:
    from steam_client.steam import Steam
    import winreg
except ImportError as exc:
    raise SystemExit(
        "This script requires: \nsteam_client \nwinreg \n\nPlease install the required packages with pip and try again."
    ) from exc


STEAM_APP_ID = 4630570
STEAM_GAME_URL = f"steam://run/{STEAM_APP_ID}"


def launch_game() -> bool:
    return webbrowser.open(STEAM_GAME_URL)

def locate_steam() -> str | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                             r"SOFTWARE\WOW6432Node\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        return Path(path)
    except:
        return None

def locate_game_folder(app_id: str = STEAM_APP_ID) -> Path | None:
    steam_path = locate_steam()

    try:
        library_file = steam_path / "steamapps" / "libraryfolders.vdf"

        if not library_file.exists():
            raise FileNotFoundError(f"Cannot find Steam library file at{library_file}")

        content = library_file.read_text(encoding="utf-8", errors="ignore")

        library_paths = re.findall(
            r'"path"\s+"([^"]+)"',
            content
        )

        if str(steam_path) not in library_paths:
            library_paths.insert(0, str(steam_path))

        for library in library_paths:
            game_dir = Path(library) / "steamapps" / "common"

            manifest = Path(library) / "steamapps" / f"appmanifest_{app_id}.acf"

            if manifest.exists():
                manifest_content = manifest.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

                match = re.search(
                    r'"installdir"\s+"([^"]+)"',
                    manifest_content
                )

                if match:
                    install_dir = game_dir / match.group(1)
                    return install_dir

        return None
    except:
        return None
