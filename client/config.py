import os

# Адрес WebSocket-сервера (IP вашего VPS)
SERVER_URL: str = os.getenv("SERVER_URL", "ws://163.5.41.97:8765/ws")

# Секретный токен авторизации (должен совпадать с токеном на сервере)
AUTH_TOKEN: str = os.getenv("AUTH_TOKEN", "SecretAuthToken123!@#")

# Интервал отправки heartbeat (пульса) в секундах
HEARTBEAT_INTERVAL: int = 15

# Формат скриншотов (PNG = 100% качество и четкость текста, без артефактов сжатия)
SCREENSHOT_FORMAT: str = "PNG"
SCREENSHOT_QUALITY: int = 95
