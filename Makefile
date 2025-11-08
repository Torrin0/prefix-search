# Makefile для управления проектом

.PHONY: help build up down restart logs load evaluate clean test all

help:
	@echo "Доступные команды:"
	@echo "  make build      - Собрать Docker образы"
	@echo "  make up         - Запустить инфраструктуру"
	@echo "  make down       - Остановить инфраструктуру"
	@echo "  make restart    - Перезапустить сервисы"
	@echo "  make logs       - Показать логи"
	@echo "  make load       - Загрузить каталог в Elasticsearch"
	@echo "  make evaluate   - Запустить оценку качества"
	@echo "  make test       - Запустить тестовые запросы"
	@echo "  make clean      - Очистить Docker volumes"
	@echo "  make all        - Полный цикл (сборка + запуск + загрузка + оценка)"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Ожидание запуска Elasticsearch..."
	@sleep 15
	@echo "Инфраструктура запущена!"
	@echo "API: http://localhost:5000"
	@echo "Elasticsearch: http://localhost:9200"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

load:
	@echo "Загрузка каталога..."
	docker exec prefix_search_api python load_catalog.py

evaluate:
	@echo "Запуск оценки качества..."
	docker exec prefix_search_api python evaluate.py

test:
	@echo "Тестовые запросы:"
	@echo ""
	@echo "1. Префикс 'ма':"
	@curl -s "http://localhost:5000/search?q=ма&top_k=3" | python -m json.tool 2>/dev/null || echo "API не доступен"
	@echo ""

clean:
	docker-compose down -v
	@echo "Все volumes удалены"

all: build up
	@sleep 20
	@make load
	@sleep 5
	@make evaluate
