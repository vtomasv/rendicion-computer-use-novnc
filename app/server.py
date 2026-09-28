"""API local de la demo y servidor de la interfaz compilada."""
from __future__ import annotations

import os
import re
import smtplib
import subprocess
import sys
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

from app import core

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024 + 4096
FRONTEND = core.ROOT / "frontend" / "dist"


def failure(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        return failure(error.description, error.code)
    app.logger.exception("Error de API")
    return failure("Ocurrió un error interno; consulte los registros", 500)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "mode": "demo-local", "auto_approve_max_clp": core.MAX_AMOUNT,
                    "smtp_configured": bool(os.environ.get("SMTP_HOST", "mailpit"))})


@app.get("/api/claims")
def claims():
    return jsonify(core.list_claims())


@app.post("/api/claims")
def create():
    upload = request.files.get("receipt")
    if not upload:
        return failure("Seleccione una boleta")
    try:
        item = core.create_claim(upload, request.form.get("employee", ""), request.form.get("category", ""))
    except ValueError as exc:
        return failure(str(exc))
    except (subprocess.SubprocessError, OSError) as exc:
        app.logger.warning("No se pudo leer el archivo: %s", exc)
        return failure("El archivo no se pudo leer con OCR; compruebe su integridad", 422)
    return jsonify(item), 201


@app.get("/api/claims/<claim_id>")
def detail(claim_id):
    item = core.get_claim(claim_id)
    return jsonify({**item, "events": core.list_events(claim_id)}) if item else failure("Rendición no encontrada", 404)


@app.post("/api/claims/<claim_id>/decision")
def decide(claim_id):
    item = core.get_claim(claim_id)
    if not item:
        return failure("Rendición no encontrada", 404)
    choice = (request.get_json(silent=True) or {}).get("decision")
    if choice not in ("aprobar", "rechazar"):
        return failure("La decisión debe ser aprobar o rechazar")
    if choice == "aprobar":
        try:
            date.fromisoformat(item["receipt_date"])
        except ValueError:
            return failure("No se puede aprobar una fecha ilegible: vuelva a subir una boleta clara", 409)
        if not item["merchant"] or not item["receipt_number"] or item["amount"] <= 0:
            return failure("No se puede aprobar sin proveedor, folio y monto positivo: vuelva a subir una boleta clara", 409)
    target = "listo" if choice == "aprobar" else "rechazado"
    if not core.transition(claim_id, ("pendiente_aprobacion",), target):
        return failure("Solo puede decidir una excepción pendiente", 409)
    core.event(claim_id, "Decisión humana", f"{choice.capitalize()} por revisor de la demo. Motivo original: {item['reason']}")
    return jsonify(core.get_claim(claim_id))


@app.post("/api/claims/<claim_id>/automate")
def automate(claim_id):
    item = core.get_claim(claim_id)
    if not item:
        return failure("Rendición no encontrada", 404)
    if not core.transition(claim_id, ("listo", "excel_listo"), "ejecutando", error=""):
        return failure("La rendición no está lista o ya se está procesando", 409)
    log_path = core.DATA / "runs" / f"{claim_id}.log"
    try:
        with log_path.open("a", encoding="utf-8") as log:
            subprocess.Popen([sys.executable, "-m", "app.agent", claim_id], cwd=core.ROOT,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                             env={**os.environ, "PYTHONUNBUFFERED": "1"})
    except OSError as exc:
        core.transition(claim_id, ("ejecutando",), "listo" if item["state"] == "listo" else "excel_listo", error=str(exc))
        return failure(f"No se pudo iniciar el agente: {exc}", 500)
    core.event(claim_id, "Agente", "Iniciado: observar pantalla → escribir en Calc → enviar desde la interfaz")
    return jsonify({"started": True}), 202


@app.post("/api/claims/<claim_id>/send")
def send_email(claim_id):
    """La interfaz del escritorio invoca el envío. En modo demo solo acepta .local."""
    item = core.get_claim(claim_id)
    if not item:
        return failure("Rendición no encontrada", 404)
    body = request.get_json(silent=True) or {}
    to = str(body.get("to", "")).strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", to) or len(to) > 200:
        return failure("Dirección de correo inválida")
    if not os.environ.get("ALLOW_EXTERNAL_EMAIL") == "1" and not to.lower().endswith(".local"):
        return failure("Modo demo: solo destinatarios .local; configure ALLOW_EXTERNAL_EMAIL=1 para SMTP externo")
    if core.book_row(claim_id) is None:
        return failure("La fila en Excel debe verificarse antes del correo", 409)
    if not core.transition(claim_id, ("ejecutando", "excel_listo"), "enviando_correo", email_to=to):
        return failure("Correo ya enviado o proceso no disponible", 409)
    message = EmailMessage()
    message["From"] = os.environ.get("SMTP_FROM", "rendiciones@demo.local")
    message["To"] = to
    message["Subject"] = str(body.get("subject", f"Rendición {item['receipt_number']} — {item['employee']}"))[:180].replace("\n", " ")
    message.set_content(str(body.get("body", f"Se adjunta rendición {claim_id} por {item['amount']:,} CLP.\nDemo: no es una orden de pago."))[:3000])
    for path, mime, label in ((core.BOOK, ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"), "rendiciones.xlsx"),
                              (core.DATA / "uploads" / item["filename"], ("application", "octet-stream"), item["original_name"])):
        message.add_attachment(path.read_bytes(), maintype=mime[0], subtype=mime[1], filename=label)
    try:
        host = os.environ.get("SMTP_HOST", "127.0.0.1")
        port = int(os.environ.get("SMTP_PORT", "1025"))
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if os.environ.get("SMTP_STARTTLS") == "1":
                smtp.starttls()
            if os.environ.get("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except Exception as exc:
        core.transition(claim_id, ("enviando_correo",), "excel_listo", error=f"SMTP: {exc}")
        core.event(claim_id, "Correo", f"Error SMTP; se permite reintento: {exc}")
        return failure(f"No se pudo enviar el correo: {exc}", 502)
    core.transition(claim_id, ("enviando_correo",), "correo_enviado", error="")
    core.event(claim_id, "Correo", f"Enviado a {to} vía {host}:{port} con XLSX y boleta adjuntos")
    return jsonify({"sent": True, "to": to})


@app.get("/api/claims/<claim_id>/screenshot/<path:name>")
def screenshot(claim_id, name):
    if not core.get_claim(claim_id) or not re.fullmatch(r"\d{2}-[a-z0-9-]+\.png", name):
        return failure("Captura no encontrada", 404)
    return send_from_directory(core.DATA / "runs" / claim_id, name)


@app.get("/api/claims/<claim_id>/receipt")
def receipt(claim_id):
    item = core.get_claim(claim_id)
    if not item:
        return failure("Boleta no encontrada", 404)
    return send_file(core.DATA / "uploads" / item["filename"], as_attachment=True, download_name=item["original_name"])


@app.get("/api/workbook")
def workbook():
    return send_file(core.BOOK, as_attachment=True, download_name="rendiciones.xlsx")


@app.get("/api/diagrams/<name>")
def diagram(name):
    if name not in ("manual", "automatizado"):
        return failure("Diagrama no encontrado", 404)
    return send_file(core.ROOT / "bpmn" / f"{name}.bpmn", mimetype="application/xml")


@app.get("/")
@app.get("/<path:page>")
def frontend(page=""):
    if page and (FRONTEND / page).is_file():
        return send_from_directory(FRONTEND, page)
    if (FRONTEND / "index.html").exists():
        return send_from_directory(FRONTEND, "index.html")
    return failure("Interfaz no compilada: cd frontend && npm install && npm run build", 503)


if __name__ == "__main__":
    core.init()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), threaded=True)
