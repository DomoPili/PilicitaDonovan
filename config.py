"""
Archivo: config.py
Descripción: Configuración general del proyecto
"""

import os
from pathlib import Path

# Directorios
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
COOKIES_DIR = BASE_DIR / "cookies"

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
COOKIES_DIR.mkdir(exist_ok=True)

# Archivos
CONFIG_FILE = 'config.ini'
COOKIES_FILE = COOKIES_DIR / 'cookie.json'

# Configuración de Selenium
SELENIUM_CONFIG = {
    'window_size': '1920,1080',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'headless': True,
    'detach': True
}

# Límites y timeouts
SCRAPING_CONFIG = {
    'default_timeout': 15,
    'scroll_delay_min': 1.5,
    'scroll_delay_max': 2.5,
    'max_scroll_attempts': 50,
    'no_change_max': 3,
    'request_delay_min': 2,
    'request_delay_max': 4
}

# URLs de Instagram
INSTAGRAM_URLS = {
    'login': 'https://www.instagram.com/accounts/login/',
    'home': 'https://www.instagram.com/',
    'profile': 'https://www.instagram.com/{username}/',
    'followers': 'https://www.instagram.com/{username}/followers/'
}

