import time
import requests
import os
import sys

# CONFIGURACIÓN
ZAP_PROXY_API = "http://localhost:8081"
TARGET_URL = os.getenv("DAST_TARGET_URL")
CONTEXT_FILE_REL = os.getenv("CONTEXT_FILE_PATH", "security/context.xml")
CONTEXT_PATH_DOCKER = f"/zap/security/{CONTEXT_FILE_REL}"

print(f"--- FASE ATAQUE (Post-Selenium) ---")

try:
    # 1. Cargar Contexto (Por seguridad, aseguramos que esté cargado)
    print(" [1] Asegurando contexto...")
    requests.get(f"{ZAP_PROXY_API}/JSON/context/action/importContext/", params={'contextFile': CONTEXT_PATH_DOCKER})
    
    # 2. Verificar cuántas URLs capturó Selenium
    sites_resp = requests.get(f"{ZAP_PROXY_API}/JSON/core/view/sites/")
    sites = sites_resp.json()
    total_sites = len(sites.get('sites', []))
    print(f" [INFO] Nodos descubiertos por Selenium: {total_sites}")
    
    if total_sites <= 1:
        print(" [WARN] Selenium no encontró muchas URLs. El ataque puede ser corto.")

    # --- LIMPIEZA DE RUIDO (MICROSOFT) ---
    print("\n--- LIMPIEZA DE NODOS EXTERNOS ---")
    # Borramos explícitamente el árbol de sitios de Microsoft
    sitios_a_borrar = [
        "https://login.microsoftonline.com",
        "https://aadcdn.msauth.net",
        "https://aadcdn.msftauth.net",
        "https://browser.events.data.microsoft.com"
    ]
    
    for sitio in sitios_a_borrar:
        try:
            # La API deleteSiteNode elimina todo el árbol bajo esa URL
            requests.get(f"{ZAP_PROXY_API}/JSON/core/action/deleteSiteNode/", params={'url': sitio, 'method': 'GET'})
        except:
            pass
            
    print(" [INFO] Limpieza completada.")

    # 3. Lanzar Active Scan
    print(f" [2] Lanzando Active Scan sobre lo navegado...")
    
    # Obtenemos Context ID
    r_ctx = requests.get(f"{ZAP_PROXY_API}/JSON/context/view/contextList/")
    try:
        context_name = r_ctx.json()['contextList'][0]
    except:
        context_name = "Default Context"

    r_cid = requests.get(f"{ZAP_PROXY_API}/JSON/context/view/context/", params={'contextName': context_name})
    try:
        CONTEXT_ID = r_cid.json()['context']['id']
    except:
        CONTEXT_ID = "1"

    scan_params = {
        'url': TARGET_URL, 
        'recurse': 'true', 
        'inScopeOnly': 'true', 
        'contextId': CONTEXT_ID
    }
    
    r_scan = requests.get(f"{ZAP_PROXY_API}/JSON/ascan/action/scan/", params=scan_params)
    scan_id = r_scan.json().get('scan')
    
    if str(scan_id).isdigit():
        print(f" Ataque iniciado. Scan ID: {scan_id}")
        while True:
            time.sleep(15) 
            status_resp = requests.get(f"{ZAP_PROXY_API}/JSON/ascan/view/status/", params={'scanId': scan_id})
            status = status_resp.json().get('status', '0')
            
            sys.stdout.write(f"\r Progreso: {status}%")
            sys.stdout.flush()
            
            if status == "100":
                print("\n Ataque Terminado.")
                break
    else:
        print(f" [ERROR] No se pudo lanzar el ataque: {r_scan.json()}")
        # Fallback: Intentar sin ContextID si falla
        print(" Reintentando sin Context ID...")
        del scan_params['contextId']
        r_scan_retry = requests.get(f"{ZAP_PROXY_API}/JSON/ascan/action/scan/", params=scan_params)
        retry_id = r_scan_retry.json().get('scan')
        
        if str(retry_id).isdigit():
            print(f" Ataque iniciado (Fallback). Scan ID: {retry_id}")
            # No monitoreamos el fallback para simplificar, o podrías copiar el while loop aquí
        else:
            sys.exit(1)

except Exception as e:
    print(f" [ERROR CRÍTICO] {e}")
    sys.exit(1)