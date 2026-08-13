import base64
import datetime
import io
import math
import os
import zipfile
from typing import Dict, List, Optional


ALREADY_COMPRESSED_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".mp3", ".wav", ".aac", ".flac", ".ogg",
    ".iso", ".img", ".jpg", ".jpeg", ".png", ".webp"
}


def list_directory_contents(dir_path: Optional[str] = None) -> dict:
    """
    Получает список файлов и папок в указанной директории.
    Если путь не указан, открывает домашнюю папку пользователя.
    """
    if not dir_path or dir_path.strip() == "":
        dir_path = os.path.expanduser("~")

    dir_path = os.path.abspath(dir_path)

    if not os.path.exists(dir_path):
        return {"success": False, "error": f"Путь не существует: {dir_path}"}
    if not os.path.isdir(dir_path):
        return {"success": False, "error": f"Указанный путь не является папкой: {dir_path}"}

    items: List[dict] = []
    try:
        with os.scandir(dir_path) as entries:
            for entry in entries:
                try:
                    stat = entry.stat()
                    is_dir = entry.is_dir()
                    size_str = "[DIR]" if is_dir else f"{round(stat.st_size / 1024, 1)} KB"
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

                    items.append({
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": is_dir,
                        "size": size_str,
                        "size_bytes": stat.st_size if not is_dir else 0,
                        "modified": mtime
                    })
                except (PermissionError, OSError):
                    continue

        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "success": True,
            "current_path": dir_path,
            "parent_path": os.path.dirname(dir_path) if dir_path != os.path.dirname(dir_path) else None,
            "total_items": len(items),
            "items": items[:40]
        }
    except PermissionError:
        return {"success": False, "error": f"Отказано в доступе к директории: {dir_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_file_for_download(file_path: str, chunk_size_mb: int = 40) -> dict:
    """
    Считывает файл любого размера. Если файл > 40 МБ:
    1. Для несжатых форматов (txt, log, doc, csv, exe, etc.) сжимает быстрым ZIP (level 1).
    2. Если файл уже сжат или после сжатия всё ещё > 40 МБ, делит на тома по 40 МБ.
    """
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не найден: {file_path}"}
    if os.path.isdir(file_path):
        return {"success": False, "error": f"Указанный путь является папкой, а не файлом: {file_path}"}

    try:
        orig_size = os.path.getsize(file_path)
        base_name = os.path.basename(file_path)
        _, ext = os.path.splitext(base_name)
        chunk_size_bytes = chunk_size_mb * 1024 * 1024

        # Случай 1: Файл <= 40 МБ - читаем напрямую
        if orig_size <= chunk_size_bytes:
            with open(file_path, "rb") as f:
                content = f.read()

            return {
                "success": True,
                "is_multipart": False,
                "is_compressed": False,
                "original_name": base_name,
                "original_size_mb": round(orig_size / (1024 * 1024), 2),
                "total_parts": 1,
                "parts": [{
                    "filename": base_name,
                    "size_kb": round(orig_size / 1024, 2),
                    "file_base64": base64.b64encode(content).decode("utf-8")
                }]
            }

        # Случай 2: Файл > 40 МБ
        target_bytes = None
        is_zip = False
        target_name = base_name

        # Если расширение не входит в список уже сжатых, пробуем быстрое сжатие
        if ext.lower() not in ALREADY_COMPRESSED_EXTENSIONS:
            try:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zip_f:
                    zip_f.write(file_path, arcname=base_name)
                zipped = zip_buffer.getvalue()
                if len(zipped) < orig_size:
                    target_bytes = zipped
                    is_zip = True
                    target_name = f"{base_name}.zip"
            except Exception:
                target_bytes = None

        # Если не сжимали или сжатие не помогло:
        if target_bytes is None:
            with open(file_path, "rb") as f:
                target_bytes = f.read()

        total_bytes_len = len(target_bytes)

        # Если после сжатия поместился в 40 МБ
        if total_bytes_len <= chunk_size_bytes:
            return {
                "success": True,
                "is_multipart": False,
                "is_compressed": is_zip,
                "original_name": base_name,
                "original_size_mb": round(orig_size / (1024 * 1024), 2),
                "total_parts": 1,
                "parts": [{
                    "filename": target_name,
                    "size_kb": round(total_bytes_len / 1024, 2),
                    "file_base64": base64.b64encode(target_bytes).decode("utf-8")
                }]
            }

        # Случай 3: Многотомный архив/файл
        total_parts = math.ceil(total_bytes_len / chunk_size_bytes)
        parts_list = []

        for i in range(total_parts):
            start = i * chunk_size_bytes
            end = start + chunk_size_bytes
            part_data = target_bytes[start:end]
            part_filename = f"{target_name}.part{i+1:02d}"

            parts_list.append({
                "part_num": i + 1,
                "total_parts": total_parts,
                "filename": part_filename,
                "size_kb": round(len(part_data) / 1024, 2),
                "file_base64": base64.b64encode(part_data).decode("utf-8")
            })

        return {
            "success": True,
            "is_multipart": True,
            "is_compressed": is_zip,
            "target_name": target_name,
            "original_name": base_name,
            "original_size_mb": round(orig_size / (1024 * 1024), 2),
            "total_parts": total_parts,
            "parts": parts_list
        }

    except PermissionError:
        return {"success": False, "error": "Отказано в доступе для чтения файла"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_uploaded_file(target_path: str, file_b64: str) -> dict:
    """
    Сохраняет полученный по сети файл на жесткий диск целевого ПК.
    """
    try:
        target_path = os.path.abspath(target_path)
        target_dir = os.path.dirname(target_path)

        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        raw_bytes = base64.b64decode(file_b64)

        with open(target_path, "wb") as f:
            f.write(raw_bytes)

        return {
            "success": True,
            "saved_path": target_path,
            "size_kb": round(len(raw_bytes) / 1024, 2)
        }
    except PermissionError:
        return {"success": False, "error": f"Отказано в доступе для записи в {target_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
