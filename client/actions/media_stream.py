import io
import time
import logging
import platform
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Tuple, Optional
import cv2

logger = logging.getLogger("MediaDiagnostic")


def _capture_worker(device_index: int, warmup_frames: int, quality: int) -> Tuple[bool, Optional[str], dict]:
    """
    Внутренний воркер: инициализация видеоустройства, прогрев сенсора, 
    захват тестового кадра, сжатие в RAM и гарантированное освобождение ресурса.
    """
    metrics = {
        "init_time_ms": 0.0,
        "capture_time_ms": 0.0,
        "resolution": "Unknown",
        "payload_kb": 0.0
    }
    
    start_init = time.perf_counter()

    # Оптимизация выбора бэкенда для минимальной задержки
    if platform.system() == "Windows":
        backend = cv2.CAP_DSHOW
    elif platform.system() == "Linux":
        backend = cv2.CAP_V4L2
    else:
        backend = cv2.CAP_ANY

    cap = cv2.VideoCapture(device_index, backend)
    metrics["init_time_ms"] = round((time.perf_counter() - start_init) * 1000, 2)

    try:
        if not cap.isOpened():
            return False, None, {"error": f"Видеоустройство (Index {device_index}) недоступно или занято"}

        start_capture = time.perf_counter()

        # 1. Быстрый пропуск кадров через grab() для автоэкспозиции
        for _ in range(max(1, warmup_frames)):
            if not cap.grab():
                break

        # 2. Извлечение и декодирование тестового кадра
        ret, frame = cap.retrieve()
        if not ret or frame is None:
            return False, None, {"error": "Не удалось декодировать кадр с видеосенсора"}

        metrics["capture_time_ms"] = round((time.perf_counter() - start_capture) * 1000, 2)
        height, width = frame.shape[:2]
        metrics["resolution"] = f"{width}x{height}"

        # 3. Кодирование в JPEG в оперативной памяти (без жесткого диска)
        encode_params = [
            int(cv2.IMWRITE_JPEG_QUALITY), quality,
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1
        ]
        success, buffer = cv2.imencode('.jpg', frame, encode_params)
        if not success:
            return False, None, {"error": "Ошибка сжатия кадра в JPEG"}

        raw_bytes = buffer.tobytes()
        metrics["payload_kb"] = round(len(raw_bytes) / 1024, 2)
        
        # Кодируем в base64 для передачи по WebSocket
        b64_img = base64.b64encode(raw_bytes).decode('utf-8')
        return True, b64_img, metrics

    finally:
        # 4. Мгновенное освобождение дескриптора камеры
        if cap is not None:
            cap.release()


def run_video_stream_diagnostic(device_index: int = 0, warmup_frames: int = 4, quality: int = 85, timeout_sec: float = 4.0) -> dict:
    """
    Неблокирующий запуск аппаратной диагностики видеопотока с таймаутом.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_capture_worker, device_index, warmup_frames, quality)
        try:
            success, b64_img, stats = future.result(timeout=timeout_sec)
            if success:
                return {
                    "success": True,
                    "image_base64": b64_img,
                    "metrics": stats
                }
            else:
                return {
                    "success": False,
                    "error": stats.get("error", "Сбой чтения видеопотока")
                }
        except TimeoutError:
            return {
                "success": False,
                "error": f"Превышен таймаут ({timeout_sec}с) при опросе видеодрайвера"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
