import webbrowser


STEAM_GAME_URL = "steam://run/4630570"


def launch_game() -> bool:
    """Open Running Train through Steam's URL protocol."""
    return webbrowser.open(STEAM_GAME_URL)
