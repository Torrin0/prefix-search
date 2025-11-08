#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

TRANSLIT_MAP = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
    'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
    'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
    'б': ',', 'ю': '.', ' ': ' '
}

REVERSE_MAP = {v: k for k, v in TRANSLIT_MAP.items()}

CYRILLIC_CHARS = set('йцукенгшщзхъфывапролджэячсмитьбюЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ')


def has_cyrillic(text):
    for char in text:
        if char in CYRILLIC_CHARS:
            return True
    return False


def has_latin(text):
    for char in text.lower():
        if 'a' <= char <= 'z':
            return True
    return False


def convert_layout(text, to_latin=True):
    if to_latin:
        result = ''
        for char in text.lower():
            result += TRANSLIT_MAP.get(char, char)
        return result
    else:
        result = ''
        for char in text.lower():
            result += REVERSE_MAP.get(char, char)
        return result


def extract_numeric_attributes(query):
    attributes = {}

    volume_match = re.search(r'(\d+(?:\.\d+)?)\s*л', query, re.IGNORECASE)
    if volume_match:
        attributes['volume'] = float(volume_match.group(1))
        attributes['volume_unit'] = 'л'

    weight_match = re.search(r'(\d+(?:\.\d+)?)\s*(кг|г|kg|g)', query, re.IGNORECASE)
    if weight_match:
        attributes['weight'] = float(weight_match.group(1))
        attributes['weight_unit'] = weight_match.group(2).lower()

    return attributes


def normalize_query(query):
    query = query.strip().lower()

    result = {
        'original': query,
        'normalized': query,
        'latin_variant': None,
        'cyrillic_variant': None,
        'attributes': extract_numeric_attributes(query)
    }

    if has_cyrillic(query):
        result['latin_variant'] = convert_layout(query, to_latin=True)

    if has_latin(query):
        result['cyrillic_variant'] = convert_layout(query, to_latin=False)

    return result


def clean_query_for_search(query):
    cleaned = re.sub(r'\d+(?:\.\d+)?\s*(?:л|кг|г|kg|g|ml|мл)', '', query, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned
