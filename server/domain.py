"""Business validation shared by API, migrations and backup import.
Amounts are integer centavos; cross-record rules run against the complete
transactional candidate, never against the caller's filtered view.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import math
import re
from zoneinfo import ZoneInfo

CORE_KINDS = ('clients', 'deals', 'proposals', 'projects', 'tasks', 'contracts', 'entries', 'activities')
BOS_KINDS = ('strategies','goals','kpis','contents','campaigns','approvals','requests','handoffs','meetings','decisions','knowledge','processes','incidents','automations','integrations','domains','hosting','developments','bugs','deployments','change_requests','files','comments','notifications','time_entries','checklists')
KINDS = CORE_KINDS + BOS_KINDS
MAX_CENTS = 1_000_000_000_000
MAX_RECORDS = 10000
LABELS = dict(zip(CORE_KINDS, ('Cliente', 'Oportunidade', 'Proposta', 'Projeto', 'Tarefa', 'Recorrência', 'Lançamento', 'Interação')))
LABELS.update({'strategies':'Estratégia','goals':'Meta','kpis':'KPI','contents':'Conteúdo','campaigns':'Campanha','approvals':'Aprovação','requests':'Solicitação','handoffs':'Handoff','meetings':'Reunião','decisions':'Decisão','knowledge':'Artigo','processes':'Processo','incidents':'Incidente','automations':'Automação','integrations':'Integração','domains':'Domínio','hosting':'Hospedagem','developments':'Desenvolvimento','bugs':'Bug','deployments':'Deploy','change_requests':'Solicitação de alteração','files':'Arquivo','comments':'Comentário','notifications':'Notificação','time_entries':'Apontamento','checklists':'Checklist'})
SERVICES = {'marketing', 'dev', 'hybrid', 'other'}
READ = {
 'admin': set(KINDS),
 'sales': {'clients','deals','proposals','projects','tasks','activities','strategies','goals','kpis','contents','campaigns','approvals','requests','handoffs','meetings','decisions','knowledge','processes','files','comments','notifications','checklists'},
 'operations': {'clients','projects','tasks','activities','strategies','goals','kpis','contents','campaigns','approvals','requests','handoffs','meetings','decisions','knowledge','processes','incidents','automations','integrations','domains','hosting','developments','bugs','deployments','change_requests','files','comments','notifications','time_entries','checklists'},
 'finance': {'clients','projects','contracts','entries','activities','approvals','requests','meetings','decisions','files','comments','notifications','time_entries'},
 'client': {'clients','projects','tasks','contents','campaigns','approvals','requests','meetings','files','comments','notifications'},
}
WRITE = {
 'admin': set(KINDS),
 'sales': {'clients','deals','proposals','projects','tasks','activities','strategies','goals','kpis','contents','campaigns','approvals','requests','handoffs','meetings','decisions','knowledge','processes','files','comments','notifications','checklists'},
 'operations': {'projects','tasks','activities','strategies','goals','kpis','contents','campaigns','approvals','requests','handoffs','meetings','decisions','knowledge','processes','incidents','automations','integrations','domains','hosting','developments','bugs','deployments','change_requests','files','comments','notifications','time_entries','checklists'},
 'finance': {'contracts','entries','activities','approvals','requests','meetings','decisions','files','comments','notifications','time_entries'},
 'client': {'approvals','requests','files','comments'},
}
ROLE_LABELS = {'admin':'Administrador','sales':'Comercial','operations':'Operação','finance':'Financeiro','client':'Cliente'}
TEXT = {
 'clients':['name','contact','email','phone','document','segment','source','owner','notes','website'],
 'deals':['clientId','title','owner','nextAction','lossReason','notes'],
 'proposals':['clientId','dealId','code','title','payment','scope','exclusions','delivery','notes'],
 'projects':['clientId','dealId','title','owner','url','description'],
 'tasks':['clientId','projectId','dealId','title','owner','notes'],
 'entries':['clientId','projectId','contractId','description','category','notes'],
 'contracts':['clientId','title','owner','scope'],
 'activities':['clientId','text'],
}
EXTRA = {
 'clients': {'status','tags','health','nextAction','nextDate'},
 'deals': {'stage','service','billing','valueCents','expectedClose','nextDate','closedAt'},
 'proposals': {'status','service','validUntil','discountCents','items'},
 'projects': {'status','service','budgetCents','startDate','dueDate','priority','nextAction'},
 'tasks': {'status','priority','dueDate','doneAt','estimatedHours','spentHours','nextAction','blockedReason','blockedBy','blockedSince','approver','participants','dependsOn','progress','flowX','flowY'},
 'entries': {'status','type','service','method','valueCents','dueDate','paidDate','competence'},
 'contracts': {'status','service','amountCents','startDate','endDate','dueDay'},
 'activities': {'kind','date','visibility'},
}
BOS_TEXT_FIELDS = ['title','clientId','projectId','owner','description','nextAction','category','relatedType','relatedId']
BOS_EXTRA_FIELDS = {'status','priority','dueDate','startDate','tags','data','visibility'}
for _kind in BOS_KINDS:
    TEXT[_kind] = list(BOS_TEXT_FIELDS)
    EXTRA[_kind] = set(BOS_EXTRA_FIELDS)
# File metadata is still stored as a record; bytes live outside the database.
EXTRA['files'] |= {'originalName','storageKey','mimeType','size','version'}
EXTRA['time_entries'] |= {'hours','date'}
BASE = {'id','createdAt','updatedAt','_rev'}
ID_RE = re.compile(r'^[-_a-zA-Z0-9]{1,80}$')
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

class Invalid(ValueError):
    pass

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def today() -> str:
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()

def blank(company='Sua agência') -> dict:
    stamp=now()
    return {'schema':1,'version':'3.0.0','meta':{'createdAt':stamp,'updatedAt':stamp,'lastBackup':'','revision':0,'changeId':'initial','demo':False,'onboarded':True},
       'settings':{'company':company,'owner':'Minha operação','email':'','phone':'','document':'','city':'','brandColor':'#111111','monthlyGoalCents':0,'team':[]}, **{k:[] for k in KINDS}}

def string(v, label, limit=6000, required=False):
    if not isinstance(v,str) or len(v)>limit or (required and not v.strip()):
        raise Invalid(f'{label}: texto obrigatório, inválido ou extenso demais.')

def cents(v,label,positive=False):
    if type(v) is not int or v < (1 if positive else 0) or v>MAX_CENTS:
        raise Invalid(f'{label}: informe um valor válido em centavos inteiros.')

def enum(v,values,label):
    if not isinstance(v,str) or v not in values:
        raise Invalid(f'{label}: opção inválida.')

def check_date(v,label,required=False):
    if v=='' and not required: return
    try:
        if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v) or not ('1900-01-01'<=v<='2199-12-31'):
            raise ValueError()
        date.fromisoformat(v)
    except (ValueError,TypeError):
        raise Invalid(f'{label}: data inválida.') from None

def subtotal(p):
    return sum(int((Decimal(str(i['quantity']))*i['unitCents']).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) for i in p['items'])

def no_secret_fields(value,depth=0):
    if depth>20: raise Invalid('Estrutura de dados profunda demais.')
    if isinstance(value,dict):
        for key,val in value.items():
            normalized=re.sub(r'[^a-z]','',str(key).lower())
            if any(word in normalized for word in ('password','passwd','secret','accesstoken','refreshtoken','apikey','privatekey')):
                raise Invalid('Não armazene senhas, tokens ou chaves secretas em campos do CRM. Use um cofre de segredos.')
            no_secret_fields(val,depth+1)
    elif isinstance(value,list):
        for item in value:no_secret_fields(item,depth+1)

def no_dangerous_keys(value,depth=0):
    if depth>20: raise Invalid('Estrutura de dados profunda demais.')
    if isinstance(value,dict):
        if {'__proto__','constructor','prototype'} & value.keys():
            raise Invalid('Propriedade não permitida.')
        for v in value.values(): no_dangerous_keys(v,depth+1)
    elif isinstance(value,list):
        for v in value: no_dangerous_keys(v,depth+1)

def validate(data:dict) -> dict:
    no_dangerous_keys(data)
    if not isinstance(data,dict) or type(data.get('schema')) is not int or data.get('schema')!=1:
        raise Invalid('Backup incompatível: esperado Nexo CRM schema 1.')
    if not isinstance(data.get('meta'),dict): raise Invalid('Metadados ausentes ou inválidos.')
    for key in ('demo','onboarded'):
        if type(data['meta'].get(key)) is not bool: raise Invalid('Metadado booleano inválido.')
    s=data.get('settings')
    if not isinstance(s,dict): raise Invalid('Configurações ausentes.')
    if set(s) != {'company','owner','email','phone','document','city','brandColor','monthlyGoalCents','team'}:
        raise Invalid('Campos de configuração incompatíveis.')
    for key in ['company','owner','email','phone','document','city','brandColor']:
        string(s.get(key),f'Configuração {key}',300,key=='company')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',s['brandColor']): raise Invalid('Cor inválida.')
    cents(s.get('monthlyGoalCents'),'Meta mensal')
    if not isinstance(s.get('team'),list) or len(s['team'])>60: raise Invalid('Lista de responsáveis inválida.')
    for name in s['team']: string(name,'Responsável',100,True)
    by_kind={}; all_ids=set(); current=today()
    for kind in KINDS:
        records=data.get(kind)
        if not isinstance(records,list) or len(records)>MAX_RECORDS:
            raise Invalid(f'{LABELS[kind]}: máximo de {MAX_RECORDS} registros.')
        by_kind[kind]={}
        for r in records:
            if not isinstance(r,dict) or not isinstance(r.get('id'),str) or not ID_RE.fullmatch(r['id']) or r['id'] in all_ids:
                raise Invalid(f'{LABELS[kind]}: identificador inválido ou duplicado.')
            if set(r) - (set(TEXT[kind])|EXTRA[kind]|BASE):
                raise Invalid(f'{LABELS[kind]}: campo não reconhecido.')
            all_ids.add(r['id']); by_kind[kind][r['id']]=r
            for key in TEXT[kind]: string(r.get(key),f'{LABELS[kind]} / {key}')
            for key in ['createdAt','updatedAt']:
                string(r.get(key),'Data do registro',100,True)
                try: datetime.fromisoformat(r[key].replace('Z','+00:00'))
                except ValueError: raise Invalid('Data de criação ou atualização inválida.') from None
            if kind=='clients':
                string(r['name'],'Nome do cliente',300,True)
                enum(r.get('status'),{'lead','active','inactive'},'Situação do cliente')
                if not isinstance(r.get('tags'),list) or len(r['tags'])>30: raise Invalid('Tags inválidas.')
                for t in r['tags']: string(t,'Tag',100)
                if r['email'] and not EMAIL_RE.fullmatch(r['email']): raise Invalid('E-mail do cliente inválido.')
                check_url(r['website'],'Site do cliente')
                if 'health' in r: enum(r.get('health'),{'healthy','attention','risk'},'Saúde do cliente')
                if 'nextAction' in r: string(r.get('nextAction'),'Próxima ação do cliente',600)
                if 'nextDate' in r: check_date(r.get('nextDate'),'Próxima ação do cliente')
            elif kind=='deals':
                enum(r.get('stage'),{'new','discovery','proposal','negotiation','won','lost'},'Etapa')
                enum(r.get('billing'),{'project','monthly','hourly'},'Contratação')
                cents(r.get('valueCents'),'Valor comercial')
                for k in ['expectedClose','nextDate','closedAt']: check_date(r.get(k),k)
                if r['stage'] in {'won','lost'}:
                    if not r['closedAt'] or r['closedAt']>current: raise Invalid('Fechamento obrigatório e não pode estar no futuro.')
                elif not r['nextDate'] or not r['nextAction'].strip(): raise Invalid('Oportunidade aberta precisa de próxima ação e data.')
                if r['stage']=='lost' and not r['lossReason'].strip(): raise Invalid('Informe o motivo da perda.')
            elif kind=='proposals':
                enum(r.get('status'),{'draft','sent','accepted','rejected'},'Situação da proposta')
                check_date(r.get('validUntil'),'Validade',True)
                cents(r.get('discountCents'),'Desconto')
                string(r.get('code'),'Número da proposta',80,True)
                if not isinstance(r.get('items'),list) or not 1<=len(r['items'])<=100: raise Invalid('A proposta precisa de 1 a 100 itens.')
                for item in r['items']:
                    if not isinstance(item,dict) or set(item)!={'description','quantity','unitCents'}: raise Invalid('Item inválido.')
                    string(item.get('description'),'Descrição do item',600,True)
                    q=item.get('quantity')
                    if type(q) not in (int,float) or not math.isfinite(q) or not 0<q<=1000000: raise Invalid('Quantidade inválida.')
                    cents(item.get('unitCents'),'Preço unitário')
                total=subtotal(r)
                if total>MAX_CENTS or r['discountCents']>total: raise Invalid('Total inválido ou desconto acima do subtotal.')
            elif kind=='projects':
                enum(r.get('status'),{'planning','running','approval','paused','done','cancelled'},'Situação do projeto')
                if 'priority' in r: enum(r.get('priority'),{'low','normal','high','urgent'},'Prioridade do projeto')
                if 'nextAction' in r: string(r.get('nextAction'),'Próxima ação do projeto',600)
                cents(r.get('budgetCents'),'Valor do projeto')
                check_date(r.get('startDate'),'Início',True); check_date(r.get('dueDate'),'Entrega',True)
                if r['dueDate']<r['startDate']: raise Invalid('A entrega não pode ser anterior ao início.')
                check_url(r['url'],'Link do projeto')
            elif kind=='tasks':
                enum(r.get('status'),{'todo','planned','doing','review','approval','waiting_client','blocked','done','cancelled'},'Situação da tarefa')
                enum(r.get('priority'),{'low','normal','high','urgent'},'Prioridade')
                for key,label in [('nextAction','Próxima ação'),('blockedReason','Motivo do bloqueio'),('blockedBy','Responsável por desbloquear'),('approver','Aprovador')]:
                    if key in r: string(r.get(key),label,600)
                if 'blockedSince' in r: check_date(r.get('blockedSince'),'Data do bloqueio')
                if 'participants' in r:
                    if not isinstance(r['participants'],list) or len(r['participants'])>60: raise Invalid('Participantes da tarefa inválidos.')
                    for name in r['participants']: string(name,'Participante',100,True)
                if 'dependsOn' in r:
                    if not isinstance(r['dependsOn'],list) or len(r['dependsOn'])>100 or len(set(r['dependsOn']))!=len(r['dependsOn']): raise Invalid('Dependências da tarefa inválidas.')
                    for ident in r['dependsOn']:
                        if not isinstance(ident,str) or not ID_RE.fullmatch(ident): raise Invalid('Dependência da tarefa inválida.')
                if 'progress' in r and (type(r['progress']) is not int or not 0<=r['progress']<=100): raise Invalid('Progresso da tarefa inválido.')
                for key in ['flowX','flowY']:
                    if key in r and (type(r[key]) not in (int,float) or not math.isfinite(r[key]) or not -10000<=r[key]<=10000): raise Invalid('Posição do Flow Map inválida.')
                if r['status']=='blocked':
                    if not r.get('blockedReason','').strip(): raise Invalid('Tarefa bloqueada precisa informar o motivo do bloqueio.')
                    if not r.get('blockedBy','').strip() and not r.get('dependsOn'): raise Invalid('Tarefa bloqueada precisa indicar quem ou o que pode desbloqueá-la.')
                check_date(r.get('dueDate'),'Prazo',True); check_date(r.get('doneAt'),'Conclusão',r['status']=='done')
                if r.get('doneAt') and r['doneAt']>current: raise Invalid('Conclusão no futuro não permitida.')
                for k in ['estimatedHours','spentHours']:
                    v=r.get(k)
                    if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100000: raise Invalid('Horas inválidas.')
            elif kind=='entries':
                enum(r.get('status'),{'open','paid','cancelled'},'Situação financeira')
                enum(r.get('type'),{'income','expense'},'Tipo financeiro')
                enum(r.get('method'),{'pix','transfer','boleto','card','cash','other'},'Forma de pagamento')
                cents(r.get('valueCents'),'Valor financeiro',True)
                check_date(r.get('dueDate'),'Vencimento',True);check_date(r.get('paidDate'),'Liquidação',r['status']=='paid')
                if r['status']=='paid' and r['paidDate']>current: raise Invalid('Liquidação no futuro não permitida.')
                if not isinstance(r.get('competence'),str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',r['competence']): raise Invalid('Competência inválida.')
                if not '1900-01'<=r['competence']<='2199-12': raise Invalid('Competência fora do intervalo.')
                if r['contractId'] and r['type']!='income': raise Invalid('Mensalidade deve ser receita.')
            elif kind=='contracts':
                enum(r.get('status'),{'active','paused','cancelled'},'Situação da recorrência')
                cents(r.get('amountCents'),'Mensalidade',True)
                check_date(r.get('startDate'),'Início',True);check_date(r.get('endDate'),'Fim')
                if r['endDate'] and r['endDate']<r['startDate']: raise Invalid('Fim anterior ao início.')
                if type(r.get('dueDay')) is not int or not 1<=r['dueDay']<=31: raise Invalid('Dia de vencimento inválido.')
            elif kind=='activities':
                enum(r.get('kind'),{'note','call','meeting','email','whatsapp'},'Tipo de interação')
                enum(r.get('visibility','shared'),{'shared','commercial','finance','private'},'Visibilidade')
                check_date(r.get('date'),'Data da interação',True)
                string(r['text'],'Descrição da interação',6000,True)
            elif kind in BOS_KINDS:
                string(r.get('title'),f'{LABELS[kind]} / título',600,True)
                for key in ('description','nextAction','category','owner','relatedType','relatedId'):
                    string(r.get(key,''),f'{LABELS[kind]} / {key}',6000 if key=='description' else 600)
                enum(r.get('status','planned'),{'planned','todo','doing','review','approval','waiting_client','blocked','active','paused','done','cancelled','draft','sent','approved','rejected','open','resolved','online','degraded','offline'},'Status')
                enum(r.get('priority','normal'),{'low','normal','high','urgent','critical'},'Prioridade')
                check_date(r.get('dueDate',''),'Prazo'); check_date(r.get('startDate',''),'Início')
                if not isinstance(r.get('tags',[]),list) or len(r.get('tags',[]))>50: raise Invalid('Tags inválidas.')
                for tag in r.get('tags',[]): string(tag,'Tag',100,True)
                if not isinstance(r.get('data',{}),dict): raise Invalid('Dados estruturados inválidos.')
                no_dangerous_keys(r.get('data',{})); no_secret_fields(r.get('data',{}))
                enum(r.get('visibility','internal'),{'internal','partners','project','client','private'},'Visibilidade')
                if kind=='files':
                    for key in ('originalName','storageKey','mimeType'): string(r.get(key,''),f'Arquivo / {key}',600)
                    if type(r.get('size',0)) is not int or not 0<=r.get('size',0)<=16*1024*1024: raise Invalid('Tamanho de arquivo inválido.')
                    if type(r.get('version',1)) is not int or not 1<=r.get('version',1)<=10000: raise Invalid('Versão de arquivo inválida.')
                if kind=='time_entries':
                    h=r.get('hours',0)
                    if type(h) not in (int,float) or not math.isfinite(h) or not 0<h<=24: raise Invalid('Horas do apontamento inválidas.')
                    check_date(r.get('date',''),'Data do apontamento',True)
            if kind in {'deals','proposals','projects','entries','contracts'}: enum(r.get('service'),SERVICES,'Serviço')
            if kind not in {'clients','activities'}: string(r.get('title') or r.get('description'),'Título',6000,True)
    codes=set(); bills=set()
    for kind, records in by_kind.items():
        for r in records.values():
            for key,ref in [('clientId','clients'),('dealId','deals'),('projectId','projects'),('contractId','contracts')]:
                if r.get(key) and r[key] not in by_kind[ref]: raise Invalid(f'{LABELS[kind]}: vínculo inexistente ({key}). Exclua ou desvincule os registros dependentes antes.')
                if ref!='clients' and r.get(key) and by_kind[ref][r[key]]['clientId']!=r.get('clientId'):
                    raise Invalid('O cliente deve corresponder ao registro vinculado.')
            if kind in {'deals','proposals','projects','contracts','activities'} and not r.get('clientId'):
                raise Invalid(f'{LABELS[kind]} precisa de um cliente.')
            if kind=='proposals':
                if r['code'].casefold() in codes: raise Invalid('Número de proposta duplicado.')
                codes.add(r['code'].casefold())
            if kind=='entries' and r['contractId']:
                key=(r['contractId'],r['competence'])
                if key in bills: raise Invalid('Mensalidade duplicada para o mesmo contrato e competência.')
                bills.add(key)
            if kind=='tasks':
                for dependency_id in r.get('dependsOn',[]):
                    dependency=by_kind['tasks'].get(dependency_id)
                    if not dependency: raise Invalid('Tarefa: dependência inexistente.')
                    if dependency_id==r['id']: raise Invalid('Uma tarefa não pode depender dela mesma.')
                    if r.get('projectId') and dependency.get('projectId')!=r.get('projectId'):
                        raise Invalid('Dependências devem pertencer ao mesmo projeto.')
                    if r.get('clientId') and dependency.get('clientId')!=r.get('clientId'):
                        raise Invalid('Dependências devem pertencer ao mesmo cliente.')
    visiting=set();visited=set()
    def visit_task(ident):
        if ident in visited:return
        if ident in visiting: raise Invalid('Dependências de tarefas não podem formar um ciclo.')
        visiting.add(ident)
        for dep in by_kind['tasks'][ident].get('dependsOn',[]): visit_task(dep)
        visiting.remove(ident);visited.add(ident)
    for ident in by_kind['tasks']: visit_task(ident)
    return data

def check_url(v,label):
    if v and not re.match(r'^https?://[^\s]+$',v,re.I):
        raise Invalid(f'{label}: use um endereço http:// ou https:// completo.')

def filtered(data,role):
    out=deepcopy(data)
    for k in KINDS:
        if k not in READ[role]: out[k]=[]
    allowed={'admin':{'shared','finance','commercial','private'},'sales':{'shared','commercial'},'operations':{'shared'},'finance':{'shared','finance'},'client':set()}[role]
    out['activities']=[a for a in out['activities'] if a.get('visibility','shared') in allowed]
    if role!='admin':
        out['settings']['monthlyGoalCents']=0
    if role in {'operations','finance'}:
        for p in out['projects']:
            p['dealId']=''
            if role=='operations': p['budgetCents']=0
        for t in out['tasks']: t['dealId']=''
    return out
