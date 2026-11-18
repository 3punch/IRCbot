.PHONY: help install run test lint format docker-up docker-down

help:
	@echo "دستورات موجود:"
	@echo "  make install     نصب وابستگی‌ها"
	@echo "  make run         اجرای ربات تلگرام"
	@echo "  make test        اجرای تست‌های پروژه"
	@echo "  make lint        بررسی کیفیت کد با ruff"
	@echo "  make format      فرمت‌سازی خودکار کد"
	@echo "  make docker-up   اجرای کانتینرهای داکر (بات + اولاما)"
	@echo "  make docker-down توقف کانتینرهای داکر"

install:
	pip install -r requirements.txt

run:
	python bot.py

test:
	pytest tests/

lint:
	ruff check src tests

format:
	ruff format src tests

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
