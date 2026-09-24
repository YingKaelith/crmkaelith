"""Gera deploy/.env localmente, sem contatar serviço algum nem publicar aplicação."""
from pathlib import Path
import os,re,secrets
ROOT=Path(__file__).resolve().parents[1]
def main():
    file=ROOT/'deploy'/'.env'
    if file.exists():raise SystemExit('deploy/.env já existe. Não será sobrescrito; preserve os segredos da instalação.')
    domain=input('Domínio do CRM (ex.: crm.suaempresa.com.br): ').strip().lower()
    if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',domain):raise SystemExit('Domínio inválido. Sem https://, porta ou caminho.')
    email=input('E-mail técnico para certificados TLS: ').strip()
    if not re.fullmatch(r'[a-zA-Z0-9._+%\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,63}',email):raise SystemExit('E-mail inválido.')
    token=secrets.token_urlsafe(36);password=secrets.token_hex(32)
    content=f'NEXO_DOMAIN={domain}\nNEXO_TLS_EMAIL={email}\nNEXO_DB_PASSWORD={password}\nNEXO_DB_ADMIN_PASSWORD={secrets.token_hex(32)}\nNEXO_SETUP_TOKEN={token}\n'
    fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(content)
    print('Arquivo criado em deploy/.env. Guarde-o em um cofre de segredos e confira permissões.\nA aplicação ainda NÃO foi publicada. Consulte docs/PUBLICACAO.md.\nO código de primeiro acesso está em NEXO_SETUP_TOKEN; não o envie em chats.')
if __name__=='__main__':main()
