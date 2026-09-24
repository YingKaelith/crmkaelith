"""Backups locais: JSON de negócio + cópia integral SQLite ou pg_dump.
Os arquivos não são criptografados. Copie-os para armazenamento externo protegido.
O backup integral e o JSON são fotografias consistentes independentes, realizadas
em sequência; sob edição concorrente podem representar revisões diferentes.
"""
from __future__ import annotations
import argparse,hashlib,json,logging,os,secrets,shutil,sqlite3,subprocess,time
from copy import deepcopy
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from threading import Event
from sqlalchemy import select,update,delete
from sqlalchemy.engine import make_url
from .app import Config,write_snapshot
from .database import make_engine,workspace,records,sessions,resets,audit,idempotency,rate_limits
from . import domain as D
log=logging.getLogger('nexo.backup')


def restrict(path:Path):
    try:path.chmod(0o700 if path.is_dir() else 0o600)
    except OSError:pass  # Em Windows, aplique ACLs da conta do serviço.


def checksum(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def business_snapshot(engine)->dict:
    with engine.begin() as conn:
        conn.execute(update(workspace).where(workspace.c.id==1).values(revision=workspace.c.revision))
        w=conn.execute(select(workspace).where(workspace.c.id==1)).mappings().one()
        data=D.blank();data['settings']=deepcopy(w['settings']);data['meta']=deepcopy(w['meta'])
        data['meta']['revision']=w['revision'];data['meta']['lastBackup']=D.now()
        for row in conn.execute(select(records)).mappings():
            r=deepcopy(row['data']);r.pop('_rev',None);data[row['kind']].append(r)
        D.validate(data)
        return data


def take_backup(config:Config,retention:int=28,full:bool=True)->dict:
    """Só publica manifesto após completar os arquivos e verificar integridade.
    Falhas geram exceção; não são transformadas em falso sucesso.
    """
    if retention<2:raise ValueError('Mantenha no mínimo dois conjuntos de backup.')
    folder=config.data_dir/'backups';folder.mkdir(parents=True,exist_ok=True);restrict(folder)
    engine=make_engine(config.database_url)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'-'+secrets.token_hex(3)
    paths=[];temp=None
    try:
        data=business_snapshot(engine)
        paths.append(folder/write_snapshot(folder,data,'automatico'))
        if full and engine.dialect.name=='sqlite':
            dbpath=Path(engine.url.database).resolve()
            temp=folder/f'.integral-{stamp}.sqlite.tmp';target=folder/f'integral-{stamp}.sqlite'
            os.close(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
            with closing(sqlite3.connect(dbpath)) as source,closing(sqlite3.connect(temp)) as dest:
                source.backup(dest)
                dest.execute('PRAGMA journal_mode=DELETE')
                if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise RuntimeError('A cópia SQLite não passou na verificação de integridade.')
                # Backup integral não deve preservar sessões autenticadas nem códigos.
                dest.execute('DELETE FROM sessions');dest.execute('DELETE FROM password_resets');dest.commit()
            restrict(temp);os.replace(temp,target);paths.append(target)
        elif full and engine.dialect.name=='postgresql':
            if not shutil.which('pg_dump'):raise RuntimeError('pg_dump não instalado; backup integral PostgreSQL não concluído.')
            u=engine.url;target=folder/f'integral-{stamp}.dump';temp=folder/f'.integral-{stamp}.dump.tmp'
            os.close(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
            # Senha apenas no ambiente do subprocesso, nunca nos argumentos/logs.
            env=os.environ.copy();env.update(PGHOST=u.host or 'localhost',PGPORT=str(u.port or 5432),PGUSER=u.username or '',PGPASSWORD=u.password or '',PGDATABASE=u.database or '')
            if u.query.get('sslmode'):env['PGSSLMODE']=u.query['sslmode']
            cmd=['pg_dump','--format=custom','--no-owner','--no-acl',*[f'--exclude-table-data=public.{t}' for t in ['sessions','password_resets','idempotency','rate_limits']],'--file',str(temp)]
            result=subprocess.run(cmd,env=env,capture_output=True,timeout=600)
            if result.returncode:raise RuntimeError('pg_dump falhou. Confira conectividade, permissões e a versão do cliente; a senha não foi registrada.')
            if not temp.exists() or temp.stat().st_size<64:raise RuntimeError('pg_dump não gerou um arquivo válido.')
            restrict(temp);os.replace(temp,target);paths.append(target)
        manifest={'createdAt':D.now(),'database':engine.dialect.name,'full':full,'businessRevision':data['meta']['revision'],'files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':checksum(p)} for p in paths]}
        target=folder/f'conjunto-{stamp}.manifest.json';temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');restrict(temp);os.replace(temp,target)
        # Só remove conjuntos antigos depois que um novo conjunto está completo.
        for old in sorted(folder.glob('conjunto-*.manifest.json'),reverse=True)[retention:]:
            try:
                info=json.loads(old.read_text())
                for item in info['files']:
                    name=item['name']
                    if Path(name).name==name:(folder/name).unlink(missing_ok=True)
                old.unlink()
            except (OSError,ValueError,KeyError):log.warning('Não foi possível limpar um conjunto antigo; confira o espaço disponível.')
        log.info('Backup concluído: %s; %d arquivos',target.name,len(paths))
        return manifest
    finally:
        if temp and temp.exists():temp.unlink(missing_ok=True)
        engine.dispose()


def run_loop(config:Config,stop:Event,interval_seconds:int=21600,retention:int=28):
    """Executa imediatamente e a cada 6h, apenas enquanto o processo estiver vivo."""
    while not stop.is_set():
        try:take_backup(config,retention=retention)
        except Exception as exc:log.error('BACKUP NÃO CONCLUÍDO: %s',exc)
        stop.wait(max(60,interval_seconds))


def restore_sqlite(config:Config,source:Path,confirmation:str)->Path:
    """Restauração integral OFFLINE. O operador deve parar todas as instâncias.
    Não substitui arquivos abertos: evita perda de dados por WAL ou processos ativos.
    """
    if confirmation!='RESTAURAR':raise ValueError('Confirme explicitamente com RESTAURAR.')
    url=make_url(config.database_url)
    if url.get_backend_name()!='sqlite':raise ValueError('Este comando só restaura SQLite. Para PostgreSQL, consulte o guia.')
    if (config.data_dir/'server.pid').exists():raise RuntimeError('Pare o iniciador antes de restaurar. Se houve falha, confirme que não há processo ativo antes de remover server.pid.')
    source=source.resolve();target=Path(url.database).resolve()
    if source==target or not source.is_file():raise ValueError('Escolha um arquivo de backup diferente do banco atual.')
    if any(Path(str(target)+suffix).exists() for suffix in ['-wal','-shm']):
        raise RuntimeError('Arquivos WAL/SHM presentes. Pare o servidor e faça checkpoint antes de restaurar. Não os apague manualmente.')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup SQLite corrompido.')
        names={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'workspace','records','users','sessions','password_resets','audit_log'}<=names:raise ValueError('Arquivo não é um backup integral deste CRM.')
        if src.execute('SELECT schema_version FROM workspace WHERE id=1').fetchone()!=(1,):raise ValueError('Versão de backup incompatível.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'-'+secrets.token_hex(3)
    recovery=config.data_dir/'backups'/f'antes-restauracao-integral-{stamp}.sqlite';recovery.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():shutil.copy2(target,recovery);restrict(recovery)
    temp=target.with_name(f'.restaurando-{stamp}.db')
    try:
        shutil.copy2(source,temp);restrict(temp)
        with closing(sqlite3.connect(temp)) as conn:
            conn.execute('PRAGMA journal_mode=DELETE')
            conn.execute('DELETE FROM sessions');conn.execute('DELETE FROM password_resets');conn.execute('DELETE FROM idempotency');conn.execute('DELETE FROM rate_limits')
            conn.execute('INSERT INTO audit_log(time,actor_id,actor,action,kind,record_id,details) VALUES(?,?,?,?,?,?,?)',(D.now(),'system','console-local','full_backup_restored','','','{}'));conn.commit()
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)
    return recovery


def main():
    p=argparse.ArgumentParser(description='Backup protegido por permissões de arquivo, sem criptografia automática.')
    p.add_argument('--loop',action='store_true');p.add_argument('--interval-hours',type=int,default=6);p.add_argument('--retention',type=int,default=28);p.add_argument('--business-only',action='store_true')
    p.add_argument('--restore-sqlite',type=Path);p.add_argument('--confirm',default='')
    args=p.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s');c=Config.environment()
    if args.restore_sqlite:
        print('Restauração concluída. Cópia anterior:',restore_sqlite(c,args.restore_sqlite,args.confirm))
    elif args.loop:
        if args.business_only:raise SystemExit('--loop inclui backup integral; não combine com --business-only.')
        if args.interval_hours<1:raise SystemExit('Intervalo mínimo de uma hora.')
        run_loop(c,Event(),args.interval_hours*3600,args.retention)
    else:print(json.dumps(take_backup(c,args.retention,not args.business_only),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
