POST_ACTION_NONE = "none"
POST_ACTION_CLOSE_GAME = "close_game"
POST_ACTION_SHUTDOWN_PC = "shutdown_pc"

VALID_POST_ACTIONS = {
    POST_ACTION_NONE,
    POST_ACTION_CLOSE_GAME,
    POST_ACTION_SHUTDOWN_PC,
}

POE_PROCESS_NAMES = (
    "PathOfExile.exe",
    "PathOfExile_x64.exe",
    "PathOfExileSteam.exe",
    "PathOfExile_x64Steam.exe",
)


def normalize_post_action(value):
    value = str(value or "").strip().lower()
    return value if value in VALID_POST_ACTIONS else POST_ACTION_NONE


def post_craft_command_plan(action, end_kind, shutdown_delay=30):
    action = normalize_post_action(action)
    if action == POST_ACTION_NONE or str(end_kind or "").lower() == "manual":
        return []

    commands = [
        ["taskkill.exe", "/F", "/IM", process_name]
        for process_name in POE_PROCESS_NAMES
    ]
    if action == POST_ACTION_SHUTDOWN_PC:
        delay = max(15, int(shutdown_delay))
        commands.append(
            [
                "shutdown.exe",
                "/s",
                "/t",
                str(delay),
                "/c",
                "Waukeen Crafting Assistant islemi tamamlandi.",
            ]
        )
    return commands
