"""Capturas reales, no mockups. Ejecútese tras levantar la demo y procesar una boleta."""
from __future__ import annotations
import shutil
import sys
import json
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'images'
OUT.mkdir(parents=True,exist_ok=True)
CLAIM=sys.argv[1] if len(sys.argv)>1 else None

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
    page.goto('http://127.0.0.1:8080/',wait_until='networkidle')
    page.screenshot(path=str(OUT/'01-vista-general.png'))
    for label,filename in [('Proceso manual','02-bpmn-manual.png'),('Proceso automatizado','03-bpmn-automatizado.png'),('Laboratorio','04-laboratorio.png')]:
        page.locator('.sidebar-link',has_text=label).click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT/filename))
    if CLAIM:
        page.get_by_role('button',name='Ver detalle').first.click()
        page.wait_for_timeout(500)
        page.get_by_text('Cronología auditable').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'08-trazabilidad.png'))
        run=ROOT/'data'/'runs'/CLAIM
        for glob,target in [('*-calc-escrito.png','05-calc-computer-use.png'),('*-correo-borrador.png','06-correo-interfaz.png')]:
            source=next(iter(sorted(run.glob(glob))),None)
            if source: shutil.copy2(source,OUT/target)
    page.goto('http://127.0.0.1:8025/',wait_until='networkidle')
    page.wait_for_timeout(500)
    if CLAIM:
        claim=json.load(urllib.request.urlopen(f'http://127.0.0.1:8080/api/claims/{CLAIM}'))
        page.get_by_text(f"Rendición {claim['receipt_number']}",exact=False).first.click()
        page.wait_for_timeout(500)
    page.screenshot(path=str(OUT/'07-mailpit-correo.png'))
    try:
        page.goto('http://127.0.0.1:6082/vnc.html?autoconnect=true&resize=scale',wait_until='domcontentloaded',timeout=10000)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT/'09-novnc-escritorio.png'))
    except Exception as exc: print('noVNC browser preview unavailable:',exc)
    browser.close()
print('Capturas:',*[x.name for x in sorted(OUT.glob('*.png'))],sep='\n  ')
