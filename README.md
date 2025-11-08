# Префиксный поиск для грузового каталога

## Описание решения

Реализация поискового движка с поддержкой префиксных запросов для каталога ~1000 товаров.
Решение использует Elasticsearch с edge n-gram анализатором и поддерживает:

- ✓ Префиксный поиск (от 1 символа)
- ✓ Коррекция раскладки (ЙЦУКЕН ↔ QWERTY)
- ✓ Обработка числовых атрибутов (10л, 5kg)
- ✓ Ранжирование с бустами по category/brand
- ✓ Фильтрация нерелевантных результатов
- ✓ Метрики качества (Precision@3, Coverage)

## Быстрый старт

### Требования

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM минимум

### Запуск (3 команды)


# 1. Клонировать репозиторий
git clone <repo-url>
cd prefix-search

# 2. Запустить инфраструктуру
docker-compose up -d

# 3. Загрузить каталог
docker exec prefix_search_api python load_catalog.py


Через 30-60 секунд поиск доступен по адресу: http://localhost:5000

### Проверка работы


# Тест поиска
curl "http://localhost:5000/search?q=масло"

# Health check
curl http://localhost:5000/health


## Архитектура

### Компоненты


Данные XML → load_catalog.py → Elasticsearch (порт 9200)
                                      ↓
                    search_service.py (Flask API, порт 5000)
                              ↓
                    utils.py (транслитерация)


## Логика ранжирования

### 1. Нормализация запроса

- Извлечение числовых атрибутов (10л, 5kg)
- Генерация вариантов раскладки (йцукен ↔ qwerty)
- Очистка текста для поиска

### 2. Коррекция раскладки

Автоматическая конвертация ЙЦУКЕН ↔ QWERTY:

| Запрос (ошибка) | Коррекция | Результат |
|-----------------|-----------|-----------|
| "xfq"           | → "чай"   | Найдет чай |
| "vfckj"         | → "масло" | Найдет масло |
| "гкщыуссщ"      | → "prosecco" | Найдет вино |

### 3. Match Bool Prefix

Для каждого варианта запроса создается multi_match с бустами:
- name: boost 3.0
- brand: boost 2.5
- category: boost 2.0
- keywords: boost 1.5

### 4. Фильтрация мусора

Отбрасываем результаты с score < 30% от max_score

## Метрики качества

### Запуск оценки


docker exec prefix_search_api python evaluate.py


### Результаты


ИТОГОВЫЕ МЕТРИКИ
============================================================
Всего запросов:               30
Coverage (есть результаты):   96.7%
Relevance Rate (релевантные): 73.3%  ✓ Целевой KPI ≥70%
Avg Precision@3:              68.5%
Category Match Rate (топ-3):  70.0%
Avg Score:                    12.45
============================================================


## API Reference

### GET /search

Выполняет префиксный поиск.

**Параметры:**
- q (string, required) - поисковый запрос
- top_k (int, optional) - количество результатов (по умолчанию 10)

**Пример:**


curl "http://localhost:5000/search?q=масло%20сливочное&top_k=5"


### GET /health

Проверка статуса сервиса.

curl http://localhost:5000/health


## Что бы я сделал в проде

### 1. Мониторинг и алерты

- Query latency (p50, p95, p99)
- Search success rate
- Elasticsearch cluster health
- API error rate

### 2. A/B тестирование

- Разные веса бустов
- Эксперименты с min_gram / max_gram
- Сравнение edge_ngram vs completion suggester

### 3. Векторный поиск (Hybrid)

- Использовать семантический поиск (BERT embeddings)
- Комбинировать lexical + semantic scoring
- Переранжирование топ-100 с ML-моделью

### 4. Масштабирование

- Несколько нод Elasticsearch (минимум 3)
- Redis для кэширования
- Kubernetes для API
- Горизонтальное масштабирование

### 5. Персонализация

- История поисков пользователя
- Буст по популярности товаров
- Региональные предпочтения

## Команды управления


# Помощь
make help

# Запуск всего
make all

# Отдельные команды
make build       # Собрать образы
make up          # Запустить инфраструктуру
make down        # Остановить
make load        # Загрузить каталог
make evaluate    # Оценка качества
make test        # Тестовые запросы
make logs        # Показать логи
make clean       # Очистить volumes


# Структура проекта

prefix-search/
├── docker-compose.yml          # Оркестрация контейнеров
├── Dockerfile                  # Образ для API
├── requirements.txt            # Python зависимости
├── README.md                   # Этот файл
├── Makefile                    # Команды
├── load_catalog.py             # Загрузка XML
├── search_service.py           # Flask API
├── evaluate.py                 # Оценка качества
├── utils.py                    # Утилиты
├── data/
│   ├── catalog_products.xml    # Каталог товаров
│   └── prefix_queries.csv      # Тестовые запросы
└── logs/
    ├── search.log
    ├── evaluation_results.csv
    └── evaluation_results_metrics.json

Время реализации MVP:** ~3 часа
Итоговая релевантность:** 73.3% (✓ >= 70%)