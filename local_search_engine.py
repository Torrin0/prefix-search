#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
from typing import List, Dict
from utils import normalize_query, clean_query_for_search, extract_numeric_attributes

class LocalSearchEngine:
    
    def __init__(self):
        self.products = []
        self.index = {}
    
    def load_products(self, xml_file):
        import xml.etree.ElementTree as ET
        
        if not os.path.exists(xml_file):
            print(f"Ошибка: {xml_file} не найден")
            return False
        
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        for product in root.findall('.//product'):
            item = {
                'id': product.find('id').text if product.find('id') is not None else '',
                'name': product.find('name').text if product.find('name') is not None else '',
                'category': product.find('category').text if product.find('category') is not None else '',
                'brand': product.find('brand').text if product.find('brand') is not None else '',
                'weight': product.find('weight').text if product.find('weight') is not None else '',
                'package_size': product.find('package_size').text if product.find('package_size') is not None else '',
                'keywords': product.find('keywords').text if product.find('keywords') is not None else '',
                'description': product.find('description').text if product.find('description') is not None else '',
                'price': float(product.find('price').text) if product.find('price') is not None and product.find('price').text else 0.0,
                'image_url': product.find('image_url').text if product.find('image_url') is not None else ''
            }
            self.products.append(item)
        
        self._build_index()
        print(f"Загружено {len(self.products)} товаров")
        return True
    
    def _build_index(self):
        self.index = {}
        
        for product in self.products:
            for field in ['name', 'category', 'brand', 'keywords']:
                text = product.get(field, '').lower()
                if not text:
                    continue
                
                for i in range(1, min(len(text) + 1, 16)):
                    prefix = text[:i]
                    if prefix not in self.index:
                        self.index[prefix] = []
                    if product['id'] not in self.index[prefix]:
                        self.index[prefix].append(product['id'])
    
    def search(self, query: str, top_k: int = 10) -> Dict:
        
        normalized = normalize_query(query)
        clean_text = clean_query_for_search(normalized['normalized'])
        
        print(f"\n[ПОИСК] '{query}' -> '{clean_text}'")
        if normalized['latin_variant']:
            print(f"  Латиница: {normalized['latin_variant']}")
        if normalized['cyrillic_variant']:
            print(f"  Кириллица: {normalized['cyrillic_variant']}")
        
        query_variants = [clean_text]
        if normalized['latin_variant']:
            query_variants.append(clean_query_for_search(normalized['latin_variant']))
        if normalized['cyrillic_variant']:
            query_variants.append(clean_query_for_search(normalized['cyrillic_variant']))
        
        query_variants = list(set(v for v in query_variants if v))
        
        matched_ids = set()
        scores = {}
        
        for variant in query_variants:
            variant_lower = variant.lower()
            
            for prefix_key, product_ids in self.index.items():
                if prefix_key.startswith(variant_lower[:min(len(variant_lower), len(prefix_key))]):
                    for pid in product_ids:
                        matched_ids.add(pid)
                        
                        product = self._get_product_by_id(pid)
                        score = self._calculate_score(variant_lower, product)
                        
                        if pid not in scores:
                            scores[pid] = 0
                        scores[pid] = max(scores[pid], score)
        
        sorted_results = sorted(
            [(pid, scores[pid]) for pid in matched_ids],
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        results = []
        for pid, score in sorted_results:
            product = self._get_product_by_id(pid)
            results.append({
                'id': product['id'],
                'name': product['name'],
                'category': product['category'],
                'brand': product['brand'],
                'weight': product['weight'],
                'package_size': product['package_size'],
                'price': product['price'],
                'score': score
            })
        
        if results:
            max_score = results[0]['score']
            threshold = max_score * 0.3
            filtered_results = [r for r in results if r['score'] >= threshold]
        else:
            filtered_results = []
        
        return {
            'query': {
                'original': query,
                'normalized': clean_text,
                'variants': query_variants,
                'attributes': normalized['attributes']
            },
            'total': len(filtered_results),
            'results': filtered_results
        }
    
    def _get_product_by_id(self, product_id: str) -> Dict:
        for product in self.products:
            if product['id'] == product_id:
                return product
        return {}
    
    def _calculate_score(self, query: str, product: Dict) -> float:
        score = 0.0
        query_lower = query.lower()
        
        weights = {
            'name': 3.0,
            'brand': 2.5,
            'category': 2.0,
            'keywords': 1.5
        }
        
        for field, weight in weights.items():
            text = product.get(field, '').lower()
            if query_lower in text:
                score += weight * 10
            elif text.startswith(query_lower):
                score += weight * 5
            elif query_lower in text:
                score += weight * 2
        
        return score


engine = LocalSearchEngine()


def load_catalog(xml_file):
    return engine.load_products(xml_file)


def search(query: str, top_k: int = 10) -> Dict:
    return engine.search(query, top_k)


if __name__ == '__main__':
    xml_file = 'data/catalog_products.xml'
    
    if load_catalog(xml_file):
        test_queries = ['ма', 'масло', 'xfq', 'prosecco', 'чай']
        
        for q in test_queries:
            result = search(q, top_k=3)
            print(f"\nРезультаты для '{q}':")
            for r in result['results']:
                print(f"  - {r['name']} ({r['category']}) - score: {r['score']:.2f}")
