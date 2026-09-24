from __future__ import annotations
from sqlalchemy import create_engine, event, MetaData, Table, Column, Integer, BigInteger, String, Text, Boolean, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.engine import Engine
from pathlib import Path

metadata=MetaData()
workspace=Table('workspace',metadata,Column('id',Integer,primary_key=True),Column('revision',Integer,nullable=False,default=0),Column('schema_version',Integer,nullable=False,default=1),Column('settings',JSON,nullable=False),Column('meta',JSON,nullable=False))
users=Table('users',metadata,Column('id',String(80),primary_key=True),Column('name',String(100),nullable=False),Column('email',String(254),nullable=False,unique=True),Column('password_hash',Text,nullable=False),Column('role',String(20),nullable=False),Column('active',Boolean,nullable=False,default=True),Column('created_at',String(40),nullable=False),Column('updated_at',String(40),nullable=False))
user_scopes=Table('user_scopes',metadata,Column('user_id',String(80),ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),Column('client_id',String(80),nullable=False,index=True))
sessions=Table('sessions',metadata,Column('token_hash',String(64),primary_key=True),Column('user_id',String(80),ForeignKey('users.id',ondelete='CASCADE'),nullable=False,index=True),Column('csrf',String(80),nullable=False),Column('created',BigInteger,nullable=False),Column('expires',BigInteger,nullable=False,index=True),Column('last_seen',BigInteger,nullable=False))
resets=Table('password_resets',metadata,Column('token_hash',String(64),primary_key=True),Column('user_id',String(80),ForeignKey('users.id',ondelete='CASCADE'),nullable=False),Column('expires',BigInteger,nullable=False),Column('used',Boolean,nullable=False,default=False))
records=Table('records',metadata,Column('id',String(80),primary_key=True),Column('kind',String(20),nullable=False,index=True),Column('revision',Integer,nullable=False),Column('data',JSON,nullable=False),Column('unique_key',String(200),nullable=True),UniqueConstraint('kind','unique_key',name='uq_business_key'))
audit=Table('audit_log',metadata,Column('id',Integer,primary_key=True,autoincrement=True),Column('time',String(40),nullable=False),Column('actor_id',String(80),nullable=False),Column('actor',String(254),nullable=False),Column('action',String(80),nullable=False),Column('kind',String(30),nullable=False),Column('record_id',String(80),nullable=False),Column('details',JSON,nullable=False))
idempotency=Table('idempotency',metadata,Column('id',String(180),primary_key=True),Column('body_hash',String(64),nullable=False),Column('created',BigInteger,nullable=False))
rate_limits=Table('rate_limits',metadata,Column('id',String(100),primary_key=True),Column('count',Integer,nullable=False),Column('window',BigInteger,nullable=False))
Index('ix_audit_time',audit.c.time)

def make_engine(url:str) -> Engine:
    if url.startswith('postgres://'): url=url.replace('postgres://','postgresql+psycopg://',1)
    if url.startswith('postgresql://'): url=url.replace('postgresql://','postgresql+psycopg://',1)
    sqlite=url.startswith('sqlite:')
    engine=create_engine(url,pool_pre_ping=True,connect_args={'check_same_thread':False,'timeout':30} if sqlite else {})
    if sqlite:
        @event.listens_for(engine,'connect')
        def sqlite_connect(conn,_):
            conn.isolation_level=None
            cur=conn.cursor();cur.execute('PRAGMA foreign_keys=ON');cur.execute('PRAGMA busy_timeout=30000');cur.execute('PRAGMA journal_mode=WAL');cur.close()
        @event.listens_for(engine,'begin')
        def sqlite_begin(conn): conn.exec_driver_sql('BEGIN')
    return engine
