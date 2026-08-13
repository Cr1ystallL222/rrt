@echo off
chcp 65001 > nul
echo ===================================================
echo Сборка клиента Remote Support в независимый .EXE
echo ===================================================

:: 1. Установка PyInstaller и зависимостей, если еще не установлены
pip install pyinstaller mss Pillow psutil websockets

:: 2. Сборка с PyInstaller
:: Флаги:
:: --onefile         : сборка всего приложения в единый .exe
:: --noconsole       : запуск без окна консоли (GUI / фоновый режим) [можно убрать для отладки]
:: --name "SupportAgent" : имя выходного исполняемого файла
:: --clean           : очистка кэша перед сборкой
:: --add-data        : если требуются доп. файлы или иконки (--icon=app.ico)
pyinstaller --onefile --noconsole --name "RemoteSupportAgent" --clean client/client.py

echo ===================================================
echo Сборка завершена!
echo Исполняемый файл находится в: dist\RemoteSupportAgent.exe
echo ===================================================
pause
