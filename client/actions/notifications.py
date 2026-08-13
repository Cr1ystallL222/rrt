import tkinter as tk
from tkinter import ttk

def show_topmost_modal(title: str, message: str) -> dict:
    """
    Создает графическое модальное окно поверх всех остальных запущенных программ (Topmost).
    Гарантирует, что пользователь не пропустит сервисную инструкцию или оповещение.
    """
    try:
        root = tk.Tk()
        root.title(title if title else "Важное сервисное сообщение")
        
        # Делаем окно поверх всех окон
        root.attributes('-topmost', True)
        root.lift()
        root.focus_force()

        # Настройки геометрии и центрирование
        window_width = 460
        window_height = 240
        
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        x_pos = int((screen_width - window_width) / 2)
        y_pos = int((screen_height - window_height) / 2)
        
        root.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        root.resizable(False, False)
        root.configure(bg="#F3F4F6")

        # Основной контейнер
        frame = tk.Frame(root, bg="#F3F4F6", padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        lbl_title = tk.Label(
            frame,
            text=title if title else "Уведомление от администратора",
            font=("Segoe UI", 12, "bold"),
            fg="#1F2937",
            bg="#F3F4F6",
            wraplength=420,
            justify=tk.LEFT
        )
        lbl_title.pack(anchor="w", pady=(0, 10))

        # Текст сообщения
        lbl_msg = tk.Label(
            frame,
            text=message,
            font=("Segoe UI", 10),
            fg="#374151",
            bg="#F3F4F6",
            wraplength=420,
            justify=tk.LEFT
        )
        lbl_msg.pack(anchor="w", fill=tk.BOTH, expand=True)

        # Кнопка подтверждения прочтения
        btn_close = tk.Button(
            frame,
            text="Понятно / Закрыть",
            font=("Segoe UI", 10, "bold"),
            bg="#2563EB",
            fg="white",
            activebackground="#1D4ED8",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor="hand2",
            command=root.destroy
        )
        btn_close.pack(anchor="e", pady=(10, 0))

        # Запуск модального цикла окна
        root.mainloop()
        return {"success": True, "message": "Окно успешно отображено и закрыто пользователем"}
    except Exception as e:
        return {"success": False, "error": str(e)}
