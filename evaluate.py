#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import json
import requests

SEARCH_API = os.getenv('SEARCH_API', 'http://localhost:5000/search')
QUERIES_FILE = '/app/data/prefix_queries.csv'
OUTPUT_CSV = '/app/logs/evaluation_results.csv'
OUTPUT_JSON = '/app/logs/evaluation_metrics.json'

def run_search(query, top_k=5):
    try:
        response = requests.get(SEARCH_API, params={'q': query, 'top_k': top_k}, timeout=10)
        return response.json()
    except Exception as e:
        return {'error': str(e), 'results': []}

def main():
    queries = []
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append({
                'query': row.get('query', ''),
                'store': row.get('store', ''),
                'expected_category': row.get('expected_category', '').lower()
            })
    results = []
    for i, qinfo in enumerate(queries, 1):
        query = qinfo['query']
        expected_category = qinfo['expected_category']
        output = run_search(query)
        search_results = output.get('results', [])
        top_3 = search_results[:3]
        precision_at_3 = 0.0
        category_match = False
        if expected_category and top_3:
            matches = [r for r in top_3 if expected_category in r.get('category', '').lower()]
            if matches:
                category_match = True
                precision_at_3 = len(matches) / len(top_3)
        results.append({
            'query': query,
            'expected_category': expected_category,
            'n_results': len(search_results),
            'top1': top_3[0]['name'] if top_3 else '',
            'precision_at_3': precision_at_3,
            'category_match': category_match,
        })
        print(f"[{i:2d}] '{query}' --> {precision_at_3:.2f}, {category_match}")

    total = len(results)
    with_match = sum(1 for r in results if r['category_match'])
    avg_prec = sum(r['precision_at_3'] for r in results) / total if total else 0

    metrics = {
        'total_queries': total,
        'category_match_count': with_match,
        'avg_precision_at_3': avg_prec,
        'status': 'PASSED' if avg_prec >= 0.7 else 'FAILED'
    }

    os.makedirs('/app/logs', exist_ok=True)
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print('\nMETRICS:', metrics)

if __name__ == '__main__':
    main()
