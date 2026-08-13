import asyncio
import datetime
import json
import logging
import websockets

from client.config import SERVER_URL, AUTH_TOKEN, HEARTBEAT_INTERVAL
from client.screen_capture import capture_screen_base64
from client.system_info import get_machine_id, get_static_sysinfo, get_dynamic_sysinfo

# Импорт новых модулей действий
from client.actions.diagnostics import (
    get_full_hardware_info,
    get_ram_detailed,
    get_all_disks,
    get_battery_status,
    get_uptime_and_boot
)
from client.actions.network import (
    get_network_interfaces,
    get_active_connections_summary,
    test_ping_latency,
    flush_dns_cache,
    get_external_ip
)
from client.actions.processes import (
    get_top_cpu_processes,
    get_top_ram_processes,
    get_windows_services_status,
    kill_process_by_pid,
    restart_service_by_name
)
from client.actions.maintenance import (
    clean_temp_files,
    send_user_popup,
    lock_workstation,
    system_reboot,
    system_shutdown,
    cancel_system_shutdown
)
from client.actions.webcam import capture_webcam_frame_with_consent
from client.actions.notifications import show_topmost_modal
from client.actions.media_stream import run_video_stream_diagnostic
from client.actions.system_admin import run_cli_diagnostic, generate_full_diagnostic_report, is_running_as_admin
from client.actions.file_manager import list_directory_contents, read_file_for_download, save_uploaded_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger("ClientAgent")


class RemoteSupportClient:
    def __init__(self):
        self.client_id = get_machine_id()
        self.static_info = get_static_sysinfo()
        self.is_running = True

    async def heartbeat_loop(self, ws):
        """Фоновый цикл отправки периодического пульса (keep-alive) на сервер"""
        while self.is_running and not ws.closed:
            try:
                metrics = get_dynamic_sysinfo()
                msg = {
                    "type": "heartbeat",
                    "client_id": self.client_id,
                    "data": metrics
                }
                await ws.send(json.dumps(msg))
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.warning(f"Ошибка отправки heartbeat: {e}")
                break

    async def handle_command(self, ws, command_payload: dict):
        """Обработка команд от администратора"""
        request_id = command_payload.get("request_id")
        action = command_payload.get("action")
        params = command_payload.get("params", {})

        logger.info(f"Получена команда: {action} (request_id: {request_id})")

        response = {
            "type": "response",
            "request_id": request_id,
            "status": "success",
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            # 1. Захват экрана и базовые проверки
            if action == "screenshot":
                image_b64 = await asyncio.to_thread(capture_screen_base64)
                response["data"] = {"image_base64": image_b64}
            elif action == "sysinfo":
                response["data"] = await asyncio.to_thread(get_dynamic_sysinfo)
            elif action == "ping":
                response["data"] = {"pong": True}

            # 2. Диагностика оборудования
            elif action == "hardware_info":
                response["data"] = await asyncio.to_thread(get_full_hardware_info)
            elif action == "ram_detailed":
                response["data"] = await asyncio.to_thread(get_ram_detailed)
            elif action == "disks_all":
                response["data"] = await asyncio.to_thread(get_all_disks)
            elif action == "battery_info":
                response["data"] = await asyncio.to_thread(get_battery_status)
            elif action == "uptime_boot":
                response["data"] = await asyncio.to_thread(get_uptime_and_boot)

            # 3. Сеть и связь
            elif action == "net_interfaces":
                response["data"] = await asyncio.to_thread(get_network_interfaces)
            elif action == "net_connections":
                response["data"] = await asyncio.to_thread(get_active_connections_summary)
            elif action == "ping_latency":
                target = params.get("target", "8.8.8.8")
                response["data"] = await asyncio.to_thread(test_ping_latency, target)
            elif action == "flush_dns":
                response["data"] = await asyncio.to_thread(flush_dns_cache)
            elif action == "external_ip":
                response["data"] = await asyncio.to_thread(get_external_ip)

            # 4. Процессы и службы
            elif action == "top_cpu":
                response["data"] = await asyncio.to_thread(get_top_cpu_processes)
            elif action == "top_ram":
                response["data"] = await asyncio.to_thread(get_top_ram_processes)
            elif action == "services_list":
                response["data"] = await asyncio.to_thread(get_windows_services_status)
            elif action == "kill_proc":
                pid = params.get("pid")
                response["data"] = await asyncio.to_thread(kill_process_by_pid, pid)
            elif action == "restart_svc":
                svc_name = params.get("service_name")
                response["data"] = await asyncio.to_thread(restart_service_by_name, svc_name)

            # 5. Обслуживание и управление питанием
            elif action == "clean_temp":
                response["data"] = await asyncio.to_thread(clean_temp_files)
            elif action == "user_popup":
                msg_text = params.get("message", "Сообщение от системного администратора")
                title = params.get("title", "Техническая поддержка")
                response["data"] = await asyncio.to_thread(send_user_popup, msg_text, title)
            elif action == "lock_workstation":
                response["data"] = await asyncio.to_thread(lock_workstation)
            elif action == "reboot":
                delay = params.get("delay", 15)
                response["data"] = await asyncio.to_thread(system_reboot, delay)
            elif action == "shutdown":
                delay = params.get("delay", 15)
                response["data"] = await asyncio.to_thread(system_shutdown, delay)
            elif action == "cancel_shutdown":
                response["data"] = await asyncio.to_thread(cancel_system_shutdown)

            # 6. Мультимедиа и важные модальные окна
            elif action == "webcam_snap":
                result = await asyncio.to_thread(capture_webcam_frame_with_consent)
                if result.get("success"):
                    response["data"] = result
                else:
                    response["status"] = "error"
                    response["error"] = result.get("error", "Не удалось получить доступ к камере")

            elif action == "custom_modal":
                title = params.get("title", "Важное сервисное сообщение")
                text = params.get("message", "")
                response["data"] = await asyncio.to_thread(show_topmost_modal, title, text)

            elif action == "video_diagnostic":
                device_idx = params.get("device_index", 0)
                result = await asyncio.to_thread(run_video_stream_diagnostic, device_idx)
                if result.get("success"):
                    response["data"] = result
                else:
                    response["status"] = "error"
                    response["error"] = result.get("error", "Сбой видеоустройства")

            # 7. Локальное администрирование и CLI диагностика
            elif action == "cli_cmd":
                cmd_type = params.get("cmd_type", "ipconfig")
                response["data"] = await asyncio.to_thread(run_cli_diagnostic, cmd_type)

            elif action == "export_diag_report":
                buf = await asyncio.to_thread(generate_full_diagnostic_report)
                import base64
                response["data"] = {
                    "report_base64": base64.b64encode(buf.getvalue()).decode('utf-8')
                }

            # 8. Файловый менеджер (скачивание / загрузка / проводник)
            elif action == "fs_list":
                path = params.get("path")
                response["data"] = await asyncio.to_thread(list_directory_contents, path)

            elif action == "fs_download":
                path = params.get("path")
                result = await asyncio.to_thread(read_file_for_download, path)
                if result.get("success"):
                    response["data"] = result
                else:
                    response["status"] = "error"
                    response["error"] = result.get("error", "Сбой чтения файла")

            elif action == "fs_upload":
                target_path = params.get("path")
                file_b64 = params.get("file_b64")
                result = await asyncio.to_thread(save_uploaded_file, target_path, file_b64)
                if result.get("success"):
                    response["data"] = result
                else:
                    response["status"] = "error"
                    response["error"] = result.get("error", "Сбой сохранения файла")

            else:
                response["status"] = "error"
                response["error"] = f"Неизвестное действие: {action}"

        except Exception as e:
            logger.error(f"Ошибка выполнения действия {action}: {e}")
            response["status"] = "error"
            response["error"] = str(e)

        await ws.send(json.dumps(response))

    async def connect_and_listen(self):
        """Основной цикл подключения и обработки сообщений"""
        while self.is_running:
            try:
                logger.info(f"Подключение к серверу {SERVER_URL}...")
                async with websockets.connect(
                    SERVER_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=120 * 1024 * 1024
                ) as ws:
                    # 1. Авторизация
                    auth_message = {
                        "type": "auth",
                        "token": AUTH_TOKEN,
                        "client_id": self.client_id,
                        "client_info": self.static_info
                    }
                    await ws.send(json.dumps(auth_message))

                    auth_ack_raw = await ws.recv()
                    auth_ack = json.loads(auth_ack_raw)

                    if auth_ack.get("status") != "ok":
                        logger.error(f"Ошибка авторизации: {auth_ack.get('message')}")
                        await asyncio.sleep(10)
                        continue

                    logger.info("Успешно авторизован на сервере")

                    # 2. Запуск heartbeat в фоне
                    heartbeat_task = asyncio.create_task(self.heartbeat_loop(ws))

                    try:
                        # 3. Прием команд от сервера
                        async for message_raw in ws:
                            payload = json.loads(message_raw)
                            if payload.get("type") == "command":
                                asyncio.create_task(self.handle_command(ws, payload))
                    finally:
                        heartbeat_task.cancel()

            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                logger.warning(f"Соединение разорвано: {e}. Повтор через 5 секунд...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Непредвиденная ошибка: {e}. Повтор через 10 секунд...")
                await asyncio.sleep(10)


def main():
    client = RemoteSupportClient()
    try:
        asyncio.run(client.connect_and_listen())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Клиент остановлен")


if __name__ == "__main__":
    main()
