import os
from typing import Set

# Telegram Bot Token (получить у @BotFather)
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8820444947:AAEG_Ef8Z8IHcTvDhVMKaDzpv6oaivWh5VE")

# Список Telegram ID администраторов с доступом к панели управления
ADMIN_IDS: Set[int] = {
    int(x) for x in os.getenv("ADMIN_IDS", "6621458292").split(",") if x.strip().isdigit()
}

# Настройки WebSocket сервера
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8765"))

# Секретный ключ для авторизации клиентов при подключении к серверу
CLIENT_AUTH_TOKEN: str = os.getenv("CLIENT_AUTH_TOKEN", "SecretAuthToken123!@#")
