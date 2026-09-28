# Plan de pruebas y evidencia

## 1. Pruebas automáticas

Desde la raíz del repositorio con las dependencias del proyecto instaladas:

```bash
python3 -m pytest -q
npm ci --prefix frontend
npm run build --prefix frontend
```

`tests/test_demo.py` cubre: OCR de una boleta autoaprobada, rechazo de duplicados por proveedor/folio, excepción por monto y aprobación humana, prevención de correo previo a la fila verificada, bloqueo de destinatarios externos en modo demo, adjuntos del mensaje SMTP, sintaxis XML y compuertas exclusivas en ambos BPMN, y errores de carga. El test de SMTP usa un doble de prueba; la verificación contra Mailpit se describe en el apartado siguiente.

**Resultado verificado el 28-09-2026:** `7 passed`; Vite compiló; `docker compose config --quiet` pasó; la imagen Docker se construyó y ejecutó como usuario `demo` no privilegiado. Un `docker run` con puertos de laboratorio alternativos completó OCR → Calc → SMTP en **22 segundos**, con una fila XLSX, siete capturas y dos adjuntos Mailpit. La configuración Compose se validó sintácticamente; el runtime Compose completo **no** se levantó en este sandbox, que limita el networking Docker. La ruta E2E de los mismos componentes en contenedor sí fue probada.

## 2. Prueba integral visual (Docker)

1. `docker compose up --build -d` y `docker compose ps` (ambos servicios arriba).
2. `curl http://localhost:8080/api/health` devuelve `ok: true`.
3. Abra http://localhost:6080/vnc.html?autoconnect=true&resize=scale. Debe ver Chromium en el escritorio de 1440 × 900 px.
4. En otra pestaña abra http://localhost:8080, sección **Laboratorio**, cargue una boleta sintética y compruebe los datos OCR.
5. Pulse **Ejecutar computer use**, observe Calc y Chromium en noVNC sin tocar el ratón/teclado, y espere el estado **Correo enviado**.
6. Descargue `rendiciones.xlsx`, busque el ID del expediente en la columna A, verifique importe y proveedor y compruebe que solo hay **una** fila para el ID.
7. Abra http://localhost:8025: verifique asunto, destinatario `demo@ejemplo.local`, texto y **dos adjuntos** (`rendiciones.xlsx` y la boleta).
8. Inspeccione las capturas en **Trazabilidad**. Deben verse escritorio inicial, apertura de Calc, fila destino, celdas escritas, guardado, formulario de correo y confirmación.
9. Intente repetir `POST /api/claims/<ID>/automate` para un caso ya terminado: debe devolver `409` y no enviar otro correo. Vuelva a cargar la misma muestra: se rechaza el folio duplicado.
10. Cargue `samples/boleta-excepcion.png`. Debe quedar en **Revisión humana** y no permitir ejecución antes de la aprobación. Puede aprobar la excepción para probar la segunda ruta o rechazarla y verificar que no se automatiza.

### Verificador E2E automático sobre un volumen nuevo

```bash
python3 scripts/verify_e2e.py
```

Arranca con la boleta sintética autoaprobable, lanza el agente, espera hasta 110 segundos y comprueba una fila única en el XLSX, estado final, capturas y dos adjuntos en Mailpit. Para la ejecución aislada en sandbox se usó: `DEMO_URL=http://127.0.0.1:8090 MAILPIT_URL=http://127.0.0.1:8025 python3 scripts/verify_e2e.py`. En el Compose por defecto no se necesitan variables. **No ejecute dos veces con la misma muestra/volumen**: la detección de folios duplicados bloqueará la segunda carga deliberadamente.

### Verificación programática de un expediente

```bash
# Sustituya ID por el valor mostrado en Laboratorio:
ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
curl -s "http://localhost:8080/api/claims/$ID"
curl -OJ http://localhost:8080/api/workbook
curl -s http://localhost:8025/api/v1/messages
```

El agente **no** usa `openpyxl` para agregar datos: las capturas permiten observar la edición visible en Calc, y la lectura final del XLSX comprueba la persistencia. El correo sale mediante el botón/atajo del formulario en Chromium; la llamada SMTP la hace el servidor de la demo, no la GUI directamente.

## 3. Ejecutar sin Docker (desarrollo nativo)

Solo si ya dispone de Linux con X11/Xvfb y desea depurar el escritorio de manera local:

```bash
sudo apt-get install -y xvfb x11vnc openbox novnc websockify \
  libreoffice-calc chromium tesseract-ocr tesseract-ocr-spa \
  xclip xdotool scrot poppler-utils python3-tk
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
npm ci --prefix frontend && npm run build --prefix frontend
python3 scripts/generate_samples.py
python3 scripts/generate_bpmn.py
```

En terminales separadas:

```bash
# 1: servidor X
export DISPLAY=:99 XDG_SESSION_TYPE=x11
touch "$HOME/.Xauthority"
Xvfb :99 -screen 0 1440x900x24 -ac -nolisten tcp
# 2: gestor de ventanas
DISPLAY=:99 openbox
# 3: VNC solo localhost y su cliente web
DISPLAY=:99 x11vnc -display :99 -localhost -rfbport 5902 -shared -forever -nopw
# 4: adaptar 5902/6082 si se usan otros puertos
/usr/bin/websockify --web /usr/share/novnc 127.0.0.1:6082 localhost:5902
# 5: Mailpit descargado desde https://github.com/axllent/mailpit/releases
mailpit --listen 127.0.0.1:8025 --smtp 127.0.0.1:1025
# 6: aplicación y escritorio
DISPLAY=:99 XDG_SESSION_TYPE=x11 SMTP_HOST=127.0.0.1 python -m app.server
DISPLAY=:99 chromium --no-sandbox --user-data-dir=/tmp/rendicion-chromium http://127.0.0.1:8080
```

En Docker se usan internamente **5900/6080**; este ejemplo nativo usa **5902/6082** para evitar conflictos con VNC existente en el anfitrión. El `compose.yaml` es la forma recomendada de uso: evita instalaciones nativas y mantiene el correo local separado.

## 4. Regenerar capturas del README

Después de procesar una boleta en el entorno nativo anterior (puertos 8080, 6082 y 8025):

```bash
python3 scripts/capture_screenshots.py ID_DEL_EXPEDIENTE
```

Genera `docs/images/01-...png` a `09-...png` con Playwright sobre la **interfaz real**, las capturas registradas por el agente y Mailpit. No son ilustraciones reconstruidas. Para volver a capturar con Docker, ajuste el puerto noVNC del script a 6080 o ejecute la captura en el anfitrión con Chromium/Python instalados.

## 5. Interpretar fallas comunes

| Síntoma | Causa probable | Acción |
| --- | --- | --- |
| `DISPLAY no definido` | Agente fuera del contenedor o Xvfb apagado | Verifique `DISPLAY=:99` y `docker compose ps` |
| `~/.Xauthority` ausente | PyAutoGUI requiere archivo de autoridad | El `docker/start.sh` lo crea; en nativo use `touch ~/.Xauthority` |
| `scrot`/captura falla | Falta scrot o `XDG_SESSION_TYPE=x11` | Instale scrot y exporte la variable; el agente la fija internamente |
| Ventana Calc sin foco | Diálogo de bienvenida, usuario mueve noVNC o otra ventana se superpone | Reinicie la ejecución sin intervenir; el agente cierra la pantalla inicial de consejos |
| `SMTP: connection refused` | Mailpit aún no inició | `docker compose logs mailpit` y vuelva a ejecutar; la fila XLSX no se duplica |
| `Boleta duplicada` | Folio/proveedor ya existe en SQLite | Use una muestra de folio distinto; no borre el volumen salvo decisión expresa |
| `No se confirmó el envío` | Formulario no cargó o API con error | Consulte `docker compose logs desktop`, el expediente y la bandeja Mailpit |

**Criterio de aceptación:** solo declarar éxito E2E cuando los cuatro elementos concuerden: estado `correo_enviado`, una fila XLSX con ID/proveedor/monto correctos, un mensaje en Mailpit con dos adjuntos y capturas del desktop visibles en el expediente.
