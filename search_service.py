#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch
from utils import normalize_query, clean_query_for_search

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/search.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

ES_HOST = os.getenv('ELASTICSEARCH_HOST', 'http://elasticsearch:9200')
INDEX_NAME = 'products'
es = Elasticsearch([ES_HOST], request_timeout=30)

def build_search_query(query_text, top_k=10):
    normalized = normalize_query(query_text)
    clean_text = clean_query_for_search(normalized['normalized'])
    logger.info(f"Поиск: оригинал='{query_text}', очищенный='{clean_text}'")
    query_variants = [clean_text]
    if normalized['latin_variant']:
        query_variants.append(clean_query_for_search(normalized['latin_variant']))
    if normalized['cyrillic_variant']:
        query_variants.append(clean_query_for_search(normalized['cyrillic_variant']))
    query_variants = list(set(v for v in query_variants if v))
    logger.info(f"Варианты запроса: {query_variants}")
    should_queries = []
    for variant in query_variants:
        should_queries.append({
            "match_bool_prefix": {
                "name": {"query": variant, "boost": 3.0}
            }
        })
        should_queries.append({
            "match_bool_prefix": {
                "category": {"query": variant, "boost": 2.0}
            }
        })
        should_queries.append({
            "match_bool_prefix": {
                "brand": {"query": variant, "boost": 2.5}
            }
        })
        should_queries.append({
            "match_bool_prefix": {
                "keywords": {"query": variant, "boost": 1.5}
            }
        })
    es_query = {
        "query": {
            "bool": {
                "should": should_queries,
                "minimum_should_match": 1
            }
        },
        "size": top_k,
        "_source": ["id", "name", "category", "brand", "weight", "package_size", "price"]
    }
    try:
        response = es.search(index=INDEX_NAME, body=es_query)
        results = []
        for hit in response['hits']['hits']:
            result = {
                'id': hit['_source']['id'],
                'name': hit['_source']['name'],
                'category': hit['_source']['category'],
                'brand': hit['_source']['brand'],
                'weight': hit['_source'].get('weight', ''),
                'package_size': hit['_source'].get('package_size', ''),
                'price': hit['_source'].get('price', 0),
                'score': hit['_score']
            }
            results.append(result)
        if results:
            max_score = results[0]['score']
            threshold = max_score * 0.3
            filtered_results = [r for r in results if r['score'] >= threshold]
            logger.info(f"Результатов до фильтрации: {len(results)}, после: {len(filtered_results)}")
            return {
                'query': {
                    'original': query_text,
                    'normalized': clean_text,
                    'variants': query_variants,
                    'attributes': normalized['attributes']
                },
                'total': len(filtered_results),
                'results': filtered_results
            }
        return {
            'query': {
                'original': query_text,
                'normalized': clean_text,
                'variants': query_variants,
                'attributes': normalized['attributes']
            },
            'total': 0,
            'results': []
        }
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return {
            'error': str(e),
            'query': query_text,
            'total': 0,
            'results': []
        }

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        data = request.get_json()
        query = data.get('query', '')
        top_k = data.get('top_k', 10)
    else:
        query = request.args.get('q', '')
        top_k = int(request.args.get('top_k', 10))
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    results = build_search_query(query, top_k)
    return jsonify(results)

@app.route('/health', methods=['GET'])
def health():
    try:
        es.ping()
        return jsonify({'status': 'healthy', 'elasticsearch': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    import time
    for i in range(30):
        try:
            if es.ping():
                logger.info("Подключение к Elasticsearch установлено")
                break
        except:
            logger.info(f"Ожидание Elasticsearch... ({i+1}/30)")
            time.sleep(2)
    app.run(host='0.0.0.0', port=5000, debug=False)
