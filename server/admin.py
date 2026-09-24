"""Recuperação administrativa com acesso ao servidor, sem senha padrão.
Não publique este comando como endpoint HTTP. Exige acesso ao sistema operacional.
"""
from __future__ import annotations
import argparse,secrets,time
from sqlalchemy import select,insert,update,delete
from .app import Config,digest
from .database import make_engine,workspace,users,resets,audit
from . import domain as D


def issue_reset(config:Config,email:str)->str:
    engine=make_engine(config.database_url)
    try:
        with engine.begin() as conn:
            conn.execute(update(workspace).where(workspace.c.id==1).values(revision=workspace.c.revision))
            user=conn.execute(select(users).where(users.c.email==email.strip().lower(),users.c.active==True)).mappings().first()
            if not user:raise ValueError('Conta ativa não encontrada. Este comando não cria nem reativa contas.')
            token=secrets.token_urlsafe(32)
            conn.execute(delete(resets).where(resets.c.user_id==user['id']))
            conn.execute(insert(resets).values(token_hash=digest(token),user_id=user['id'],expires=int(time.time())+3600,used=False))
            conn.execute(insert(audit).values(time=D.now(),actor_id='system',actor='console-local',action='console_password_reset_issued',kind='users',record_id=user['id'],details={}))
        return config.public_origin+'/#ativar='+token
    finally:engine.dispose()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('email');a=p.parse_args()
    try:
        print('Link privado, válido por uma hora e um único uso:')
        print(issue_reset(Config.environment(),a.email))
        print('Não envie a logs, chamados públicos ou repositórios. O uso revoga as sessões anteriores.')
    except (ValueError,RuntimeError) as exc:raise SystemExit(str(exc))

if __name__=='__main__':main()
