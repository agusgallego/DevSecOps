import time
import os
import sys
import argparse
import traceback
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from zapv2 import ZAPv2

sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIGURACIÓN DE TRANSFERENCIA A ZAP ---
def transfer_session_to_zap(driver, zap_proxy_addr):
    print(" [SYNC] Transfiriendo cookies a ZAP (para Active Scan posterior)...")
    try:
        selenium_cookies = driver.get_cookies()
        zap = ZAPv2(proxies={'http': f'http://{zap_proxy_addr}', 'https': f'http://{zap_proxy_addr}'})
        
        cookie_string = ""
        for cookie in selenium_cookies:
            cookie_string += f"{cookie['name']}={cookie['value']}; "

        zap.replacer.add_rule(
            description="AuthHeader", enabled="true", matchtype="REQ_HEADER",
            matchregex="false", matchstring="Cookie", replacement=cookie_string
        )
        print(" [SYNC] Cookies inyectadas.")
    except Exception as e:
        print(f" [WARN] No se pudo conectar con ZAP API: {e}")

# --- FUNCIÓN DE CRAWLING (LA CLAVE DEL ÉXITO) ---
def selenium_crawl(driver, base_url):
    print("\n--- INICIANDO CRAWLING CON SELENIUM (SPIDER HUMANO) ---")
    print(" Buscando enlaces internos para alimentar a ZAP...")
    
    visited_links = set()
    links_to_visit = set()
    
    # 1. Obtener enlaces de la Home
    try:
        # Esperamos que cargue el dashboard
        time.sleep(5) 
        elements = driver.find_elements(By.TAG_NAME, "a")
        
        domain = urlparse(base_url).netloc
        print(f" Filtrando enlaces para el dominio: {domain}")

        for elem in elements:
            try:
                href = elem.get_attribute('href')
                if href and domain in href and href not in visited_links:
                    links_to_visit.add(href)
            except:
                continue
    except Exception as e:
        print(f" [WARN] Error obteniendo enlaces iniciales: {e}")

    print(f" Enlaces encontrados en Home: {len(links_to_visit)}")
    
    # 2. Visitar cada enlace encontrado (Limitado a 15 para no tardar horas)
    count = 0
    max_crawl = 20 
    
    for link in list(links_to_visit):
        if count >= max_crawl: 
            break
        
        if link == base_url or "logout" in link or "signout" in link:
            continue

        print(f" [CRAWL {count+1}/{len(links_to_visit)}] Visitando: {link}")
        try:
            driver.get(link)
            time.sleep(3) # Tiempo para que ZAP intercepte y analice JS
            visited_links.add(link)
            count += 1
        except Exception as e:
            print(f" [WARN] Error visitando {link}: {e}")
            
    print(f"--- CRAWLING FINALIZADO. URLs inyectadas en ZAP: {count} ---\n")


def run_login(target_url, user_email, user_pass, proxy_address=None):
    print(f"--- LOGIN + CRAWLING: {target_url} ---")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")
    
    if proxy_address:
        print(f" [PROXY] Conectado a: {proxy_address}")
        chrome_options.add_argument(f'--proxy-server=http://{proxy_address}')

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 40)

    try:
        # --- LOGIN FLOW (Ya sabemos que esto funciona) ---
        driver.get(target_url)
        time.sleep(3)
        
        try:
            # Landing check
            wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Iniciar sesión')]"))).click()
        except: pass

        # Email
        print(" [1] Email...")
        wait.until(EC.element_to_be_clickable((By.NAME, "loginfmt"))).send_keys(user_email)
        driver.find_element(By.ID, "idSIButton9").click()
        
        # Password
        print(" [2] Password...")
        time.sleep(2)
        pass_field = wait.until(EC.element_to_be_clickable((By.NAME, "passwd")))
        pass_field.click()
        driver.execute_script("arguments[0].value = arguments[1];", pass_field, user_pass)
        pass_field.send_keys(" ")
        pass_field.send_keys("\b")
        time.sleep(1)
        driver.execute_script("document.getElementById('idSIButton9').click()")

        # KMSI
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
        except: pass

        # Validacion
        print(" [3] Esperando Dashboard...")
        WebDriverWait(driver, 60).until_not(EC.url_contains("login.microsoft"))
        print(f" [OK] Login Exitoso. URL: {driver.current_url}")

        # --- AQUI ESTA LA MAGIA: CRAWLING MANUAL ---
        if proxy_address:
            # 1. Pasamos cookies para el Active Scan posterior
            transfer_session_to_zap(driver, proxy_address)
            
            # 2. Navegamos nosotros mismos para llenar el árbol de ZAP
            selenium_crawl(driver, target_url)

    except Exception:
        traceback.print_exc()
        driver.save_screenshot("ERROR_LOGIN.png")
        sys.exit(1)
    finally:
        driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("DAST_TARGET_URL"))
    parser.add_argument("--email", default=os.environ.get("DAST_USER_EMAIL"))
    parser.add_argument("--password", default=os.environ.get('DAST_USER_PASS'))
    args = parser.parse_args()
    zap_proxy = os.environ.get("ZAP_PROXY_ADDRESS") 

    run_login(args.url, args.email, args.password, zap_proxy)