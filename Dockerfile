FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# نصب ابزارهای پایه سیستم
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# کپی و نصب وابستگی‌ها
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# کپی کد سورس پروژه
COPY src ./src
COPY bot.py ./
COPY irc_bot.py ./
COPY pyproject.toml ./
COPY README.md ./
COPY .env.example ./

# دایرکتوری ذخیره سازی حالت‌ها
RUN mkdir -p .state

ENV LOG_LEVEL="INFO"

CMD ["python", "bot.py"]
