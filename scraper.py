"""
Archivo: scraper.py
Descripción: Funciones principales de scraping (correcciones: extracción confiable de bio y captions)
MODIFICACIONES RECIENTES:
- Agregadas funciones para extraer 'following' (seguidos) del perfil
- Agregada función para extraer 'name' (nombre completo) del perfil
- Actualizado get_profile_info para incluir name y following
- Actualizado collect_followers_data para manejar los nuevos campos
- Corregido error stale element reference en scrape_followers
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


# =====================================================================
# FUNCIONES AUXILIARES PARA EXTRACCIÓN DE DATOS
# =====================================================================

def _extract_from_meta_description(content):
    """Extrae información de la meta description"""
    if not content:
        return None, None
    parts = content.split(' - ', 1)
    if len(parts) == 2:
        left, right = parts
        right = right.split('See Instagram', 1)[0].split('See posts', 1)[0].strip()
        return left.strip(), right.strip()
    return content.strip(), None


def _get_followers_from_spans(driver):
    """Intenta obtener el número de followers desde los elementos <span>"""
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
    """Intenta obtener el número de followers desde las meta tags"""
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
    """Intenta obtener el número de followers desde el código fuente de la página"""
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


def _get_following_from_spans(driver):
    """
    [FUNCIÓN NUEVA - CORREGIDA] Intenta obtener el número de seguidos desde los elementos <span>
    Busca patrones como "33 seguidos" o "33 following"
    """
    try:
        # DEBUG: Ver qué texto tiene el header (puedes comentar esto después)
        try:
            header_text = driver.find_element(By.TAG_NAME, "header").text
            print(f"    DEBUG - Header texto: {header_text[:200]}")  # Primeros 200 caracteres
        except:
            pass
        
        # Buscar todos los spans que contengan texto
        spans = driver.find_elements(By.XPATH, "//header//span")
        for span in spans:
            text = span.text.strip().lower()
            # Buscar patrones como "33 seguidos" o "131 following"
            if 'seguidos' in text or 'following' in text or 'siguiendo' in text:
                # Extraer el número que aparece antes de la palabra
                # Usar \b para límites de palabra (evita conflicto con "seguidores")
                match = re.search(r'(\d+(?:[.,]\d+)*)\s*(?:seguidos|following|siguiendo)\b', text)
                if match:
                    num_str = match.group(1).replace(',', '').replace('.', '')
                    print(f"    ✓ Following encontrado en span: {num_str}")
                    return int(num_str)
        
        # Método alternativo: buscar directamente en todo el texto del header
        # Este método es más robusto para Instagram
        try:
            all_text = driver.find_element(By.TAG_NAME, "header").text.lower()
            
            # Buscar "número seguidos" (para español)
            match = re.search(r'(\d+(?:[.,]\d+)*)\s+seguidos\b', all_text)
            if match:
                num_str = match.group(1).replace(',', '').replace('.', '')
                print(f"    ✓ Following encontrado en header (es): {num_str}")
                return int(num_str)
            
            # Buscar "número following" (para inglés)
            match = re.search(r'(\d+(?:[.,]\d+)*)\s+following\b', all_text)
            if match:
                num_str = match.group(1).replace(',', '').replace('.', '')
                print(f"    ✓ Following encontrado en header (en): {num_str}")
                return int(num_str)
        except Exception:
            pass
        
        # Intentar con el span interno que tiene la clase específica
        number_spans = driver.find_elements(By.XPATH, 
            "//header//span[contains(@class, 'x5n08af')]//span[contains(@class, 'html-span')]")
        
        for i, span in enumerate(number_spans):
            try:
                # Obtener el número
                num_text = span.text.strip()
                if num_text and num_text.replace(',', '').replace('.', '').isdigit():
                    # Verificar el contexto (siguiente span o padre)
                    # CORREGIDO: usar "seguidos" en plural
                    parent = span.find_element(By.XPATH, 
                        "./ancestor::span[contains(text(), 'seguidos') or contains(text(), 'following')]")
                    if parent:
                        print(f"    ✓ Following encontrado en clase específica: {num_text}")
                        return parse_follower_count(num_text)
            except Exception:
                continue
                
    except Exception as e:
        print(f"    _get_following_from_spans error: {e}")
    return None


def _get_following_from_meta(driver):
    """[FUNCIÓN NUEVA] Intenta obtener el número de seguidos desde las meta tags"""
    try:
        meta_element = driver.find_element(By.XPATH, "//meta[@property='og:description']")
        content = meta_element.get_attribute('content')
        # Buscar patrón como "123 Following"
        m = re.search(r'([\d,\.KMB]+)\s+[Ff]ollowing', content)
        if m:
            return parse_follower_count(m.group(1))
    except Exception:
        pass
    return None


def _get_following_from_page_source(driver):
    """
    [FUNCIÓN NUEVA - MEJORADA] Intenta obtener el número de seguidos desde el código fuente
    """
    try:
        page_source = driver.page_source
        # Patrones más completos
        patterns = [
            r'"edge_follow":\s*\{\s*"count":\s*(\d+)',
            r'"following_count":\s*(\d+)',
            r'"edge_owner_to_timeline_media".*?"edge_follow":\s*\{\s*"count":\s*(\d+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, page_source)
            if match:
                return int(match.group(1))
    except Exception as e:
        print(f"    _get_following_from_page_source error: {e}")
    return None


def _get_full_name(driver):
    """
    [FUNCIÓN NUEVA - CORREGIDA] Intenta obtener el nombre completo del perfil
    Evita capturar el username
    """
    # Método 1: Buscar en section del header (nombre real suele estar en un span o h2)
    try:
        # El nombre completo suele estar en header > section
        header_sections = driver.find_elements(By.XPATH, "//header//section")
        for section in header_sections:
            # Buscar h1 o h2 que NO contenga @ (para evitar username)
            names = section.find_elements(By.XPATH, ".//h1 | .//h2")
            for name_elem in names:
                text = name_elem.text.strip()
                # Si tiene caracteres especiales Unicode o no empieza con @, es el nombre
                if text and '@' not in text and text != text.lower():
                    return text
                # Si contiene caracteres especiales (como 𝙇𝙞𝙥𝙕𝙯)
                if text and any(ord(c) > 127 for c in text):
                    return text
    except Exception:
        pass
    
    # Método 2: Desde meta og:title
    try:
        meta = driver.find_element(By.XPATH, "//meta[@property='og:title']")
        content = meta.get_attribute('content')
        # Formato: "Name (@username) • Instagram"
        match = re.match(r'^(.+?)\s*\(@', content)
        if match:
            name = match.group(1).strip()
            # Verificar que no sea solo el username
            if name and not name.startswith('@'):
                return name
    except Exception:
        pass
    
    # Método 3: JSON embebido en page source
    try:
        page_source = driver.page_source
        match = re.search(r'"full_name":"([^"]+)"', page_source)
        if match:
            name = match.group(1).strip()
            # Verificar que no sea vacío o igual al username
            if name and len(name) > 0:
                return name
    except Exception:
        pass
    
    # Método 4: Buscar spans con dir="auto" que contengan el nombre
    try:
        spans = driver.find_elements(By.XPATH, "//header//span[@dir='auto']")
        for span in spans:
            text = span.text.strip()
            # El nombre real suele tener más de 2 caracteres y no ser números puros
            if text and len(text) > 2 and not text.isdigit() and '@' not in text:
                # Evitar que capture textos como "followers", "posts", etc.
                if not any(word in text.lower() for word in ['follower', 'post', 'seguidor', 'publicacion']):
                    return text
    except Exception:
        pass
    
    return None


# =====================================================================
# FUNCIONES PRINCIPALES DE SCRAPING
# =====================================================================

def scrape_followers(driver, profile, limit):
    """
    Scrapea los followers de un perfil con manejo mejorado de scroll.
    [CORREGIDO] Maneja stale element reference
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
    consecutive_errors = 0
    max_consecutive_errors = 3

    while len(followers) < limit:
        try:
            # Re-localizar elementos en cada iteración para evitar stale reference
            links = driver.find_elements(By.XPATH, "//div[@role='dialog']//a[contains(@href,'/')]")
            
            for a in links:
                try:
                    # Extraer href inmediatamente antes de que el DOM cambie
                    href = a.get_attribute("href")
                    if href:
                        username = extract_username_from_url(href)
                        if username and username not in followers:
                            followers.add(username)
                except Exception:
                    # Ignorar elementos individuales que fallan
                    continue

            current_count = len(followers)
            print(f"📢 Followers capturados: {current_count}/{limit}", end="\r")

            if current_count >= limit:
                print(f"\n✅ Límite alcanzado: {limit} followers")
                break

            # Re-localizar modal antes de hacer scroll
            try:
                modal = driver.find_element(By.XPATH, "//div[@role='dialog']//div[@class and @style]")
            except:
                # Si no podemos re-localizar el modal, intentar continuar con el anterior
                pass

            # Scroll
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", modal)
            time.sleep(random.uniform(SCRAPING_CONFIG['scroll_delay_min'], SCRAPING_CONFIG['scroll_delay_max']))

            # Verificar posición de scroll
            try:
                new_scroll_position = driver.execute_script("return arguments[0].scrollTop", modal)
            except:
                # Si falla, intentar re-localizar modal
                try:
                    modal = driver.find_element(By.XPATH, "//div[@role='dialog']//div[@class and @style]")
                    new_scroll_position = driver.execute_script("return arguments[0].scrollTop", modal)
                except:
                    print("\n⚠️ No se pudo verificar posición de scroll")
                    break

            if new_scroll_position == last_scroll_position:
                no_change_count += 1
                print(f"\n⚠️ Sin cambios en scroll ({no_change_count}/{SCRAPING_CONFIG['no_change_max']})")
                if no_change_count >= SCRAPING_CONFIG['no_change_max']:
                    print("🛑 No hay más followers para cargar")
                    break
                # Scroll adicional
                try:
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollTop + 1000;", modal)
                except:
                    pass
                time.sleep(2)
            else:
                no_change_count = 0
                consecutive_errors = 0  # Reset error counter on success
                last_scroll_position = new_scroll_position

        except Exception as e:
            consecutive_errors += 1
            print(f"\n⚠️ Error durante extracción ({consecutive_errors}/{max_consecutive_errors}): {str(e)[:100]}")
            
            if consecutive_errors >= max_consecutive_errors:
                print("❌ Demasiados errores consecutivos. Deteniendo extracción.")
                break
            
            # Intentar recuperación
            time.sleep(2)
            try:
                # Re-localizar modal
                modal = driver.find_element(By.XPATH, "//div[@role='dialog']//div[@class and @style]")
            except:
                print("❌ No se pudo recuperar el modal")
                break
            
            continue

    print(f"\n✅ Extracción completada: {len(followers)} followers encontrados")
    return followers


def get_bio(driver):
    """
    [MODIFICADO] Intenta obtener la biografía del perfil de forma robusta.
    Evita capturar el conteo de "seguidos"
    """
    try:
        # data-testid es la forma más directa y estable
        bio_element = driver.find_element(By.XPATH, "//div[@data-testid='user-bio']")
        bio_text = bio_element.text.strip()
        if bio_text:
            # Limpiar si capturó "X seguidos" por error
            bio_text = re.sub(r'\d+\s+seguidos?', '', bio_text).strip()
            bio_text = re.sub(r'\d+\s+following', '', bio_text, flags=re.IGNORECASE).strip()
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
                if txt and len(txt) > 5:
                    candidate_texts.append(txt)
            except Exception:
                continue
        
        for t in sorted(candidate_texts, key=lambda x: len(x), reverse=True):
            low = t.lower()
            # Filtrar textos que no son bio
            if any(word in low for word in ['followers', 'seguidores', 'following', 'posts', 
                                             'publicaciones', 'seguidos', 'siguiendo']):
                continue
            # Limpiar y retornar
            clean_bio = t.split('\n')[0].strip()
            if clean_bio and len(clean_bio) > 3:
                return clean_bio
    except Exception:
        pass

    # último recurso: meta og:description
    try:
        meta_element = driver.find_element(By.XPATH, "//meta[@property='og:description']")
        content = meta_element.get_attribute('content')
        _, possible_bio = _extract_from_meta_description(content)
        if possible_bio:
            # Limpiar patrones de seguidos
            possible_bio = re.sub(r'\d+\s+seguidos?', '', possible_bio).strip()
            possible_bio = re.sub(r'\d+\s+following', '', possible_bio, flags=re.IGNORECASE).strip()
            if possible_bio and len(possible_bio) > 3:
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
    [MODIFICADO] Obtiene followers, following, name, bio y recent_captions
    
    Retorna:
        dict con keys: username, name, followers, following, bio, recent_captions
    """
    try:
        url = INSTAGRAM_URLS['profile'].format(username=username)
        driver.get(url)
        human_delay(2, 4)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "header")))

        # Obtener followers
        follower_count = _get_followers_from_spans(driver)
        if follower_count is None:
            follower_count = _get_followers_from_meta(driver)
        if follower_count is None:
            follower_count = _get_followers_from_page_source(driver)

        # [NUEVO] Obtener following (seguidos)
        following_count = _get_following_from_spans(driver)
        if following_count is None:
            following_count = _get_following_from_meta(driver)
        if following_count is None:
            following_count = _get_following_from_page_source(driver)

        # [NUEVO] Obtener nombre completo
        full_name = _get_full_name(driver)

        # Obtener biografía
        bio_text = get_bio(driver)
        
        # Obtener posts recientes
        recent_captions = []
        if posts_to_extract and posts_to_extract > 0:
            recent_captions = get_recent_captions(driver, max_posts=posts_to_extract)

        return {
            'username': username,
            'name': full_name,              # [NUEVO]
            'followers': follower_count,
            'following': following_count,    # [NUEVO]
            'bio': bio_text,
            'recent_captions': recent_captions
        }

    except TimeoutException:
        print(f"  ❌ @{username}: Timeout")
        return {
            'username': username, 
            'name': None,
            'followers': None, 
            'following': None,
            'bio': None, 
            'recent_captions': []
        }
    except Exception as e:
        print(f"  ❌ @{username}: Error {e}")
        return {
            'username': username,
            'name': None,
            'followers': None,
            'following': None,
            'bio': None,
            'recent_captions': []
        }


def collect_followers_data(driver, usernames_set, max_profiles=None, posts_to_extract=3):
    """
     Recopila followers, following, name, bio y captions para una lista de usernames.
    """
    print("\n" + "=" * 60)
    print("📊 RECOPILANDO DATOS DE FOLLOWERS (completo)")
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
            'name': info.get('name'),                    # [NUEVO]
            'followers': info.get('followers'),
            'following': info.get('following'),          # [NUEVO]
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