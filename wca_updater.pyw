# -*- coding: utf-8 -*-
"""Atomic updater for Waukeen Crafting Assistant Windows releases."""

import argparse
import ctypes
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile


APP_EXE = "Waukeen Crafting Assistant.exe"
MAX_ARCHIVE_FILES = 30_000
MAX_UNCOMPRESSED_BYTES = 1_500 * 1024 * 1024
PROCESS_SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT_MS = 120_000


def _log(message):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    path = Path(tempfile.gettempdir()) / "WCA-Updater.log"
    try:
        with path.open("a", encoding="utf-8") as output:
            output.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def _message(message, error=False):
    try:
        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, str(message), "WCA Updater", flags)
    except Exception:
        pass


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _wait_for_process(pid):
    if pid <= 0:
        return
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        result = ctypes.windll.kernel32.WaitForSingleObject(handle, WAIT_TIMEOUT_MS)
        if result == 0x00000102:
            raise RuntimeError("WCA belirtilen surede kapanmadi.")
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _safe_member_path(staging, member_name):
    normalized = str(member_name or "").replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or not relative.parts:
        raise RuntimeError("Guncelleme paketinde gecersiz dosya yolu var.")
    if any(part in ("", ".", "..") for part in relative.parts):
        raise RuntimeError("Guncelleme paketinde guvensiz dosya yolu var.")
    if ":" in relative.parts[0]:
        raise RuntimeError("Guncelleme paketinde surucu yolu var.")
    destination = staging.joinpath(*relative.parts)
    destination.resolve().relative_to(staging.resolve())
    return destination


def _extract_package(package, staging):
    total_size = 0
    with zipfile.ZipFile(package, "r") as archive:
        members = archive.infolist()
        if not members or len(members) > MAX_ARCHIVE_FILES:
            raise RuntimeError("Guncelleme paketindeki dosya sayisi gecersiz.")
        for member in members:
            total_size += int(member.file_size)
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise RuntimeError("Guncelleme paketinin acilmis boyutu cok buyuk.")
            destination = _safe_member_path(staging, member.filename)
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


def _release_root(staging):
    if (staging / APP_EXE).is_file():
        return staging
    candidates = [
        child for child in staging.iterdir()
        if child.is_dir() and (child / APP_EXE).is_file()
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(f"Guncelleme paketinde {APP_EXE} bulunamadi.")


def _preserve_user_data(backup, target):
    relative_paths = (
        Path("_internal") / "settings.ini",
        Path("settings.ini"),
        Path("_internal") / "data" / "proxies.json",
        Path("data") / "proxies.json",
    )
    for relative in relative_paths:
        old_path = backup / relative
        if old_path.is_file():
            new_path = target / relative
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_path, new_path)

    for relative in (Path("_internal") / "logs", Path("logs")):
        old_logs = backup / relative
        if old_logs.is_dir():
            new_logs = target / relative
            shutil.copytree(old_logs, new_logs, dirs_exist_ok=True)


def _validate_target(target):
    target = target.resolve()
    if not target.is_absolute() or target == Path(target.anchor):
        raise RuntimeError("Kurulum hedefi guvenli degil.")
    if target.parent == target:
        raise RuntimeError("Kurulum hedefi gecersiz.")
    if not (target / APP_EXE).is_file():
        raise RuntimeError(f"Kurulum klasorunde {APP_EXE} bulunamadi.")
    return target


def _clear_directory(directory):
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _copy_release(release_root, target):
    shutil.copytree(release_root, target, dirs_exist_ok=True)


def _install_in_place(release_root, target):
    """Fallback for OneDrive folders that cannot be renamed while synchronized."""
    backup_parent = Path(tempfile.mkdtemp(prefix="wca-install-backup-"))
    backup = backup_parent / "installation"
    shutil.copytree(target, backup)
    keep_backup = False
    try:
        _clear_directory(target)
        _copy_release(release_root, target)
        if not (target / APP_EXE).is_file():
            raise RuntimeError("Yeni uygulama dosyasi kopyalanamadi.")
        _preserve_user_data(backup, target)
    except Exception:
        try:
            _clear_directory(target)
            _copy_release(backup, target)
        except Exception as rollback_error:
            keep_backup = True
            raise RuntimeError(
                "Guncelleme ve otomatik geri yukleme basarisiz oldu. "
                f"Yedek klasoru: {backup}"
            ) from rollback_error
        raise
    finally:
        if not keep_backup:
            shutil.rmtree(backup_parent, ignore_errors=True)


def _install(release_root, target):
    backup = target.with_name(
        f"{target.name}.backup-{int(time.time())}-{os.getpid()}"
    )
    if backup.exists():
        raise RuntimeError("Guncelleme yedek klasoru zaten mevcut.")

    try:
        target.rename(backup)
    except OSError as exc:
        _log(
            "Atomic directory swap unavailable; using in-place rollback mode: "
            f"{exc}"
        )
        _install_in_place(release_root, target)
        return

    try:
        shutil.copytree(release_root, target)
        if not (target / APP_EXE).is_file():
            raise RuntimeError("Yeni uygulama dosyasi kopyalanamadi.")
        _preserve_user_data(backup, target)
    except Exception:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        backup.rename(target)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--restart", action="store_true")
    return parser.parse_args()


def main():
    args = _parse_args()
    package = Path(args.package).resolve()
    target = _validate_target(Path(args.target))
    expected_sha = str(args.expected_sha256).strip().lower()
    if len(expected_sha) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha):
        raise RuntimeError("Beklenen SHA-256 degeri gecersiz.")
    if not package.is_file():
        raise RuntimeError("Guncelleme paketi bulunamadi.")
    if _sha256(package) != expected_sha:
        raise RuntimeError("Guncelleme paketi SHA-256 dogrulamasindan gecemedi.")

    _log(f"Update started: target={target}")
    _wait_for_process(args.pid)
    with tempfile.TemporaryDirectory(prefix="wca-stage-") as staging_name:
        staging = Path(staging_name)
        _extract_package(package, staging)
        release_root = _release_root(staging)
        _install(release_root, target)
    _log("Update installed successfully.")

    if args.restart:
        subprocess.Popen(
            [str(target / APP_EXE)],
            cwd=str(target),
            close_fds=True,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _log(f"Update failed: {exc}\n{traceback.format_exc()}")
        _message(f"Guncelleme uygulanamadi.\n\n{exc}\n\nEski kurulum korundu.", error=True)
        sys.exit(1)
