Запуск через Docker

## Быстрый старт (3 команды):

1. Соберите и поднимите контейнеры:


docker-compose up -d --build


2. Загрузите каталог товаров в Elasticsearch:


docker exec prefix_search_api python load_catalog.py


3. Проверьте работу API поискового сервиса:


curl --get --data-urlencode "q=масло" "http://localhost:5001/search"
curl http://localhost:5001/health



## Что будет:

- Elasticsearch и API сервис запущены в контейнерах  
- Каталог загружается в Elasticsearch с помощью `load_catalog.py`  
- API принимает поисковые запросы на порт 5001  
- Оценка качества поиска производится командой:


docker exec prefix_search_api python evaluate.py


Результаты сохраняются в папке `logs/`



## Структура файлов:


prefix-search/
├── utils.py
├── Dockerfile
├── docker-compose.yml
├── load_catalog.py
├── search_service.py
├── evaluate.py
├── data/
│   ├── catalog_products.xml
│   └── prefix_queries.csv
└── logs/
    ├── evaluation_results.csv
    └── evaluation_metrics.json


---

## Примеры запроса к API:

curl --get --data-urlencode "q=масло" "http://localhost:5001/search"

Для получения статуса сервиса:

curl http://localhost:5001/health
