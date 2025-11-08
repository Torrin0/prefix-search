#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import xml.etree.ElementTree as ET
from elasticsearch import Elasticsearch, helpers

# Получаем адрес Elasticsearch из переменной окружения, по умолчанию localhost:9200
ES_HOST = os.getenv('ELASTICSEARCH_HOST', 'http://localhost:9200')
INDEX_NAME = 'products'

# Мэппинг индекса с edge n-gram анализатором для префиксного поиска
INDEX_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "prefix_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "prefix_edge_ngram"]
                },
                "search_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase"]
                }
            },
            "filter": {
                "prefix_edge_ngram": {
                    "type": "edge_ngram",
                    "min_gram": 1,
                    "max_gram": 15
                }
            }
        },
        "max_ngram_diff": 14
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "prefix": {"type": "search_as_you_type"}
                }
            },
            "category": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "brand": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "keywords": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer"
            },
            "description": {"type": "text"},
            "weight": {"type": "keyword"},
            "package_size": {"type": "keyword"},
            "price": {"type": "float"},
            "image_url": {"type": "keyword"}
        }
    }
}


def parse_catalog_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    products = []
    for product in root.findall('.//product'):
        item = {}
        item['id'] = product.find('id').text if product.find('id') is not None else ''
        item['name'] = product.find('name').text if product.find('name') is not None else ''
        item['category'] = product.find('category').text if product.find('category') is not None else ''
        item['brand'] = product.find('brand').text if product.find('brand') is not None else ''
        item['weight'] = product.find('weight').text if product.find('weight') is not None else ''
        item['package_size'] = product.find('package_size').text if product.find('package_size') is not None else ''
        item['keywords'] = product.find('keywords').text if product.find('keywords') is not None else ''
        item['description'] = product.find('description').text if product.find('description') is not None else ''
        price_elem = product.find('price')
        item['price'] = float(price_elem.text) if price_elem is not None and price_elem.text else 0.0
        item['image_url'] = product.find('image_url').text if product.find('image_url') is not None else ''
        products.append(item)
    return products


def create_index(es, index_name, mapping):
    if es.indices.exists(index=index_name):
        print(f"Индекс {index_name} уже существует. Удаляем...")
        es.indices.delete(index=index_name)
    print(f"Создаем индекс {index_name}...")
    es.indices.create(index=index_name, body=mapping)
    print("Индекс создан успешно!")


def bulk_index_products(es, index_name, products):
    actions = [
        {
            "_index": index_name,
            "_id": product['id'],
            "_source": product
        }
        for product in products
    ]
    print(f"Загружаем {len(products)} товаров...")
    success, failed = helpers.bulk(es, actions, raise_on_error=False)
    print(f"Загружено: {success}, ошибок: {len(failed)}")
    return success, failed


def main():
    xml_file = '/app/data/catalog_products.xml'
    if not os.path.exists(xml_file):
        print(f"Файл {xml_file} не найден!")
        sys.exit(1)
    print(f"Подключение к Elasticsearch: {ES_HOST}")
    es = Elasticsearch([ES_HOST], request_timeout=30)

    for i in range(30):
        try:
            if es.ping():
                print("Elasticsearch готов!")
                break
        except Exception:
            print(f"Ожидание Elasticsearch... ({i+1}/30)")
            time.sleep(2)
    else:
        print("Не удалось подключиться к Elasticsearch")
        sys.exit(1)
    print(f"Парсинг {xml_file}...")
    products = parse_catalog_xml(xml_file)
    print(f"Найдено товаров: {len(products)}")
    create_index(es, INDEX_NAME, INDEX_MAPPING)
    success, failed = bulk_index_products(es, INDEX_NAME, products)
    es.indices.refresh(index=INDEX_NAME)
    print("\nЗагрузка завершена!")
    print(f"Всего документов в индексе: {es.count(index=INDEX_NAME)['count']}")


if __name__ == '__main__':
    main()
