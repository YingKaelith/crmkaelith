"""Read-only HTTP smoke checks. Never logs in, modifies data, or creates an account.
Usage: python scripts/verificar_publicacao.py https://YOUR-SERVICE.onrender.com
Local testing only: add --allow-local for an http://127.0.0.1 address.
"""
from __future__ import annotations
import argparse
import json
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from pathlib import Path
from datetime import datetime, timezone

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check(origin: str, allow_local: bool=False) -> dict:
    origin=origin.rstrip('/')
    p=urlsplit(origin)
    if p.username or p.password or p.path or p.query or p.fragment or not p.hostname:
        raise ValueError('Use somente a origem: https://servico.exemplo.com, sem caminho ou credenciais.')
    local=p.scheme=='http' and p.hostname in {'127.0.0.1','localhost'} and allow_local
    if p.scheme!='https' and not local:
        raise ValueError('Publicação exige HTTPS. --allow-local permite HTTP somente em loopback para testes.')
    opener=build_opener(NoRedirect)
    checks=[]; warnings=[]

    def get(path):
        request=Request(origin+path,headers={'User-Agent':'Nexo-Deployment-Check/2.2','Accept':'*/*'})
        try:
            with opener.open(request,timeout=15) as response:
                return response.status,dict(response.headers.items()),response.read(2_000_000)
        except HTTPError as error:
            return error.code,dict(error.headers.items()),error.read(4096)

    def item(name,ok):checks.append({'check':name,'passed':bool(ok)})
    status,headers,body=get('/api/health')
    health=json.loads(body) if status==200 else {}
    item('API responde e consulta o banco',status==200 and health.get('status')=='ok')
    status,headers,body=get('/')
    h={k.lower():v for k,v in headers.items()}
    item('Página principal acessível sem redirecionamento',status==200)
    item('HTML referencia manifesto e instalação',b'/manifest.webmanifest' in body and b'/assets/pwa.js' in body)
    item('Proteções CSP e antienquadramento',"worker-src 'self'" in h.get('content-security-policy','') and h.get('x-frame-options')=='DENY')
    item('HTML não fica em cache HTTP',h.get('cache-control')=='no-store')
    if not local:item('HSTS ativo', 'max-age=' in h.get('strict-transport-security',''))
    status,_,body=get('/manifest.webmanifest')
    manifest=json.loads(body) if status==200 else {}
    item('Manifesto define abertura como aplicativo',status==200 and manifest.get('display')=='standalone' and manifest.get('start_url')=='/')
    icons=manifest.get('icons',[])
    item('Ícones declarados em 192 e 512 pixels',{'192x192','512x512'} <= {i.get('sizes') for i in icons})
    for icon in icons:
        src=icon.get('src','')
        if not src.startswith('/icons/') or '?' in src:
            item('Caminho seguro do ícone',False);continue
        code,_,content=get(src);item('Ícone acessível: '+src,code==200 and content.startswith(b'\x89PNG'))
    status,headers,body=get('/sw.js')
    item('Service worker acessível',status==200 and b'nexo-public-' in body)
    status,_,_=get('/api/state');item('Base não é exposta sem login',status==401)
    status,_,_=get('/api/backup');item('Backup não é exposto sem login',status==401)
    status,_,body=get('/api/bootstrap')
    if status==200 and json.loads(body).get('setupRequired'):
        warnings.append('Primeiro administrador ainda não criado. Use o token secreto no painel do provedor.')
    if local:warnings.append('Execução local: não confirma domínio público, TLS real, PWA instalada ou acesso externo.')
    warnings.append('Este teste não valida instalação em celular, permissões entre contas, restauração PostgreSQL, carga ou disponibilidade futura.')
    return {'origin':origin,'checkedAt':datetime.now(timezone.utc).isoformat(),
            'scope':'Somente leitura; sem login, sem alterações','passed':all(c['passed'] for c in checks),'checks':checks,'warnings':warnings}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin');parser.add_argument('--allow-local',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        result=check(args.origin,args.allow_local)
    except (ValueError,URLError,TimeoutError,OSError) as error:
        print('Verificação interrompida:',str(error));return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.output:
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return 0 if result['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
