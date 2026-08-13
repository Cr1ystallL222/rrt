import datetime
import os
import platform
import psutil
import time

def get_full_hardware_info() -> dict:
    """1. Полная системная и аппаратная информация"""
    cpu_freq = psutil.cpu_freq()
    freq_str = f"{round(cpu_freq.current, 0)} MHz" if cpu_freq else "N/A"
    
    return {
        "os": f"{platform.system()} {platform.release()} (Build {platform.version()})",
        "architecture": platform.machine(),
        "processor": platform.processor() or "Unknown",
        "cores_physical": psutil.cpu_count(logical=False),
        "cores_logical": psutil.cpu_count(logical=True),
        "cpu_frequency": freq_str,
        "python_version": platform.python_version()
    }

def get_ram_detailed() -> dict:
    """2. Детальная статистика оперативной памяти и файла подкачки"""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    gb = 1024 ** 3

    return {
        "total_gb": round(vm.total / gb, 2),
        "used_gb": round(vm.used / gb, 2),
        "free_gb": round(vm.available / gb, 2),
        "percent": vm.percent,
        "swap_total_gb": round(swap.total / gb, 2),
        "swap_used_gb": round(swap.used / gb, 2),
        "swap_percent": swap.percent
    }

def get_all_disks() -> list:
    """3. Статус всех дисковых разделов (C:, D:, и др.)"""
    disks = []
    gb = 1024 ** 3

    for part in psutil.disk_partitions(all=False):
        if os.name == 'nt' and ('cdrom' in part.opts or part.fstype == ''):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / gb, 2),
                "used_gb": round(usage.used / gb, 2),
                "free_gb": round(usage.free / gb, 2),
                "percent": usage.percent
            })
        except PermissionError:
            continue

    return disks

def get_battery_status() -> dict:
    """4. Состояние аккумулятора и питания"""
    battery = psutil.sensors_battery()
    if not battery:
        return {"has_battery": False, "status": "Устройство работает от стационарной сети (аккумулятор не обнаружен)"}

    return {
        "has_battery": True,
        "percent": battery.percent,
        "power_plugged": battery.power_plugged,
        "secsleft_min": round(battery.secsleft / 60, 1) if battery.secsleft > 0 else "Неизвестно"
    }

def get_uptime_and_boot() -> dict:
    """5. Точное время последней загрузки и аптайм"""
    boot_timestamp = psutil.boot_time()
    boot_dt = datetime.datetime.fromtimestamp(boot_timestamp)
    delta = datetime.datetime.now() - boot_dt

    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    return {
        "boot_time": boot_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_str": f"{days} дн. {hours} ч. {minutes} мин.",
        "uptime_hours_total": round(delta.total_seconds() / 3600, 1)
    }
