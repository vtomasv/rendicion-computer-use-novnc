"""Genera archivos BPMN 2.0 interoperables y con DI para bpmn-js / Camunda Modeler."""
from __future__ import annotations
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'bpmn'
NS = {
    'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
    'dc': 'http://www.omg.org/spec/DD/20100524/DC',
    'di': 'http://www.omg.org/spec/DD/20100524/DI',
}
for prefix, uri in NS.items(): ET.register_namespace(prefix, uri)
ET.register_namespace('xsi','http://www.w3.org/2001/XMLSchema-instance')

def tag(prefix: str, name: str) -> str: return f'{{{NS[prefix]}}}{name}'

def build(name: str, lanes: list[tuple[str,str,int,int]], nodes: list[tuple[str,str,str,int,int,int,int,str]], flows: list[tuple[str,str,str,str,list[tuple[int,int]]]]) -> None:
    definitions = ET.Element(tag('bpmn','definitions'), {'id':f'Definitions_{name}','targetNamespace':'https://example.local/rendiciones'})
    process = ET.SubElement(definitions, tag('bpmn','process'), {'id':f'Process_{name}','name':f'Rendición {name}','isExecutable':'false'})
    lane_set = ET.SubElement(process,tag('bpmn','laneSet'),{'id':f'LaneSet_{name}'})
    for lane_id,label,_,_ in lanes:
        lane = ET.SubElement(lane_set,tag('bpmn','lane'),{'id':lane_id,'name':label})
        for node_id,_,_,_,y,_,h,parent in nodes:
            if parent == lane_id:
                ET.SubElement(lane,tag('bpmn','flowNodeRef')).text=node_id
    for node_id,kind,label,_,_,_,_,_ in nodes:
        attrs={'id':node_id,'name':label}
        if kind == 'exclusiveGateway': attrs['gatewayDirection']='Diverging'
        ET.SubElement(process,tag('bpmn',kind),attrs)
    for flow_id,src,dst,label,_ in flows:
        attrs={'id':flow_id,'sourceRef':src,'targetRef':dst}
        if label: attrs['name']=label
        ET.SubElement(process,tag('bpmn','sequenceFlow'),attrs)
    diagram=ET.SubElement(definitions,tag('bpmndi','BPMNDiagram'),{'id':f'Diagram_{name}'})
    plane=ET.SubElement(diagram,tag('bpmndi','BPMNPlane'),{'id':f'Plane_{name}','bpmnElement':f'Process_{name}'})
    for lane_id,_,y,height in lanes:
        shape=ET.SubElement(plane,tag('bpmndi','BPMNShape'),{'id':f'{lane_id}_di','bpmnElement':lane_id,'isHorizontal':'true'})
        ET.SubElement(shape,tag('dc','Bounds'),{'x':'80','y':str(y),'width':'2140','height':str(height)})
    for node_id,kind,_,x,y,w,h,_ in nodes:
        attrs={'id':f'{node_id}_di','bpmnElement':node_id}
        if kind == 'exclusiveGateway': attrs['isMarkerVisible']='true'
        shape=ET.SubElement(plane,tag('bpmndi','BPMNShape'),attrs)
        ET.SubElement(shape,tag('dc','Bounds'),{'x':str(x),'y':str(y),'width':str(w),'height':str(h)})
    for flow_id,_,_,_,points in flows:
        edge=ET.SubElement(plane,tag('bpmndi','BPMNEdge'),{'id':f'{flow_id}_di','bpmnElement':flow_id})
        for x,y in points: ET.SubElement(edge,tag('di','waypoint'),{'x':str(x),'y':str(y)})
    tree=ET.ElementTree(definitions)
    ET.indent(tree,space='  ')
    target=ROOT / f'{name}.bpmn'
    tree.write(target,encoding='utf-8',xml_declaration=True)
    print(target)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    e='Empleado'; c='Contabilidad'; a='Aprobador'; s='Sistema'
    build('manual',[(e,e,80,160),(c,c,240,170),(a,a,410,170),(s,s,580,170)], [
        ('m_start','startEvent','Boleta recibida',135,139,36,36,e),
        ('m_receive','task','Recibir boleta',210,122,130,70,e),
        ('m_extract','task','Extraer datos a mano',390,122,150,70,e),
        ('m_excel','task','Llenar Excel',590,122,130,70,e),
        ('m_send','sendTask','Enviar correo',770,122,140,70,e),
        ('m_review','task','Revisar rendición',1010,292,145,70,c),
        ('m_gate','exclusiveGateway','¿Aprueba?',1240,470,50,50,a),
        ('m_correct','task','Corregir datos',1540,122,135,70,e),
        ('m_reimburse','task','Reembolsar (externo)',1540,635,175,70,s),
        ('m_end','endEvent','Fin',1800,652,36,36,s),
    ],[
        ('mf1','m_start','m_receive','',[(171,157),(210,157)]),
        ('mf2','m_receive','m_extract','',[(340,157),(390,157)]),
        ('mf3','m_extract','m_excel','',[(540,157),(590,157)]),
        ('mf4','m_excel','m_send','',[(720,157),(770,157)]),
        ('mf5','m_send','m_review','',[(910,157),(970,157),(970,327),(1010,327)]),
        ('mf6','m_review','m_gate','',[(1155,327),(1265,327),(1265,470)]),
        ('mf7','m_gate','m_correct','No',[(1265,470),(1265,215),(1607,215),(1607,192)]),
        ('mf8','m_correct','m_extract','Reingresar',[(1607,122),(1607,95),(465,95),(465,122)]),
        ('mf9','m_gate','m_reimburse','Sí',[(1290,495),(1627,495),(1627,635)]),
        ('mf10','m_reimburse','m_end','',[(1715,670),(1800,670)]),
    ])
    build('automatizado',[(e,e,80,160),(s,s,240,200),(a,a,440,180)], [
        ('a_start','startEvent','Subir boleta',140,140,36,36,e),
        ('a_ocr','serviceTask','OCR / extracción',240,300,145,75,s),
        ('a_rules','businessRuleTask','Validar política',450,300,145,75,s),
        ('a_gate','exclusiveGateway','¿Cumple política?',660,312,50,50,s),
        ('a_approval','userTask','Aprobación jefatura',780,495,175,75,a),
        ('a_decision','exclusiveGateway','¿Autoriza?',1010,507,50,50,a),
        ('a_rejected','endEvent','Rechazada',1190,514,36,36,a),
        ('a_merge','exclusiveGateway','',1040,312,50,50,s),
        ('a_excel','task','Escribir en Calc (GUI)',1165,300,180,75,s),
        ('a_mail','sendTask','Enviar correo (GUI)',1420,300,170,75,s),
        ('a_end','endEvent','Fin de demo',1690,319,36,36,s),
    ],[
        ('af1','a_start','a_ocr','',[(176,158),(205,158),(205,338),(240,338)]),
        ('af2','a_ocr','a_rules','',[(385,338),(450,338)]),
        ('af3','a_rules','a_gate','',[(595,338),(660,338)]),
        ('af4','a_gate','a_merge','Autoaprobación',[(710,337),(1040,337)]),
        ('af5','a_gate','a_approval','Excepción',[(685,362),(685,532),(780,532)]),
        ('af6','a_approval','a_decision','',[(955,532),(1010,532)]),
        ('af6a','a_decision','a_merge','Sí',[(1035,507),(1035,422),(1065,422),(1065,362)]),
        ('af6b','a_decision','a_rejected','No',[(1060,532),(1190,532)]),
        ('af7','a_merge','a_excel','',[(1090,337),(1165,337)]),
        ('af8','a_excel','a_mail','',[(1345,337),(1420,337)]),
        ('af9','a_mail','a_end','',[(1590,337),(1690,337)]),
    ])

if __name__=='__main__': main()
