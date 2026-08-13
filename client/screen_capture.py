import io
import base64
from PIL import Image
from client.config import SCREENSHOT_FORMAT, SCREENSHOT_QUALITY

def capture_screen_base64() -> str:
    """
    Создает снимок экрана всех мониторов (или основного) в памяти,
    сжимает его и возвращает base64-строку.
    Использует mss для максимальной скорости или PIL.ImageGrab как запасной вариант.
    """
    buffer = io.BytesIO()

    try:
        import mss
        with mss.mss() as sct:
            # Если есть физические мониторы (len > 1), берем основной экран (индекс 1),
            # чтобы избежать искажения масштаба и лишних черных полей
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)
            # Конвертируем mss ScreenShot в PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception:
        from PIL import ImageGrab
        img = ImageGrab.grab()

    # Сохраняем в буфер памяти
    if SCREENSHOT_FORMAT.upper() == "PNG":
        img.save(buffer, format="PNG", optimize=True)
    else:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buffer, format="JPEG", quality=SCREENSHOT_QUALITY, optimize=True)

    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
