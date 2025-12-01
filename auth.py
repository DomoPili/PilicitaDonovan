"""
Archivo: auth.py
Descripción: Manejo de login y cookies
"""

import json
import time
import random
import configparser
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from config import CONFIG_FILE, COOKIES_FILE, INSTAGRAM_URLS


def load_credentials():
    """Carga credenciales desde config.ini"""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config['Instagram']['username'], config['Instagram']['password']


def save_cookies(driver, filename=None):
    """Guarda las cookies actuales"""
    if filename is None:
        filename = COOKIES_FILE
    
    cookies = driver.get_cookies()
    with open(filename, 'w') as file:
        json.dump(cookies, file, indent=2)
    print(f"✅ Cookies guardadas en {filename}")


def load_cookies(driver, filename=None):
    """Carga cookies guardadas"""
    if filename is None:
        filename = COOKIES_FILE
    
    try:
        driver.get(INSTAGRAM_URLS['home'])
        time.sleep(2)

        with open(filename, "r") as file:
            cookies = json.load(file)

        for cookie in cookies:
            cookie.pop('sameSite', None)
            cookie.pop('priority', None)
            cookie.pop('id', None)

            if 'domain' not in cookie:
                cookie['domain'] = '.instagram.com'

            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"⚠️ No se pudo agregar cookie: {e}")
                continue

        print("✅ Cookies cargadas correctamente")
        driver.refresh()
        time.sleep(3)
        return True

    except FileNotFoundError:
        print("❌ Archivo cookie.json no encontrado")
        return False
    except json.JSONDecodeError:
        print("❌ cookie.json no es JSON válido")
        return False


def login(driver, username, password):
    """Realiza login en Instagram"""
    driver.get(INSTAGRAM_URLS['login'])
    time.sleep(3)
    
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )

        username_field = driver.find_element(By.NAME, "username")
        password_field = driver.find_element(By.NAME, "password")

        # Escribir de forma más humana
        for char in username:
            username_field.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))

        time.sleep(random.uniform(0.5, 1))

        for char in password:
            password_field.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))

        time.sleep(1)
        password_field.send_keys(Keys.RETURN)

        print("✅ Login enviado. Esperando verificación...")
        time.sleep(5)

        input("⏸️  Presiona ENTER después de completar el login y verificación manualmente...")

        save_cookies(driver)
        return True
        
    except TimeoutException:
        print("❌ Timeout esperando elementos de login")
        return False
    except Exception as e:
        print(f"❌ Error en login: {e}")
        return False


def verify_session(driver):
    """Verifica si hay una sesión activa"""
    try:
        driver.find_element(By.XPATH, "//a[contains(@href, '/direct')]")
        print("✅ Sesión válida con cookies")
        return True
    except:
        print("⚠️ Sesión inválida")
        return False

