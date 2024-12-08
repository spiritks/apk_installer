# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y adb ssh
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Указываем рабочую директорию
WORKDIR /app

# Команда для запуска скрипта
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false"]
