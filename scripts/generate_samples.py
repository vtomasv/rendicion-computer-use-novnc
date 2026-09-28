"""Boletas 100 % sintéticas: ninguna imagen de terceros ni dato personal real."""
from datetime import date, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def make(name: str, merchant: str, folio: str, total: str, label: str) -> None:
    canvas = Image.new('RGB', (1000, 1250), '#f4f7f8')
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((115,65,885,1160),radius=20,fill='white',outline='#d8e1e6',width=3)
    d.rectangle((115,65,885,83),fill='#17324d')
    f22 = ImageFont.truetype(FONT,22)
    f26 = ImageFont.truetype(FONT,26)
    f32 = ImageFont.truetype(BOLD,32)
    f44 = ImageFont.truetype(BOLD,44)
    d.text((175,125),'COMPROBANTE DE GASTO',font=f26,fill='#687d8d')
    d.text((175,180),'BOLETA ELECTRONICA',font=f44,fill='#17324d')
    d.line((175,267,825,267),fill='#d9e2e7',width=2)
    issued=(date.today()-timedelta(days=2)).isoformat()
    lines=[f'EMISOR: {merchant}',f'FOLIO: {folio}',f'FECHA: {issued}', 'CONCEPTO: Gasto de trabajo', 'CANTIDAD: 1']
    for i,line in enumerate(lines):
        d.text((175,325+i*84),line,font=f26,fill='#263f50')
    d.line((175,775,825,775),fill='#d9e2e7',width=2)
    d.text((175,808),f'TOTAL: $ {total}',font=f32,fill='#17324d')
    d.rounded_rectangle((175,940,825,1040),radius=9,fill='#edf5f2')
    d.text((200,953),'DOCUMENTO SINTETICO - SOLO DEMO',font=f22,fill='#257060')
    d.text((175,1090),label,font=f22,fill='#748797')
    output=ROOT/'samples'/f'boleta-{name}.png'
    output.parent.mkdir(exist_ok=True)
    canvas.save(output, optimize=True)
    public=ROOT/'frontend'/'public'/'samples'/output.name
    public.parent.mkdir(exist_ok=True,parents=True)
    public.write_bytes(output.read_bytes())
    dist=ROOT/'frontend'/'dist'/'samples'/output.name
    if dist.parent.exists():
        dist.write_bytes(output.read_bytes())
    print(output)


if __name__=='__main__':
    make('auto','Cafeteria Central SpA','A000481','12.490','Caso A: monto dentro de politica')
    make('excepcion','Transporte Regional SpA','X000782','82.900','Caso B: requiere aprobacion')
    make('aprobacion','Transporte Regional SpA','X000783','82.900','Caso C: excepcion aprobada por jefatura')
