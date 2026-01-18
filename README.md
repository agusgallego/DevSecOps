# 🛡️ DevSecOps Templates

Repositorio centralizado de plantillas YAML y scripts de automatización para integrar seguridad en pipelines de **Azure DevOps**.

## 🚀 Propósito
Estandarizar los controles de seguridad en la organización, resolviendo la complejidad de **autenticar escaneos DAST contra Microsoft Entra ID** y centralizando las mejores prácticas de herramientas como OWASP ZAP, SonarCloud y Trivy. Donde ampliarmos la variedad de análisis a demanda, siempre de forma modular.

---

## 📂 Estructura del Repositorio

### 1. CI - Análisis Estático (Static Analysis)
Validaciones que deben ejecutarse en la fase de *Build*.

| Archivo | Herramienta | Descripción |
| :--- | :--- | :--- |
| `CI/sast.yml` | **SonarCloud** | Análisis de calidad de código y detección de vulnerabilidades lógicas (SAST). |
| `CI/sca.yml` | **Trivy** | Escaneo de sistema de archivos (`fs`) para detectar CVEs en dependencias y librerías. |
| `CI/secrets.yml` | **Gitleaks** | Prevención de fuga de credenciales, API Keys y secretos en el historial de Git. |
| `CI/container-security.yml` | **Hadolint** & **Trivy** | Linter de mejores prácticas para `Dockerfile` y escaneo de infraestructura como código (IaC). |

### 2. CD - Análisis Dinámico (DAST)
Orquestación de ataques controlados en tiempo de ejecución.

| Script/Archivo | Herramienta | Función Técnica |
| :--- | :--- | :--- |
| `genericAuthEntra.py` | **Selenium** | **Bypass de Login:** Simula un usuario real en Microsoft Entra ID, obtiene cookies de sesión e inyecta el contexto autenticado en ZAP. |
| `lanzarAtaque.py` | **Python (Reqs)** | **Ataque Dirigido:** Limpia nodos externos (ruido de Microsoft/Google) y ejecuta el *Active Scan* de ZAP sobre el `TARGET_URL`. |
| `generarReporteDevops.py` | **Python (XML)** | **Reportabilidad:** Filtra alertas fuera de dominio y transforma los hallazgos a **JUnit XML** para visualización nativa en Azure DevOps. |
| `zapScanTemplate.yml` | **Docker** | Levanta el contenedor `zaproxy/zap-stable`, gestiona limpieza de RAM y coordina la ejecución de los scripts anteriores. |

---
##  variables de grupos SAST

| cliProjectKey > acacoop-backoffice.git |
| cliProjectName > app-backoffice.git |
| connection > SonarQube-Connection |
| organization > acacoop-1 |

---

## 🛠️ Implementación

Para consumir estos templates en tu pipeline (`azure-pipelines.yml`), define el recurso y referencia la plantilla deseada:

```yaml
resources:
  repositories:
    - repository: templates
      type: git
      name: 'DevSecOps-Templates/Templates'

stages:
# Ejemplo: DAST con Autenticación
- stage: SecurityScan
  jobs:
  - job: DAST
    pool: 'Agente-Con-Docker'
    steps:
      - template: CD/zapScanTemplate.yml@templates
        parameters:
          appName: 'MiAplicacion'
          targetUrl: '[https://mi-app-test.dominio.com](https://mi-app-test.dominio.com)'
          zapPort: 8081
