import ctypes
import os
import shutil
import subprocess
import tempfile

def clean_temp_files() -> dict:
    """16. Очистка временных файлов пользователя (%TEMP%)"""
    temp_dir = tempfile.gettempdir()
    deleted_files = 0
    deleted_dirs = 0
    freed_bytes = 0

    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for f in files:
            file_path = os.path.join(root, f)
            try:
                size = os.path.getsize(file_path)
                os.remove(file_path)
                deleted_files += 1
                freed_bytes += size
            except Exception:
                pass

        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
                deleted_dirs += 1
            except Exception:
                pass

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    return {
        "success": True,
        "temp_path": temp_dir,
        "freed_mb": freed_mb,
        "deleted_files": deleted_files,
        "deleted_folders": deleted_dirs
    }

def send_user_popup(message: str, title: str = "Техническая поддержка") -> dict:
    """17. Отправка всплывающего сообщения пользователю на экран"""
    if not message:
        return {"success": False, "message": "Текст сообщения пуст"}

    try:
        # Используем PowerShell для создания красивого всплывающего диалогового окна
        ps_command = f"""
        Add-Type -AssemblyName PresentationFramework;
        [System.Windows.MessageBox]::Show('{message}', '{title}', 'OK', 'Information');
        """
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_command], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return {"success": True, "message": f"Окно с сообщением отправлено на экран пользователя"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def lock_workstation() -> dict:
    """18. Блокировка рабочего стола (экран входа Windows)"""
    try:
        if os.name == 'nt':
            ctypes.windll.user32.LockWorkStation()
            return {"success": True, "message": "Рабочая станция заблокирована"}
        else:
            return {"success": False, "message": "Блокировка поддерживается только в Windows"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def system_reboot(delay_seconds: int = 30) -> dict:
    """19. Перезагрузка системы с таймером"""
    try:
        if os.name == 'nt':
            subprocess.run(["shutdown", "/r", "/t", str(delay_seconds), "/c", "Плановая перезагрузка администратором"], check=True)
            return {"success": True, "message": f"Команда перезагрузки отправлена. Система перезагрузится через {delay_seconds} сек."}
        else:
            subprocess.run(["sudo", "reboot"], check=True)
            return {"success": True, "message": "Команда перезагрузки отправлена"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def system_shutdown(delay_seconds: int = 30) -> dict:
    """20. Корректное выключение компьютера"""
    try:
        if os.name == 'nt':
            subprocess.run(["shutdown", "/s", "/t", str(delay_seconds), "/c", "Выключение по команде администратора"], check=True)
            return {"success": True, "message": f"Команда выключения отправлена. Компьютер выключится через {delay_seconds} сек."}
        else:
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
            return {"success": True, "message": "Команда выключения отправлена"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def cancel_system_shutdown() -> dict:
    """Отмена запланированной перезагрузки или выключения"""
    try:
        if os.name == 'nt':
            subprocess.run(["shutdown", "/a"], check=True)
            return {"success": True, "message": "Выключение / перезагрузка успешно отменены"}
        return {"success": False, "message": "Не поддерживается"}
    except Exception as e:
        return {"success": False, "message": str(e)}
