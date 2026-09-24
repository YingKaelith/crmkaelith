from pathlib import Path
import sys,secrets
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from server.app import create_app,Config
from server import domain as D

ORIGIN='http://testserver'
PASSWORD='Senha exclusiva apenas para testes!'
TOKEN='codigo-de-instalacao-exclusivo-dos-testes'

@pytest.fixture
def env(tmp_path):
    app=create_app(Config('sqlite:///'+str(tmp_path/'test.db'),ORIGIN,TOKEN,False,tmp_path))
    admin=TestClient(app,base_url=ORIGIN,headers={'Origin':ORIGIN})
    response=admin.post('/api/setup',json={'token':TOKEN,'email':'admin@example.com','name':'Admin de testes','company':'Empresa fictícia','password':PASSWORD})
    assert response.status_code==200,response.text
    packet=response.json();admin.headers['X-CSRF-Token']=packet['csrf']
    yield {'app':app,'admin':admin,'user':packet['user'],'dir':tmp_path}
    admin.close();app.state.engine.dispose()

def make_record(kind,**override):
    stamp=D.now();day=D.today()
    common={'id':secrets.token_hex(12),'createdAt':stamp,'updatedAt':stamp}
    defaults={
     'clients':dict(name='Cliente fictício',contact='Contato de teste',email='',phone='',document='',segment='',source='Indicação',owner='Admin de testes',notes='',website='',status='lead',tags=[]),
     'deals':dict(clientId='',title='Projeto de site',owner='Admin de testes',nextAction='Conversar',lossReason='',notes='',stage='new',service='dev',billing='project',valueCents=100000,expectedClose=day,nextDate=day,closedAt=''),
     'proposals':dict(clientId='',dealId='',code='PROP-'+secrets.token_hex(4),title='Proposta de site',payment='',scope='Site institucional',exclusions='',delivery='',notes='',status='draft',service='dev',validUntil=day,discountCents=0,items=[{'description':'Desenvolvimento','quantity':1,'unitCents':100000}]),
     'projects':dict(clientId='',dealId='',title='Projeto de site',owner='Admin de testes',url='',description='Escopo de teste',status='planning',service='dev',budgetCents=100000,startDate=day,dueDate=day),
     'tasks':dict(clientId='',projectId='',dealId='',title='Desenvolvimento',owner='Admin de testes',notes='',status='todo',priority='normal',dueDate=day,doneAt='',estimatedHours=2.5,spentHours=0),
     'contracts':dict(clientId='',title='Marketing mensal',owner='Admin de testes',scope='',status='active',service='marketing',amountCents=150000,startDate=day,endDate='',dueDay=31),
     'entries':dict(clientId='',projectId='',contractId='',description='Receita de teste',category='Serviços',notes='',status='open',type='income',service='dev',method='pix',valueCents=100000,dueDate=day,paidDate='',competence=day[:7]),
     'activities':dict(clientId='',text='Observação de teste',kind='note',date=day),
    }
    return common|defaults[kind]|override

def up(kind,record,expected=None):
    return {'kind':kind,'record':record,'expectedRevision':record.get('_rev',0) if expected is None else expected}

def tx(client,upserts=None,deletes=None,**extra):
    return client.post('/api/transactions',json={'requestId':secrets.token_hex(12),'upserts':upserts or [],'deletes':deletes or [],**extra})

def data(client):
    response=client.get('/api/state');assert response.status_code==200,response.text
    return response.json()['data']

def new_role(env,role,name=None):
    admin=env['admin'];email=role+'-'+secrets.token_hex(3)+'@example.com'
    response=admin.post('/api/users',json={'name':name or role,'email':email,'role':role});assert response.status_code==200,response.text
    user=response.json()['user'];token=response.json()['activationToken']
    account=TestClient(env['app'],base_url=ORIGIN,headers={'Origin':ORIGIN})
    r=account.post('/api/password/reset',json={'token':token,'password':PASSWORD});assert r.status_code==200,r.text
    r=account.post('/api/login',json={'email':email,'password':PASSWORD});assert r.status_code==200,r.text
    account.headers['X-CSRF-Token']=r.json()['csrf']
    return account,user
