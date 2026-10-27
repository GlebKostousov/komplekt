"""Подготовить приложение и открыть его в браузере без команд для пользователя."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def _arguments() -> argparse.Namespace:
    """Разрешить запуск без открытия вкладки при ручной проверке."""
    parser = argparse.ArgumentParser(description="Локальный запуск приложения Комплект")
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def _check_python() -> None:
    """Не создавать несовместимое окружение молча."""
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError(
            "Для этой версии нужен Python 3.13. Установите его с python.org "
            "и снова откройте start.cmd. Подробные шаги есть в README.md."
        )


def _prepare(root: Path) -> Path:
    """Установить только закреплённые зависимости при первом запуске."""
    environment = root / ".venv"
    executable = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not executable.exists():
        print("Первый запуск. Подготавливаю приложение — это займёт несколько минут.", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    requirements = root / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment / ".komplekt-dependencies"
    installed = marker.read_text() if marker.exists() else ""
    if installed != digest:
        _install(executable, requirements)
        marker.write_text(digest)
    return executable


def _install(executable: Path, requirements: Path) -> None:
    """Установить зависимости; данные пользователя и исходники не отправляются."""
    print("Устанавливаю необходимые библиотеки. На этом шаге нужен интернет.", flush=True)
    subprocess.run([str(executable), "-m", "ensurepip", "--upgrade"], check=True)
    subprocess.run([
        str(executable), "-m", "pip", "install", "--disable-pip-version-check",
        "-r", str(requirements),
    ], check=True)


def _is_our_application(address: str) -> bool:
    """Не открыть вместо приложения постороннюю страницу на занятом порту."""
    try:
        with urllib.request.urlopen(address + "/api/health", timeout=1) as response:
            result = json.loads(response.read(4096))
        return isinstance(result, dict) and result.get("application") == "komplekt"
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _wait_ready(process: subprocess.Popen[bytes], address: str) -> None:
    """Открывать вкладку только после готовности приложения."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "Приложение не запустилось. Возможно, адрес 127.0.0.1:8765 занят. "
                "Посмотрите сообщение выше и раздел «Если приложение не открылось» в README.md."
            )
        if _is_our_application(address):
            return
        time.sleep(0.25)
    raise RuntimeError("Запуск занял больше 30 секунд. Закройте окно и попробуйте снова.")


def _run(root: Path, executable: Path, address: str, open_browser: bool) -> None:
    """Держать приложение открытым до остановки пользователем."""
    process = subprocess.Popen([
        str(executable), "-m", "uvicorn", "app:create_app", "--factory",
        "--host", "127.0.0.1", "--port", "8765", "--log-level", "warning",
    ], cwd=root)
    try:
        _wait_ready(process, address)
        print(f"\nКомплект готов: {address}\n", flush=True)
        print("Оставьте это окно открытым. Для остановки нажмите Ctrl+C.", flush=True)
        if open_browser:
            webbrowser.open(address)
        process.wait()
    except KeyboardInterrupt:
        print("\nПриложение остановлено. Сохранённые данные остались на месте.")
    finally:
        _stop(process)


def _stop(process: subprocess.Popen[bytes]) -> None:
    """Не оставлять запущенный сервер после закрытия запускающего процесса."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main() -> int:
    """Проверить готовую сборку и вывести понятную причину ошибки запуска."""
    try:
        _check_python()
        arguments = _arguments()
        root = Path(__file__).resolve().parent.parent
        address = "http://127.0.0.1:8765"
        if _is_our_application(address):
            print(f"Приложение уже открыто: {address}")
            if not arguments.no_browser:
                webbrowser.open(address)
            return 0
        if not (root / "frontend" / "dist" / "index.html").exists():
            raise RuntimeError(
                "Не найдена готовая сборка интерфейса. Распакуйте архив целиком. "
                "Для разработчика шаг сборки описан в docs/development.md."
            )
        _run(root, _prepare(root), address, not arguments.no_browser)
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"\nНе получилось запустить приложение: {error}\n")
        print("Ваши данные не удалены. Помощь: раздел «Если приложение не открылось» в README.md.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
