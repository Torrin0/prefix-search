#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
from pathlib import Path
from local_search_engine import load_catalog, search

def load_queries(csv_file):
    queries = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                queries.append({
                    'query': row.get('query', ''),
                    'store': row.get('store', ''),
                    'expected_category': row.get('expected_category', ''),
                    'notes': row.get('notes', '')
                })
    except Exception as e:
        print(f"Ошибка при загрузке {csv_file}: {e}")
        return []
    
    return queries


def evaluate_query(query_info, search_result):
    results = search_result.get('results', [])
    expected_category = query_info.get('expected_category', '').lower()
    
    evaluation = {
        'query': query_info['query'],
        'store': query_info['store'],
        'expected_category': expected_category,
        'total_results': len(results),
        'has_relevant': False,
        'precision_at_3': 0.0,
        'category_match_at_3': False,
        'top_3': []
    }
    
    if not results:
        return evaluation
    
    for i, result in enumerate(results[:3], 1):
        category = result.get('category', '').lower()
        evaluation['top_3'].append({
            'rank': i,
            'name': result.get('name', ''),
            'category': category,
            'score': result.get('score', 0)
        })
        
        if expected_category and expected_category in category:
            evaluation['has_relevant'] = True
            evaluation['category_match_at_3'] = True
    
    if expected_category:
        relevant_count = sum(
            1 for r in results[:3]
            if expected_category in r.get('category', '').lower()
        )
        evaluation['precision_at_3'] = relevant_count / min(3, len(results))
    
    return evaluation


def main():
    
    print("="*70)
    print("ЛОКАЛЬНЫЙ ПОИСКОВИК - БЕЗ DOCKER")
    print("="*70)
    
    print("\n1. ЗАГРУЗКА КАТАЛОГА")
    print("-" * 70)
    
    if not load_catalog('data/catalog_products.xml'):
        print("Не удалось загрузить каталог!")
        return
    
    print("\n2. ЗАГРУЗКА ТЕСТОВЫХ ЗАПРОСОВ")
    print("-" * 70)
    
    queries = load_queries('data/prefix_queries.csv')
    if not queries:
        print("Не удалось загрузить запросы!")
        return
    
    print(f"Загружено {len(queries)} запросов")
    
    print("\n3. ОЦЕНКА КАЧЕСТВА ПОИСКА")
    print("-" * 70)
    
    results = []
    
    for i, query_info in enumerate(queries, 1):
        query_text = query_info['query']
        expected_cat = query_info['expected_category']
        
        search_result = search(query_text, top_k=5)
        
        evaluation = evaluate_query(query_info, search_result)
        results.append(evaluation)
        
        status = "OK" if evaluation['has_relevant'] else "FAIL"
        print(f"{status} [{i:2d}] '{query_text}' -> {expected_cat}")
        if evaluation['top_3']:
            print(f"       Топ-1: {evaluation['top_3'][0]['name']}")
            if evaluation['precision_at_3'] > 0:
                print(f"       Precision@3: {evaluation['precision_at_3']:.0%}")
    
    print("\n4. ИТОГОВЫЕ МЕТРИКИ")
    print("=" * 70)
    
    total = len(results)
    with_results = sum(1 for r in results if r['total_results'] > 0)
    with_relevant = sum(1 for r in results if r['has_relevant'])
    category_matches = sum(1 for r in results if r['category_match_at_3'])
    avg_precision = sum(r['precision_at_3'] for r in results) / total if total > 0 else 0
    
    coverage = with_results / total if total > 0 else 0
    relevance_rate = with_relevant / total if total > 0 else 0
    category_match_rate = category_matches / total if total > 0 else 0
    
    print(f"Всего запросов:                {total}")
    print(f"Coverage (есть результаты):    {coverage*100:.1f}%")
    print(f"Relevance Rate (релевантные):  {relevance_rate*100:.1f}%  ", end="")
    
    if relevance_rate >= 0.70:
        print("OK (>=70%)")
    else:
        print(f"FAIL (<70%)")
    
    print(f"Avg Precision@3:               {avg_precision*100:.1f}%")
    print(f"Category Match Rate (топ-3):   {category_match_rate*100:.1f}%")
    print("=" * 70)
    
    print("\n5. СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
    print("-" * 70)
    
    Path('logs').mkdir(exist_ok=True)
    
    csv_file = 'logs/evaluation_results.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'query', 'store', 'expected_category', 'total_results',
            'has_relevant', 'precision_at_3', 'category_match_at_3',
            'top_1_name', 'top_1_category', 'top_1_score'
        ])
        
        for r in results:
            top_1 = r['top_3'][0] if r['top_3'] else {}
            writer.writerow([
                r['query'],
                r['store'],
                r['expected_category'],
                r['total_results'],
                r['has_relevant'],
                r['precision_at_3'],
                r['category_match_at_3'],
                top_1.get('name', ''),
                top_1.get('category', ''),
                top_1.get('score', 0)
            ])
    
    print(f"Результаты сохранены в {csv_file}")
    
    metrics_file = 'logs/evaluation_metrics.json'
    metrics = {
        'total_queries': total,
        'coverage': coverage,
        'relevance_rate': relevance_rate,
        'avg_precision_at_3': avg_precision,
        'category_match_rate': category_match_rate,
        'status': 'PASSED' if relevance_rate >= 0.70 else 'FAILED'
    }
    
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    
    print(f"Метрики сохранены в {metrics_file}")
    
    print("\n" + "="*70)
    print("ОЦЕНКА ЗАВЕРШЕНА!")
    print("="*70)


if __name__ == '__main__':
    main()
