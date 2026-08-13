import asyncio
import json
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher

from server.config import BOT_TOKEN, SERVER_HOST, SERVER_PORT, CLIENT_AUTH_TOKEN
from server.session_manager import session_manager
from server.bot_handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("Server")

# Инициализация Bot и Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(router)


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Обработчик входящих WebSocket-соединений от клиентов"""
    ws = web.WebSocketResponse(heartbeat=30.0, max_msg_size=120 * 1024 * 1024)
    await ws.prepare(request)

    client_ip = request.remote or "Unknown"
    logger.info(f"Новая попытка подключения с IP: {client_ip}")

    client_id = None
    authenticated = False

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    payload = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                msg_type = payload.get("type")

                # 1. Этап авторизации и регистрации клиента
                if msg_type == "auth":
                    token = payload.get("token")
                    if token != CLIENT_AUTH_TOKEN:
                        logger.warning(f"Неверный токен авторизации от {client_ip}")
                        await ws.send_str(json.dumps({"type": "auth_result", "status": "error", "message": "Unauthorized"}))
                        await ws.close()
                        break

                    client_id = payload.get("client_id")
                    client_data = payload.get("client_info", {})
                    await session_manager.register(client_id, client_data, ws, client_ip)
                    authenticated = True

                    logger.info(f"Клиент успешно авторизован: {client_id} ({client_data.get('hostname')})")
                    await ws.send_str(json.dumps({"type": "auth_result", "status": "ok"}))

                # 2. Обработка сообщений только от авторизованных клиентов
                elif authenticated and client_id:
                    if msg_type == "heartbeat":
                        session_manager.update_heartbeat(client_id, payload.get("data", {}))
                    elif msg_type == "response":
                        session_manager.handle_client_response(client_id, payload)

            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"Ошибка соединения WS: {ws.exception()}")

    finally:
        if client_id:
            logger.info(f"Клиент {client_id} отключился")
            await session_manager.unregister(client_id)

    return ws


async def start_server():
    # Создание aiohttp приложения
    app = web.Application()
    app.router.add_get("/ws", websocket_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, SERVER_HOST, SERVER_PORT)
    await site.start()
    logger.info(f"WebSocket сервер запущен на ws://{SERVER_HOST}:{SERVER_PORT}/ws")

    # Запуск polling бота Telegram
    logger.info("Запуск Telegram-бота...")
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Сервер остановлен")
