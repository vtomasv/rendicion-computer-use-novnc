from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image
from openpyxl import load_workbook

from app import core
from app.agent import safe_excel
from app.server import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DATA', tmp_path)
    monkeypatch.setattr(core, 'DB', tmp_path / 'test.sqlite3')
    monkeypatch.setattr(core, 'BOOK', tmp_path / 'rendiciones.xlsx')
    core.init()
    app.config['TESTING'] = True
    return app.test_client()


def upload(client, kind='auto'):
    path = ROOT / 'samples' / f'boleta-{kind}.png'
    return client.post('/api/claims', data={'employee': 'Ana Pérez', 'category': 'Alimentación',
                                              'receipt': (io.BytesIO(path.read_bytes()), path.name)},
                       content_type='multipart/form-data')


def test_ocr_autoapproval_and_duplicate(client):
    response = upload(client)
    assert response.status_code == 201, response.get_json()
    item = response.get_json()
    assert item['merchant'] == 'Cafeteria Central SpA'
    assert item['receipt_number'] == 'A000481'
    assert item['amount'] == 12490
    assert item['state'] == 'listo'
    assert upload(client).status_code == 400
    assert len(client.get('/api/claims').get_json()) == 1


def test_exception_requires_human_and_rejection(client):
    item = upload(client, 'excepcion').get_json()
    assert item['state'] == 'pendiente_aprobacion'
    assert 'Monto mayor' in item['reason']
    assert client.post(f"/api/claims/{item['id']}/automate").status_code == 409
    answer = client.post(f"/api/claims/{item['id']}/decision", json={'decision':'aprobar'})
    assert answer.get_json()['state'] == 'listo'
    assert client.post(f"/api/claims/{item['id']}/decision", json={'decision':'aprobar'}).status_code == 409
    assert any(e['step'] == 'Decisión humana' for e in client.get(f"/api/claims/{item['id']}").get_json()['events'])


def test_mail_needs_gui_saved_row_and_local_destination(client, monkeypatch):
    item = upload(client).get_json()
    path = f"/api/claims/{item['id']}/send"
    assert client.post(path, json={'to':'demo@ejemplo.local'}).status_code == 409
    book = load_workbook(core.BOOK)
    book.active.append([item['id'], 'Ana Pérez', item['merchant']])
    book.save(core.BOOK)
    assert client.post(path, json={'to':'alguien@gmail.com'}).status_code == 400
    assert core.transition(item['id'], ('listo',), 'excel_listo')
    captured=[]
    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured.extend([host, port])
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def send_message(self, msg): captured.append(msg)
    monkeypatch.setattr('app.server.smtplib.SMTP', FakeSMTP)
    response = client.post(path, json={'to':'demo@ejemplo.local'})
    assert response.status_code == 200
    assert len(list(captured[2].iter_attachments())) == 2
    assert core.get_claim(item['id'])['state'] == 'correo_enviado'
    assert client.post(path, json={'to':'demo@ejemplo.local'}).status_code == 409


def test_bpmn_diagrams_parse_and_use_exclusive_gateways(client):
    for name in ('manual','automatizado'):
        response = client.get(f'/api/diagrams/{name}')
        assert response.status_code == 200
        root = ET.fromstring(response.data)
        namespace = {'bpmn':'http://www.omg.org/spec/BPMN/20100524/MODEL',
                     'bpmndi':'http://www.omg.org/spec/BPMN/20100524/DI'}
        assert root.findall('.//bpmn:exclusiveGateway', namespace)
        assert root.findall('.//bpmn:lane', namespace)
        assert root.findall('.//bpmndi:BPMNShape', namespace)


def test_missing_and_invalid_upload(client):
    assert client.post('/api/claims').status_code == 400
    result=client.post('/api/claims',data={'employee':'Ana','category':'Otros',
                                          'receipt':(io.BytesIO(b'evil'), 'boleta.exe')})
    assert result.status_code == 400
    assert client.get('/api/claims/00000000-0000-0000-0000-000000000000').status_code == 404


def test_spreadsheet_formula_injection_is_neutralized():
    for value in ('=HYPERLINK("a")', '+SUM(1,2)', '-1+2', '@COMMAND'):
        assert safe_excel(value).startswith("'")
    assert safe_excel('Cafeteria Central SpA') == 'Cafeteria Central SpA'


def test_frontend_has_no_blocking_external_stylesheets():
    html = (ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8')
    assert 'fonts.googleapis.com' not in html
    assert 'https://' not in html
    assert '@fontsource-variable/dm-sans/wght.css' in (ROOT / 'frontend' / 'src' / 'main.tsx').read_text(encoding='utf-8')


def test_unreadable_receipt_cannot_be_approved(client):
    buffer = io.BytesIO()
    Image.new('RGB', (400, 250), 'white').save(buffer, format='PNG')
    buffer.seek(0)
    result = client.post('/api/claims', data={'employee':'Ana', 'category':'Otros',
                                               'receipt':(buffer,'ilegible.png')},
                         content_type='multipart/form-data')
    assert result.status_code == 201
    item = result.get_json()
    assert item['state'] == 'pendiente_aprobacion'
    decision = client.post(f"/api/claims/{item['id']}/decision", json={'decision':'aprobar'})
    assert decision.status_code == 409
    assert core.get_claim(item['id'])['state'] == 'pendiente_aprobacion'
