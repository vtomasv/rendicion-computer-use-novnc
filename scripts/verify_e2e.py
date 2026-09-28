"""Prueba integral del escritorio real. Úsese con un volumen/datos de demo recién iniciados.

DEMO_URL=http://127.0.0.1:8090 MAILPIT_URL=http://127.0.0.1:8025 python scripts/verify_e2e.py
"""
from __future__ import annotations
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
APP=os.environ.get('DEMO_URL','http://127.0.0.1:8080').rstrip('/')
MAIL=os.environ.get('MAILPIT_URL','http://127.0.0.1:8025').rstrip('/')


def get(url: str):
    return json.load(urllib.request.urlopen(url,timeout=10))


def post(url: str, body: bytes, content_type: str):
    req=urllib.request.Request(url,data=body,headers={'Content-Type':content_type},method='POST')
    return get_request(req)


def get_request(req):
    try:
        return json.load(urllib.request.urlopen(req,timeout=20))
    except urllib.error.HTTPError as exc:
        raise AssertionError(f'HTTP {exc.code}: {exc.read().decode()}') from exc


def main():
    assert get(APP+'/api/health')['ok']
    before=get(MAIL+'/api/v1/messages')['messages_count']
    source=ROOT/'samples'/'boleta-auto.png'
    boundary='----rendicion'+uuid.uuid4().hex
    parts=[]
    def part(name,value,filename=None):
        head=f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename: head+=f'; filename="{filename}"\r\nContent-Type: image/png'
        parts.append((head+'\r\n\r\n').encode()+value+b'\r\n')
    part('employee','Ana Pérez'.encode())
    part('category','Alimentación'.encode())
    part('receipt',source.read_bytes(),source.name)
    body=b''.join(parts)+f'--{boundary}--\r\n'.encode()
    item=post(APP+'/api/claims',body,f'multipart/form-data; boundary={boundary}')
    assert (item['state'],item['amount'],item['merchant'])==('listo',12490,'Cafeteria Central SpA'),item
    print('OCR aprobado:',item['receipt_number'],item['amount'],'CLP',flush=True)
    result=post(APP+f"/api/claims/{item['id']}/automate",b'', 'application/json')
    assert result['started']
    started=time.monotonic(); last=''
    while time.monotonic()-started<110:
        detail=get(APP+f"/api/claims/{item['id']}")
        if detail['state']!=last:
            last=detail['state'];print(f"{int(time.monotonic()-started):02d}s: {last}",flush=True)
        if last=='correo_enviado': break
        if last in ('listo','excel_listo') and detail['error']:
            raise AssertionError(detail['error'])
        time.sleep(2)
    else: raise TimeoutError('No terminó en 110 segundos')
    data=urllib.request.urlopen(APP+'/api/workbook',timeout=15).read()
    wb=load_workbook(io.BytesIO(data),read_only=True)
    rows=[r for r in wb.active.values if r[0]==item['id']]
    wb.close()
    assert len(rows)==1 and rows[0][2]=='Cafeteria Central SpA' and rows[0][6]==12490,rows
    shots=[e['screenshot'] for e in detail['events'] if e['screenshot']]
    assert len(shots)>=6,shots
    messages=get(MAIL+'/api/v1/messages')
    assert messages['messages_count']==before+1,messages['messages_count']
    email=get(MAIL+'/api/v1/message/'+messages['messages'][0]['ID'])
    attached={a['FileName'] for a in email['Attachments']}
    assert attached=={'rendiciones.xlsx','boleta-auto.png'},attached
    print('ÉXITO E2E:',len(rows),'fila GUI,',len(shots),'capturas,',len(attached),'adjuntos SMTP',flush=True)

if __name__=='__main__': main()
