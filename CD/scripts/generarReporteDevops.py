import requests
import xml.etree.ElementTree as ET
import sys
import os
import traceback

# --- CONFIGURACIÓN ---
# Obtenemos la URL del Proxy y el Target del entorno
ZAP_PROXY_API = os.environ.get("ZAP_PROXY_ADDRESS", "localhost:8081")
if not ZAP_PROXY_API.startswith("http"):
    ZAP_PROXY_API = f"http://{ZAP_PROXY_API}"

# Definimos el dominio clave para filtrar el ruido.
# Si la URL de la alerta NO contiene esto, la ignoramos.
DOMINIO_OBJETIVO = "acacoop.com.ar" 

# Ruta Absoluta para el reporte (Evita error "No matches found")
BASE_DIR = os.getcwd()
ARCHIVO_SALIDA = os.path.join(BASE_DIR, "TEST-ZAP-Report.xml")

print(f"--- GENERANDO REPORTE XML PARA AZURE DEVOPS ---")
print(f"API ZAP: {ZAP_PROXY_API}")
print(f"Filtro de Dominio: {DOMINIO_OBJETIVO}")
print(f"Archivo de Salida: {ARCHIVO_SALIDA}")

# --- FUNCIÓN DE SEGURIDAD ---
def generar_xml_error(mensaje_error):
    """
    Genera un XML válido aunque falle el script, para que el Pipeline
    no oculte el error y lo muestre en el Dashboard de Tests.
    """
    root = ET.Element('testsuites')
    ts = ET.SubElement(root, 'testsuite', name="ZAP Report Error", tests="1", failures="1")
    tc = ET.SubElement(ts, 'testcase', name="Fallo en Generacion de Reporte", classname="DevSecOps.Script")
    fail = ET.SubElement(tc, 'failure', message="El script de Python falló")
    fail.text = mensaje_error
    
    tree = ET.ElementTree(root)
    with open(ARCHIVO_SALIDA, "wb") as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)
    print(f" [WARN] Se generó un XML de error para notificar al dashboard.")

# --- LÓGICA PRINCIPAL ---
try:
    print(" [1] Descargando alertas de la API de ZAP...")
    try:
        r = requests.get(f"{ZAP_PROXY_API}/JSON/core/view/alerts/", timeout=30)
        data = r.json()
    except Exception as e:
        raise Exception(f"No se pudo conectar a ZAP. ¿Contenedor caído? Error: {e}")

    alerts = data.get('alerts', [])
    print(f" [2] Alertas totales recibidas (Brutas): {len(alerts)}")

    # Estructura JUnit XML
    testsuites = ET.Element('testsuites')
    # Creamos un testsuite temporal que luego llenaremos
    testsuite = ET.SubElement(testsuites, 'testsuite', name="OWASP ZAP Security Scan")

    alertas_procesadas = 0
    alertas_filtradas = 0

    for alert in alerts:
        risk = alert.get('risk', 'Info')
        name = alert.get('alert', 'Unknown')
        url = alert.get('url', 'Unknown')
        desc = alert.get('description', '')[:800] # Limitamos largo para no romper el XML
        solution = alert.get('solution', '')[:800]

        # --- FILTRO ANTI-RUIDO (CRÍTICO) ---
        # Si la URL es de Microsoft, Google, o Auth, la saltamos.
        if DOMINIO_OBJETIVO not in url:
            # print(f" [SKIP] Ignorando alerta externa: {url}")
            alertas_filtradas += 1
            continue
        # -----------------------------------

        alertas_procesadas += 1
        
        # Nombre del Test Case: [Riesgo] Nombre de la vulnerabilidad
        testcase_name = f"[{risk}] {name}"
        testcase = ET.SubElement(testsuite, 'testcase', name=testcase_name, classname=url)
        
        # Lógica de Semáforo:
        # High/Medium = Falla el test (Rojo/Naranja)
        # Low/Info = Pasa el test con logs (Verde/Gris)
        if risk in ["High", "Medium"]:
            failure = ET.SubElement(testcase, 'failure', message=f"Vulnerabilidad {risk} detectada")
            failure.text = f"URL: {url}\n\nDESCRIPCIÓN:\n{desc}\n\nSOLUCIÓN:\n{solution}"
        else:
            system_out = ET.SubElement(testcase, 'system-out')
            system_out.text = f"Riesgo: {risk}\nURL: {url}\n{desc}"

    # Actualizamos el contador real de tests en el XML
    testsuite.set('tests', str(alertas_procesadas))
    
    # Si no hubo alertas reales (o se filtraron todas), agregamos un caso dummy de éxito
    if alertas_procesadas == 0:
        print(" [INFO] No se encontraron vulnerabilidades en el dominio objetivo.")
        tc = ET.SubElement(testsuite, 'testcase', name="Escaneo Limpio", classname="ZAP.Scan")
        sys_out = ET.SubElement(tc, 'system-out')
        sys_out.text = f"Se escanearon sitios, pero no se hallaron riesgos en {DOMINIO_OBJETIVO}. (Se filtraron {alertas_filtradas} alertas externas)."

    # Guardar archivo
    tree = ET.ElementTree(testsuites)
    with open(ARCHIVO_SALIDA, "wb") as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)
    
    print(f" [OK] Reporte generado exitosamente.")
    print(f"      Ubicación: {ARCHIVO_SALIDA}")
    print(f"      Alertas Reportadas: {alertas_procesadas}")
    print(f"      Alertas Ignoradas (Microsoft/Otros): {alertas_filtradas}")

except Exception as e:
    print(f" [ERROR CRÍTICO] {str(e)}")
    traceback.print_exc()
    generar_xml_error(str(e))
    # No salimos con error code 1 para permitir que la tarea 'PublishTestResults' suba el XML de error.