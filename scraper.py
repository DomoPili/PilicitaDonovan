"""
Archivo: scraper.py
Descripción: Funciones principales de scraping (correcciones: extracción confiable de bio y captions)
"""

import time
import random
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from config import INSTAGRAM_URLS, SCRAPING_CONFIG
from utils import human_delay, extract_username_from_url, parse_follower_count


def scrape_followers(driver, profile, limit):
    """
    Scrapea los followers de un perfil con manejo mejorado de scroll.
    """
    print(f"\n🔍 Scrapeando followers de @{profile}...")
    driver.get(INSTAGRAM_URLS['profile'].format(username=profile))
    human_delay(3, 5)

    wait = WebDriverWait(driver, SCRAPING_CONFIG['default_timeout'])
    followers = set()

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "header")))
        print("✅ Perfil cargado correctamente")
    except TimeoutException:
        print("❌ No se pudo cargar el perfil. Puede ser privado o no existe.")
        return set()

    # abrir modal de followers
    try:
        followers_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers')]"))
        )
        driver.execute_script("arguments[0].click();", followers_link)
        time.sleep(2)
    except Exception:
        print("❌ No se pudo abrir el modal de followers")
        return set()

    # detectar contenedor con scroll
    modal = None
    try:
        posibles = driver.find_elements(By.XPATH, "//div[@role='dialog']//div[@class]")
        for div in posibles:
            try:
                scroll_height = driver.execute_script("return arguments[0].scrollHeight", div)
                client_height = driver.execute_script("return arguments[0].clientHeight", div)
                if scroll_height > client_height + 100:
                    modal = div
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"⚠️ Error buscando contenedor: {e}")

    if not modal:
        print("❌ No se encontró el contenedor desplazable del modal.")
        return set()

    # scroll + extracción
    last_scroll_position = 0
    no_change_count = 0

    while len(followers) < limit:
        try:
            links = modal.find_elements(By.XPATH, ".//a[contains(@href,'/')]")
            for a in links:
                try:
                    href = a.get_attribute("href")
                    username = extract_username_from_url(href)
                    if username and username not in followers:
                        followers.add(username)
                except Exception:
                    continue

            current_count = len(followers)
            print(f"📢 Followers capturados: {current_count}/{limit}", end="\r")

            if current_count >= limit:
                print(f"\n✅ Límite alcanzado: {limit} followers")
                break

            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", modal)
            time.sleep(random.uniform(SCRAPING_CONFIG['scroll_delay_min'], SCRAPING_CONFIG['scroll_delay_max']))

            new_scroll_position = driver.execute_script("return arguments[0].scrollTop", modal)

            if new_scroll_position == last_scroll_position:
                no_change_count += 1
                print(f"\n⚠️ Sin cambios en scroll ({no_change_count}/{SCRAPING_CONFIG['no_change_max']})")
                if no_change_count >= SCRAPING_CONFIG['no_change_max']:
                    print("🛑 No hay más followers para cargar")
                    break
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollTop + 1000;", modal)
                time.sleep(2)
            else:
                no_change_count = 0
                last_scroll_position = new_scroll_position

        except Exception as e:
            print(f"\n⚠️ Error durante extracción: {e}")
            time.sleep(2)
            continue

    print(f"\n✅ Extracción completada: {len(followers)} followers encontrados")
    return followers


def _extract_from_meta_description(content):
    if not content:
        return None, None
    parts = content.split(' - ', 1)
    if len(parts) == 2:
        left, right = parts
        right = right.split('See Instagram', 1)[0].split('See posts', 1)[0].strip()
        return left.strip(), right.strip()
    return content.strip(), None


def _get_followers_from_spans(driver):
    try:
        spans_with_title = driver.find_elements(By.XPATH, "//span[@title]")
        for span in spans_with_title:
            title = span.get_attribute('title')
            if title and title.replace(',', '').replace('.', '').isdigit():
                parent_text = ''
                try:
                    parent = span.find_element(By.XPATH, "./parent::*")
                    parent_text = parent.text.lower()
                except Exception:
                    parent_text = ''
                if any(word in parent_text for word in ['seguidores', 'followers', 'follower']):
                    return parse_follower_count(title)
    except Exception:
        pass
    return None


def _get_followers_from_meta(driver):
    try:
        meta_element = driver.find_element(By.XPATH, "//meta[@property='og:description']")
        content = meta_element.get_attribute('content')
        left_text, _ = _extract_from_meta_description(content)
        m = re.search(r'([\d,\.KMB]+)\s+[Ff]ollowers?', left_text)
        if m:
            return parse_follower_count(m.group(1))
    except Exception:
        pass
    return None


def _get_followers_from_page_source(driver):
    try:
        page_source = driver.page_source
        patterns = [r'"edge_followed_by":\{"count":(\d+)\}', r'"follower_count":(\d+)']
        for pattern in patterns:
            match = re.search(pattern, page_source)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return None


def get_bio(driver):
    """
    Intenta obtener la biografía del perfil de forma robusta.
    Primero: selector data-testid (recomendado).
    Fallbacks: heurísticas en header y meta og:description.
    """
    try:
        # data-testid es la forma más directa y estable
        bio_element = driver.find_element(By.XPATH, "//div[@data-testid='user-bio']")
        bio_text = bio_element.text.strip()
        if bio_text:
            return bio_text
    except Exception:
        pass

    # fallback: buscar en header divs (texto que no contenga "followers" o "publicaciones")
    try:
        header_divs = driver.find_elements(By.XPATH, "//header//div")
        candidate_texts = []
        for div in header_divs:
            try:
                txt = div.text.strip()
                if txt and len(txt) > 10:
                    candidate_texts.append(txt)
            except Exception:
                continue
        for t in sorted(candidate_texts, key=lambda x: len(x), reverse=True):
            low = t.lower()
            if 'followers' in low or 'seguidores' in low or 'following' in low or 'posts' in low or 'publicaciones' in low:
                continue
            return t.split('\n')[0].strip()
    except Exception:
        pass

    # último recurso: meta og:description
    try:
        meta_element = driver.find_element(By.XPATH, "//meta[@property='og:description']")
        content = meta_element.get_attribute('content')
        _, possible_bio = _extract_from_meta_description(content)
        if possible_bio:
            return possible_bio
    except Exception:
        pass

    return None


def get_recent_captions(driver, max_posts=3):
    """
    Extrae captions de las últimas publicaciones abriendo cada post (modal).
    Devuelve lista con longitud <= max_posts (None para captchas no encontrados).
    """
    captions = []
    try:
        # recolectar enlaces de posts mostrados en la grilla
        post_links = []
        anchors = driver.find_elements(By.XPATH, "//article//a[contains(@href, '/p/')]")
        for a in anchors:
            href = a.get_attribute('href')
            if href and '/p/' in href:
                post_links.append(a)
            if len(post_links) >= max_posts:
                break

        for post_elem in post_links:
            try:
                # abrir modal clickeando el elemento
                driver.execute_script("arguments[0].click();", post_elem)
                # esperar modal
                WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
                human_delay(0.8, 1.5)

                caption = None
                # Método 1: div.C4VMK > span (común)
                try:
                    el = driver.find_element(By.XPATH, "//div[@role='dialog']//div[contains(@class,'C4VMK')]/span")
                    caption = el.text.strip()
                except Exception:
                    pass

                # Método 2: meta og:description del post (fallback)
                if not caption:
                    try:
                        meta = driver.find_element(By.XPATH, "//meta[@property='og:description']")
                        caption_candidate = meta.get_attribute('content')
                        if caption_candidate:
                            caption = caption_candidate.split('•')[0].strip()
                    except Exception:
                        pass

                # Método 3: alt del img
                if not caption:
                    try:
                        img = driver.find_element(By.XPATH, "//div[@role='dialog']//img")
                        alt = img.get_attribute('alt')
                        if alt:
                            caption = alt.strip()
                    except Exception:
                        pass

                if caption:
                    caption = " ".join(caption.splitlines()).strip()
                    if len(caption) > 800:
                        caption = caption[:800] + "..."
                    captions.append(caption)
                else:
                    captions.append(None)

            except Exception:
                captions.append(None)
            finally:
                # cerrar modal (intento robusto)
                try:
                    # primer botón dentro del dialog (suele ser cerrar)
                    close_btn = driver.find_element(By.XPATH, "//div[@role='dialog']//button")
                    driver.execute_script("arguments[0].click();", close_btn)
                except Exception:
                    try:
                        # alternativa: ESC
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    except Exception:
                        pass
                human_delay(0.5, 1.2)
    except Exception:
        pass

    return captions


def get_profile_info(driver, username, posts_to_extract=3):
    """
    Obtiene followers (int|None), bio (str|None) y recent_captions (list)
    """
    try:
        url = INSTAGRAM_URLS['profile'].format(username=username)
        driver.get(url)
        human_delay(2, 4)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "header")))

        follower_count = _get_followers_from_spans(driver)
        if follower_count is None:
            follower_count = _get_followers_from_meta(driver)
        if follower_count is None:
            follower_count = _get_followers_from_page_source(driver)

        bio_text = get_bio(driver)
        recent_captions = []
        if posts_to_extract and posts_to_extract > 0:
            recent_captions = get_recent_captions(driver, max_posts=posts_to_extract)

        return {
            'username': username,
            'followers': follower_count,
            'bio': bio_text,
            'recent_captions': recent_captions
        }

    except TimeoutException:
        print(f"  ❌ @{username}: Timeout")
        return {'username': username, 'followers': None, 'bio': None, 'recent_captions': []}
    except Exception as e:
        print(f"  ❌ @{username}: Error {e}")
        return {'username': username, 'followers': None, 'bio': None, 'recent_captions': []}


def collect_followers_data(driver, usernames_set, max_profiles=None, posts_to_extract=3):
    """
    Recopila followers, bio y captions para una lista de usernames.
    """
    print("\n" + "=" * 60)
    print("📊 RECOPILANDO DATOS DE FOLLOWERS (con bio y captions)")
    print("=" * 60)

    followers_data = []
    usernames_list = list(usernames_set)
    if max_profiles:
        usernames_list = usernames_list[:max_profiles]

    total = len(usernames_list)
    print(f"Total de perfiles a procesar: {total}\n")

    for index, username in enumerate(usernames_list, 1):
        print(f"[{index}/{total}] Procesando @{username}...")
        info = get_profile_info(driver, username, posts_to_extract=posts_to_extract)

        followers_data.append({
            'username': info.get('username'),
            'followers': info.get('followers'),
            'bio': info.get('bio'),
            'recent_captions': info.get('recent_captions') or []
        })

        if index < total:
            human_delay()

    successful = sum(1 for item in followers_data if item['followers'] is not None)
    failed = total - successful

    print("\n" + "=" * 60)
    print(f"✅ Completado: {successful}/{total} perfiles exitosos")
    if failed > 0:
        print(f"⚠️ Fallidos: {failed} perfiles")
    print("=" * 60 + "\n")

    return followers_data
