# Локальный запуск (без Docker)

## Быстрый старт (3 команды):

# 1. Убедитесь, что у вас есть Python 3.7+
python3 --version

# 2. Запустите оценку
python3 run_local_search.py

# 3. Проверьте результаты
cat logs/evaluation_metrics.json

## Что будет:

✓ Локальный поисковик на чистом Python
✓ Поддержка префиксов (edge n-grams)
✓ Коррекция раскладки ЙЦУКЕН ↔ QWERTY
✓ Числовые атрибуты (10л, 5kg)
✓ Ранжирование с бустами
✓ Метрики качества

## Результаты:

- logs/evaluation_results.csv - результаты по каждому запросу
- logs/evaluation_metrics.json - итоговые метрики

## Структура файлов:

prefix-search/
├── utils.py                    # Транслитерация, нормализация
├── local_search_engine.py      # Локальный поисковик
├── run_local_search.py         # Скрипт оценки
├── README.md                   # Документация
├── LOCAL_SETUP.md              # Эта инструкция
├── data/
│   ├── catalog_products.xml    # Каталог товаров
│   └── prefix_queries.csv      # Тестовые запросы
└── logs/                       # Результаты
    ├── evaluation_results.csv
    └── evaluation_metrics.json

## Примеры использования:

### Поиск "ма" (префикс):

from local_search_engine import load_catalog, search

load_catalog('data/catalog_products.xml')
result = search('ма', top_k=3)

# Результат:
# Масло сливочное
# Молоко коровье


### Поиск с ошибкой раскладки "xfq" (чай):

result = search('xfq')  # Автоматически конвертирует в "чай"


### Поиск с атрибутами "масло 10л":

result = search('масло 10л')
# Найдет масло подсолнечное 10л с правильной категорией

Все файлы готовы! Просто запустите:

python3 run_local_search.py
