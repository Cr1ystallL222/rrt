import ctypes
import datetime
import io
import os
import platform
import subprocess
from typing import Dict, List, Union


def is_running_as_admin() -> bool:
    """Проверка наличия прав локального администратора"""
    if os.name != "nt":
        return os.geteuid() == 0
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_cli_diagnostic(cmd_type: str) -> dict:
    """
    Выполнение стандартных системных диагностических утилит Windows
    с перехватом вывода в кодировке cp866.
    """
    cmd_map = {
        "ipconfig": ["ipconfig", "/all"],
        "systeminfo": ["systeminfo"],
        "route": ["route", "print"],
        "arp": ["arp", "-a"],
        "whoami": ["whoami", "/all"],
        "netstat_summary": ["netstat", "-e"]
    }

    command = cmd_map.get(cmd_type)
    if not command:
        return {"success": False, "error": f"Неизвестный тип диагностики: {cmd_type}"}

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="replace",
            timeout=25
        )

        return {
            "success": process.returncode == 0,
            "command": " ".join(command),
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Таймаут выполнения команды (превышено 25с)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_full_diagnostic_report() -> io.BytesIO:
    """
    Формирует комплексный текстовый отчет о состоянии системы в памяти (RAM)
    для экспорта администратору.
    """
    report_lines = [
        "=" * 70,
        f"КОМПЛЕКСНЫЙ ОТЧЕТ ДИАГНОСТИКИ РАБОЧЕЙ СТАНЦИИ",
        f"Дата формирования: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Права процесса: {'Администратор (Elevated)' if is_running_as_admin() else 'Обычный пользователь'}",
        "=" * 70,
        ""
    ]

    for title, cmd_key in [
        ("1. СЕТЕВАЯ КОНФИГУРАЦИЯ (IPCONFIG)", "ipconfig"),
        ("2. ТАБЛИЦА МАРШРУТИЗАЦИИ (ROUTE PRINT)", "route"),
        ("3. ТАБЛИЦА ARP СОСЕДЕЙ", "arp"),
        ("4. ИНФОРМАЦИЯ О СИСТЕМЕ И СБОРКЕ (SYSTEMINFO)", "systeminfo")
    ]:
        report_lines.append(f"\n--- {title} ---")
        res = run_cli_diagnostic(cmd_key)
        if res.get("success"):
            report_lines.append(res.get("stdout", ""))
        else:
            report_lines.append(f"Ошибка сбора данных: {res.get('error')}")

    content = "\n".join(report_lines)
    buffer = io.BytesIO(content.encode("utf-8"))
    buffer.seek(0)
    return buffer
