import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MantineProvider, AppShell, NavLink, Group, Stack, Title, Text, Badge, Button, Paper, SimpleGrid, ThemeIcon, Table, FileInput, TextInput, Select, Alert, Timeline, Divider, ScrollArea, Loader, Modal, Textarea, Box, Anchor, Center, ActionIcon, Tooltip } from '@mantine/core';
import { IconReceipt2, IconLayoutDashboard, IconArrowsRightLeft, IconRobot, IconDeviceDesktop, IconFileSpreadsheet, IconMail, IconExternalLink, IconUpload, IconCheck, IconAlertTriangle, IconArrowRight, IconDownload, IconRefresh, IconShieldCheck, IconPhoto, IconPlayerPlay, IconClock, IconCircleCheck, IconCircleX, IconInfoCircle, IconGitBranch, IconEye } from '@tabler/icons-react';
import Viewer from 'bpmn-js/lib/Viewer';
import '@fontsource-variable/dm-sans/wght.css';
import '@fontsource-variable/manrope/wght.css';
import '@mantine/core/styles.css';
import 'bpmn-js/dist/assets/bpmn-js.css';
import 'bpmn-js/dist/assets/diagram-js.css';
import './style.css';

type Claim = {
  id: string; employee: string; category: string; merchant: string; receipt_number: string;
  receipt_date: string; amount: number; filename: string; original_name: string;
  state: string; reason: string; ocr_text: string; email_to: string; error: string;
  created_at: string; events?: { at: string; step: string; detail: string; screenshot: string }[];
};

type Section = 'inicio' | 'manual' | 'automatizado' | 'laboratorio' | 'trazabilidad';
const colors: Record<string, string> = { listo: 'teal', pendiente_aprobacion: 'orange', ejecutando: 'blue', excel_listo: 'cyan', correo_enviado: 'green', rechazado: 'red', enviando_correo: 'blue' };
const labels: Record<string, string> = { listo: 'Lista para ejecutar', pendiente_aprobacion: 'Revisión humana', ejecutando: 'En ejecución', excel_listo: 'Excel listo', correo_enviado: 'Correo enviado', rechazado: 'Rechazada', enviando_correo: 'Enviando correo' };
const money = (value: number) => '$' + new Intl.NumberFormat('es-CL').format(value) + ' CLP';
const short = (id: string) => id.slice(0, 8).toUpperCase();
const preview = /^8080-.*\.manus\.computer$/.test(window.location.hostname);
const previewUrl = (port: number) => `${window.location.protocol}//${window.location.hostname.replace(/^8080-/, `${port}-`)}`;
const desktopUrl = preview ? `${previewUrl(6082)}/vnc.html?autoconnect=true&resize=scale` : 'http://localhost:6080/vnc.html?autoconnect=true&resize=scale';
const mailpitUrl = preview ? previewUrl(8026) : 'http://localhost:8025';
async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data as T;
}

function Diagram({ name }: { name: 'manual' | 'automatizado' }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!ref.current) return;
    const viewer = new Viewer({ container: ref.current });
    let disposed = false;
    fetch(`/api/diagrams/${name}`).then(r => r.text()).then(xml => viewer.importXML(xml)).then(() => {
      if (!disposed) (viewer.get('canvas') as { zoom: (level: string) => void }).zoom('fit-viewport');
    }).catch(e => { if (!disposed) setError(String(e)); });
    return () => { disposed = true; viewer.destroy(); };
  }, [name]);
  return <Paper className="diagram-frame" p="xs" radius="md" withBorder>{error ? <Alert color="red">No se pudo abrir el BPMN: {error}</Alert> : <div className="diagram-canvas" ref={ref} aria-label={`Diagrama BPMN ${name}`} />}</Paper>;
}

function Status({ value }: { value: string }) { return <Badge variant="light" color={colors[value] || 'gray'} size="lg" radius="sm">{labels[value] || value}</Badge>; }

function MailComposer({ id }: { id: string }) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [to, setTo] = useState('demo@ejemplo.local');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { api<Claim>(`/api/claims/${id}`).then(c => {
    setClaim(c); setTo(c.email_to);
    setSubject(`Rendición ${c.receipt_number} — ${c.employee}`);
    setBody(`Estimado equipo de Contabilidad:\n\nSe adjunta la boleta ${c.receipt_number} de ${c.merchant} y el registro de rendiciones actualizado.\nMonto: ${money(c.amount)}.\n\nDemo de proceso: este mensaje no ordena un reembolso.`);
  }).catch(e => setMessage(e.message)); }, [id]);
  const send = async (e: React.FormEvent) => {
    e.preventDefault(); if (busy || claim?.state === 'correo_enviado') return;
    setBusy(true); setMessage('');
    try { await api(`/api/claims/${id}/send`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ to, subject, body }) }); setClaim(c => c ? { ...c, state: 'correo_enviado' } : c); setMessage('Correo aceptado por Mailpit. Revise su bandeja de pruebas.'); }
    catch (err) { setMessage((err as Error).message); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    const listener = (e: KeyboardEvent) => { if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); form.current?.requestSubmit(); } };
    document.addEventListener('keydown', listener); return () => document.removeEventListener('keydown', listener);
  }, []);
  return <MantineProvider theme={theme}><div className="compose-page"><Paper className="compose-card" radius="lg" p="xl" shadow="md">
    <Group justify="space-between" mb="xl"><Group><ThemeIcon size={45} radius="md" color="navy"><IconMail size={24} /></ThemeIcon><div><Text fw={800}>CENTRO DE RENDICIONES</Text><Text size="sm" c="dimmed">Composición de correo · escritorio noVNC</Text></div></Group><Badge color="teal" variant="light">ENTORNO DE PRUEBA</Badge></Group>
    <Title order={2}>Enviar rendición a Contabilidad</Title><Text c="dimmed" mt="xs" mb="lg">El agente utiliza este formulario visible. Ctrl + Enter confirma el envío; el servidor entrega el correo por SMTP.</Text>
    {claim && <Paper p="md" mb="lg" className="compose-summary"><Group justify="space-between"><div><Text size="xs" tt="uppercase" fw={700} c="dimmed">Rendición #{short(claim.id)}</Text><Text fw={700}>{claim.merchant} · {money(claim.amount)}</Text></div><Status value={claim.state} /></Group></Paper>}
    <form ref={form} onSubmit={send}><Stack gap="md"><TextInput label="Para" value={to} onChange={e => setTo(e.target.value)} autoFocus required description="Por defecto: bandeja local Mailpit; no sale a Internet" /><TextInput label="Asunto" value={subject} onChange={e => setSubject(e.target.value)} required /><Textarea label="Mensaje" rows={7} value={body} onChange={e => setBody(e.target.value)} /><Paper p="sm" withBorder><Text size="sm" fw={700}>Adjuntos generados automáticamente</Text><Text size="sm" c="dimmed">rendiciones.xlsx · {claim?.original_name || 'boleta'}</Text></Paper><Group justify="space-between"><Text size="xs" c="dimmed">Sin pagos reales ni reembolsos · Datos sintéticos</Text><Button type="submit" color="teal" loading={busy} disabled={!claim || claim.state === 'correo_enviado'} leftSection={<IconMail size={18} />}>Enviar correo</Button></Group></Stack></form>
    {message && <Alert mt="md" color={claim?.state === 'correo_enviado' ? 'teal' : 'red'}>{message}</Alert>}
  </Paper></div></MantineProvider>;
}

const theme = { primaryColor: 'navy', colors: { navy: ['#e7eff5','#bfd0dd','#91aec4','#648dab','#426d90','#2b577b','#214764','#1a3852','#172d44','#102237'] as const } };

function App() {
  const [section, setSection] = useState<Section>('inicio');
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selected, setSelected] = useState<Claim | null>(null);
  const [receipt, setReceipt] = useState<File | null>(null);
  const [employee, setEmployee] = useState('Ana Pérez');
  const [category, setCategory] = useState<string | null>('Alimentación');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [modalImage, setModalImage] = useState('');
  const refresh = useCallback(async () => {
    try {
      const rows = await api<Claim[]>('/api/claims'); setClaims(rows);
      if (selected) { const item = await api<Claim>(`/api/claims/${selected.id}`); setSelected(item); }
    } catch (e) { setError((e as Error).message); }
  }, [selected?.id]);
  useEffect(() => { void refresh(); const interval = window.setInterval(() => { void refresh(); }, 2200); return () => clearInterval(interval); }, [refresh]);

  const upload = async (file: File | null) => {
    if (!file) { setError('Seleccione una boleta para continuar'); return; }
    setBusy(true); setError(''); setNotice('');
    const data = new FormData(); data.append('receipt', file); data.append('employee', employee); data.append('category', category || 'Otros');
    try { const item = await api<Claim>('/api/claims', { method: 'POST', body: data }); setSelected(item); setReceipt(null); setNotice(`Boleta ${item.receipt_number || 'sin folio'} recibida y analizada. Revise los campos antes de avanzar.`); setSection('laboratorio'); await refresh(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const sample = async (which: 'auto' | 'excepcion') => { const url = `/samples/boleta-${which}.png`; const blob = await fetch(url).then(r => r.blob()); await upload(new File([blob], `boleta-${which}.png`, { type: 'image/png' })); };
  const action = async (url: string, body?: object) => { setError(''); setNotice(''); try { await api(url, { method: 'POST', headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined }); setNotice('Acción registrada. El historial se actualizará automáticamente.'); await refresh(); } catch (e) { setError((e as Error).message); } };
  const nav = [
    { key: 'inicio' as Section, label: 'Vista general', icon: IconLayoutDashboard },
    { key: 'manual' as Section, label: 'Proceso manual', icon: IconArrowsRightLeft },
    { key: 'automatizado' as Section, label: 'Proceso automatizado', icon: IconGitBranch },
    { key: 'laboratorio' as Section, label: 'Laboratorio', icon: IconDeviceDesktop },
    { key: 'trazabilidad' as Section, label: 'Trazabilidad', icon: IconEye },
  ];
  return <MantineProvider theme={theme}><AppShell navbar={{ width: 264, breakpoint: 'sm' }} header={{ height: 68 }} padding="xl">
    <AppShell.Header><Group h="100%" px="xl" justify="space-between"><Group gap="md"><div className="brand-icon"><IconReceipt2 size={23} stroke={2} /></div><div><Text size="sm" fw={800} className="brand-name">RENDICIÓN <span>LAB</span></Text><Text size="xs" c="dimmed">Computer use · demostración</Text></div></Group><Group gap="lg"><Badge variant="dot" color="teal" visibleFrom="sm">ENTORNO LOCAL</Badge><Text size="xs" c="dimmed" visibleFrom="sm">v1.0 · Datos de ejemplo</Text></Group></Group></AppShell.Header>
    <AppShell.Navbar p="md" className="sidebar"><Text size="xs" fw={800} c="dimmed" tt="uppercase" px="md" mt="lg" mb="sm" className="tracking">EXPLORAR DEMO</Text>{nav.map(n => <NavLink key={n.key} label={n.label} leftSection={<n.icon size={19} />} active={section === n.key} onClick={() => setSection(n.key)} className="sidebar-link" />)}<div className="sidebar-bottom"><Divider my="md" /><Text size="xs" fw={700} mb="xs">ENTORNO CONTROLADO</Text><Text size="xs" c="dimmed" lh={1.6}>OCR local · Excel mediante GUI · correo capturado en Mailpit. Sin pagos reales.</Text><Anchor href="https://github.com/redai-studio/hybrid-routing-agent" target="_blank" size="xs" mt="md" display="block">Investigación de referencia ↗</Anchor></div></AppShell.Navbar>
    <AppShell.Main><div className="content-wrap">
      {error && <Alert color="red" icon={<IconAlertTriangle size={18} />} withCloseButton onClose={() => setError('')} mb="md">{error}</Alert>}
      {notice && <Alert color="teal" icon={<IconCheck size={18} />} withCloseButton onClose={() => setNotice('')} mb="md">{notice}</Alert>}
      {section === 'inicio' && <>
        <div className="eyebrow">LABORATORIO DE AUTOMATIZACIÓN · CHILE</div><div className="hero"><div className="hero-copy"><Badge className="hero-badge" variant="light" color="cyan">BPMN + OCR + COMPUTER USE</Badge><Title order={1}>De la boleta al Excel.<br /><span>Sin copiar ni pegar a mano.</span></Title><Text className="hero-intro">Explore el proceso manual, compárelo con el flujo automatizado y observe a un agente operar LibreOffice y el correo directamente sobre un escritorio remoto.</Text><Group mt="xl"><Button color="teal" size="md" rightSection={<IconArrowRight size={18} />} onClick={() => setSection('laboratorio')}>Iniciar demostración</Button><Button variant="white" color="navy" size="md" onClick={() => setSection('manual')}>Ver proceso BPMN</Button></Group></div><div className="hero-side"><div className="hero-illustration"><IconReceipt2 size={64} stroke={1.2} /><div className="hero-flow"><span>BOLETA</span><IconArrowRight size={18} /><span>CALC</span><IconArrowRight size={18} /><span>CORREO</span></div></div><div className="hero-meta"><b>01</b><span>UN FLUJO REAL, PASO A PASO</span></div></div></div>
        <div className="section-heading"><div><Text className="overline">EL RECORRIDO</Text><Title order={2}>Una demo verificable, no una simulación visual</Title></div><Text c="dimmed" size="sm">Cada paso registra eventos y capturas del escritorio.</Text></div>
        <SimpleGrid cols={{ base: 1, md: 3 }} spacing="lg">{[
          { icon: IconUpload, num: '01', title: 'Recibir y leer', body: 'Cargue una boleta sintética. Tesseract extrae folio, emisor, fecha y total; las reglas deciden si requiere revisión.', color: 'blue' },
          { icon: IconDeviceDesktop, num: '02', title: 'Operar el escritorio', body: 'PyAutoGUI observa el escritorio, abre LibreOffice Calc, escribe la fila en celdas y guarda el XLSX.', color: 'teal' },
          { icon: IconMail, num: '03', title: 'Enviar con evidencia', body: 'El agente abre Chromium y envía desde el formulario; Mailpit captura correo y adjuntos de prueba.', color: 'orange' },
        ].map(card => <Paper key={card.num} className="feature-card" p="xl" radius="md"><Group justify="space-between" mb="xl"><ThemeIcon size={44} radius="md" variant="light" color={card.color}><card.icon size={22} /></ThemeIcon><Text className="card-number">{card.num}</Text></Group><Title order={3}>{card.title}</Title><Text size="sm" c="dimmed" mt="sm" lh={1.7}>{card.body}</Text></Paper>)}</SimpleGrid>
        <Paper className="info-strip" p="lg" mt="xl" radius="md"><Group justify="space-between"><Group><IconShieldCheck size={28} /><div><Text fw={750}>Límites y control humano</Text><Text size="sm">Monto superior a $50.000 CLP o datos dudosos ⇒ aprobación de jefatura. Reembolso real fuera del alcance.</Text></div></Group><Button variant="subtle" color="navy" rightSection={<IconArrowRight size={16} />} onClick={() => setSection('automatizado')}>Explorar reglas</Button></Group></Paper>
      </>}
      {(section === 'manual' || section === 'automatizado') && <>
        <div className="eyebrow">MAPA DE PROCESO · BPMN 2.0</div><Group justify="space-between" align="end" className="page-title"><div><Title order={1}>{section === 'manual' ? 'Proceso manual' : 'Proceso automatizado'}</Title><Text c="dimmed" mt="xs">{section === 'manual' ? 'Flujo actual: captura, transcripción y coordinación por correo.' : 'Flujo propuesto: OCR, reglas de negocio y trabajo visible en escritorio.'}</Text></div><Group><Button variant="default" onClick={() => setSection(section === 'manual' ? 'automatizado' : 'manual')} leftSection={<IconArrowsRightLeft size={16} />}>Comparar</Button><Button component="a" variant="light" href={`/api/diagrams/${section === 'manual' ? 'manual' : 'automatizado'}`} download leftSection={<IconDownload size={16} />}>Descargar BPMN</Button></Group></Group>
        <Paper p="md" radius="md" className="diagram-panel"><Group justify="space-between" mb="sm"><Group><IconGitBranch size={18} /><Text fw={700}>Modelo BPMN 2.0 editable e interoperable</Text></Group><Badge variant="light">{section === 'manual' ? '4 carriles · revisión y corrección' : '3 carriles · excepción y control humano'}</Badge></Group><Diagram name={section} /></Paper>
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg" mt="lg"><Paper p="xl" radius="md" withBorder><Text className="overline">SECUENCIA OPERATIVA</Text><Title order={3} mt="xs">{section === 'manual' ? 'Dónde se consume el tiempo' : 'Qué cambia con computer use'}</Title><Stack gap="md" mt="lg">{(section === 'manual' ? [
          ['Recepción', 'Empleado entrega la boleta; no existe todavía un registro estructurado.'],
          ['Digitación', 'Empleado transcribe importe, proveedor, fecha y folio en Excel.'],
          ['Control', 'Contabilidad revisa, jefatura aprueba y el empleado corrige si hay observaciones.'],
          ['Cierre', 'La solicitud aprobada habilita un reembolso posterior (no implementado).'],
        ] : [
          ['Lectura', 'OCR local extrae datos; el archivo y el texto quedan trazados.'],
          ['Regla', 'Monto ≤ $50.000 CLP y campos válidos: autoaprobación. Excepción: decisión humana.'],
          ['Escritorio', 'PyAutoGUI opera Calc mediante GUI y verifica la fila guardada en el XLSX.'],
          ['Correo', 'Chromium envía con Ctrl + Enter. Mailpit intercepta el SMTP y conserva adjuntos.'],
        ]).map(([a,b], i) => <Group align="flex-start" key={a} wrap="nowrap"><ThemeIcon size={27} radius="xl" variant="light" color={section === 'manual' ? 'gray' : 'teal'}>{i+1}</ThemeIcon><div><Text fw={700} size="sm">{a}</Text><Text c="dimmed" size="sm">{b}</Text></div></Group>)}</Stack></Paper>
        <Paper p="xl" radius="md" withBorder><Text className="overline">CRITERIOS DE DISEÑO</Text><Title order={3} mt="xs">{section === 'manual' ? 'Puntos de fricción' : 'Automatización gobernada'}</Title><Table mt="lg" verticalSpacing="md"><Table.Tbody>{(section === 'manual' ? [
          ['Errores de transcripción', 'Folio o montos incorrectos al copiar'],['Tiempos de espera', 'Correcciones que regresan al empleado'],['Poca trazabilidad', 'Evidencia dispersa entre correo y Excel'],
        ] : [
          ['Idempotencia', 'El mismo folio no se registra dos veces'],['Separación', 'El OCR y las reglas no sustituyen la aprobación humana'],['Verificación', 'Fila leída desde el XLSX luego del guardado GUI'],['Contención', 'Correo .local por defecto; nada se reembolsa'],
        ]).map(([a,b]) => <Table.Tr key={a}><Table.Td fw={700}>{a}</Table.Td><Table.Td c="dimmed">{b}</Table.Td></Table.Tr>)}</Table.Tbody></Table><Alert color="blue" variant="light" mt="xl" icon={<IconInfoCircle size={17} />}>El artículo de referencia demuestra enrutamiento GUI/MCP con un modelo Qwen entrenado. Esta demo usa un agente GUI determinista; no ejecuta ese checkpoint ni declara sus métricas.</Alert></Paper></SimpleGrid>
      </>}
      {(section === 'laboratorio' || section === 'trazabilidad') && <>
        <div className="eyebrow">{section === 'laboratorio' ? 'LABORATORIO INTERACTIVO' : 'AUDITORÍA DEL PROCESO'}</div><Group justify="space-between" align="end" className="page-title"><div><Title order={1}>{section === 'laboratorio' ? 'Ejecute una rendición' : 'Trazabilidad completa'}</Title><Text c="dimmed" mt="xs">{section === 'laboratorio' ? 'Suba una boleta, confirme reglas y observe el escritorio.' : 'Cada ejecución conserva estados, capturas y archivos verificables.'}</Text></div><Group><Button component="a" href={desktopUrl} target="_blank" variant="light" leftSection={<IconDeviceDesktop size={18} />} rightSection={<IconExternalLink size={14} />}>Abrir noVNC</Button><Button component="a" href={mailpitUrl} target="_blank" variant="default" leftSection={<IconMail size={18} />}>Ver Mailpit</Button></Group></Group>
        {section === 'laboratorio' && <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg"><Paper p="xl" radius="md" withBorder><Group mb="lg"><ThemeIcon size={42} radius="md" color="teal" variant="light"><IconUpload size={22} /></ThemeIcon><div><Text fw={750}>01 / Ingreso de boleta</Text><Text size="xs" c="dimmed">PNG, JPG o PDF · máximo 5 MB</Text></div></Group><Stack><TextInput label="Empleado" value={employee} onChange={e => setEmployee(e.target.value)} /><Select label="Categoría" data={['Alimentación','Transporte','Materiales','Otros']} value={category} onChange={setCategory} /><FileInput label="Documento" placeholder="Seleccione una boleta" accept="image/png,image/jpeg,application/pdf" value={receipt} onChange={setReceipt} leftSection={<IconPhoto size={17} />} /><Button onClick={() => upload(receipt)} loading={busy} leftSection={<IconUpload size={17} />}>Cargar y extraer con OCR</Button></Stack><Divider label="O pruebe un caso sintético" my="lg" /><Group grow><Button variant="light" color="teal" size="xs" onClick={() => sample('auto')} disabled={busy}>Boleta · autoaprobación</Button><Button variant="light" color="orange" size="xs" onClick={() => sample('excepcion')} disabled={busy}>Boleta · excepción</Button></Group></Paper>
          <Paper p="xl" radius="md" withBorder><Group mb="lg"><ThemeIcon size={42} radius="md" color="navy" variant="light"><IconRobot size={22} /></ThemeIcon><div><Text fw={750}>02 / Ruta de automatización</Text><Text size="xs" c="dimmed">Ejecución local y verificable</Text></div></Group><Timeline active={selected ? 2 : 0} bulletSize={24} lineWidth={2} color="teal"><Timeline.Item bullet={<IconReceipt2 size={14} />} title="Capturar y leer"><Text size="sm" c="dimmed">OCR Tesseract + campos estructurados</Text></Timeline.Item><Timeline.Item bullet={<IconShieldCheck size={14} />} title="Validar política"><Text size="sm" c="dimmed">Autoaprobación o revisión de jefatura</Text></Timeline.Item><Timeline.Item bullet={<IconFileSpreadsheet size={14} />} title="Escribir en LibreOffice"><Text size="sm" c="dimmed">Interacción GUI, no inserción de filas por API</Text></Timeline.Item><Timeline.Item bullet={<IconMail size={14} />} title="Enviar correo"><Text size="sm" c="dimmed">Formulario visible + SMTP de pruebas</Text></Timeline.Item></Timeline><Alert color="gray" variant="light" mt="lg" icon={<IconInfoCircle size={16} />}>Para ver las acciones en tiempo real, abra noVNC antes de ejecutar el agente.</Alert></Paper></SimpleGrid>}
        <div className="section-heading"><div><Text className="overline">REGISTRO DE EJECUCIÓN</Text><Title order={2}>Rendiciones</Title></div><Group><Button variant="default" leftSection={<IconRefresh size={16} />} onClick={() => refresh()}>Actualizar</Button><Button component="a" href="/api/workbook" leftSection={<IconDownload size={16} />}>Descargar Excel</Button></Group></div>
        <Paper withBorder radius="md" className="table-shell"><ScrollArea><Table striped highlightOnHover verticalSpacing="md" horizontalSpacing="lg"><Table.Thead><Table.Tr><Table.Th>ID / fecha</Table.Th><Table.Th>Empleado</Table.Th><Table.Th>Proveedor / folio</Table.Th><Table.Th>Monto</Table.Th><Table.Th>Estado</Table.Th><Table.Th></Table.Th></Table.Tr></Table.Thead><Table.Tbody>{claims.length ? claims.map(c => <Table.Tr key={c.id}><Table.Td><Text fw={750} size="sm">#{short(c.id)}</Text><Text size="xs" c="dimmed">{new Date(c.created_at).toLocaleString('es-CL')}</Text></Table.Td><Table.Td>{c.employee}</Table.Td><Table.Td><Text size="sm" fw={600}>{c.merchant || 'Pendiente'}</Text><Text size="xs" c="dimmed">{c.receipt_number || 'Folio no identificado'}</Text></Table.Td><Table.Td fw={700}>{money(c.amount)}</Table.Td><Table.Td><Status value={c.state} /></Table.Td><Table.Td><Button size="xs" variant="subtle" onClick={() => setSelected(c)}>Ver detalle <IconArrowRight size={14} /></Button></Table.Td></Table.Tr>) : <Table.Tr><Table.Td colSpan={6}><Center py="xl"><Text c="dimmed">Aún no hay rendiciones. Cargue una boleta de ejemplo.</Text></Center></Table.Td></Table.Tr>}</Table.Tbody></Table></ScrollArea></Paper>
        {selected && <Paper mt="xl" p="xl" radius="md" withBorder><Group justify="space-between" align="start" mb="lg"><div><Text className="overline">EXPEDIENTE / #{short(selected.id)}</Text><Title order={2}>{selected.merchant || 'Lectura pendiente'}</Title><Text c="dimmed" size="sm">{selected.employee} · folio {selected.receipt_number || 'sin identificar'} · {selected.receipt_date || 'sin fecha'}</Text></div><Status value={selected.state} /></Group><SimpleGrid cols={{ base: 1, md: 3 }} spacing="lg"><Paper p="md" className="metric"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Importe detectado</Text><Text size="xl" fw={800}>{money(selected.amount)}</Text></Paper><Paper p="md" className="metric"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Ruta de decisión</Text><Text fw={700}>{selected.reason ? 'Excepción / revisión humana' : 'Autoaprobación'}</Text></Paper><Paper p="md" className="metric"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Evidencia</Text><Text fw={700}>{selected.events?.filter(e => e.screenshot).length || 0} capturas del escritorio</Text></Paper></SimpleGrid>
          {selected.reason && <Alert color="orange" mt="lg" icon={<IconAlertTriangle size={18} />} title="Excepción detectada">{selected.reason}</Alert>}
          {selected.error && <Alert color="red" mt="lg" title="Último error">{selected.error}</Alert>}
          <Group mt="lg"><Button component="a" href={`/api/claims/${selected.id}/receipt`} variant="default" leftSection={<IconDownload size={16} />}>Boleta</Button>{selected.state === 'pendiente_aprobacion' && <><Button color="teal" leftSection={<IconCheck size={16} />} onClick={() => action(`/api/claims/${selected.id}/decision`, { decision: 'aprobar' })}>Aprobar excepción</Button><Button color="red" variant="light" onClick={() => action(`/api/claims/${selected.id}/decision`, { decision: 'rechazar' })}>Rechazar</Button></>}{['listo','excel_listo'].includes(selected.state) && <Button color="teal" leftSection={<IconPlayerPlay size={16} />} onClick={() => action(`/api/claims/${selected.id}/automate`)}>Ejecutar computer use</Button>}{selected.state === 'correo_enviado' && <Badge color="green" size="xl" leftSection={<IconCircleCheck size={16} />}>Completado · revise Mailpit</Badge>}</Group>
          <Divider my="xl" /><SimpleGrid cols={{ base: 1, lg: 2 }}><div><Text fw={750} mb="md">Cronología auditable</Text><Timeline active={(selected.events?.length || 1) - 1} bulletSize={22} lineWidth={2} color="teal">{selected.events?.map((e, index) => <Timeline.Item key={index} bullet={e.step === 'Error' ? <IconCircleX size={13} /> : <IconClock size={13} />} title={e.step}><Text size="xs" c="dimmed">{new Date(e.at).toLocaleString('es-CL')}</Text><Text size="sm" mt={4}>{e.detail}</Text>{e.screenshot && <Button variant="subtle" size="xs" px={0} onClick={() => setModalImage(`/api/claims/${selected.id}/screenshot/${e.screenshot}`)}>Ver captura ↗</Button>}</Timeline.Item>)}</Timeline></div><div><Text fw={750} mb="md">Capturas reales de la ejecución</Text><div className="screenshot-grid">{selected.events?.filter(e => e.screenshot).map(e => <button className="shot" key={e.screenshot} onClick={() => setModalImage(`/api/claims/${selected.id}/screenshot/${e.screenshot}`)}><img src={`/api/claims/${selected.id}/screenshot/${e.screenshot}`} alt={`Captura ${e.step}`} /><span>{e.step.replaceAll('-', ' ')}</span></button>)}{!selected.events?.some(e => e.screenshot) && <Paper p="xl" withBorder><Text size="sm" c="dimmed">Las capturas aparecerán cuando se ejecute el agente.</Text></Paper>}</div><Text fw={750} mt="xl" mb="xs">Texto leído por OCR</Text><pre className="ocr-block">{selected.ocr_text || '(sin texto)'}</pre></div></SimpleGrid></Paper>}
      </>}
      <footer className="footer">RENDICIÓN LAB · Demostración técnica · Sin datos personales reales · Inspirado en investigación GUI + MCP, no afiliado a sus autores.</footer>
    </div></AppShell.Main><Modal opened={Boolean(modalImage)} onClose={() => setModalImage('')} title="Captura original del escritorio" size="90vw" centered><img src={modalImage} alt="Evidencia del escritorio" style={{ width: '100%', height: 'auto' }} /></Modal>
  </AppShell></MantineProvider>;
}

const match = window.location.pathname.match(/^\/correo\/([a-f0-9-]{36})$/);
createRoot(document.getElementById('root')!).render(match ? <MailComposer id={match[1]} /> : <App />);
