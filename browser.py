"""
Archivo: browser.py
Descripción: Inicialización y configuración del driver
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from config import SELENIUM_CONFIG


def init_browser(headless=None, detach=None):
    """Inicializa el navegador Chrome con configuración anti-detección"""
    if headless is None:
        headless = SELENIUM_CONFIG['headless']
    if detach is None:
        detach = SELENIUM_CONFIG['detach']
    
    options = webdriver.ChromeOptions()
    options.add_argument(f"--window-size={SELENIUM_CONFIG['window_size']}")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument(f"user-agent={SELENIUM_CONFIG['user_agent']}")
    
    if headless:
        options.add_argument("--headless=new")
    
    if detach:
        options.add_experimental_option("detach", True)
    
    driver = webdriver.Chrome(options=options)

    # Anti-detección
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        '''
    })
    
    return driver

