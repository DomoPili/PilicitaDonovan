"""
Archivo: utils.py
Descripción: Utilidades generales
"""

import time
import random
import re
from config import SCRAPING_CONFIG


def human_delay(min_sec=None, max_sec=None):
    """Delay aleatorio para simular comportamiento humano"""
    if min_sec is None:
        min_sec = SCRAPING_CONFIG['request_delay_min']
    if max_sec is None:
        max_sec = SCRAPING_CONFIG['request_delay_max']
    
    time.sleep(random.uniform(min_sec, max_sec))


def parse_follower_count(text):
    """
    Convierte texto de followers a número entero
    Maneja formatos: 1234, 1.2K, 1.2M, 1,234
    """
    try:
        text = text.replace(',', '').replace(' ', '').upper()

        if 'K' in text:
            number = float(text.replace('K', ''))
            return int(number * 1000)
        elif 'M' in text:
            number = float(text.replace('M', ''))
            return int(number * 1000000)
        else:
            return int(float(text))
    except (ValueError, AttributeError):
        return None


def extract_username_from_url(url):
    """Extrae el username de una URL de Instagram"""
    if not url or "instagram.com" not in url:
        return None
    
    parts = url.rstrip('/').split('/')
    username = parts[-1] if parts[-1] else parts[-2]
    
    # Filtrar URLs que no son perfiles
    invalid_paths = ['explore', 'direct', 'p', 'reel', 'reels', 'tv', 'stories', 
                     'accounts', 'about', 'legal', 'help']
    
    if username in invalid_paths:
        return None
    
    return username
