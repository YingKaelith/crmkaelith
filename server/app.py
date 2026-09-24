"""Nexo CRM Equipe — same-origin HTTP API and static application.
Single-company deployment. The API, not the browser, is the trust boundary.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import time
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import select, insert, update, delete, func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import domain as D
from .database import metadata, make_engine, workspace, users, user_scopes, sessions, resets, records, audit, idempotency, rate_limits

log=logging.getLogger('nexo')
ROOT=Path(__file__).resolve().parent.parent
PASSWORD_HASHER=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
DUMMY_HASH=PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
MAX_BODY=16*1024*1024

@dataclass
class Config:
    database_url: str
    public_origin: str='http://127.0.0.1:8765'
    setup_token: str=''
    production: bool=False
    data_dir: Path=ROOT/'data'
    session_hours: int=8
    backup_mode: str='local'

    @classmethod
    def environment(cls):
        data=Path(os.environ.get('NEXO_DATA_DIR',ROOT/'data')).resolve()
        data.mkdir(parents=True,exist_ok=True,mode=0o700)
        try:data.chmod(0o700)
        except OSError:log.warning("Confira as permissões da pasta de dados.")
        prod=os.environ.get('NEXO_ENV','development')=='production'
        url=os.environ.get('DATABASE_URL',f'sqlite:///{data / "nexo.db"}')
        origin=(os.environ.get('NEXO_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL') or 'http://127.0.0.1:8765').rstrip('/')
        from urllib.parse import urlsplit
        parsed=urlsplit(origin)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise RuntimeError('NEXO_ORIGIN deve ser uma origem sem caminho, consulta ou credenciais, como https://crm.exemplo.com.')
        token=os.environ.get('NEXO_SETUP_TOKEN','')
        if not prod and not token:
            token_file=data/'setup-token.txt'
            if token_file.exists(): token=token_file.read_text().strip()
            else:
                token=secrets.token_urlsafe(32)
                fd=os.open(token_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f: f.write(token+'\n')
        if len(token)<24 or token.startswith('SUBSTITUIR'):
            raise RuntimeError('Defina NEXO_SETUP_TOKEN com pelo menos 24 caracteres aleatórios.')
        if prod and (not origin.startswith('https://') or not url.startswith(('postgres://','postgresql://','postgresql+psycopg://'))):
            raise RuntimeError('Produção exige NEXO_ORIGIN=https://... e DATABASE_URL PostgreSQL. Use o modo de desenvolvimento somente em loopback.')
        mode=os.environ.get('NEXO_BACKUP_MODE','local')
        if mode not in {'local','managed'}:raise RuntimeError('NEXO_BACKUP_MODE deve ser local ou managed.')
        return cls(url,origin,token,prod,data,backup_mode=mode)

def digest(s:str): return hashlib.sha256(s.encode()).hexdigest()

def fail(code,message,**extra):
    raise HTTPException(code,detail={'message':message,**extra})

def public_user(row):
    return {k:row[k] for k in ['id','name','email','role','active','created_at','updated_at']}

def client_scope(conn,user_id):
    row=conn.execute(select(user_scopes.c.client_id).where(user_scopes.c.user_id==user_id)).first()
    return row[0] if row else ''

def validate_password(value):
    if not isinstance(value,str) or not 12<=len(value)<=128:
        fail(422,'A senha deve ter entre 12 e 128 caracteres. Use uma frase longa e exclusiva.')
    if len(set(value))<5: fail(422,'Use uma senha menos repetitiva.')

def verify_password(stored,password):
    try: return PASSWORD_HASHER.verify(stored,password)
    except (VerifyMismatchError, InvalidHashError, VerificationError): return False

def validate_email(value):
    if not isinstance(value,str) or len(value)>254 or not D.EMAIL_RE.fullmatch(value.strip()):
        fail(422,'Informe um e-mail válido.')
    return value.strip().lower()

class BodyLimitMiddleware:
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[])); length=headers.get(b'content-length',b'0')
        try: too_large=int(length)>MAX_BODY
        except ValueError: too_large=True
        if too_large:
            return await JSONResponse({'message':'Requisição acima de 16 MB.'},status_code=413)(scope,receive,send)
        # Buffer with an enforced streaming limit, including chunked requests.
        messages=[]; total=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            total+=len(message.get('body',b''))
            if total>MAX_BODY:
                return await JSONResponse({'message':'Requisição acima de 16 MB.'},status_code=413)(scope,receive,send)
            messages.append(message)
            if not message.get('more_body'): break
        index=0
        async def replay():
            nonlocal index
            if index<len(messages):
                item=messages[index];index+=1;return item
            return await receive()
        await self.app(scope,replay,send)

def create_app(config:Config|None=None):
    c=config or Config.environment()
    c.data_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:c.data_dir.chmod(0o700)
    except OSError:log.warning("Confira as permissões da pasta de dados.")
    engine=make_engine(c.database_url)
    metadata.create_all(engine)
    with engine.begin() as conn:
        if not conn.execute(select(workspace.c.id)).first():
            b=D.blank()
            conn.execute(insert(workspace).values(id=1,revision=0,schema_version=1,settings=b['settings'],meta=b['meta']))
        version=conn.execute(select(workspace.c.schema_version)).scalar_one()
        if version!=1: raise RuntimeError('Versão de banco incompatível. Consulte as migrações.')
    app=FastAPI(title='Nexo CRM Equipe',version='3.0.0',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.config=c;app.state.engine=engine
    from urllib.parse import urlsplit
    host=urlsplit(c.public_origin).hostname
    if not host: raise RuntimeError('NEXO_ORIGIN inválida.')
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=[host],www_redirect=False)
    cookie_name='__Host-nexo' if c.production else 'nexo_session'

    @app.middleware('http')
    async def security_headers(request:Request,call_next):
        # All unsafe operations require exact same-origin, including login/setup.
        if request.method not in {'GET','HEAD','OPTIONS'} and request.headers.get('origin')!=c.public_origin:
            response=JSONResponse({'message':'Origem da requisição não autorizada.'},status_code=403)
        else:
            try: response=await call_next(request)
            except Exception:
                log.exception('Erro interno não tratado')
                response=JSONResponse({'message':'Erro interno. Nenhuma confirmação de gravação foi emitida.'},status_code=500)
        response.headers.update({
            'Cache-Control':'no-store',
            'X-Content-Type-Options':'nosniff',
            'X-Frame-Options':'DENY',
            'Referrer-Policy':'no-referrer',
            'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        })
        if c.production: response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        content=exc.detail if isinstance(exc.detail,dict) else {'message':str(exc.detail)}
        return JSONResponse(content,status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request,exc):
        return JSONResponse({'message':'Requisição inválida. Confira os campos e o formato JSON.'},status_code=422)

    @app.exception_handler(D.Invalid)
    async def validation_error(request,exc): return JSONResponse({'message':str(exc)},status_code=422)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request,exc):
        return JSONResponse({'message':'Registro ou identificador já existente; atualize e tente novamente.'},status_code=409)

    @app.exception_handler(OperationalError)
    async def database_error(request,exc):
        log.error('Falha de disponibilidade/transação no banco: %s',type(exc).__name__)
        return JSONResponse({'message':'Banco temporariamente ocupado ou indisponível. Tente novamente; não repita uma cobrança sem conferir o resultado.'},status_code=503)

    @contextmanager
    def transaction(write=False):
        with engine.begin() as conn:
            if write:
                # Lock the single-company aggregate before reading or validating it.
                # This is a DB lock, also effective across worker processes on Postgres.
                conn.execute(update(workspace).where(workspace.c.id==1).values(revision=workspace.c.revision))
            elif engine.dialect.name=='postgresql':
                conn.execute(select(workspace.c.id).where(workspace.c.id==1).with_for_update(read=True))
            yield conn

    def load_data(conn):
        w=conn.execute(select(workspace).where(workspace.c.id==1)).mappings().one()
        data=D.blank();data['settings']=deepcopy(w['settings']);data['meta']=deepcopy(w['meta']);data['meta']['revision']=w['revision']
        for row in conn.execute(select(records).order_by(records.c.kind,records.c.id)).mappings():
            r=deepcopy(row['data']);r['_rev']=row['revision'];data[row['kind']].append(r)
        return data

    def log_event(conn,user,action,kind='',record_id='',details=None):
        conn.execute(insert(audit).values(time=D.now(),actor_id=user.get('id','system'),actor=user.get('email','system'),action=action,kind=kind,record_id=record_id,details=details or {}))

    def principal(conn,request:Request,csrf=False,allow_missing=False):
        token=request.cookies.get(cookie_name,'')
        if not token:
            if allow_missing:return None,None
            fail(401,'Entre na sua conta para continuar.')
        row=conn.execute(select(sessions).where(sessions.c.token_hash==digest(token))).mappings().first()
        now=int(time.time())
        if not row or row['expires']<=now or row['last_seen']<now-2*3600:
            fail(401,'Sua sessão expirou. Entre novamente; textos não salvos não foram gravados.')
        user=conn.execute(select(users).where(users.c.id==row['user_id'],users.c.active==True)).mappings().first()
        if not user:fail(401,'Esta conta não está ativa.')
        if csrf and not hmac.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']):
            fail(403,'Token de proteção inválido. Atualize a sessão.')
        return dict(user),dict(row)

    def require_admin(user):
        if user['role']!='admin':fail(403,'Esta ação é exclusiva de administradores.')

    def new_session(conn,user,response):
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);now=int(time.time())
        conn.execute(delete(sessions).where(sessions.c.expires<now))
        conn.execute(insert(sessions).values(token_hash=digest(token),user_id=user['id'],csrf=csrf,created=now,expires=now+c.session_hours*3600,last_seen=now))
        response.set_cookie(cookie_name,token,max_age=c.session_hours*3600,httponly=True,secure=c.production,samesite='strict',path='/')
        return csrf

    def data_for_user(conn,data,user):
        d=D.filtered(data,user['role'])
        if user['role']=='client':
            scope=client_scope(conn,user['id'])
            for kind in D.KINDS:
                if kind=='clients': d[kind]=[r for r in d[kind] if r['id']==scope]
                elif kind in D.READ['client']:
                    d[kind]=[r for r in d[kind] if r.get('clientId')==scope and (kind not in {'files','comments','notifications'} or r.get('visibility')=='client')]
                else:d[kind]=[]
            d['settings']['monthlyGoalCents']=0
        return d

    def envelope(conn,user,csrf=None):
        d=data_for_user(conn,load_data(conn),user)
        pu=public_user(user)
        if user['role']=='client':pu['clientId']=client_scope(conn,user['id'])
        payload={'user':pu,'data':d,'permissions':{'read':sorted(D.READ[user['role']]),'write':sorted(D.WRITE[user['role']]),'admin':user['role']=='admin'},'serverDate':D.today()}
        if csrf:payload['csrf']=csrf
        return payload

    def rate_check(request,email=''):
        # Limits are persisted centrally; X-Forwarded-For is not trusted by the app.
        ip=request.client.host if request.client else 'unknown';now=int(time.time())
        blocked=False
        with transaction(True) as conn:
            for key,max_count in [('ip:'+digest(ip),40),('account:'+digest(email or ip),12)]:
                row=conn.execute(select(rate_limits).where(rate_limits.c.id==key)).mappings().first()
                count=row['count']+1 if row and row['window']>now-900 else 1
                window=row['window'] if row and row['window']>now-900 else now
                if row:conn.execute(update(rate_limits).where(rate_limits.c.id==key).values(count=count,window=window))
                else:conn.execute(insert(rate_limits).values(id=key,count=count,window=window))
                blocked=blocked or count>max_count
            conn.execute(delete(rate_limits).where(rate_limits.c.window<now-86400))
        if blocked:fail(429,'Muitas tentativas. Aguarde 15 minutos antes de tentar novamente.')

    def auth_body(body):
        if not isinstance(body,dict):fail(422,'Corpo JSON inválido.')
        D.no_dangerous_keys(body)
        return body

    @app.get('/api/health')
    def health():
        with engine.connect() as conn:conn.execute(select(workspace.c.id)).first()
        return {'status':'ok','version':'3.0.0'}

    @app.get('/api/bootstrap')
    def bootstrap():
        with transaction() as conn: needed=conn.execute(select(func.count()).select_from(users)).scalar_one()==0
        return {'setupRequired':needed,'version':'3.0.0'}

    @app.post('/api/setup')
    def setup(request:Request,body:dict):
        auth_body(body);rate_check(request,'setup')
        if not hmac.compare_digest(str(body.get('token','')),c.setup_token):fail(403,'Código de instalação incorreto.')
        email=validate_email(body.get('email'));validate_password(body.get('password'))
        name=body.get('name','');company=body.get('company','')
        D.string(name,'Seu nome',100,True);D.string(company,'Sua empresa',300,True)
        user={'id':secrets.token_hex(16),'name':name.strip(),'email':email,'password_hash':PASSWORD_HASHER.hash(body['password']),'role':'admin','active':True,'created_at':D.now(),'updated_at':D.now()}
        response=JSONResponse({})
        with transaction(True) as conn:
            if conn.execute(select(users.c.id)).first():fail(409,'A instalação já foi concluída. Use o login.')
            conn.execute(insert(users).values(**user))
            d=D.blank(company.strip());d['settings']['owner']=name.strip();d['settings']['team']=[name.strip()]
            conn.execute(update(workspace).where(workspace.c.id==1).values(settings=d['settings'],meta=d['meta']))
            csrf=new_session(conn,user,response);log_event(conn,user,'setup')
            payload=envelope(conn,user,csrf)
        response.body=json.dumps(payload,ensure_ascii=False).encode();response.headers['content-length']=str(len(response.body))
        return response

    @app.post('/api/login')
    def login(request:Request,body:dict):
        auth_body(body)
        email=body.get('email','');password=body.get('password','')
        if not isinstance(email,str) or not isinstance(password,str) or len(email)>254 or len(password)>128:fail(401,'E-mail ou senha incorretos.')
        email=email.strip().lower();rate_check(request,email)
        with transaction() as conn:user=conn.execute(select(users).where(users.c.email==email)).mappings().first()
        valid=verify_password(user['password_hash'] if user else DUMMY_HASH,password)
        if not valid or not user or not user['active']:fail(401,'E-mail ou senha incorretos.')
        response=JSONResponse({})
        with transaction(True) as conn:
            # Re-read after hashing to avoid revocation/change races.
            latest=conn.execute(select(users).where(users.c.id==user['id'])).mappings().one()
            if not latest['active'] or latest['password_hash']!=user['password_hash']:fail(401,'Credenciais alteradas. Entre novamente.')
            old=request.cookies.get(cookie_name)
            if old:conn.execute(delete(sessions).where(sessions.c.token_hash==digest(old)))
            csrf=new_session(conn,dict(latest),response)
            conn.execute(delete(rate_limits).where(rate_limits.c.id=='account:'+digest(email)))
            log_event(conn,latest,'login');payload=envelope(conn,latest,csrf)
        response.body=json.dumps(payload,ensure_ascii=False).encode();response.headers['content-length']=str(len(response.body));return response

    @app.get('/api/session')
    def session(request:Request):
        with transaction() as conn:
            user,s=principal(conn,request)
            return envelope(conn,user,s['csrf'])

    @app.get('/api/state')
    def state(request:Request):
        with transaction() as conn:
            user,_=principal(conn,request)
            return envelope(conn,user)

    @app.post('/api/heartbeat')
    def heartbeat(request:Request):
        with transaction(True) as conn:
            user,s=principal(conn,request,True)
            conn.execute(update(sessions).where(sessions.c.token_hash==s['token_hash']).values(last_seen=int(time.time())))
        return {'ok':True}

    @app.post('/api/logout')
    def logout(request:Request):
        with transaction(True) as conn:
            user,s=principal(conn,request,True)
            conn.execute(delete(sessions).where(sessions.c.token_hash==s['token_hash']));log_event(conn,user,'logout')
        response=JSONResponse({'ok':True});response.delete_cookie(cookie_name,path='/',secure=c.production,httponly=True,samesite='strict');return response

    @app.post('/api/password/change')
    def password_change(request:Request,body:dict):
        auth_body(body);validate_password(body.get('password'))
        old=body.get('current','')
        if not isinstance(old,str) or len(old)>128:fail(422,'Senha atual inválida.')
        response=JSONResponse({})
        with transaction(True) as conn:
            user,s=principal(conn,request,True)
            if not verify_password(user['password_hash'],old):fail(403,'Senha atual incorreta.')
            ph=PASSWORD_HASHER.hash(body['password'])
            conn.execute(update(users).where(users.c.id==user['id']).values(password_hash=ph,updated_at=D.now()))
            conn.execute(delete(sessions).where(sessions.c.user_id==user['id']))
            conn.execute(delete(resets).where(resets.c.user_id==user['id']))
            csrf=new_session(conn,user,response);log_event(conn,user,'password_changed')
        response.body=json.dumps({'ok':True,'csrf':csrf}).encode();response.headers['content-length']=str(len(response.body));return response

    @app.get('/api/users')
    def list_users(request:Request):
        with transaction() as conn:
            user,_=principal(conn,request);require_admin(user)
            return {'users':[public_user(r)|({'clientId':client_scope(conn,r['id'])} if r['role']=='client' else {}) for r in conn.execute(select(users).order_by(users.c.name)).mappings()]}

    @app.post('/api/users')
    def create_user(request:Request,body:dict):
        auth_body(body)
        email=validate_email(body.get('email'));D.string(body.get('name'),'Nome',100,True)
        role=body.get('role');D.enum(role,D.ROLE_LABELS,'Perfil')
        client_id=body.get('clientId','')
        if role=='client' and (not isinstance(client_id,str) or not D.ID_RE.fullmatch(client_id)):fail(422,'Perfil Cliente exige um cliente vinculado.')
        uid=secrets.token_hex(16);token=secrets.token_urlsafe(32)
        with transaction(True) as conn:
            user,_=principal(conn,request,True);require_admin(user)
            if conn.execute(select(func.count()).select_from(users)).scalar_one()>=60:fail(422,'Limite de 60 contas nesta edição.')
            new={'id':uid,'name':body['name'].strip(),'email':email,'role':role,'active':True,'password_hash':PASSWORD_HASHER.hash(secrets.token_urlsafe(48)),'created_at':D.now(),'updated_at':D.now()}
            conn.execute(insert(users).values(**new))
            if role=='client':
                if not conn.execute(select(records.c.id).where(records.c.id==client_id,records.c.kind=='clients')).first():fail(422,'Cliente vinculado não encontrado.')
                conn.execute(insert(user_scopes).values(user_id=uid,client_id=client_id))
            conn.execute(insert(resets).values(token_hash=digest(token),user_id=uid,expires=int(time.time())+3600,used=False))
            d=load_data(conn);team=list(dict.fromkeys(d['settings']['team']+[new['name']]))[:60]
            d['settings']['team']=team;d['meta']['updatedAt']=D.now();d['meta']['changeId']=secrets.token_hex(12);d['meta']['settingsRevision']=d['meta'].get('settingsRevision',0)+1
            conn.execute(update(workspace).where(workspace.c.id==1).values(settings=d['settings'],meta=d['meta'],revision=workspace.c.revision+1))
            log_event(conn,user,'user_created','users',uid,{'role':role})
        return {'user':public_user(new),'activationToken':token,'expiresIn':3600}

    @app.patch('/api/users/{uid}')
    def edit_user(uid:str,request:Request,body:dict):
        auth_body(body)
        if set(body)-{'role','active','name','clientId'}:fail(422,'Campo não permitido na conta.')
        with transaction(True) as conn:
            actor,_=principal(conn,request,True);require_admin(actor)
            old=conn.execute(select(users).where(users.c.id==uid)).mappings().first()
            if not old:fail(404,'Conta não encontrada.')
            role=body.get('role',old['role']);active=body.get('active',old['active']);name=body.get('name',old['name']);client_id=body.get('clientId',client_scope(conn,uid))
            D.enum(role,D.ROLE_LABELS,'Perfil');D.string(name,'Nome',100,True)
            if role=='client' and (not isinstance(client_id,str) or not D.ID_RE.fullmatch(client_id) or not conn.execute(select(records.c.id).where(records.c.id==client_id,records.c.kind=='clients')).first()):fail(422,'Perfil Cliente exige um cliente válido.')
            if type(active) is not bool:fail(422,'Situação inválida.')
            if old['role']=='admin' and old['active'] and (role!='admin' or not active):
                n=conn.execute(select(func.count()).select_from(users).where(users.c.active==True,users.c.role=='admin')).scalar_one()
                if n<=1:fail(409,'Não é permitido desativar ou rebaixar o último administrador.')
            conn.execute(update(users).where(users.c.id==uid).values(role=role,active=active,name=name.strip(),updated_at=D.now()))
            conn.execute(delete(user_scopes).where(user_scopes.c.user_id==uid))
            if role=='client':conn.execute(insert(user_scopes).values(user_id=uid,client_id=client_id))
            conn.execute(delete(sessions).where(sessions.c.user_id==uid))
            if not active:conn.execute(delete(resets).where(resets.c.user_id==uid))
            log_event(conn,actor,'user_updated','users',uid,{'role':role,'active':active})
        return {'ok':True}

    @app.post('/api/users/{uid}/reset')
    def reset_user(uid:str,request:Request):
        token=secrets.token_urlsafe(32)
        with transaction(True) as conn:
            actor,_=principal(conn,request,True);require_admin(actor)
            target=conn.execute(select(users).where(users.c.id==uid,users.c.active==True)).mappings().first()
            if not target:fail(404,'Conta ativa não encontrada.')
            conn.execute(delete(resets).where(resets.c.user_id==uid))
            conn.execute(insert(resets).values(token_hash=digest(token),user_id=uid,expires=int(time.time())+3600,used=False))
            log_event(conn,actor,'password_reset_issued','users',uid)
        return {'activationToken':token,'expiresIn':3600}

    @app.post('/api/password/reset')
    def redeem_reset(request:Request,body:dict):
        auth_body(body);rate_check(request,'password-reset');validate_password(body.get('password'))
        token=body.get('token','')
        if not isinstance(token,str) or len(token)>100:fail(422,'Código inválido.')
        with transaction(True) as conn:
            r=conn.execute(select(resets).where(resets.c.token_hash==digest(token),resets.c.used==False,resets.c.expires>int(time.time()))).mappings().first()
            if not r:fail(400,'Código inválido, expirado ou já utilizado. Solicite outro ao administrador.')
            target=conn.execute(select(users).where(users.c.id==r['user_id'],users.c.active==True)).mappings().first()
            if not target:fail(400,'Conta indisponível.')
            conn.execute(update(users).where(users.c.id==target['id']).values(password_hash=PASSWORD_HASHER.hash(body['password']),updated_at=D.now()))
            conn.execute(delete(sessions).where(sessions.c.user_id==target['id']))
            conn.execute(delete(resets).where(resets.c.user_id==target['id']))
            log_event(conn,target,'password_reset_completed')
        return {'ok':True}

    def save_candidate(conn,user,old,candidate,changed,deleted,settings_changed=False,action='transaction'):
        D.validate(candidate)
        w=conn.execute(select(workspace.c.revision)).scalar_one();revision=w+1;stamp=D.now()
        for kind,r,prior in changed:
            r.pop('_rev',None)
            r['createdAt']=prior['createdAt'] if prior else r.get('createdAt',stamp)
            r['updatedAt']=stamp
            unique=None
            if kind=='proposals':unique=r['code'].casefold()
            if kind=='entries' and r['contractId']:unique=r['contractId']+'|'+r['competence']
            values={'kind':kind,'revision':revision,'data':r,'unique_key':unique}
            if prior:conn.execute(update(records).where(records.c.id==r['id']).values(**values))
            else:conn.execute(insert(records).values(id=r['id'],**values))
            fields=sorted(k for k,v in r.items() if k not in {'createdAt','updatedAt','id'} and (not prior or prior.get(k)!=v))
            log_event(conn,user,'record_updated' if prior else 'record_created',kind,r['id'],{'fields':fields})
        for kind,r in deleted:
            conn.execute(delete(records).where(records.c.id==r['id']))
            log_event(conn,user,'record_deleted',kind,r['id'])
        candidate['meta']['updatedAt']=stamp;candidate['meta']['changeId']=secrets.token_hex(12)
        if settings_changed:
            candidate['meta']['settingsRevision']=old['meta'].get('settingsRevision',0)+1
            log_event(conn,user,'settings_updated')
        conn.execute(update(workspace).where(workspace.c.id==1).values(revision=revision,settings=candidate['settings'],meta=candidate['meta']))
        log_event(conn,user,action,details={'upserts':len(changed),'deletes':len(deleted),'revision':revision})

    @app.post('/api/transactions')
    def mutate(request:Request,body:dict):
        auth_body(body)
        if set(body)-{'requestId','upserts','deletes','settings','settingsRevision','demo'}:fail(422,'Campo desconhecido na transação.')
        req=body.get('requestId','')
        if not isinstance(req,str) or not D.ID_RE.fullmatch(req):fail(422,'Identificador de requisição obrigatório.')
        ups=body.get('upserts',[]);dels=body.get('deletes',[])
        if not isinstance(ups,list) or not isinstance(dels,list) or len(ups)+len(dels)>10000:fail(422,'Transação acima do limite de 10.000 alterações.')
        body_hash=digest(json.dumps(body,sort_keys=True,ensure_ascii=False))
        with transaction(True) as conn:
            user,s=principal(conn,request,True);role=user['role'];key=user['id']+':'+req
            seen=conn.execute(select(idempotency).where(idempotency.c.id==key)).mappings().first()
            if seen:
                if seen['body_hash']!=body_hash:fail(409,'Identificador reutilizado com conteúdo diferente.')
                result=envelope(conn,user);result['replayed']=True;return result
            old=load_data(conn);candidate=deepcopy(old)
            oldmap={k:{r['id']:r for r in old[k]} for k in D.KINDS}
            visible=data_for_user(conn,old,user);visible_ids={k:{r['id'] for r in visible[k]} for k in D.KINDS}
            changed=[];deleted=[];touched=set();mutated_kinds={o.get('kind') for o in ups+dels if isinstance(o,dict) and isinstance(o.get('kind'),str)}
            for op in ups:
                if not isinstance(op,dict) or set(op)!={'kind','record','expectedRevision'}:fail(422,'Operação inválida.')
                kind=op['kind'];r=deepcopy(op['record']);expected=op['expectedRevision']
                if not isinstance(kind,str) or kind not in D.WRITE[role]:fail(403,'Seu perfil não pode alterar este módulo.')
                if not isinstance(r,dict):fail(422,'Registro inválido.')
                ident=r.get('id');prior=oldmap[kind].get(ident) if isinstance(ident,str) else None
                if not isinstance(ident,str) or not D.ID_RE.fullmatch(ident):fail(422,'Identificador inválido.')
                if ident in touched:fail(422,'O mesmo registro aparece mais de uma vez na transação.')
                touched.add(ident)
                if type(expected) is not int or expected!=(prior['_rev'] if prior else 0):
                    fail(409,'Este registro mudou em outra sessão. Seu formulário foi preservado. Copie os campos necessários, atualize a base e revise antes de salvar.',kind=kind,recordId=ident)
                if prior and ident not in visible_ids[kind]:fail(403,'Registro fora do seu perfil de acesso.')
                if role=='client':
                    scope=client_scope(conn,user['id'])
                    if not scope or r.get('clientId')!=scope:fail(403,'Registro fora do cliente vinculado a esta conta.')
                    if kind in {'files','comments'}:r['visibility']='client'
                if role=='operations' and kind=='projects':
                    if r.get('budgetCents',0)!=0 or r.get('dealId','')!='':fail(403,'O perfil Operação não pode alterar valores ou vínculos comerciais.')
                    r['budgetCents']=prior['budgetCents'] if prior else 0
                    r['dealId']=prior['dealId'] if prior else ''
                if role=='operations' and kind=='tasks':
                    if r.get('dealId','')!='':fail(403,'Vínculo comercial não permitido para este perfil.')
                    r['dealId']=prior['dealId'] if prior else ''
                if kind=='activities':
                    allowed={'admin':{'shared','commercial','finance','private'},'sales':{'shared','commercial'},'operations':{'shared'},'finance':{'shared','finance'}}[role]
                    visibility=r.get('visibility',prior.get('visibility','shared') if prior else ('finance' if mutated_kinds & {'entries','contracts'} else 'commercial' if mutated_kinds & {'deals','proposals'} else {'sales':'commercial','finance':'finance'}.get(role,'shared')))
                    if not isinstance(visibility,str) or visibility not in allowed:fail(403,'Visibilidade da interação não permitida.')
                    r['visibility']=visibility
                if prior and kind=='entries' and prior['contractId'] and any(r.get(k)!=prior[k] for k in ['contractId','competence','clientId','type']):
                    fail(422,'Os vínculos de uma mensalidade gerada não podem ser alterados.')
                r.pop('_rev',None);stamp=D.now()
                r['createdAt']=prior['createdAt'] if prior else stamp;r['updatedAt']=stamp
                candidate[kind]=[v for v in candidate[kind] if v['id']!=ident]+[r]
                changed.append((kind,r,prior))
            for op in dels:
                if not isinstance(op,dict) or set(op)!={'kind','id','expectedRevision'}:fail(422,'Exclusão inválida.')
                kind=op['kind'];ident=op['id']
                if not isinstance(kind,str) or kind not in D.WRITE[role]:fail(403,'Seu perfil não pode excluir neste módulo.')
                if not isinstance(ident,str) or ident in touched:fail(422,'Identificador repetido ou inválido.')
                touched.add(ident);prior=oldmap[kind].get(ident)
                if not prior or type(op['expectedRevision']) is not int or op['expectedRevision']!=prior['_rev']:fail(409,'Registro excluído ou alterado por outra pessoa. Atualize antes de excluir.')
                if ident not in visible_ids[kind]:fail(403,'Registro fora do seu acesso.')
                candidate[kind]=[r for r in candidate[kind] if r['id']!=ident];deleted.append((kind,prior))
            settings_changed='settings' in body
            if settings_changed:
                require_admin(user)
                if type(body.get('settingsRevision')) is not int or body['settingsRevision']!=old['meta'].get('settingsRevision',0):fail(409,'As configurações foram alteradas por outra pessoa. Atualize antes de salvar.')
                candidate['settings']=body['settings']
            if 'demo' in body:
                require_admin(user)
                if type(body['demo']) is not bool:fail(422,'Demonstração inválida.')
                candidate['meta']['demo']=body['demo']
            self_contained_guard(old,candidate,changed)
            save_candidate(conn,user,old,candidate,changed,deleted,settings_changed)
            conn.execute(insert(idempotency).values(id=key,body_hash=body_hash,created=int(time.time())))
            conn.execute(delete(idempotency).where(idempotency.c.created<int(time.time())-30*86400))
            conn.execute(update(sessions).where(sessions.c.token_hash==s['token_hash']).values(last_seen=int(time.time())))
            return envelope(conn,user)

    def self_contained_guard(old,candidate,changed):
        """A proposal marked accepted must agree with its linked sale in the SAME commit.
        The UI performs the transition and the server verifies it; bypassing the UI
        cannot produce a half-accepted transaction.
        """
        D.validate(candidate)
        deals={r['id']:r for r in candidate['deals']};clients={r['id']:r for r in candidate['clients']}
        for kind,r,prior in changed:
            if kind=='proposals' and r.get('status')=='accepted':
                if r.get('dealId'):
                    deal=deals.get(r['dealId'])
                    if not deal or deal['stage']!='won' or deal['valueCents']!=D.subtotal(r)-r['discountCents']:
                        fail(422,'O aceite precisa atualizar a oportunidade vinculada na mesma transação.')
                client=clients.get(r.get('clientId'))
                if not client or client.get('status')!='active':fail(422,'O aceite precisa ativar o cliente na mesma transação.')

    @app.post('/api/files/upload')
    async def upload_file(request:Request):
        from urllib.parse import unquote
        raw=await request.body()
        if not raw: fail(422,'Selecione um arquivo com conteúdo.')
        if len(raw)>MAX_BODY: fail(413,'Arquivo acima de 16 MB nesta edição monolítica.')
        allowed={'application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','text/csv','image/jpeg','image/png','image/webp','image/svg+xml','video/mp4','video/quicktime','application/zip','application/vnd.openxmlformats-officedocument.presentationml.presentation','text/plain','application/octet-stream'}
        mime=(request.headers.get('content-type') or 'application/octet-stream').split(';',1)[0].strip().lower()
        if mime not in allowed: fail(415,'Tipo de arquivo não permitido.')
        original=unquote(request.headers.get('x-file-name','arquivo')).replace('\\','/').split('/')[-1].strip()
        if not original or len(original)>240: fail(422,'Nome de arquivo inválido.')
        client_id=request.headers.get('x-client-id','').strip(); project_id=request.headers.get('x-project-id','').strip()
        fid='file_'+secrets.token_hex(12); stamp=D.now()
        record={'id':fid,'createdAt':stamp,'updatedAt':stamp,'title':original,'clientId':client_id,'projectId':project_id,'owner':'','description':'','nextAction':'','category':'Arquivo','relatedType':'','relatedId':'','status':'active','priority':'normal','dueDate':'','startDate':D.today(),'tags':[],'data':{},'visibility':'internal','originalName':original,'storageKey':fid,'mimeType':mime,'size':len(raw),'version':1}
        with transaction(True) as conn:
            user,sess=principal(conn,request,True)
            if 'files' not in D.WRITE[user['role']]: fail(403,'Seu perfil não pode enviar arquivos.')
            record['owner']=user['name']
            if user['role']=='client':
                scope=client_scope(conn,user['id'])
                if not scope:fail(403,'Conta de cliente sem vínculo válido.')
                record['clientId']=scope;record['visibility']='client';client_id=scope
            old=load_data(conn); candidate=deepcopy(old)
            if client_id and not any(x['id']==client_id for x in candidate['clients']): fail(422,'Cliente vinculado não existe.')
            if project_id:
                project=next((x for x in candidate['projects'] if x['id']==project_id),None)
                if not project: fail(422,'Projeto vinculado não existe.')
                if client_id and project['clientId']!=client_id: fail(422,'Projeto e cliente não correspondem.')
                record['clientId']=project['clientId']
            candidate['files'].append(record); D.validate(candidate)
            uploads=c.data_dir/'uploads'; uploads.mkdir(parents=True,exist_ok=True,mode=0o700)
            target=uploads/fid; temp=uploads/(fid+'.tmp')
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            try:
                with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                os.replace(temp,target)
                save_candidate(conn,user,old,candidate,[('files',record,None)],[],False,action='file_uploaded')
                conn.execute(update(sessions).where(sessions.c.token_hash==sess['token_hash']).values(last_seen=int(time.time())))
            except Exception:
                try: temp.unlink(missing_ok=True); target.unlink(missing_ok=True)
                except OSError: pass
                raise
            return envelope(conn,user)

    @app.get('/api/files/{fid}/content')
    def download_file(fid:str,request:Request):
        if not D.ID_RE.fullmatch(fid): fail(404,'Arquivo não encontrado.')
        with transaction() as conn:
            user,_=principal(conn,request)
            if 'files' not in D.READ[user['role']]: fail(403,'Seu perfil não pode consultar arquivos.')
            row=conn.execute(select(records).where(records.c.id==fid,records.c.kind=='files')).mappings().first()
            if not row: fail(404,'Arquivo não encontrado.')
            meta=deepcopy(row['data'])
            if user['role']=='client' and (meta.get('clientId')!=client_scope(conn,user['id']) or meta.get('visibility')!='client'):fail(403,'Arquivo não disponível no portal do cliente.')
        target=c.data_dir/'uploads'/meta.get('storageKey',fid)
        if not target.is_file(): fail(404,'Conteúdo do arquivo não está disponível neste servidor.')
        name=meta.get('originalName') or meta.get('title') or 'arquivo'
        return FileResponse(target,media_type=meta.get('mimeType') or 'application/octet-stream',filename=name)

    @app.get('/api/backup')
    def export_backup(request:Request):
        with transaction(True) as conn:
            user,_=principal(conn,request);require_admin(user)
            data=load_data(conn)
            for k in D.KINDS:
                for r in data[k]:r.pop('_rev',None)
            data['meta']['lastBackup']=D.now()
            log_event(conn,user,'backup_exported',details={'records':sum(len(data[k]) for k in D.KINDS)})
        return JSONResponse(data,headers={'Content-Disposition':f'attachment; filename="nexo-equipe-{D.today()}.json"'})

    def import_data(body):
        data=deepcopy(body.get('data'))
        if not isinstance(data,dict):fail(422,'Backup JSON ausente.')
        if set(data)-set(D.blank()):fail(422,'Campos desconhecidos no backup.')
        for kind in D.KINDS:data.setdefault(kind,[])
        # Legacy notes may contain payment/commercial figures. Keep them admin-only
        # unless they already carry a valid explicit visibility classification.
        for kind in D.KINDS:
            for r in data.get(kind,[]):
                if not isinstance(r,dict):fail(422,'Registro de backup inválido.')
                r.pop('_rev',None)
                if kind=='activities':r.setdefault('visibility','private')
        D.validate(data)
        return data

    @app.post('/api/import/preview')
    def import_preview(request:Request,body:dict):
        auth_body(body)
        with transaction() as conn:
            user,_=principal(conn,request,True);require_admin(user)
            data=import_data(body);current=load_data(conn)
            return {'counts':{k:len(data[k]) for k in D.KINDS},'currentCounts':{k:len(current[k]) for k in D.KINDS},'revision':current['meta']['revision'],'demo':bool(data.get('meta',{}).get('demo',False))}

    @app.post('/api/import')
    def restore_backup(request:Request,body:dict):
        auth_body(body)
        if body.get('confirmation')!='RESTAURAR':fail(422,'Digite RESTAURAR para confirmar a substituição.')
        with transaction(True) as conn:
            user,_=principal(conn,request,True);require_admin(user)
            data=import_data(body);current=load_data(conn)
            if type(body.get('expectedRevision')) is not int or body['expectedRevision']!=current['meta']['revision']:
                fail(409,'A base mudou depois da prévia. Revise o arquivo novamente antes de restaurar.')
            # Save a consistent recovery snapshot BEFORE replacing any business data.
            name=write_snapshot(c.data_dir/'backups',current,'antes-restauracao')
            revision=current['meta']['revision']+1
            conn.execute(delete(records))
            for kind in D.KINDS:
                for r in data[kind]:
                    key=r['code'].casefold() if kind=='proposals' else r['contractId']+'|'+r['competence'] if kind=='entries' and r['contractId'] else None
                    conn.execute(insert(records).values(id=r['id'],kind=kind,revision=revision,data=r,unique_key=key))
            meta=D.blank()['meta'];meta.update({'demo':bool(data.get('meta',{}).get('demo',False)),'revision':revision,'changeId':secrets.token_hex(12),'settingsRevision':current['meta'].get('settingsRevision',0)+1})
            conn.execute(update(workspace).where(workspace.c.id==1).values(revision=revision,meta=meta,settings=data['settings']))
            log_event(conn,user,'backup_restored',details={'counts':{k:len(data[k]) for k in D.KINDS},'recoverySnapshot':name})
            return envelope(conn,user)

    @app.get('/api/audit')
    def audit_log(request:Request,before:int=0,limit:int=50):
        with transaction() as conn:
            user,_=principal(conn,request);require_admin(user)
            q=select(audit).order_by(audit.c.id.desc()).limit(max(1,min(limit,100)))
            if before>0:q=q.where(audit.c.id<before)
            rows=[dict(r) for r in conn.execute(q).mappings()]
            return {'events':rows,'nextBefore':rows[-1]['id'] if rows else None}

    @app.get('/api/admin/status')
    def admin_status(request:Request):
        with transaction() as conn:
            user,_=principal(conn,request);require_admin(user)
            active=conn.execute(select(func.count()).select_from(users).where(users.c.active==True)).scalar_one()
        files=sorted((c.data_dir/'backups').glob('conjunto-*.manifest.json'),key=lambda p:p.stat().st_mtime,reverse=True) if (c.data_dir/'backups').exists() else []
        return {'database':engine.dialect.name,'production':c.production,'activeUsers':active,'lastServerBackup':datetime.fromtimestamp(files[0].stat().st_mtime,timezone.utc).isoformat() if files else None,'serverBackups':len(files),'backupMode':c.backup_mode,'version':'3.0.0'}

    @app.get('/')
    def index():return FileResponse(ROOT/'web'/'index.html',media_type='text/html')

    @app.get('/assets/{name}')
    def asset(name:str):
        allowed={'app.js':'application/javascript','styles.css':'text/css','pwa.js':'application/javascript'}
        if name not in allowed:fail(404,'Arquivo não encontrado.')
        return FileResponse(ROOT/'web'/name,media_type=allowed[name])

    @app.get('/manifest.webmanifest')
    def manifest():return FileResponse(ROOT/'web'/'manifest.webmanifest',media_type='application/manifest+json')

    @app.get('/sw.js')
    def service_worker():return FileResponse(ROOT/'web'/'sw.js',media_type='application/javascript',headers={'Service-Worker-Allowed':'/'})

    @app.get('/offline.html')
    def offline():return FileResponse(ROOT/'web'/'offline.html',media_type='text/html')

    @app.get('/icons/{name}')
    def icon_asset(name:str):
        allowed={'icon-192.png','icon-512.png','maskable-512.png','apple-touch-icon.png','favicon-32.png'}
        if name not in allowed:fail(404,'Arquivo não encontrado.')
        return FileResponse(ROOT/'web'/'icons'/name,media_type='image/png')

    @app.get('/robots.txt')
    def robots():return Response('User-agent: *\nDisallow: /\n',media_type='text/plain')

    return app

def write_snapshot(folder:Path,data:dict,prefix='automatico') -> str:
    folder.mkdir(parents=True,exist_ok=True)
    name=f'{prefix}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}-{secrets.token_hex(3)}.json'
    target=folder/name
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    return name
