import os
import platform
import socket
import time
import uuid
import psutil

def get_machine_id() -> str:
    """Генерирует стабильный уникальный идентификатор машины"""
    node = uuid.getnode()
    return f"cli_{hex(node)[2:]}"

def get_static_sysinfo() -> dict:
    """Возвращает статическую информацию о клиенте и правах процесса"""
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0 if os.name == 'nt' else os.geteuid() == 0
    except Exception:
        is_admin = False

    return {
        "hostname": socket.gethostname(),
        "username": os.getlogin() if hasattr(os, "getlogin") else os.getenv("USERNAME", "Unknown"),
        "os_info": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
        "is_admin": is_admin
    }

def get_dynamic_sysinfo() -> dict:
    """Возвращает текущие показатели загрузки системы (CPU, RAM, Disk, Uptime)"""
    # RAM
    ram = psutil.virtual_memory()
    ram_data = {
        "total_gb": round(ram.total / (1024 ** 3), 2),
        "used_gb": round(ram.used / (1024 ** 3), 2),
        "percent": ram.percent
    }

    # Disk C: / Root
    disk_path = "C:\\" if platform.system() == "Windows" else "/"
    try:
        disk = psutil.disk_usage(disk_path)
        disk_data = {
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "used_gb": round(disk.used / (1024 ** 3), 2),
            "percent": disk.percent
        }
    except Exception:
        disk_data = {"total_gb": 0, "used_gb": 0, "percent": 0}

    # Uptime
    boot_time = psutil.boot_time()
    uptime_hours = round((time.time() - boot_time) / 3600, 1)

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram": ram_data,
        "disk": disk_data,
        "uptime_hours": uptime_hours
    }
