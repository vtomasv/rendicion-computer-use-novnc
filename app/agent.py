"""Agente GUI determinista; NO usa la política RL del artículo ni APIs para escribir Excel.

Entrada: ID de la rendición. Observación: capturas del DISPLAY. Acción: PyAutoGUI
sobre LibreOffice Calc y Chromium. La lectura del XLSX sirve exclusivamente de aserción
post-acción y de idempotencia; nunca escribe filas desde Python.
"""
from __future__ import annotations

import os
import fcntl
import subprocess
import sys
import time
from pathlib import Path

from app import core

SCREENSHOT_DELAY = float(os.environ.get("GUI_STEP_DELAY", "0.55"))


def active_window() -> str:
    result = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                            capture_output=True, text=True, timeout=5)
    return result.stdout.strip()


def wait_for(title: str, timeout: float = 25) -> None:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if title.lower() in active_window().lower():
            return
        time.sleep(0.4)
    raise RuntimeError(f"La ventana esperada '{title}' no tomó el foco; actual: {active_window()!r}")


def find_window(title: str, timeout: float = 25) -> str:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        result = subprocess.run(["xdotool", "search", "--name", title],
                                capture_output=True, text=True)
        if result.stdout.strip():
            return result.stdout.splitlines()[-1]
        time.sleep(0.4)
    raise RuntimeError(f"No se abrió la ventana '{title}'")


def paste(gui, text: str) -> None:
    subprocess.run(["xclip", "-selection", "clipboard"], input=str(text).encode("utf-8"), check=True, timeout=5)
    gui.hotkey("ctrl", "v")
    time.sleep(0.16)


def safe_excel(value: str) -> str:
    """Evita que el contenido de boletas cree fórmulas al pegarlo en Calc."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def run(claim_id: str) -> None:
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("DISPLAY no definido: inicie Xvfb/noVNC antes de ejecutar")
    os.environ["XDG_SESSION_TYPE"] = "x11"  # PyScreeze usa este indicador para habilitar scrot.
    import pyautogui as gui  # después de verificar DISPLAY

    gui.FAILSAFE = True
    gui.PAUSE = 0.18
    item = core.get_claim(claim_id)
    if not item or item["state"] != "ejecutando":
        raise RuntimeError("Rendición no disponible para ejecución")
    desktop_lock = (core.DATA / "desktop.lock").open("w")
    fcntl.flock(desktop_lock, fcntl.LOCK_EX)  # un único operador en la GUI compartida
    directory = core.DATA / "runs" / claim_id
    directory.mkdir(parents=True, exist_ok=True)
    counter = 0

    def observe(step: str, detail: str) -> None:
        nonlocal counter
        counter += 1
        time.sleep(SCREENSHOT_DELAY)
        name = f"{counter:02d}-{step}.png"
        gui.screenshot().save(directory / name)
        core.event(claim_id, step, detail + f" | Ventana: {active_window()}", name)
        print(f"[{counter:02d}] {step}: {detail}", flush=True)

    observe("escritorio", "Observación inicial del escritorio remoto")
    if core.book_row(claim_id) is None:
        core.event(claim_id, "Plan", "Ruta GUI: LibreOffice Calc; no escritura programática en XLSX")
        stale_lock = core.BOOK.parent / f".~lock.{core.BOOK.name}#"
        if stale_lock.exists():
            if subprocess.run(["pgrep", "-x", "soffice.bin"], capture_output=True).returncode == 0:
                raise RuntimeError("La planilla ya está abierta en otra sesión de LibreOffice")
            stale_lock.unlink()  # documento local de demo: bloqueo obsoleto tras fallo previo
            core.event(claim_id, "Recuperación", "Se retiró bloqueo XLSX obsoleto sin proceso LibreOffice activo")
        wb = core.load_workbook(core.BOOK, read_only=True)
        try:
            next_row = wb.active.max_row + 1
        finally:
            wb.close()
        values = [item["id"], item["employee"], item["merchant"], item["receipt_number"],
                  item["receipt_date"], item["category"], str(item["amount"]),
                  "Autoaprobada" if not item["reason"] else "Aprobada por jefatura",
                  item["original_name"], "Pendiente"]
        profile = f"file:///tmp/rendicion-lo-{os.getpid()}"
        office = subprocess.Popen(["libreoffice", f"-env:UserInstallation={profile}", "--calc", str(core.BOOK)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            calc_window = find_window("LibreOffice Calc", timeout=35)
            # LibreOffice muestra un modal "Tip of the Day" en perfiles nuevos.
            # Detectarlo por ventana X11 evita escribir accidentalmente en el modal.
            time.sleep(1.5)
            found = subprocess.run(["xdotool", "search", "--name", "Tip of the Day"],
                                   capture_output=True, text=True)
            if found.stdout.strip():
                tip_window = found.stdout.splitlines()[-1]
                subprocess.run(["xdotool", "windowactivate", "--sync", tip_window], check=True)
                gui.press("esc")
                time.sleep(0.5)
                core.event(claim_id, "Preparación GUI", "Cerrado el diálogo inaugural de LibreOffice")
            subprocess.run(["xdotool", "windowactivate", "--sync", calc_window], check=True)
            wait_for("LibreOffice Calc", timeout=8)
            gui.press("esc")  # cerrar menú accidental sin depender de atajos de Openbox
            observe("calc-abierto", f"Calc abierto; fila de destino {next_row}")
            gui.hotkey("ctrl", "home")
            if next_row > 1:
                gui.press("down", presses=next_row - 1, interval=0.012)
            observe("fila-destino", f"Celda A{next_row} seleccionada por teclado")
            for n, value in enumerate(values):
                if "LibreOffice Calc" not in active_window():
                    title = active_window()
                    name = f"{counter + 1:02d}-foco-perdido.png"
                    gui.screenshot().save(directory / name)
                    core.event(claim_id, "Foco perdido", f"Columna {n+1}, ventana: {title}", name)
                    raise RuntimeError(f"Se perdió el foco de Calc en columna {n+1}: {title}")
                paste(gui, safe_excel(value))
                if n < len(values) - 1:
                    gui.press("tab")
            observe("calc-escrito", "Los 10 campos fueron escritos en celdas mediante Ctrl+V y Tab")
            gui.hotkey("ctrl", "s")
            time.sleep(2.2)
            title = active_window()
            if "format" in title.lower() or "formato" in title.lower():
                gui.press("enter")
                time.sleep(1.4)
            observe("calc-guardado", "Guardado desde LibreOffice con Ctrl+S")
        finally:
            if "LibreOffice Calc" in active_window():
                gui.hotkey("alt", "f4")
            try:
                office.wait(timeout=8)
            except subprocess.TimeoutExpired:
                office.terminate()
        deadline = time.monotonic() + 15
        while core.book_row(claim_id) is None and time.monotonic() < deadline:
            time.sleep(0.5)
        if core.book_row(claim_id) is None:
            raise RuntimeError("La fila no figura en el XLSX tras el guardado GUI")
        core.event(claim_id, "Verificación", "openpyxl leyó la fila resultante; no se usó para escribir el archivo")
    else:
        core.event(claim_id, "Idempotencia", "Fila existente detectada: se evita duplicar la rendición")

    # El backend envía SMTP; el agente interactúa con el formulario HTML visible en Chromium.
    if not core.transition(claim_id, ("ejecutando",), "excel_listo"):
        raise RuntimeError("Estado inválido después de verificar el Excel")
    url = f"http://127.0.0.1:{os.environ.get('PORT', '8080')}/correo/{claim_id}"
    browser = subprocess.Popen(["chromium", "--no-sandbox", "--disable-dev-shm-usage",
                                "--no-first-run", "--user-data-dir=/tmp/rendicion-chromium",
                                "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for("Chromium", timeout=30)
        time.sleep(2)
        observe("correo-borrador", "Formulario de correo visible en Chromium, con adjuntos identificados")
        # El formulario escucha Ctrl+Enter: acto de envío realizado desde la interfaz gráfica.
        gui.hotkey("ctrl", "enter")
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            current = core.get_claim(claim_id)
            if current["state"] == "correo_enviado":
                observe("correo-enviado", "Correo aceptado por SMTP de pruebas; confirmación visible")
                return
            if current["error"]:
                raise RuntimeError(current["error"])
            time.sleep(0.5)
        raise RuntimeError("No se confirmó el envío tras Ctrl+Enter; revise el formulario y el SMTP")
    finally:
        # Dejamos Chromium abierto para que el usuario vea el estado en noVNC.
        if browser.poll() is not None:
            print(f"Chromium terminó con {browser.returncode}", flush=True)


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        run(code)
    except Exception as exc:
        print(f"FALLO: {exc}", file=sys.stderr, flush=True)
        item = core.get_claim(code)
        if item and item["state"] in ("ejecutando", "excel_listo"):
            # Un reintento verifica primero si la fila ya existe: no duplica Excel.
            core.transition(code, (item["state"],), "excel_listo" if core.book_row(code) else "listo", error=str(exc)[:500])
        core.event(code, "Error", str(exc)[:500]) if item else None
        sys.exit(1)
