import base64
import tkinter as tk
from tkinter import messagebox

def ask_camera_consent() -> bool:
    """
    Отображает модальное окно с запросом согласия пользователя на доступ к камере.
    Гарантирует соблюдение приватности: без согласия камера не включается.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    result = messagebox.askyesno(
        title="Запрос доступа к оборудованию",
        message="Служба технической поддержки запрашивает разовый доступ к веб-камере для диагностики устройства.\n\nРазрешить включение камеры?",
        icon='question',
        parent=root
    )
    root.destroy()
    return result

def capture_webcam_frame_with_consent() -> dict:
    """
    Запрашивает согласие пользователя и, при подтверждении, делает снимок с веб-камеры.
    Камера инициализируется кратковременно и немедленно освобождается (cap.release()).
    """
    # 1. Проверка согласия пользователя
    has_consent = ask_camera_consent()
    if not has_consent:
        return {
            "success": False,
            "error": "Пользователь отклонил запрос на доступ к веб-камере."
        }

    # 2. Захват кадра через OpenCV
    try:
        import cv2
    except ImportError:
        return {
            "success": False,
            "error": "Библиотека opencv-python (cv2) не установлена на клиенте."
        }

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) # CAP_DSHOW ускоряет открытие камеры на Windows
    if not cap.isOpened():
        # Попытка открыть без DirectShow, если не удалось
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        return {
            "success": False,
            "error": "Веб-камера не обнаружена или уже используется другим приложением."
        }

    try:
        # Пропускаем первые несколько кадров для стабилизации автоэкспозиции и баланса белого
        for _ in range(8):
            cap.read()

        ret, frame = cap.read()
        if not ret or frame is None:
            return {
                "success": False,
                "error": "Не удалось получить изображение с видеосенсора."
            }

        # Кодируем снимок в JPEG в памяти
        success, encoded_img = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not success:
            return {
                "success": False,
                "error": "Ошибка кодирования изображения."
            }

        image_b64 = base64.b64encode(encoded_img.tobytes()).decode('utf-8')
        return {
            "success": True,
            "image_base64": image_b64
        }
    finally:
        # Обязательно освобождаем устройство захвата
        cap.release()
