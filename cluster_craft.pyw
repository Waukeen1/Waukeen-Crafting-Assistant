# -*- coding: utf-8 -*-
"""
Waukeen Crafting Assistant (Classic GUI + MicroDrift Core v2)
Full Classic GUI (Templates + Chain + Comb + Log + Settings + Hotkeys)
MicroDrift v2 click engine with strict down/up sequencing (no orb pick-ups).
1080p Windowed Fullscreen, DX12 compatible.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os, sys, json, configparser, threading, time, re, queue, traceback, subprocess, importlib, importlib.util, site
import ast
import functools
import hashlib
import shutil
import tempfile
import webbrowser
from collections import deque
import urllib.request
import urllib.parse

from phone_notifications import (
    DEFAULT_NTFY_SERVER,
    generate_ntfy_topic,
    ntfy_subscription_url,
    publish_ntfy,
)
from post_craft_actions import (
    POST_ACTION_CLOSE_GAME,
    POST_ACTION_NONE,
    POST_ACTION_SHUTDOWN_PC,
    normalize_post_action,
    post_craft_command_plan,
)

APP_NAME = "Waukeen Crafting Assistant"
APP_SHORT_NAME = "WCA"
APP_VERSION = "1.0.0"
UPDATE_REPOSITORY = "Waukeen1/Waukeen-Crafting-Assistant"
UPDATE_RELEASE_API = f"https://api.github.com/repos/{UPDATE_REPOSITORY}/releases/latest"
UPDATE_PACKAGE_NAME = "Waukeen-Crafting-Assistant-Windows.zip"
UPDATE_CHECKSUM_NAME = f"{UPDATE_PACKAGE_NAME}.sha256"

def _show_bootstrap_error(msg: str):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, APP_NAME, 0x10)
    except Exception:
        try:
            print(msg)
        except Exception:
            pass

def _module_exists(module_name):
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False

def _refresh_import_system():
    try:
        importlib.invalidate_caches()
    except Exception:
        pass
    try:
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            site.addsitedir(user_site)
    except Exception:
        pass
    try:
        for site_path in site.getsitepackages():
            if site_path and site_path not in sys.path:
                site.addsitedir(site_path)
    except Exception:
        pass

BOOTSTRAP_PACKAGE_ALIASES = {
    "pyautogui": ("pyautogui", ["pyautogui"]),
    "keyboard": ("keyboard", ["keyboard"]),
    "pyperclip": ("pyperclip", ["pyperclip"]),
    "pystray": ("pystray", ["pystray"]),
    "PIL": ("pillow", ["PIL"]),
    "PIL.Image": ("pillow", ["PIL"]),
    "PIL.ImageDraw": ("pillow", ["PIL"]),
    "PIL.ImageTk": ("pillow", ["PIL"]),
    "requests": ("requests", ["requests"]),
    "bs4": ("beautifulsoup4", ["bs4"]),
    "cv2": ("opencv-python-headless", ["cv2"]),
    "yaml": ("PyYAML", ["yaml"]),
    "tomlkit": ("tomlkit", ["tomlkit"]),
    "tomli": ("tomli", ["tomli"]),
    "tomli_w": ("tomli-w", ["tomli_w"]),
    "lxml": ("lxml", ["lxml"]),
    "dns": ("dnspython", ["dns"]),
    "jwt": ("PyJWT", ["jwt"]),
    "Crypto": ("pycryptodome", ["Crypto"]),
    "Cryptodome": ("pycryptodomex", ["Cryptodome"]),
    "nacl": ("PyNaCl", ["nacl"]),
    "OpenSSL": ("pyOpenSSL", ["OpenSSL"]),
    "win32api": ("pywin32", ["win32api"]),
    "win32con": ("pywin32", ["win32con"]),
    "win32gui": ("pywin32", ["win32gui"]),
    "win32clipboard": ("pywin32", ["win32clipboard"]),
    "pythoncom": ("pywin32", ["pythoncom"]),
    "win32com": ("pywin32", ["win32com"]),
    "sklearn": ("scikit-learn", ["sklearn"]),
    "fitz": ("PyMuPDF", ["fitz"]),
    "pymupdf": ("PyMuPDF", ["fitz"]),
    "Levenshtein": ("python-Levenshtein", ["Levenshtein"]),
    "serial": ("pyserial", ["serial"]),
    "usb": ("pyusb", ["usb"]),
    "dateutil": ("python-dateutil", ["dateutil"]),
    "dotenv": ("python-dotenv", ["dotenv"]),
    "OpenGL": ("PyOpenGL", ["OpenGL"]),
    "MySQLdb": ("mysqlclient", ["MySQLdb"]),
    "psycopg2": ("psycopg2-binary", ["psycopg2"]),
    "pymysql": ("PyMySQL", ["pymysql"]),
    "websocket": ("websocket-client", ["websocket"]),
    "multipart": ("python-multipart", ["multipart"]),
    "googleapiclient": ("google-api-python-client", ["googleapiclient"]),
    "google.generativeai": ("google-generativeai", ["google.generativeai"]),
    "google.cloud.storage": ("google-cloud-storage", ["google.cloud.storage"]),
    "google.cloud.bigquery": ("google-cloud-bigquery", ["google.cloud.bigquery"]),
    "google.cloud.firestore": ("google-cloud-firestore", ["google.cloud.firestore"]),
    "google.cloud.pubsub": ("google-cloud-pubsub", ["google.cloud.pubsub"]),
    "google.cloud.secretmanager": ("google-cloud-secret-manager", ["google.cloud.secretmanager"]),
    "google.cloud.aiplatform": ("google-cloud-aiplatform", ["google.cloud.aiplatform"]),
    "dxcam": ("dxcam[winrt]", ["dxcam"]),
    "winrt": ("dxcam[winrt]", ["winrt.windows.graphics.capture"]),
    "winrt.system": ("winrt-runtime", ["winrt.system"]),
    "winrt.windows.graphics.capture": ("dxcam[winrt]", ["winrt.windows.graphics.capture"]),
    "winrt.windows.graphics.capture.interop": (
        "winrt-Windows.Graphics.Capture",
        ["winrt.windows.graphics.capture.interop"],
    ),
    "winrt.windows.graphics.directx": (
        "winrt-Windows.Graphics.DirectX",
        ["winrt.windows.graphics.directx"],
    ),
    "winrt.windows.graphics.directx.direct3d11.interop": (
        "winrt-Windows.Graphics.DirectX.Direct3D11",
        ["winrt.windows.graphics.directx.direct3d11.interop"],
    ),
}

OPTIONAL_RUNTIME_IMPORTS = {
    "win32clipboard",
}

def _collect_runtime_imports():
    try:
        with open(os.path.abspath(__file__), "r", encoding="utf-8-sig") as f:
            tree = ast.parse(f.read(), filename=__file__)
    except Exception:
        return set()
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    stdlib.update({"tkinter", "typing"})
    third_party = set()
    for module_name in imports:
        if module_name in OPTIONAL_RUNTIME_IMPORTS:
            continue
        top_level = module_name.split(".", 1)[0]
        if top_level in stdlib:
            continue
        third_party.add(module_name)
    return third_party

def _package_candidates_for_module(module_name):
    candidates = []
    tried = set()

    def add(pip_name, modules):
        key = (pip_name, tuple(modules))
        if pip_name and key not in tried:
            candidates.append((pip_name, list(modules)))
            tried.add(key)

    if module_name in BOOTSTRAP_PACKAGE_ALIASES:
        pip_name, modules = BOOTSTRAP_PACKAGE_ALIASES[module_name]
        add(pip_name, modules)

    if "." in module_name:
        parts = module_name.split(".")
        for size in range(len(parts), 0, -1):
            candidate = ".".join(parts[:size])
            if candidate in BOOTSTRAP_PACKAGE_ALIASES:
                pip_name, modules = BOOTSTRAP_PACKAGE_ALIASES[candidate]
                add(pip_name, modules)

    top_level = module_name.split(".", 1)[0]
    if top_level in BOOTSTRAP_PACKAGE_ALIASES:
        pip_name, modules = BOOTSTRAP_PACKAGE_ALIASES[top_level]
        add(pip_name, modules)

    raw_candidates = [
        module_name,
        top_level,
        module_name.lower(),
        top_level.lower(),
        module_name.replace("_", "-"),
        top_level.replace("_", "-"),
        module_name.lower().replace("_", "-"),
        top_level.lower().replace("_", "-"),
    ]
    for raw in raw_candidates:
        add(raw, [top_level])

    return candidates

def _resolve_runtime_packages(extra_modules=None):
    requested_modules = _collect_runtime_imports()
    requested_modules.update(str(m).strip() for m in (extra_modules or []) if str(m).strip())
    packages = []
    for module_name in sorted(requested_modules):
        for pip_name, modules in _package_candidates_for_module(module_name):
            packages.append((module_name, pip_name, modules))
    deduped = []
    seen = set()
    for module_name, pip_name, modules in packages:
        key = (module_name, pip_name)
        if key not in seen:
            deduped.append((module_name, pip_name, modules))
            seen.add(key)
    return deduped

def ensure_runtime_dependencies(app_title, extra_modules=None):
    _refresh_import_system()
    package_defs = _resolve_runtime_packages(extra_modules=extra_modules)
    missing = [(module_name, pip_name, modules) for module_name, pip_name, modules in package_defs if any(not _module_exists(name) for name in modules)]
    if not missing:
        return
    unresolved = []
    attempted = []
    grouped = {}
    for module_name, pip_name, modules in missing:
        grouped.setdefault(module_name, []).append((pip_name, modules))

    for module_name, candidates in grouped.items():
        resolved = False
        for pip_name, modules in candidates:
            if pip_name not in attempted:
                attempted.append(pip_name)
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", pip_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                continue
            _refresh_import_system()
            if all(_module_exists(name) for name in modules):
                resolved = True
                break
        if not resolved:
            unresolved.append(module_name)

    _refresh_import_system()
    package_defs = _resolve_runtime_packages(extra_modules=extra_modules)
    still_missing = [module_name for module_name, pip_name, modules in package_defs if any(not _module_exists(name) for name in modules)]
    final_missing = list(dict.fromkeys(unresolved + still_missing))
    if final_missing:
        _show_bootstrap_error(
            "Bazi kutuphaneler yuklenemedi.\n\n"
            f"Eksikler: {', '.join(final_missing)}"
        )
        raise SystemExit(1)

ensure_runtime_dependencies(APP_NAME)

try:
    import pyautogui, keyboard, pyperclip, requests
except ModuleNotFoundError as exc:
    ensure_runtime_dependencies(APP_NAME, extra_modules=[exc.name])
    import pyautogui, keyboard, pyperclip, requests
import generic_item_craft as generic_item
import flask_craft_guide as flask_guide
import auto_flask
import cluster_trade
import map_craft_rules as map_rules
import voyage_planner as voyage
try:
    import dxcam
except ModuleNotFoundError as exc:
    ensure_runtime_dependencies(APP_NAME, extra_modules=[exc.name])
    import dxcam
except Exception:
    dxcam = None

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ModuleNotFoundError as exc:
    ensure_runtime_dependencies(APP_NAME, extra_modules=[exc.name, "PIL"])
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except Exception:
    pystray = None
    Image = None
    ImageDraw = None
    TRAY_AVAILABLE = False

RE_FIRST_NUMBER = re.compile(r"(\d+(?:\.\d+)?)")
RE_SIGNED_INT = re.compile(r"([+-]?\d+)(?:%)?")
RE_AFFIX_TAG = re.compile(r"\[(P|S)\]")
RE_TARGET_CONTENT = re.compile(r"\]\s(.+)")
RE_TRAILING_ROLL = re.compile(r"\((\d+)\)\s*$")
RE_TARGET_SPEND = re.compile(r"\[(\d+)\]")
RE_NORMALIZE_PREFIX = re.compile(r"^\[[PS]\](?:\[\d+\])?\s*", re.I)
RE_NORMALIZE_NOTABLE = re.compile(r"1 added passive skill is\s*", re.I)
RE_NORMALIZE_SMALL_GRANT = re.compile(r"added small passive skills (also )?grant:?\s*", re.I)
RE_NORMALIZE_SMALL_HAVE = re.compile(r"added small passive skills have\s*", re.I)
RE_ADVANCED_ROLL_RANGE = re.compile(
    r"(?<=\d)\([+-]?\d+(?:\.\d+)?(?:-[+-]?\d+(?:\.\d+)?)?\)"
)
RE_INTANGIBILITY_METADATA = re.compile(
    r"^intangibility\s*:\s*\d+(?:\.\d+)?%?$",
    re.IGNORECASE,
)
MATCH_WILDCARD_PATTERN = r"[\d\.]+%?"

# ================ PATHS & CONSTANTS ================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATE_DIR = os.path.join(BASE_DIR, "itemcraft")
MAP_TEMPLATE_DIR = os.path.join(BASE_DIR, "mapcraft")
BASE_JEWEL_TEMPLATE_DIR = os.path.join(BASE_DIR, "basejewelcraft")
GENERIC_ITEM_TEMPLATE_DIR = os.path.join(BASE_DIR, "genericitemcraft")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
SETTINGS_INI = os.path.join(BASE_DIR, "settings.ini")
APP_ICON_PNG = os.path.join(BASE_DIR, "assets", "wca_icon.png")
APP_ICON_ICO = os.path.join(BASE_DIR, "assets", "wca_icon.ico")
BUILD_INFO_PATH = os.path.join(BASE_DIR, "build_info.json")
UPDATER_EXE = os.path.join(BASE_DIR, "updater", "WCA Updater.exe")
CLUSTER_P_PATH = os.path.join(DATA_DIR, "cluster_p.txt")
CLUSTER_S_PATH = os.path.join(DATA_DIR, "cluster_s.txt")
BASE_JEWEL_AFFIX_PATH = os.path.join(DATA_DIR, "base_jewel_affixes.json")
ITEM_AFFIX_CATALOG_PATH = os.path.join(DATA_DIR, "item_affixes.json")
MAP_MODS_PATH = os.path.join(DATA_DIR, "map_mods.json")
DEFAULT_BASE_JEWEL_CRIT_MODS = [
    "+#% to Global Critical Strike Multiplier",
    "+#% to Critical Strike Multiplier with Fire Skills",
    "+#% to Critical Strike Multiplier with Cold Skills",
    "+#% to Critical Strike Multiplier with Lightning Skills",
    "+#% to Critical Strike Multiplier with Elemental Skills",
]
DEFAULT_BASE_JEWEL_LIFE_MODS = ["#% increased maximum Life"]
BASE_JEWEL_STALE_READ_LIMIT = 6
GENERIC_ITEM_STALE_READ_LIMIT = 6

try:
    with open(BUILD_INFO_PATH, "r", encoding="utf-8") as build_info_file:
        APP_VERSION = str(json.load(build_info_file).get("version", APP_VERSION)).strip() or APP_VERSION
except Exception:
    pass

# cluster paths korunuyor — classify_mod_type() combcraft prefix/suffix tespiti için kullanıyor

WINDOW_W, WINDOW_H = 420, 500
FLASK_GUIDE_W, FLASK_GUIDE_H = 344, WINDOW_H
FLASK_GUIDE_GAP = 4
CLUSTER_TRADE_W, CLUSTER_TRADE_H = 390, WINDOW_H
CLUSTER_TRADE_GAP = 4
PADX, PADY = 5, 5
shift_spam_active = False
socket_shift_spam_orb = None
chain_backup_slot_warning_shown = False

# Effect35 mod tier aralıkları: (pattern, min_roll, max_roll, tier)
# tier1 en iyi, tier3 en kötü
EFFECT35_TIERS = [
    # Prefix - increased Damage
    (re.compile(r'increased damage', re.I), 2, 2, 3),
    (re.compile(r'increased damage', re.I), 3, 3, 2),
    (re.compile(r'increased damage', re.I), 4, 99, 1),
    # Prefix - Armour
    (re.compile(r'to armour', re.I), 11, 20, 3),
    (re.compile(r'to armour', re.I), 21, 30, 2),
    (re.compile(r'to armour', re.I), 31, 99, 1),
    # Prefix - Evasion
    (re.compile(r'to evasion', re.I), 11, 20, 3),
    (re.compile(r'to evasion', re.I), 21, 30, 2),
    (re.compile(r'to evasion', re.I), 31, 99, 1),
    # Prefix - Maximum Energy Shield
    (re.compile(r'to maximum energy shield', re.I), 4, 5, 3),
    (re.compile(r'to maximum energy shield', re.I), 6, 9, 2),
    (re.compile(r'to maximum energy shield', re.I), 10, 99, 1),
    # Prefix - Maximum Life
    (re.compile(r'to maximum life', re.I), 2, 3, 3),
    (re.compile(r'to maximum life', re.I), 4, 7, 2),
    (re.compile(r'to maximum life', re.I), 8, 99, 1),
    # Prefix - Maximum Mana
    (re.compile(r'to maximum mana', re.I), 2, 5, 3),
    (re.compile(r'to maximum mana', re.I), 6, 8, 2),
    (re.compile(r'to maximum mana', re.I), 9, 99, 1),
    # Prefix - increased Effect
    (re.compile(r'increased effect', re.I), 25, 25, 2),
    (re.compile(r'increased effect', re.I), 35, 99, 1),
    # Suffix - Cast Speed
    (re.compile(r'increased cast speed', re.I), 1, 1, 3),
    (re.compile(r'increased cast speed', re.I), 2, 2, 2),
    (re.compile(r'increased cast speed', re.I), 3, 99, 1),
    # Suffix - Mana Regeneration Rate
    (re.compile(r'mana regeneration rate', re.I), 4, 4, 3),
    (re.compile(r'mana regeneration rate', re.I), 5, 5, 2),
    (re.compile(r'mana regeneration rate', re.I), 6, 99, 1),
    # Suffix - All Attributes
    (re.compile(r'to all attributes', re.I), 2, 2, 3),
    (re.compile(r'to all attributes', re.I), 3, 3, 2),
    (re.compile(r'to all attributes', re.I), 4, 99, 1),
    # Suffix - Dexterity
    (re.compile(r'to dexterity', re.I), 2, 3, 3),
    (re.compile(r'to dexterity', re.I), 4, 5, 2),
    (re.compile(r'to dexterity', re.I), 6, 99, 1),
    # Suffix - Intelligence
    (re.compile(r'to intelligence', re.I), 2, 3, 3),
    (re.compile(r'to intelligence', re.I), 4, 5, 2),
    (re.compile(r'to intelligence', re.I), 6, 99, 1),
    # Suffix - Strength
    (re.compile(r'to strength', re.I), 2, 3, 3),
    (re.compile(r'to strength', re.I), 4, 5, 2),
    (re.compile(r'to strength', re.I), 6, 99, 1),
    # Suffix - All Elemental Resistances
    (re.compile(r'to all elemental resistances', re.I), 2, 2, 3),
    (re.compile(r'to all elemental resistances', re.I), 3, 3, 2),
    (re.compile(r'to all elemental resistances', re.I), 4, 99, 1),
    # Suffix - Chaos Resistance
    (re.compile(r'to chaos resistance', re.I), 3, 3, 3),
    (re.compile(r'to chaos resistance', re.I), 4, 4, 2),
    (re.compile(r'to chaos resistance', re.I), 5, 99, 1),
    # Suffix - Cold Resistance
    (re.compile(r'to cold resistance', re.I), 2, 3, 3),
    (re.compile(r'to cold resistance', re.I), 4, 5, 2),
    (re.compile(r'to cold resistance', re.I), 6, 99, 1),
    # Suffix - Fire Resistance
    (re.compile(r'to fire resistance', re.I), 2, 3, 3),
    (re.compile(r'to fire resistance', re.I), 4, 5, 2),
    (re.compile(r'to fire resistance', re.I), 6, 99, 1),
    # Suffix - Lightning Resistance
    (re.compile(r'to lightning resistance', re.I), 2, 3, 3),
    (re.compile(r'to lightning resistance', re.I), 4, 5, 2),
    (re.compile(r'to lightning resistance', re.I), 6, 99, 1),
    # Suffix - Regenerate Life per Second
    (re.compile(r'regenerate.*life per second', re.I), 0.1, 0.1, 3),
    (re.compile(r'regenerate.*life per second', re.I), 0.15, 0.15, 2),
    (re.compile(r'regenerate.*life per second', re.I), 0.2, 99, 1),
]

@functools.lru_cache(maxsize=4096)
def get_mod_tier(mod_text):
    """Oyundaki mod metninin tier'ını döner. Tanınmazsa None."""
    low = mod_text.lower()
    num_m = RE_FIRST_NUMBER.search(low)
    if not num_m:
        return None
    val = float(num_m.group(1))
    for pat, mn, mx, tier in EFFECT35_TIERS:
        if pat.search(low) and mn <= val <= mx:
            return tier
    return None

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(MAP_TEMPLATE_DIR, exist_ok=True)
os.makedirs(BASE_JEWEL_TEMPLATE_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# ================ SETTINGS ================
settings_cfg = configparser.ConfigParser()
settings_cfg.optionxform = str
if os.path.exists(SETTINGS_INI):
    try:
        settings_cfg.read(SETTINGS_INI, encoding="utf-8")
    except Exception:
        # guard against corrupt ini
        pass

for sec in ("OrbLocations", "General", "Hotkeys", "Voyage", "Notifications", "AutoFlask"):
    if not settings_cfg.has_section(sec):
        settings_cfg.add_section(sec)

defaults = {
    ("General", "delay"): "30",
    ("General", "safe_mode"): "False",
    ("General", "auto_update"): "True",
    ("General", "post_craft_action"): POST_ACTION_NONE,
    ("Hotkeys", "start"): "F4",
    ("Hotkeys", "stop"): "F5",
    ("Voyage", "chart_grid_tl"): "",
    ("Voyage", "chart_grid_br"): "",
    ("Voyage", "board_grid_tl"): "",
    ("Voyage", "board_grid_br"): "",
    ("Voyage", "auto_place"): "True",
    ("Notifications", "enabled"): "False",
    ("Notifications", "provider"): "ntfy",
    ("Notifications", "server"): DEFAULT_NTFY_SERVER,
    ("Notifications", "topic"): generate_ntfy_topic(),
    ("AutoFlask", "life_enabled"): "True",
    ("AutoFlask", "life_threshold"): "98",
    ("AutoFlask", "life_key"): "1",
    ("AutoFlask", "mana_enabled"): "False",
    ("AutoFlask", "mana_threshold"): "25",
    ("AutoFlask", "mana_key"): "2",
}

for (sec, key), val in defaults.items():
    if not settings_cfg.has_option(sec, key):
        settings_cfg.set(sec, key, val)

def save_settings_now():
    with open(SETTINGS_INI, "w", encoding="utf-8") as f:
        settings_cfg.write(f)

save_settings_now()

def save_settings_debounced(min_interval=0.5):
    now = time.time()
    if not hasattr(save_settings_debounced, "_last"):
        save_settings_debounced._last = 0.0
    if (now - save_settings_debounced._last) >= min_interval:
        save_settings_now()
        save_settings_debounced._last = now

def get_delay_s():
    try:
        raw = (delay_var.get() or "").strip()
        if raw:
            return int(raw) / 1000.0
        return int(settings_cfg.get("General", "delay", fallback="30")) / 1000.0
    except Exception:
        return 0.03

class CraftRecoveryNeeded(Exception):
    pass

class CraftFatalError(CraftRecoveryNeeded):
    pass

RUNTIME_SAFE_MODE = False
SAFE_STACK_TRACKED_ORBS = {"Orb of Alteration", "Orb of Augmentation"}
SAFE_CRITICAL_ORBS = {
    "Regal Orb",
    "Orb of Scouring",
    "Orb of Annulment",
    "Exalted Orb",
    "Orb of Chance",
    "Vaal Orb",
}
SAFE_ALTER_VERIFY_EVERY = 20
SAFE_AUG_VERIFY_EVERY = 1
FAST_STACK_TRACKED_ORBS = {"Orb of Alteration", "Orb of Augmentation"}
FAST_ALTER_SLOT_CHECK_EVERY = 20
FAST_STACK_DEPLETION_THRESHOLD = 50

ACTIVE_ORB_SLOT_CACHE = {
    "Orb of Alteration": None,
    "Orb of Augmentation": None,
}
ACTIVE_ORB_STACK_CACHE = {
    "Orb of Alteration": None,
    "Orb of Augmentation": None,
}
ORB_VERIFY_COUNTERS = {
    "Orb of Alteration": 0,
    "Orb of Augmentation": 0,
}
FAST_ORB_SLOT_CACHE = {
    "Orb of Alteration": None,
    "Orb of Augmentation": None,
}
FAST_ORB_STACK_CACHE = {
    "Orb of Alteration": None,
    "Orb of Augmentation": None,
}
FAST_ORB_USE_COUNTERS = {
    "Orb of Alteration": 0,
    "Orb of Augmentation": 0,
}
CRAFT_CURRENCY_COUNTS = {}
CRAFT_CURRENCY_LOCK = threading.Lock()
CRAFT_RATES_CACHE = None
CRAFT_LEAGUE_ID_CACHE = None
CRAFT_COST_SUMMARY_PENDING = False
CRAFT_RATE_LEAGUE_OVERRIDE = "Mirage"

def reset_safe_runtime_tracking():
    global ACTIVE_ORB_SLOT_CACHE, ACTIVE_ORB_STACK_CACHE, ORB_VERIFY_COUNTERS
    ACTIVE_ORB_SLOT_CACHE = {
        "Orb of Alteration": None,
        "Orb of Augmentation": None,
    }
    ACTIVE_ORB_STACK_CACHE = {
        "Orb of Alteration": None,
        "Orb of Augmentation": None,
    }
    ORB_VERIFY_COUNTERS = {
        "Orb of Alteration": 0,
        "Orb of Augmentation": 0,
    }

def reset_fast_runtime_tracking():
    global FAST_ORB_SLOT_CACHE, FAST_ORB_STACK_CACHE, FAST_ORB_USE_COUNTERS
    FAST_ORB_SLOT_CACHE = {
        "Orb of Alteration": None,
        "Orb of Augmentation": None,
    }
    FAST_ORB_STACK_CACHE = {
        "Orb of Alteration": None,
        "Orb of Augmentation": None,
    }
    FAST_ORB_USE_COUNTERS = {
        "Orb of Alteration": 0,
        "Orb of Augmentation": 0,
    }

def reset_currency_usage_tracking():
    global CRAFT_CURRENCY_COUNTS, CRAFT_COST_SUMMARY_PENDING
    with CRAFT_CURRENCY_LOCK:
        CRAFT_CURRENCY_COUNTS = {}
    CRAFT_COST_SUMMARY_PENDING = True
    _perf_reset()

def record_currency_use(orb_name: str, count: int = 1):
    if not orb_name or count <= 0:
        return
    with CRAFT_CURRENCY_LOCK:
        CRAFT_CURRENCY_COUNTS[orb_name] = int(CRAFT_CURRENCY_COUNTS.get(orb_name, 0)) + int(count)

def get_currency_usage_snapshot():
    with CRAFT_CURRENCY_LOCK:
        return dict(CRAFT_CURRENCY_COUNTS)

def get_current_challenge_league_id_craft():
    global CRAFT_LEAGUE_ID_CACHE
    if CRAFT_LEAGUE_ID_CACHE:
        return CRAFT_LEAGUE_ID_CACHE
    if CRAFT_RATE_LEAGUE_OVERRIDE:
        CRAFT_LEAGUE_ID_CACHE = CRAFT_RATE_LEAGUE_OVERRIDE
        return CRAFT_LEAGUE_ID_CACHE
    headers = {
        "User-Agent": "Cluster Notable Scanner (utf-8, by Burak+GPT)",
        "From": "burakgundgdu@gmail.com",
    }
    resp = requests.get(
        "https://api.pathofexile.com/leagues",
        params={"type": "main"},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    leagues = resp.json()
    bad_tokens = ("Standard", "Hardcore", "SSF", "Ruthless")
    candidates = [
        lg for lg in leagues
        if not any(tok in lg.get("id", "") for tok in bad_tokens) and not lg.get("event")
    ]
    candidates.sort(key=lambda lg: lg.get("startAt") or "", reverse=True)
    league_id = candidates[0]["id"] if candidates else leagues[0]["id"]
    CRAFT_LEAGUE_ID_CACHE = league_id
    return league_id

def get_currency_rates_chaos_craft(league_id: str):
    global CRAFT_RATES_CACHE
    if CRAFT_RATES_CACHE:
        return dict(CRAFT_RATES_CACHE)

    rates = {"chaos": 1.0}
    headers = {
        "User-Agent": "Cluster Notable Scanner (utf-8, by Burak+GPT)",
        "From": "burakgundgdu@gmail.com",
    }
    league_name = CRAFT_RATE_LEAGUE_OVERRIDE or league_id or "Mirage"
    exchange_url = "https://poe.ninja/poe1/api/economy/exchange/current/overview"
    exchange_aliases = {
        "chaos": ["chaos", "chaos orb"],
        "divine": ["divine", "divine orb"],
        "fracturing-orb": ["fracturing-orb", "fracturing orb"],
        "alch": ["alch", "alchemy", "alchemy orb", "orb of alchemy"],
        "alt": ["alt", "alteration", "alteration orb", "orb of alteration"],
        "aug": ["aug", "augmentation", "augmentation orb", "orb of augmentation"],
        "scour": ["scour", "scouring", "scouring orb", "orb of scouring"],
        "exalted": ["exalted", "exalted orb"],
        "regal": ["regal", "regal orb"],
        "annul": ["annul", "annulment orb", "orb of annulment"],
        "transmute": ["transmute", "transmutation", "transmutation orb", "orb of transmutation"],
        "chance": ["chance", "chance orb", "orb of chance"],
        "chaos-orb": ["chaos-orb", "chaos orb"],
        "vaal": ["vaal", "vaal orb"],
    }
    try:
        resp = requests.get(
            exchange_url,
            params={"league": league_name, "type": "Currency"},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for c in data.get("lines", []):
            currency_id = str(c.get("id") or "").lower()
            primary_value = c.get("primaryValue")
            if not currency_id or primary_value is None:
                continue
            value = float(primary_value)
            rates[currency_id] = value
            rates[currency_id.replace("-", " ")] = value
            for alias in exchange_aliases.get(currency_id, []):
                rates[alias] = value
    except Exception:
        pass

    if "divine orb" in rates and "divine" not in rates:
        rates["divine"] = rates["divine orb"]
    if len(rates) == 1:
        rates.update({"divine": 200.0, "divine orb": 200.0})
    CRAFT_RATES_CACHE = dict(rates)
    return rates

def _orb_name_to_rate_alias(orb_name: str):
    mapping = {
        "Orb of Alteration": "orb of alteration",
        "Orb of Augmentation": "orb of augmentation",
        "Orb of Scouring": "orb of scouring",
        "Orb of Annulment": "orb of annulment",
        "Regal Orb": "regal orb",
        "Exalted Orb": "exalted orb",
        "Orb of Transmutation": "orb of transmutation",
        "Orb of Chance": "orb of chance",
        "Orb of Alchemy": "orb of alchemy",
        "Vaal Orb": "vaal orb",
        "Chaos Orb": "chaos orb",
        "Divine Orb": "divine orb",
    }
    return mapping.get(orb_name, (orb_name or "").strip().lower())

def get_currency_cost_summary_lines():
    counts = get_currency_usage_snapshot()
    if not counts:
        return ["[COST] Kullanilan currency: yok"]
    detail = ", ".join(f"{name} x{amount}" for name, amount in sorted(counts.items()))
    return [f"[COST] Kullanilan currency: {detail}"]

def log_currency_cost_summary():
    for line in get_currency_cost_summary_lines():
        log_message(line)

RUNTIME_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(sys.argv[0])),
    "data",
)
CURSOR_CALIBRATION_DIR = os.path.join(RUNTIME_DATA_DIR, "cursor_calibration")
CURSOR_DEFAULT_CROP_PNG = os.path.join(CURSOR_CALIBRATION_DIR, "default_crop.png")
CURSOR_ACTIVE_CROP_PNG = os.path.join(CURSOR_CALIBRATION_DIR, "active_crop.png")
FAST_CURSOR_PATCH_BOX = (2, 9, 5, 12)
FAST_CURSOR_CROP_SIZE = (40, 53)
FAST_CURSOR_PATCH_SIZE = (
    int(FAST_CURSOR_PATCH_BOX[2] - FAST_CURSOR_PATCH_BOX[0]),
    int(FAST_CURSOR_PATCH_BOX[3] - FAST_CURSOR_PATCH_BOX[1]),
)
FAST_CURSOR_MONITOR_INTERVAL = 0.005
FAST_CURSOR_TRANSITION_TIMEOUT = 0.20
FAST_CURSOR_LIVE_SAMPLE_COUNT = 3
FAST_CURSOR_LIVE_SAMPLE_INTERVAL = 0.10
FAST_CURSOR_LIVE_STATE_SETTLE = 0.40
FAST_CURSOR_LIVE_WARMUP_CAPTURES = 2
FAST_CURSOR_LOG_SUCCESS_DETAILS = False
FAST_CURSOR_PICK_RETRIES = 3
FAST_CURSOR_APPLY_RETRIES = 3
FAST_CURSOR_CLEANUP_RETRIES = 3
FAST_CURSOR_TRANSITION_CONFIRM_SAMPLES = 2
FAST_CURSOR_RETRY_WAIT = 0.03
FAST_CURSOR_SHIFT_RELEASE_RETRIES = 2
FAST_SLOT_PROBE_RETRIES = 3
FAST_SLOT_PROBE_RETRY_WAIT = 0.06
FAST_CURSOR_MODEL = {
    "ready": False,
    "width": int(FAST_CURSOR_PATCH_SIZE[0]),
    "height": int(FAST_CURSOR_PATCH_SIZE[1]),
    "patch_box": (0, 0, int(FAST_CURSOR_PATCH_SIZE[0]), int(FAST_CURSOR_PATCH_SIZE[1])),
    "default_avg": (),
    "active_avg": (),
}
FAST_CURSOR_MONITOR = {
    "running": False,
    "thread": None,
    "state": "unknown",
    "d_default": None,
    "d_active": None,
    "sample_id": 0,
    "last_error": "",
    "warned": False,
}
FAST_CURSOR_MONITOR_LOCK = threading.Lock()
FAST_CURSOR_CAPTURE_LOCK = threading.Lock()
FAST_CURSOR_CAPTURE_STATE = {
    "dxcam_cameras": {},
    "dxcam_backends": {},
    "fallback_logged": False,
}

def critical_orb_right_click_safe(x: int, y: int):
    _instant_move(x, y)
    safe_wait(0.07)
    pyautogui.mouseDown(button="right")
    safe_wait(0.04)
    pyautogui.mouseUp(button="right")
    safe_wait(0.11)

# ================ CLIPBOARD (FAST) ================

# ================ LOGGING & GUI QUEUES ================
log_queue, gui_queue = queue.Queue(maxsize=400), queue.Queue(maxsize=100)
session_log_file = None
session_log_lock = threading.Lock()
LOG_GUI_HISTORY = deque(maxlen=2500)
LOG_GUI_LINE_LIMIT = 2500
LOG_GUI_ORB_CONTEXT = 10
LOG_GUI_PRE_ORB_LINES = 12
LOG_GUI_FALLBACK_LINES = 180

CRAFT_NOTIFICATION_LOCK = threading.Lock()
CRAFT_NOTIFICATION_STATE = {
    "active": False,
    "sent": False,
    "mode": "Craft",
    "started_at": 0.0,
    "reason": "",
    "kind": "completed",
    "rank": 0,
}


def _notification_mode_label(settings):
    logic = str(settings.get("craft_logic") or "craft").replace("_", " ").title()
    if settings.get("chain_craft"):
        return f"{logic} Chain"
    return logic


def _notification_session_begin(settings):
    with CRAFT_NOTIFICATION_LOCK:
        CRAFT_NOTIFICATION_STATE.update(
            active=True,
            sent=False,
            mode=_notification_mode_label(settings),
            started_at=time.time(),
            reason="",
            kind="completed",
            rank=0,
        )


def _notification_set_reason(reason, kind="stopped", rank=1):
    reason = str(reason or "").strip().splitlines()[0]
    if not reason:
        return
    with CRAFT_NOTIFICATION_LOCK:
        if not CRAFT_NOTIFICATION_STATE["active"]:
            return
        if int(rank) >= int(CRAFT_NOTIFICATION_STATE["rank"]):
            CRAFT_NOTIFICATION_STATE["reason"] = reason[:280]
            CRAFT_NOTIFICATION_STATE["kind"] = kind
            CRAFT_NOTIFICATION_STATE["rank"] = int(rank)


def _notification_observe_log(message):
    text = str(message or "").strip().splitlines()[0]
    low = text.translate(
        str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    ).lower()
    if not text:
        return
    if "stop komutu" in low:
        _notification_set_reason("F5 ile manuel olarak durduruldu.", "manual", 100)
        return
    if any(token in low for token in ("[hata]", "[safe-fatal]", "beklenmeyen hata")):
        _notification_set_reason(text, "error", 90)
        return
    if any(
        token in low
        for token in (
            "currency bitmis",
            "currency bitti",
            "hata limiti asildi",
            "uygulanmamis olabilir",
            "monitor hazir olmadan",
            "pozisyonu bulunamadi",
            "rota bulunamadi",
            "durduruluyor",
        )
    ):
        _notification_set_reason(text, "error", 80)
        return
    if "craft durduruldu" in low and not low.startswith("[craft]"):
        _notification_set_reason(text, "error", 80)
        return
    if any(
        token in low
        for token in (
            "craft tamamlandi",
            "hedef tamamlandi",
            "hedefe ulasildi",
            "target reached",
        )
    ):
        _notification_set_reason(text, "completed", 30)


def _send_phone_notification_worker(server, topic, title, message, priority):
    try:
        publish_ntfy(server, topic, title, message, priority=priority)
        log_message("[NOTIFY] Telefon bildirimi gonderildi.")
    except Exception as exc:
        log_message(f"[NOTIFY] Telefon bildirimi gonderilemedi: {exc}")


def _notification_session_finish():
    with CRAFT_NOTIFICATION_LOCK:
        if not CRAFT_NOTIFICATION_STATE["active"] or CRAFT_NOTIFICATION_STATE["sent"]:
            return
        state = dict(CRAFT_NOTIFICATION_STATE)
        CRAFT_NOTIFICATION_STATE["active"] = False
        CRAFT_NOTIFICATION_STATE["sent"] = True

    if not settings_cfg.getboolean("Notifications", "enabled", fallback=False):
        return
    topic = settings_cfg.get("Notifications", "topic", fallback="").strip()
    if not topic:
        log_message("[NOTIFY] Bildirim acik ancak ntfy topic bos.")
        return

    elapsed = max(0, int(time.time() - float(state["started_at"] or time.time())))
    minutes, seconds = divmod(elapsed, 60)
    reason = state["reason"]
    if not reason:
        reason = "Islem tamamlandi." if not stop_event.is_set() else "Craft durduruldu."
    kind = state["kind"]
    if kind == "error":
        title, priority = "WCA - Craft hatayla durdu", 4
    elif kind == "manual":
        title, priority = "WCA - Craft durduruldu", 3
    else:
        title, priority = "WCA - Craft tamamlandi", 3
    message = f"Mod: {state['mode']}\nSure: {minutes} dk {seconds} sn\nNeden: {reason}"
    server = settings_cfg.get("Notifications", "server", fallback=DEFAULT_NTFY_SERVER)
    threading.Thread(
        target=_send_phone_notification_worker,
        args=(server, topic, title, message, priority),
        daemon=True,
    ).start()


def _notification_session_kind():
    with CRAFT_NOTIFICATION_LOCK:
        return str(CRAFT_NOTIFICATION_STATE.get("kind") or "completed")


def _execute_post_craft_action(settings, end_kind):
    action = normalize_post_action(settings.get("post_craft_action"))
    commands = post_craft_command_plan(action, end_kind, shutdown_delay=30)
    if not commands:
        if action != POST_ACTION_NONE and end_kind == "manual":
            log_message("[POST] Manuel durdurmada otomatik kapatma atlandi.")
        return

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for command in commands:
        try:
            if command[0].lower() == "shutdown.exe":
                subprocess.Popen(command, creationflags=flags)
                log_message(
                    "[POST] Bilgisayar 30 saniye icinde kapatilacak. "
                    "Iptal: shutdown /a"
                )
            else:
                subprocess.run(
                    command,
                    check=False,
                    timeout=5,
                    creationflags=flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as exc:
            log_message(f"[POST] Kapatma komutu uygulanamadi: {exc}")

    if action == POST_ACTION_CLOSE_GAME:
        log_message("[POST] Path of Exile kapatma komutu uygulandi.")

PERF_STATS = {}
PERF_STATS_LOCK = threading.Lock()
PERF_SUMMARY_PENDING = False

def _perf_record(name, elapsed):
    with PERF_STATS_LOCK:
        calls, total, max_elapsed = PERF_STATS.get(name, (0, 0.0, 0.0))
        calls += 1
        total += float(elapsed)
        if elapsed > max_elapsed:
            max_elapsed = float(elapsed)
        PERF_STATS[name] = (calls, total, max_elapsed)

def _perf_reset():
    global PERF_SUMMARY_PENDING
    with PERF_STATS_LOCK:
        PERF_STATS.clear()
    PERF_SUMMARY_PENDING = True

def _perf_summary_lines():
    with PERF_STATS_LOCK:
        items = list(PERF_STATS.items())
    if not items:
        return []
    items.sort(key=lambda kv: kv[1][1], reverse=True)
    lines = ["[PERF] Sicak yol ozeti:"]
    for name, (calls, total, max_elapsed) in items[:8]:
        avg_ms = (total / calls * 1000.0) if calls else 0.0
        total_ms = total * 1000.0
        max_ms = max_elapsed * 1000.0
        lines.append(f"[PERF] {name}: calls={calls} avg={avg_ms:.3f}ms max={max_ms:.3f}ms total={total_ms:.1f}ms")
    return lines

def _queue_put_drop_oldest(q, item):
    try:
        q.put_nowait(item)
        return
    except queue.Full:
        pass
    try:
        q.get_nowait()
    except Exception:
        pass
    try:
        q.put_nowait(item)
    except Exception:
        pass

def prune_old_logs(max_files=200):
    try:
        txt_files = []
        for name in os.listdir(LOGS_DIR):
            if not name.lower().endswith(".txt"):
                continue
            path = os.path.join(LOGS_DIR, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            txt_files.append((mtime, path))
        overflow = len(txt_files) - max_files + 1
        if overflow <= 0:
            return
        txt_files.sort(key=lambda x: x[0])
        for _, path in txt_files[:overflow]:
            try:
                os.remove(path)
            except OSError:
                pass
    except Exception:
        pass

def start_session_log():
    global session_log_file
    stop_session_log()
    prune_old_logs(max_files=200)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(LOGS_DIR, f"log{timestamp}.txt")
    with session_log_lock:
        session_log_file = open(path, "a", encoding="utf-8", buffering=1)
    return path

def stop_session_log():
    global session_log_file, CRAFT_COST_SUMMARY_PENDING, PERF_SUMMARY_PENDING
    with session_log_lock:
        if session_log_file:
            try:
                if CRAFT_COST_SUMMARY_PENDING:
                    for line in get_currency_cost_summary_lines():
                        try:
                            sys.__stdout__.write(line + "\n")
                            sys.__stdout__.flush()
                        except Exception:
                            pass
                        session_log_file.write(line + "\n")
                        _queue_put_drop_oldest(log_queue, line)
                    CRAFT_COST_SUMMARY_PENDING = False
                if PERF_SUMMARY_PENDING:
                    for line in _perf_summary_lines():
                        try:
                            sys.__stdout__.write(line + "\n")
                        except Exception:
                            pass
                        session_log_file.write(line + "\n")
                        _queue_put_drop_oldest(log_queue, line)
                    PERF_SUMMARY_PENDING = False
                session_log_file.flush()
                session_log_file.close()
            except Exception:
                pass
            session_log_file = None

def log_message(msg: str):
    _notification_observe_log(msg)
    try:
        sys.__stdout__.write(msg + "\n")
    except Exception:
        pass
    try:
        with session_log_lock:
            if session_log_file:
                session_log_file.write(msg + "\n")
    except Exception:
        pass
    _queue_put_drop_oldest(log_queue, msg)

def gui_info(msg, title="Bilgi"): gui_queue.put(("info", title, msg))
def gui_error(msg, title="Hata"): gui_queue.put(("error", title, msg))
def gui_warn(msg, title="Uyarı"): gui_queue.put(("warning", title, msg))

# ================ CLICK ENGINE (SetCursorPos style — no drift, no animation) ================
def gui_info(msg, title="Bilgi"): _queue_put_drop_oldest(gui_queue, ("info", title, msg))
def gui_error(msg, title="Hata"): _queue_put_drop_oldest(gui_queue, ("error", title, msg))
def gui_warn(msg, title="UyarÄ±"): _queue_put_drop_oldest(gui_queue, ("warning", title, msg))

# ================ GITHUB RELEASE UPDATES ================
UPDATE_CHECK_LOCK = threading.Lock()
UPDATE_CHECK_RUNNING = False
STARTUP_UPDATE_WINDOW = None

def _version_parts(value):
    raw = str(value or "").strip().lower()
    if raw.startswith("v"):
        raw = raw[1:]
    parts = []
    for token in raw.split("."):
        match = re.match(r"(\d+)", token)
        parts.append(int(match.group(1)) if match else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)

def _release_asset(release, name):
    for asset in release.get("assets") or []:
        if str(asset.get("name", "")).casefold() == name.casefold():
            return asset
    return None

def _download_update_file(url, destination, max_bytes):
    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": f"Waukeen-Crafting-Assistant/{APP_VERSION}",
    }
    total = 0
    with requests.get(url, headers=headers, stream=True, timeout=(5, 30)) as response:
        response.raise_for_status()
        declared = int(response.headers.get("Content-Length") or 0)
        if declared > max_bytes:
            raise RuntimeError("Guncelleme dosyasi izin verilen boyutu asiyor.")
        with open(destination, "wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError("Guncelleme dosyasi izin verilen boyutu asiyor.")
                output.write(chunk)
    if total <= 0:
        raise RuntimeError("Guncelleme dosyasi bos geldi.")

def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()

def _read_expected_checksum(path):
    with open(path, "r", encoding="utf-8-sig") as source:
        text = source.read(4096)
    match = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if not match:
        raise RuntimeError("Release SHA-256 dosyasi gecersiz.")
    return match.group(1).lower()

def _craft_is_running():
    thread = globals().get("craft_thread")
    return bool(thread and thread.is_alive())

def _start_downloaded_update(package_path, expected_sha, version):
    if _craft_is_running():
        log_message(f"[UPDATE] v{version} hazir fakat craft aktif; sonraki acilista uygulanacak.")
        gui_warn("Guncelleme indirildi ancak craft aktif. Programi kapatip yeniden actiginizda tekrar kontrol edilecek.", "Update")
        return
    if not os.path.isfile(UPDATER_EXE):
        gui_error("WCA Updater pakette bulunamadi. Uygulamayi tam klasor olarak yeniden indirin.", "Update")
        return
    try:
        updater_copy = os.path.join(
            tempfile.gettempdir(),
            f"WCA-Updater-{os.getpid()}-{int(time.time())}.exe",
        )
        shutil.copy2(UPDATER_EXE, updater_copy)
        install_dir = os.path.dirname(os.path.abspath(sys.executable))
        subprocess.Popen(
            [
                updater_copy,
                "--package", package_path,
                "--target", install_dir,
                "--pid", str(os.getpid()),
                "--expected-sha256", expected_sha,
                "--restart",
            ],
            cwd=tempfile.gettempdir(),
            close_fds=True,
        )
        log_message(f"[UPDATE] v{version} dogrulandi; guvenli updater baslatildi.")
        root.after(150, on_main_close)
    except Exception as exc:
        log_message(f"[UPDATE] Updater baslatilamadi: {exc}")
        gui_error(f"Guncelleme baslatilamadi:\n{exc}", "Update")

def _complete_startup_update_check(success, error_message=""):
    global STARTUP_UPDATE_WINDOW
    window = STARTUP_UPDATE_WINDOW
    STARTUP_UPDATE_WINDOW = None
    if window is not None:
        try:
            window.grab_release()
            window.destroy()
        except Exception:
            pass
    if success:
        return
    message = (
        "Zorunlu guncelleme kontrolu tamamlanamadi.\n\n"
        f"{error_message}\n\n"
        "Internet baglantisini kontrol edip programi yeniden acin."
    )
    try:
        messagebox.showerror("WCA Update", message, parent=root)
    finally:
        root.after(0, on_main_close)

def _update_check_worker(manual, startup=False):
    global UPDATE_CHECK_RUNNING
    try:
        if not getattr(sys, "frozen", False):
            message = "Update kontrolu yalnizca paketlenmis WCA uygulamasinda calisir."
            log_message(f"[UPDATE] {message}")
            if manual:
                gui_info(message, "Check for Updates")
            if startup:
                root.after(0, lambda: _complete_startup_update_check(True))
            return
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Waukeen-Crafting-Assistant/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = requests.get(UPDATE_RELEASE_API, headers=headers, timeout=(5, 15))
        if response.status_code == 404:
            raise RuntimeError("GitHub release kanali henuz yayinda degil.")
        response.raise_for_status()
        release = response.json()
        remote_version = str(release.get("tag_name") or release.get("name") or "").lstrip("vV")
        if not remote_version:
            raise RuntimeError("Release surumu okunamadi.")
        if _version_parts(remote_version) <= _version_parts(APP_VERSION):
            log_message(f"[UPDATE] Guncel surum kullaniliyor: v{APP_VERSION}.")
            if manual:
                gui_info(f"WCA guncel.\nKurulu surum: v{APP_VERSION}", "Check for Updates")
            if startup:
                root.after(0, lambda: _complete_startup_update_check(True))
            return

        package_asset = _release_asset(release, UPDATE_PACKAGE_NAME)
        checksum_asset = _release_asset(release, UPDATE_CHECKSUM_NAME)
        if not package_asset or not checksum_asset:
            raise RuntimeError("Release paketi veya SHA-256 dosyasi eksik.")

        update_dir = tempfile.mkdtemp(prefix="wca-update-")
        package_path = os.path.join(update_dir, UPDATE_PACKAGE_NAME)
        checksum_path = os.path.join(update_dir, UPDATE_CHECKSUM_NAME)
        log_message(f"[UPDATE] v{remote_version} bulundu; paket indiriliyor.")
        _download_update_file(checksum_asset["browser_download_url"], checksum_path, 64 * 1024)
        _download_update_file(package_asset["browser_download_url"], package_path, 750 * 1024 * 1024)
        expected_sha = _read_expected_checksum(checksum_path)
        actual_sha = _sha256_file(package_path)
        if actual_sha != expected_sha:
            raise RuntimeError("Indirilen release paketinin SHA-256 degeri uyusmuyor.")
        root.after(0, lambda: _start_downloaded_update(package_path, expected_sha, remote_version))
    except Exception as exc:
        log_message(f"[UPDATE] Kontrol basarisiz: {exc}")
        if startup:
            error_message = str(exc)
            root.after(0, lambda message=error_message: _complete_startup_update_check(False, message))
        elif manual:
            gui_error(f"Update kontrolu basarisiz:\n{exc}", "Check for Updates")
    finally:
        with UPDATE_CHECK_LOCK:
            UPDATE_CHECK_RUNNING = False

def check_for_updates(manual=False, startup=False):
    global UPDATE_CHECK_RUNNING
    with UPDATE_CHECK_LOCK:
        if UPDATE_CHECK_RUNNING:
            if manual:
                gui_info("Update kontrolu zaten devam ediyor.", "Check for Updates")
            return
        UPDATE_CHECK_RUNNING = True
    threading.Thread(
        target=_update_check_worker,
        args=(bool(manual), bool(startup)),
        daemon=True,
    ).start()

def begin_required_update_check():
    global STARTUP_UPDATE_WINDOW
    settings_cfg.set("General", "auto_update", "True")
    save_settings_now()
    window = tk.Toplevel(root)
    STARTUP_UPDATE_WINDOW = window
    window.title("WCA Update")
    window.configure(bg="#202020")
    window.resizable(False, False)
    window.transient(root)
    window.protocol("WM_DELETE_WINDOW", lambda: None)
    try:
        window.iconbitmap(default=APP_ICON_ICO)
    except Exception:
        pass
    ttk.Label(
        window,
        text="Guncellemeler kontrol ediliyor...",
        font=("Tahoma", 10, "bold"),
    ).pack(padx=30, pady=(22, 8))
    ttk.Label(
        window,
        text="Kontrol tamamlanana kadar lutfen bekleyin.",
    ).pack(padx=30, pady=(0, 22))
    window.update_idletasks()
    x = root.winfo_rootx() + max(0, (root.winfo_width() - window.winfo_width()) // 2)
    y = root.winfo_rooty() + max(0, (root.winfo_height() - window.winfo_height()) // 2)
    window.geometry(f"+{x}+{y}")
    window.grab_set()
    check_for_updates(startup=True)

def safe_wait(s: float):
    if s <= 0:
        return
    time.sleep(s)


def _poe_window_if_foreground():
    import win32gui

    game_window = win32gui.FindWindow(None, "Path of Exile")
    if not game_window or win32gui.GetForegroundWindow() != game_window:
        return None
    return game_window


def _poe_resource_counts_if_foreground(resources):
    """Capture only the small resource-globe regions while PoE is foreground."""
    from PIL import ImageGrab
    import win32gui

    game_window = _poe_window_if_foreground()
    if not game_window:
        return None
    left, top = win32gui.ClientToScreen(game_window, (0, 0))
    right, bottom = win32gui.ClientToScreen(
        game_window,
        win32gui.GetClientRect(game_window)[2:4],
    )
    if right <= left or bottom <= top:
        return None
    client_size = (right - left, bottom - top)
    counts = {}
    for resource in resources:
        roi_left, roi_top, roi_right, roi_bottom = auto_flask.resource_roi_box(
            client_size, resource
        )
        crop = ImageGrab.grab(
            bbox=(
                left + roi_left,
                top + roi_top,
                left + roi_right,
                top + roi_bottom,
            ),
            all_screens=True,
        )
        counts[resource] = auto_flask.resource_color_count_crop(crop, resource)
    return counts


def _set_auto_flask_status(value):
    try:
        auto_flask_status_var.set(str(value))
    except Exception:
        pass


def run_auto_flask(settings):
    enabled = {
        "life": bool(settings.get("auto_flask_life_enabled")),
        "mana": bool(settings.get("auto_flask_mana_enabled")),
    }
    thresholds = {
        "life": float(settings.get("auto_flask_life_threshold", 98)),
        "mana": float(settings.get("auto_flask_mana_threshold", 25)),
    }
    keys = {
        "life": str(settings.get("auto_flask_life_key", "1")),
        "mana": str(settings.get("auto_flask_mana_key", "2")),
    }
    meters = {
        resource: auto_flask.RelativeGlobeMeter()
        for resource in enabled
        if enabled[resource]
    }
    triggers = {
        "life": auto_flask.ThresholdTrigger(thresholds["life"], 0.80),
        "mana": auto_flask.ThresholdTrigger(thresholds["mana"], 1.00),
    }
    names = {"life": "Life", "mana": "Mana"}
    calibration_started = None
    calibrated_logged = False
    last_status_update = 0.0
    paused_logged = False

    log_message(
        "[AUTO FLASK] Kalibrasyon basladi. Baslangictaki kullanilabilir dolu "
        "Life/Mana alani %100 kabul edilir; reserve alanlari hesaba katilmaz."
    )
    try:
        while not stop_event.is_set():
            counts = _poe_resource_counts_if_foreground(meters)
            if counts is None:
                if not paused_logged:
                    log_message("[AUTO FLASK] PoE onde degil; izleme ve tuslar duraklatildi.")
                    paused_logged = True
                root.after(0, lambda: _set_auto_flask_status("Duraklatildi: Path of Exile onde degil."))
                stop_event.wait(0.20)
                continue
            if paused_logged:
                log_message("[AUTO FLASK] PoE yeniden onde; izleme devam ediyor.")
                paused_logged = False

            now = time.monotonic()
            if calibration_started is None:
                calibration_started = now
            percentages = {}
            for resource, meter in meters.items():
                percentages[resource] = meter.feed(counts[resource])

            if not all(meter.calibrated for meter in meters.values()):
                if now - calibration_started > 8.0:
                    missing = ", ".join(
                        names[resource]
                        for resource, meter in meters.items()
                        if not meter.calibrated
                    )
                    log_message(
                        f"[AUTO FLASK] {missing} globu kalibre edilemedi. "
                        "HUD gorunur ve kaynak doluyken tekrar baslat."
                    )
                    stop_event.set()
                    break
                root.after(0, lambda: _set_auto_flask_status("Kalibrasyon yapiliyor... Life/Mana dolu olmali."))
                stop_event.wait(0.06)
                continue

            if not calibrated_logged:
                details = ", ".join(
                    f"{names[resource]} baseline={int(meter.baseline)}"
                    for resource, meter in meters.items()
                )
                log_message(f"[AUTO FLASK] Kalibrasyon tamamlandi: {details}.")
                calibrated_logged = True

            for resource, percent in percentages.items():
                if stop_event.is_set():
                    break
                if triggers[resource].feed(percent, now=now):
                    # Re-check foreground immediately before emitting any key.
                    if not _poe_window_if_foreground() or stop_event.is_set():
                        break
                    keyboard.press_and_release(keys[resource])
                    log_message(
                        f"[AUTO FLASK] {names[resource]} {percent:.1f}% <= "
                        f"{thresholds[resource]:.0f}% -> flask {keys[resource]}."
                    )

            if now - last_status_update >= 0.25:
                status = " | ".join(
                    f"{names[resource]}: {percentages[resource]:.0f}%"
                    for resource in meters
                    if percentages.get(resource) is not None
                )
                root.after(0, lambda value=status: _set_auto_flask_status(value))
                last_status_update = now
            stop_event.wait(0.06)
    except Exception as exc:
        log_message(f"[AUTO FLASK] Beklenmeyen hata: {exc}\n{traceback.format_exc()}")
        stop_event.set()
    finally:
        root.after(0, lambda: _set_auto_flask_status("Durduruldu. F4 ile yeniden baslat."))
        log_message("[AUTO FLASK] Izleme durduruldu.")
        log_message("[CRAFT] Dongu durduruldu.")
        stop_session_log()

def _craft_stop_requested():
    event = globals().get("stop_event")
    return bool(event and event.is_set())

def _instant_move(x: int, y: int):
    """Fareyi animasyonsuz direkt koordinata taşır — orb kaçırma riski yok."""
    pyautogui.moveTo(x, y, duration=0)

def orb_right_click(x: int, y: int):
    """Adamın RClick: SetCursorPos → Sleep(25) → down → up → Sleep(25)"""
    if _craft_stop_requested():
        return False
    pyautogui.moveTo(x, y, duration=0)
    time.sleep(0.025)
    if _craft_stop_requested():
        return False
    pyautogui.mouseDown(button="right")
    pyautogui.mouseUp(button="right")
    time.sleep(0.025)
    return not _craft_stop_requested()

def item_left_click(x: int, y: int):
    """Adamın LClick: SetCursorPos → Sleep(25) → down → up → Sleep(25)"""
    if _craft_stop_requested():
        return False
    pyautogui.moveTo(x, y, duration=0)
    time.sleep(0.025)
    if _craft_stop_requested():
        return False
    pyautogui.mouseDown(button="left")
    pyautogui.mouseUp(button="left")
    time.sleep(0.025)
    return not _craft_stop_requested()

def ctrl_left_click_item(x: int, y: int):
    """Move an item to the open stash while guaranteeing Ctrl is released."""
    if _craft_stop_requested():
        return False
    try:
        keyboard.press("ctrl")
        time.sleep(0.015)
        if _craft_stop_requested():
            return False
        return item_left_click(x, y)
    finally:
        try:
            keyboard.release("ctrl")
        except Exception:
            pass

def _mean_rgb_on_box(img, box):
    x0, y0, x1, y1 = [int(v) for v in box]
    if hasattr(img, "shape"):
        height = int(img.shape[0])
        width = int(img.shape[1])
        x0 = max(0, min(width, x0))
        y0 = max(0, min(height, y0))
        x1 = max(x0, min(width, x1))
        y1 = max(y0, min(height, y1))
        if x1 <= x0 or y1 <= y0:
            return ()
        region = img[y0:y1, x0:x1]
        if getattr(region, "size", 0) <= 0 or len(region.shape) != 3 or region.shape[2] < 3:
            return ()
        mean_channels = region[..., :3].mean(axis=(0, 1))
        b, g, r = (float(mean_channels[0]), float(mean_channels[1]), float(mean_channels[2]))
        return (round(r, 4), round(g, 4), round(b, 4))

    x0 = max(0, min(img.size[0], x0))
    y0 = max(0, min(img.size[1], y0))
    x1 = max(x0, min(img.size[0], x1))
    y1 = max(y0, min(img.size[1], y1))
    if x1 <= x0 or y1 <= y0:
        return ()
    pix = img.load()
    total_r = total_g = total_b = 0.0
    count = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pix[x, y]
            total_r += float(r)
            total_g += float(g)
            total_b += float(b)
            count += 1
    if count <= 0:
        return ()
    return (
        round(total_r / count, 4),
        round(total_g / count, 4),
        round(total_b / count, 4),
    )

def _rgb_distance(avg_a, avg_b):
    if not avg_a or not avg_b:
        return None
    return (
        ((float(avg_a[0]) - float(avg_b[0])) ** 2)
        + ((float(avg_a[1]) - float(avg_b[1])) ** 2)
        + ((float(avg_a[2]) - float(avg_b[2])) ** 2)
    ) ** 0.5

def _avg_rgb_list(values):
    valid = [tuple(v) for v in values if v and len(v) == 3]
    if not valid:
        return ()
    count = float(len(valid))
    return (
        round(sum(float(v[0]) for v in valid) / count, 4),
        round(sum(float(v[1]) for v in valid) / count, 4),
        round(sum(float(v[2]) for v in valid) / count, 4),
    )

def reset_fast_cursor_model():
    global FAST_CURSOR_MODEL
    FAST_CURSOR_MODEL = {
        "ready": False,
        "width": int(FAST_CURSOR_PATCH_SIZE[0]),
        "height": int(FAST_CURSOR_PATCH_SIZE[1]),
        "patch_box": (0, 0, int(FAST_CURSOR_PATCH_SIZE[0]), int(FAST_CURSOR_PATCH_SIZE[1])),
        "default_avg": (),
        "active_avg": (),
    }

def _set_fast_cursor_model(default_avg, active_avg):
    global FAST_CURSOR_MODEL
    FAST_CURSOR_MODEL = {
        "ready": bool(default_avg and active_avg),
        "width": int(FAST_CURSOR_PATCH_SIZE[0]),
        "height": int(FAST_CURSOR_PATCH_SIZE[1]),
        "patch_box": (0, 0, int(FAST_CURSOR_PATCH_SIZE[0]), int(FAST_CURSOR_PATCH_SIZE[1])),
        "default_avg": tuple(float(v) for v in default_avg),
        "active_avg": tuple(float(v) for v in active_avg),
    }
    return FAST_CURSOR_MODEL.get("ready", False)

def _get_cursor_pos():
    import ctypes
    class _Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = _Point()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        raise RuntimeError("GetCursorPos basarisiz")
    return (int(pt.x), int(pt.y))

def _get_dxcam_monitor_camera():
    if dxcam is None:
        raise RuntimeError("dxcam kullanilamiyor")
    tid = threading.get_ident()
    with FAST_CURSOR_CAPTURE_LOCK:
        cam = FAST_CURSOR_CAPTURE_STATE["dxcam_cameras"].get(tid)
        if cam is None:
            try:
                cam = dxcam.create(backend="winrt", output_color="BGRA")
                backend = "winrt"
            except Exception as winrt_error:
                try:
                    cam = dxcam.create(backend="dxgi", output_color="BGRA")
                    backend = "dxgi"
                except Exception as dxgi_error:
                    raise RuntimeError(
                        f"WinRT ve DXGI capture baslatilamadi: "
                        f"WinRT={winrt_error}; DXGI={dxgi_error}"
                    ) from dxgi_error
                if not FAST_CURSOR_CAPTURE_STATE["fallback_logged"]:
                    FAST_CURSOR_CAPTURE_STATE["fallback_logged"] = True
                    log_message(
                        "[FAST-CURSOR] WinRT kullanilamadi; DXGI yedek backend aktif."
                    )
            FAST_CURSOR_CAPTURE_STATE["dxcam_cameras"][tid] = cam
            FAST_CURSOR_CAPTURE_STATE["dxcam_backends"][tid] = backend
        return cam

def _release_dxcam_monitor_camera(thread_id=None, release_all=False):
    with FAST_CURSOR_CAPTURE_LOCK:
        if release_all:
            items = list(FAST_CURSOR_CAPTURE_STATE["dxcam_cameras"].items())
            FAST_CURSOR_CAPTURE_STATE["dxcam_cameras"] = {}
            FAST_CURSOR_CAPTURE_STATE["dxcam_backends"] = {}
        else:
            tid = threading.get_ident() if thread_id is None else int(thread_id)
            cam = FAST_CURSOR_CAPTURE_STATE["dxcam_cameras"].pop(tid, None)
            FAST_CURSOR_CAPTURE_STATE["dxcam_backends"].pop(tid, None)
            items = [] if cam is None else [(tid, cam)]
    for _, cam in items:
        try:
            if hasattr(cam, "stop"):
                cam.stop()
        except Exception:
            pass
        try:
            if hasattr(cam, "release"):
                cam.release()
        except Exception:
            pass

def _capture_cursor_runtime_crop():
    pos = _get_cursor_pos()
    patch_x0, patch_y0, patch_x1, patch_y1 = [int(v) for v in FAST_CURSOR_PATCH_BOX]
    width = int(FAST_CURSOR_MODEL.get("width") or FAST_CURSOR_PATCH_SIZE[0])
    height = int(FAST_CURSOR_MODEL.get("height") or FAST_CURSOR_PATCH_SIZE[1])
    bbox = (
        int(pos[0]) + patch_x0,
        int(pos[1]) + patch_y0,
        int(pos[0]) + patch_x1,
        int(pos[1]) + patch_y1,
    )
    cam = _get_dxcam_monitor_camera()
    frame = None
    for _ in range(5):
        frame = cam.grab(region=bbox, new_frame_only=False)
        if frame is not None:
            break
        time.sleep(0.004)
    if frame is None:
        raise RuntimeError("dxcam frame donmedi")
    return frame

def _classify_cursor_image(img):
    if img is None or not FAST_CURSOR_MODEL.get("ready"):
        return {"state": "unknown", "d_default": None, "d_active": None, "avg": ()}
    avg = _mean_rgb_on_box(img, FAST_CURSOR_MODEL["patch_box"])
    d_default = _rgb_distance(avg, FAST_CURSOR_MODEL["default_avg"])
    d_active = _rgb_distance(avg, FAST_CURSOR_MODEL["active_avg"])
    if d_default is None or d_active is None:
        state = "unknown"
    elif d_default < d_active:
        state = "default"
    elif d_active < d_default:
        state = "active"
    else:
        state = "unknown"
    return {"state": state, "d_default": d_default, "d_active": d_active, "avg": avg}

def live_calibrate_fast_cursor(item_pos):
    if not item_pos:
        raise RuntimeError("Item konumu yok")
    if dxcam is None:
        raise RuntimeError("dxcam kullanilamiyor")

    def _warmup_capture_reads():
        for _ in range(FAST_CURSOR_LIVE_WARMUP_CAPTURES):
            try:
                _capture_cursor_runtime_crop()
            except Exception:
                pass
            safe_wait(0.01)

    def _sample_state_averages():
        samples = []
        for idx in range(FAST_CURSOR_LIVE_SAMPLE_COUNT):
            img = _capture_cursor_runtime_crop()
            avg = _mean_rgb_on_box(img, FAST_CURSOR_MODEL["patch_box"])
            if not avg:
                raise RuntimeError("Patch ortalamasi alinamadi")
            samples.append(avg)
            if idx < FAST_CURSOR_LIVE_SAMPLE_COUNT - 1:
                safe_wait(FAST_CURSOR_LIVE_SAMPLE_INTERVAL)
        return samples

    _instant_move(item_pos[0], item_pos[1])
    safe_wait(FAST_CURSOR_LIVE_SAMPLE_INTERVAL)
    _warmup_capture_reads()
    default_samples = _sample_state_averages()
    default_avg = _avg_rgb_list(default_samples)
    if not default_avg:
        raise RuntimeError("Default patch ortalamasi alinamadi")

    safe_wait(FAST_CURSOR_LIVE_STATE_SETTLE)
    item_left_click(item_pos[0], item_pos[1])
    safe_wait(FAST_CURSOR_LIVE_STATE_SETTLE)
    _warmup_capture_reads()
    active_samples = _sample_state_averages()
    active_avg = _avg_rgb_list(active_samples)
    if not active_avg:
        raise RuntimeError("Active patch ortalamasi alinamadi")

    item_left_click(item_pos[0], item_pos[1])
    safe_wait(FAST_CURSOR_LIVE_SAMPLE_INTERVAL)
    _instant_move(item_pos[0], item_pos[1])
    safe_wait(0.02)

    if not _set_fast_cursor_model(default_avg, active_avg):
        raise RuntimeError("Cursor patch modeli kurulamadı")

    log_message(
        f"[FAST-CURSOR] Live kalibrasyon: default_avg={FAST_CURSOR_MODEL['default_avg']} "
        f"active_avg={FAST_CURSOR_MODEL['active_avg']} "
        f"default_samples={default_samples} active_samples={active_samples}"
    )
    return True

def _fast_cursor_monitor_loop():
    thread_id = threading.get_ident()
    try:
        while True:
            with FAST_CURSOR_MONITOR_LOCK:
                if not FAST_CURSOR_MONITOR["running"]:
                    break
            try:
                crop = _capture_cursor_runtime_crop()
                sample = _classify_cursor_image(crop)
                with FAST_CURSOR_MONITOR_LOCK:
                    FAST_CURSOR_MONITOR["state"] = sample["state"]
                    FAST_CURSOR_MONITOR["d_default"] = sample["d_default"]
                    FAST_CURSOR_MONITOR["d_active"] = sample["d_active"]
                    FAST_CURSOR_MONITOR["sample_id"] += 1
                    FAST_CURSOR_MONITOR["last_error"] = ""
            except Exception as e:
                with FAST_CURSOR_MONITOR_LOCK:
                    FAST_CURSOR_MONITOR["last_error"] = str(e)
                    if not FAST_CURSOR_MONITOR["warned"]:
                        FAST_CURSOR_MONITOR["warned"] = True
                        try:
                            log_message(f"[FAST-CURSOR] Monitor hatasi: {e}")
                        except Exception:
                            pass
                time.sleep(0.02)
                continue
            time.sleep(FAST_CURSOR_MONITOR_INTERVAL)
    finally:
        _release_dxcam_monitor_camera(thread_id=thread_id)

def start_fast_cursor_monitor(item_pos):
    stop_fast_cursor_monitor()
    if dxcam is None:
        log_message("[FAST-CURSOR] dxcam hazir degil, monitor acilamadi.")
        return False
    try:
        live_calibrate_fast_cursor(item_pos)
    except Exception as e:
        reset_fast_cursor_model()
        log_message(f"[FAST-CURSOR] Live kalibrasyon basarisiz: {e}")
        return False
    with FAST_CURSOR_MONITOR_LOCK:
        FAST_CURSOR_MONITOR["running"] = True
        FAST_CURSOR_MONITOR["state"] = "unknown"
        FAST_CURSOR_MONITOR["d_default"] = None
        FAST_CURSOR_MONITOR["d_active"] = None
        FAST_CURSOR_MONITOR["sample_id"] = 0
        FAST_CURSOR_MONITOR["last_error"] = ""
        FAST_CURSOR_MONITOR["warned"] = False
        FAST_CURSOR_MONITOR["thread"] = threading.Thread(target=_fast_cursor_monitor_loop, daemon=True)
        FAST_CURSOR_MONITOR["thread"].start()
    log_message(
        f"[FAST-CURSOR] Monitor aktif. patch={FAST_CURSOR_PATCH_BOX}, "
        f"default_avg={FAST_CURSOR_MODEL['default_avg']}, active_avg={FAST_CURSOR_MODEL['active_avg']}"
    )
    return True

def stop_fast_cursor_monitor():
    thread = None
    with FAST_CURSOR_MONITOR_LOCK:
        FAST_CURSOR_MONITOR["running"] = False
        thread = FAST_CURSOR_MONITOR.get("thread")
        FAST_CURSOR_MONITOR["thread"] = None
    if thread and thread.is_alive():
        thread.join(timeout=0.3)
    _release_dxcam_monitor_camera(release_all=True)
    reset_fast_cursor_model()

def get_fast_cursor_snapshot():
    with FAST_CURSOR_MONITOR_LOCK:
        return {
            "state": FAST_CURSOR_MONITOR["state"],
            "d_default": FAST_CURSOR_MONITOR["d_default"],
            "d_active": FAST_CURSOR_MONITOR["d_active"],
            "sample_id": FAST_CURSOR_MONITOR["sample_id"],
            "last_error": FAST_CURSOR_MONITOR["last_error"],
        }

def _wait_for_cursor_state(expected_state, timeout=FAST_CURSOR_TRANSITION_TIMEOUT, require_newer_than=None):
    deadline = time.time() + float(timeout)
    last_seen = None
    while time.time() <= deadline:
        snap = get_fast_cursor_snapshot()
        last_seen = snap
        if require_newer_than is not None and int(snap["sample_id"]) <= int(require_newer_than):
            time.sleep(0.003)
            continue
        if snap["state"] == expected_state:
            return snap
        time.sleep(0.003)
    return last_seen or get_fast_cursor_snapshot()

def _wait_for_stable_cursor_state(expected_state, timeout=FAST_CURSOR_TRANSITION_TIMEOUT, consecutive=2, require_newer_than=None):
    deadline = time.time() + float(timeout)
    needed = max(1, int(consecutive))
    streak = 0
    last_sample_id = None
    last_seen = None
    while time.time() <= deadline:
        snap = get_fast_cursor_snapshot()
        last_seen = snap
        sample_id = int(snap.get("sample_id") or 0)
        if require_newer_than is not None and sample_id <= int(require_newer_than):
            time.sleep(0.003)
            continue
        if last_sample_id == sample_id:
            time.sleep(0.003)
            continue
        last_sample_id = sample_id
        if snap["state"] == expected_state:
            streak += 1
            if streak >= needed:
                return snap
        else:
            streak = 0
        time.sleep(0.003)
    return last_seen or get_fast_cursor_snapshot()

def _stop_fast_cursor_craft(reason):
    log_message(reason)
    stop_event.set()

def _log_fast_cursor_state(prefix, snap, note):
    d_default = "?" if snap.get("d_default") is None else f"{float(snap['d_default']):.2f}"
    d_active = "?" if snap.get("d_active") is None else f"{float(snap['d_active']):.2f}"
    log_message(f"[FAST-CURSOR] {prefix}: state={snap.get('state')} d_default={d_default} d_active={d_active} -> {note}")

def _recover_default_after_shift_stream(context_name):
    if not FAST_CURSOR_MODEL.get("ready"):
        return True
    first = _ensure_cursor_default_after_shift_stream(context_name)
    if first is True:
        return True
    snap = first or get_fast_cursor_snapshot()
    for attempt in range(1, FAST_CURSOR_CLEANUP_RETRIES + 1):
        post = _wait_for_stable_cursor_state("default", timeout=FAST_CURSOR_TRANSITION_TIMEOUT, consecutive=2, require_newer_than=snap["sample_id"])
        if post["state"] == "default":
            if FAST_CURSOR_LOG_SUCCESS_DETAILS:
                _log_fast_cursor_state(f"{context_name} stream cleanup post", post, f"retry={attempt}")
            return True
        snap = post or get_fast_cursor_snapshot()
        if attempt < FAST_CURSOR_CLEANUP_RETRIES:
            if attempt <= FAST_CURSOR_SHIFT_RELEASE_RETRIES:
                try:
                    keyboard.release("shift")
                    log_message(f"[FAST-CURSOR] {context_name} cleanup icin shift release tekrarlandi ({attempt}).")
                except Exception:
                    pass
            log_message(f"[FAST-CURSOR] {context_name} stream cleanup retry {attempt}/{FAST_CURSOR_CLEANUP_RETRIES}")
            safe_wait(FAST_CURSOR_RETRY_WAIT)
    _log_fast_cursor_state(f"{context_name} stream cleanup pre", first if isinstance(first, dict) else get_fast_cursor_snapshot(), "shift cikisi oncesi")
    _log_fast_cursor_state(f"{context_name} stream cleanup post", snap, "shift cikisi sonrasi")
    _stop_fast_cursor_craft(f"[FAST-CURSOR] {context_name} stream cleanup default gorunmedi. Craft durduruldu.")
    return False

def _pick_orb_with_verify(orb_name, orb_pos):
    retries = FAST_CURSOR_PICK_RETRIES if FAST_CURSOR_MODEL.get("ready") else 1
    last_post = None
    for attempt in range(1, retries + 1):
        pick_pre = None
        if FAST_CURSOR_MODEL.get("ready"):
            pick_pre = get_fast_cursor_snapshot()
            if pick_pre["state"] != "default":
                _log_fast_cursor_state(f"{orb_name} pick pre", pick_pre, f"retry={attempt}")
                if attempt < retries:
                    safe_wait(FAST_CURSOR_RETRY_WAIT)
                    continue
                _stop_fast_cursor_craft(f"[FAST-CURSOR] {orb_name} pick pre default degil. Craft durduruldu.")
                return False
        orb_right_click(orb_pos[0], orb_pos[1])
        if stop_event.is_set():
            return False
        result = _verify_pick_transition(orb_name, pick_pre["sample_id"] if pick_pre else None)
        if result is True:
            return True
        last_post = result
        if attempt < retries:
            _log_fast_cursor_state(f"{orb_name} pick post", result, f"retry={attempt}")
            safe_wait(FAST_CURSOR_RETRY_WAIT)
            continue
    if last_post:
        _log_fast_cursor_state(f"{orb_name} pick post", last_post, "orb sonrasi")
    _stop_fast_cursor_craft(f"[FAST-CURSOR] {orb_name} pick post active gorunmedi. Craft durduruldu.")
    return False

def _apply_orb_to_item_with_verify(orb_name, item_pos):
    retries = FAST_CURSOR_APPLY_RETRIES if FAST_CURSOR_MODEL.get("ready") else 1
    last_post = None
    for attempt in range(1, retries + 1):
        apply_pre = None
        if FAST_CURSOR_MODEL.get("ready"):
            apply_pre = get_fast_cursor_snapshot()
            if apply_pre["state"] != "active":
                _log_fast_cursor_state(f"{orb_name} apply pre", apply_pre, f"retry={attempt}")
                if attempt < retries:
                    safe_wait(FAST_CURSOR_RETRY_WAIT)
                    continue
                _stop_fast_cursor_craft(f"[FAST-CURSOR] {orb_name} apply pre active degil. Craft durduruldu.")
                return False
        item_left_click(item_pos[0], item_pos[1])
        if stop_event.is_set():
            return False
        result = _verify_apply_transition(orb_name, apply_pre["sample_id"] if apply_pre else None)
        if result is True:
            return True
        last_post = result
        if attempt < retries:
            _log_fast_cursor_state(f"{orb_name} apply post", result, f"retry={attempt}")
            safe_wait(FAST_CURSOR_RETRY_WAIT)
            continue
    if last_post:
        _log_fast_cursor_state(f"{orb_name} apply post", last_post, "item sonrasi")
    _stop_fast_cursor_craft(f"[FAST-CURSOR] {orb_name} apply post default gorunmedi. Craft durduruldu.")
    return False

def _stream_click_item_with_verify(orb_name, item_pos):
    retries = FAST_CURSOR_APPLY_RETRIES if FAST_CURSOR_MODEL.get("ready") else 1
    last_post = None
    for attempt in range(1, retries + 1):
        stream_pre = None
        if FAST_CURSOR_MODEL.get("ready"):
            stream_pre = get_fast_cursor_snapshot()
            if stream_pre["state"] != "active":
                _log_fast_cursor_state(f"{orb_name} stream pre", stream_pre, f"retry={attempt}")
                if attempt < retries:
                    safe_wait(FAST_CURSOR_RETRY_WAIT)
                    continue
                _stop_fast_cursor_craft(f"[FAST-CURSOR] {orb_name} stream pre active degil. Craft durduruldu.")
                return False
        item_left_click(item_pos[0], item_pos[1])
        if stop_event.is_set():
            return False
        result = _verify_stream_click_state(orb_name, stream_pre["sample_id"] if stream_pre else None)
        if result is True:
            return True
        last_post = result
        if attempt < retries:
            _log_fast_cursor_state(f"{orb_name} stream post", result, f"retry={attempt}")
            safe_wait(FAST_CURSOR_RETRY_WAIT)
            continue
    if last_post:
        _log_fast_cursor_state(f"{orb_name} stream post", last_post, "shift stream sonrasi")
    _stop_fast_cursor_craft(f"[FAST-CURSOR] {orb_name} stream post active degil. Craft durduruldu.")
    return False

def _verify_pick_transition(orb_name, before_id):
    if not FAST_CURSOR_MODEL.get("ready"):
        return True
    post = _wait_for_stable_cursor_state(
        "active",
        timeout=FAST_CURSOR_TRANSITION_TIMEOUT,
        consecutive=FAST_CURSOR_TRANSITION_CONFIRM_SAMPLES,
        require_newer_than=before_id,
    )
    if post["state"] != "active":
        return post
    return True

def _verify_apply_transition(orb_name, before_id):
    if not FAST_CURSOR_MODEL.get("ready"):
        return True
    post = _wait_for_stable_cursor_state(
        "default",
        timeout=FAST_CURSOR_TRANSITION_TIMEOUT,
        consecutive=FAST_CURSOR_TRANSITION_CONFIRM_SAMPLES,
        require_newer_than=before_id,
    )
    if post["state"] != "default":
        return post
    if FAST_CURSOR_LOG_SUCCESS_DETAILS:
        _log_fast_cursor_state(f"{orb_name} apply post", post, "item sonrasi")
    return True

def _verify_stream_click_state(orb_name, before_id):
    if not FAST_CURSOR_MODEL.get("ready"):
        return True
    post = _wait_for_stable_cursor_state(
        "active",
        timeout=FAST_CURSOR_TRANSITION_TIMEOUT,
        consecutive=FAST_CURSOR_TRANSITION_CONFIRM_SAMPLES,
        require_newer_than=before_id,
    )
    if post["state"] != "active":
        return post
    return True

def _ensure_cursor_default_after_shift_stream(context_name):
    if not FAST_CURSOR_MODEL.get("ready"):
        return True
    snap = get_fast_cursor_snapshot()
    if snap["state"] == "default":
        return True
    return snap

# ================ CLIPBOARD (FAST) ================
WIN32_AVAILABLE = False
try:
    import win32clipboard
    WIN32_AVAILABLE = True
except Exception:
    pass

def clipboard_clear_until_empty():
    """Adamın ClipboardClear: repeat Open,Clear,Read,Close until cb=''"""
    for _ in range(2):
        try:
            if WIN32_AVAILABLE:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                try:
                    cb = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or ""
                except Exception:
                    cb = ""
                win32clipboard.CloseClipboard()
            else:
                pyperclip.copy("")
                cb = pyperclip.paste() or ""
            if not cb.strip():
                return
        except Exception:
            try:
                if WIN32_AVAILABLE:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass
            return
        time.sleep(0.001)

def fast_clipboard_read():
    """Adamın ClipboardGetItemData: repeat i++,Open,Read,Close until cb<>'' or i>10 (11 deneme)"""
    for i in range(1, 12):  # i=1..11, until i>10
        try:
            if WIN32_AVAILABLE:
                win32clipboard.OpenClipboard()
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                if data and data.strip():
                    return data.strip()
            else:
                data = pyperclip.paste()
                if data and data.strip():
                    return data.strip()
        except Exception:
            try:
                if WIN32_AVAILABLE:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass
    return ""

def _clipboard_wait_for_text(max_wait=0.05, poll_interval=0.005):
    deadline = time.perf_counter() + float(max_wait)
    last = ""
    while time.perf_counter() < deadline:
        last = fast_clipboard_read()
        if last:
            return last
        time.sleep(poll_interval)
    return fast_clipboard_read() or last

def capture_item_text_once():
    """
    ITEM_POS üzerindeki item text'ini tek seferlik RAW olarak okur.
    Alter/Augment failover'ı bu fonksiyonu kullanıyor.
    """
    started = time.perf_counter()
    try:
        if ITEM_POS:
            _instant_move(ITEM_POS[0], ITEM_POS[1])
            safe_wait(0.025)
            clipboard_clear_until_empty()
            try:
                keyboard.press_and_release("ctrl+c")
            except Exception:
                pyautogui.hotkey("ctrl", "c")
            txt = _clipboard_wait_for_text(max_wait=0.05, poll_interval=0.005)
        else:
            txt = fast_clipboard_read()
        return (txt or "").strip()
    except Exception:
        return ""
    finally:
        _perf_record("capture_item_text_once_fast", time.perf_counter() - started)

# ================ ORB LOCATION HELPERS ================
def get_orb_locations_dict():
    if not settings_cfg.has_section("OrbLocations"):
        return {}
    return dict(settings_cfg.items("OrbLocations"))

def get_orb_location(name: str):
    val = get_orb_locations_dict().get(name.lower())
    if not val:
        return None
    try:
        x, y = map(int, val.split(","))
        return (x, y)
    except Exception:
        return None

# ================ ITEM HOVER / SLOT CHECK ================
def is_slot_empty(pos, dark_threshold=60):
    if not pos:
        return True
    try:
        r, g, b = pyautogui.pixel(int(pos[0]), int(pos[1]))
        brightness = (r + g + b) / 3
        return brightness < dark_threshold
    except Exception:
        return True

def release_cursor_item_if_any():
    try:
        screen_w, screen_h = pyautogui.size()
        safe_x = max(50, min(screen_w - 50, screen_w // 2))
        safe_y = max(50, min(screen_h - 50, screen_h // 2))
        _instant_move(safe_x, safe_y)
        safe_wait(0.04)
        pyautogui.mouseUp(button="left")
        pyautogui.mouseUp(button="right")
        safe_wait(0.02)
    except Exception:
        pass

def reset_hover_before_slot():
    try:
        screen_w, screen_h = pyautogui.size()
        _instant_move(screen_w // 2, screen_h // 2)
        safe_wait(0.06)
    except Exception:
        pass

def _send_ctrl_c_lowlevel():
    try:
        import ctypes
        VK_CONTROL = 0x11
        ORD_C = 0x43
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(ORD_C, 0, 0, 0)
        ctypes.windll.user32.keybd_event(ORD_C, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        try:
            keyboard.press_and_release("ctrl+c")
        except Exception:
            pyautogui.hotkey("ctrl", "c")

def capture_text_at_pos(pos, pre_wait=0.035, post_copy_wait=0.045, tries=2):
    try:
        if not pos:
            return ""
        _instant_move(pos[0], pos[1])
        safe_wait(pre_wait)
        clipboard_clear_until_empty()

        result = ""
        for _ in range(tries):
            _send_ctrl_c_lowlevel()
            safe_wait(post_copy_wait)
            result = fast_clipboard_read()
            if result and result.strip():
                break

        clipboard_clear_until_empty()
        return (result or "").strip()
    except Exception:
        return ""

def _voyage_parse_point(raw_value):
    try:
        x, y = str(raw_value or "").split(",", 1)
        return int(x.strip()), int(y.strip())
    except (TypeError, ValueError):
        return None

def _voyage_point_setting(key):
    return _voyage_parse_point(
        settings_cfg.get("Voyage", key, fallback="")
    )

def _voyage_save_point(key, point):
    settings_cfg.set("Voyage", key, f"{int(point[0])},{int(point[1])}")
    client_rect = _voyage_poe_client_rect()
    if client_rect:
        left, top, right, bottom = client_rect
        settings_cfg.set("Voyage", "calibration_client_rect", f"{left},{top},{right},{bottom}")
    save_settings_now()


def _voyage_scaled_manual_points(points, client_rect):
    if not all(points.values()) or not client_rect:
        return points
    raw_rect = settings_cfg.get(
        "Voyage",
        "calibration_client_rect",
        fallback="",
    )
    try:
        old_left, old_top, old_right, old_bottom = (
            int(value.strip()) for value in raw_rect.split(",")
        )
    except (TypeError, ValueError):
        return points
    return voyage.scale_calibration_points(
        points,
        (old_left, old_top, old_right, old_bottom),
        client_rect,
    )

def _voyage_grid_points(top_left, bottom_right, columns, rows):
    x0, y0 = top_left
    x1, y1 = bottom_right
    result = []
    for row in range(rows):
        y = round(y0 + (y1 - y0) * row / max(1, rows - 1))
        for column in range(columns):
            x = round(x0 + (x1 - x0) * column / max(1, columns - 1))
            result.append((x, y))
    return result

def _voyage_board_points(top_left, bottom_right):
    return _voyage_grid_points(top_left, bottom_right, 3, 3)

def _voyage_border_probes(top_left, bottom_right):
    x0, y0 = top_left
    x2, y2 = bottom_right
    dx = (x2 - x0) / 2.0
    dy = (y2 - y0) / 2.0
    # Border modifier hover targets are on the decorative frame, not aligned
    # with the visual centers used to place Charts.
    xs = [
        round(x0 - dx * 0.39),
        round(x0 + dx),
        round(x2 + dx * 0.41),
    ]
    ys = [
        round(y0 + dy * 0.03),
        round(y0 + dy * 1.14),
        round(y2 + dy * 0.24),
    ]
    side_offset = round(abs(dx) * 0.75)
    top_offset = round(abs(dy) * 0.74)
    bottom_offset = round(abs(dy) * 0.83)
    probes = []
    for column, x in enumerate(xs):
        probes.append(((x, round(y0 - top_offset)), column, "top"))
    for row, y in enumerate(ys):
        probes.append(((round(x2 + side_offset), y), row * 3 + 2, "right"))
    for column, x in enumerate(xs):
        probes.append(((x, round(y2 + bottom_offset)), 6 + column, "bottom"))
    for row, y in enumerate(ys):
        probes.append(((round(x0 - side_offset), y), row * 3, "left"))
    return probes

def _voyage_wait(seconds):
    return not stop_event.wait(max(0.0, float(seconds)))

def _voyage_ocr_image(image):
    """Use the built-in Windows OCR engine without an external OCR process."""
    import asyncio
    import io
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    async def recognize():
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="BMP")
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(buffer.getvalue())
        await writer.store_async()
        writer.detach_stream()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            return ""
        result = await engine.recognize_async(bitmap)
        return (result.text or "").strip()

    return asyncio.run(recognize())

def _voyage_blue_text_mask(image):
    from PIL import Image as PilImage

    source = image.convert("RGB")
    result = PilImage.new("L", source.size, 0)
    source_pixels = source.load()
    result_pixels = result.load()
    for y in range(source.height):
        for x in range(source.width):
            r, g, b = source_pixels[x, y]
            if b > 110 and (b - r) > 30 and (b - g) > 15:
                result_pixels[x, y] = 255
    return result.resize(
        (result.width * 2, result.height * 2),
        PilImage.Resampling.NEAREST,
    )

def _voyage_clean_border_ocr(text):
    cleaned = re.sub(
        r"\b[LIi1][':;.,]?\s*\d{1,3}\b",
        " ",
        text or "",
        flags=re.I,
    )
    cleaned = re.sub(r"\bArea\s+Modifiers\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(\d{1,3})96\b", r"\1%", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|")
    cues = (
        "adjacent",
        "monster",
        "pack",
        "chart",
        "voyage",
        "lantern",
        "strongbox",
        "orb",
        "currency",
        "scarab",
        "altar",
        "sulphur",
        "quantity",
        "rarity",
        "gold",
        "map",
        "sea beast",
        "crab",
        "drowned",
        "filth",
    )
    if not any(cue in cleaned.lower() for cue in cues):
        return ""
    return cleaned

def _voyage_scan_borders(board_tl, board_br):
    from PIL import ImageGrab

    board_points = _voyage_board_points(board_tl, board_br)
    xs = [p[0] for p in board_points]
    ys = [p[1] for p in board_points]
    board_scale = max(0.75, min(2.5, (max(ys) - min(ys)) / 288.0))
    crop_pad_x = round(430 * board_scale)
    crop_pad_y = round(180 * board_scale)
    screen_w, screen_h = pyautogui.size()
    crop = (
        max(0, min(xs) - crop_pad_x),
        max(0, min(ys) - crop_pad_y),
        min(screen_w, max(xs) + crop_pad_x),
        min(screen_h, max(ys) + crop_pad_y),
    )
    cell_mods = [[] for _ in range(9)]
    for index, (point, cell, edge_name) in enumerate(
        _voyage_border_probes(board_tl, board_br), start=1
    ):
        if stop_event.is_set():
            return None
        offsets = (
            ((0, 0), (4, 0), (-4, 0))
            if edge_name in ("top", "bottom")
            else ((0, 0), (0, 4), (0, -4))
        )
        normalized = ""
        for attempt, (offset_x, offset_y) in enumerate(offsets, start=1):
            _instant_move(point[0] + offset_x, point[1] + offset_y)
            # Border tooltips animate in; side tooltips can take longer to settle.
            if not _voyage_wait(0.35):
                return None
            screenshot = ImageGrab.grab(bbox=crop, all_screens=True)
            try:
                text = _voyage_ocr_image(_voyage_blue_text_mask(screenshot))
            except Exception as exc:
                log_message(f"[VOYAGE] Kenar OCR hatasi ({edge_name}): {exc}")
                return None
            normalized = _voyage_clean_border_ocr(text)
            if normalized:
                if attempt > 1:
                    log_message(
                        f"[VOYAGE] Kenar {index}/12 OCR retry {attempt} ile okundu."
                    )
                break
        if not normalized:
            log_message(
                f"[VOYAGE] Kenar {index}/12 uc denemede okunamadi "
                f"({edge_name}, cell {cell + 1})."
            )
            return None
        cell_mods[cell].append(normalized)
        log_message(
            f"[VOYAGE] Kenar {index}/12 -> cell {cell + 1}: {normalized}"
        )
    return cell_mods

def _voyage_chart_page_point(chart_tl, chart_br, page):
    width = chart_br[0] - chart_tl[0]
    row_height = (chart_br[1] - chart_tl[1]) / 9.0
    fraction = 0.37 if int(page) == 1 else 0.61
    return (
        round(chart_tl[0] + width * fraction),
        round(chart_tl[1] - row_height * 0.92),
    )


def _voyage_select_chart_page(chart_tl, chart_br, page):
    point = _voyage_chart_page_point(chart_tl, chart_br, page)
    _instant_move(*point)
    if not _voyage_wait(0.08) or not _voyage_click("left"):
        return False
    return _voyage_wait(0.3)


def _voyage_chart_panel_image():
    from PIL import ImageGrab

    return ImageGrab.grab(all_screens=True)


def _voyage_occupied_chart_slots(image, chart_tl, chart_br):
    points = _voyage_grid_points(chart_tl, chart_br, 6, 10)
    return {
        index
        for index, point in enumerate(points, start=1)
        if voyage.chart_slot_occupied(image, point)
    }


def _voyage_chart_panel_changed(before, after, chart_tl, chart_br):
    from PIL import ImageChops, ImageStat

    row_height = max(1, round((chart_br[1] - chart_tl[1]) / 9.0))
    box = (
        max(0, chart_tl[0] - 30),
        max(0, chart_tl[1] - row_height - 25),
        min(before.width, chart_br[0] + 30),
        min(before.height, chart_br[1] + 30),
    )
    difference = ImageChops.difference(before.crop(box), after.crop(box))
    return max(ImageStat.Stat(difference).mean) >= 1.0


def _voyage_scan_charts(chart_tl, chart_br, page=1, occupied_slots=None):
    points = _voyage_grid_points(chart_tl, chart_br, 6, 10)
    charts = []
    for index, point in enumerate(points, start=1):
        if occupied_slots is not None and index not in occupied_slots:
            continue
        if stop_event.is_set():
            return None
        text = capture_text_at_pos(
            point,
            pre_wait=0.025,
            post_copy_wait=0.08,
            tries=3,
        )
        if not text or not re.search(r"Item Class:\s*Chart\b", text, re.I):
            continue
        provisional = voyage.parse_chart_text(
            text,
            uid=f"page-{page}-slot-{index}",
            source=point,
            source_page=page,
        )
        if provisional is None:
            continue
        parsed = voyage.parse_chart_text(
            text,
            uid=f"page-{page}-slot-{index}",
            source=point,
            initial_edges=None,
            source_page=page,
        )
        if parsed is not None:
            charts.append(parsed)
            log_message(
                f"[VOYAGE] Sayfa {page} Chart {index}: L{parsed.area_level} "
                f"{parsed.shape}"
            )
    log_message(
        f"[VOYAGE] Sayfa {page}: {len(charts)} kullanilabilir Chart okundu."
    )
    return charts


def _voyage_scan_chart_pages(chart_tl, chart_br):
    page_one_image = _voyage_chart_panel_image()
    charts = _voyage_scan_charts(chart_tl, chart_br, page=1)
    if charts is None or stop_event.is_set():
        return None

    if not _voyage_select_chart_page(chart_tl, chart_br, 2):
        return None
    page_two_image = _voyage_chart_panel_image()
    page_changed = _voyage_chart_panel_changed(
        page_one_image,
        page_two_image,
        chart_tl,
        chart_br,
    )
    if not page_changed:
        log_message("[VOYAGE] Ikinci Chart sayfasi bulunamadi; sayfa 1 kullaniliyor.")
    else:
        occupied = _voyage_occupied_chart_slots(
            page_two_image,
            chart_tl,
            chart_br,
        )
        if occupied:
            log_message(
                f"[VOYAGE] Sayfa 2'de {len(occupied)} dolu Chart slotu algilandi."
            )
            page_two_charts = _voyage_scan_charts(
                chart_tl,
                chart_br,
                page=2,
                occupied_slots=occupied,
            )
            if page_two_charts is None or stop_event.is_set():
                return None
            charts.extend(page_two_charts)
        else:
            log_message("[VOYAGE] Sayfa 2 tamamen bos; clipboard taramasi atlandi.")

    if not _voyage_select_chart_page(chart_tl, chart_br, 1):
        return None
    log_message(f"[VOYAGE] Iki sayfada toplam {len(charts)} Chart kullanilabilir.")
    return charts

def _voyage_click(button="left", point=None, hover_origin=None):
    import ctypes
    from ctypes import wintypes

    class MouseInput(ctypes.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouse_data", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("extra_info", ctypes.c_size_t),
        )

    class InputUnion(ctypes.Union):
        _fields_ = (("mouse", MouseInput),)

    class Input(ctypes.Structure):
        _anonymous_ = ("data",)
        _fields_ = (("type", wintypes.DWORD), ("data", InputUnion))

    if button == "left":
        down_flag, up_flag = 0x0002, 0x0004
    else:
        down_flag, up_flag = 0x0008, 0x0010

    def send_flag(flag, dx=0, dy=0):
        event = Input(type=0, mouse=MouseInput(dx, dy, 0, flag, 0, 0))
        return ctypes.windll.user32.SendInput(
            1,
            ctypes.byref(event),
            ctypes.sizeof(Input),
        ) == 1

    def send_absolute(target):
        virtual_left = ctypes.windll.user32.GetSystemMetrics(76)
        virtual_top = ctypes.windll.user32.GetSystemMetrics(77)
        virtual_width = max(1, ctypes.windll.user32.GetSystemMetrics(78))
        virtual_height = max(1, ctypes.windll.user32.GetSystemMetrics(79))
        normalized_x = round(
            (target[0] - virtual_left) * 65535 / max(1, virtual_width - 1)
        )
        normalized_y = round(
            (target[1] - virtual_top) * 65535 / max(1, virtual_height - 1)
        )
        return send_flag(0xC001, normalized_x, normalized_y)

    if button == "right":
        # SetCursorPos does not always refresh PoE's DirectInput hover state.
        # Leave the chart cell and re-enter its exact centre using absolute
        # SendInput movement before delivering the right-click.
        if point is None or hover_origin is None:
            return False
        if not send_absolute(hover_origin):
            return False
        if not _voyage_wait(0.06):
            return False
        if not send_absolute(point):
            return False
        if not _voyage_wait(0.09):
            return False
    if not send_flag(down_flag):
        return False
    try:
        return _voyage_wait(0.1 if button == "right" else 0.06)
    finally:
        send_flag(up_flag)

def _voyage_place_chart(source, target, placement, cell_span):
    from PIL import ImageGrab

    if stop_event.is_set():
        return None

    _instant_move(*source)
    if not _voyage_wait(0.08):
        return None
    if not _voyage_click("left"):
        return None

    _instant_move(*target)
    if not _voyage_wait(0.14):
        return None
    if not _voyage_click("left"):
        return None
    if not _voyage_wait(0.22):
        return None

    # Keep the proven v1.0.44 placement path: read and rotate the chart while
    # the cursor is on its cell. Moving to a distant safe point between clicks
    # causes PoE to lose the board hover state on some systems.
    current_edges = voyage.detect_board_edges(
        ImageGrab.grab(all_screens=True),
        target,
        placement.chart.shape,
        cell_span=cell_span,
    )
    if current_edges is None:
        log_message(
            f"[VOYAGE] Cell {placement.cell + 1} anlik yonu okunamadi."
        )
        return None
    log_message(
        f"[VOYAGE] Cell {placement.cell + 1} birakma yonu "
        f"{_voyage_edge_code(current_edges)}; "
        f"hedef {_voyage_edge_code(placement.required_edges)}."
    )

    delivered_rotations = 0
    unchanged_attempts = 0
    for _attempt in range(8):
        if current_edges == placement.required_edges:
            return delivered_rotations
        hover_origin = (
            target[0] - max(84, round(cell_span * 0.65)),
            target[1],
        )
        if stop_event.is_set() or not _voyage_click(
            "right",
            point=target,
            hover_origin=hover_origin,
        ):
            return None
        if not _voyage_wait(0.42):
            return None
        updated_edges = voyage.detect_board_edges(
            ImageGrab.grab(all_screens=True),
            target,
            placement.chart.shape,
            cell_span=cell_span,
        )
        log_message(
            f"[VOYAGE] Cell {placement.cell + 1} sag tik sonucu: "
            f"{_voyage_edge_code(current_edges)} -> "
            f"{_voyage_edge_code(updated_edges)}."
        )
        if updated_edges is None:
            return None
        if updated_edges == current_edges:
            unchanged_attempts += 1
            if unchanged_attempts >= 3:
                log_message(
                    f"[VOYAGE] Cell {placement.cell + 1} sag tik uc kez "
                    "oyuna ulasmadi."
                )
                return None
            if not _voyage_wait(0.35):
                return None
            continue
        delivered_rotations += 1
        unchanged_attempts = 0
        current_edges = updated_edges
    return None

def _voyage_edge_code(edges):
    return "".join(
        direction
        for direction, active in zip("NESW", edges or ())
        if active
    ) or "?"

def _voyage_validate_placed_cell(placement, target, cell_span):
    from PIL import ImageGrab

    shape = placement.chart.shape
    if stop_event.is_set():
        return False
    _instant_move(pyautogui.size().width // 2, 80)
    if not _voyage_wait(0.22):
        return False
    detected = voyage.detect_board_edges(
        ImageGrab.grab(all_screens=True),
        target,
        shape,
        cell_span=cell_span,
    )
    log_message(
        f"[VOYAGE] Cell {placement.cell + 1} board yonu "
        f"{_voyage_edge_code(detected)}; "
        f"hedef {_voyage_edge_code(placement.required_edges)}."
    )
    return detected == placement.required_edges

def _voyage_validate_placed_plan(plan, board_points, cell_span):
    from PIL import ImageGrab

    _instant_move(pyautogui.size().width // 2, 80)
    if not _voyage_wait(0.2):
        return False
    screenshot = ImageGrab.grab(all_screens=True)
    actual_edges = []
    for placement in sorted(plan.placements, key=lambda item: item.cell):
        detected = voyage.detect_board_edges(
            screenshot,
            board_points[placement.cell],
            placement.chart.shape,
            cell_span=cell_span,
        )
        actual_edges.append(detected)
        if detected != placement.required_edges:
            log_message(
                f"[VOYAGE] Final kontrol cell {placement.cell + 1}: "
                f"{_voyage_edge_code(detected)} != "
                f"{_voyage_edge_code(placement.required_edges)}."
            )
            return False
    if not voyage.is_connected(tuple(actual_edges)):
        log_message("[VOYAGE] Final board baglanti grafigi kesintili.")
        return False
    log_message("[VOYAGE] Final board kontrolu: 9/9 yon ve baglanti dogru.")
    return True

def _voyage_place_plan(plan, board_tl, board_br, chart_tl, chart_br):
    board_points = _voyage_board_points(board_tl, board_br)
    if len(board_points) != 9 or len(set(board_points)) != 9:
        log_message(
            "[VOYAGE] Board koordinatlari 9 farkli hucre olusturmuyor; "
            "yerlestirme baslatilmadi."
        )
        stop_event.set()
        return False
    x_span = abs(board_points[1][0] - board_points[0][0])
    y_span = abs(board_points[3][1] - board_points[0][1])
    cell_span = min(x_span, y_span)
    active_page = 1
    for placement in voyage.placement_order(plan):
        if stop_event.is_set():
            return False
        source = placement.chart.source
        source_page = int(getattr(placement.chart, "source_page", 1) or 1)
        target = board_points[placement.cell]
        log_message(
            f"[VOYAGE] Yerlestirme {placement.chart.uid}: "
            f"source={source} -> cell {placement.cell + 1} target={target}."
        )
        if not source:
            log_message(
                f"[VOYAGE] {placement.chart.uid} kaynak koordinati yok; "
                "yerlestirme durduruldu."
            )
            stop_event.set()
            return False
        if source_page != active_page:
            log_message(f"[VOYAGE] Chart kaynak sayfasi {source_page} seciliyor.")
            if not _voyage_select_chart_page(chart_tl, chart_br, source_page):
                stop_event.set()
                return False
            active_page = source_page
        log_message(
            f"[VOYAGE] {placement.chart.uid} tek tikla aliniyor; "
            f"cell {placement.cell + 1} hedefine tek tikla birakilacak."
        )
        rotation_clicks = _voyage_place_chart(
            source,
            target,
            placement,
            cell_span,
        )
        if rotation_clicks is None:
            stop_event.set()
            return False
        if not _voyage_wait(0.12):
            return False
        source_text = capture_text_at_pos(
            source,
            pre_wait=0.03,
            post_copy_wait=0.08,
            tries=3,
        )
        if re.search(r"Item Class:\s*Chart\b", source_text or "", re.I):
            log_message(
                f"[VOYAGE] {placement.chart.uid} kaynak slottan alinmadi; "
                f"cell {placement.cell + 1} yerlestirmesi durduruldu."
            )
            stop_event.set()
            return False
        if not _voyage_validate_placed_cell(
            placement,
            target,
            cell_span,
        ):
            log_message(
                f"[VOYAGE] Cell {placement.cell + 1} yanlis yonle yerlesti; "
                "guvenlik icin devam edilmedi."
            )
            stop_event.set()
            return False
        log_message(
            f"[VOYAGE] Cell {placement.cell + 1}: "
            f"{placement.chart.uid}, hedefte R x{rotation_clicks}; "
            "kaynak slot bosaldi."
        )
    return _voyage_validate_placed_plan(plan, board_points, cell_span)

def _voyage_focus_game():
    try:
        import win32con
        import win32gui

        game_window = win32gui.FindWindow(None, "Path of Exile")
        if not game_window:
            return False
        win32gui.ShowWindow(game_window, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(game_window)
        return True
    except Exception as exc:
        log_message(f"[VOYAGE] PoE penceresi odaklanamadi: {exc}")
        return False


def _voyage_poe_client_rect():
    try:
        import win32gui

        game_window = win32gui.FindWindow(None, "Path of Exile")
        if not game_window:
            return None
        client_left, client_top = win32gui.ClientToScreen(game_window, (0, 0))
        client_right, client_bottom = win32gui.ClientToScreen(
            game_window,
            win32gui.GetClientRect(game_window)[2:4],
        )
        return client_left, client_top, client_right, client_bottom
    except Exception as exc:
        log_message(f"[VOYAGE] PoE istemci alani okunamadi: {exc}")
        return None

def _voyage_restore_window():
    try:
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
    except Exception:
        pass

def run_voyage_craft(settings):
    manual_points = {
        "chart_tl": settings.get("voyage_chart_tl"),
        "chart_br": settings.get("voyage_chart_br"),
        "board_tl": settings.get("voyage_board_tl"),
        "board_br": settings.get("voyage_board_br"),
    }
    try:
        root.after(0, root.withdraw)
    except Exception:
        pass
    if not _voyage_wait(0.25) or not _voyage_focus_game():
        log_message("[VOYAGE] Path of Exile penceresi bulunamadi; tarama baslatilmadi.")
        return
    if not _voyage_wait(0.2):
        return
    client_rect = _voyage_poe_client_rect()
    automatic_points = voyage.auto_calibration_points(client_rect)
    scaled_manual_points = _voyage_scaled_manual_points(manual_points, client_rect)
    candidates = []
    if automatic_points:
        log_message(
            f"[VOYAGE] Otomatik kalibrasyon: client={client_rect}, "
            f"chart={automatic_points['chart_tl']}..{automatic_points['chart_br']}, "
            f"board={automatic_points['board_tl']}..{automatic_points['board_br']}."
        )
        candidates.append(("otomatik", automatic_points))
    if all(scaled_manual_points.values()) and scaled_manual_points != automatic_points:
        candidates.append(("kisisel-olcekli", scaled_manual_points))
    if not candidates:
        log_message("[VOYAGE] Otomatik ve manuel kalibrasyon bulunamadi.")
        return

    charts = None
    border_mods = None
    selected_points = None
    for calibration_name, points in candidates:
        if stop_event.is_set():
            return
        chart_tl, chart_br = points["chart_tl"], points["chart_br"]
        board_tl, board_br = points["board_tl"], points["board_br"]
        log_message(
            f"[VOYAGE] {calibration_name} kalibrasyon ile once 12 kenar okunuyor."
        )
        border_mods = _voyage_scan_borders(board_tl, board_br)
        if border_mods is None:
            log_message(
                f"[VOYAGE] {calibration_name} kenar dogrulamasi basarisiz."
            )
            continue
        log_message("[VOYAGE] 6x10 Chart paneli taraniyor.")
        charts = _voyage_scan_chart_pages(chart_tl, chart_br)
        if charts is None or stop_event.is_set():
            return
        if len(charts) < 9:
            log_message(
                f"[VOYAGE] {calibration_name} ile en az 9 Chart bulunamadi."
            )
            continue
        selected_points = points
        break
    if selected_points is None:
        log_message(
            "[VOYAGE] Hicbir kalibrasyon hem board kenarlarini hem Chart panelini "
            "dogrulayamadi."
        )
        return
    chart_tl, chart_br = selected_points["chart_tl"], selected_points["chart_br"]
    board_tl, board_br = selected_points["board_tl"], selected_points["board_br"]
    plan = voyage.plan_voyage(charts, border_mods)
    if plan is None:
        log_message(
            "[VOYAGE] Mevcut Chart sekilleriyle 9 parcali baglantili rota bulunamadi."
        )
        return
    summary = voyage.summarize_plan(plan)
    log_message("[VOYAGE] Plan hazir:\n" + summary)
    try:
        root.after(0, lambda value=summary: _voyage_set_status(value))
    except Exception:
        pass
    if settings.get("voyage_auto_place", True):
        if _voyage_place_plan(plan, board_tl, board_br, chart_tl, chart_br):
            log_message(
                "[VOYAGE] 9 Chart yerlestirildi ve dogrulandi. "
                "Begin Voyage otomatik tiklanmadi."
            )
    else:
        log_message("[VOYAGE] Auto Place kapali; yalnizca plan olusturuldu.")

def parse_currency_stack(text: str):
    if not text:
        return None
    patterns = [
        r"stack size:\s*([\d\.,]+)\s*/\s*([\d\.,]+)",
        r"stack size\s+([\d\.,]+)\s*/\s*([\d\.,]+)",
        r"stack:\s*([\d\.,]+)\s*/\s*([\d\.,]+)",
    ]
    low = text.lower()
    for pat in patterns:
        m = re.search(pat, low, re.IGNORECASE)
        if m:
            try:
                current = re.sub(r"[^\d]", "", m.group(1))
                return int(current) if current else None
            except Exception:
                return None
    return None

def is_expected_currency_text(text: str, orb_name: str):
    low = (text or "").lower()
    return ("rarity: currency" in low) and (orb_name.lower() in low)

def get_orb_slot_candidates(orb_name: str):
    locs = get_orb_locations_dict()
    base = orb_name.lower().strip()
    candidates = []
    seen_positions = set()

    try:
        x, y = map(int, locs.get(base, "").split(","))
        candidates.append((1, base, (x, y)))
        seen_positions.add((x, y))
    except Exception:
        pass

    shared_bases = ("orb of alteration", "orb of augmentation")
    accepted_bases = shared_bases if base in shared_bases else (base,)
    backups = []
    for key, val in locs.items():
        match = re.match(r"^(.+?)\s+slot\s+(\d+)$", key)
        if not match or match.group(1) not in accepted_bases:
            continue
        try:
            x, y = map(int, val.split(","))
            configured_slot = int(match.group(2))
        except Exception:
            continue
        # Prefer labels belonging to the requested orb, but scan every configured
        # Alteration/Augmentation backup location and verify its live contents.
        owner_priority = 0 if match.group(1) == base else 1
        backups.append((owner_priority, configured_slot, key, (x, y)))

    backups.sort(key=lambda item: (item[0], item[1], item[2]))
    for _, _, key, pos in backups:
        if pos in seen_positions:
            continue
        seen_positions.add(pos)
        candidates.append((len(candidates) + 1, key, pos))
    return candidates

def verify_cached_currency_slot(orb_name: str):
    cache = ACTIVE_ORB_SLOT_CACHE.get(orb_name)
    if not cache:
        return None
    _, pos = cache
    txt = capture_text_at_pos(pos, pre_wait=0.03, post_copy_wait=0.04, tries=2)
    if is_expected_currency_text(txt, orb_name):
        parsed_stack = parse_currency_stack(txt)
        if parsed_stack is not None:
            ACTIVE_ORB_STACK_CACHE[orb_name] = parsed_stack
        return pos
    return None

def _read_stack_at_slot(pos):
    txt = capture_text_at_pos(pos, pre_wait=0.03, post_copy_wait=0.04, tries=2)
    if not txt.strip():
        return None, txt
    return parse_currency_stack(txt), txt

def update_stack_cache_after_use(orb_name: str, before_stack, after_stack, after_txt):
    if orb_name not in SAFE_STACK_TRACKED_ORBS:
        return
    if after_stack is not None:
        ACTIVE_ORB_STACK_CACHE[orb_name] = after_stack
    elif before_stack is not None and (not after_txt or not is_expected_currency_text(after_txt, orb_name)):
        ACTIVE_ORB_STACK_CACHE[orb_name] = 0
    else:
        current = ACTIVE_ORB_STACK_CACHE.get(orb_name)
        if current is None and before_stack is not None:
            ACTIVE_ORB_STACK_CACHE[orb_name] = max(0, before_stack - 1)

def find_currency_slot_initial(orb_name: str):
    verified = verify_cached_currency_slot(orb_name)
    if verified:
        return verified

    candidates = get_orb_slot_candidates(orb_name)
    if not candidates:
        ACTIVE_ORB_SLOT_CACHE[orb_name] = None
        ACTIVE_ORB_STACK_CACHE[orb_name] = None
        return None

    for _, key, pos in candidates:
        txt = capture_text_at_pos(pos, pre_wait=0.03, post_copy_wait=0.04, tries=2)
        if is_expected_currency_text(txt, orb_name):
            ACTIVE_ORB_SLOT_CACHE[orb_name] = (key, pos)
            ACTIVE_ORB_STACK_CACHE[orb_name] = parse_currency_stack(txt)
            return pos

    ACTIVE_ORB_SLOT_CACHE[orb_name] = None
    ACTIVE_ORB_STACK_CACHE[orb_name] = None
    return None

def find_next_currency_slot_after_cache(orb_name: str):
    candidates = get_orb_slot_candidates(orb_name)
    if not candidates:
        ACTIVE_ORB_SLOT_CACHE[orb_name] = None
        ACTIVE_ORB_STACK_CACHE[orb_name] = None
        return None

    cache = ACTIVE_ORB_SLOT_CACHE.get(orb_name)
    ordered = list(candidates)

    if cache:
        cached_key, _ = cache
        idx = -1
        for i, (_, key, _) in enumerate(candidates):
            if key == cached_key:
                idx = i
                break
        if idx != -1:
            ordered = candidates[idx + 1:] + candidates[:idx + 1]

    for _, key, pos in ordered:
        txt = capture_text_at_pos(pos, pre_wait=0.03, post_copy_wait=0.04, tries=2)
        if is_expected_currency_text(txt, orb_name):
            ACTIVE_ORB_SLOT_CACHE[orb_name] = (key, pos)
            ACTIVE_ORB_STACK_CACHE[orb_name] = parse_currency_stack(txt)
            return pos

    ACTIVE_ORB_SLOT_CACHE[orb_name] = None
    ACTIVE_ORB_STACK_CACHE[orb_name] = None
    return None

def resolve_orb_location(orb_name: str):
    if orb_name in SAFE_STACK_TRACKED_ORBS:
        return find_currency_slot_initial(orb_name)
    return get_orb_location(orb_name)

def get_cached_orb_loc(orb_name: str):
    cache = ACTIVE_ORB_SLOT_CACHE.get(orb_name)
    if cache:
        return cache[1]
    return None

def decrement_local_stack_cache(orb_name: str):
    if orb_name not in SAFE_STACK_TRACKED_ORBS:
        return
    current = ACTIVE_ORB_STACK_CACHE.get(orb_name)
    if isinstance(current, int):
        ACTIVE_ORB_STACK_CACHE[orb_name] = max(0, current - 1)

def ensure_stack_tracked_orb_available(orb_name: str):
    if orb_name not in SAFE_STACK_TRACKED_ORBS:
        return resolve_orb_location(orb_name)

    current_stack = ACTIVE_ORB_STACK_CACHE.get(orb_name)
    if current_stack == 0:
        log_message(f"[{orb_name}] Local count hit 0, searching next slot.")
        return find_next_currency_slot_after_cache(orb_name)

    loc = get_cached_orb_loc(orb_name)
    if loc:
        return loc
    return find_currency_slot_initial(orb_name)

def _read_fast_tracked_slot_stack(orb_name: str, pos):
    txt = capture_text_at_pos(pos, pre_wait=0.03, post_copy_wait=0.04, tries=2)
    if not txt.strip():
        return "empty", None, txt
    if not is_expected_currency_text(txt, orb_name):
        return "other", None, txt
    stack = parse_currency_stack(txt)
    if stack is None:
        return "unknown", None, txt
    return "ok", stack, txt

def _fast_probe_log_preview(text: str):
    raw = (text or "").replace("\r", " ").replace("\n", " | ").strip()
    return raw[:220] if len(raw) > 220 else raw

def _decrement_fast_tracked_stack(orb_name: str):
    if orb_name not in FAST_STACK_TRACKED_ORBS:
        return None
    current = FAST_ORB_STACK_CACHE.get(orb_name)
    if isinstance(current, int):
        FAST_ORB_STACK_CACHE[orb_name] = max(0, current - 1)
    return FAST_ORB_STACK_CACHE.get(orb_name)

def _prepare_fast_stack_probe(orb_name: str):
    snap = get_fast_cursor_snapshot() if FAST_CURSOR_MODEL.get("ready") else {"state": "unknown"}
    if snap.get("state") != "active":
        return
    try:
        keyboard.release("shift")
    except Exception:
        pass
    safe_wait(0.15)
    try:
        pyautogui.click(button="right")
    except Exception:
        try:
            pyautogui.mouseDown(button="right")
            pyautogui.mouseUp(button="right")
        except Exception:
            pass
    safe_wait(0.15)
    log_message(f"[FAST-CURSOR] {orb_name} slot probe oncesi active goruldu, shift release + sag tik uygulandi.")

def _find_fast_stack_tracked_orb_slot(orb_name: str, prefer_next=False):
    if orb_name not in FAST_STACK_TRACKED_ORBS:
        return get_orb_location(orb_name)

    candidates = get_orb_slot_candidates(orb_name)
    if not candidates:
        return None

    cached = FAST_ORB_SLOT_CACHE.get(orb_name)
    start_index = 0
    if cached:
        cached_no, cached_pos = cached
        cached_stack = FAST_ORB_STACK_CACHE.get(orb_name)
        if not prefer_next and isinstance(cached_stack, int) and cached_stack > FAST_STACK_DEPLETION_THRESHOLD:
            return cached_pos
        for idx, (slot_no, _, _) in enumerate(candidates):
            if slot_no == cached_no:
                if prefer_next or (isinstance(cached_stack, int) and cached_stack <= FAST_STACK_DEPLETION_THRESHOLD):
                    start_index = idx + 1
                else:
                    start_index = idx
                break

    ordered = candidates[start_index:] + candidates[:start_index]
    for slot_no, _, pos in ordered:
        last_status = None
        last_stack = None
        for attempt in range(1, FAST_SLOT_PROBE_RETRIES + 1):
            _prepare_fast_stack_probe(orb_name)
            status, stack, raw_txt = _read_fast_tracked_slot_stack(orb_name, pos)
            last_status = status
            last_stack = stack
            log_message(
                f"[FAST-SLOT] {orb_name} slot#{slot_no} probe {attempt}/{FAST_SLOT_PROBE_RETRIES}: "
                f"status={status} stack={stack} text={_fast_probe_log_preview(raw_txt)}"
            )
            if status == "ok" and stack is not None and stack > FAST_STACK_DEPLETION_THRESHOLD:
                FAST_ORB_SLOT_CACHE[orb_name] = (slot_no, pos)
                FAST_ORB_STACK_CACHE[orb_name] = stack
                return pos
            if attempt < FAST_SLOT_PROBE_RETRIES:
                safe_wait(FAST_SLOT_PROBE_RETRY_WAIT)
        if last_status == "ok" and isinstance(last_stack, int):
            FAST_ORB_STACK_CACHE[orb_name] = last_stack

    FAST_ORB_SLOT_CACHE[orb_name] = None
    FAST_ORB_STACK_CACHE[orb_name] = None
    return None

def has_backup_orb_slot(orb_name: str):
    return any(slot_no > 1 for slot_no, _, _ in get_orb_slot_candidates(orb_name))

# ================ PARSER & AFFIX CLASSIFY ================
AFFIX_BOILERPLATE = [
    re.compile(r"1 added passive skill is\s*", re.IGNORECASE),
    re.compile(r"added small passive skills (also )?grant:?\s*", re.IGNORECASE),
    re.compile(r"added small passive skills have\s*", re.IGNORECASE),
]

def clean_advanced_explicit_mod_block(block):
    has_advanced_headers = any(line.lstrip().startswith("{") for line in block)
    cleaned = []
    current_fractured = False
    for raw in block:
        line = raw.strip()
        if not line or RE_INTANGIBILITY_METADATA.fullmatch(line):
            continue
        if has_advanced_headers:
            if line.startswith("{"):
                current_fractured = "fractured" in line.lower()
                continue
            # Advanced descriptions add explanatory parenthetical lines that are not affixes.
            if line.startswith("(") and line.endswith(")"):
                continue
            line = RE_ADVANCED_ROLL_RANGE.sub("", line)
        if line:
            if current_fractured and "(fractured)" not in line.lower():
                line = f"{line} (fractured)"
            cleaned.append(line)
    return cleaned

@functools.lru_cache(maxsize=1024)
def _parse_item_text_cached(text: str):
    lines = text.splitlines()
    item_class = next(
        (l.split(":", 1)[1].strip().lower() for l in lines if l.strip().lower().startswith("item class:")),
        "",
    )
    rarity = next(
        (l.split(":", 1)[1].strip().capitalize() for l in lines if l.strip().lower().startswith("rarity:")),
        "Unknown",
    )
    mods = []
    try:
        sep = [i for i, l in enumerate(lines) if "--------" in l]
        if not sep:
            return rarity, tuple()
        for i in range(len(sep) - 1):
            sidx = sep[i] + 1
            eidx = sep[i + 1]
            block = [ln.strip() for ln in lines[sidx:eidx] if ln.strip()]
            if not block:
                continue

            if item_class == "maps":
                skip_map_block = False
                for ln in block:
                    low = ln.lower()
                    if any(kw in low for kw in ["(implicit)", "item level:", "monster level:", "travel to a map", "can only be used once.", "requirements:"]):
                        skip_map_block = True
                        break
                if skip_map_block:
                    continue
                # Map summary blocklari (quantity/rarity/pack size/more scarabs vb.) ":" icerir;
                # explicit map modlari ise ayri blokta ve genelde ":" icermez.
                if all(":" in ln for ln in block):
                    continue

            is_mod = True
            for ln in block:
                low = ln.lower()
                if any(kw in low for kw in [
                    "(enchant)",
                    "enchantment modifier",
                    "implicit modifier",
                    "requirements:",
                    "item level:",
                    "place into",
                ]):
                    is_mod = False
                    break
            if is_mod:
                cleaned_block = clean_advanced_explicit_mod_block(block)
                if cleaned_block:
                    mods.extend(cleaned_block)
                    break
    except Exception as e:
        log_message(f"[HATA] Parser: {e}")
    return rarity, tuple(mods)

def parse_item_text(text: str):
    started = time.perf_counter()
    try:
        rarity, mods = _parse_item_text_cached(text or "")
        return rarity, list(mods)
    finally:
        _perf_record("parse_item_text", time.perf_counter() - started)

def parse_socket_state(text: str):
    state = {
        "raw_line": "",
        "groups": [],
        "total_sockets": 0,
        "max_link": 0,
        "colors": {"R": 0, "G": 0, "B": 0, "W": 0},
    }
    if not text:
        return state

    for raw in text.splitlines():
        line = raw.strip()
        if not line.lower().startswith("sockets:"):
            continue

        state["raw_line"] = line
        groups = []
        for token in line.split(":", 1)[1].strip().upper().split():
            letters = re.findall(r"[RGBW]", token)
            if letters:
                groups.append(letters)

        state["groups"] = groups
        state["total_sockets"] = sum(len(group) for group in groups)
        state["max_link"] = max((len(group) for group in groups), default=0)
        for group in groups:
            for color in group:
                if color in state["colors"]:
                    state["colors"][color] += 1
        break

    return state

def format_socket_state(state):
    colors = state.get("colors", {})
    parts = [
        f"Sockets={state.get('total_sockets', 0)}",
        f"MaxLink={state.get('max_link', 0)}",
        f"Colors=R{colors.get('R', 0)} G{colors.get('G', 0)} B{colors.get('B', 0)}",
    ]
    if colors.get("W", 0):
        parts.append(f"W{colors.get('W', 0)}")
    return " ".join(parts)

def parse_map_summary_stats(text: str):
    stats = {
        "quantity": None,
        "rarity": None,
        "pack_size": None,
    }
    if not text:
        return stats

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        num_match = RE_SIGNED_INT.search(line)
        value = int(num_match.group(1)) if num_match else None

        if low.startswith("item quantity:") and value is not None:
            stats["quantity"] = value
        elif low.startswith("item rarity:") and value is not None:
            stats["rarity"] = value
        elif low.startswith("monster pack size:") and value is not None:
            stats["pack_size"] = value

    return stats

def _map_threshold_checks(summary_stats, settings):
    return map_rules.threshold_checks(summary_stats, settings)

def _map_numeric_threshold_failures(summary_stats, settings):
    return map_rules.threshold_failures(summary_stats, settings)

def _find_matching_map_mod_index(template_entry, available_mods):
    for idx, mod in enumerate(available_mods):
        if _match_normalized(template_entry, [normalize_mod_text(mod)]):
            return idx
    return None

def load_affix_patterns(path):
    patterns, texts = set(), set()
    if not os.path.exists(path):
        return patterns, texts
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip().lower()
            if not s or s.startswith("#"):
                continue
            pat_str = re.escape(s).replace(r"\#", r"[\d\.]+")
            patterns.add(re.compile(pat_str))
            texts.add(s.replace(r"\#", ".*"))
    return patterns, texts

P_PATTERNS, P_TEXTS = load_affix_patterns(CLUSTER_P_PATH)
S_PATTERNS, S_TEXTS = load_affix_patterns(CLUSTER_S_PATH)

def load_base_jewel_affix_catalog():
    fallback = [
        {
            "type": "prefix",
            "group": "BaseJewelCritElementPrefix",
            "patterns": DEFAULT_BASE_JEWEL_CRIT_MODS[1:4],
        },
        {
            "type": "suffix",
            "group": "BaseJewelCritSuffix",
            "patterns": [DEFAULT_BASE_JEWEL_CRIT_MODS[0], DEFAULT_BASE_JEWEL_CRIT_MODS[4]],
        },
        {
            "type": "prefix",
            "group": "PercentIncreasedLifeForJewel",
            "patterns": DEFAULT_BASE_JEWEL_LIFE_MODS,
        },
    ]
    try:
        if os.path.exists(BASE_JEWEL_AFFIX_PATH):
            with open(BASE_JEWEL_AFFIX_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list) and loaded:
                fallback = loaded
    except Exception as e:
        log_message(f"[BASE JEWEL] Affix catalog okunamadi: {e}")

    catalog = []
    for index, raw in enumerate(fallback):
        affix_type = str(raw.get("type", "unknown")).strip().lower()
        if affix_type not in ("prefix", "suffix"):
            continue
        patterns = []
        raw_patterns = []
        for value in raw.get("patterns", []):
            text = str(value).strip().lower()
            if not text:
                continue
            pattern = re.escape(text).replace(r"\#", MATCH_WILDCARD_PATTERN)
            patterns.append(re.compile(pattern, re.I))
            raw_patterns.append(text)
        if patterns:
            catalog.append({
                "index": index,
                "type": affix_type,
                "group": str(raw.get("group") or f"base_jewel_{index}"),
                "patterns": tuple(patterns),
                "raw_patterns": tuple(raw_patterns),
            })
    return tuple(catalog)

BASE_JEWEL_AFFIX_CATALOG = load_base_jewel_affix_catalog()

@functools.lru_cache(maxsize=8192)
def find_base_jewel_affix_entry(mod_text):
    low = (mod_text or "").lower()
    for entry in BASE_JEWEL_AFFIX_CATALOG:
        if any(pattern.search(low) for pattern in entry["patterns"]):
            return entry["index"], entry["type"], entry["group"]
    return None, "unknown", ""

def classify_base_jewel_mod_type(mod_text):
    return find_base_jewel_affix_entry(mod_text)[1]

def base_jewel_affix_records(mods, magic_item=False):
    records = {}
    order = []
    for line_index, mod in enumerate(mods):
        catalog_index, affix_type, group = find_base_jewel_affix_entry(mod)
        key = ("known", group) if catalog_index is not None else ("unknown", line_index)
        if key not in records:
            records[key] = {
                "type": affix_type,
                "group": group,
                "mods": [],
            }
            order.append(key)
        records[key]["mods"].append(mod)
    result = [records[key] for key in order]
    if not magic_item:
        return result

    # A magic item can have at most one prefix and one suffix. Some affixes
    # produce multiple text lines, so collapse same-type lines before counting.
    collapsed = []
    by_type = {}
    for record in result:
        affix_type = record["type"]
        if affix_type not in ("prefix", "suffix"):
            collapsed.append(record)
            continue
        if affix_type not in by_type:
            merged = {
                "type": affix_type,
                "group": record["group"],
                "mods": list(record["mods"]),
            }
            by_type[affix_type] = merged
            collapsed.append(merged)
        else:
            by_type[affix_type]["mods"].extend(record["mods"])
    return collapsed

@functools.lru_cache(maxsize=8192)
def _extract_first_numeric_value(text):
    m = RE_FIRST_NUMBER.search(text or "")
    return float(m.group(1)) if m else None

@functools.lru_cache(maxsize=8192)
def classify_mod_type(mod_text):
    low = (mod_text or "").lower()
    if "added small passive skills" in low:
        if any(k in low for k in [
            "increased effect",
            "increased damage",
            "to armour",
            "to evasion",
            "to maximum energy shield",
            "to maximum life",
            "to maximum mana",
        ]):
            return "prefix"
        return "suffix"
    if any(p.search(low) for p in P_PATTERNS):
        return "prefix"
    if any(p.search(low) for p in S_PATTERNS):
        return "suffix"
    return "unknown"

@functools.lru_cache(maxsize=2048)
def _mods_with_types_cached(mods_key):
    return tuple((m, classify_mod_type(m)) for m in mods_key)

def mods_with_types(mods):
    return list(_mods_with_types_cached(tuple(mods)))

# weight pool sistemi kaldırıldı — combcraft kombinasyon mantığına geçildi

def stop_shift_spam():
    """Adamın stopStream — sadece isStream=true iken shift bırakır."""
    global shift_spam_active, socket_shift_spam_orb
    was_active = shift_spam_active
    try:
        keyboard.release("shift")
    except Exception:
        pass
    shift_spam_active = False
    socket_shift_spam_orb = None
    if was_active:
        time.sleep(0.005)  # adamın ShiftUp: Sleep(5)
        log_message("[ShiftSpam] Durduruldu.")

# ================ ORB APPLICATION ================
def apply_orb(orb_name, item_pos):
    """Adamın craftMagic orb kısmı: stopStream → RClick(orb) → LClick(item), aralarında sleep yok."""
    loc = get_orb_location(orb_name)
    if not loc:
        log_message(f"[HATA] {orb_name} konumu yok! Settings > Orb Locations")
        return
    try:
        stop_shift_spam()
        if not _recover_default_after_shift_stream(orb_name):
            return
        if stop_event.is_set():
            return
        if not _pick_orb_with_verify(orb_name, loc):
            return
        if not _apply_orb_to_item_with_verify(orb_name, item_pos):
            return
        record_currency_use(orb_name)
        if FAST_CURSOR_LOG_SUCCESS_DETAILS:
            log_message(f"[FAST-CURSOR] {orb_name} verify ok.")
        log_message(f"🧿 {orb_name}")
    except Exception as e:
        log_message(f"[HATA] apply_orb(): {e}\n{traceback.format_exc()}")

# ================ CRAFT LOGIC (Magic/Rare/Comb) ================
def apply_augmentation_with_failover(chain_craft=False):
    """Augment at - tekli craftta eski davranis, chainde ilk dolu yedek slot."""
    if not chain_craft:
        log_message("[AUG] Orb of Augmentation deneniyor.")
        apply_orb("Orb of Augmentation", ITEM_POS)
        return

    orb_loc = _find_fast_stack_tracked_orb_slot("Orb of Augmentation")
    if not orb_loc:
        log_message("[HATA] Orb of Augmentation slotu yok veya tum yedek slotlar bos!")
        return

    FAST_ORB_USE_COUNTERS["Orb of Augmentation"] += 1
    stop_shift_spam()
    if not _recover_default_after_shift_stream("Orb of Augmentation"):
        return
    log_message("[AUG] Orb of Augmentation deneniyor.")
    if not _pick_orb_with_verify("Orb of Augmentation", orb_loc):
        return
    if not _apply_orb_to_item_with_verify("Orb of Augmentation", ITEM_POS):
        return
    record_currency_use("Orb of Augmentation")
    remaining = _decrement_fast_tracked_stack("Orb of Augmentation")
    if isinstance(remaining, int) and remaining <= FAST_STACK_DEPLETION_THRESHOLD:
        log_message(f"[AUG] Slot stack {remaining} oldu, sonraki augmentte yedek slot aranacak.")

def apply_alteration_with_failover(chain_craft=False):
    """
    Adamın craftMagic alter kısmı birebir:
    if not isStream: RClick(alter) → ShiftDown() → isStream=true
    LClick(item)
    """
    global shift_spam_active

    if not chain_craft:
        orb_loc = get_orb_location("Orb of Alteration")
        if not orb_loc:
            log_message("[HATA] Orb of Alteration konumu yok!")
            return

        if not shift_spam_active:
            if not _recover_default_after_shift_stream("Orb of Alteration"):
                return
            if not _pick_orb_with_verify("Orb of Alteration", orb_loc):
                return
            try:
                keyboard.press("shift")
            except Exception:
                pass
            time.sleep(0.005)
            shift_spam_active = True
            log_message("[ALT] Orb of Alteration alindi, spam basliyor.")

        if not _stream_click_item_with_verify("Orb of Alteration", ITEM_POS):
            return
        record_currency_use("Orb of Alteration")
        return

    if shift_spam_active:
        FAST_ORB_USE_COUNTERS["Orb of Alteration"] += 1
        if FAST_ORB_USE_COUNTERS["Orb of Alteration"] >= FAST_ALTER_SLOT_CHECK_EVERY:
            FAST_ORB_USE_COUNTERS["Orb of Alteration"] = 0
            cached_stack = FAST_ORB_STACK_CACHE.get("Orb of Alteration")
            if isinstance(cached_stack, int) and cached_stack <= FAST_STACK_DEPLETION_THRESHOLD:
                stop_shift_spam()
                next_loc = _find_fast_stack_tracked_orb_slot("Orb of Alteration", prefer_next=True)
                if not next_loc:
                    log_message("[HATA] Orb of Alteration icin dolu slot kalmadi!")
                    return
                orb_right_click(next_loc[0], next_loc[1])
                try:
                    keyboard.press("shift")
                except Exception:
                    pass
                time.sleep(0.005)
                shift_spam_active = True
                log_message("[ALT] Alteration yedek slota gecti.")

    orb_loc = _find_fast_stack_tracked_orb_slot("Orb of Alteration")
    if not orb_loc:
        log_message("[HATA] Orb of Alteration slotu yok veya tum yedek slotlar bos!")
        return

    if not shift_spam_active:
        if not _recover_default_after_shift_stream("Orb of Alteration"):
            return
        if not _pick_orb_with_verify("Orb of Alteration", orb_loc):
            return
        try:
            keyboard.press("shift")
        except Exception:
            pass
        time.sleep(0.005)  # adamın ShiftDown: Sleep(5)
        shift_spam_active = True
        FAST_ORB_USE_COUNTERS["Orb of Alteration"] = 0
        log_message("[ALT] Orb of Alteration alındı, spam başlıyor.")

    # Adamın: LClick(item) — her tur
    if not _stream_click_item_with_verify("Orb of Alteration", ITEM_POS):
        return
    record_currency_use("Orb of Alteration")
    remaining = _decrement_fast_tracked_stack("Orb of Alteration")
    if isinstance(remaining, int) and remaining <= FAST_STACK_DEPLETION_THRESHOLD:
        next_loc = _find_fast_stack_tracked_orb_slot("Orb of Alteration", prefer_next=True)
        if next_loc:
            stop_shift_spam()
            orb_right_click(next_loc[0], next_loc[1])
            try:
                keyboard.press("shift")
            except Exception:
                pass
            time.sleep(0.005)
            shift_spam_active = True
            FAST_ORB_USE_COUNTERS["Orb of Alteration"] = 0
            log_message("[ALT] Alteration yedek slota gecti.")
        else:
            log_message("[HATA] Orb of Alteration icin sonraki dolu slot bulunamadi!")

def handle_map_craft_state(mods, settings, item_text=""):
    """Compatibility entry point for the current profile-based map rules."""
    return handle_map_craft_state_v2(mods, settings, item_text)

def load_map_affix_groups():
    try:
        return map_rules.load_affix_groups(MAP_MODS_PATH)
    except Exception as e:
        log_message(f"[MAP] map_mods.json okunamadi: {e}")
        return []

def get_unique_map_affix_shapes():
    seen = set()
    unique = []
    for group in load_map_affix_groups():
        key = (group.get("affix_type", ""), tuple(group.get("mods", [])))
        if key in seen:
            continue
        seen.add(key)
        unique.append(group)
    return unique

def match_map_affix_groups(mods, groups):
    available = list(mods)
    matched = []
    ordered = sorted(groups, key=lambda g: (-len(g.get("mods", [])), g.get("affix_type", "")))
    for group in ordered:
        working = list(available)
        picked = []
        ok = True
        for template_mod in group.get("mods", []):
            idx = _find_matching_map_mod_index(template_mod, working)
            if idx is None:
                ok = False
                break
            picked.append(working.pop(idx))
        if ok:
            matched.append(group)
            available = working
    return matched

def get_map_open_affix_types(mods):
    matched_groups = match_map_affix_groups(mods, get_unique_map_affix_shapes())
    prefix_count = sum(1 for g in matched_groups if g.get("affix_type") == "prefix")
    suffix_count = sum(1 for g in matched_groups if g.get("affix_type") == "suffix")
    open_types = []
    if prefix_count < 3:
        open_types.append("prefix")
    if suffix_count < 3:
        open_types.append("suffix")
    return open_types, matched_groups

def find_map_exalt_candidate(mods, summary_stats, settings):
    open_types, matched_groups = get_map_open_affix_types(mods)
    if not open_types:
        return None
    forbidden = map_rules.active_forbidden(settings)
    matched_keys = {
        (g.get("affix_type", ""), tuple(g.get("mods", [])))
        for g in matched_groups
    }
    for group in load_map_affix_groups():
        if group.get("affix_type") not in open_types:
            continue
        key = (group.get("affix_type", ""), tuple(group.get("mods", [])))
        if key in matched_keys:
            continue
        if _count_template_matches(forbidden, group.get("mods", [])) > 0:
            continue
        projected = {
            "quantity": (summary_stats.get("quantity") or 0) + int(group.get("quantity", 0) or 0),
            "rarity": (summary_stats.get("rarity") or 0) + int(group.get("rarity", 0) or 0),
            "pack_size": (summary_stats.get("pack_size") or 0) + int(group.get("pack", 0) or 0),
        }
        if not _map_numeric_threshold_failures(projected, settings):
            return group
    return None

def _map_reset_exalt_fail_state(settings):
    settings["_map_exalt_pending"] = False
    settings["_map_exalt_last_text"] = None
    settings["_map_exalt_same_text_failures"] = 0

def _map_note_exalt_attempt(settings, item_text):
    settings["_map_exalt_pending"] = True
    settings["_map_exalt_last_text"] = item_text or ""

def _map_register_exalt_result(settings, item_text):
    if not settings.get("_map_exalt_pending"):
        return 0
    settings["_map_exalt_pending"] = False
    current_text = item_text or ""
    previous_text = settings.get("_map_exalt_last_text") or ""
    if current_text and current_text == previous_text:
        failures = int(settings.get("_map_exalt_same_text_failures", 0) or 0) + 1
        settings["_map_exalt_same_text_failures"] = failures
        return failures
    _map_reset_exalt_fail_state(settings)
    return 0

def _map_apply_reroll_orb(orb_mode):
    if orb_mode == "chaos":
        apply_orb("Chaos Orb", ITEM_POS)
    else:
        apply_orb("Orb of Scouring", ITEM_POS)
        safe_wait(0.05)
        apply_orb("Orb of Alchemy", ITEM_POS)

def handle_map_craft_state_v2(mods, settings, item_text=""):
    forbidden = map_rules.active_forbidden(settings)
    summary_stats = parse_map_summary_stats(item_text)
    orb_mode = settings.get(
        "map_orb_mode",
        "alchemy" if settings.get("craft_logic") == "Rare (alchemy)" else "chaos"
    )

    exalt_failures = _map_register_exalt_result(settings, item_text)
    if exalt_failures >= 5:
        log_message(f"[MAP] Exalted failsafe: 5 ayni clipboard -> {orb_mode.title()} ile reroll.")
        _map_reset_exalt_fail_state(settings)
        _map_apply_reroll_orb(orb_mode)
        return "continue"

    forbidden_count = _count_template_matches(forbidden, mods)
    evaluation = map_rules.evaluate(forbidden_count, summary_stats, settings)
    profile_label = evaluation["profile_label"]

    if forbidden_count > 0:
        _map_reset_exalt_fail_state(settings)
        log_message(
            f"[MAP:{profile_label}] {forbidden_count} istenmeyen mod bulundu → reroll."
        )
        _map_apply_reroll_orb(orb_mode)
        return "continue"

    if evaluation["accepted"]:
        _map_reset_exalt_fail_state(settings)
        log_message(
            f"[MAP:{profile_label}] İstenmeyen mod yok; "
            "Quantity/Rarity/Pack şartları sağlandı → Dur."
        )
        return "done"

    failures = evaluation["threshold_failures"]
    log_message(
        f"[MAP:{profile_label}] Sayısal eşikler yetmedi: {', '.join(failures)}"
    )
    if settings.get("map_use_exalt"):
        candidate = find_map_exalt_candidate(mods, summary_stats, settings)
        if candidate:
            joined = " + ".join(candidate.get("mods", []))
            log_message(
                "[MAP] Use Exalted aktif → blacklist temiz ve tek Exalt ile "
                f"eşikler yakalanabilir: {joined}"
            )
            _map_note_exalt_attempt(settings, item_text)
            apply_orb("Exalted Orb", ITEM_POS)
            return "continue"

    _map_reset_exalt_fail_state(settings)
    _map_apply_reroll_orb(orb_mode)
    return "continue"

def _wait_for_map_item_change(before_text, predicate, operation, attempts=5):
    for attempt in range(1, attempts + 1):
        if stop_event.is_set():
            return ""
        safe_wait(0.08 if attempt == 1 else 0.12)
        current_text = capture_item_text_once()
        if (
            current_text
            and current_text != (before_text or "")
            and predicate(current_text)
        ):
            return current_text
    stop_event.set()
    raise CraftFatalError(f"[MAP BATCH] {operation} sonucu doğrulanamadı.")

def handle_map_alchemy_vaal_batch_item(item_text, settings):
    map_tier = map_rules.parse_map_tier(item_text)
    start_failures = map_rules.alchemy_vaal_start_failures(
        item_text,
        required_tier=16,
        allow_missing_tier=True,
    )
    if start_failures:
        log_message(f"[MAP BATCH] Slot atlandı: {', '.join(start_failures)}.")
        return "done"
    if map_tier is None:
        log_message(
            "[MAP BATCH] Tier satiri okunamadi; Maps sinifi ve rarity "
            "dogrulandigi icin devam ediliyor."
        )

    starting_rarity, _starting_mods = parse_item_text(item_text)
    if starting_rarity.casefold() == "normal":
        log_message("[MAP BATCH] Normal T16 doğrulandı → Orb of Alchemy.")
        apply_orb("Orb of Alchemy", ITEM_POS)
        if stop_event.is_set():
            return "stopped"
        alched_text = _wait_for_map_item_change(
            item_text,
            lambda text: parse_item_text(text)[0].casefold() == "rare",
            "Orb of Alchemy",
        )
    else:
        alched_text = item_text
        log_message("[MAP BATCH] Rare T16 doğrulandı → Alchemy atlandı.")

    log_message("[MAP BATCH] Rare map doğrulandı → Vaal Orb.")
    apply_orb("Vaal Orb", ITEM_POS)
    if stop_event.is_set():
        return "stopped"
    final_text = _wait_for_map_item_change(
        alched_text,
        map_rules.is_corrupted,
        "Vaal Orb",
    )

    _rarity, final_mods = parse_item_text(final_text)
    forbidden = map_rules.active_forbidden(settings)
    forbidden_count = _count_template_matches(forbidden, final_mods)
    summary_stats = parse_map_summary_stats(final_text)
    failures = map_rules.alchemy_vaal_final_failures(
        final_text,
        forbidden_count,
        summary_stats,
        settings,
    )
    if not failures:
        log_message(
            "[MAP BATCH] Corrupted map kabul edildi; blacklist temiz ve "
            "Quantity/Rarity/Pack şartları sağlandı."
        )
        return "done"

    log_message(
        f"[MAP BATCH] Map reddedildi: {', '.join(failures)} → stashe gönderiliyor."
    )
    if stop_event.is_set():
        return "stopped"
    if not ctrl_left_click_item(ITEM_POS[0], ITEM_POS[1]):
        if stop_event.is_set():
            return "stopped"
        stop_event.set()
        raise CraftFatalError("[MAP BATCH] Ctrl+sol tık uygulanamadı.")
    safe_wait(0.12)
    after_stash_text = capture_item_text_once()
    if after_stash_text == final_text:
        stop_event.set()
        raise CraftFatalError(
            "[MAP BATCH] Item stashe taşınmadı; stash dolu veya açık olmayabilir."
        )
    log_message("[MAP BATCH] Reddedilen map stashe taşındı.")
    currency_tab = get_orb_location("Currency Stash Tab")
    if not currency_tab:
        stop_event.set()
        raise CraftFatalError(
            "[MAP BATCH] Currency Stash Tab konumu ayarlanmamış."
        )
    if not item_left_click(currency_tab[0], currency_tab[1]):
        return "stopped"
    safe_wait(0.18)
    log_message("[MAP BATCH] Currency stash sekmesine geri dönüldü.")
    return "done"

def _socket_craft_stop(message):
    log_message(message)
    stop_event.set()
    stop_shift_spam()
    return "done"

def apply_socket_orb_with_shift_spam(orb_name, item_pos):
    global shift_spam_active, socket_shift_spam_orb

    if stop_event.is_set():
        stop_shift_spam()
        return False

    orb_loc = get_orb_location(orb_name)
    if not orb_loc:
        _socket_craft_stop(f"[SOCKET] {orb_name} konumu bulunamadi. Craft durduruldu.")
        return False

    if shift_spam_active and socket_shift_spam_orb != orb_name:
        stop_shift_spam()

    if not shift_spam_active:
        if not _recover_default_after_shift_stream(orb_name):
            return False
        if stop_event.is_set():
            return False
        if not _pick_orb_with_verify(orb_name, orb_loc):
            return False
        if stop_event.is_set():
            return False
        try:
            keyboard.press("shift")
        except Exception as exc:
            _socket_craft_stop(f"[SOCKET] Shift basili tutulamadi: {exc}")
            return False
        shift_spam_active = True
        socket_shift_spam_orb = orb_name
        safe_wait(0.005)
        if stop_event.is_set():
            stop_shift_spam()
            return False
        log_message(f"[SOCKET] {orb_name} secildi, Shift + sol tik spam basladi.")

    if stop_event.is_set():
        stop_shift_spam()
        return False
    if not _stream_click_item_with_verify(orb_name, item_pos):
        return False
    if stop_event.is_set():
        stop_shift_spam()
        return False

    record_currency_use(orb_name)
    return True

def handle_socket_craft_state(item_text, settings):
    state = parse_socket_state(item_text)
    if state["total_sockets"] <= 0:
        log_message("[SOCKET] Socket bilgisi okunamadi. Imlec item uzerinde olmayabilir.")
        return "continue"

    log_message(f"[SOCKET] {format_socket_state(state)}")

    target_sockets = int(settings.get("socket_target_sockets", 0) or 0)
    target_links = int(settings.get("socket_target_links", 0) or 0)
    target_colors = settings.get("socket_target_colors", {}) or {}
    target_red = int(target_colors.get("R", 0) or 0)
    target_green = int(target_colors.get("G", 0) or 0)
    target_blue = int(target_colors.get("B", 0) or 0)
    target_color_total = target_red + target_green + target_blue

    use_jeweller = bool(settings.get("socket_use_jeweller"))
    use_fusing = bool(settings.get("socket_use_fusing"))
    use_chromatic = bool(settings.get("socket_use_chromatic"))

    if target_sockets > 0 and state["total_sockets"] != target_sockets:
        if not use_jeweller:
            return _socket_craft_stop("[SOCKET] Socket hedefi tutmuyor ama Jeweller kapali. Craft durduruldu.")
        log_message(f"[SOCKET] {target_sockets} socket icin Jeweller's Orb.")
        if not apply_socket_orb_with_shift_spam("Jeweller's Orb", ITEM_POS) and stop_event.is_set():
            return "done"
        return "continue"

    if use_chromatic and target_color_total > 0:
        if state["total_sockets"] != target_color_total:
            return _socket_craft_stop("[SOCKET] Renk hedefi mevcut socket sayisiyla uyusmuyor. Craft durduruldu.")
        colors = state["colors"]
        if (
            colors.get("R", 0) != target_red
            or colors.get("G", 0) != target_green
            or colors.get("B", 0) != target_blue
        ):
            log_message(f"[SOCKET] R{target_red} G{target_green} B{target_blue} icin Chromatic Orb.")
            if not apply_socket_orb_with_shift_spam("Chromatic Orb", ITEM_POS) and stop_event.is_set():
                return "done"
            return "continue"

    if target_links > 0 and state["max_link"] != target_links:
        if state["total_sockets"] < target_links:
            return _socket_craft_stop("[SOCKET] Link hedefi mevcut socket sayisindan buyuk. Craft durduruldu.")
        if not use_fusing:
            return _socket_craft_stop("[SOCKET] Link hedefi tutmuyor ama Fusing kapali. Craft durduruldu.")
        log_message(f"[SOCKET] {target_links}-link icin Orb of Fusing.")
        if not apply_socket_orb_with_shift_spam("Orb of Fusing", ITEM_POS) and stop_event.is_set():
            return "done"
        return "continue"

    log_message("[SOCKET] Hedef tamamlandi.")
    stop_shift_spam()
    return "done"

def find_cluster_no_regal_two_match(mods, comb_data):
    matches = [
        pot
        for pot in _analyze_item_potential(mods, comb_data)
        if pot.get("match_count", 0) >= 2
    ]
    if not matches:
        return None
    return min(
        matches,
        key=lambda pot: (
            -int(pot.get("match_count", 0)),
            len(pot.get("junk_mods", [])),
            len(pot.get("missing_mods", [])),
            str(pot.get("comb_no", "")),
        ),
    )

def handle_cluster_no_regal_magic_state(mods, settings):
    global shift_spam_active, solo_regal_active, solo_regal_exalt

    solo_regal_active = False
    solo_regal_exalt = False
    comb_data = settings.get("comb_craft_data", {})
    matched = find_cluster_no_regal_two_match(mods, comb_data)
    if matched:
        log_message(
            f"[NO REGAL] Komb #{matched['comb_no']} icin "
            f"{matched['match_count']} hedef bulundu -> Craft tamamlandi."
        )
        stop_shift_spam()
        return "done"

    typed = mods_with_types(mods)
    affix_count = sum(1 for _, affix_type in typed if affix_type in ("prefix", "suffix"))
    has_open_slot = affix_count < 2
    has_target = any(
        pot.get("match_count", 0) >= 1
        for pot in _analyze_item_potential(mods, comb_data)
    )
    augment_enabled = settings.get("augment_mode", "Use if needed") != "Don't use"

    if has_target and has_open_slot and augment_enabled:
        log_message("[NO REGAL] 1 hedef + bos slot -> Augment.")
        apply_augmentation_with_failover(chain_craft=settings.get("chain_craft", False))
        safe_wait(get_delay_s())
        return "continue"

    if not shift_spam_active:
        log_message("[ShiftSpam] Baslatildi.")
    log_message("[NO REGAL] Ayni kombinasyondan 2 hedef yok -> Alteration devam.")
    apply_alteration_with_failover(chain_craft=settings.get("chain_craft", False))
    safe_wait(get_delay_s())
    return "continue"

def handle_magic_state(mods, settings):
    """
    CombCraft magic aşaması:
    - Solo Regal: tek bir mod bile solo_regal listesindeyse → augment mantığına bak → regal
    - 1P+1S varsa: hangi kombinasyonlara uyuyor → no_regal filtresi → uygun varsa regal
    - Hiçbiri değilse → alteration devam
    """
    global shift_spam_active, solo_regal_active, solo_regal_exalt

    if settings.get("cluster_no_regal_two_mods"):
        return handle_cluster_no_regal_magic_state(mods, settings)

    if settings.get("is_effect35"):
        solo_regal_active = False
        solo_regal_exalt = False
        return handle_effect35_magic_state(mods, settings)

    typed = mods_with_types(mods)
    p_count = sum(1 for _, t in typed if t == "prefix")
    s_count = sum(1 for _, t in typed if t == "suffix")
    has_open_slot = (p_count + s_count) < 2

    solo_regal_mods = settings.get("solo_regal_mods", [])
    no_regal_mods   = settings.get("no_regal_mods", [])
    comb_data       = settings.get("comb_craft_data", {})

    # === SOLO REGAL KONTROLÜ ===
    solo_hit = any(_mod_matches_any(m, solo_regal_mods) for m in mods if "(fractured)" not in m.lower())
    if solo_hit:
        # Tetikleyen mod annul_combs ile kesişiyor mu?
        annul_combs = settings.get("annul_combs", [])
        triggering_mods = [m for m in mods if _mod_matches_any(m, solo_regal_mods)]
        exalt_after_regal = any(_mod_matches_any(m, annul_combs) for m in triggering_mods)

        augment_mode_val = settings.get("augment_mode", "Use if needed")
        if augment_mode_val == "Always use" and has_open_slot:
            log_message("[MAGIC] Solo Regal + boş slot → Augment atılıyor, sonra item okunacak.")
            apply_augmentation_with_failover(chain_craft=settings.get("chain_craft", False))
            safe_wait(0.08)
            new_text = capture_item_text_once()
            if new_text:
                _, new_mods = parse_item_text(new_text)
                if find_stop_on_two_match_pair(new_mods, settings):
                    log_message("[GLOBAL] 2'li ozel kombinasyon bulundu, craft tamamlandi.")
                    stop_shift_spam()
                    return "done"
            log_message(f"[MAGIC] Solo Regal → Regal atılıyor. {'(Exalt sonrası gelecek)' if exalt_after_regal else '(Normal rare akışı)'}")
            solo_regal_active = True
            solo_regal_exalt = exalt_after_regal
            apply_orb("Regal Orb", ITEM_POS)
            return "continue"
        else:
            log_message(f"[MAGIC] Solo Regal → Regal atılıyor. {'(Exalt sonrası gelecek)' if exalt_after_regal else '(Normal rare akışı)'}")
            solo_regal_active = True
            solo_regal_exalt = exalt_after_regal
            apply_orb("Regal Orb", ITEM_POS)
            return "continue"

    # === 1P + 1S VARSA KOMBİNASYON KONTROLÜ ===
    if p_count >= 1 and s_count >= 1:
        pots = _analyze_item_potential(mods, comb_data)
        relevant = [p for p in pots if p["match_count"] >= len(mods)]

        if relevant:
            def comb_has_no_regal(pot):
                comb_key = pot["comb_no"]
                comb_targets = comb_data.get(str(comb_key), [])
                matched_targets = [t for t in comb_targets if t not in pot.get("missing_mods", [])]
                no_regal_normalized = [normalize_mod_text(nr) for nr in no_regal_mods]
                for t in matched_targets:
                    tn = normalize_mod_text(t)
                    if any(tn == nrn or (nrn and nrn in tn) or (tn and tn in nrn) for nrn in no_regal_normalized):
                        return True
                return False

            free_combs = [p for p in relevant if not comb_has_no_regal(p)]

            if free_combs:
                augment_mode_val = settings.get("augment_mode", "Use if needed")
                if augment_mode_val == "Always use" and has_open_slot:
                    log_message("[MAGIC] Uyumlu kombinasyon + boş slot → Augment → Regal.")
                    apply_augmentation_with_failover(chain_craft=settings.get("chain_craft", False))
                    return "continue"
                else:
                    comb_nos = [str(p["comb_no"]) for p in free_combs]
                    log_message(f"[MAGIC] Uyumlu kombinasyonlar: {', '.join(comb_nos)} → Regal atılıyor.")
                    apply_orb("Regal Orb", ITEM_POS)
                    return "continue"
            else:
                log_message("[MAGIC] Tüm uyumlu kombinasyonlar No-Regal listesinde → Alteration devam.")

    # === AUGMENT — ALWAYS USE: tek mod varken boş slot doldurul ===
    augment_mode_val = settings.get("augment_mode", "Use if needed")
    if augment_mode_val == "Always use" and has_open_slot:
        log_message("[MAGIC] Always use augment + boş slot → Augment atılıyor.")
        apply_augmentation_with_failover(chain_craft=settings.get("chain_craft", False))
        safe_wait(get_delay_s())
        return "continue"

    # === ALTERATION DEVAM ===
    if not shift_spam_active:
        log_message("[ShiftSpam] Başlatıldı.")
    apply_alteration_with_failover(chain_craft=settings.get("chain_craft", False))
    safe_wait(get_delay_s())
    return "continue"

# === STOP-ON-TWO NORMALIZE HELPER (sadece eşleşme için, prefix/suffix logic'e dokunmaz) ===
@functools.lru_cache(maxsize=8192)
def normalize_mod_text(raw):
    s = RE_NORMALIZE_PREFIX.sub("", raw or "").strip().lower()
    s = RE_NORMALIZE_NOTABLE.sub("", s)
    s = RE_NORMALIZE_SMALL_GRANT.sub("", s)
    s = RE_NORMALIZE_SMALL_HAVE.sub("", s)
    # Sondaki (N) minimum roll parantezini çıkar
    s = RE_TRAILING_ROLL.sub("", s).strip()
    return s.strip()

@functools.lru_cache(maxsize=8192)
def _prepare_match_template(template_entry):
    entry = (template_entry or "").strip()
    roll_req = None
    roll_m = RE_TRAILING_ROLL.search(entry)
    if roll_m:
        roll_req = int(roll_m.group(1))
        entry = entry[:roll_m.start()].strip()
    normalized = normalize_mod_text(entry)
    pattern = None
    if "#" in normalized:
        pattern = re.compile(re.escape(normalized).replace(r"\#", MATCH_WILDCARD_PATTERN))
    return normalized, roll_req, pattern

def _clear_comb_match_caches():
    _get_compiled_comb_data.cache_clear()
    _analyze_item_potential_cached.cache_clear()

def _mod_matches_any(mod_text, mod_list):
    item_mods_clean = [normalize_mod_text(mod_text)]
    for entry in mod_list:
        if isinstance(entry, str) and entry:
            if _match_normalized(entry, item_mods_clean):
                return True
    return False

@functools.lru_cache(maxsize=2048)
def _normalize_mod_tuple(mods_key):
    return tuple(normalize_mod_text(m) for m in mods_key)

def _normalized_mod_list(mods):
    return list(_normalize_mod_tuple(tuple(mods)))

@functools.lru_cache(maxsize=2048)
def _item_has_fractured_mod_cached(mods_key):
    return any("(fractured)" in (m or "").lower() for m in mods_key)

def item_has_fractured_mod(mods):
    return _item_has_fractured_mod_cached(tuple(mods))


def validate_cluster_fracture_mode(mods, settings):
    mode = settings.get("cluster_fracture_mode", "unfractured")
    fractured_mods = [m for m in mods if "(fractured)" in (m or "").lower()]
    if mode == "unfractured":
        return not fractured_mods
    if mode != "fractured":
        return True
    if not fractured_mods:
        return False
    target = settings.get("cluster_fractured_target", "")
    if not target:
        return True
    return any(_mod_matches_any(mod, [target]) for mod in fractured_mods)

def find_stop_on_two_match_pair(mods, settings):
    stop_pairs = settings.get("stop_on_two_match", [])
    if not stop_pairs or not mods or item_has_fractured_mod(mods):
        return None
    item_mods_clean = _normalized_mod_list(mods)
    for pair in stop_pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        if all(_match_normalized(p, item_mods_clean) for p in pair):
            return pair
    return None

def item_has_annul_combo(mods, annul_combs):
    if not annul_combs:
        return True
    item_mods_clean = _normalized_mod_list(mods)
    for entry in annul_combs:
        if isinstance(entry, str) and entry:
            if _match_normalized(entry, item_mods_clean):
                return True
    return False

def _match_normalized(template_entry, item_mods_normalized):
    """
    Template entry ile normalize edilmiş item modlarını karşılaştırır.
    Roll kontrolü için (N) parantezini normalize ÖNCE ham string'den çıkarır.
    """
    raw, roll_req, pat = _prepare_match_template(template_entry)

    if pat is not None:
        for im in item_mods_normalized:
            if pat.search(im):
                if roll_req is None:
                    return True
                num = _extract_first_numeric_value(im)
                if num is not None and num >= roll_req:
                    return True
        return False

    for im in item_mods_normalized:
        if raw in im:
            if roll_req is None:
                return True
            num = _extract_first_numeric_value(im)
            if num is not None and num >= roll_req:
                return True
    return False

def is_regular_base_jewel_text(item_text):
    low = (item_text or "").lower()
    item_class = next(
        (
            line.split(":", 1)[1].strip().lower()
            for line in low.splitlines()
            if line.strip().startswith("item class:")
        ),
        "",
    )
    return (
        item_class == "jewels"
        and "cluster jewel" not in low
        and "added small passive skills" not in low
    )

def _base_jewel_mod_matches_strict(mod_text, template_entry):
    normalized_mod = normalize_mod_text(mod_text)
    normalized_target, roll_req, pattern = _prepare_match_template(template_entry)
    if pattern is not None:
        matched = pattern.fullmatch(normalized_mod) is not None
    else:
        matched = normalized_mod == normalized_target
    if not matched:
        return False
    if roll_req is None:
        return True
    value = _extract_first_numeric_value(normalized_mod)
    return value is not None and value >= roll_req

def _base_jewel_record_matches(record, patterns):
    return any(
        _base_jewel_mod_matches_strict(mod, pattern)
        for mod in record.get("mods", [])
        for pattern in patterns
        if isinstance(pattern, str) and pattern.strip()
    )

def analyze_base_jewel(mods, settings, magic_item=False):
    crit_patterns = settings.get("base_jewel_crit_mods") or DEFAULT_BASE_JEWEL_CRIT_MODS
    life_patterns = settings.get("base_jewel_life_mods") or DEFAULT_BASE_JEWEL_LIFE_MODS
    no_regal = bool(settings.get("base_jewel_no_regal", False))
    crit_goal = max(0, int(settings.get("base_jewel_crit_count", 3)))
    life_goal = max(0, int(settings.get("base_jewel_life_count", 0)))
    records = base_jewel_affix_records(mods, magic_item=magic_item)
    crit_records = []
    life_records = []
    junk_records = []

    for record in records:
        if crit_goal > 0 and _base_jewel_record_matches(record, crit_patterns):
            crit_records.append(record)
        elif (life_goal > 0 or no_regal) and _base_jewel_record_matches(record, life_patterns):
            life_records.append(record)
        else:
            junk_records.append(record)

    prefix_count = sum(1 for record in records if record["type"] == "prefix")
    suffix_count = sum(1 for record in records if record["type"] == "suffix")
    unknown_count = len(records) - prefix_count - suffix_count
    crit_count = len(crit_records)
    life_count = len(life_records)
    missing_crit = max(0, crit_goal - crit_count)
    missing_life = max(0, life_goal - life_count)
    goal_met = (
        (crit_count >= 2 or (crit_count >= 1 and life_count >= 1))
        if no_regal
        else (missing_crit == 0 and missing_life == 0)
    )

    return {
        "records": records,
        "affix_count": len(records),
        "prefix_count": prefix_count,
        "suffix_count": suffix_count,
        "unknown_count": unknown_count,
        "crit_count": crit_count,
        "life_count": life_count,
        "target_count": min(crit_count, crit_goal) + min(life_count, life_goal),
        "crit_goal": crit_goal,
        "life_goal": life_goal,
        "missing_crit": missing_crit,
        "missing_life": missing_life,
        "junk_records": junk_records,
        "goal_met": goal_met,
        "no_regal": no_regal,
    }

def base_jewel_goal_reachable(summary):
    total_free = max(0, 4 - summary["affix_count"])
    missing_total = summary["missing_crit"] + summary["missing_life"]
    if missing_total > total_free:
        return False

    prefix_free = max(0, 2 - summary["prefix_count"])
    suffix_free = max(0, 2 - summary["suffix_count"])
    if summary["missing_life"] > prefix_free:
        return False

    prefix_after_life = max(0, prefix_free - summary["missing_life"])
    crit_capacity = prefix_after_life + suffix_free
    return summary["missing_crit"] <= crit_capacity

def _format_base_jewel_summary(summary):
    return (
        f"Crit={summary['crit_count']}/{summary['crit_goal']} "
        f"Life={summary['life_count']}/{summary['life_goal']} "
        f"Affix={summary['affix_count']}/4 "
        f"P={summary['prefix_count']} S={summary['suffix_count']} "
        f"Junk={len(summary['junk_records'])}"
    )

def base_jewel_state_key(rarity, mods):
    return (
        (rarity or "").strip().lower(),
        tuple(sorted(normalize_mod_text(mod) for mod in mods)),
    )

def handle_base_jewel_magic_state(mods, settings):
    global shift_spam_active
    summary = analyze_base_jewel(mods, settings, magic_item=True)
    log_message(f"[BASE JEWEL] {_format_base_jewel_summary(summary)}")
    if summary["goal_met"]:
        message = (
            "Regalsiz hedef tamamlandi: Double Crit veya Crit + Life."
            if summary["no_regal"]
            else "Hedef tamamlandi."
        )
        log_message(f"[BASE JEWEL] {message}")
        stop_shift_spam()
        return "done"

    if (
        summary["affix_count"] < 2
        and summary["target_count"] >= 1
        and settings.get("base_jewel_use_augment", True)
    ):
        log_message("[BASE JEWEL] Tek hedef modlu magic item -> Augment.")
        apply_augmentation_with_failover(chain_craft=settings.get("chain_craft", False))
        return "continue"

    regal_min = max(1, int(settings.get("base_jewel_regal_min", 2)))
    if (
        not summary["no_regal"]
        and summary["target_count"] >= regal_min
        and base_jewel_goal_reachable(summary)
    ):
        log_message("[BASE JEWEL] Yeterli hedef var ve hedef rare itemde ulasilabilir -> Regal.")
        stop_shift_spam()
        apply_orb("Regal Orb", ITEM_POS)
        return "continue"

    if not shift_spam_active:
        log_message("[ShiftSpam] Baslatildi.")
    log_message("[BASE JEWEL] Magic item yeterli hedef tasimiyor -> Alteration.")
    apply_alteration_with_failover(chain_craft=settings.get("chain_craft", False))
    return "continue"

def _scour_base_jewel():
    log_message("[BASE JEWEL] Hedef artik verimli sekilde ulasilabilir degil -> Scouring.")
    stop_shift_spam()
    apply_orb("Orb of Scouring", ITEM_POS)
    return "reset_to_magic"

def handle_base_jewel_rare_state(mods, settings):
    summary = analyze_base_jewel(mods, settings)
    log_message(f"[BASE JEWEL] {_format_base_jewel_summary(summary)}")
    if summary["goal_met"]:
        log_message("[BASE JEWEL] Hedef tamamlandi.")
        stop_shift_spam()
        return "done"

    regal_min = max(1, int(settings.get("base_jewel_regal_min", 2)))
    if summary["target_count"] < regal_min:
        return _scour_base_jewel()

    reachable = base_jewel_goal_reachable(summary)
    has_junk = bool(summary["junk_records"])
    if (
        reachable
        and summary["affix_count"] < 4
        and settings.get("base_jewel_use_exalt", True)
    ):
        log_message("[BASE JEWEL] Hedef icin bos affix var -> Exalted Orb.")
        stop_shift_spam()
        apply_orb("Exalted Orb", ITEM_POS)
        return "continue"

    if has_junk and settings.get("base_jewel_use_annul", True):
        reason = "hedef affix tipi dolu" if not reachable else "item 4 mod dolu"
        log_message(f"[BASE JEWEL] {reason}; junk mod silmek icin Annul.")
        stop_shift_spam()
        apply_orb("Orb of Annulment", ITEM_POS)
        return "continue"

    return _scour_base_jewel()

def handle_base_jewel_craft_state(rarity, mods, item_text, settings):
    low = (item_text or "").lower()
    if not is_regular_base_jewel_text(item_text):
        log_message("[BASE JEWEL] Cursor altindaki item normal base jewel degil. Craft durduruldu.")
        stop_event.set()
        stop_shift_spam()
        return "done"
    if "corrupted" in low or "mirrored" in low:
        log_message("[BASE JEWEL] Corrupted veya mirrored item craft edilemez. Craft durduruldu.")
        stop_event.set()
        stop_shift_spam()
        return "done"
    if item_has_fractured_mod(mods):
        log_message("[BASE JEWEL] Fractured jewel bu modda desteklenmiyor. Craft durduruldu.")
        stop_event.set()
        stop_shift_spam()
        return "done"

    if mods:
        log_message(f"--- {rarity.upper()} BASE JEWEL ---")
        for mod in mods:
            mod_type = classify_base_jewel_mod_type(mod)
            tag = mod_type[0].upper() if mod_type != "unknown" else "?"
            log_message(f"  [{tag}] {mod}")

    rarity_low = (rarity or "").lower()
    if rarity_low == "normal":
        log_message("[BASE JEWEL] Normal item -> Transmutation.")
        apply_orb("Orb of Transmutation", ITEM_POS)
        return "continue"
    if rarity_low == "magic":
        return handle_base_jewel_magic_state(mods, settings)
    if rarity_low == "rare":
        return handle_base_jewel_rare_state(mods, settings)

    log_message(f"[BASE JEWEL] Desteklenmeyen rarity: {rarity}")
    stop_event.set()
    stop_shift_spam()
    return "done"

@functools.lru_cache(maxsize=1)
def get_item_affix_catalog():
    return generic_item.load_catalog(ITEM_AFFIX_CATALOG_PATH)

def generic_item_state_key(rarity, mods):
    return (
        (rarity or "").strip().lower(),
        tuple(sorted(normalize_mod_text(mod) for mod in mods)),
    )

def _format_generic_item_summary(summary):
    return (
        f"Target={summary['matched_count']}/{summary['required_count']} "
        f"Affix={summary['affix_count']}/6 "
        f"P={summary['prefix_count']} S={summary['suffix_count']} "
        f"Junk={len(summary['junk_records'])}"
    )

def handle_generic_item_craft_state(rarity, mods, item_text, settings):
    base_name = settings["item_base"]
    influence = settings.get("item_influence", "None")
    valid, reason, actual_item_level = generic_item.validate_item(
        item_text,
        base_name,
        influence,
    )
    if not valid:
        log_message(f"[ITEM CRAFT] {reason} Craft durduruldu.")
        stop_event.set()
        stop_shift_spam()
        return "done"
    if item_has_fractured_mod(mods):
        log_message("[ITEM CRAFT] Fractured item bu modda desteklenmiyor. Craft durduruldu.")
        stop_event.set()
        stop_shift_spam()
        return "done"

    if settings.get("item_chance_to_unique", False):
        action, reason = generic_item.choose_chance_to_unique_action(rarity)
        log_message(f"[ITEM CHANCE] {reason}")
        if action == "done":
            stop_shift_spam()
            return "done"
        if action == "chance":
            stop_shift_spam()
            apply_orb("Orb of Chance", ITEM_POS)
            return "continue"
        if action == "scour":
            stop_shift_spam()
            apply_orb("Orb of Scouring", ITEM_POS)
            return "continue"
        stop_event.set()
        stop_shift_spam()
        return "done"

    catalog = get_item_affix_catalog()
    target_ids = list(settings.get("item_target_ids", []))
    summary = generic_item.analyze(
        catalog,
        base_name,
        influence,
        actual_item_level,
        mods,
        target_ids,
        settings.get("item_required_count", 1),
    )
    if len(summary["targets"]) != len(target_ids):
        log_message(
            "[ITEM CRAFT] Secili hedeflerden biri itemin gercek ilvl/base/influence "
            "havuzunda yok. Craft durduruldu."
        )
        stop_event.set()
        stop_shift_spam()
        return "done"

    if mods:
        log_message(f"--- {rarity.upper()} ITEM CRAFT ---")
        record_by_index = {
            index: record["type"]
            for record in summary["records"]
            for index in record["indices"]
        }
        for index, mod in enumerate(mods):
            mod_type = record_by_index.get(index, "unknown")
            tag = mod_type[0].upper() if mod_type != "unknown" else "?"
            log_message(f"  [{tag}] {mod}")

    log_message(f"[ITEM CRAFT] {_format_generic_item_summary(summary)}")
    action, reason = generic_item.choose_action(rarity, summary, settings)
    log_message(f"[ITEM CRAFT] {reason}")

    if action == "done":
        stop_shift_spam()
        return "done"
    if action == "transmute":
        stop_shift_spam()
        apply_orb("Orb of Transmutation", ITEM_POS)
        return "continue"
    if action == "augment":
        stop_shift_spam()
        apply_augmentation_with_failover(
            chain_craft=settings.get("chain_craft", False)
        )
        return "continue"
    if action == "alter":
        apply_alteration_with_failover(
            chain_craft=settings.get("chain_craft", False)
        )
        return "continue"
    if action == "regal":
        stop_shift_spam()
        apply_orb("Regal Orb", ITEM_POS)
        return "continue"
    if action == "exalt":
        stop_shift_spam()
        apply_orb("Exalted Orb", ITEM_POS)
        return "continue"
    if action == "annul":
        stop_shift_spam()
        apply_orb("Orb of Annulment", ITEM_POS)
        return "continue"
    if action == "scour":
        stop_shift_spam()
        apply_orb("Orb of Scouring", ITEM_POS)
        return "reset_to_magic"

    stop_event.set()
    stop_shift_spam()
    return "done"

def _count_template_matches(entries, mods):
    item_mods_normalized = _normalized_mod_list(mods)
    return sum(
        1
        for entry in entries
        if isinstance(entry, str) and entry and _match_normalized(entry, item_mods_normalized)
    )

def _comb_no_int(value, default=999999):
    try:
        return int(str(value))
    except Exception:
        return default

def _pot_priority_key(pot):
    return (_comb_no_int(pot.get("comb_no")), -int(pot.get("match_count", 0)), len(pot.get("junk_mods", [])), len(pot.get("missing_mods", [])))

def _sorted_potentials_by_priority(pots):
    return sorted(pots, key=_pot_priority_key)

def _no_annul_comb_set(settings):
    return {str(v).strip() for v in settings.get("no_annul_combs", []) if str(v).strip()}

def _pot_is_no_annul(pot, settings):
    return str(pot.get("comb_no")) in _no_annul_comb_set(settings)

def _pot_missing_types(pot):
    result = []
    for missing in pot.get("missing_mods", []):
        tag = RE_AFFIX_TAG.search(missing)
        if not tag:
            continue
        result.append("prefix" if tag.group(1) == "P" else "suffix")
    return result

def _pot_affix_state(pot, mods):
    typed = mods_with_types(mods)
    p_count = sum(1 for _, t in typed if t == "prefix")
    s_count = sum(1 for _, t in typed if t == "suffix")
    missing_types = _pot_missing_types(pot)
    open_types = set()
    if p_count < 2:
        open_types.add("prefix")
    if s_count < 2:
        open_types.add("suffix")
    preferred_missing_type = next((t for t in missing_types if t in open_types), (missing_types[0] if missing_types else "unknown"))
    has_open_slot = any(t in open_types for t in missing_types)
    has_matching_junk = any(
        "(fractured)" not in (m or "").lower()
        and classify_mod_type(m) in missing_types
        for m in pot.get("junk_mods", [])
    )
    return {
        "missing_type": preferred_missing_type,
        "missing_types": missing_types,
        "p_count": p_count,
        "s_count": s_count,
        "has_open_slot": has_open_slot,
        "has_matching_junk": has_matching_junk,
    }

@functools.lru_cache(maxsize=32)
def _get_compiled_comb_data(comb_key):
    compiled = []
    for comb_no, targets in comb_key:
        target_defs = []
        for raw_target in targets:
            content_match = RE_TARGET_CONTENT.search(raw_target)
            content = content_match.group(1).lower().replace("\\#", "#") if content_match else raw_target.lower()
            roll_match = RE_TRAILING_ROLL.search(content)
            min_roll = None
            if roll_match:
                min_roll = int(roll_match.group(1))
                content = content[:roll_match.start()].strip()
            pattern = re.compile(re.escape(content).replace(r"\#", MATCH_WILDCARD_PATTERN))
            spend_match = RE_TARGET_SPEND.search(raw_target)
            spend_tag = spend_match.group(1) if spend_match else None
            target_defs.append({
                "raw": raw_target,
                "pattern": pattern,
                "min_roll": min_roll,
                "spend_tag": spend_tag,
            })
        compiled.append((comb_no, tuple(target_defs)))
    return tuple(compiled)

@functools.lru_cache(maxsize=2048)
def _analyze_item_potential_cached(mods_key, comb_key):
    potentials = []
    compiled_combos = _get_compiled_comb_data(comb_key)
    mods = tuple(mods_key)
    mods_lower = tuple((mod, mod.lower()) for mod in mods)
    for comb_no, targets in compiled_combos:
        matching, remaining = [], list(mods)
        unmatched = list(targets)
        for mod, low in mods_lower:
            for target in list(unmatched):
                if target["pattern"].search(low):
                    min_roll = target["min_roll"]
                    if min_roll is not None:
                        num_value = _extract_first_numeric_value(low)
                        if num_value is None or num_value < min_roll:
                            continue
                    matching.append(mod)
                    if mod in remaining:
                        remaining.remove(mod)
                    unmatched.remove(target)
                    break
        if not matching:
            continue
        can_spend = bool(unmatched) and all(target.get("spend_tag") == "1" for target in unmatched)
        potentials.append(
            (
                comb_no,
                len(matching),
                tuple(target["raw"] for target in unmatched),
                tuple(remaining),
                not unmatched,
                can_spend,
            )
        )
    return tuple(potentials)

def _comb_cache_key(comb_data):
    return tuple((str(comb_no), tuple(targets)) for comb_no, targets in comb_data.items())

def _combo_target_pots(mods, settings):
    pots = _sorted_potentials_by_priority(_analyze_item_potential(mods, settings.get("comb_craft_data", {})))
    return [p for p in pots if p.get("match_count", 0) >= 2 and p.get("can_spend") and not p.get("is_perfect_match")]

def _select_best_combo_progress(mods, settings, pots=None):
    use_exalt = bool(settings.get("use_exalt", True))
    use_annul = bool(settings.get("use_annul", True))
    for pot in (pots if pots is not None else _combo_target_pots(mods, settings)):
        state = _pot_affix_state(pot, mods)
        if state["has_open_slot"] and use_exalt:
            if _pot_is_no_annul(pot, settings) and pot.get("match_count", 0) < 3:
                continue
            return "exalt", pot, state
        if pot.get("match_count", 0) < 3:
            continue
        if state["has_open_slot"]:
            continue
        if not state["has_matching_junk"]:
            continue
        if not use_annul:
            continue
        if _pot_is_no_annul(pot, settings):
            continue
        return "annul", pot, state
    return None, None, None

def _medium_single_target_exalt_pot(mods, settings, pots):
    """Allow a two-target cluster combo to use the fourth rare affix."""
    if int(settings.get("cluster_passive_count", 0) or 0) not in (4, 5):
        return None
    if not settings.get("use_exalt", True):
        return None
    for pot in pots:
        match_count = int(pot.get("match_count", 0))
        missing_mods = pot.get("missing_mods", [])
        target_count = match_count + len(missing_mods)
        if (
            target_count == 2
            and match_count == 1
            and len(missing_mods) == 1
            and pot.get("can_spend")
            and _pot_affix_state(pot, mods)["has_open_slot"]
        ):
            return pot
    return None


def find_small_stop_three_match(mods, settings):
    """Return a four-mod Small Cluster combo when exactly three targets match."""
    if settings.get("cluster_size") != "small":
        return None
    if not settings.get("cluster_small_stop_three"):
        return None

    candidates = []
    comb_data = settings.get("comb_craft_data", {})
    for pot in _analyze_item_potential(
        mods,
        comb_data,
    ):
        target_count = int(pot.get("match_count", 0)) + len(
            pot.get("missing_mods", [])
        )
        missing_targets = list(pot.get("missing_mods", []))
        if (
            target_count < 4
            or int(pot.get("match_count", 0)) != 3
            or len(missing_targets) != 1
        ):
            continue
        candidates.append(pot)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda pot: (
            -int(pot.get("match_count", 0)),
            len(pot.get("junk_mods", [])),
            _comb_no_int(pot.get("comb_no")),
        ),
    )[0]

def is_cluster_notable_mod(mod):
    return bool(re.search(r"\b1\s+Added\s+Passive\s+Skill\s+is\b", str(mod or ""), re.IGNORECASE))

def handle_comb_craft_state(mods, settings):
    typed = mods_with_types(mods)
    stop_pairs = settings.get("stop_on_two_match", [])

    if stop_pairs and not item_has_fractured_mod(mods):
        item_mods = [normalize_mod_text(m) for m in mods]
        for pair in stop_pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            if all(_match_normalized(p, item_mods) for p in pair):
                log_message("💎 [CombCraft] Özel 2'li kombinasyon tespit edildi → Craft tamamlandı.")
                return "done"

    pots = _analyze_item_potential(mods, settings.get("comb_craft_data", {}))
    notable_mods = [m for m in mods if is_cluster_notable_mod(m)]

    if any(p["is_perfect_match"] for p in pots):
        first = [p["comb_no"] for p in pots if p["is_perfect_match"]][0]
        log_message(f"[COMB] Hedef tamam: Komb #{first}")
        return "done"

    if len(notable_mods) >= 3:
        if settings["use_annul"]:
            annul_combs = settings.get("annul_combs", [])
            if item_has_annul_combo(mods, annul_combs):
                log_message("[COMB] Hedeflenmeyen 3+ notable var → Annul dene.")
                apply_orb("Orb of Annulment", ITEM_POS)
                return "continue"
            else:
                log_message("[COMB] Annul Combs eşleşmedi → Annul atlanıyor, Scouring.")
                apply_orb("Orb of Scouring", ITEM_POS)
                return "reset_to_magic"
        else:
            log_message("[COMB] Hedeflenmeyen 3+ notable var, Annul kapalı → Scouring.")
            apply_orb("Orb of Scouring", ITEM_POS)
            return "reset_to_magic"

    actionable = [p for p in pots if p["match_count"] == 2 and p["can_spend"]]
    if not actionable:
        medium_progress = _medium_single_target_exalt_pot(mods, settings, pots)
        if medium_progress:
            actionable = [medium_progress]
    if not actionable:
        log_message("[COMB] Değerli 2'li alt küme yok → Scouring")
        apply_orb("Orb of Scouring", ITEM_POS)
        return "reset_to_magic"

    chosen = actionable[0]

    # Effect35: 4 mod dolu, 2 hedef + 2 junk → direkt scour
    if settings.get("is_effect35") and len(mods) >= 4 and len(chosen["junk_mods"]) >= 2:
        log_message("[COMB] Effect35: 4 mod dolu, 2 hedef 2 junk → Scouring.")
        apply_orb("Orb of Scouring", ITEM_POS)
        return "reset_to_magic"

    # Effect35: 4 mod dolmadan önce exalt at
    if settings.get("is_effect35") and len(mods) < 4 and settings["use_exalt"]:
        log_message("[COMB] Effect35: 4 mod dolmadı → Exalt.")
        apply_orb("Exalted Orb", ITEM_POS)
        return "continue"

    missing_str = chosen["missing_mods"][0]
    tag = re.search(r"\[(P|S)\]", missing_str)
    missing_type = "prefix" if tag and tag.group(1) == "P" else "suffix"
    p_count = sum(1 for _, t in typed if t == "prefix")
    s_count = sum(1 for _, t in typed if t == "suffix")
    log_message(f"[COMB] Komb #{chosen['comb_no']} hedefleniyor. Eksik: {missing_type.upper()}")

    annul_combs = settings.get("annul_combs", [])

    if missing_type == "prefix":
        if p_count < 2 and settings["use_exalt"]:
            log_message("[COMB] Boş prefix için Exalt.")
            apply_orb("Exalted Orb", ITEM_POS)
        elif p_count >= 2 and settings["use_annul"]:
            if [
                m for m in chosen["junk_mods"]
                if "(fractured)" not in (m or "").lower()
                and classify_mod_type(m) == "prefix"
            ]:
                if item_has_annul_combo(mods, annul_combs):
                    log_message("[COMB] Prefix boşaltmak için Annul.")
                    apply_orb("Orb of Annulment", ITEM_POS)
                else:
                    log_message("[COMB] Annul Combs eşleşmedi → Annul atlanıyor, Scouring.")
                    apply_orb("Orb of Scouring", ITEM_POS)
                    return "reset_to_magic"
            else:
                log_message("[COMB] Tıkandı → Scouring.")
                apply_orb("Orb of Scouring", ITEM_POS)
                return "reset_to_magic"
        else:
            log_message("[COMB] İlerlenemiyor → Scouring.")
            apply_orb("Orb of Scouring", ITEM_POS)
            return "reset_to_magic"
    else:
        if s_count < 2 and settings["use_exalt"]:
            log_message("[COMB] Boş suffix için Exalt.")
            apply_orb("Exalted Orb", ITEM_POS)
        elif s_count >= 2 and settings["use_annul"]:
            if [
                m for m in chosen["junk_mods"]
                if "(fractured)" not in (m or "").lower()
                and classify_mod_type(m) == "suffix"
            ]:
                if item_has_annul_combo(mods, annul_combs):
                    log_message("[COMB] Suffix boşaltmak için Annul.")
                    apply_orb("Orb of Annulment", ITEM_POS)
                else:
                    log_message("[COMB] Annul Combs eşleşmedi → Annul atlanıyor, Scouring.")
                    apply_orb("Orb of Scouring", ITEM_POS)
                    return "reset_to_magic"
            else:
                log_message("[COMB] Tıkandı → Scouring.")
                apply_orb("Orb of Scouring", ITEM_POS)
                return "reset_to_magic"
        else:
            log_message("[COMB] İlerlenemiyor → Scouring.")
            apply_orb("Orb of Scouring", ITEM_POS)
            return "reset_to_magic"
    return "continue"

def _analyze_item_potential(mods, comb_data):
    started = time.perf_counter()
    try:
        cached = _analyze_item_potential_cached(tuple(mods), _comb_cache_key(comb_data))
        return [
            {
                "comb_no": comb_no,
                "match_count": match_count,
                "missing_mods": list(missing_mods),
                "junk_mods": list(junk_mods),
                "is_perfect_match": is_perfect_match,
                "can_spend": can_spend,
            }
            for comb_no, match_count, missing_mods, junk_mods, is_perfect_match, can_spend in cached
        ]
    finally:
        _perf_record("_analyze_item_potential", time.perf_counter() - started)

def _effect35_sort_key(pot):
    return (_comb_no_int(pot.get("comb_no")), -int(pot.get("match_count", 0)), len(pot.get("junk_mods", [])), len(pot.get("missing_mods", [])))

def _effect35_potentials(mods, settings, min_match=0):
    pots = _analyze_item_potential(mods, settings.get("comb_craft_data", {}))
    if min_match:
        pots = [p for p in pots if p.get("match_count", 0) >= min_match]
    return sorted(pots, key=_effect35_sort_key)

def _effect35_target_type(target_str):
    tag = RE_AFFIX_TAG.search(target_str or "")
    if not tag:
        return "unknown"
    return "prefix" if tag.group(1) == "P" else "suffix"

def _effect35_open_affix_types(mods):
    typed = mods_with_types(mods)
    p_count = sum(1 for _, t in typed if t == "prefix")
    s_count = sum(1 for _, t in typed if t == "suffix")
    open_types = set()
    if p_count < 2:
        open_types.add("prefix")
    if s_count < 2:
        open_types.add("suffix")
    return open_types, p_count, s_count

def _effect35_potential_has_open_slot(pot, mods):
    open_types, _, _ = _effect35_open_affix_types(mods)
    if not open_types:
        return False
    for missing in pot.get("missing_mods", []):
        if _effect35_target_type(missing) in open_types:
            return True
    return False

def _select_best_effect35_progress(mods, settings):
    use_exalt = bool(settings.get("use_exalt", True))
    use_annul = bool(settings.get("use_annul", True))
    skipped_no_annul = []
    for pot in _effect35_potentials(mods, settings, min_match=2):
        if pot.get("is_perfect_match"):
            continue
        if _effect35_potential_has_open_slot(pot, mods):
            if use_exalt:
                if _pot_is_no_annul(pot, settings) and pot.get("match_count", 0) < 3:
                    skipped_no_annul.append(str(pot.get("comb_no")))
                    continue
                return "exalt", pot, skipped_no_annul
            continue
        # A full four-affix item with two targets and two junk mods can only
        # progress by freeing a slot. Respect the template's Annul setting
        # instead of scouring a still-valuable 2/4 subset immediately.
        if pot.get("match_count", 0) < 2:
            continue
        if not any(
            "(fractured)" not in (junk or "").lower()
            for junk in pot.get("junk_mods", [])
        ):
            continue
        if not use_annul:
            continue
        if _pot_is_no_annul(pot, settings):
            skipped_no_annul.append(str(pot.get("comb_no")))
            continue
        return "annul", pot, skipped_no_annul
    return None, None, skipped_no_annul

def _effect35_scour_result(mods):
    apply_orb("Orb of Scouring", ITEM_POS)
    return "continue" if item_has_fractured_mod(mods) else "reset_to_magic"

def handle_effect35_magic_state(mods, settings):
    global shift_spam_active

    fractured = item_has_fractured_mod(mods)
    typed = mods_with_types(mods)
    affix_count = sum(1 for _, t in typed if t in ("prefix", "suffix"))
    has_open_slot = affix_count < 2

    def _effect35_stop_before_regal(current_mods, context_label):
        if fractured:
            return False
        if find_stop_on_two_match_pair(current_mods, settings):
            log_message(f"[{context_label}] stop_on_two_match yakalandi -> Craft tamamlandi.")
            return True
        return False

    if not fractured:
        solo_regal_mods = settings.get("solo_regal_mods", [])
        solo_hit = any(_mod_matches_any(m, solo_regal_mods) for m in mods)
        if solo_hit:
            if has_open_slot:
                log_message("[E35 MAGIC] Solo mod bulundu + bos slot -> Augment, sonra Regal.")
                apply_augmentation_with_failover(chain_craft=settings.get("chain_craft", False))
                safe_wait(0.08)
                new_text = capture_item_text_once()
                if not new_text:
                    return "continue"
                _, new_mods = parse_item_text(new_text)
                if _effect35_stop_before_regal(new_mods, "E35 SOLO"):
                    return "done"
                log_message("[E35 MAGIC] Solo mod yolu -> Regal.")
                apply_orb("Regal Orb", ITEM_POS)
                return "continue"
            if _effect35_stop_before_regal(mods, "E35 SOLO"):
                return "done"
            log_message("[E35 MAGIC] Solo mod yolu -> Regal.")
            apply_orb("Regal Orb", ITEM_POS)
            return "continue"

    subset_pots = _effect35_potentials(mods, settings, min_match=2)
    if subset_pots:
        if _effect35_stop_before_regal(mods, "E35 MAGIC"):
            return "done"
        chosen = subset_pots[0]
        log_message(f"[E35 MAGIC] Komb #{chosen['comb_no']} icin 2/4 alt kume bulundu -> Regal.")
        apply_orb("Regal Orb", ITEM_POS)
        return "continue"

    augment_mode_val = settings.get("augment_mode", "Use if needed")
    if has_open_slot and augment_mode_val == "Always use":
        log_message("[E35 MAGIC] Always use augment + bos slot -> Augment atiliyor.")
        apply_augmentation_with_failover(chain_craft=settings.get("chain_craft", False))
        safe_wait(get_delay_s())
        return "continue"

    if not shift_spam_active:
        log_message("[ShiftSpam] Baslatildi.")
    apply_alteration_with_failover(chain_craft=settings.get("chain_craft", False))
    safe_wait(get_delay_s())
    return "continue"

def handle_effect35_rare_state(mods, settings):
    pots = _effect35_potentials(mods, settings, min_match=1)
    perfect = next((p for p in pots if p.get("is_perfect_match")), None)
    if perfect:
        log_message(f"[E35 RARE] Hedef tamam: Komb #{perfect['comb_no']}")
        return "done"

    next_action, chosen_pot, skipped_no_annul = _select_best_effect35_progress(mods, settings)
    for comb_no in skipped_no_annul:
        log_message(f"[E35 RARE] Komb #{comb_no} hedeflenebilirdi fakat Annul izni yok. Diger kombinasyonlara bakiliyor.")
    if next_action == "exalt" and chosen_pot:
        log_message(f"[E35 RARE] Komb #{chosen_pot['comb_no']} icin bos affix var -> Exalt.")
        apply_orb("Exalted Orb", ITEM_POS)
        return "continue"

    if next_action == "annul" and chosen_pot:
        match_count = int(chosen_pot.get("match_count", 0))
        log_message(
            f"[E35 RARE] Komb #{chosen_pot['comb_no']} icin "
            f"{match_count}/4 alt kume var, exalt yeri yok -> Annul."
        )
        apply_orb("Orb of Annulment", ITEM_POS)
        return "continue"

    log_message("[E35 RARE] Yeterli 2/4 veya 3/4 alt kume kalmadi -> Scouring.")
    return _effect35_scour_result(mods)

solo_regal_active = False   # solo regal atıldı — rare'e gelince özel davran
solo_regal_exalt  = False   # tetikleyen mod annul_combs'ta → exalt yap

def _is_subset_of_any_comb(mods, comb_data):
    """2 modun herhangi bir kombinasyonun alt kümesi olup olmadığını kontrol eder."""
    pots = _analyze_item_potential(mods, comb_data)
    return any(p["match_count"] >= 2 for p in pots)

def handle_rare_state(mods, settings):
    global solo_regal_active, solo_regal_exalt

    if settings.get("is_effect35"):
        solo_regal_active = False
        solo_regal_exalt = False
        return handle_effect35_rare_state(mods, settings)

    if solo_regal_active:
        solo_regal_active = False
        do_exalt = solo_regal_exalt
        solo_regal_exalt = False
        comb_data = settings.get("comb_craft_data", {})

        if do_exalt:
            # Tetikleyen mod annul_combs'taydı → exalt at
            if not settings.get("use_exalt", True):
                log_message("[SOLO REGAL RARE] Exalt kapalı → Scour.")
                apply_orb("Orb of Scouring", ITEM_POS)
                return "reset_to_magic"

            log_message("[SOLO REGAL RARE] Exalt atılıyor.")
            apply_orb("Exalted Orb", ITEM_POS)

            safe_wait(0.1)
            new_text = capture_item_text_once()
            if not new_text:
                return "continue"

            _, new_mods = parse_item_text(new_text)

            if _is_subset_of_any_comb(new_mods, comb_data):
                log_message("[SOLO REGAL RARE] Exalt sonrası comb eşleşti → CombCraft.")
                return handle_comb_craft_state(new_mods, settings)
            else:
                log_message("[SOLO REGAL RARE] Exalt sonrası comb eşleşmedi → Scour.")
                apply_orb("Orb of Scouring", ITEM_POS)
                return "reset_to_magic"
        else:
            # Tetikleyen mod annul_combs'ta değil → normal rare akışı
            log_message("[SOLO REGAL RARE] Annul_combs kesişimi yok → Normal CombCraft.")
            return handle_comb_craft_state(mods, settings)

    return handle_comb_craft_state(mods, settings)

# ================ HOTKEYS & THREAD START ================
stop_event = threading.Event()
LOCK = threading.Lock()
craft_thread = None
ITEM_POS = None

def _hotkeys_enabled_in_current_view():
    try:
        mode = app_mode.get()
    except Exception:
        mode = "cluster"
    if mode == "map":
        try:
            return not bool(map_affix_visible[0])
        except Exception:
            return True
    if mode == "item":
        try:
            return not bool(item_mod_pool_visible[0])
        except Exception:
            return True
    try:
        return current_mode == "normal"
    except Exception:
        return True

def start_craft_hotkey():
    if not _hotkeys_enabled_in_current_view():
        return
    if craft_thread and craft_thread.is_alive():
        log_message("[HOTKEY] Craft zaten çalışıyor.")
        return
    start_craft()

def stop_craft_hotkey():
    if not _hotkeys_enabled_in_current_view():
        return
    stop_event.set()
    stop_shift_spam()
    try:
        keyboard.release("ctrl")
    except Exception:
        pass
    try:
        pyautogui.mouseUp(button="left")
        pyautogui.mouseUp(button="right")
    except Exception:
        pass
    log_message("[CRAFT] STOP komutu alındı.")

def start_hotkey_listener():
    start_key = settings_cfg.get("Hotkeys", "start", fallback="F4")
    stop_key = settings_cfg.get("Hotkeys", "stop", fallback="F5")
    log_message(f"[HOTKEY] Start={start_key} Stop={stop_key}")
    try:
        keyboard.unhook_all_hotkeys()
    except Exception:
        pass
    keyboard.add_hotkey(start_key, start_craft_hotkey, suppress=False)
    keyboard.add_hotkey(stop_key, stop_craft_hotkey, suppress=False)

def start_craft():
    global craft_thread, ITEM_POS, comb_craft_data, stop_on_two_match_config, annul_combs_config
    global solo_regal_mods_config, no_regal_mods_config, no_annul_combs_config
    global RUNTIME_SAFE_MODE, chain_backup_slot_warning_shown
    with LOCK:
        if craft_thread and craft_thread.is_alive():
            return
        try:
            _clear_comb_match_caches()
            mode = app_mode.get()
            is_map = mode == "map"
            is_socket = mode == "socket"
            is_base_jewel = mode == "base_jewel"
            is_item = mode == "item"
            is_voyage = mode == "voyage"
            is_auto_flask = mode == "auto_flask"

            def _parse_optional_nonnegative(raw_value, label):
                raw = (raw_value or "").strip()
                if not raw:
                    return 0
                try:
                    value = int(raw)
                except ValueError:
                    gui_error(f"{label} sayi olmali.")
                    raise
                if value < 0:
                    gui_error(f"{label} negatif olamaz.")
                    raise ValueError(label)
                return value

            if is_auto_flask:
                try:
                    life_threshold = int(auto_flask_life_threshold_var.get().strip())
                    mana_threshold = int(auto_flask_mana_threshold_var.get().strip())
                except (ValueError, AttributeError):
                    gui_error("Life ve Mana esikleri tam sayi olmali.")
                    return
                life_enabled = bool(auto_flask_life_enabled_var.get())
                mana_enabled = bool(auto_flask_mana_enabled_var.get())
                if not life_enabled and not mana_enabled:
                    gui_error("Auto Flask icin Life veya Mana'dan en az birini ac.")
                    return
                if not 1 <= life_threshold <= 99 or not 1 <= mana_threshold <= 99:
                    gui_error("Auto Flask esikleri 1 ile 99 arasinda olmali.")
                    return
                life_key = auto_flask_life_key_var.get().strip()
                mana_key = auto_flask_mana_key_var.get().strip()
                if life_enabled and life_key not in {"1", "2", "3", "4", "5"}:
                    gui_error("Life flask tusu 1-5 arasinda olmali.")
                    return
                if mana_enabled and mana_key not in {"1", "2", "3", "4", "5"}:
                    gui_error("Mana flask tusu 1-5 arasinda olmali.")
                    return
                if life_enabled and mana_enabled and life_key == mana_key:
                    gui_error("Life ve Mana flasklari farkli tuslarda olmali.")
                    return
                snapshot = {
                    "craft_logic": "auto_flask",
                    "auto_flask_life_enabled": life_enabled,
                    "auto_flask_life_threshold": life_threshold,
                    "auto_flask_life_key": life_key,
                    "auto_flask_mana_enabled": mana_enabled,
                    "auto_flask_mana_threshold": mana_threshold,
                    "auto_flask_mana_key": mana_key,
                    "chain_craft": False,
                    "comb_craft": False,
                    "safe_mode": False,
                }
                if not settings_cfg.has_section("AutoFlask"):
                    settings_cfg.add_section("AutoFlask")
                settings_cfg.set("AutoFlask", "life_enabled", str(life_enabled))
                settings_cfg.set("AutoFlask", "life_threshold", str(life_threshold))
                settings_cfg.set("AutoFlask", "life_key", life_key)
                settings_cfg.set("AutoFlask", "mana_enabled", str(mana_enabled))
                settings_cfg.set("AutoFlask", "mana_threshold", str(mana_threshold))
                settings_cfg.set("AutoFlask", "mana_key", mana_key)
                save_settings_now()
            elif is_voyage:
                chart_tl = _voyage_point_setting("chart_grid_tl")
                chart_br = _voyage_point_setting("chart_grid_br")
                board_tl = _voyage_point_setting("board_grid_tl")
                board_br = _voyage_point_setting("board_grid_br")
                if chart_tl and chart_br and (
                    chart_tl[0] >= chart_br[0]
                    or chart_tl[1] >= chart_br[1]
                ):
                    gui_error("Chart TL noktasi, Chart BR noktasinin sol-ustunde olmali.")
                    return
                if board_tl and board_br and (
                    board_tl[0] >= board_br[0]
                    or board_tl[1] >= board_br[1]
                ):
                    gui_error("Board TL noktasi, Board BR noktasinin sol-ustunde olmali.")
                    return
                snapshot = {
                    "craft_logic": "voyage",
                    "voyage_chart_tl": chart_tl,
                    "voyage_chart_br": chart_br,
                    "voyage_board_tl": board_tl,
                    "voyage_board_br": board_br,
                    "voyage_auto_place": voyage_auto_place_var.get(),
                    "chain_craft": False,
                    "comb_craft": False,
                    "safe_mode": False,
                }
            elif is_map:
                try:
                    qthresh = int(map_quantity_thresh.get().strip()) if map_quantity_thresh.get().strip() else None
                    rthresh = int(map_rarity_thresh.get().strip()) if map_rarity_thresh.get().strip() else None
                    psthresh = int(map_pack_size_thresh.get().strip()) if map_pack_size_thresh.get().strip() else None
                    if any(
                        value is not None and value < 0
                        for value in (qthresh, rthresh, psthresh)
                    ):
                        raise ValueError
                except ValueError:
                    gui_error("Quant, Rarity ve Pack alanları boş veya negatif olmayan sayı olmalı.")
                    return
                map_mode = {
                    "Rare (alchemy)": "alchemy",
                    "Alchemy + Vaal": "alchemy_vaal",
                }.get(craft_logic.get(), "chaos")
                if map_mode == "alchemy_vaal":
                    missing_orbs = [
                        orb_name
                        for orb_name in (
                            "Orb of Alchemy",
                            "Vaal Orb",
                            "Currency Stash Tab",
                        )
                        if not get_orb_location(orb_name)
                    ]
                    if missing_orbs:
                        gui_error(
                            "Alchemy + Vaal icin Orb Locations ayarla: "
                            + ", ".join(missing_orbs)
                        )
                        return
                snapshot = {
                    "craft_logic": "map",
                    "map_orb_mode": map_mode,
                    "map_profile": (
                        map_rules.PROFILE_NORMAL
                        if map_mode == "alchemy_vaal"
                        else map_rules.normalize_profile(map_profile_var.get())
                    ),
                    "map_normal_forbidden": list(map_normal_forbidden),
                    "map_memory_forbidden": list(map_memory_forbidden),
                    "map_quantity_thresh": qthresh,
                    "map_rarity_thresh": rthresh,
                    "map_pack_size_thresh": psthresh,
                    "map_use_exalt": (
                        False if map_mode == "alchemy_vaal" else map_use_exalt.get()
                    ),
                    "comb_craft": False,
                    "safe_mode": False,
                }
                snapshot["chain_craft"] = chain_craft.get()
                snapshot["chain_count"] = int(chain_count_var.get() or 1)
                if snapshot["chain_craft"]:
                    slots = calculate_inventory_slots()
                    if not slots:
                        gui_error("Chain Craft iÃ§in Inventory 1st Slot ve Last Slot ayarla (Settings â†’ Orb Locations).")
                        return
                    snapshot["inventory_slots"] = slots
                else:
                    ITEM_POS = pyautogui.position()
                if map_mode == "alchemy_vaal":
                    log_message(
                        "[MAP BATCH] Alchemy + Vaal modu: Normal T16 maplere önce "
                        "Alchemy, Rare T16 maplere direkt Vaal uygulanır; reddedilenler "
                        "açık stashe Ctrl+sol tık ile gönderilir."
                    )
            elif is_socket:
                try:
                    target_sockets = _parse_optional_nonnegative(socket_target_sockets_var.get(), "Target sockets")
                    target_links = _parse_optional_nonnegative(socket_target_links_var.get(), "Target links")
                    target_red = _parse_optional_nonnegative(socket_target_red_var.get(), "Red target")
                    target_green = _parse_optional_nonnegative(socket_target_green_var.get(), "Green target")
                    target_blue = _parse_optional_nonnegative(socket_target_blue_var.get(), "Blue target")
                except ValueError:
                    return

                use_jeweller_socket = socket_use_jeweller_var.get()
                use_fusing_socket = socket_use_fusing_var.get()
                use_chromatic_socket = socket_use_chromatic_var.get()
                target_color_total = target_red + target_green + target_blue

                if not any((use_jeweller_socket, use_fusing_socket, use_chromatic_socket)):
                    gui_error("Socket modunda en az bir hedef acik olmali.")
                    return

                if use_chromatic_socket and target_color_total <= 0:
                    gui_error("Chromatic icin en az bir renk hedefi gir.")
                    return

                if use_jeweller_socket and target_sockets <= 0:
                    if target_links > 0:
                        target_sockets = max(target_sockets, target_links)
                    elif target_color_total > 0:
                        target_sockets = target_color_total
                    else:
                        gui_error("Jeweller icin target sockets gir.")
                        return

                if use_chromatic_socket and target_sockets <= 0:
                    target_sockets = target_color_total

                if target_sockets > 6 or target_links > 6 or target_color_total > 6:
                    gui_error("Socket, link ve toplam renk hedefi 6'dan buyuk olamaz.")
                    return

                if target_links > 0 and target_sockets > 0 and target_links > target_sockets:
                    gui_error("Target links, target sockets'ten buyuk olamaz.")
                    return

                if use_chromatic_socket and target_sockets != target_color_total:
                    gui_error("Chromatic hedefinde R+G+B toplami target sockets ile ayni olmali.")
                    return

                snapshot = {
                    "craft_logic": "socket",
                    "socket_target_sockets": target_sockets,
                    "socket_target_links": target_links,
                    "socket_target_colors": {
                        "R": target_red,
                        "G": target_green,
                        "B": target_blue,
                    },
                    "socket_use_jeweller": use_jeweller_socket,
                    "socket_use_fusing": use_fusing_socket,
                    "socket_use_chromatic": use_chromatic_socket,
                    "comb_craft": False,
                    "chain_craft": False,
                    "safe_mode": False,
                }
                ITEM_POS = pyautogui.position()
            elif is_item:
                catalog = get_item_affix_catalog()
                base_name = item_base_var.get().strip()
                influence = item_influence_var.get().strip() or "None"
                chance_to_unique = item_chance_to_unique_var.get()
                base = generic_item.find_base(catalog, base_name)
                if not base:
                    gui_error("Gecerli bir item base sec.")
                    return
                if influence != "None" and influence not in base.get("influences", {}):
                    gui_error(f"{base_name} base'i {influence} influence alamiyor.")
                    return
                try:
                    item_level = int(item_level_var.get().strip())
                    required_count = int(item_required_count_var.get().strip())
                except (ValueError, AttributeError):
                    gui_error("Item Level ve gerekli hedef sayisi tam sayi olmali.")
                    return
                if item_level < 1 or item_level > 100:
                    gui_error("Item Level 1 ile 100 arasinda olmali.")
                    return
                if chance_to_unique and not get_orb_location("Orb of Chance"):
                    gui_error(
                        "Chance + Scour modu icin Settings > Orb Locations ekraninda "
                        "Orb of Chance konumunu ayarla."
                    )
                    return
                if chance_to_unique and not get_orb_location("Orb of Scouring"):
                    gui_error(
                        "Chance + Scour modu icin Settings > Orb Locations ekraninda "
                        "Orb of Scouring konumunu ayarla."
                    )
                    return
                if not chance_to_unique and not item_target_ids:
                    gui_error("Item Craft icin en az bir hedef mod sec.")
                    return
                eligible = generic_item.eligible_mods(
                    catalog,
                    base_name,
                    influence,
                    item_level,
                )
                eligible_by_id = {mod["id"]: mod for mod in eligible}
                selected_targets = [
                    eligible_by_id[target_id]
                    for target_id in item_target_ids
                    if target_id in eligible_by_id
                ]
                if not chance_to_unique and len(selected_targets) != len(item_target_ids):
                    gui_error(
                        "Secili hedeflerden biri mevcut base/influence/ilvl havuzunda yok. "
                        "Mod havuzunu yenileyip hedefi tekrar sec."
                    )
                    return
                target_group_capacity = len(
                    {
                        (target["type"], target.get("group"))
                        for target in selected_targets
                    }
                )
                if (
                    not chance_to_unique
                    and (
                        required_count < 1
                        or required_count > len(selected_targets)
                        or required_count > target_group_capacity
                    )
                ):
                    gui_error(
                        "Gerekli hedef sayisi secili modlardan ve birlikte gelebilen "
                        "mod ailelerinden fazla olamaz."
                    )
                    return

                snapshot = {
                    "craft_logic": "generic_item",
                    "item_base": base_name,
                    "item_influence": influence,
                    "item_level": item_level,
                    "item_target_ids": list(item_target_ids),
                    "item_required_count": required_count,
                    "item_use_augment": item_use_augment_var.get(),
                    "item_use_regal": item_use_regal_var.get(),
                    "item_use_exalt": item_use_exalt_var.get(),
                    "item_use_annul": item_use_annul_var.get(),
                    "item_chance_to_unique": chance_to_unique,
                    "comb_craft": False,
                    "chain_craft": chain_craft.get(),
                    "chain_count": int(chain_count_var.get() or 1),
                    "safe_mode": False,
                }
                if snapshot["chain_craft"]:
                    slots = calculate_inventory_slots()
                    if not slots:
                        gui_error("Chain Craft icin Inventory 1st Slot ve Last Slot ayarla.")
                        return
                    snapshot["inventory_slots"] = slots
                else:
                    ITEM_POS = pyautogui.position()
            elif is_base_jewel:
                try:
                    crit_count = int(base_jewel_crit_count_var.get().strip())
                    regal_min = int(base_jewel_regal_min_var.get().strip())
                except (ValueError, AttributeError):
                    gui_error("Base Jewel hedef sayilari tam sayi olmali.")
                    return
                life_count = 1 if base_jewel_require_life_var.get() else 0
                no_regal = base_jewel_no_regal_var.get()
                if no_regal:
                    crit_count = 2
                    life_count = 1
                total_goal = crit_count + life_count
                if crit_count < 0 or total_goal < 1 or total_goal > 4:
                    gui_error("Base Jewel toplam hedef sayisi 1 ile 4 arasinda olmali.")
                    return
                if regal_min < 1 or regal_min > 2 or regal_min > total_goal:
                    gui_error("Base Jewel Regal esigi 1-2 arasinda ve toplam hedeften buyuk olmamali.")
                    return
                crit_patterns = get_base_jewel_crit_patterns()
                if crit_count and not crit_patterns:
                    gui_error("En az bir Crit Multiplier hedef modu gir.")
                    return

                snapshot = {
                    "craft_logic": "base_jewel",
                    "base_jewel_crit_count": crit_count,
                    "base_jewel_life_count": life_count,
                    "base_jewel_regal_min": regal_min,
                    "base_jewel_no_regal": no_regal,
                    "base_jewel_use_augment": base_jewel_use_augment_var.get(),
                    "base_jewel_use_exalt": base_jewel_use_exalt_var.get(),
                    "base_jewel_use_annul": base_jewel_use_annul_var.get(),
                    "base_jewel_crit_mods": crit_patterns,
                    "base_jewel_life_mods": list(DEFAULT_BASE_JEWEL_LIFE_MODS),
                    "comb_craft": False,
                    "chain_craft": chain_craft.get(),
                    "chain_count": int(chain_count_var.get() or 1),
                    "safe_mode": False,
                }
                if snapshot["chain_craft"]:
                    slots = calculate_inventory_slots()
                    if not slots:
                        gui_error("Chain Craft icin Inventory 1st Slot ve Last Slot ayarla.")
                        return
                    snapshot["inventory_slots"] = slots
                else:
                    ITEM_POS = pyautogui.position()
            else:
                if not comb_craft_data:
                    if market_cluster_template_active:
                        gui_error(
                            "Secili fiyat filtresinde kombinasyon yok. "
                            "Daha dusuk bir Saved min filtresi sec."
                        )
                    else:
                        gui_error("Cluster craft icin en az bir kombinasyon gerekli.")
                    return
                snapshot = {
                    "craft_logic": craft_logic.get(),
                    "augment_mode": augment_mode.get(),
                    "cluster_size": cluster_size_var.get(),
                    "cluster_fracture_mode": cluster_fracture_mode_var.get(),
                    "cluster_fractured_target": cluster_fractured_target_var.get(),
                    "cluster_no_regal_two_mods": cluster_no_regal_two_var.get(),
                    "cluster_small_stop_three": (
                        cluster_size_var.get() == "small"
                        and cluster_small_stop_three_var.get()
                    ),
                    "use_exalt": use_exalt.get(),
                    "use_annul": use_annul.get(),
                    "comb_craft": True,
                    "chain_craft": chain_craft.get(),
                    "chain_count": int(chain_count_var.get() or 1),
                    "comb_craft_data": comb_craft_data,
                    "cluster_passive_count": int(
                        template_cluster_meta.get("passive_count", 0) or 0
                    ),
                    "stop_on_two_match": stop_on_two_match_config,
                    "annul_combs": annul_combs_config,
                    "no_annul_combs": no_annul_combs_config,
                    "solo_regal_mods": solo_regal_mods_config,
                    "no_regal_mods": no_regal_mods_config,
                    "is_effect35": is_effect35_template,
                    "safe_mode": False,
                }
                if snapshot["chain_craft"]:
                    slots = calculate_inventory_slots()
                    if not slots:
                        gui_error("Chain Craft için Inventory 1st Slot ve Last Slot ayarla (Settings → Orb Locations).")
                        return
                    if not has_backup_orb_slot("Orb of Alteration") or not has_backup_orb_slot("Orb of Augmentation"):
                        if not chain_backup_slot_warning_shown:
                            gui_warn("Chain Craft için Settings → Orb Locations içinde Alteration ve Augmentation yedek slotları tanımlaman önerilir. Tanımlı değilse craft ana slotlarla devam eder.")
                            chain_backup_slot_warning_shown = True
                            return
                    snapshot["inventory_slots"] = slots
                else:
                    ITEM_POS = pyautogui.position()
        except Exception as e:
            gui_error(f"Ayarlar okunamadı: {e}")
            return
        snapshot["safe_mode"] = False
        snapshot["post_craft_action"] = (
            POST_ACTION_NONE
            if is_auto_flask
            else normalize_post_action(post_craft_action_var.get())
        )
        RUNTIME_SAFE_MODE = False
        reset_currency_usage_tracking()
        log_path = start_session_log()
        log_message(f"[LOG] Session log: {os.path.basename(log_path)}")
        mode_label = (
            "Auto Flask"
            if is_auto_flask
            else (
                "Voyage"
                if is_voyage
                else (
                    "Map"
                    if is_map
                    else (
                        "Socket"
                        if is_socket
                        else (
                            "Item Chain"
                            if is_item and snapshot.get("chain_craft")
                            else (
                                "Item"
                                if is_item
                                else (
                                    "Base Jewel Chain"
                                    if is_base_jewel and snapshot.get("chain_craft")
                                    else (
                                        "Base Jewel"
                                        if is_base_jewel
                                        else ("Chain" if snapshot.get("chain_craft") else "Single")
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
        log_message(f"[CRAFT] Başlatıldı. Mod: {mode_label}")
        engine_label = "Fast"
        log_message(f"[CRAFT] Engine: {engine_label}")
        stop_event.clear()
        craft_thread = threading.Thread(target=craft_thread_loop, args=(snapshot,), daemon=True)
        craft_thread.start()

# ================ MAIN CRAFT LOOP ================
def craft_thread_loop(settings):
    global shift_spam_active
    global ITEM_POS

    if settings.get("craft_logic") == "voyage":
        try:
            run_voyage_craft(settings)
        except Exception as exc:
            log_message(f"[VOYAGE] Beklenmeyen hata: {exc}\n{traceback.format_exc()}")
        finally:
            try:
                pyautogui.mouseUp(button="left")
                pyautogui.mouseUp(button="right")
                keyboard.release("ctrl")
            except Exception:
                pass
            try:
                root.after(0, _voyage_restore_window)
            except Exception:
                pass
            log_message("[CRAFT] Dongu durduruldu.")
            stop_session_log()
        return

    def get_item_info():
        """
        Adamın GetItemInfo birebir:
        cb='' → ClipboardClear → 3x (Ctrl+C → cb boşken 3x [Sleep(10)+ClipboardGetItemData]) → length>100: break → Sleep(50) → ClipboardClear
        """
        started = time.perf_counter()
        import ctypes
        VK_CONTROL = 0x11
        ORD_C = 0x43
        KEYEVENTF_KEYUP = 0x0002

        def _keybd_event(vk, flags=0):
            ctypes.windll.user32.keybd_event(vk, 0, flags, 0)

        result = ""
        if ITEM_POS:
            _instant_move(ITEM_POS[0], ITEM_POS[1])
            safe_wait(0.025)
        clipboard_clear_until_empty()

        for i in range(3):
            # Adamın: keybd_event(VK_CONTROL,0,0,0) / C down / C up / CTRL up
            try:
                _keybd_event(VK_CONTROL, 0)
                _keybd_event(ORD_C, 0)
                _keybd_event(ORD_C, KEYEVENTF_KEYUP)
                _keybd_event(VK_CONTROL, KEYEVENTF_KEYUP)
            except Exception:
                keyboard.press_and_release("ctrl+c")

            max_wait = 0.018 if i == 0 else (0.024 if i == 1 else 0.03)
            result = _clipboard_wait_for_text(max_wait=max_wait, poll_interval=0.004)
            if len(result) > 100:
                break
            time.sleep(0.006)

        _perf_record("get_item_info_fast", time.perf_counter() - started)
        return result

    def process_single_item():
        single_done = False
        last_base_jewel_state = None
        unchanged_base_jewel_reads = 0
        last_generic_item_state = None
        unchanged_generic_item_reads = 0
        while not single_done and not stop_event.is_set():

            # Adamın isCrafted() → GetItemInfo() — önce oku
            item_text = get_item_info()
            if not item_text:
                if (
                    settings.get("craft_logic") == "map"
                    and settings.get("map_orb_mode") == "alchemy_vaal"
                ):
                    log_message("[MAP BATCH] Boş veya okunamayan slot atlandı.")
                    return "completed"
                safe_wait(get_delay_s())
                continue

            if settings.get("craft_logic") == "socket":
                result = handle_socket_craft_state(item_text, settings)
                if result == "done":
                    single_done = True
                safe_wait(get_delay_s())
                continue

            if (
                settings.get("craft_logic") == "map"
                and settings.get("map_orb_mode") == "alchemy_vaal"
            ):
                result = handle_map_alchemy_vaal_batch_item(item_text, settings)
                return "stopped" if result == "stopped" else "completed"

            rarity, mods = parse_item_text(item_text)

            if settings.get("craft_logic") == "generic_item":
                rarity, mods, _ = generic_item.parse_item_for_craft(
                    get_item_affix_catalog(),
                    settings["item_base"],
                    settings.get("item_influence", "None"),
                    item_text,
                )
                current_state = generic_item_state_key(rarity, mods)
                if current_state == last_generic_item_state:
                    unchanged_generic_item_reads += 1
                else:
                    last_generic_item_state = current_state
                    unchanged_generic_item_reads = 1
                if unchanged_generic_item_reads >= GENERIC_ITEM_STALE_READ_LIMIT:
                    log_message(
                        "[ITEM CRAFT] Item 6 okumadir degismedi. Currency bitmis veya tiklama "
                        "uygulanmamis olabilir; guvenlik icin craft durduruldu."
                    )
                    stop_shift_spam()
                    stop_event.set()
                    return "stopped"
                result = handle_generic_item_craft_state(
                    rarity,
                    mods,
                    item_text,
                    settings,
                )
                if result == "done":
                    single_done = True
                elif result == "reset_to_magic":
                    safe_wait(0.2)
                    apply_orb("Orb of Transmutation", ITEM_POS)
                safe_wait(get_delay_s())
                continue

            if settings.get("craft_logic") == "base_jewel":
                current_state = base_jewel_state_key(rarity, mods)
                if current_state == last_base_jewel_state:
                    unchanged_base_jewel_reads += 1
                else:
                    last_base_jewel_state = current_state
                    unchanged_base_jewel_reads = 1
                if unchanged_base_jewel_reads >= BASE_JEWEL_STALE_READ_LIMIT:
                    log_message(
                        "[BASE JEWEL] Item 6 okumadir degismedi. Currency bitmis veya tiklama "
                        "uygulanmamis olabilir; guvenlik icin craft durduruldu."
                    )
                    stop_shift_spam()
                    stop_event.set()
                    return "stopped"
                result = handle_base_jewel_craft_state(rarity, mods, item_text, settings)
                if result == "done":
                    single_done = True
                elif result == "reset_to_magic":
                    safe_wait(0.2)
                    apply_orb("Orb of Transmutation", ITEM_POS)
                safe_wait(get_delay_s())
                continue

            if not validate_cluster_fracture_mode(mods, settings):
                log_message(
                    "[CLUSTER] Item fracture secimiyle uyusmuyor; "
                    "yanlis itemi degistirmemek icin craft durduruldu."
                )
                stop_shift_spam()
                stop_event.set()
                return "stopped"

            small_stop = find_small_stop_three_match(mods, settings)
            if small_stop:
                log_message(
                    f"[SMALL] Komb #{small_stop['comb_no']} icin 3 hedef bulundu; "
                    "Allflame craft icin duruldu."
                )
                stop_shift_spam()
                return "done"

            # === GLOBAL STOP-ON-TWO MATCH ===
            if find_stop_on_two_match_pair(mods, settings):
                log_message("ðŸ’Ž [GLOBAL] 2'li Ã¶zel kombinasyon bulundu â†’ Craft tamamlandÄ±.")
                stop_shift_spam()
                return "done"
            stop_pairs = []
            if stop_pairs and mods and not item_has_fractured_mod(mods):
                item_mods_clean = [normalize_mod_text(m) for m in mods]
                for pair in stop_pairs:
                    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                        continue
                    p1, p2 = pair
                    p1n, p2n = normalize_mod_text(p1), normalize_mod_text(p2)
                    if any(p1n in m for m in item_mods_clean) and any(p2n in m for m in item_mods_clean):
                        log_message("💎 [GLOBAL] 2'li özel kombinasyon bulundu → Craft tamamlandı.")
                        stop_shift_spam()
                        return "done"

            if mods:
                log_message(f"--- {rarity.upper()} Item ---")
                for mod, mtype in mods_with_types(mods):
                    tag = mtype[0].upper() if mtype != "unknown" else "?"
                    log_message(f"  [{tag}] {mod}")

            # Adamın craftMods() — karar ver + orb at
            result = "continue"
            if settings.get("craft_logic") == "map":
                result = handle_map_craft_state_v2(mods, settings, item_text)
            elif rarity.lower() == "magic":
                result = handle_magic_state(mods, settings)
            elif rarity.lower() == "rare":
                result = handle_rare_state(mods, settings)
            elif rarity.lower() == "normal":
                apply_orb("Orb of Transmutation", ITEM_POS)
            else:
                log_message(f"[UYARI] Rarity tespit edilemedi: {rarity}")

            if result == "done":
                single_done = True
            elif result == "reset_to_magic" and not item_has_fractured_mod(mods):
                safe_wait(0.2)
                apply_orb("Orb of Transmutation", ITEM_POS)

            # Adamın Sleep(craft_sleep) — her tur, done dahil
            safe_wait(get_delay_s())

        return "stopped" if stop_event.is_set() else "completed"

    try:
        if settings.get("chain_craft"):
            count = settings.get("chain_count", 1)
            slots = settings.get("inventory_slots", {})
            log_message(f"[CHAIN] {count} item için zincir craft başlıyor.")
            for i in range(1, count + 1):
                if stop_event.is_set():
                    break
                key = f"slot_{i}"
                if key not in slots:
                    log_message(f"[CHAIN] {i}. slot ({key}) yok → atla.")
                    continue
                ITEM_POS = slots[key]
                reset_hover_before_slot()
                _instant_move(ITEM_POS[0], ITEM_POS[1])
                safe_wait(0.12)
                log_message(f"--- {i}. ITEM BAŞLIYOR ---")
                status = process_single_item()
                if status == "stopped":
                    break
                log_message(f"--- {i}. ITEM BİTTİ ---")
                safe_wait(0.5)
        else:
            ITEM_POS = pyautogui.position()
            reset_hover_before_slot()
            _instant_move(ITEM_POS[0], ITEM_POS[1])
            safe_wait(0.05)
            process_single_item()
    except Exception as e:
        log_message(f"[HATA] Ana döngü: {e}\n{traceback.format_exc()}")
    finally:
        stop_shift_spam()
        try:
            keyboard.release("ctrl")
        except Exception:
            pass
        log_message("[CRAFT] Döngü durduruldu.")
        stop_session_log()

capture_item_text_once_fast = capture_item_text_once
apply_orb_fast = apply_orb
apply_augmentation_with_failover_fast = apply_augmentation_with_failover
apply_alteration_with_failover_fast = apply_alteration_with_failover
craft_thread_loop_fast = craft_thread_loop

def capture_item_text_once_safe():
    started = time.perf_counter()
    try:
        if ITEM_POS:
            return capture_text_at_pos(ITEM_POS, pre_wait=0.025, post_copy_wait=0.045, tries=2)
        return ""
    except Exception:
        return ""
    finally:
        _perf_record("capture_item_text_once_safe", time.perf_counter() - started)

def capture_item_text_once():
    if RUNTIME_SAFE_MODE:
        return capture_item_text_once_safe()
    return capture_item_text_once_fast()

def _slot_consumed_for_safe_orb(orb_name, before_slot_stack, before_slot_txt, after_slot_stack, after_slot_txt):
    if before_slot_stack is not None and after_slot_stack is not None:
        return after_slot_stack < before_slot_stack
    if before_slot_stack is not None and (not after_slot_txt or not is_expected_currency_text(after_slot_txt, orb_name)):
        return True
    if before_slot_txt and after_slot_txt and after_slot_txt != before_slot_txt:
        return True
    return False

def _fatal_safe_stop(message: str):
    log_message(message)
    stop_event.set()
    raise CraftFatalError(message)

def apply_orb_basic_safe(orb_name, item_pos):
    loc = resolve_orb_location(orb_name)
    if not loc:
        _fatal_safe_stop(f"[SAFE] {orb_name} konumu bulunamadi.")

    stop_shift_spam()
    release_cursor_item_if_any()
    before_item_text = capture_item_text_once_safe()
    before_slot_stack, before_slot_txt = _read_stack_at_slot(loc)
    if before_slot_txt and not is_expected_currency_text(before_slot_txt, orb_name):
        _fatal_safe_stop(f"[SAFE] {orb_name} slotu dogrulanamadi.")

    orb_right_click(loc[0], loc[1])
    extra_gap = 0.04 if orb_name in ("Orb of Transmutation", "Orb of Alchemy", "Orb of Scouring") else 0.02
    safe_wait(extra_gap)
    item_left_click(item_pos[0], item_pos[1])
    safe_wait(0.06)

    after_item_text = capture_item_text_once_safe()
    if before_item_text and after_item_text and before_item_text == after_item_text:
        safe_wait(0.08)
        after_item_text = capture_item_text_once_safe()

    after_slot_stack, after_slot_txt = _read_stack_at_slot(loc)
    slot_consumed = _slot_consumed_for_safe_orb(
        orb_name, before_slot_stack, before_slot_txt, after_slot_stack, after_slot_txt
    )
    item_changed = bool(before_item_text and after_item_text and before_item_text != after_item_text)

    if slot_consumed or item_changed:
        update_stack_cache_after_use(orb_name, before_slot_stack, after_slot_stack, after_slot_txt)
        record_currency_use(orb_name)
        log_message(f"[SAFE] {orb_name} uygulandi.")
        return True

    raise CraftRecoveryNeeded(f"{orb_name} dogrulanamadi.")

def apply_orb_critical_safe(orb_name, item_pos):
    loc = resolve_orb_location(orb_name)
    if not loc:
        _fatal_safe_stop(f"[SAFE] {orb_name} konumu bulunamadi.")

    before_slot_stack, before_slot_txt = _read_stack_at_slot(loc)
    before_item_text = capture_item_text_once_safe()
    if before_slot_txt and not is_expected_currency_text(before_slot_txt, orb_name):
        _fatal_safe_stop(f"[SAFE] {orb_name} slotu dogrulanamadi.")

    for attempt in range(1, 4):
        try:
            stop_shift_spam()
            release_cursor_item_if_any()
            critical_orb_right_click_safe(loc[0], loc[1])
            safe_wait(0.08)
            item_left_click(item_pos[0], item_pos[1])
            safe_wait(0.12)

            after_slot_stack, after_slot_txt = _read_stack_at_slot(loc)
            after_item_text = capture_item_text_once_safe()
            if before_item_text and after_item_text and before_item_text == after_item_text:
                safe_wait(0.08)
                after_item_text = capture_item_text_once_safe()
            slot_consumed = _slot_consumed_for_safe_orb(
                orb_name, before_slot_stack, before_slot_txt, after_slot_stack, after_slot_txt
            )
            item_changed = bool(before_item_text and after_item_text and before_item_text != after_item_text)

            if slot_consumed or item_changed:
                record_currency_use(orb_name)
                log_message(f"[SAFE] {orb_name} verify ok (try {attempt}).")
                return True

            log_message(f"[SAFE] {orb_name} verify fail (try {attempt}/3).")
            safe_wait(0.08)
        except Exception as e:
            release_cursor_item_if_any()
            log_message(f"[SAFE] {orb_name} try {attempt} hata: {e}")

    raise CraftRecoveryNeeded(f"{orb_name} 3 denemede uygulanamadi.")

def apply_orb_safe(orb_name, item_pos):
    if orb_name in SAFE_CRITICAL_ORBS:
        return apply_orb_critical_safe(orb_name, item_pos)
    return apply_orb_basic_safe(orb_name, item_pos)

def apply_orb(orb_name, item_pos):
    if RUNTIME_SAFE_MODE:
        return apply_orb_safe(orb_name, item_pos)
    return apply_orb_fast(orb_name, item_pos)

def apply_augmentation_with_failover_safe(chain_craft=False):
    ORB_VERIFY_COUNTERS["Orb of Augmentation"] += 1

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        orb_loc = ensure_stack_tracked_orb_available("Orb of Augmentation")
        if not orb_loc:
            _fatal_safe_stop("[SAFE] Orb of Augmentation slotu bulunamadi.")

        if ORB_VERIFY_COUNTERS["Orb of Augmentation"] >= SAFE_AUG_VERIFY_EVERY:
            ORB_VERIFY_COUNTERS["Orb of Augmentation"] = 0
            verified = verify_cached_currency_slot("Orb of Augmentation")
            if verified:
                orb_loc = verified
            else:
                next_loc = find_next_currency_slot_after_cache("Orb of Augmentation")
                if not next_loc:
                    _fatal_safe_stop("[SAFE] Orb of Augmentation dogrulanamadi.")
                orb_loc = next_loc

        before_slot_stack, before_slot_txt = _read_stack_at_slot(orb_loc)
        before_item_text = capture_item_text_once_safe()
        if before_slot_txt and not is_expected_currency_text(before_slot_txt, "Orb of Augmentation"):
            ACTIVE_ORB_STACK_CACHE["Orb of Augmentation"] = 0
            next_loc = find_next_currency_slot_after_cache("Orb of Augmentation")
            if not next_loc:
                _fatal_safe_stop("[SAFE] Orb of Augmentation slotu beklenen currency degil.")
            orb_loc = next_loc
            before_slot_stack, before_slot_txt = _read_stack_at_slot(orb_loc)
            before_item_text = capture_item_text_once_safe()

        stop_shift_spam()
        release_cursor_item_if_any()
        orb_right_click(orb_loc[0], orb_loc[1])
        safe_wait(0.05)
        item_left_click(ITEM_POS[0], ITEM_POS[1])
        safe_wait(0.12)

        after_slot_stack, after_slot_txt = _read_stack_at_slot(orb_loc)
        after_item_text = capture_item_text_once_safe()
        if before_item_text and after_item_text and before_item_text == after_item_text:
            safe_wait(0.08)
            after_item_text = capture_item_text_once_safe()

        slot_consumed = _slot_consumed_for_safe_orb(
            "Orb of Augmentation", before_slot_stack, before_slot_txt, after_slot_stack, after_slot_txt
        )
        item_changed = bool(before_item_text and after_item_text and before_item_text != after_item_text)

        if slot_consumed or item_changed:
            update_stack_cache_after_use("Orb of Augmentation", before_slot_stack, after_slot_stack, after_slot_txt)
            record_currency_use("Orb of Augmentation")
            log_message("[SAFE] Orb of Augmentation verify ok.")
            return True

        log_message(f"[SAFE] Orb of Augmentation verify fail (try {attempt}/{max_attempts}).")
        if not after_slot_txt or not is_expected_currency_text(after_slot_txt, "Orb of Augmentation"):
            ACTIVE_ORB_STACK_CACHE["Orb of Augmentation"] = 0

    raise CraftRecoveryNeeded("Orb of Augmentation uygulanamadi.")

def apply_augmentation_with_failover(chain_craft=False):
    if RUNTIME_SAFE_MODE:
        return apply_augmentation_with_failover_safe(chain_craft=chain_craft)
    return apply_augmentation_with_failover_fast(chain_craft=chain_craft)

def apply_alteration_with_failover_safe(chain_craft=False):
    global shift_spam_active

    orb_loc = ensure_stack_tracked_orb_available("Orb of Alteration")
    if not orb_loc:
        _fatal_safe_stop("[SAFE] Orb of Alteration slotu bulunamadi.")

    if not shift_spam_active:
        orb_right_click(orb_loc[0], orb_loc[1])
        try:
            keyboard.press("shift")
        except Exception:
            pass
        safe_wait(0.005)
        shift_spam_active = True
        ORB_VERIFY_COUNTERS["Orb of Alteration"] = 0
        log_message(f"[SAFE] Alteration spam basladi. Local stack={ACTIVE_ORB_STACK_CACHE.get('Orb of Alteration')}")

    ORB_VERIFY_COUNTERS["Orb of Alteration"] += 1
    if ORB_VERIFY_COUNTERS["Orb of Alteration"] >= SAFE_ALTER_VERIFY_EVERY:
        ORB_VERIFY_COUNTERS["Orb of Alteration"] = 0
        verified = verify_cached_currency_slot("Orb of Alteration")
        if not verified:
            log_message("[SAFE] Alteration slot verify fail, sonraki slot araniyor.")
            stop_shift_spam()
            orb_loc = find_next_currency_slot_after_cache("Orb of Alteration")
            if not orb_loc:
                _fatal_safe_stop("[SAFE] Orb of Alteration icin baska slot bulunamadi.")
            orb_right_click(orb_loc[0], orb_loc[1])
            try:
                keyboard.press("shift")
            except Exception:
                pass
            safe_wait(0.005)
            shift_spam_active = True

    try:
        item_left_click(ITEM_POS[0], ITEM_POS[1])
        decrement_local_stack_cache("Orb of Alteration")
        record_currency_use("Orb of Alteration")
        return True
    except Exception as e:
        release_cursor_item_if_any()
        raise CraftRecoveryNeeded(f"Alteration uygulanirken hata olustu: {e}")

def apply_alteration_with_failover(chain_craft=False):
    if RUNTIME_SAFE_MODE:
        return apply_alteration_with_failover_safe(chain_craft=chain_craft)
    return apply_alteration_with_failover_fast(chain_craft=chain_craft)

def get_item_info_safe():
    started = time.perf_counter()
    result = ""
    if ITEM_POS:
        _instant_move(ITEM_POS[0], ITEM_POS[1])
        safe_wait(0.025)

    clipboard_clear_until_empty()
    for i in range(3):
        _send_ctrl_c_lowlevel()
        max_wait = 0.018 if i == 0 else (0.024 if i == 1 else 0.03)
        result = _clipboard_wait_for_text(max_wait=max_wait, poll_interval=0.004)
        if len(result) > 100:
            break
        safe_wait(0.006)
    _perf_record("get_item_info_safe", time.perf_counter() - started)
    return result

def craft_thread_loop_safe(settings):
    global ITEM_POS
    consecutive_errors = 0

    def process_single_item_safe():
        nonlocal consecutive_errors
        single_done = False
        last_base_jewel_state = None
        unchanged_base_jewel_reads = 0
        last_generic_item_state = None
        unchanged_generic_item_reads = 0
        while not single_done and not stop_event.is_set():
            try:
                item_text = get_item_info_safe()
                if not item_text:
                    if (
                        settings.get("craft_logic") == "map"
                        and settings.get("map_orb_mode") == "alchemy_vaal"
                    ):
                        log_message("[MAP BATCH] Boş veya okunamayan slot atlandı.")
                        return "completed"
                    raise CraftRecoveryNeeded("Esya metni kopyalanamadi.")

                if settings.get("craft_logic") == "socket":
                    result = handle_socket_craft_state(item_text, settings)
                    if result == "done":
                        single_done = True
                    safe_wait(get_delay_s())
                    consecutive_errors = 0
                    continue

                if (
                    settings.get("craft_logic") == "map"
                    and settings.get("map_orb_mode") == "alchemy_vaal"
                ):
                    result = handle_map_alchemy_vaal_batch_item(item_text, settings)
                    consecutive_errors = 0
                    return "stopped" if result == "stopped" else "completed"

                rarity, mods = parse_item_text(item_text)

                if settings.get("craft_logic") == "generic_item":
                    rarity, mods, _ = generic_item.parse_item_for_craft(
                        get_item_affix_catalog(),
                        settings["item_base"],
                        settings.get("item_influence", "None"),
                        item_text,
                    )
                    current_state = generic_item_state_key(rarity, mods)
                    if current_state == last_generic_item_state:
                        unchanged_generic_item_reads += 1
                    else:
                        last_generic_item_state = current_state
                        unchanged_generic_item_reads = 1
                    if unchanged_generic_item_reads >= GENERIC_ITEM_STALE_READ_LIMIT:
                        log_message(
                            "[ITEM CRAFT] Item 6 okumadir degismedi. Currency bitmis veya tiklama "
                            "uygulanmamis olabilir; guvenlik icin craft durduruldu."
                        )
                        stop_shift_spam()
                        stop_event.set()
                        return "stopped"
                    result = handle_generic_item_craft_state(
                        rarity,
                        mods,
                        item_text,
                        settings,
                    )
                    if result == "done":
                        single_done = True
                    elif result == "reset_to_magic":
                        safe_wait(0.2)
                        apply_orb("Orb of Transmutation", ITEM_POS)
                    safe_wait(get_delay_s())
                    consecutive_errors = 0
                    continue

                if settings.get("craft_logic") == "base_jewel":
                    current_state = base_jewel_state_key(rarity, mods)
                    if current_state == last_base_jewel_state:
                        unchanged_base_jewel_reads += 1
                    else:
                        last_base_jewel_state = current_state
                        unchanged_base_jewel_reads = 1
                    if unchanged_base_jewel_reads >= BASE_JEWEL_STALE_READ_LIMIT:
                        log_message(
                            "[BASE JEWEL] Item 6 okumadir degismedi. Currency bitmis veya tiklama "
                            "uygulanmamis olabilir; guvenlik icin craft durduruldu."
                        )
                        stop_shift_spam()
                        stop_event.set()
                        return "stopped"
                    result = handle_base_jewel_craft_state(rarity, mods, item_text, settings)
                    if result == "done":
                        single_done = True
                    elif result == "reset_to_magic":
                        safe_wait(0.2)
                        apply_orb("Orb of Transmutation", ITEM_POS)
                    safe_wait(get_delay_s())
                    consecutive_errors = 0
                    continue

                if not validate_cluster_fracture_mode(mods, settings):
                    log_message(
                        "[CLUSTER] Item fracture secimiyle uyusmuyor; "
                        "yanlis itemi degistirmemek icin craft durduruldu."
                    )
                    stop_shift_spam()
                    stop_event.set()
                    return "stopped"

                small_stop = find_small_stop_three_match(mods, settings)
                if small_stop:
                    log_message(
                        f"[SMALL] Komb #{small_stop['comb_no']} icin 3 hedef bulundu; "
                        "Allflame craft icin duruldu."
                    )
                    stop_shift_spam()
                    return "done"

                if find_stop_on_two_match_pair(mods, settings):
                    log_message("[GLOBAL] 2'li ozel kombinasyon bulundu, craft tamamlandi.")
                    stop_shift_spam()
                    return "done"

                stop_pairs = []
                if stop_pairs and mods and not item_has_fractured_mod(mods):
                    item_mods_clean = [normalize_mod_text(m) for m in mods]
                    for pair in stop_pairs:
                        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                            continue
                        p1, p2 = pair
                        p1n, p2n = normalize_mod_text(p1), normalize_mod_text(p2)
                        if any(p1n in m for m in item_mods_clean) and any(p2n in m for m in item_mods_clean):
                            log_message("[GLOBAL] 2'li ozel kombinasyon bulundu, craft tamamlandi.")
                            stop_shift_spam()
                            return "done"

                if mods:
                    log_message(f"--- {rarity.upper()} Item ---")
                    for mod, mtype in mods_with_types(mods):
                        tag = mtype[0].upper() if mtype != "unknown" else "?"
                        log_message(f"  [{tag}] {mod}")

                result = "continue"
                if settings.get("craft_logic") == "map":
                    result = handle_map_craft_state_v2(mods, settings, item_text)
                elif rarity.lower() == "magic":
                    result = handle_magic_state(mods, settings)
                elif rarity.lower() == "rare":
                    result = handle_rare_state(mods, settings)
                elif rarity.lower() == "normal":
                    apply_orb("Orb of Transmutation", ITEM_POS)
                else:
                    log_message(f"[UYARI] Rarity tespit edilemedi: {rarity}")

                if result == "done":
                    single_done = True
                elif result == "reset_to_magic" and not item_has_fractured_mod(mods):
                    safe_wait(0.2)
                    apply_orb("Orb of Transmutation", ITEM_POS)

                safe_wait(get_delay_s())
                consecutive_errors = 0
            except CraftFatalError as e:
                log_message(f"[SAFE-FATAL] {e}")
                stop_shift_spam()
                clipboard_clear_until_empty()
                release_cursor_item_if_any()
                stop_event.set()
                return "stopped"
            except CraftRecoveryNeeded as e:
                consecutive_errors += 1
                log_message(f"[SAFE] {e} ({consecutive_errors}/5)")
                stop_shift_spam()
                clipboard_clear_until_empty()
                release_cursor_item_if_any()
                safe_wait(min(1.4, 0.8 + (consecutive_errors - 1) * 0.2))
                if consecutive_errors >= 5:
                    log_message("[SAFE] Ardisik hata limiti asildi, craft durduruluyor.")
                    stop_event.set()
                    return "stopped"

        return "stopped" if stop_event.is_set() else "completed"

    try:
        if settings.get("chain_craft"):
            count = settings.get("chain_count", 1)
            slots = settings.get("inventory_slots", {})
            log_message(f"[CHAIN] {count} item icin zincir craft basliyor.")
            for i in range(1, count + 1):
                if stop_event.is_set():
                    break
                key = f"slot_{i}"
                if key not in slots:
                    log_message(f"[CHAIN] {i}. slot ({key}) yok, atla.")
                    continue
                ITEM_POS = slots[key]
                reset_hover_before_slot()
                _instant_move(ITEM_POS[0], ITEM_POS[1])
                safe_wait(0.12)
                log_message(f"--- {i}. ITEM BASLIYOR ---")
                status = process_single_item_safe()
                if status == "stopped":
                    break
                log_message(f"--- {i}. ITEM BITTI ---")
                safe_wait(0.35)
        else:
            ITEM_POS = pyautogui.position()
            reset_hover_before_slot()
            _instant_move(ITEM_POS[0], ITEM_POS[1])
            safe_wait(0.05)
            process_single_item_safe()
    except Exception as e:
        release_cursor_item_if_any()
        log_message(f"[HATA] Safe dongu: {e}\n{traceback.format_exc()}")
    finally:
        stop_shift_spam()
        try:
            keyboard.release("ctrl")
        except Exception:
            pass
        release_cursor_item_if_any()
        log_message("[CRAFT] Dongu durduruldu.")
        stop_session_log()

def _craft_thread_loop_dispatch(settings):
    global RUNTIME_SAFE_MODE
    if settings.get("craft_logic") == "auto_flask":
        return run_auto_flask(settings)
    RUNTIME_SAFE_MODE = bool(settings.get("safe_mode"))
    if RUNTIME_SAFE_MODE:
        reset_safe_runtime_tracking()
        return craft_thread_loop_safe(settings)
    reset_fast_runtime_tracking()
    monitor_item_pos = None
    if settings.get("chain_craft"):
        slots = settings.get("inventory_slots", {})
        for i in range(1, int(settings.get("chain_count", 1)) + 1):
            pos = slots.get(f"slot_{i}")
            if pos:
                monitor_item_pos = pos
                break
    else:
        try:
            pos = pyautogui.position()
            monitor_item_pos = (int(pos[0]), int(pos[1]))
        except Exception:
            monitor_item_pos = ITEM_POS
    if not monitor_item_pos:
        log_message("[FAST-CURSOR] Baslangic item pozisyonu bulunamadi. Fast craft baslatilmadi.")
        stop_session_log()
        return
    if not start_fast_cursor_monitor(monitor_item_pos):
        log_message("[FAST-CURSOR] Monitor hazir olmadan fast craft baslatilmadi.")
        stop_session_log()
        return
    try:
        return craft_thread_loop_fast(settings)
    finally:
        stop_fast_cursor_monitor()


def craft_thread_loop(settings):
    _notification_session_begin(settings)
    try:
        return _craft_thread_loop_dispatch(settings)
    except Exception as exc:
        _notification_set_reason(f"Beklenmeyen hata: {exc}", "error", 95)
        raise
    finally:
        end_kind = _notification_session_kind()
        _notification_session_finish()
        _execute_post_craft_action(settings, end_kind)

# ================ TEMPLATE & COMB UI HELPERS ================
comb_craft_data = {}
combo_price_data = {}
template_price_meta = {}
template_cluster_meta = {}
template_comb_craft_data = {}
template_combo_price_data = {}
template_stop_on_two_match_config = []
template_annul_combs_config = []
template_no_annul_combs_config = []
template_solo_regal_mods_config = []
template_no_regal_mods_config = []
market_cluster_template_active = False
market_filter_source_keys = []
is_effect35_template = False
stop_on_two_match_config = []
annul_combs_config = []
no_annul_combs_config = []
solo_regal_mods_config = []   # magic'te tek başına regal tetikleyen modlar
no_regal_mods_config = []     # kombinasyonda bu mod varsa regal atılmaz

CLUSTER_PRICE_FILTERS = {
    "All": 0.0,
    "2d+": 2.0,
    "5d+": 5.0,
    "10d+": 10.0,
    "20d+": 20.0,
    "50d+": 50.0,
}

def format_affix_for_display(text):
    m = re.search(r"\[(P|S)\]\[(\d+)\]\s(.+)", text)
    if not m:
        return text
    tag, weight, content = m.groups()
    for pat in AFFIX_BOILERPLATE:
        content = pat.sub("", content).strip()
    parts = content.split()
    if len(parts) > 1:
        content = f"{parts[0]} {parts[1][0]}."
    return f"[{tag}][{weight}]{content}"

def _format_combo_price(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "?"
    if amount >= 1000:
        return f"{amount / 1000:.1f}kc"
    if amount >= 100:
        return f"{amount:.0f}c"
    return f"{amount:.1f}c"

def _format_combo_divine_price(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "?"
    return f"{amount:.1f}d"

def populate_comb_list():
    global comb_craft_data, combo_price_data, no_annul_combs_config
    comb_list.delete(0, "end")
    if not comb_craft_data:
        return
    sorted_keys = sorted(comb_craft_data.keys(), key=lambda x: int(x))
    old_to_new = {str(k): str(i + 1) for i, k in enumerate(sorted_keys)}
    comb_craft_data = {str(i + 1): comb_craft_data[k] for i, k in enumerate(sorted_keys)}
    combo_price_data = {
        old_to_new[str(k)]: value
        for k, value in combo_price_data.items()
        if str(k) in old_to_new
    }
    no_annul_combs_config[:] = [old_to_new.get(str(k), str(k)) for k in no_annul_combs_config if str(k) in old_to_new]
    for i in range(1, len(comb_craft_data) + 1):
        key = str(i)
        display_parts = [format_affix_for_display(aff) for aff in comb_craft_data[key]]
        display_text = "|".join(display_parts)
        price = combo_price_data.get(key, {})
        if isinstance(price, dict) and price:
            min_divine = price.get("min_divine")
            max_divine = price.get("max_divine")
            min_price = price.get("min_chaos")
            max_price = price.get("max_chaos")
            sample_size = price.get("sample_size", price.get("listings", 0))
            if (
                min_divine is not None
                and max_divine is not None
                and sample_size
            ):
                display_text = (
                    f"[{_format_combo_divine_price(min_divine)}-"
                    f"{_format_combo_divine_price(max_divine)}] {display_text}"
                )
            elif min_price is not None and max_price is not None and sample_size:
                display_text = (
                    f"[{_format_combo_price(min_price)}-"
                    f"{_format_combo_price(max_price)}] {display_text}"
                )
            elif min_price is not None or max_price is not None:
                display_text = f"[ilan yok] {display_text}"
        elif template_price_meta:
            display_text = f"[fiyat bekleniyor] {display_text}"
        comb_list.insert("end", display_text)

def list_templates_from_folder():
    mode = app_mode.get()
    template_dir = (
        MAP_TEMPLATE_DIR
        if mode == "map"
        else (
            BASE_JEWEL_TEMPLATE_DIR
            if mode == "base_jewel"
            else (GENERIC_ITEM_TEMPLATE_DIR if mode == "item" else TEMPLATE_DIR)
        )
    )
    os.makedirs(template_dir, exist_ok=True)
    names = sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(template_dir)
        if f.endswith(".json")
    )
    if mode != "cluster":
        return names

    selected_size = cluster_size_var.get()
    visible = []
    for name in names:
        path = os.path.join(template_dir, f"{name}.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = {}
        if cluster_template_size(name, data) == selected_size:
            visible.append(name)
    return visible


def cluster_template_size(name, data=None):
    """Classify templates while retaining compatibility with legacy names."""
    data = data if isinstance(data, dict) else {}
    explicit = str(data.get("cluster_size", "")).strip().lower()
    if explicit in {"small", "medium", "large"}:
        return explicit

    meta = data.get("cluster_meta", {})
    try:
        passive_count = int(meta.get("passive_count", 0) or 0)
    except (TypeError, ValueError):
        passive_count = 0
    if 1 <= passive_count <= 3:
        return "small"
    if 4 <= passive_count <= 6:
        return "medium"
    if passive_count >= 7:
        return "large"

    lowered = str(name or "").strip().lower()
    if re.match(r"^s\d+\s*-", lowered):
        return "small"
    if re.match(r"^m\d+\s*-", lowered):
        return "medium"
    return "large"

def template_path(name: str):
    mode = app_mode.get()
    template_dir = (
        MAP_TEMPLATE_DIR
        if mode == "map"
        else (
            BASE_JEWEL_TEMPLATE_DIR
            if mode == "base_jewel"
            else (GENERIC_ITEM_TEMPLATE_DIR if mode == "item" else TEMPLATE_DIR)
        )
    )
    return os.path.join(template_dir, f"{name}.json")

def refresh_templates():
    names = list_templates_from_folder()
    template_cb["values"] = names
    current_name = template_var.get().strip()
    if current_name and current_name not in names:
        template_var.set("")
    refresh_trade_panel = globals().get("refresh_cluster_trade_templates")
    if callable(refresh_trade_panel):
        refresh_trade_panel()

def _copy_combo_data(data):
    return {
        str(key): list(value)
        for key, value in data.items()
        if isinstance(value, (list, tuple))
    }

def _copy_price_data(data):
    return {
        str(key): dict(value)
        for key, value in data.items()
        if isinstance(value, dict)
    }

def _combo_visible_mods(combos):
    return {
        mod
        for combo in combos.values()
        for mod in combo
    }

def _filter_stop_pairs_for_combos(pairs, combos):
    combo_sets = [set(combo) for combo in combos.values()]
    return [
        list(pair)
        for pair in pairs
        if isinstance(pair, (list, tuple))
        and len(pair) == 2
        and any(set(pair).issubset(combo) for combo in combo_sets)
    ]

def _prune_active_combo_rules():
    visible_mods = _combo_visible_mods(comb_craft_data)
    stop_on_two_match_config[:] = _filter_stop_pairs_for_combos(
        stop_on_two_match_config,
        comb_craft_data,
    )
    annul_combs_config[:] = [
        mod for mod in annul_combs_config if mod in visible_mods
    ]
    solo_regal_mods_config[:] = [
        mod for mod in solo_regal_mods_config if mod in visible_mods
    ]
    no_regal_mods_config[:] = [
        mod for mod in no_regal_mods_config if mod in visible_mods
    ]

def _price_filter_floor():
    value = cluster_price_filter_var.get().strip()
    return CLUSTER_PRICE_FILTERS.get(value, 0.0)

def _select_cluster_price_keys(combos, prices, minimum_divine):
    selected_keys = []
    for key in sorted(combos, key=int):
        if minimum_divine <= 0:
            selected_keys.append(key)
            continue
        try:
            listed_minimum = float(prices.get(key, {}).get("min_divine"))
        except (TypeError, ValueError):
            continue
        if listed_minimum >= minimum_divine:
            selected_keys.append(key)
    return selected_keys

def apply_cluster_price_filter(log_change=False):
    global comb_craft_data, combo_price_data, market_filter_source_keys
    if not market_cluster_template_active:
        market_filter_source_keys = []
        cluster_price_filter_cb.configure(state="disabled")
        cluster_price_filter_status_var.set("No saved market data")
        populate_comb_list()
        return

    cluster_price_filter_cb.configure(state="readonly")
    floor = _price_filter_floor()
    source_keys = sorted(template_comb_craft_data, key=int)
    selected_keys = _select_cluster_price_keys(
        template_comb_craft_data,
        template_combo_price_data,
        floor,
    )

    market_filter_source_keys = list(selected_keys)
    source_to_active = {
        source_key: str(index + 1)
        for index, source_key in enumerate(selected_keys)
    }
    comb_craft_data = {
        str(index + 1): list(template_comb_craft_data[source_key])
        for index, source_key in enumerate(selected_keys)
    }
    combo_price_data = {
        str(index + 1): dict(template_combo_price_data[source_key])
        for index, source_key in enumerate(selected_keys)
        if source_key in template_combo_price_data
    }

    visible_mods = _combo_visible_mods(comb_craft_data)
    stop_on_two_match_config[:] = _filter_stop_pairs_for_combos(
        template_stop_on_two_match_config,
        comb_craft_data,
    )
    annul_combs_config[:] = [
        mod for mod in template_annul_combs_config if mod in visible_mods
    ]
    no_annul_combs_config[:] = [
        source_to_active[str(key)]
        for key in template_no_annul_combs_config
        if str(key) in source_to_active
    ]
    solo_regal_mods_config[:] = [
        mod for mod in template_solo_regal_mods_config if mod in visible_mods
    ]
    no_regal_mods_config[:] = [
        mod for mod in template_no_regal_mods_config if mod in visible_mods
    ]

    _clear_comb_match_caches()
    populate_comb_list()
    populate_stop_two_list()
    populate_annul_combs_list()
    populate_solo_regal_list()
    populate_no_regal_list()
    cluster_price_filter_status_var.set(
        f"{len(selected_keys)}/{len(source_keys)} combos"
    )
    if log_change:
        log_message(
            f"[PRICE FILTER] {cluster_price_filter_var.get()}: "
            f"{len(selected_keys)}/{len(source_keys)} kombinasyon. "
            "Son kayitli tarama kullanildi; API istegi yapilmadi."
        )

def on_cluster_price_filter_changed(event=None):
    settings_cfg.set(
        "General", "cluster_price_filter", cluster_price_filter_var.get()
    )
    save_settings_debounced()
    apply_cluster_price_filter(log_change=True)

def load_template():
    global comb_craft_data, combo_price_data, template_price_meta
    global template_cluster_meta
    global template_comb_craft_data, template_combo_price_data
    global template_stop_on_two_match_config, template_annul_combs_config
    global template_no_annul_combs_config, template_solo_regal_mods_config
    global template_no_regal_mods_config, market_cluster_template_active
    global stop_on_two_match_config, annul_combs_config, no_annul_combs_config, is_effect35_template
    if app_mode.get() == "socket":
        gui_warn("Socket modunda template kullanilmiyor.")
        return
    name = template_var.get().strip()
    if not name:
        return
    path = template_path(name)
    if not os.path.exists(path):
        gui_error(f"'{name}' bulunamadı.")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logic_val = data.get("craft_logic", "Rare (regal)")
        if logic_val == "effect35":
            logic_val = "Rare (regal)"
        is_map_template = bool(
            data.get("app_mode") == "map"
            or any(
                key in data
                for key in (
                    "map_normal_forbidden",
                    "map_memory_forbidden",
                    "map_forbidden",
                    "map_good",
                    "map_bad",
                )
            )
        )
        is_base_jewel_template = bool(
            data.get("app_mode") == "base_jewel"
            or data.get("craft_logic") == "base_jewel"
        )
        is_item_template = bool(
            data.get("app_mode") == "item"
            or data.get("craft_logic") == "generic_item"
        )
        if is_map_template and logic_val not in (
            "Rare (alchemy)",
            "Rare (chaos)",
            "Alchemy + Vaal",
        ):
            logic_val = "Rare (chaos)"
        if not is_base_jewel_template and not is_item_template:
            craft_logic.set(logic_val)
        if not is_map_template and not is_base_jewel_template and not is_item_template:
            cluster_size_var.set(cluster_template_size(name, data))
            augment_mode.set(data.get("augment_mode", "Use if needed"))
            cluster_no_regal_two_var.set(
                bool(data.get("cluster_no_regal_two_mods", False))
            )
            cluster_small_stop_three_var.set(
                cluster_size_var.get() == "small"
                and bool(data.get("cluster_small_stop_three_mods", False))
            )
        else:
            cluster_no_regal_two_var.set(False)
            cluster_small_stop_three_var.set(False)
        # Effect35 templatelerinde her kombinasyon 4 mod içerir → exalt şart
        comb_craft_data_raw = data.get("comb_craft_data", {}) if not is_map_template else {}
        is_effect35 = any(len(v) >= 4 for v in comb_craft_data_raw.values())
        is_effect35_template = is_effect35
        if not is_map_template and not is_base_jewel_template and not is_item_template:
            use_exalt.set(True if is_effect35 else bool(data.get("use_exalt", False)))
        if not is_map_template and not is_base_jewel_template and not is_item_template:
            use_annul.set(bool(data.get("use_annul", False)))
        chain_craft.set(bool(data.get("chain_craft", False)))
        chain_count_var.set(str(data.get("chain_count", 1)))
        if is_base_jewel_template:
            base_jewel_crit_count_var.set(str(data.get("base_jewel_crit_count", 3)))
            base_jewel_require_life_var.set(int(data.get("base_jewel_life_count", 0)) > 0)
            base_jewel_regal_min_var.set(str(data.get("base_jewel_regal_min", 2)))
            base_jewel_no_regal_var.set(bool(data.get("base_jewel_no_regal", False)))
            base_jewel_use_augment_var.set(bool(data.get("base_jewel_use_augment", True)))
            base_jewel_use_exalt_var.set(bool(data.get("base_jewel_use_exalt", True)))
            base_jewel_use_annul_var.set(bool(data.get("base_jewel_use_annul", True)))
            set_base_jewel_crit_patterns(
                data.get("base_jewel_crit_mods") or DEFAULT_BASE_JEWEL_CRIT_MODS
            )
        if is_item_template:
            item_base_var.set(str(data.get("item_base", "Blizzard Crown")))
            item_influence_var.set(str(data.get("item_influence", "None")))
            item_level_var.set(str(data.get("item_level", 75)))
            item_required_count_var.set(str(data.get("item_required_count", 1)))
            item_use_augment_var.set(bool(data.get("item_use_augment", True)))
            item_use_regal_var.set(bool(data.get("item_use_regal", False)))
            item_use_exalt_var.set(bool(data.get("item_use_exalt", False)))
            item_use_annul_var.set(bool(data.get("item_use_annul", False)))
            item_chance_to_unique_var.set(bool(data.get("item_chance_to_unique", False)))
            item_target_ids[:] = [
                str(target_id)
                for target_id in data.get("item_target_ids", [])
                if str(target_id).strip()
            ]
            populate_item_target_list()
            reload_item_mod_pool()
        map_orb_mode.set({
            "Rare (alchemy)": "alchemy",
            "Alchemy + Vaal": "alchemy_vaal",
        }.get(logic_val, "chaos"))
        map_use_exalt.set(bool(data.get("map_use_exalt", False)))
        map_profile_var.set(map_rules.normalize_profile(data.get("map_profile")))
        map_normal_forbidden[:] = data.get(
            "map_normal_forbidden",
            data.get("map_forbidden", []),
        )
        map_memory_forbidden[:] = data.get("map_memory_forbidden", [])
        for var, key in [
            (map_quantity_thresh, "map_quantity_thresh"),
            (map_rarity_thresh, "map_rarity_thresh"),
            (map_pack_size_thresh, "map_pack_size_thresh"),
        ]:
            val = data.get(key, "")
            var.set("" if val is None else str(val))

        if not is_map_template and not is_base_jewel_template and not is_item_template:
            template_cluster_meta = dict(data.get("cluster_meta", {}))
            cluster_fracture_mode_var.set(
                str(data.get("cluster_fracture_mode", "unfractured"))
            )
            cluster_fractured_target_var.set(
                str(data.get("cluster_fractured_target", ""))
            )
            template_comb_craft_data = _copy_combo_data(
                data.get("comb_craft_data", {})
            )
            template_combo_price_data = _copy_price_data(
                data.get("combo_prices", {})
            )
            template_price_meta = data.get("price_meta", {})
            template_stop_on_two_match_config = list(
                data.get("stop_on_two_match", [])
            )
            template_annul_combs_config = list(data.get("annul_combs", []))
            template_no_annul_combs_config = list(
                data.get("no_annul_combs", [])
            )
            template_solo_regal_mods_config = list(
                data.get("solo_regal_mods", [])
            )
            template_no_regal_mods_config = list(
                data.get("no_regal_mods", [])
            )
            market_cluster_template_active = bool(
                re.fullmatch(
                    r"L(?:8|12) - [A-Za-z0-9]+(?: - ilvl\d+)?",
                    name,
                )
                and template_price_meta.get("market_scan_complete")
            )
            if market_cluster_template_active:
                apply_cluster_price_filter()
            else:
                comb_craft_data = _copy_combo_data(template_comb_craft_data)
                combo_price_data = _copy_price_data(template_combo_price_data)
                stop_on_two_match_config[:] = template_stop_on_two_match_config
                annul_combs_config[:] = template_annul_combs_config
                no_annul_combs_config[:] = template_no_annul_combs_config
                solo_regal_mods_config[:] = template_solo_regal_mods_config
                no_regal_mods_config[:] = template_no_regal_mods_config
                _clear_comb_match_caches()
                apply_cluster_price_filter()
        elif is_map_template or is_base_jewel_template or is_item_template:
            template_cluster_meta = {}
            comb_craft_data = {}
            combo_price_data = {}
            template_price_meta = {}
            template_comb_craft_data = {}
            template_combo_price_data = {}
            template_stop_on_two_match_config = []
            template_annul_combs_config = []
            template_no_annul_combs_config = []
            template_solo_regal_mods_config = []
            template_no_regal_mods_config = []
            market_cluster_template_active = False
            no_annul_combs_config[:] = []
            apply_cluster_price_filter()
        populate_stop_two_list()
        populate_annul_combs_list()
        populate_solo_regal_list()
        populate_no_regal_list()
        sync_cluster_size_controls = globals().get("_sync_cluster_size_controls")
        if callable(sync_cluster_size_controls):
            sync_cluster_size_controls()
        populate_map_normal_list()
        populate_map_memory_list()
        select_map_profile_tab()
        sync_map_mode_controls()
        log_message(f"[TEMPLATE] '{name}' yüklendi.")
        if template_price_meta:
            log_message(
                f"[PRICE] Lig={template_price_meta.get('league', '?')} "
                f"Tarama={template_price_meta.get('scanned_at', '?')} "
                f"Aralik={template_price_meta.get('range_basis', 'ilk ilanlar')}"
            )
    except Exception as e:
        gui_error(f"Yüklenemedi: {e}")

def save_template():
    global stop_on_two_match_config, no_annul_combs_config
    if app_mode.get() == "socket":
        gui_warn("Socket modunda template kullanilmiyor.")
        return
    current_name = template_var.get().strip()
    mode_label = (
        "Map"
        if app_mode.get() == "map"
        else (
            "Base Jewel"
            if app_mode.get() == "base_jewel"
            else ("Item" if app_mode.get() == "item" else "Cluster")
        )
    )
    name = simpledialog.askstring(
        "Save Template",
        f"{mode_label} template name:",
        initialvalue=current_name,
        parent=root,
    )
    if name is None:
        return
    name = name.strip()
    if not name:
        gui_warn("Template adı girin.")
        return
    try:
        populate_comb_list()
        is_map = app_mode.get() == "map"
        is_base_jewel = app_mode.get() == "base_jewel"
        is_item = app_mode.get() == "item"
        data = {
            "app_mode": app_mode.get(),
            "craft_logic": (
                "base_jewel"
                if is_base_jewel
                else ("generic_item" if is_item else craft_logic.get())
            ),
            "chain_craft": chain_craft.get(),
            "chain_count": int(chain_count_var.get() or 1),
        }
        if is_map:
            def _optional_int(var):
                raw = var.get().strip()
                return int(raw) if raw else None
            data.update({
                "map_profile": map_rules.normalize_profile(map_profile_var.get()),
                "map_normal_forbidden": list(map_normal_forbidden),
                "map_memory_forbidden": list(map_memory_forbidden),
                "map_quantity_thresh": _optional_int(map_quantity_thresh),
                "map_rarity_thresh": _optional_int(map_rarity_thresh),
                "map_pack_size_thresh": _optional_int(map_pack_size_thresh),
                "map_use_exalt": map_use_exalt.get(),
            })
        elif is_item:
            item_level = int(item_level_var.get().strip())
            required_count = int(item_required_count_var.get().strip())
            chance_to_unique = item_chance_to_unique_var.get()
            if not chance_to_unique and not item_target_ids:
                raise ValueError("En az bir Item Craft hedef modu sec.")
            if (
                not chance_to_unique
                and (required_count < 1 or required_count > len(item_target_ids))
            ):
                raise ValueError("Gerekli hedef sayisi secili hedef sayisini asamaz.")
            data.update({
                "item_base": item_base_var.get().strip(),
                "item_influence": item_influence_var.get().strip() or "None",
                "item_level": item_level,
                "item_target_ids": list(item_target_ids),
                "item_required_count": required_count,
                "item_use_augment": item_use_augment_var.get(),
                "item_use_regal": item_use_regal_var.get(),
                "item_use_exalt": item_use_exalt_var.get(),
                "item_use_annul": item_use_annul_var.get(),
                "item_chance_to_unique": chance_to_unique,
            })
        elif is_base_jewel:
            crit_count = int(base_jewel_crit_count_var.get().strip())
            life_count = 1 if base_jewel_require_life_var.get() else 0
            regal_min = int(base_jewel_regal_min_var.get().strip())
            no_regal = base_jewel_no_regal_var.get()
            if crit_count < 0 or crit_count + life_count < 1 or crit_count + life_count > 4:
                raise ValueError("Toplam Base Jewel hedef sayisi 1-4 arasinda olmali.")
            if regal_min < 1 or regal_min > 2:
                raise ValueError("Regal esigi 1 veya 2 olmali.")
            data.update({
                "base_jewel_crit_count": crit_count,
                "base_jewel_life_count": life_count,
                "base_jewel_regal_min": regal_min,
                "base_jewel_no_regal": no_regal,
                "base_jewel_use_augment": base_jewel_use_augment_var.get(),
                "base_jewel_use_exalt": base_jewel_use_exalt_var.get(),
                "base_jewel_use_annul": base_jewel_use_annul_var.get(),
                "base_jewel_crit_mods": get_base_jewel_crit_patterns(),
                "base_jewel_life_mods": list(DEFAULT_BASE_JEWEL_LIFE_MODS),
            })
        else:
            save_combos = (
                template_comb_craft_data
                if market_cluster_template_active
                else comb_craft_data
            )
            save_prices = (
                template_combo_price_data
                if market_cluster_template_active
                else combo_price_data
            )
            save_stop_two = (
                template_stop_on_two_match_config
                if market_cluster_template_active
                else stop_on_two_match_config
            )
            save_annul = (
                template_annul_combs_config
                if market_cluster_template_active
                else annul_combs_config
            )
            save_no_annul = (
                template_no_annul_combs_config
                if market_cluster_template_active
                else no_annul_combs_config
            )
            save_solo_regal = (
                template_solo_regal_mods_config
                if market_cluster_template_active
                else solo_regal_mods_config
            )
            save_no_regal = (
                template_no_regal_mods_config
                if market_cluster_template_active
                else no_regal_mods_config
            )
            data.update({
                "cluster_size": cluster_size_var.get(),
                "cluster_meta": dict(template_cluster_meta),
                "augment_mode": augment_mode.get(),
                "cluster_fracture_mode": cluster_fracture_mode_var.get(),
                "cluster_fractured_target": cluster_fractured_target_var.get(),
                "cluster_no_regal_two_mods": cluster_no_regal_two_var.get(),
                "cluster_small_stop_three_mods": (
                    cluster_size_var.get() == "small"
                    and cluster_small_stop_three_var.get()
                ),
                "use_exalt": use_exalt.get(),
                "use_annul": use_annul.get(),
                "comb_craft_data": save_combos,
                "combo_prices": save_prices,
                "price_meta": template_price_meta,
                "stop_on_two_match": save_stop_two,
                "annul_combs": save_annul,
                "no_annul_combs": save_no_annul,
                "solo_regal_mods": save_solo_regal,
                "no_regal_mods": save_no_regal,
            })
        with open(template_path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        template_var.set(name)
        gui_info(f"Template '{name}' kaydedildi.")
        refresh_templates()
    except Exception as e:
        gui_error(f"Kaydedilemedi: {e}")

def delete_template():
    if app_mode.get() == "socket":
        gui_warn("Socket modunda template kullanilmiyor.")
        return
    name = template_var.get().strip()
    if not name:
        gui_warn("Önce bir template seçin.")
        return
    path = template_path(name)
    if os.path.exists(path):
        if messagebox.askyesno("Sil", f"'{name}' template'ini silmek istiyor musunuz?", parent=root):
            os.remove(path)
            gui_info(f"Template '{name}' silindi.")
            refresh_templates()
    else:
        gui_error(f"'{name}' bulunamadı.")

# ================ ORB LOCATIONS UI (CALIBRATION) ================
class OrbLocationsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.window_w = WINDOW_W
        self.window_h = WINDOW_H
        self.title_h = 21
        self._drag_x = 0
        self._drag_y = 0
        self._rounding_after_id = None
        self._last_rounded_size = None

        self.title("Orb Locations")
        self.attributes("-topmost", True)
        self.configure(bg="#2b2b2b")
        try:
            parent.update_idletasks()
            x = max(0, parent.winfo_x() - self.window_w - 2)
            y = parent.winfo_y()
            self.geometry(f"{self.window_w}x{self.window_h}+{x}+{y}")
        except Exception:
            self.geometry(f"{self.window_w}x{self.window_h}")
        self.overrideredirect(True)
        self.resizable(False, False)

        self.title_grip = tk.Frame(self, bg="#2b2b2b", height=self.title_h, highlightthickness=0, bd=0)
        self.title_grip.place(x=0, y=0, width=self.window_w, height=self.title_h)
        self.title_grip.bind("<ButtonPress-1>", self.start_move)
        self.title_grip.bind("<B1-Motion>", self.on_move)

        self.minimize_btn = tk.Button(
            self,
            text="—",
            command=self._minimize_window,
            bg="#2b2b2b",
            fg="#e6e6e6",
            activebackground="#3a3a3a",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            font=("Tahoma", 9, "bold"),
            padx=0,
            pady=0,
            highlightthickness=0,
        )
        self.minimize_btn.place(x=self.window_w - 44, y=0, width=22, height=18)

        self.close_btn = tk.Button(
            self,
            text="×",
            command=self.destroy,
            bg="#2b2b2b",
            fg="#e6e6e6",
            activebackground="#5a2a2a",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            font=("Tahoma", 9, "bold"),
            padx=0,
            pady=0,
            highlightthickness=0,
        )
        self.close_btn.place(x=self.window_w - 22, y=0, width=22, height=18)

        body = ttk.Frame(self)
        body.place(x=0, y=self.title_h, width=self.window_w, height=self.window_h - self.title_h)

        tree_wrap = ttk.Frame(body)
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=(4, 6))

        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("orb", "x", "y"),
            show="headings",
            height=18,
            style="Orb.Treeview",
        )
        self.tree.heading("orb", text="Item")
        self.tree.heading("x", text="X")
        self.tree.heading("y", text="Y")
        self.tree.column("orb", width=142, anchor="w", stretch=False)
        self.tree.column("x", width=64, anchor="center", stretch=False)
        self.tree.column("y", width=64, anchor="center", stretch=False)
        tv_style = ttk.Style(self)
        tv_style.configure(
            "Orb.Treeview",
            background="#0c0c0c",
            foreground="#d7d7d7",
            fieldbackground="#0c0c0c",
            font=("Tahoma", 7),
            rowheight=18,
            borderwidth=0,
            relief="flat",
        )
        tv_style.configure(
            "Orb.Treeview.Heading",
            background="#3a3a3a",
            foreground="#f0f0f0",
            bordercolor="#0f0f0f",
            darkcolor="#1f1f1f",
            lightcolor="#565656",
            relief="raised",
            font=("Tahoma", 7, "bold"),
        )
        tv_style.map("Orb.Treeview", background=[("selected", "#444444")], foreground=[("selected", "#ffffff")])
        tv_style.map("Orb.Treeview.Heading", background=[("active", "#4a4a4a")])
        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.tag_configure("set", foreground="#fff")
        self.tree.tag_configure("unset", foreground="#f55")
        self.tree.bind("<Double-Button-1>", self.on_double)
        self.bind("<Configure>", self._on_configure)
        self.bind("<Map>", self._on_restore)
        self.bind("<Visibility>", self._schedule_rounding, add="+")
        self._schedule_rounding(force=True)
        self.populate()

    def populate(self):
        self.tree.delete(*self.tree.get_children())
        locs = get_orb_locations_dict()
        items = [
            "Orb of Transmutation",
            "Orb of Alteration",
            "Orb of Augmentation",
            "Jeweller's Orb",
            "Orb of Fusing",
            "Chromatic Orb",
            "Orb of Scouring",
            "Orb of Chance",
            "Orb of Annulment",
            "Orb of Alchemy",
            "Vaal Orb",
            "Currency Stash Tab",
            "Regal Orb",
            "Chaos Orb",
            "Exalted Orb",
            "Orb of Alteration Slot 2",
            "Orb of Alteration Slot 3",
            "Orb of Alteration Slot 4",
            "Orb of Alteration Slot 5",
            "Orb of Alteration Slot 6",
            "Orb of Alteration Slot 7",
            "Orb of Alteration Slot 8",
            "Orb of Augmentation Slot 2",
            "Orb of Augmentation Slot 3",
            "Orb of Augmentation Slot 4",
            "Orb of Augmentation Slot 5",
            "Orb of Augmentation Slot 6",
            "Orb of Augmentation Slot 7",
            "Orb of Augmentation Slot 8",
            "Inventory 1. Slotun Ortası",
            "Inventory 60. Slotun Ortası",
        ]
        for name in items:
            if val := locs.get(name.lower()):
                try:
                    x, y = map(int, val.split(","))
                    self.tree.insert("", "end", values=(name, x, y), tags=("set",))
                except Exception:
                    self.tree.insert(
                        "", "end", values=(name, "hatalı", "hatalı"), tags=("unset",)
                    )
            else:
                self.tree.insert(
                    "", "end", values=(name, "ayarlanmadı", "ayarlanmadı"), tags=("unset",)
                )

    def on_double(self, _event):
        if sel := self.tree.selection():
            name = self.tree.item(sel[0])["values"][0]
            CalibrationPopup(self, name, self.on_saved)

    def on_saved(self, name, x, y):
        save_orb_location(name, x, y)
        self.populate()

    def start_move(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def on_move(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"{self.window_w}x{self.window_h}+{x}+{y}")

    def _apply_rounded_corners(self, force=False):
        try:
            width = max(self.window_w, self.winfo_width())
            height = max(self.window_h, self.winfo_height())
            size_key = (width, height)
            if not force and size_key == self._last_rounded_size:
                return
            _apply_window_rounding(self, width, height, radius=18)
            self._last_rounded_size = size_key
        except Exception:
            pass

    def _minimize_window(self):
        try:
            self.overrideredirect(False)
            self.iconify()
        except Exception:
            pass

    def _on_restore(self, _event=None):
        try:
            self.overrideredirect(True)
            self._last_rounded_size = None
            self._schedule_rounding(force=True)
        except Exception:
            pass

    def _on_configure(self, _event=None):
        self._schedule_rounding()

    def _schedule_rounding(self, _event=None, force=False):
        try:
            if self._rounding_after_id is not None:
                self.after_cancel(self._rounding_after_id)
        except Exception:
            pass
        self._rounding_after_id = self.after(45, lambda: self._apply_rounded_corners(force=force))

def calculate_inventory_slots():
    """
    Inventory 1. Slotun Ortası ve Inventory 60. Slotun Ortası koordinatlarından
    12 sütun × 5 satır = 60 slotun koordinatını hesaplar.
    """
    orbs = get_orb_locations_dict()
    first = orbs.get("inventory 1. slotun ortası")
    last  = orbs.get("inventory 60. slotun ortası")
    if not first or not last:
        return {}
    try:
        fx, fy = map(int, first.split(","))
        lx, ly = map(int, last.split(","))
    except Exception:
        return {}

    step_x = (lx - fx) / 11  # 12 sütun → 11 adım
    step_y = (ly - fy) / 4   # 5 satır → 4 adım

    slots = {}
    slot = 1
    for col in range(12):
        for row in range(5):
            cx = round(fx + col * step_x)
            cy = round(fy + row * step_y)
            slots[f"slot_{slot}"] = (cx, cy)
            slot += 1
    return slots

def save_orb_location(name, x, y):
    if not settings_cfg.has_section("OrbLocations"):
        settings_cfg.add_section("OrbLocations")
    settings_cfg.set("OrbLocations", name.lower(), f"{x},{y}")
    save_settings_debounced()
    if name.lower() in ("inventory 1. slotun ortası", "inventory 60. slotun ortası"):
        slots = calculate_inventory_slots()
        if slots:
            log_message(f"[SETUP] {len(slots)} envanter slotu hesaplandı.")

def _apply_window_rounding(win, width, height, radius=18):
    try:
        import ctypes
        win.update_idletasks()
        hwnd = win.winfo_id()
        try:
            GA_ROOT = 2
            root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
            if root_hwnd:
                hwnd = root_hwnd
        except Exception:
            pass
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
        ctypes.windll.user32.SetWindowRgn(hwnd, region, True)
    except Exception:
        pass

class CalibrationPopup(tk.Toplevel):
    def __init__(self, parent, orb_name, on_save_cb):
        super().__init__(parent)
        self.title("Kalibrasyon")
        self.attributes("-topmost", True, "-alpha", 0.7)
        self.configure(bg="#2b2b2b")
        self.geometry("210x100")
        self.resizable(False, False)
        self.orb_name, self.on_save_cb = orb_name, on_save_cb
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.on_move)
        frame = tk.Frame(
            self,
            bg="#000",
            highlightbackground="#f00",
            highlightthickness=2,
            width=40,
            height=40,
        )
        frame.place(x=10, y=15)
        cv = tk.Canvas(frame, width=36, height=36, bg="#000", highlightthickness=0)
        cv.place(x=1, y=1)
        cv.create_line(18, 6, 18, 30, fill="#f00", width=1)
        cv.create_line(6, 18, 30, 18, fill="#f00", width=1)
        ttk.Label(
            self,
            text=orb_name,
            foreground="#ffc",
            background="#2b2b2b",
            font=("Segoe UI", 9, "bold"),
        ).place(x=70, y=10)
        self.lbl_x = ttk.Label(self, text="X: ...", background="#2b2b2b", foreground="#fff")
        self.lbl_x.place(x=70, y=30)
        self.lbl_y = ttk.Label(self, text="Y: ...", background="#2b2b2b", foreground="#fff")
        self.lbl_y.place(x=70, y=50)
        ttk.Button(self, text="Confirm", style="Dark.TButton", command=self.confirm).place(
            relx=0.5, rely=0.85, anchor="center"
        )
        self.update_labels()

    def start_move(self, event):
        self._x, self._y = event.x, event.y

    def on_move(self, event):
        self.geometry(
            f"+{self.winfo_x() + (event.x - self._x)}+{self.winfo_y() + (event.y - self._y)}"
        )

    def _center_screen_xy(self):
        return (self.winfo_rootx() + 29, self.winfo_rooty() + 34)

    def update_labels(self):
        cx, cy = self._center_screen_xy()
        self.lbl_x.config(text=f"X: {cx}")
        self.lbl_y.config(text=f"Y: {cy}")
        self.after(100, self.update_labels)

    def confirm(self):
        cx, cy = self._center_screen_xy()
        self.on_save_cb(self.orb_name, cx, cy)
        self.destroy()

# ================ GUI ================
root = tk.Tk()
root.title(APP_NAME)
try:
    root.iconbitmap(default=APP_ICON_ICO)
except Exception:
    pass
template_var = tk.StringVar()
# Kaydedilmiş pencere konumunu yükle
_saved_pos = settings_cfg.get("General", "window_pos", fallback="")
if _saved_pos:
    root.geometry(f"{WINDOW_W}x{WINDOW_H}+{_saved_pos}")
else:
    root.geometry(f"{WINDOW_W}x{WINDOW_H}")
root.configure(bg="#2b2b2b")
root.overrideredirect(True)
root.resizable(False, False)

style = ttk.Style()
style.theme_use("clam")
style.configure("TFrame", background="#2b2b2b")
style.configure("TLabel", background="#2b2b2b", foreground="#d7d7d7", font=("Tahoma", 8))
style.configure(
    "TRadiobutton", background="#2b2b2b", foreground="#d7d7d7", font=("Tahoma", 8), padding=(0, 1)
)
style.configure(
    "Compact.TRadiobutton", background="#2b2b2b", foreground="#d7d7d7", font=("Tahoma", 8), padding=(0, 0)
)
style.configure(
    "TCheckbutton", background="#2b2b2b", foreground="#d7d7d7", font=("Tahoma", 8), padding=(0, 1)
)
style.configure(
    "Aligned.TCheckbutton", background="#2b2b2b", foreground="#d7d7d7", font=("Tahoma", 8), padding=(0, 0)
)
style.configure(
    "Dark.TButton",
    background="#3a3a3a",
    foreground="#f0f0f0",
    bordercolor="#0f0f0f",
    darkcolor="#1f1f1f",
    lightcolor="#565656",
    relief="raised",
    borderwidth=1,
    focusthickness=0,
    padding=(8, 2),
)
style.map("Dark.TButton", background=[("active", "#4a4a4a"), ("pressed", "#2d2d2d")], foreground=[("disabled", "#8e8e8e")])
style.configure(
    "Dark.TCombobox",
    fieldbackground="#0c0c0c",
    background="#3a3a3a",
    foreground="#f0f0f0",
    bordercolor="#0f0f0f",
    lightcolor="#505050",
    darkcolor="#1f1f1f",
    arrowcolor="#dcdcdc",
    padding=(2, 1),
)
style.configure("TNotebook", background="#2b2b2b", borderwidth=0, tabmargins=[0, 2, 0, 0])
style.configure(
    "TNotebook.Tab",
    background="#3a3a3a",
    foreground="#f0f0f0",
    borderwidth=1,
    lightcolor="#565656",
    darkcolor="#1f1f1f",
    bordercolor="#0f0f0f",
    relief="raised",
    focusthickness=0,
    padding=[8, 4],
)
style.map(
    "TNotebook.Tab",
    background=[("selected", "#4a4a4a"), ("active", "#444444")],
    foreground=[("selected", "#ffffff"), ("active", "#ffffff")],
    lightcolor=[("selected", "#6a6a6a"), ("active", "#606060")],
    darkcolor=[("selected", "#202020"), ("active", "#242424")],
)
style.map("TCheckbutton", foreground=[("disabled", "#cfcfcf")], background=[("disabled", "#2b2b2b")])
style.map("TRadiobutton", foreground=[("disabled", "#cfcfcf")], background=[("disabled", "#2b2b2b")])

_drag_state = {"x": 0, "y": 0}
tray_icon = None
tray_thread = None
tray_lock = threading.Lock()

def _start_drag(event):
    _drag_state["x"] = event.x_root - root.winfo_x()
    _drag_state["y"] = event.y_root - root.winfo_y()

def _do_drag(event):
    x = event.x_root - _drag_state["x"]
    y = event.y_root - _drag_state["y"]
    root.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+{y}")
    positioner = globals().get("position_flask_guide_panel")
    if positioner:
        positioner()
    trade_positioner = globals().get("position_cluster_trade_panel")
    if trade_positioner:
        trade_positioner()

def _apply_rounded_corners():
    try:
        width = max(WINDOW_W, root.winfo_width())
        height = max(WINDOW_H, root.winfo_height())
        _apply_window_rounding(root, width, height, radius=18)
    except Exception:
        pass

def _schedule_root_rounding(_event=None):
    try:
        root.after_idle(_apply_rounded_corners)
    except Exception:
        pass

def _build_tray_image():
    try:
        if os.path.isfile(APP_ICON_PNG):
            return Image.open(APP_ICON_PNG).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    except Exception:
        pass
    img = Image.new("RGBA", (64, 64), (43, 43, 43, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((6, 6, 58, 58), radius=12, fill=(58, 58, 58, 255), outline=(120, 120, 120, 255))
    draw.line((20, 24, 44, 24), fill=(102, 199, 240, 255), width=4)
    draw.line((20, 34, 44, 34), fill=(220, 220, 220, 255), width=4)
    draw.line((20, 44, 44, 44), fill=(220, 220, 220, 255), width=4)
    return img

def _stop_tray_icon():
    global tray_icon
    with tray_lock:
        icon = tray_icon
        tray_icon = None
    if icon:
        try:
            icon.stop()
        except Exception:
            pass

def _restore_from_tray():
    def _restore():
        _stop_tray_icon()
        try:
            root.deiconify()
            root.overrideredirect(True)
            root.after(10, _apply_rounded_corners)
            root.lift()
            root.focus_force()
        except Exception:
            pass
        on_main_restore()
    root.after(0, _restore)

def _exit_from_tray():
    root.after(0, on_main_close)

def _start_tray_icon():
    global tray_icon, tray_thread
    if not TRAY_AVAILABLE:
        return False
    with tray_lock:
        if tray_icon is not None:
            return True
        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda icon, item: _restore_from_tray(), default=True),
            pystray.MenuItem("Exit", lambda icon, item: _exit_from_tray()),
        )
        tray_icon = pystray.Icon("waukeen_crafting_assistant", _build_tray_image(), APP_NAME, menu)
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
        return True

def _minimize_window():
    try:
        if _start_tray_icon():
            on_main_minimize()
            root.withdraw()
            return
        root.overrideredirect(False)
        root.iconify()
    except Exception:
        pass

title_bar_bg = "#2b2b2b"
title_grip = tk.Frame(root, bg=title_bar_bg, height=21, highlightthickness=0, bd=0)
title_grip.place(x=0, y=0, width=WINDOW_W, height=21)
title_grip.bind("<ButtonPress-1>", _start_drag)
title_grip.bind("<B1-Motion>", _do_drag)

title_label = tk.Label(
    root,
    text=APP_SHORT_NAME,
    bg=title_bar_bg,
    fg="#d6ad63",
    font=("Tahoma", 8, "bold"),
    padx=0,
    pady=0,
)
title_label.place(x=6, y=1, height=18)
title_label.bind("<ButtonPress-1>", _start_drag)
title_label.bind("<B1-Motion>", _do_drag)

minimize_btn = tk.Button(
    root,
    text="—",
    command=_minimize_window,
    bg=title_bar_bg,
    fg="#e6e6e6",
    activebackground="#3a3a3a",
    activeforeground="#ffffff",
    relief="flat",
    bd=0,
    font=("Tahoma", 9, "bold"),
    padx=0,
    pady=0,
    highlightthickness=0,
)
minimize_btn.place(x=WINDOW_W - 44, y=0, width=22, height=18)

close_btn = tk.Button(
    root,
    text="×",
    command=lambda: on_main_close(),
    bg=title_bar_bg,
    fg="#e6e6e6",
    activebackground="#5a2a2a",
    activeforeground="#ffffff",
    relief="flat",
    bd=0,
    font=("Tahoma", 9, "bold"),
    padx=0,
    pady=0,
    highlightthickness=0,
)
close_btn.place(x=WINDOW_W - 22, y=0, width=22, height=18)
root.after_idle(_apply_rounded_corners)
root.after(10, _apply_rounded_corners)
root.after(40, _apply_rounded_corners)
root.after(100, _apply_rounded_corners)

craft_logic = tk.StringVar(value="Rare (regal)")
augment_mode = tk.StringVar(value="Use if needed")
use_exalt, use_annul = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
cluster_no_regal_two_var = tk.BooleanVar(value=False)
cluster_small_stop_three_var = tk.BooleanVar(value=False)
cluster_fracture_mode_var = tk.StringVar(value="unfractured")
cluster_fractured_target_var = tk.StringVar(value="")
cluster_size_var = tk.StringVar(
    value=settings_cfg.get("General", "cluster_size", fallback="large")
)
if cluster_size_var.get() not in {"small", "medium", "large"}:
    cluster_size_var.set("large")
chain_craft = tk.BooleanVar(value=False)
affix_weight_var = tk.StringVar(value="1")
delay_var = tk.StringVar(value=settings_cfg.get("General", "delay", fallback="30"))
safe_mode_var = tk.BooleanVar(value=False)
chain_count_var = tk.StringVar(value="1")
post_craft_action_var = tk.StringVar(
    value=normalize_post_action(
        settings_cfg.get("General", "post_craft_action", fallback=POST_ACTION_NONE)
    )
)
_saved_cluster_price_filter = settings_cfg.get(
    "General", "cluster_price_filter", fallback="2d+"
)
if _saved_cluster_price_filter not in CLUSTER_PRICE_FILTERS:
    _saved_cluster_price_filter = "2d+"
cluster_price_filter_var = tk.StringVar(value=_saved_cluster_price_filter)
cluster_price_filter_status_var = tk.StringVar(value="No saved market data")
map_orb_mode = tk.StringVar(value="chaos")   # "chaos" | "alchemy" | "alchemy_vaal"
map_profile_var = tk.StringVar(value=map_rules.PROFILE_NORMAL)
map_normal_forbidden = []
map_memory_forbidden = []
map_quantity_thresh = tk.StringVar(value="")
map_rarity_thresh = tk.StringVar(value="")
map_pack_size_thresh = tk.StringVar(value="")
map_use_exalt = tk.BooleanVar(value=False)
socket_use_jeweller_var = tk.BooleanVar(value=True)
socket_use_fusing_var = tk.BooleanVar(value=True)
socket_use_chromatic_var = tk.BooleanVar(value=False)
socket_target_sockets_var = tk.StringVar(value="6")
socket_target_links_var = tk.StringVar(value="6")
socket_target_red_var = tk.StringVar(value="1")
socket_target_green_var = tk.StringVar(value="4")
socket_target_blue_var = tk.StringVar(value="1")
base_jewel_crit_count_var = tk.StringVar(value="3")
base_jewel_require_life_var = tk.BooleanVar(value=False)
base_jewel_regal_min_var = tk.StringVar(value="2")
base_jewel_no_regal_var = tk.BooleanVar(value=False)
base_jewel_use_augment_var = tk.BooleanVar(value=True)
base_jewel_use_exalt_var = tk.BooleanVar(value=True)
base_jewel_use_annul_var = tk.BooleanVar(value=True)
item_base_var = tk.StringVar(value="")
item_influence_var = tk.StringVar(value="")
item_level_var = tk.StringVar(value="75")
item_required_count_var = tk.StringVar(value="1")
item_use_augment_var = tk.BooleanVar(value=True)
item_use_regal_var = tk.BooleanVar(value=False)
item_use_exalt_var = tk.BooleanVar(value=False)
item_use_annul_var = tk.BooleanVar(value=False)
item_chance_to_unique_var = tk.BooleanVar(value=False)
item_mod_search_var = tk.StringVar(value="")
item_affix_filter_var = tk.StringVar(value="All")
item_target_ids = []
item_mod_pool_entries = []
item_mod_pool_visible = [False]
flask_guide_visible = [False]
cluster_trade_visible = [False]
voyage_auto_place_var = tk.BooleanVar(
    value=settings_cfg.getboolean("Voyage", "auto_place", fallback=True)
)
auto_flask_life_enabled_var = tk.BooleanVar(
    value=settings_cfg.getboolean("AutoFlask", "life_enabled", fallback=True)
)
auto_flask_life_threshold_var = tk.StringVar(
    value=settings_cfg.get("AutoFlask", "life_threshold", fallback="98")
)
auto_flask_life_key_var = tk.StringVar(
    value=settings_cfg.get("AutoFlask", "life_key", fallback="1")
)
auto_flask_mana_enabled_var = tk.BooleanVar(
    value=settings_cfg.getboolean("AutoFlask", "mana_enabled", fallback=False)
)
auto_flask_mana_threshold_var = tk.StringVar(
    value=settings_cfg.get("AutoFlask", "mana_threshold", fallback="25")
)
auto_flask_mana_key_var = tk.StringVar(
    value=settings_cfg.get("AutoFlask", "mana_key", fallback="2")
)

# Global mode and completion controls.
settings_bar = ttk.Frame(root)
settings_bar.place(x=PADX, y=PADY + 14, width=WINDOW_W - 2 * PADX, height=24)
settings_bar.grid_columnconfigure(1, weight=1)
settings_bar.grid_columnconfigure(3, weight=1)

app_mode = tk.StringVar(value="cluster")
MODE_DISPLAY_TO_VALUE = {
    "Cluster": "cluster",
    "Map": "map",
    "Socket": "socket",
    "Jewel": "base_jewel",
    "Item": "item",
    "Voyage": "voyage",
    "Auto Flask": "auto_flask",
}
MODE_VALUE_TO_DISPLAY = {value: label for label, value in MODE_DISPLAY_TO_VALUE.items()}
startup_mode = settings_cfg.get("General", "last_mode", fallback="cluster")
if startup_mode not in MODE_VALUE_TO_DISPLAY:
    startup_mode = "cluster"
POST_ACTION_DISPLAY_TO_VALUE = {
    "Bir sey yapma": POST_ACTION_NONE,
    "Oyunu kapat": POST_ACTION_CLOSE_GAME,
    "PC'yi kapat": POST_ACTION_SHUTDOWN_PC,
}
POST_ACTION_VALUE_TO_DISPLAY = {
    value: label for label, value in POST_ACTION_DISPLAY_TO_VALUE.items()
}

mode_selector_var = tk.StringVar(value=MODE_VALUE_TO_DISPLAY[startup_mode])
post_action_display_var = tk.StringVar(
    value=POST_ACTION_VALUE_TO_DISPLAY.get(
        post_craft_action_var.get(), POST_ACTION_VALUE_TO_DISPLAY[POST_ACTION_NONE]
    )
)

ttk.Label(settings_bar, text="Mod:").grid(row=0, column=0, sticky="w", padx=(0, 3))
mode_selector = ttk.Combobox(
    settings_bar,
    textvariable=mode_selector_var,
    values=tuple(MODE_DISPLAY_TO_VALUE),
    state="readonly",
    width=12,
    style="Dark.TCombobox",
)
mode_selector.grid(row=0, column=1, sticky="ew", padx=(0, 5))

ttk.Label(settings_bar, text="Bitince:").grid(row=0, column=2, sticky="w", padx=(0, 3))
post_action_selector = ttk.Combobox(
    settings_bar,
    textvariable=post_action_display_var,
    values=tuple(POST_ACTION_DISPLAY_TO_VALUE),
    state="readonly",
    width=12,
    style="Dark.TCombobox",
)
post_action_selector.grid(row=0, column=3, sticky="ew", padx=(0, 4))

global_settings_btn = ttk.Button(settings_bar, text="⚙", width=3, style="Dark.TButton")
global_settings_btn.grid(row=0, column=4, sticky="e", padx=(0, 3))

always_on_top_var = tk.BooleanVar(value=True)
def toggle_always_on_top():
    val = always_on_top_var.get()
    root.attributes("-topmost", val)
    if log_window and log_window.winfo_exists():
        log_window.attributes("-topmost", val)
def toggle_safe_mode():
    safe_mode_var.set(False)
    settings_cfg.set("General", "safe_mode", "False")
    save_settings_debounced()
always_on_top_cb = ttk.Checkbutton(
    settings_bar,
    text="📌",
    variable=always_on_top_var,
    command=toggle_always_on_top,
)
always_on_top_cb.grid(row=0, column=5, sticky="e", padx=(0, 3))
always_on_top_cb.config(text="\U0001F4CC", width=2)
safe_mode_cb = ttk.Checkbutton(
    settings_bar,
    text="Safe",
    variable=safe_mode_var,
    command=toggle_safe_mode,
)
safe_mode_cb.grid(row=0, column=6, sticky="e")
safe_mode_cb.state(["disabled"])
toggle_safe_mode()
root.attributes("-topmost", True)

# Cluster template sections.
cluster_size_bar = tk.Frame(root, bg="#202020", bd=0, highlightthickness=0)
cluster_size_buttons = {}


def _clear_cluster_section_session():
    global template_price_meta, template_cluster_meta
    global market_cluster_template_active, is_effect35_template

    template_var.set("")
    for mapping in (
        comb_craft_data,
        combo_price_data,
        template_comb_craft_data,
        template_combo_price_data,
    ):
        mapping.clear()
    for collection in (
        stop_on_two_match_config,
        annul_combs_config,
        no_annul_combs_config,
        solo_regal_mods_config,
        no_regal_mods_config,
        template_stop_on_two_match_config,
        template_annul_combs_config,
        template_no_annul_combs_config,
        template_solo_regal_mods_config,
        template_no_regal_mods_config,
    ):
        collection.clear()
    template_price_meta = {}
    template_cluster_meta = {}
    market_cluster_template_active = False
    is_effect35_template = False
    cluster_no_regal_two_var.set(False)
    cluster_fracture_mode_var.set("unfractured")
    cluster_fractured_target_var.set("")
    cluster_small_stop_three_var.set(False)
    _clear_comb_match_caches()


def _sync_cluster_size_controls():
    is_small = cluster_size_var.get() == "small"
    if is_small:
        cluster_small_stop_three_cb.pack(
            side="left",
            padx=(0, 4),
        )
    else:
        cluster_small_stop_three_cb.pack_forget()


def _on_cluster_size_selected():
    settings_cfg.set("General", "cluster_size", cluster_size_var.get())
    save_settings_debounced()
    _clear_cluster_section_session()
    refresh_templates()
    populate_comb_list()
    populate_stop_two_list()
    populate_annul_combs_list()
    populate_solo_regal_list()
    populate_no_regal_list()
    _sync_cluster_size_controls()


for column, (label, value) in enumerate(
    (("Small", "small"), ("Medium", "medium"), ("Large", "large"))
):
    button = tk.Radiobutton(
        cluster_size_bar,
        text=label,
        value=value,
        variable=cluster_size_var,
        command=_on_cluster_size_selected,
        indicatoron=False,
        bg="#262626",
        fg="#f0f0f0",
        activebackground="#4b4028",
        activeforeground="#ffffff",
        selectcolor="#6a542b",
        relief="flat",
        bd=0,
        highlightthickness=0,
        font=("Segoe UI", 8, "bold"),
    )
    button.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 2, 0))
    cluster_size_bar.grid_columnconfigure(column, weight=1)
    cluster_size_buttons[value] = button


# template row
top = ttk.Frame(root)
top.place(x=PADX, y=PADY + 66, width=WINDOW_W - 2 * PADX, height=56)
top.grid_columnconfigure(0, weight=1, uniform="top_btns")
top.grid_columnconfigure(1, weight=1, uniform="top_btns")
top.grid_columnconfigure(2, weight=1, uniform="top_btns")
top.grid_columnconfigure(3, weight=1, uniform="top_btns")
template_cb = ttk.Combobox(
    top,
    textvariable=template_var,
    values=list_templates_from_folder(),
    state="normal",
    style="Dark.TCombobox",
)
template_cb.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 4))
template_cb.bind("<<ComboboxSelected>>", lambda e: load_template())
save_template_btn = ttk.Button(top, text="Save", style="Dark.TButton", command=save_template)
save_template_btn.grid(row=1, column=0, padx=(0, 2), sticky="ew")
delete_template_btn = ttk.Button(
    top, text="Delete", style="Dark.TButton", command=delete_template
)
delete_template_btn.grid(row=1, column=1, padx=(0, 2), sticky="ew")
top_log_btn = ttk.Button(top, text="Log", style="Dark.TButton", command=lambda: toggle_log_window())
top_log_btn.grid(row=1, column=2, padx=(0, 2), sticky="ew")
settings_btn = ttk.Button(top, text="âš™", style="Dark.TButton")
settings_btn.grid(row=1, column=3, sticky="ew")
settings_btn.config(text="Settings")

def show_top_controls():
    if app_mode.get() == "cluster":
        cluster_size_bar.place(
            x=PADX,
            y=PADY + 42,
            width=WINDOW_W - 2 * PADX,
            height=22,
        )
        top_y = PADY + 66
    else:
        cluster_size_bar.place_forget()
        top_y = PADY + 42
    top.place(x=PADX, y=top_y, width=WINDOW_W - 2 * PADX, height=56)

def hide_top_controls():
    cluster_size_bar.place_forget()
    top.place_forget()

def configure_top_controls_for_socket_mode(enabled=False):
    try:
        template_cb.config(state="disabled" if enabled else "readonly")
    except Exception:
        pass
    try:
        if enabled:
            save_template_btn.state(["disabled"])
            delete_template_btn.state(["disabled"])
            settings_btn.config(text="Orb Locations", command=lambda: OrbLocationsWindow(root))
        else:
            save_template_btn.state(["!disabled"])
            delete_template_btn.state(["!disabled"])
            settings_btn.config(text="Settings", command=toggle_settings_panel)
    except Exception:
        pass

socket_frame = ttk.Frame(root)
socket_frame.configure(padding=(6, 6))

ttk.Label(socket_frame, text="Socket / Link / Color Craft", font=("Segoe UI", 9, "bold")).grid(
    row=0, column=0, columnspan=8, sticky="w", pady=(0, 6)
)
ttk.Checkbutton(socket_frame, text="Jeweller's Orb", variable=socket_use_jeweller_var).grid(
    row=1, column=0, sticky="w"
)
ttk.Label(socket_frame, text="Target Sockets:").grid(row=1, column=1, sticky="e", padx=(8, 4))
tk.Entry(
    socket_frame,
    width=4,
    textvariable=socket_target_sockets_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=1, column=2, sticky="w")

ttk.Checkbutton(socket_frame, text="Orb of Fusing", variable=socket_use_fusing_var).grid(
    row=2, column=0, sticky="w", pady=(4, 0)
)
ttk.Label(socket_frame, text="Target Links:").grid(row=2, column=1, sticky="e", padx=(8, 4), pady=(4, 0))
tk.Entry(
    socket_frame,
    width=4,
    textvariable=socket_target_links_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=2, column=2, sticky="w", pady=(4, 0))

ttk.Checkbutton(socket_frame, text="Chromatic Orb", variable=socket_use_chromatic_var).grid(
    row=3, column=0, columnspan=7, sticky="w", pady=(4, 0)
)

socket_color_frame = ttk.Frame(socket_frame)
socket_color_frame.grid(row=4, column=0, columnspan=7, sticky="w", padx=(16, 0), pady=(4, 0))
ttk.Label(socket_color_frame, text="Targets:").pack(side="left", padx=(0, 6))
ttk.Label(socket_color_frame, text="R:").pack(side="left")
tk.Entry(
    socket_color_frame,
    width=3,
    textvariable=socket_target_red_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left", padx=(2, 8))
ttk.Label(socket_color_frame, text="G:").pack(side="left")
tk.Entry(
    socket_color_frame,
    width=3,
    textvariable=socket_target_green_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left", padx=(2, 8))
ttk.Label(socket_color_frame, text="B:").pack(side="left")
tk.Entry(
    socket_color_frame,
    width=3,
    textvariable=socket_target_blue_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left", padx=(2, 0))

ttk.Label(
    socket_frame,
    text="Order: sockets -> colors -> links",
    font=("Segoe UI", 8, "italic"),
).grid(row=5, column=0, columnspan=8, sticky="w", pady=(8, 2))
ttk.Label(
    socket_frame,
    text="Chromatic exact match ister. R+G+B toplami hedef socket sayisiyla ayni olmali.",
    wraplength=WINDOW_W - 2 * PADX - 20,
    justify="left",
).grid(row=6, column=0, columnspan=8, sticky="w")

auto_flask_frame = ttk.Frame(root)
auto_flask_frame.configure(padding=(9, 9))
auto_flask_frame.grid_columnconfigure(1, weight=1)

ttk.Label(
    auto_flask_frame,
    text="Auto Flask",
    font=("Segoe UI", 10, "bold"),
).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 10))

ttk.Checkbutton(
    auto_flask_frame,
    text="Life Flask",
    variable=auto_flask_life_enabled_var,
).grid(row=1, column=0, sticky="w")
ttk.Label(auto_flask_frame, text="Life <=").grid(row=1, column=1, sticky="e", padx=(12, 3))
tk.Entry(
    auto_flask_frame,
    width=4,
    textvariable=auto_flask_life_threshold_var,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=1, column=2, sticky="w")
ttk.Label(auto_flask_frame, text="%   Tus:").grid(row=1, column=3, sticky="w", padx=(3, 3))
tk.Entry(
    auto_flask_frame,
    width=3,
    textvariable=auto_flask_life_key_var,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=1, column=4, sticky="w")

ttk.Checkbutton(
    auto_flask_frame,
    text="Mana Flask",
    variable=auto_flask_mana_enabled_var,
).grid(row=2, column=0, sticky="w", pady=(7, 0))
ttk.Label(auto_flask_frame, text="Mana <=").grid(row=2, column=1, sticky="e", padx=(12, 3), pady=(7, 0))
tk.Entry(
    auto_flask_frame,
    width=4,
    textvariable=auto_flask_mana_threshold_var,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=2, column=2, sticky="w", pady=(7, 0))
ttk.Label(auto_flask_frame, text="%   Tus:").grid(row=2, column=3, sticky="w", padx=(3, 3), pady=(7, 0))
tk.Entry(
    auto_flask_frame,
    width=3,
    textvariable=auto_flask_mana_key_var,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=2, column=4, sticky="w", pady=(7, 0))

ttk.Separator(auto_flask_frame, orient="horizontal").grid(
    row=3, column=0, columnspan=5, sticky="ew", pady=(12, 9)
)
ttk.Label(
    auto_flask_frame,
    text=(
        "F4'e basmadan once kullanilabilir Life/Mana dolu olmali. Program "
        "baslangictaki kullanilabilir dolu alani %100 kabul eder; reserve edilen "
        "Life/Mana hesaba katilmaz. Utility flasklara dokunulmaz."
    ),
    wraplength=WINDOW_W - 2 * PADX - 28,
    justify="left",
).grid(row=4, column=0, columnspan=5, sticky="w")

auto_flask_status_var = tk.StringVar(value="Hazir. Path of Exile ondeyken F4 ile baslat.")
ttk.Label(
    auto_flask_frame,
    textvariable=auto_flask_status_var,
    foreground="#d6ad63",
    wraplength=WINDOW_W - 2 * PADX - 28,
    justify="left",
).grid(row=5, column=0, columnspan=5, sticky="w", pady=(12, 0))

voyage_frame = ttk.Frame(root)
voyage_frame.configure(padding=(7, 7))
voyage_frame.grid_columnconfigure(0, weight=1)
voyage_frame.grid_columnconfigure(1, weight=1)

ttk.Label(
    voyage_frame,
    text="Voyage Planner",
    font=("Segoe UI", 9, "bold"),
).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
ttk.Label(
    voyage_frame,
    text=(
        "Her butona bas, 2 saniye icinde imleci istenen merkeze gotur. "
        "Chart paneli tamamen gorunur ve en ustte olmali."
    ),
    wraplength=WINDOW_W - 2 * PADX - 24,
    justify="left",
).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

voyage_status_var = tk.StringVar(value="Kalibrasyon bekleniyor.")

def _voyage_set_status(value):
    try:
        voyage_status_var.set(str(value))
    except Exception:
        pass

def _voyage_calibrate_point(key, label):
    _voyage_set_status(f"{label}: 2 saniye icinde imleci hedefe gotur...")

    def worker():
        time.sleep(2.0)
        point = pyautogui.position()
        _voyage_save_point(key, point)
        root.after(
            0,
            lambda: _voyage_set_status(
                f"{label} kaydedildi: {point.x},{point.y}"
            ),
        )

    threading.Thread(target=worker, daemon=True).start()

calibration_specs = (
    ("chart_grid_tl", "Chart TL"),
    ("chart_grid_br", "Chart BR"),
    ("board_grid_tl", "Board TL Cell"),
    ("board_grid_br", "Board BR Cell"),
)
for button_index, (setting_key, label) in enumerate(calibration_specs):
    ttk.Button(
        voyage_frame,
        text=label,
        style="Dark.TButton",
        command=lambda key=setting_key, text=label: _voyage_calibrate_point(
            key, text
        ),
    ).grid(
        row=2 + button_index // 2,
        column=button_index % 2,
        sticky="ew",
        padx=(0, 3) if button_index % 2 == 0 else (3, 0),
        pady=(0, 4),
    )

def _voyage_save_auto_place():
    settings_cfg.set(
        "Voyage",
        "auto_place",
        "True" if voyage_auto_place_var.get() else "False",
    )
    save_settings_now()

ttk.Checkbutton(
    voyage_frame,
    text="Auto Place (Begin Voyage tiklanmaz)",
    variable=voyage_auto_place_var,
    command=_voyage_save_auto_place,
).grid(row=4, column=0, columnspan=2, sticky="w", pady=(3, 4))

ttk.Button(
    voyage_frame,
    text="Scan & Plan",
    style="Dark.TButton",
    command=start_craft,
).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 4))

voyage_status_label = ttk.Label(
    voyage_frame,
    textvariable=voyage_status_var,
    wraplength=WINDOW_W - 2 * PADX - 24,
    justify="left",
)
voyage_status_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

ttk.Label(
    voyage_frame,
    text="F4: kenarlari oku -> Chart'lari tara -> planla/yerlestir. F5: aninda kes.",
    wraplength=WINDOW_W - 2 * PADX - 24,
    justify="left",
    font=("Segoe UI", 8, "italic"),
).grid(row=7, column=0, columnspan=2, sticky="w", pady=(9, 0))

base_jewel_frame = ttk.Frame(root)
base_jewel_frame.configure(padding=(7, 7))
base_jewel_frame.grid_columnconfigure(1, weight=1)

ttk.Label(base_jewel_frame, text="Base Jewel Craft", font=("Segoe UI", 9, "bold")).grid(
    row=0, column=0, columnspan=4, sticky="w", pady=(0, 8)
)

ttk.Label(base_jewel_frame, text="Crit Multi count:").grid(row=1, column=0, sticky="w")
tk.Entry(
    base_jewel_frame,
    width=4,
    textvariable=base_jewel_crit_count_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=1, column=1, sticky="w", padx=(5, 14))
ttk.Checkbutton(
    base_jewel_frame,
    text="% maximum Life",
    variable=base_jewel_require_life_var,
).grid(row=1, column=2, columnspan=2, sticky="w")

ttk.Label(base_jewel_frame, text="Regal at target >=").grid(row=2, column=0, sticky="w", pady=(6, 0))
tk.Entry(
    base_jewel_frame,
    width=4,
    textvariable=base_jewel_regal_min_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=2, column=1, sticky="w", padx=(5, 14), pady=(6, 0))

def sync_base_jewel_no_regal_ui():
    if base_jewel_no_regal_var.get():
        base_jewel_crit_count_var.set("2")
        base_jewel_require_life_var.set(True)
        base_jewel_use_exalt_var.set(False)
        base_jewel_use_annul_var.set(False)

ttk.Checkbutton(
    base_jewel_frame,
    text="No Regal: 2 Crit OR Crit + Life",
    variable=base_jewel_no_regal_var,
    command=sync_base_jewel_no_regal_ui,
).grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 2))

base_jewel_flags = ttk.Frame(base_jewel_frame)
base_jewel_flags.grid(row=4, column=0, columnspan=4, sticky="w", pady=(2, 4))
ttk.Checkbutton(
    base_jewel_flags, text="Augment", variable=base_jewel_use_augment_var
).pack(side="left")
ttk.Checkbutton(
    base_jewel_flags, text="Exalted", variable=base_jewel_use_exalt_var
).pack(side="left", padx=(8, 0))
ttk.Checkbutton(
    base_jewel_flags, text="Annul", variable=base_jewel_use_annul_var
).pack(side="left", padx=(8, 0))

base_jewel_chain_frame = ttk.Frame(base_jewel_frame)
base_jewel_chain_frame.grid(row=5, column=0, columnspan=4, sticky="w", pady=(2, 7))
ttk.Checkbutton(base_jewel_chain_frame, text="Chain", variable=chain_craft).pack(side="left")
ttk.Label(base_jewel_chain_frame, text="Count:").pack(side="left", padx=(8, 2))
tk.Entry(
    base_jewel_chain_frame,
    width=4,
    textvariable=chain_count_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left")

ttk.Label(
    base_jewel_frame,
    text="Accepted Crit Multiplier mods (one pattern per line):",
).grid(row=6, column=0, columnspan=4, sticky="w", pady=(0, 3))
base_jewel_crit_text = tk.Text(
    base_jewel_frame,
    height=7,
    width=37,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
    selectbackground="#444",
    borderwidth=1,
    font=("Tahoma", 8),
    wrap="none",
)
base_jewel_crit_text.grid(row=7, column=0, columnspan=4, sticky="ew")

def get_base_jewel_crit_patterns():
    return [
        line.strip()
        for line in base_jewel_crit_text.get("1.0", "end").splitlines()
        if line.strip()
    ]

def set_base_jewel_crit_patterns(patterns):
    base_jewel_crit_text.delete("1.0", "end")
    base_jewel_crit_text.insert("1.0", "\n".join(str(value) for value in patterns if str(value).strip()))

set_base_jewel_crit_patterns(DEFAULT_BASE_JEWEL_CRIT_MODS)

ttk.Label(
    base_jewel_frame,
    text="Flow: Alter/Augment -> Regal -> Exalt/Annul. F5 stops immediately.",
    wraplength=WINDOW_W - 2 * PADX - 22,
    justify="left",
    font=("Segoe UI", 8, "italic"),
).grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 0))

item_frame = ttk.Frame(root)
item_frame.configure(padding=(7, 6))
item_frame.grid_columnconfigure(1, weight=1)
item_frame.grid_columnconfigure(3, weight=1)

ttk.Label(item_frame, text="Item Craft", font=("Segoe UI", 9, "bold")).grid(
    row=0, column=0, columnspan=4, sticky="w", padx=(17, 0), pady=(0, 5)
)

ttk.Label(item_frame, text="Base:").grid(row=1, column=0, sticky="w")
item_base_cb = ttk.Combobox(
    item_frame,
    textvariable=item_base_var,
    values=[],
    state="normal",
    style="Dark.TCombobox",
)
item_base_cb.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(5, 0))

ttk.Label(item_frame, text="Influence:").grid(row=2, column=0, sticky="w", pady=(5, 0))
item_influence_cb = ttk.Combobox(
    item_frame,
    textvariable=item_influence_var,
    values=["None", "Shaper", "Elder", "Warlord", "Hunter", "Crusader", "Redeemer"],
    state="readonly",
    width=10,
    style="Dark.TCombobox",
)
item_influence_cb.grid(row=2, column=1, sticky="w", padx=(5, 8), pady=(5, 0))
ttk.Label(item_frame, text="iLvl:").grid(row=2, column=2, sticky="e", pady=(5, 0))
tk.Entry(
    item_frame,
    width=4,
    textvariable=item_level_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).grid(row=2, column=3, sticky="w", padx=(4, 0), pady=(5, 0))

item_flags = ttk.Frame(item_frame)
item_flags.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 1))
ttk.Checkbutton(item_flags, text="Augment", variable=item_use_augment_var).pack(side="left")
ttk.Checkbutton(item_flags, text="Regal", variable=item_use_regal_var).pack(side="left", padx=(6, 0))
ttk.Checkbutton(item_flags, text="Exalt", variable=item_use_exalt_var).pack(side="left", padx=(6, 0))
ttk.Checkbutton(item_flags, text="Annul", variable=item_use_annul_var).pack(side="left", padx=(6, 0))

ttk.Checkbutton(
    item_frame,
    text="Chance + Scour -> Unique",
    variable=item_chance_to_unique_var,
).grid(row=4, column=0, columnspan=4, sticky="w", pady=(2, 2))

item_goal_line = ttk.Frame(item_frame)
item_goal_line.grid(row=5, column=0, columnspan=4, sticky="w", pady=(2, 5))
ttk.Label(item_goal_line, text="Need:").pack(side="left")
tk.Entry(
    item_goal_line,
    width=3,
    textvariable=item_required_count_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left", padx=(3, 9))
ttk.Checkbutton(item_goal_line, text="Chain", variable=chain_craft).pack(side="left")
ttk.Label(item_goal_line, text="Count:").pack(side="left", padx=(7, 2))
tk.Entry(
    item_goal_line,
    width=4,
    textvariable=chain_count_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left")

item_target_header = ttk.Frame(item_frame)
item_target_header.grid(row=6, column=0, columnspan=4, sticky="ew")
ttk.Label(item_target_header, text="Selected target tiers:").pack(side="left")

item_target_list = tk.Listbox(
    item_frame,
    height=6,
    bg="#000",
    fg="#fff",
    selectbackground="#444",
    highlightbackground="#000",
    font=("Tahoma", 8),
)
item_target_list.grid(row=7, column=0, columnspan=4, sticky="nsew", pady=(2, 5))

def format_item_mod_label(mod):
    tag = "P" if mod.get("type") == "prefix" else "S"
    text = " / ".join(line.get("text", "") for line in mod.get("lines", []))
    affix = mod.get("affix", "")
    return f"[{tag}] i{mod.get('level', 1)} {affix} | {text}"

def populate_item_target_list():
    item_target_list.delete(0, "end")
    mod_by_id = get_item_affix_catalog()["mod_by_id"]
    for target_id in item_target_ids:
        mod = mod_by_id.get(target_id)
        item_target_list.insert(
            "end",
            format_item_mod_label(mod) if mod else f"[missing] {target_id}",
        )

def remove_selected_item_target(event=None):
    selection = item_target_list.curselection()
    if not selection:
        return
    del item_target_ids[selection[0]]
    populate_item_target_list()

ttk.Button(
    item_target_header,
    text="Remove",
    style="Dark.TButton",
    command=remove_selected_item_target,
).pack(side="right")
item_target_list.bind("<Double-Button-1>", remove_selected_item_target)

item_mod_pool_frame = ttk.Frame(root)
item_mod_pool_frame.configure(padding=(7, 6))
item_mod_pool_frame.grid_columnconfigure(0, weight=1)
item_mod_pool_frame.grid_rowconfigure(3, weight=1)

item_pool_top = ttk.Frame(item_mod_pool_frame)
item_pool_top.grid(row=0, column=0, sticky="ew", pady=(0, 4))
ttk.Label(
    item_pool_top,
    text="Natural Mod Pool",
    font=("Segoe UI", 9, "bold"),
).pack(side="left", padx=(17, 0))
item_affix_filter_cb = ttk.Combobox(
    item_pool_top,
    textvariable=item_affix_filter_var,
    values=["All", "Prefix", "Suffix"],
    state="readonly",
    width=7,
    style="Dark.TCombobox",
)
item_affix_filter_cb.pack(side="right")

item_mod_search_entry = tk.Entry(
    item_mod_pool_frame,
    textvariable=item_mod_search_var,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
)
item_mod_search_entry.grid(row=1, column=0, sticky="ew", pady=(0, 3))

item_mod_pool_status_var = tk.StringVar(value="")
ttk.Label(
    item_mod_pool_frame,
    textvariable=item_mod_pool_status_var,
).grid(row=2, column=0, sticky="w", pady=(0, 2))

item_mod_pool_list = tk.Listbox(
    item_mod_pool_frame,
    bg="#000",
    fg="#fff",
    selectbackground="#444",
    highlightbackground="#000",
    font=("Tahoma", 8),
)
item_mod_pool_list.grid(row=3, column=0, sticky="nsew")

item_pool_buttons = ttk.Frame(item_mod_pool_frame)
item_pool_buttons.grid(row=4, column=0, sticky="ew", pady=(5, 0))

def reload_item_mod_pool(*_):
    query = item_mod_search_var.get().strip().casefold()
    affix_filter = item_affix_filter_var.get().strip().casefold()
    try:
        item_level = int(item_level_var.get().strip())
    except (ValueError, AttributeError):
        item_level = 1
    eligible = generic_item.eligible_mods(
        get_item_affix_catalog(),
        item_base_var.get().strip(),
        item_influence_var.get().strip() or "None",
        item_level,
    )
    visible = []
    for mod in eligible:
        if affix_filter in ("prefix", "suffix") and mod.get("type") != affix_filter:
            continue
        label = format_item_mod_label(mod)
        if query and query not in label.casefold():
            continue
        visible.append((mod, label))
    item_mod_pool_entries[:] = [mod for mod, _ in visible]
    item_mod_pool_list.delete(0, "end")
    for _, label in visible:
        item_mod_pool_list.insert("end", label)
    item_mod_pool_status_var.set(
        f"{item_base_var.get().strip()} | {item_influence_var.get()} | "
        f"i{item_level}: {len(visible)} mods"
    )

def add_selected_item_mod(event=None):
    selection = item_mod_pool_list.curselection()
    if not selection:
        return
    mod = item_mod_pool_entries[selection[0]]
    if mod["id"] not in item_target_ids:
        item_target_ids.append(mod["id"])
        populate_item_target_list()

def post_item_base_dropdown():
    try:
        if item_base_cb.focus_get() == item_base_cb:
            popdown = item_base_cb.tk.call(
                "ttk::combobox::PopdownWindow",
                str(item_base_cb),
            )
            listbox = f"{popdown}.f.l"
            # Native ttk moves focus to the popup on <Map>. Suppress that once
            # for autocomplete so the user can keep typing without clicking back.
            item_base_cb.tk.call(
                "bind",
                listbox,
                "<Map>",
                (
                    f"focus -force {item_base_cb}; "
                    f"bind {listbox} <Map> {{}}; "
                    "break"
                ),
            )
            item_base_cb.tk.call(
                "ttk::combobox::Post",
                str(item_base_cb),
            )
    except tk.TclError:
        pass

def filter_item_base_values(event=None):
    matches = generic_item.matching_base_names(
        get_item_affix_catalog(),
        item_base_var.get(),
    )
    item_base_cb["values"] = matches
    if event and event.keysym in ("Return", "Tab"):
        reload_item_mod_pool()
        return
    if not event or event.keysym in (
        "Down",
        "Up",
        "Left",
        "Right",
        "Escape",
    ):
        return
    try:
        if matches:
            root.after_idle(post_item_base_dropdown)
        else:
            item_base_cb.tk.call(
                "ttk::combobox::Unpost",
                str(item_base_cb),
            )
    except tk.TclError:
        pass

def toggle_item_mod_pool():
    if item_mod_pool_visible[0]:
        item_mod_pool_frame.place_forget()
        item_mod_pool_visible[0] = False
        item_frame.place(
            x=PADX,
            y=104,
            width=WINDOW_W - 2 * PADX,
            height=330,
        )
        return
    item_frame.place_forget()
    reload_item_mod_pool()
    item_mod_pool_frame.place(
        x=PADX,
        y=104,
        width=WINDOW_W - 2 * PADX,
        height=330,
    )
    item_mod_pool_visible[0] = True
    item_mod_search_entry.focus_set()

ttk.Button(
    item_pool_buttons,
    text="Add",
    style="Dark.TButton",
    command=add_selected_item_mod,
).pack(side="left", fill="x", expand=True, padx=(0, 2))
ttk.Button(
    item_pool_buttons,
    text="Back",
    style="Dark.TButton",
    command=toggle_item_mod_pool,
).pack(side="left", fill="x", expand=True, padx=(2, 0))
item_mod_pool_list.bind("<Double-Button-1>", add_selected_item_mod)
item_mod_search_var.trace_add("write", reload_item_mod_pool)
item_affix_filter_cb.bind("<<ComboboxSelected>>", reload_item_mod_pool)
item_base_cb.bind("<KeyRelease>", filter_item_base_values)
item_base_cb.bind("<<ComboboxSelected>>", reload_item_mod_pool)
item_base_cb.bind("<FocusOut>", reload_item_mod_pool)
item_influence_cb.bind("<<ComboboxSelected>>", reload_item_mod_pool)
item_level_var.trace_add("write", reload_item_mod_pool)

ttk.Button(
    item_frame,
    text="Open Mod Pool",
    style="Dark.TButton",
    command=toggle_item_mod_pool,
).grid(row=8, column=0, columnspan=4, sticky="ew")
ttk.Label(
    item_frame,
    text="Chance mode: Normal -> Chance, Magic/Rare -> Scour, Unique -> stop.",
    wraplength=WINDOW_W - 2 * PADX - 22,
    justify="left",
    font=("Segoe UI", 8, "italic"),
).grid(row=9, column=0, columnspan=4, sticky="w", pady=(5, 0))
reload_item_mod_pool()

# Offline flask recommendation drawer for Item Craft.
flask_guide_panel = tk.Toplevel(root)
flask_guide_panel.withdraw()
flask_guide_panel.overrideredirect(True)
flask_guide_panel.resizable(False, False)
flask_guide_panel.configure(bg="#2b2b2b")
flask_guide_panel.attributes("-topmost", True)
try:
    flask_guide_panel.transient(root)
except tk.TclError:
    pass

flask_guide_title_bar = tk.Frame(
    flask_guide_panel,
    bg="#2b2b2b",
    height=21,
    highlightthickness=0,
    bd=0,
)
flask_guide_title_bar.place(x=0, y=0, width=FLASK_GUIDE_W, height=21)
flask_guide_title_bar.bind("<ButtonPress-1>", _start_drag)
flask_guide_title_bar.bind("<B1-Motion>", _do_drag)
flask_guide_title_label = tk.Label(
    flask_guide_title_bar,
    text="Pot Craft Rehberi",
    bg="#2b2b2b",
    fg="#d6ad63",
    font=("Tahoma", 8, "bold"),
)
flask_guide_title_label.place(x=7, y=1, height=18)
flask_guide_title_label.bind("<ButtonPress-1>", _start_drag)
flask_guide_title_label.bind("<B1-Motion>", _do_drag)

flask_guide_body = ttk.Frame(flask_guide_panel, padding=(8, 6))
flask_guide_body.place(
    x=0,
    y=21,
    width=FLASK_GUIDE_W,
    height=FLASK_GUIDE_H - 21,
)
flask_guide_body.grid_columnconfigure(0, weight=1)
flask_guide_body.grid_rowconfigure(5, weight=1)

flask_guide_type_var = tk.StringVar(value=flask_guide.flask_types()[0])
flask_guide_overview_var = tk.StringVar(value="")
flask_guide_current_combos = []

ttk.Label(
    flask_guide_body,
    text="Pot turu:",
    font=("Segoe UI", 9, "bold"),
).grid(row=0, column=0, sticky="w")
flask_guide_type_cb = ttk.Combobox(
    flask_guide_body,
    textvariable=flask_guide_type_var,
    values=flask_guide.flask_types(),
    state="readonly",
    style="Dark.TCombobox",
)
flask_guide_type_cb.grid(row=1, column=0, sticky="ew", pady=(2, 5))
ttk.Label(
    flask_guide_body,
    textvariable=flask_guide_overview_var,
    wraplength=FLASK_GUIDE_W - 24,
    justify="left",
).grid(row=2, column=0, sticky="ew", pady=(0, 6))
ttk.Label(
    flask_guide_body,
    text="En iyi kombinasyonlar:",
    font=("Segoe UI", 9, "bold"),
).grid(row=3, column=0, sticky="w")

flask_guide_combo_list = tk.Listbox(
    flask_guide_body,
    height=6,
    exportselection=False,
    bg="#090909",
    fg="#f2f2f2",
    selectbackground="#5a4a2b",
    selectforeground="#ffffff",
    highlightbackground="#111111",
    font=("Tahoma", 8),
)
flask_guide_combo_list.grid(row=4, column=0, sticky="ew", pady=(2, 6))

flask_guide_detail_wrap = ttk.Frame(flask_guide_body)
flask_guide_detail_wrap.grid(row=5, column=0, sticky="nsew")
flask_guide_detail = tk.Text(
    flask_guide_detail_wrap,
    height=12,
    wrap="word",
    bg="#111111",
    fg="#e7e0d2",
    insertbackground="#ffffff",
    selectbackground="#5a4a2b",
    relief="sunken",
    bd=1,
    font=("Tahoma", 8),
    padx=6,
    pady=5,
)
flask_guide_detail_scroll = ttk.Scrollbar(
    flask_guide_detail_wrap,
    orient="vertical",
    command=flask_guide_detail.yview,
)
flask_guide_detail.configure(yscrollcommand=flask_guide_detail_scroll.set)
flask_guide_detail.pack(side="left", fill="both", expand=True)
flask_guide_detail_scroll.pack(side="right", fill="y")
flask_guide_detail.configure(state="disabled")

flask_guide_buttons = ttk.Frame(flask_guide_body)
flask_guide_buttons.grid(row=6, column=0, sticky="ew", pady=(6, 0))


def position_flask_guide_panel(_event=None):
    if not flask_guide_visible[0]:
        return
    try:
        root.update_idletasks()
        x = root.winfo_x() - FLASK_GUIDE_W - FLASK_GUIDE_GAP
        y = root.winfo_y()
        flask_guide_panel.geometry(
            f"{FLASK_GUIDE_W}x{FLASK_GUIDE_H}{x:+d}{y:+d}"
        )
    except tk.TclError:
        pass


def show_selected_flask_guide(_event=None):
    selection = flask_guide_combo_list.curselection()
    if not selection or not flask_guide_current_combos:
        return
    combo = flask_guide_current_combos[selection[0]]
    detail = (
        f"Base: {flask_guide_type_var.get()}\n"
        f"Minimum iLvl: {combo['min_item_level']}\n\n"
        f"Prefix\n{combo['prefix']}\n\n"
        f"Suffix\n{combo['suffix']}\n\n"
        f"Neden\n{combo['why']}\n\n"
        f"Bitiris\n{combo['finish']}"
    )
    flask_guide_detail.configure(state="normal")
    flask_guide_detail.delete("1.0", "end")
    flask_guide_detail.insert("1.0", detail)
    flask_guide_detail.configure(state="disabled")


def refresh_flask_guide(_event=None):
    guide = flask_guide.guide_for(flask_guide_type_var.get())
    flask_guide_overview_var.set(guide["overview"])
    flask_guide_current_combos[:] = guide["combinations"]
    flask_guide_combo_list.delete(0, "end")
    for combo in flask_guide_current_combos:
        flask_guide_combo_list.insert(
            "end",
            f"i{combo['min_item_level']} | {combo['title']}",
        )
    if flask_guide_current_combos:
        flask_guide_combo_list.selection_set(0)
        flask_guide_combo_list.activate(0)
        show_selected_flask_guide()


def use_flask_guide_base(_event=None):
    base_name = flask_guide_type_var.get()
    item_base_var.set(base_name)
    item_influence_var.set("None")
    item_base_cb["values"] = (base_name,)
    reload_item_mod_pool()


def hide_flask_guide_panel(hide_arrow=False):
    flask_guide_visible[0] = False
    try:
        flask_guide_panel.withdraw()
        flask_guide_arrow.config(text="<")
        if hide_arrow:
            flask_guide_arrow.place_forget()
    except tk.TclError:
        pass


def show_flask_guide_panel():
    if app_mode.get() != "item":
        return
    flask_guide_visible[0] = True
    refresh_flask_guide()
    position_flask_guide_panel()
    try:
        flask_guide_panel.deiconify()
        flask_guide_panel.lift()
        flask_guide_panel.attributes("-topmost", True)
        flask_guide_arrow.config(text=">")
        flask_guide_panel.after(
            20,
            lambda: _apply_window_rounding(
                flask_guide_panel,
                FLASK_GUIDE_W,
                FLASK_GUIDE_H,
                radius=18,
            ),
        )
    except tk.TclError:
        flask_guide_visible[0] = False


def toggle_flask_guide_panel():
    if flask_guide_visible[0]:
        hide_flask_guide_panel()
    else:
        show_flask_guide_panel()


def show_flask_guide_arrow():
    flask_guide_arrow.config(text=">" if flask_guide_visible[0] else "<")
    flask_guide_arrow.place(x=0, y=107, width=19, height=27)


def sync_flask_guide_position(event=None):
    if event is not None and event.widget is not root:
        return
    if flask_guide_visible[0]:
        position_flask_guide_panel()


ttk.Button(
    flask_guide_buttons,
    text="Base'i Item Craft'a aktar",
    style="Dark.TButton",
    command=use_flask_guide_base,
).pack(side="left", fill="x", expand=True, padx=(0, 2))
ttk.Button(
    flask_guide_buttons,
    text="Kapat",
    style="Dark.TButton",
    command=hide_flask_guide_panel,
).pack(side="left", padx=(2, 0))
ttk.Label(
    flask_guide_body,
    text="Yerel rehberdir; API veya fiyat taramasi kullanmaz.",
    font=("Segoe UI", 8, "italic"),
).grid(row=7, column=0, sticky="w", pady=(5, 0))

flask_guide_arrow = tk.Button(
    root,
    text="<",
    command=toggle_flask_guide_panel,
    bg="#3a3a3a",
    fg="#d6ad63",
    activebackground="#4a4a4a",
    activeforeground="#ffffff",
    relief="raised",
    bd=1,
    font=("Tahoma", 9, "bold"),
    padx=0,
    pady=0,
    highlightthickness=0,
)
flask_guide_close = tk.Button(
    flask_guide_panel,
    text=">",
    command=hide_flask_guide_panel,
    bg="#2b2b2b",
    fg="#e6e6e6",
    activebackground="#3a3a3a",
    activeforeground="#ffffff",
    relief="flat",
    bd=0,
    font=("Tahoma", 9, "bold"),
    padx=0,
    pady=0,
    highlightthickness=0,
)
flask_guide_close.place(x=FLASK_GUIDE_W - 22, y=0, width=22, height=18)
flask_guide_panel.protocol("WM_DELETE_WINDOW", hide_flask_guide_panel)
flask_guide_type_cb.bind("<<ComboboxSelected>>", refresh_flask_guide)
flask_guide_combo_list.bind("<<ListboxSelect>>", show_selected_flask_guide)
flask_guide_combo_list.bind("<Double-Button-1>", use_flask_guide_base)
refresh_flask_guide()

# Cluster template drawer that opens a pre-filled official PoE Trade search.
cluster_trade_panel = tk.Toplevel(root)
cluster_trade_panel.withdraw()
cluster_trade_panel.overrideredirect(True)
cluster_trade_panel.resizable(False, False)
cluster_trade_panel.configure(bg="#2b2b2b")
cluster_trade_panel.attributes("-topmost", True)
try:
    cluster_trade_panel.transient(root)
except tk.TclError:
    pass

cluster_trade_title_bar = tk.Frame(
    cluster_trade_panel,
    bg="#2b2b2b",
    height=21,
    highlightthickness=0,
    bd=0,
)
cluster_trade_title_bar.place(x=0, y=0, width=CLUSTER_TRADE_W, height=21)
cluster_trade_title_label = tk.Label(
    cluster_trade_title_bar,
    text="Cluster Trade Rehberi",
    bg="#2b2b2b",
    fg="#d6ad63",
    font=("Tahoma", 8, "bold"),
)
cluster_trade_title_label.place(x=7, y=1, height=18)

cluster_trade_body = ttk.Frame(cluster_trade_panel, padding=(8, 6))
cluster_trade_body.place(
    x=0,
    y=21,
    width=CLUSTER_TRADE_W,
    height=CLUSTER_TRADE_H - 21,
)
cluster_trade_body.grid_columnconfigure(0, weight=1)
cluster_trade_body.grid_rowconfigure(3, weight=1)

cluster_trade_search_var = tk.StringVar(value="")
cluster_trade_status_var = tk.StringVar(value="Template secin.")
cluster_trade_current_entries = []
cluster_trade_default_league = ["Allflame"]
cluster_trade_request_active = [False]
cluster_trade_open_after = [None]

ttk.Label(
    cluster_trade_body,
    text="Template ara:",
    font=("Segoe UI", 9, "bold"),
).grid(row=0, column=0, sticky="w")
cluster_trade_search_entry = ttk.Entry(
    cluster_trade_body,
    textvariable=cluster_trade_search_var,
)
cluster_trade_search_entry.grid(row=1, column=0, sticky="ew", pady=(2, 5))
ttk.Label(
    cluster_trade_body,
    text="Bir isme tiklayinca hazir PoE Trade aramasi acilir:",
).grid(row=2, column=0, sticky="w", pady=(0, 3))

cluster_trade_list_wrap = ttk.Frame(cluster_trade_body)
cluster_trade_list_wrap.grid(row=3, column=0, sticky="nsew")
cluster_trade_listbox = tk.Listbox(
    cluster_trade_list_wrap,
    exportselection=False,
    bg="#090909",
    fg="#f2f2f2",
    selectbackground="#5a4a2b",
    selectforeground="#ffffff",
    highlightbackground="#111111",
    font=("Tahoma", 8),
)
cluster_trade_list_scroll = ttk.Scrollbar(
    cluster_trade_list_wrap,
    orient="vertical",
    command=cluster_trade_listbox.yview,
)
cluster_trade_listbox.configure(yscrollcommand=cluster_trade_list_scroll.set)
cluster_trade_listbox.pack(side="left", fill="both", expand=True)
cluster_trade_list_scroll.pack(side="right", fill="y")

cluster_trade_detail = tk.Text(
    cluster_trade_body,
    height=7,
    wrap="word",
    bg="#111111",
    fg="#e7e0d2",
    insertbackground="#ffffff",
    selectbackground="#5a4a2b",
    relief="sunken",
    bd=1,
    font=("Tahoma", 8),
    padx=6,
    pady=5,
)
cluster_trade_detail.grid(row=4, column=0, sticky="ew", pady=(6, 3))
cluster_trade_detail.configure(state="disabled")
ttk.Label(
    cluster_trade_body,
    textvariable=cluster_trade_status_var,
    wraplength=CLUSTER_TRADE_W - 24,
    justify="left",
    font=("Segoe UI", 8, "italic"),
).grid(row=5, column=0, sticky="ew", pady=(0, 4))
cluster_trade_buttons = ttk.Frame(cluster_trade_body)
cluster_trade_buttons.grid(row=6, column=0, sticky="ew")


def position_cluster_trade_panel(_event=None):
    if not cluster_trade_visible[0]:
        return
    try:
        root.update_idletasks()
        x = root.winfo_x() - CLUSTER_TRADE_W - CLUSTER_TRADE_GAP
        y = root.winfo_y()
        cluster_trade_panel.geometry(
            f"{CLUSTER_TRADE_W}x{CLUSTER_TRADE_H}{x:+d}{y:+d}"
        )
    except tk.TclError:
        pass


def _cluster_trade_entry_from_selection():
    selection = cluster_trade_listbox.curselection()
    if not selection:
        return None
    index = selection[0]
    if index >= len(cluster_trade_current_entries):
        return None
    return cluster_trade_current_entries[index]


def show_selected_cluster_trade(_event=None):
    entry = _cluster_trade_entry_from_selection()
    if not entry:
        return
    metadata = entry.get("metadata") or {}
    if entry.get("error"):
        detail = f"Template: {entry['name']}\n\n{entry['error']}"
    else:
        league = metadata.get("league") or cluster_trade_default_league[0]
        passive_min, passive_max = cluster_trade.passive_count_range(
            metadata["passive_count"]
        )
        passive_text = (
            f"{passive_min}-{passive_max}"
            if passive_min != passive_max
            else f"tam {passive_min}"
        )
        detail = (
            f"Template: {entry['name']}\n"
            f"Base: {metadata['base']}\n"
            f"Tur: {metadata['item_type']}\n"
            f"Pasif: {passive_text}\n"
            f"Minimum iLvl: {metadata['minimum_item_level']}\n"
            f"Lig: {league}\n"
            "Corrupted: No | Fractured: No"
        )
    cluster_trade_detail.configure(state="normal")
    cluster_trade_detail.delete("1.0", "end")
    cluster_trade_detail.insert("1.0", detail)
    cluster_trade_detail.configure(state="disabled")


def refresh_cluster_trade_templates(*_args):
    selected = _cluster_trade_entry_from_selection()
    selected_name = selected.get("name") if selected else ""
    search = cluster_trade_search_var.get().strip().casefold()
    all_entries = []
    leagues = {}
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    for file_name in sorted(os.listdir(TEMPLATE_DIR), key=str.casefold):
        if not file_name.endswith(".json"):
            continue
        name = os.path.splitext(file_name)[0]
        path = os.path.join(TEMPLATE_DIR, file_name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            metadata = cluster_trade.template_metadata(name, data)
            league = metadata.get("league")
            if league:
                leagues[league] = leagues.get(league, 0) + 1
            entry = {
                "name": name,
                "path": path,
                "data": data,
                "metadata": metadata,
                "error": "",
            }
        except Exception as exc:
            entry = {
                "name": name,
                "path": path,
                "data": {},
                "metadata": {},
                "error": str(exc),
            }
        all_entries.append(entry)

    if leagues:
        cluster_trade_default_league[0] = max(
            leagues,
            key=lambda league: (leagues[league], league),
        )
    visible = [
        entry
        for entry in all_entries
        if cluster_template_size(entry["name"], entry.get("data"))
        == cluster_size_var.get()
        and (not search or search in entry["name"].casefold())
    ]
    cluster_trade_current_entries[:] = visible
    cluster_trade_listbox.delete(0, "end")
    selected_index = 0
    for index, entry in enumerate(visible):
        cluster_trade_listbox.insert("end", entry["name"])
        if entry["name"] == selected_name:
            selected_index = index
    if visible:
        cluster_trade_listbox.selection_set(selected_index)
        cluster_trade_listbox.activate(selected_index)
        cluster_trade_listbox.see(selected_index)
        show_selected_cluster_trade()
    else:
        cluster_trade_detail.configure(state="normal")
        cluster_trade_detail.delete("1.0", "end")
        cluster_trade_detail.configure(state="disabled")
        cluster_trade_status_var.set("Eslesen cluster template bulunamadi.")


def _finish_cluster_trade_search(entry, url=None, error=None):
    cluster_trade_request_active[0] = False
    if error:
        cluster_trade_status_var.set(f"Trade aramasi acilamadi: {error}")
        log_message(f"[CLUSTER TRADE] Hata: {error}")
        return
    opened = webbrowser.open(url, new=2)
    state = "tarayicida acildi" if opened else "tarayiciya gonderildi"
    cluster_trade_status_var.set(f"{entry['name']}: {state}.")
    log_message(f"[CLUSTER TRADE] {entry['name']} -> {url}")


def open_selected_cluster_trade(_event=None):
    cluster_trade_open_after[0] = None
    entry = _cluster_trade_entry_from_selection()
    if not entry or cluster_trade_request_active[0]:
        return
    if entry.get("error"):
        cluster_trade_status_var.set(entry["error"])
        return

    metadata = entry["metadata"]
    league = metadata.get("league") or cluster_trade_default_league[0]
    cluster_trade_request_active[0] = True
    cluster_trade_status_var.set(
        f"{entry['name']}: {league} icin sorgu olusturuluyor..."
    )

    def worker():
        try:
            stats = cluster_trade.load_stats(os.path.join(DATA_DIR, "stats.json"))
            url, _metadata, _payload = cluster_trade.create_trade_search(
                requests,
                stats,
                entry["name"],
                entry["data"],
                league,
                headers={"User-Agent": f"Waukeen-Crafting-Assistant/{APP_VERSION}"},
            )
            root.after(
                0,
                lambda: _finish_cluster_trade_search(entry, url=url),
            )
        except Exception as exc:
            root.after(
                0,
                lambda message=str(exc): _finish_cluster_trade_search(
                    entry,
                    error=message,
                ),
            )

    threading.Thread(target=worker, daemon=True).start()


def on_cluster_trade_name_click(event):
    if cluster_trade_listbox.size() <= 0:
        return
    index = cluster_trade_listbox.nearest(event.y)
    bbox = cluster_trade_listbox.bbox(index)
    if not bbox or not (bbox[1] <= event.y <= bbox[1] + bbox[3]):
        return
    cluster_trade_listbox.selection_clear(0, "end")
    cluster_trade_listbox.selection_set(index)
    cluster_trade_listbox.activate(index)
    show_selected_cluster_trade()
    if cluster_trade_open_after[0] is not None:
        root.after_cancel(cluster_trade_open_after[0])
    cluster_trade_open_after[0] = root.after(160, open_selected_cluster_trade)


def hide_cluster_trade_panel(hide_arrow=False):
    cluster_trade_visible[0] = False
    try:
        cluster_trade_panel.withdraw()
        cluster_trade_arrow.config(text="<")
        if hide_arrow:
            cluster_trade_arrow.place_forget()
    except tk.TclError:
        pass


def show_cluster_trade_panel():
    if app_mode.get() != "cluster":
        return
    cluster_trade_visible[0] = True
    refresh_cluster_trade_templates()
    position_cluster_trade_panel()
    try:
        cluster_trade_panel.deiconify()
        cluster_trade_panel.lift()
        cluster_trade_panel.attributes("-topmost", True)
        cluster_trade_arrow.config(text=">")
        cluster_trade_panel.after(
            20,
            lambda: _apply_window_rounding(
                cluster_trade_panel,
                CLUSTER_TRADE_W,
                CLUSTER_TRADE_H,
                radius=18,
            ),
        )
    except tk.TclError:
        cluster_trade_visible[0] = False


def toggle_cluster_trade_panel():
    if cluster_trade_visible[0]:
        hide_cluster_trade_panel()
    else:
        show_cluster_trade_panel()


def show_cluster_trade_arrow():
    cluster_trade_arrow.config(text=">" if cluster_trade_visible[0] else "<")
    cluster_trade_arrow.place(x=0, y=107, width=19, height=27)


def sync_cluster_trade_position(event=None):
    if event is not None and event.widget is not root:
        return
    if cluster_trade_visible[0]:
        position_cluster_trade_panel()


ttk.Button(
    cluster_trade_buttons,
    text="PoE Trade'de Ac",
    style="Dark.TButton",
    command=open_selected_cluster_trade,
).pack(side="left", fill="x", expand=True, padx=(0, 2))
ttk.Button(
    cluster_trade_buttons,
    text="Kapat",
    style="Dark.TButton",
    command=hide_cluster_trade_panel,
).pack(side="left", padx=(2, 0))

cluster_trade_arrow = tk.Button(
    root,
    text="<",
    command=toggle_cluster_trade_panel,
    bg="#3a3a3a",
    fg="#d6ad63",
    activebackground="#4a4a4a",
    activeforeground="#ffffff",
    relief="raised",
    bd=1,
    font=("Tahoma", 9, "bold"),
    padx=0,
    pady=0,
    highlightthickness=0,
)
cluster_trade_close = tk.Button(
    cluster_trade_panel,
    text=">",
    command=hide_cluster_trade_panel,
    bg="#2b2b2b",
    fg="#e6e6e6",
    activebackground="#3a3a3a",
    activeforeground="#ffffff",
    relief="flat",
    bd=0,
    font=("Tahoma", 9, "bold"),
    padx=0,
    pady=0,
    highlightthickness=0,
)
cluster_trade_close.place(x=CLUSTER_TRADE_W - 22, y=0, width=22, height=18)
cluster_trade_panel.protocol("WM_DELETE_WINDOW", hide_cluster_trade_panel)
cluster_trade_search_var.trace_add("write", refresh_cluster_trade_templates)
cluster_trade_listbox.bind("<<ListboxSelect>>", show_selected_cluster_trade)
cluster_trade_listbox.bind("<ButtonRelease-1>", on_cluster_trade_name_click)
cluster_trade_listbox.bind("<Return>", open_selected_cluster_trade)
refresh_cluster_trade_templates()

# craft logic + flags
mid = ttk.Frame(root)
mid.place(x=PADX, y=124, width=WINDOW_W - 2 * PADX)
logic_label = ttk.Label(mid, text="", font=("Segoe UI", 9, "bold"))
logic_label.grid(
    row=0, column=0, sticky="w"
)
logic_frame = ttk.Frame(mid)
logic_frame.grid(row=1, column=0, sticky="nw", pady=(2, 0))
rb_regal = ttk.Radiobutton(
    logic_frame, text="Rare (regal)", variable=craft_logic, value="Rare (regal)"
)
rb_regal.pack(anchor="w")
rb_alch = ttk.Radiobutton(
    logic_frame, text="Rare (alchemy)", variable=craft_logic, value="Rare (alchemy)"
)
rb_alch.pack(anchor="w")
rb_chaos = ttk.Radiobutton(
    logic_frame, text="Rare (chaos)", variable=craft_logic, value="Rare (chaos)"
)
rb_chaos.pack(anchor="w")
rb_alch_vaal = ttk.Radiobutton(
    logic_frame,
    text="Alchemy + Vaal",
    variable=craft_logic,
    value="Alchemy + Vaal",
)
rb_alch_vaal.pack(anchor="w")
map_use_exalt_cb = ttk.Checkbutton(logic_frame, text="Use Exalted", variable=map_use_exalt)

augment_label = ttk.Label(mid, text="Augment Usage", font=("Segoe UI", 9, "bold"))
augment_label.grid(row=0, column=1, sticky="w", padx=(8, 0))
augment_frame = ttk.Frame(mid)
augment_frame.grid(row=1, column=1, sticky="nw", padx=(8, 0))
for text in ["Don't use", "Use if needed", "Always use"]:
    ttk.Radiobutton(augment_frame, text=text, variable=augment_mode, value=text).pack(anchor="w")

extra_frame = ttk.Frame(mid)
extra_frame.grid(row=1, column=2, sticky="nw", padx=(1, 0), pady=(19, 0))
use_exalt_cb = ttk.Checkbutton(extra_frame, text="Use Exalted", variable=use_exalt, style="Aligned.TCheckbutton")
use_exalt_cb.grid(row=0, column=0, sticky="w", pady=(0, 1))
use_annul_cb = ttk.Checkbutton(extra_frame, text="Use Annul", variable=use_annul, style="Aligned.TCheckbutton")
use_annul_cb.grid(row=1, column=0, sticky="w", pady=(0, 3))

map_summary_thresholds_frame = ttk.Frame(mid)
_map_summary_specs = [
    ("Quant >=", map_quantity_thresh),
    ("Rarity >=", map_rarity_thresh),
    ("Pack >=", map_pack_size_thresh),
]
for row_idx, (label, var) in enumerate(_map_summary_specs):
    ttk.Label(map_summary_thresholds_frame, text=label).grid(row=row_idx, column=0, sticky="e")
    tk.Entry(
        map_summary_thresholds_frame,
        textvariable=var,
        width=4,
        font=("Tahoma", 8),
        bg="#000",
        fg="#fff",
        insertbackground="#fff",
    ).grid(row=row_idx, column=1, padx=(3, 0), pady=(0, 1), sticky="w")

# chain
weights = ttk.Frame(root)
weights.place(x=PADX, y=194, width=WINDOW_W - 2 * PADX)
weights.columnconfigure(4, weight=1)

chain_line_frame = ttk.Frame(weights)
chain_line_frame.grid(row=0, column=0, columnspan=4, sticky="e")
cluster_no_regal_two_cb = ttk.Checkbutton(
    chain_line_frame,
    text="No Regal: 2 hedefte dur",
    variable=cluster_no_regal_two_var,
)
cluster_small_stop_three_cb = ttk.Checkbutton(
    chain_line_frame,
    text="3 hedefte dur",
    variable=cluster_small_stop_three_var,
)
chain_toggle = ttk.Checkbutton(chain_line_frame, text="Chain", variable=chain_craft)
chain_toggle.pack(side="left")
ttk.Label(chain_line_frame, text="Count:").pack(side="left", padx=(0, 2))
chain_count_entry = tk.Entry(
    chain_line_frame,
    width=4,
    textvariable=chain_count_var,
    font=("Tahoma", 8),
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
    disabledbackground="#000",
    disabledforeground="#fff",
)
chain_count_entry.pack(side="left")

# affix pool (view/search + add)
pool = ttk.Frame(root)
header = ttk.Frame(pool)
header.pack(fill="x", pady=(0, 1))
left = ttk.Frame(header)
left.pack(side="left", padx=(2, 0))
affix_mode = tk.StringVar(value="prefix")

def read_affixes(is_prefix=True):
    path = CLUSTER_P_PATH if is_prefix else CLUSTER_S_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]

def reload_affixes():
    pool_list.delete(0, "end")
    items = read_affixes(affix_mode.get() == "prefix")
    all_affixes[:] = items
    for a in items:
        pool_list.insert("end", a)
    on_search()

ttk.Radiobutton(left, text="Prefixes", variable=affix_mode, value="prefix", command=reload_affixes, style="Compact.TRadiobutton").pack(
    anchor="w"
)
ttk.Radiobutton(left, text="Suffixes", variable=affix_mode, value="suffix", command=reload_affixes, style="Compact.TRadiobutton").pack(
    anchor="w"
)

right_controls = ttk.Frame(header)
right_controls.pack(side="right", padx=(4, 8), pady=(0, 1))
affix_weight_frame = ttk.Frame(right_controls)
affix_weight_frame.pack(pady=(0, 0))
ttk.Label(affix_weight_frame, text="Affix Weight").pack(side="left")
tk.Entry(
    affix_weight_frame,
    width=4,
    textvariable=affix_weight_var,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left")

search_var = tk.StringVar()

def on_search(*_):
    q = search_var.get().lower().strip()
    pool_list.delete(0, "end")
    for a in all_affixes:
        if not q or q in a.lower():
            pool_list.insert("end", a)

tk.Entry(pool, textvariable=search_var, bg="#000", fg="#fff", insertbackground="#fff").pack(
    fill="x", padx=4, pady=(0, 2)
)
search_var.trace_add("write", on_search)
pool_list = tk.Listbox(pool, bg="#000", fg="#fff", selectbackground="#444", highlightbackground="#000")
pool_list.pack(fill="both", expand=True, padx=3, pady=3)
all_affixes = []
reload_affixes()

def on_affix_double(_event):
    if not (sel := pool_list.curselection()):
        return
    text = pool_list.get(sel[0])
    tag = "[P]" if affix_mode.get() == "prefix" else "[S]"
    try:
        w = int(affix_weight_var.get() or 1)
    except (ValueError, TypeError):
        w = 1
    prefixed_text = f"{tag}[{w}] {text}"
    idx = tabs.index(tabs.select())
    if idx == 0:  # CombCraft
        if not comb_craft_data:
            comb_craft_data["1"] = [prefixed_text]
        else:
            last_key = sorted(comb_craft_data.keys(), key=int)[-1]
            last_list = comb_craft_data[last_key]
            pc = sum(1 for s in last_list if s.startswith("[P]"))
            sc = sum(1 for s in last_list if s.startswith("[S]"))
            if pc >= 2 and sc >= 2:
                comb_craft_data[str(int(last_key) + 1)] = [prefixed_text]
            else:
                if tag == "[P]" and pc < 2:
                    last_list.append(prefixed_text)
                elif tag == "[S]" and sc < 2:
                    last_list.append(prefixed_text)
                else:
                    log_message(
                        "[UYARI] Kombinasyon dolu (Max 2P/2S). Yeni kombinasyona baslayin."
                    )
                    return
        populate_comb_list()
    elif idx == 1:  # İki Modda Dur — çift ekleme: önce seçili, sonra bir sonraki tıkla pair tamamlanır
        # stop_on_two_match çiftler listesi — her çift [mod1, mod2] şeklinde
        # Kullanıcı iki ayrı mod seçer; tek tıkla "bekleyen" slota ekler
        if not hasattr(on_affix_double, "_pending_stop"):
            on_affix_double._pending_stop = None
        if on_affix_double._pending_stop is None:
            on_affix_double._pending_stop = prefixed_text
            log_message(f"[İki Modda Dur] 1. mod seçildi: {prefixed_text} — şimdi 2. modu seçin.")
        else:
            pair = [on_affix_double._pending_stop, prefixed_text]
            stop_on_two_match_config.append(pair)
            on_affix_double._pending_stop = None
            populate_stop_two_list()
            log_message(f"[İki Modda Dur] Çift eklendi: {pair[0]} | {pair[1]}")
    elif idx == 2:  # Annul Kullan
        annul_combs_config.append(prefixed_text)
        populate_annul_combs_list()
    elif idx == 3:  # Regal Salla
        solo_regal_mods_config.append(prefixed_text)
        populate_solo_regal_list()
    elif idx == 4:  # Regalle Arama
        no_regal_mods_config.append(prefixed_text)
        populate_no_regal_list()

pool_list.bind("<Double-Button-1>", on_affix_double)

def on_affix_set_fracture(event):
    row = pool_list.nearest(event.y)
    if row < 0 or row >= pool_list.size():
        return "break"
    text = pool_list.get(row)
    tag = "[P]" if affix_mode.get() == "prefix" else "[S]"
    try:
        weight = int(affix_weight_var.get() or 1)
    except (ValueError, TypeError):
        weight = 1
    cluster_fracture_mode_var.set("fractured")
    cluster_fractured_target_var.set(f"{tag}[{weight}] {text}")
    log_message(f"[CLUSTER] Fractured hedef secildi: {text}")
    return "break"

pool_list.bind("<Button-3>", on_affix_set_fracture)

# tabs — 5 tab, programa tam yayılmış
tabs = ttk.Notebook(root)
tabs.place(x=PADX, y=228, width=WINDOW_W - 2 * PADX, height=220)
tab_comb        = ttk.Frame(tabs)
tab_stop_two    = ttk.Frame(tabs)
tab_annul_combs = ttk.Frame(tabs)
tab_solo_regal  = ttk.Frame(tabs)
tab_no_regal    = ttk.Frame(tabs)
tab_width = WINDOW_W - 2 * PADX
style.configure("TNotebook.Tab", width=tab_width, padding=[0, 4])
tabs.add(tab_comb,        text="Comb\nCraft")

cluster_fracture_bar = ttk.Frame(tab_comb)
cluster_fracture_bar.pack(fill="x", padx=3, pady=(3, 0))
ttk.Label(cluster_fracture_bar, text="Base:").pack(side="left")
ttk.Radiobutton(
    cluster_fracture_bar,
    text="Fracsiz",
    variable=cluster_fracture_mode_var,
    value="unfractured",
).pack(side="left", padx=(3, 2))
ttk.Radiobutton(
    cluster_fracture_bar,
    text="Fractured",
    variable=cluster_fracture_mode_var,
    value="fractured",
).pack(side="left", padx=(0, 4))
ttk.Label(
    cluster_fracture_bar,
    textvariable=cluster_fractured_target_var,
).pack(side="left", fill="x", expand=True)
ttk.Button(
    cluster_fracture_bar,
    text="Clear Frac",
    command=lambda: cluster_fractured_target_var.set(""),
).pack(side="right")

cluster_price_filter_bar = ttk.Frame(tab_comb)
cluster_price_filter_bar.pack(fill="x", padx=3, pady=(3, 0))
ttk.Label(cluster_price_filter_bar, text="Saved min:").pack(side="left")
cluster_price_filter_cb = ttk.Combobox(
    cluster_price_filter_bar,
    textvariable=cluster_price_filter_var,
    values=tuple(CLUSTER_PRICE_FILTERS),
    state="disabled",
    width=6,
)
cluster_price_filter_cb.pack(side="left", padx=(4, 6))
cluster_price_filter_cb.bind(
    "<<ComboboxSelected>>", on_cluster_price_filter_changed
)
ttk.Label(
    cluster_price_filter_bar,
    textvariable=cluster_price_filter_status_var,
).pack(side="left")

comb_list = tk.Listbox(tab_comb, bg="#000", fg="#fff", selectbackground="#444", borderwidth=0)
comb_list.pack(fill="both", expand=True, padx=3, pady=(2, 3))

stop_two_list = tk.Listbox(tab_stop_two, bg="#000", fg="#fff", selectbackground="#444", borderwidth=0)
stop_two_list.pack(fill="both", expand=True, padx=3, pady=3)

annul_combs_list = tk.Listbox(tab_annul_combs, bg="#000", fg="#fff", selectbackground="#444", borderwidth=0)
annul_combs_list.pack(fill="both", expand=True, padx=3, pady=3)

solo_regal_list = tk.Listbox(tab_solo_regal, bg="#000", fg="#fff", selectbackground="#444", borderwidth=0)
solo_regal_list.pack(fill="both", expand=True, padx=3, pady=3)

no_regal_list = tk.Listbox(tab_no_regal, bg="#000", fg="#fff", selectbackground="#444", borderwidth=0)
no_regal_list.pack(fill="both", expand=True, padx=3, pady=3)

def populate_stop_two_list():
    stop_two_list.delete(0, "end")
    for pair in stop_on_two_match_config:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            stop_two_list.insert("end", f"{format_affix_for_display(pair[0])}  |  {format_affix_for_display(pair[1])}")

def populate_annul_combs_list():
    annul_combs_list.delete(0, "end")
    for m in annul_combs_config:
        annul_combs_list.insert("end", format_affix_for_display(m))

def populate_solo_regal_list():
    solo_regal_list.delete(0, "end")
    for m in solo_regal_mods_config:
        solo_regal_list.insert("end", format_affix_for_display(m))

def populate_no_regal_list():
    no_regal_list.delete(0, "end")
    for m in no_regal_mods_config:
        no_regal_list.insert("end", format_affix_for_display(m))

def delete_from_listbox(event):
    if sel := event.widget.curselection():
        event.widget.delete(sel[0])

def delete_from_comb_list(event):
    global template_stop_on_two_match_config
    global template_annul_combs_config, template_no_annul_combs_config
    global template_solo_regal_mods_config, template_no_regal_mods_config

    row = comb_list.nearest(event.y)
    sorted_keys = sorted(comb_craft_data.keys(), key=int)
    if row < 0 or row >= len(sorted_keys):
        return

    if market_cluster_template_active and row < len(market_filter_source_keys):
        source_key = str(market_filter_source_keys[row])
        template_comb_craft_data.pop(source_key, None)
        template_combo_price_data.pop(source_key, None)
        template_no_annul_combs_config[:] = [
            key for key in template_no_annul_combs_config
            if str(key) != source_key
        ]
        template_visible = _combo_visible_mods(template_comb_craft_data)
        template_stop_on_two_match_config = _filter_stop_pairs_for_combos(
            template_stop_on_two_match_config,
            template_comb_craft_data,
        )
        template_annul_combs_config = [
            mod for mod in template_annul_combs_config if mod in template_visible
        ]
        template_solo_regal_mods_config = [
            mod for mod in template_solo_regal_mods_config if mod in template_visible
        ]
        template_no_regal_mods_config = [
            mod for mod in template_no_regal_mods_config if mod in template_visible
        ]
        apply_cluster_price_filter()
    else:
        key = sorted_keys[row]
        comb_craft_data.pop(key, None)
        combo_price_data.pop(key, None)
        populate_comb_list()
        _prune_active_combo_rules()
        populate_stop_two_list()
        populate_annul_combs_list()
        populate_solo_regal_list()
        populate_no_regal_list()

    _clear_comb_match_caches()
    log_message(
        "[SESSION] Comb Craft kombinasyonu kaldirildi. "
        "Save denmedikce template dosyasi degismez."
    )

def delete_from_stop_two_list(event):
    if not (sel_idx := stop_two_list.curselection()):
        return
    idx = sel_idx[0]
    if idx < len(stop_on_two_match_config):
        del stop_on_two_match_config[idx]
        populate_stop_two_list()

def delete_from_annul_combs_list(event):
    if not (sel_idx := annul_combs_list.curselection()):
        return
    idx = sel_idx[0]
    if idx < len(annul_combs_config):
        del annul_combs_config[idx]
        populate_annul_combs_list()

def delete_from_solo_regal_list(event):
    if not (sel_idx := solo_regal_list.curselection()):
        return
    idx = sel_idx[0]
    if idx < len(solo_regal_mods_config):
        del solo_regal_mods_config[idx]
        populate_solo_regal_list()

def delete_from_no_regal_list(event):
    if not (sel_idx := no_regal_list.curselection()):
        return
    idx = sel_idx[0]
    if idx < len(no_regal_mods_config):
        del no_regal_mods_config[idx]
        populate_no_regal_list()

comb_list.bind("<Double-Button-1>", delete_from_comb_list)
stop_two_list.bind("<Double-Button-1>", delete_from_stop_two_list)
annul_combs_list.bind("<Double-Button-1>", delete_from_annul_combs_list)
solo_regal_list.bind("<Double-Button-1>", delete_from_solo_regal_list)
no_regal_list.bind("<Double-Button-1>", delete_from_no_regal_list)

# ── MAP CRAFT CONFIG ────────────────────────────────────────────────────────
map_orb_mode.set("chaos")
map_profile_var.set(map_rules.PROFILE_NORMAL)
map_normal_forbidden.clear()
map_memory_forbidden.clear()
map_quantity_thresh.set("")
map_rarity_thresh.set("")
map_pack_size_thresh.set("")
map_use_exalt.set(False)

def read_map_affixes():
    return map_rules.unique_affixes(load_map_affix_groups())

# ── MAP CRAFT UI ─────────────────────────────────────────────────────────────
map_frame = ttk.Frame(root)

# Orb seçimi
orb_row = ttk.Frame(map_frame)
orb_row.pack(fill="x", pady=(2, 2))
ttk.Label(orb_row, text="Orb:").pack(side="left")
btn_chaos_orb = ttk.Button(orb_row, text="Chaos", width=10, style="Dark.TButton")
btn_alch_orb  = ttk.Button(orb_row, text="Alchemy + Scour", width=16, style="Dark.TButton")
btn_alch_vaal = ttk.Button(orb_row, text="Alchemy + Vaal", width=16, style="Dark.TButton")
btn_chaos_orb.pack(side="left", padx=(4, 2))
btn_alch_orb.pack(side="left")
btn_alch_vaal.pack(side="left", padx=(2, 0))

def _set_orb_mode(mode):
    map_orb_mode.set(mode)
    button_modes = (
        (btn_chaos_orb, "chaos"),
        (btn_alch_orb, "alchemy"),
        (btn_alch_vaal, "alchemy_vaal"),
    )
    for button, button_mode in button_modes:
        button.state(["pressed"] if mode == button_mode else ["!pressed"])

btn_chaos_orb.config(command=lambda: _set_orb_mode("chaos"))
btn_alch_orb.config(command=lambda: _set_orb_mode("alchemy"))
btn_alch_vaal.config(command=lambda: _set_orb_mode("alchemy_vaal"))
_set_orb_mode("chaos")

# Map tabs: each profile keeps its own unwanted-mod list.
map_tabs = ttk.Notebook(root)
tab_map_normal = ttk.Frame(map_tabs)
tab_map_memory = ttk.Frame(map_tabs)
map_tabs.add(tab_map_normal, text="Normal Map\nBlacklist")
map_tabs.add(tab_map_memory, text="Memory / Nightmare\nBlacklist")

map_normal_list = tk.Listbox(
    tab_map_normal,
    bg="#000",
    fg="#fff",
    selectbackground="#444",
    borderwidth=0,
)
map_normal_list.pack(fill="both", expand=True, padx=3, pady=3)
map_memory_list = tk.Listbox(
    tab_map_memory,
    bg="#000",
    fg="#fff",
    selectbackground="#444",
    borderwidth=0,
)
map_memory_list.pack(fill="both", expand=True, padx=3, pady=3)

def populate_map_normal_list():
    map_normal_list.delete(0, "end")
    for mod in map_normal_forbidden:
        map_normal_list.insert("end", mod)

def populate_map_memory_list():
    map_memory_list.delete(0, "end")
    for mod in map_memory_forbidden:
        map_memory_list.insert("end", mod)

def on_map_profile_tab_changed(_event=None):
    selected_index = map_tabs.index(map_tabs.select())
    profile = (
        map_rules.PROFILE_NORMAL
        if selected_index == 0
        else map_rules.PROFILE_MEMORY_NIGHTMARE
    )
    map_profile_var.set(profile)

def select_map_profile_tab():
    target_index = (
        1
        if map_rules.normalize_profile(map_profile_var.get())
        == map_rules.PROFILE_MEMORY_NIGHTMARE
        else 0
    )
    map_tabs.select(target_index)
    on_map_profile_tab_changed()

def sync_map_mode_controls():
    is_batch = craft_logic.get() == "Alchemy + Vaal"
    if is_batch:
        map_profile_var.set(map_rules.PROFILE_NORMAL)
        select_map_profile_tab()
        map_use_exalt.set(False)
        map_use_exalt_cb.state(["disabled"])
    else:
        map_use_exalt_cb.state(["!disabled"])

rb_alch.config(command=sync_map_mode_controls)
rb_chaos.config(command=sync_map_mode_controls)
rb_alch_vaal.config(command=sync_map_mode_controls)

def delete_from_map_list(event, lst, config_list, populate_fn):
    if sel := event.widget.curselection():
        idx = sel[0]
        if idx < len(config_list):
            del config_list[idx]
        populate_fn()

map_normal_list.bind(
    "<Double-Button-1>",
    lambda e: delete_from_map_list(
        e,
        map_normal_list,
        map_normal_forbidden,
        populate_map_normal_list,
    ),
)
map_memory_list.bind(
    "<Double-Button-1>",
    lambda e: delete_from_map_list(
        e,
        map_memory_list,
        map_memory_forbidden,
        populate_map_memory_list,
    ),
)
map_tabs.bind("<<NotebookTabChanged>>", on_map_profile_tab_changed)

# Map affix pool
map_pool_frame = ttk.Frame(root)
map_search_var = tk.StringVar()
map_roll_var = tk.StringVar(value="")
map_pool_status_var = tk.StringVar(value="")
all_map_affixes = []

def reload_map_affixes():
    all_map_affixes[:] = read_map_affixes()
    map_pool_status_var.set(f"{len(all_map_affixes)} mod")
    on_map_search()

def on_map_search(*_):
    q = map_search_var.get().lower().strip()
    map_pool_list.delete(0, "end")
    for a in all_map_affixes:
        if not q or q in a.lower():
            map_pool_list.insert("end", a)

map_pool_header = ttk.Frame(map_pool_frame)
map_pool_header.pack(fill="x", padx=4, pady=(2, 2))
ttk.Label(map_pool_header, text=">=").pack(side="left")
tk.Entry(
    map_pool_header,
    textvariable=map_roll_var,
    width=6,
    bg="#000",
    fg="#fff",
    insertbackground="#fff",
).pack(side="left", padx=(4, 0))
ttk.Label(map_pool_header, textvariable=map_pool_status_var).pack(side="right")

tk.Entry(map_pool_frame, textvariable=map_search_var,
         bg="#000", fg="#fff", insertbackground="#fff").pack(fill="x", padx=4, pady=(0, 2))
map_search_var.trace_add("write", on_map_search)
map_pool_list = tk.Listbox(map_pool_frame, bg="#000", fg="#fff",
                            selectbackground="#444", highlightbackground="#000")
map_pool_list.pack(fill="both", expand=True, padx=3, pady=3)

def on_map_affix_double(_event):
    if not (sel := map_pool_list.curselection()):
        return
    text = map_pool_list.get(sel[0])
    roll_text = map_roll_var.get().strip()
    entry_text = f"{text}({roll_text})" if roll_text else text
    idx = map_tabs.index(map_tabs.select())
    if idx == 0:
        if entry_text not in map_normal_forbidden:
            map_normal_forbidden.append(entry_text)
        populate_map_normal_list()
    else:
        if entry_text not in map_memory_forbidden:
            map_memory_forbidden.append(entry_text)
        populate_map_memory_list()
    map_roll_var.set("")

map_pool_list.bind("<Double-Button-1>", on_map_affix_double)

# Map bottom bar
map_bottom = ttk.Frame(root)
map_show_btn = ttk.Button(map_bottom, text="Show Affix List", style="Dark.TButton",
                           command=lambda: toggle_map_affix_pool())
map_show_btn.pack(fill="both", expand=True)

map_affix_visible = [False]
def toggle_map_affix_pool():
    if map_affix_visible[0]:
        map_pool_frame.place_forget()
        map_affix_visible[0] = False
        show_top_controls()
        map_show_btn.config(text="Show Affix List")
    else:
        hide_top_controls()
        map_pool_frame.place(x=PADX, y=60, width=WINDOW_W - 2 * PADX, height=144)
        reload_map_affixes()
        map_affix_visible[0] = True
        map_show_btn.config(text="Hide Affix List")

bottom = ttk.Frame(root)
bottom.place(x=PADX, y=463, width=WINDOW_W - 2 * PADX, height=26)
current_mode = "normal"

def show_mode(mode: str):
    global current_mode
    current_mode = mode
    for w in [
        mid,
        weights,
        settings_panel,
        pool,
        socket_frame,
        base_jewel_frame,
        item_frame,
        item_mod_pool_frame,
        voyage_frame,
        auto_flask_frame,
    ]:
        w.place_forget()
    if mode == "normal":
        show_top_controls()
        mid.place(x=PADX, y=124, width=WINDOW_W - 2 * PADX)
        weights.place(x=PADX, y=194, width=WINDOW_W - 2 * PADX)
    elif mode == "affix":
        hide_top_controls()
        pool.place(x=PADX, y=60, width=WINDOW_W - 2 * PADX, height=144)
    elif mode == "settings":
        hide_top_controls()
        settings_panel.place(x=PADX, y=60, width=WINDOW_W - 2 * PADX, height=144)
        refresh_settings_panel()
    tabs.place(x=PADX, y=228, width=WINDOW_W - 2 * PADX, height=220)
    bottom.place(x=PADX, y=463, width=WINDOW_W - 2 * PADX, height=26)
    show_btn.config(text="Hide Affix List" if mode == "affix" else "Show Affix List")

def toggle_affix_pool():
    show_mode("normal" if current_mode == "affix" else "affix")

show_btn = ttk.Button(bottom, text="Show Affix List", style="Dark.TButton", command=toggle_affix_pool)
show_btn.pack(fill="both", expand=True)

def toggle_settings_panel():
    if app_mode.get() in ("base_jewel", "item"):
        OrbLocationsWindow(root)
        return
    show_mode("normal" if current_mode == "settings" else "settings")

settings_btn.config(command=toggle_settings_panel)

# ── APP MODE SWITCHING: Cluster ↔ Map ───────────────────────────────────────
def switch_to_cluster():
    app_mode.set("cluster")
    mode_selector_var.set(MODE_VALUE_TO_DISPLAY["cluster"])
    hide_flask_guide_panel(hide_arrow=True)
    refresh_templates()
    configure_top_controls_for_socket_mode(False)
    # Map UI gizle
    map_frame.place_forget()
    map_tabs.place_forget()
    map_bottom.place_forget()
    map_pool_frame.place_forget()
    base_jewel_frame.place_forget()
    item_frame.place_forget()
    item_mod_pool_frame.place_forget()
    voyage_frame.place_forget()
    auto_flask_frame.place_forget()
    item_mod_pool_visible[0] = False
    map_affix_visible[0] = False
    # Logic butonları cluster moduna döndür
    craft_logic.set("Rare (regal)")
    logic_label.grid_remove()
    logic_frame.grid_remove()
    map_use_exalt_cb.pack_forget()
    augment_label.grid_remove()
    augment_frame.grid_remove()
    map_summary_thresholds_frame.grid_remove()
    use_exalt_cb.grid(row=0, column=0, sticky="w", pady=(0, 1))
    use_annul_cb.grid(row=1, column=0, sticky="w", pady=(0, 3))
    cluster_no_regal_two_cb.pack(
        side="left",
        padx=(0, 4),
        before=chain_toggle,
    )
    _sync_cluster_size_controls()
    # Chain disabled (cluster'da)
    try: chain_toggle.config(state="normal")
    except Exception: pass
    try: chain_count_entry.config(state="normal")
    except Exception: pass
    # Cluster UI göster
    show_top_controls()
    style.configure("TNotebook.Tab", width=(WINDOW_W - 2 * PADX) // 5, padding=[0, 4])
    show_mode("normal")
    show_cluster_trade_arrow()

def switch_to_map():
    app_mode.set("map")
    mode_selector_var.set(MODE_VALUE_TO_DISPLAY["map"])
    hide_flask_guide_panel(hide_arrow=True)
    hide_cluster_trade_panel(hide_arrow=True)
    refresh_templates()
    configure_top_controls_for_socket_mode(False)
    # Cluster UI gizle
    socket_frame.place_forget()
    base_jewel_frame.place_forget()
    item_frame.place_forget()
    item_mod_pool_frame.place_forget()
    voyage_frame.place_forget()
    auto_flask_frame.place_forget()
    item_mod_pool_visible[0] = False
    pool.place_forget()
    settings_panel.place_forget()
    bottom.place_forget()
    tabs.place_forget()
    # Logic butonlarını map moduna ayarla.
    logic_label.grid(row=0, column=0, sticky="w")
    logic_frame.grid(row=1, column=0, sticky="nw")
    rb_regal.pack_forget()
    for rb in [rb_alch, rb_chaos, rb_alch_vaal]:
        rb.state(["!disabled"])
    if craft_logic.get() not in ("Rare (alchemy)", "Rare (chaos)", "Alchemy + Vaal"):
        craft_logic.set("Rare (chaos)")
    map_orb_mode.set({
        "Rare (alchemy)": "alchemy",
        "Alchemy + Vaal": "alchemy_vaal",
    }.get(craft_logic.get(), "chaos"))
    map_use_exalt_cb.pack(anchor="w", pady=(2, 0))
    sync_map_mode_controls()
    # Augment kısmını gizle
    augment_frame.grid_remove()
    augment_label.grid_remove()
    use_exalt_cb.grid_remove()
    use_annul_cb.grid_remove()
    cluster_no_regal_two_cb.pack_forget()
    map_summary_thresholds_frame.grid(row=1, column=1, columnspan=2, sticky="nw", padx=(25, 0), pady=(0, 0))
    # Chain aktif
    try: chain_toggle.config(state="normal")
    except Exception: pass
    try: chain_count_entry.config(state="normal")
    except Exception: pass
    # mid ve weights aynı yerde
    logic_frame.grid(row=1, column=0, sticky="nw", pady=(0, 0))
    show_top_controls()
    mid.place(x=PADX, y=95, width=WINDOW_W - 2 * PADX)
    weights.place(x=PADX, y=170, width=WINDOW_W - 2 * PADX)
    # Map tabs ve bottom
    style.configure("TNotebook.Tab", width=(WINDOW_W - 2 * PADX) // 2, padding=[0, 4])
    map_tabs.place(x=PADX, y=204, width=WINDOW_W - 2 * PADX, height=220)
    map_bottom.place(x=PADX, y=439, width=WINDOW_W - 2 * PADX, height=26)

def switch_to_socket():
    global current_mode
    app_mode.set("socket")
    mode_selector_var.set(MODE_VALUE_TO_DISPLAY["socket"])
    hide_flask_guide_panel(hide_arrow=True)
    hide_cluster_trade_panel(hide_arrow=True)
    current_mode = "normal"
    configure_top_controls_for_socket_mode(True)
    map_frame.place_forget()
    map_tabs.place_forget()
    map_bottom.place_forget()
    map_pool_frame.place_forget()
    map_affix_visible[0] = False
    pool.place_forget()
    settings_panel.place_forget()
    bottom.place_forget()
    tabs.place_forget()
    mid.place_forget()
    weights.place_forget()
    base_jewel_frame.place_forget()
    item_frame.place_forget()
    item_mod_pool_frame.place_forget()
    voyage_frame.place_forget()
    auto_flask_frame.place_forget()
    item_mod_pool_visible[0] = False
    hide_top_controls()
    socket_frame.place(x=PADX, y=70, width=WINDOW_W - 2 * PADX, height=204)

def switch_to_base_jewel():
    global current_mode
    app_mode.set("base_jewel")
    mode_selector_var.set(MODE_VALUE_TO_DISPLAY["base_jewel"])
    hide_flask_guide_panel(hide_arrow=True)
    hide_cluster_trade_panel(hide_arrow=True)
    current_mode = "normal"
    refresh_templates()
    configure_top_controls_for_socket_mode(False)
    settings_btn.config(text="Orb Locations", command=lambda: OrbLocationsWindow(root))

    map_frame.place_forget()
    map_tabs.place_forget()
    map_bottom.place_forget()
    map_pool_frame.place_forget()
    map_affix_visible[0] = False
    socket_frame.place_forget()
    pool.place_forget()
    settings_panel.place_forget()
    bottom.place_forget()
    tabs.place_forget()
    mid.place_forget()
    weights.place_forget()
    item_frame.place_forget()
    item_mod_pool_frame.place_forget()
    voyage_frame.place_forget()
    auto_flask_frame.place_forget()
    item_mod_pool_visible[0] = False

    show_top_controls()
    base_jewel_frame.place(
        x=PADX,
        y=104,
        width=WINDOW_W - 2 * PADX,
        height=330,
    )

def switch_to_item():
    global current_mode
    app_mode.set("item")
    mode_selector_var.set(MODE_VALUE_TO_DISPLAY["item"])
    hide_cluster_trade_panel(hide_arrow=True)
    current_mode = "normal"
    refresh_templates()
    configure_top_controls_for_socket_mode(False)
    settings_btn.config(text="Orb Locations", command=lambda: OrbLocationsWindow(root))

    map_frame.place_forget()
    map_tabs.place_forget()
    map_bottom.place_forget()
    map_pool_frame.place_forget()
    map_affix_visible[0] = False
    socket_frame.place_forget()
    base_jewel_frame.place_forget()
    voyage_frame.place_forget()
    auto_flask_frame.place_forget()
    pool.place_forget()
    settings_panel.place_forget()
    bottom.place_forget()
    tabs.place_forget()
    mid.place_forget()
    weights.place_forget()
    item_mod_pool_frame.place_forget()
    item_mod_pool_visible[0] = False

    show_top_controls()
    item_frame.place(
        x=PADX,
        y=104,
        width=WINDOW_W - 2 * PADX,
        height=330,
    )
    show_flask_guide_arrow()

def switch_to_voyage():
    global current_mode
    app_mode.set("voyage")
    mode_selector_var.set(MODE_VALUE_TO_DISPLAY["voyage"])
    hide_flask_guide_panel(hide_arrow=True)
    hide_cluster_trade_panel(hide_arrow=True)
    current_mode = "normal"
    configure_top_controls_for_socket_mode(False)
    settings_btn.config(text="Settings", command=toggle_settings_panel)

    map_frame.place_forget()
    map_tabs.place_forget()
    map_bottom.place_forget()
    map_pool_frame.place_forget()
    map_affix_visible[0] = False
    socket_frame.place_forget()
    base_jewel_frame.place_forget()
    item_frame.place_forget()
    item_mod_pool_frame.place_forget()
    item_mod_pool_visible[0] = False
    pool.place_forget()
    settings_panel.place_forget()
    bottom.place_forget()
    tabs.place_forget()
    mid.place_forget()
    weights.place_forget()
    auto_flask_frame.place_forget()

    hide_top_controls()
    voyage_frame.place(
        x=PADX,
        y=70,
        width=WINDOW_W - 2 * PADX,
        height=364,
    )


def switch_to_auto_flask():
    global current_mode
    app_mode.set("auto_flask")
    mode_selector_var.set(MODE_VALUE_TO_DISPLAY["auto_flask"])
    hide_flask_guide_panel(hide_arrow=True)
    hide_cluster_trade_panel(hide_arrow=True)
    current_mode = "normal"
    configure_top_controls_for_socket_mode(False)

    map_frame.place_forget()
    map_tabs.place_forget()
    map_bottom.place_forget()
    map_pool_frame.place_forget()
    map_affix_visible[0] = False
    socket_frame.place_forget()
    base_jewel_frame.place_forget()
    item_frame.place_forget()
    item_mod_pool_frame.place_forget()
    voyage_frame.place_forget()
    item_mod_pool_visible[0] = False
    pool.place_forget()
    settings_panel.place_forget()
    bottom.place_forget()
    tabs.place_forget()
    mid.place_forget()
    weights.place_forget()

    hide_top_controls()
    auto_flask_frame.place(
        x=PADX,
        y=70,
        width=WINDOW_W - 2 * PADX,
        height=300,
    )

MODE_SWITCHERS = {
    "cluster": switch_to_cluster,
    "map": switch_to_map,
    "socket": switch_to_socket,
    "base_jewel": switch_to_base_jewel,
    "item": switch_to_item,
    "voyage": switch_to_voyage,
    "auto_flask": switch_to_auto_flask,
}


def _on_mode_selected(_event=None):
    mode = MODE_DISPLAY_TO_VALUE.get(mode_selector_var.get(), "cluster")
    MODE_SWITCHERS[mode]()
    settings_cfg.set("General", "last_mode", mode)
    save_settings_now()
    post_action_selector.config(state="disabled" if mode == "auto_flask" else "readonly")
    global_settings_btn.state(["disabled"] if mode == "auto_flask" else ["!disabled"])


def _on_post_action_selected(_event=None):
    action = POST_ACTION_DISPLAY_TO_VALUE.get(
        post_action_display_var.get(), POST_ACTION_NONE
    )
    post_craft_action_var.set(action)
    settings_cfg.set("General", "post_craft_action", action)
    save_settings_now()


def _open_global_settings():
    if app_mode.get() in ("socket", "base_jewel", "item"):
        OrbLocationsWindow(root)
    else:
        toggle_settings_panel()


mode_selector.bind("<<ComboboxSelected>>", _on_mode_selected)
post_action_selector.bind("<<ComboboxSelected>>", _on_post_action_selected)
global_settings_btn.config(command=_open_global_settings)

# ================ SETTINGS PANEL CONTENTS ================
settings_panel = ttk.Frame(root)


def open_phone_notification_settings():
    window = tk.Toplevel(root)
    window.title("Phone Notifications")
    window.geometry(f"430x265+{root.winfo_x() + 20}+{root.winfo_y() + 80}")
    window.configure(bg="#2b2b2b")
    window.resizable(False, False)
    if always_on_top_var.get():
        window.attributes("-topmost", True)

    enabled_var = tk.BooleanVar(
        value=settings_cfg.getboolean("Notifications", "enabled", fallback=False)
    )
    server_var = tk.StringVar(
        value=settings_cfg.get("Notifications", "server", fallback=DEFAULT_NTFY_SERVER)
    )
    topic_var = tk.StringVar(
        value=settings_cfg.get("Notifications", "topic", fallback=generate_ntfy_topic())
    )
    status_var = tk.StringVar(value="")

    body = ttk.Frame(window, padding=(12, 10))
    body.pack(fill="both", expand=True)
    ttk.Checkbutton(body, text="Send notification whenever craft stops", variable=enabled_var).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
    )
    ttk.Label(body, text="ntfy server:").grid(row=1, column=0, sticky="w")
    server_entry = tk.Entry(
        body, textvariable=server_var, bg="#000", fg="#fff", insertbackground="#fff"
    )
    server_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0))
    ttk.Label(body, text="Private topic:").grid(row=2, column=0, sticky="w", pady=(7, 0))
    topic_entry = tk.Entry(
        body, textvariable=topic_var, bg="#000", fg="#fff", insertbackground="#fff"
    )
    topic_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(7, 0))
    body.columnconfigure(1, weight=1)

    help_text = (
        "Telefona ntfy uygulamasini kur. + ile yeni abonelik ekle; server ve topic "
        "alanlarini burada yazan degerlerle ayni gir. Topic'i baskalariyla paylasma."
    )
    ttk.Label(body, text=help_text, wraplength=390, justify="left").grid(
        row=3, column=0, columnspan=3, sticky="w", pady=(10, 6)
    )
    ttk.Label(body, textvariable=status_var, wraplength=390).grid(
        row=4, column=0, columnspan=3, sticky="w", pady=(0, 8)
    )

    def _save(show_message=True):
        topic = topic_var.get().strip()
        if len(topic) < 12 or not re.fullmatch(r"[A-Za-z0-9_-]+", topic):
            gui_error("Topic en az 12 karakter olmali; yalnizca harf, rakam, - ve _ kullan.")
            return False
        settings_cfg.set("Notifications", "enabled", "True" if enabled_var.get() else "False")
        settings_cfg.set("Notifications", "provider", "ntfy")
        settings_cfg.set("Notifications", "server", server_var.get().strip() or DEFAULT_NTFY_SERVER)
        settings_cfg.set("Notifications", "topic", topic)
        save_settings_now()
        status_var.set(f"Subscription: {ntfy_subscription_url(server_var.get(), topic)}")
        if show_message:
            gui_info("Telefon bildirim ayarlari kaydedildi.")
        return True

    def _copy_topic():
        window.clipboard_clear()
        window.clipboard_append(topic_var.get().strip())
        status_var.set("Topic panoya kopyalandi.")

    def _test_worker(server, topic):
        try:
            publish_ntfy(
                server,
                topic,
                "WCA - Test bildirimi",
                "Telefon bildirimleri calisiyor.",
                priority=3,
            )
            root.after(0, lambda: status_var.set("Test bildirimi gonderildi."))
        except Exception as exc:
            root.after(0, lambda: status_var.set(f"Test basarisiz: {exc}"))

    def _test():
        # A successful test should leave real craft notifications enabled too.
        enabled_var.set(True)
        if not _save(show_message=False):
            return
        status_var.set("Bildirimler acildi; test bildirimi gonderiliyor...")
        threading.Thread(
            target=_test_worker,
            args=(server_var.get(), topic_var.get()),
            daemon=True,
        ).start()

    buttons = ttk.Frame(body)
    buttons.grid(row=5, column=0, columnspan=3, sticky="ew")
    ttk.Button(buttons, text="Copy Topic", command=_copy_topic).pack(side="left")
    ttk.Button(buttons, text="Test Notification", command=_test).pack(side="left", padx=6)
    ttk.Button(buttons, text="Save", command=_save).pack(side="right")
    status_var.set(
        f"Subscription: {ntfy_subscription_url(server_var.get(), topic_var.get())}"
    )


def refresh_settings_panel():
    for w in settings_panel.winfo_children():
        w.destroy()

    def _bind_hotkey_entry(entry, which, var):
        def _focus_entry(event=None):
            try:
                entry.focus_set()
            except Exception:
                pass
            return "break"

        def _capture_inline(event):
            key = (event.keysym or "").strip()
            if not key:
                return "break"
            settings_cfg.set("Hotkeys", which, key)
            save_settings_debounced()
            var.set(key)
            start_hotkey_listener()
            root.focus_set()
            return "break"

        entry.bind("<Button-1>", _focus_entry)
        entry.bind("<FocusIn>", lambda e: entry.configure(highlightbackground="#4a4a4a"))
        entry.bind("<FocusOut>", lambda e: entry.configure(highlightbackground="#1e1e1e"))
        entry.bind("<KeyPress>", _capture_inline)
    ttk.Button(
        settings_panel,
        text="Orb Locations",
        style="Dark.TButton",
        command=lambda: OrbLocationsWindow(root),
    ).grid(row=0, column=0, padx=(6, 5), pady=(5, 2), sticky="w")
    ttk.Label(settings_panel, text="Delay (ms):").grid(row=0, column=1, sticky="e")
    tk.Entry(
        settings_panel,
        width=6,
        textvariable=delay_var,
        bg="#000",
        fg="#fff",
        insertbackground="#fff",
    ).grid(row=0, column=2, padx=(4, 5), pady=(5, 2))
    ttk.Label(settings_panel, text="Suggested: 35-40").grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 0), pady=(0, 2))
    ttk.Button(
        settings_panel,
        text="Save",
        style="Dark.TButton",
        command=lambda: (
            settings_cfg.set("General", "delay", delay_var.get()),
            save_settings_debounced(),
            gui_info("Delay saved."),
        ),
    ).grid(row=0, column=3, padx=(0, 5), pady=(5, 2), sticky="w")

    start_disp = tk.StringVar(value=settings_cfg.get("Hotkeys", "start", fallback="F4"))
    stop_disp = tk.StringVar(value=settings_cfg.get("Hotkeys", "stop", fallback="F5"))
    ttk.Label(settings_panel, text="Start Craft:").grid(
        row=2, column=0, sticky="w", padx=(6, 0), pady=(6, 0)
    )
    start_entry = tk.Entry(
        settings_panel,
        width=10,
        textvariable=start_disp,
        state="readonly",
        readonlybackground="#000",
        fg="#fff",
        justify="center",
        relief="flat",
        bd=1,
        highlightthickness=1,
        highlightbackground="#1e1e1e",
        highlightcolor="#4a4a4a",
    )
    start_entry.grid(row=2, column=1, columnspan=2, padx=(4, 5), pady=(6, 0), sticky="w")
    _bind_hotkey_entry(start_entry, "start", start_disp)

    ttk.Label(settings_panel, text="Stop Craft:").grid(
        row=3, column=0, sticky="w", padx=(6, 0), pady=(2, 0)
    )
    stop_entry = tk.Entry(
        settings_panel,
        width=10,
        textvariable=stop_disp,
        state="readonly",
        readonlybackground="#000",
        fg="#fff",
        justify="center",
        relief="flat",
        bd=1,
        highlightthickness=1,
        highlightbackground="#1e1e1e",
        highlightcolor="#4a4a4a",
    )
    stop_entry.grid(row=3, column=1, columnspan=2, padx=(4, 5), pady=(2, 0), sticky="w")
    _bind_hotkey_entry(stop_entry, "stop", stop_disp)

    ttk.Label(
        settings_panel,
        text="Updates: required at startup",
    ).grid(row=4, column=0, columnspan=4, padx=(6, 5), pady=(5, 0), sticky="w")
    ttk.Button(
        settings_panel,
        text="Phone Notifications",
        style="Dark.TButton",
        command=open_phone_notification_settings,
    ).grid(row=1, column=0, padx=(6, 5), pady=(0, 2), sticky="w")

# ================ LOG WINDOW ================
log_window, log_text = None, None
_log_drag_state = {"x": 0, "y": 0}

def toggle_log_window():
    if not (log_window and log_window.winfo_exists()):
        create_log_window()
    if log_window.state() in ("withdrawn", "iconic"):
        log_window.deiconify()
        _on_log_restore()
        update_log_window_position()
    else:
        log_window.withdraw()

def _start_log_drag(event):
    _log_drag_state["x"] = event.x_root - log_window.winfo_x()
    _log_drag_state["y"] = event.y_root - log_window.winfo_y()

def _do_log_drag(event):
    if not (log_window and log_window.winfo_exists()):
        return
    lw = max(log_window.winfo_width(), log_window.winfo_reqwidth(), 320)
    lh = max(log_window.winfo_height(), log_window.winfo_reqheight(), 200)
    x = event.x_root - _log_drag_state["x"]
    y = event.y_root - _log_drag_state["y"]
    log_window.geometry(f"{lw}x{lh}+{x}+{y}")

def _apply_log_window_rounding():
    if log_window and log_window.winfo_exists():
        try:
            width = max(log_window.winfo_width(), log_window.winfo_reqwidth(), 320)
            height = max(log_window.winfo_height(), log_window.winfo_reqheight(), 200)
            _apply_window_rounding(log_window, width, height, radius=18)
        except Exception:
            pass

def _schedule_log_rounding(_event=None):
    if log_window and log_window.winfo_exists():
        log_window.after_idle(_apply_log_window_rounding)
        log_window.after(10, _apply_log_window_rounding)
        log_window.after(40, _apply_log_window_rounding)
        log_window.after(100, _apply_log_window_rounding)

def _minimize_log_window():
    if not (log_window and log_window.winfo_exists()):
        return
    try:
        log_window.overrideredirect(False)
        log_window.iconify()
    except Exception:
        pass

def _on_log_restore(event=None):
    if not (log_window and log_window.winfo_exists()):
        return
    try:
        log_window.overrideredirect(True)
    except Exception:
        pass
    _refresh_log_text_from_history()
    _schedule_log_rounding()

def _is_log_window_visible():
    return bool(log_window and log_window.winfo_exists() and log_window.state() == "normal")

def _recent_log_history_view():
    history = list(LOG_GUI_HISTORY)
    if not history:
        return []
    orb_indices = [idx for idx, msg in enumerate(history) if isinstance(msg, str) and msg.startswith("🧿")]
    if orb_indices:
        anchor = orb_indices[-min(LOG_GUI_ORB_CONTEXT, len(orb_indices))]
        start = max(0, anchor - LOG_GUI_PRE_ORB_LINES)
    else:
        start = max(0, len(history) - LOG_GUI_FALLBACK_LINES)
    return history[start:]

def _refresh_log_text_from_history():
    if not (log_text and log_text.winfo_exists()):
        return
    log_text.configure(state="normal")
    log_text.delete("1.0", "end")
    history_view = _recent_log_history_view()
    if history_view:
        log_text.insert("end", "".join(f"{msg}\n" for msg in history_view))
        log_text.see("end")
    log_text.configure(state="disabled")

def create_log_window():
    global log_window, log_text
    if log_window and log_window.winfo_exists():
        log_window.lift()
        return
    log_window = tk.Toplevel(root)
    log_window.title("Logs")
    log_window.configure(bg="#2b2b2b")
    log_window.overrideredirect(True)
    log_window.protocol("WM_DELETE_WINDOW", log_window.withdraw)
    if always_on_top_var.get():
        log_window.attributes("-topmost", True)

    title_grip = tk.Frame(log_window, bg=title_bar_bg, height=21, highlightthickness=0, bd=0)
    title_grip.place(x=0, y=0, relwidth=1, height=21)
    title_grip.bind("<ButtonPress-1>", _start_log_drag)
    title_grip.bind("<B1-Motion>", _do_log_drag)

    tk.Button(
        log_window,
        text="—",
        command=_minimize_log_window,
        bg=title_bar_bg,
        fg="#e6e6e6",
        activebackground="#3a3a3a",
        activeforeground="#ffffff",
        relief="flat",
        bd=0,
        font=("Tahoma", 9, "bold"),
        padx=0,
        pady=0,
        highlightthickness=0,
    ).place(relx=1.0, x=-44, y=0, width=22, height=18)
    tk.Button(
        log_window,
        text="×",
        command=log_window.withdraw,
        bg=title_bar_bg,
        fg="#e6e6e6",
        activebackground="#5a2a2a",
        activeforeground="#ffffff",
        relief="flat",
        bd=0,
        font=("Tahoma", 9, "bold"),
        padx=0,
        pady=0,
        highlightthickness=0,
    ).place(relx=1.0, x=-22, y=0, width=22, height=18)

    body = tk.Frame(log_window, bg="#2b2b2b")
    body.pack(fill="both", expand=True, pady=(21, 0))

    bottom_frame = tk.Frame(body, bg="#2b2b2b")
    bottom_frame.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
    ttk.Button(
        bottom_frame,
        text="Clear",
        command=clear_log_text,
        style="Dark.TButton",
    ).pack(side="left", padx=(0, 4))
    ttk.Button(
        bottom_frame,
        text="Export",
        command=export_log_text,
        style="Dark.TButton",
    ).pack(side="left")
    log_text = tk.Text(
        body,
        bg="#000",
        fg="#fff",
        insertbackground="#fff",
        wrap="word",
        state="disabled",
        font=("Tahoma", 8),
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground="#0f0f0f",
        highlightcolor="#0f0f0f",
    )
    log_text.pack(fill="both", expand=True, padx=4, pady=(0, 4))
    log_window.bind("<Map>", _on_log_restore)
    root.update_idletasks()
    log_window.update_idletasks()
    lw = max(log_window.winfo_width(), log_window.winfo_reqwidth(), 420)
    target_h = max(200, root.winfo_height())
    log_window.geometry(f"{lw}x{target_h}+{root.winfo_x() + root.winfo_width() + 3}+{root.winfo_y()}")
    _schedule_log_rounding()
    _refresh_log_text_from_history()
    log_window.withdraw()

def clear_log_text():
    LOG_GUI_HISTORY.clear()
    if log_text and log_text.winfo_exists():
        log_text.configure(state="normal")
        log_text.delete("1.0", "end")
        log_text.configure(state="disabled")

def export_log_text():
    if not (log_text and log_text.winfo_exists()):
        return
    content = log_text.get("1.0", "end-1c")
    if not content.strip():
        gui_info("Log boş.")
        return
    timestamp = time.strftime("%H%M.%d%m%Y")
    filename = f"log-{timestamp}.txt"
    filepath = os.path.join(BASE_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    gui_info(f"Log kaydedildi: {filename}")

def update_log_window_position(event=None):
    if log_window and log_window.winfo_exists() and log_window.state() == "normal":
        root.update_idletasks()
        log_window.update_idletasks()
        rx, ry, rw, rh = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
        lw = max(log_window.winfo_width(), log_window.winfo_reqwidth(), 420)
        target_h = max(200, rh)
        log_window.geometry(f"{lw}x{target_h}+{rx + rw + 3}+{ry}")
        _schedule_log_rounding()

def process_gui_queue():
    try:
        while not gui_queue.empty():
            t, title, msg = gui_queue.get_nowait()
            if t == "info":
                messagebox.showinfo(title, msg, parent=root)
            elif t == "error":
                messagebox.showerror(title, msg, parent=root)
            elif t == "warning":
                messagebox.showwarning(title, msg, parent=root)
    except Exception as e:
        log_message(f"[HATA-GUIQ] {e}")
    finally:
        if root and root.winfo_exists():
            root.after(200, process_gui_queue)

def process_log_queue():
    try:
        buf = []
        while not log_queue.empty():
            buf.append(log_queue.get_nowait())
        if buf:
            LOG_GUI_HISTORY.extend(buf)
            if _is_log_window_visible() and log_text and log_text.winfo_exists():
                log_text.configure(state="normal")
                log_text.insert("end", "".join(f"{msg}\n" for msg in buf))
                try:
                    line_count = int(log_text.index("end-1c").split(".", 1)[0])
                    overflow = line_count - LOG_GUI_LINE_LIMIT
                    if overflow > 0:
                        log_text.delete("1.0", f"{overflow + 1}.0")
                except Exception:
                    pass
                log_text.see("end")
                log_text.configure(state="disabled")
    except Exception as e:
        try:
            sys.__stdout__.write(f"[LOG_ERR] {e}\n{traceback.format_exc()}\n")
        except Exception:
            pass
    finally:
        if root and root.winfo_exists():
            root.after(120 if _is_log_window_visible() else 250, process_log_queue)

# ================ WINDOW EVENTS & MAIN ================
def on_main_minimize(event=None):
    hide_flask_guide_panel()
    hide_cluster_trade_panel()
    if log_window and log_window.winfo_exists():
        log_window.withdraw()

def on_main_restore(event=None):
    try:
        root.overrideredirect(True)
        root.after(10, _apply_rounded_corners)
        root.after(50, _apply_rounded_corners)
        root.after(120, _apply_rounded_corners)
    except Exception:
        pass
    if log_window and log_window.winfo_exists():
        update_log_window_position()

def on_main_close(event=None):
    _stop_tray_icon()
    hide_flask_guide_panel(hide_arrow=True)
    hide_cluster_trade_panel(hide_arrow=True)
    try:
        _notification_set_reason("Program kullanici tarafindan kapatildi.", "manual", 100)
        stop_event.set()
    except Exception:
        pass
    try:
        geo = root.geometry()  # "310x460+x+y"
        pos = "+".join(geo.split("+")[1:])  # "x+y"
        settings_cfg.set("General", "window_pos", pos)
        save_settings_now()
    except Exception:
        pass
    root.destroy()

start_hotkey_listener()
MODE_SWITCHERS[startup_mode]()
post_action_selector.config(
    state="disabled" if startup_mode == "auto_flask" else "readonly"
)
global_settings_btn.state(
    ["disabled"] if startup_mode == "auto_flask" else ["!disabled"]
)
root.after(200, process_log_queue)
root.after(200, process_gui_queue)
create_log_window()
root.bind("<Configure>", _schedule_root_rounding, add="+")
root.bind("<Configure>", update_log_window_position)
root.bind("<Configure>", sync_flask_guide_position, add="+")
root.bind("<Configure>", sync_cluster_trade_position, add="+")
root.bind("<Unmap>", on_main_minimize)
root.bind("<Map>", on_main_restore)
root.protocol("WM_DELETE_WINDOW", on_main_close)
root.after(0, begin_required_update_check)
log_message(f"[INIT] {APP_NAME} v{APP_VERSION} (MicroDrift v2 + RAW FailSafe) hazır.")
try:
    template_cb.config(state="readonly")
    refresh_templates()
except Exception:
    pass
root.mainloop()
