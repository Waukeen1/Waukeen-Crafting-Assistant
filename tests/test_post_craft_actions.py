from post_craft_actions import (
    POST_ACTION_CLOSE_GAME,
    POST_ACTION_NONE,
    POST_ACTION_SHUTDOWN_PC,
    normalize_post_action,
    post_craft_command_plan,
)


def test_unknown_post_action_is_safe_by_default():
    assert normalize_post_action("invalid") == POST_ACTION_NONE
    assert post_craft_command_plan("invalid", "completed") == []


def test_manual_stop_never_closes_game_or_computer():
    assert post_craft_command_plan(POST_ACTION_CLOSE_GAME, "manual") == []
    assert post_craft_command_plan(POST_ACTION_SHUTDOWN_PC, "manual") == []


def test_close_game_only_targets_known_poe_processes():
    commands = post_craft_command_plan(POST_ACTION_CLOSE_GAME, "completed")

    assert commands
    assert all(command[:3] == ["taskkill.exe", "/F", "/IM"] for command in commands)
    assert not any(command[0] == "shutdown.exe" for command in commands)


def test_shutdown_has_a_cancel_window_and_closes_poe_first():
    commands = post_craft_command_plan(POST_ACTION_SHUTDOWN_PC, "error", shutdown_delay=30)

    assert commands[-1][:4] == ["shutdown.exe", "/s", "/t", "30"]
    assert any(command[0] == "taskkill.exe" for command in commands[:-1])
