import psutil
import subprocess

def get_top_cpu_processes(limit: int = 10) -> list:
    """11. Топ процессов по потреблению CPU"""
    processes = []
    # Первичный замер для вычисления дельты CPU
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            p.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    import time
    time.sleep(0.2)

    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            info = p.info
            cpu = p.cpu_percent(interval=None)
            mem_mb = round(info['memory_info'].rss / (1024 * 1024), 1) if info.get('memory_info') else 0
            processes.append({
                "pid": info['pid'],
                "name": info['name'],
                "cpu": cpu,
                "ram_mb": mem_mb
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda x: x['cpu'], reverse=True)
    return processes[:limit]

def get_top_ram_processes(limit: int = 10) -> list:
    """12. Топ процессов по потреблению оперативной памяти"""
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'memory_info']):
        try:
            info = p.info
            mem_mb = round(info['memory_info'].rss / (1024 * 1024), 1) if info.get('memory_info') else 0
            processes.append({
                "pid": info['pid'],
                "name": info['name'],
                "ram_mb": mem_mb,
                "ram_percent": round(info['memory_percent'], 1) if info.get('memory_percent') else 0
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda x: x['ram_mb'], reverse=True)
    return processes[:limit]

def get_windows_services_status(limit: int = 15) -> list:
    """13. Список системных служб Windows"""
    services = []
    if hasattr(psutil, "win_service_iter"):
        try:
            for s in psutil.win_service_iter():
                try:
                    info = s.as_dict()
                    services.append({
                        "name": info.get("name"),
                        "display_name": info.get("display_name"),
                        "status": info.get("status")
                    })
                except Exception:
                    continue
        except Exception:
            pass

    return services[:limit]

def kill_process_by_pid(pid: int) -> dict:
    """14. Завершение процесса по указанному PID"""
    try:
        pid = int(pid)
        proc = psutil.Process(pid)
        proc_name = proc.name()
        proc.terminate()
        proc.wait(timeout=3)
        return {"success": True, "message": f"Процесс {proc_name} (PID: {pid}) успешно завершен"}
    except psutil.NoSuchProcess:
        return {"success": False, "message": f"Процесс с PID {pid} не найден"}
    except psutil.AccessDenied:
        return {"success": False, "message": f"Отказано в доступе для завершения PID {pid} (требуются права администратора)"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def restart_service_by_name(service_name: str) -> dict:
    """15. Перезапуск службы Windows"""
    try:
        res = subprocess.run(["sc", "stop", service_name], capture_output=True, text=True, timeout=5)
        import time
        time.sleep(1)
        res_start = subprocess.run(["sc", "start", service_name], capture_output=True, text=True, timeout=5)
        return {
            "success": True,
            "message": f"Команда перезапуска службы '{service_name}' отправлена"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
