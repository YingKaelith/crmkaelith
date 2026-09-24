> **Nota da edição 2.1:** este documento descreve a base Equipe e a implantação local/servidor próprio. A nova rota Render e suas diferenças de armazenamento estão em `PUBLICAR-AGORA.md`; PWA e tema estão em `MONO-E-APLICATIVO.md`; resultados atuais em `RELATORIO-2.1.md`.

# Backup, recuperação e continuidade

**Não restaure sobre uma base em uso sem interromper as operações e conferir o destino.** Backups contêm informações legíveis e, nos integrais, hashes de senhas. Não envie esses arquivos em chats públicos. A aplicação não os criptografa; configure criptografia no armazenamento externo e guarde a chave separadamente.

## Três tipos de cópia

| Tipo | Inclui | Como recuperar |
|---|---|---|
| JSON pela interface | Configurações e registros de negócio | Administrador > Configurações > restaurar; preserva contas e auditoria atuais |
| Integral SQLite, rotina local | Banco com usuários, hashes de senha, auditoria e negócio; remove sessões e códigos ativos da cópia | Console offline `server.backup --restore-sqlite` |
| Integral PostgreSQL, receita online | Dump em formato custom; usuários da aplicação, auditoria e negócio; exclui dados de sessões/códigos/requisições transitórias | `pg_restore` em banco novo isolado; procedimento abaixo, ainda não executado nesta entrega |

A exportação JSON não é um backup de usuários da aplicação, arquivos de implantação ou credenciais da infraestrutura. O pg_dump de um banco não inclui os papéis globais do cluster; a conta técnica e as variáveis da instalação precisam de recuperação separada. A documentação oficial descreve esse escopo: https://www.postgresql.org/docs/17/app-pgdump.html

## Rotina automática

O iniciador local inicia a rotina em uma thread: executa imediatamente e a cada seis horas enquanto o processo estiver aberto. O Compose usa um serviço separado `backup`, com o mesmo intervalo. Ele não envia notificações externas de falha. Monitore seus logs; uma falha é registrada como **BACKUP NÃO CONCLUÍDO**, não como sucesso.

Cada conjunto concluído possui JSON, arquivo integral e `conjunto-*.manifest.json`, com tamanho e SHA-256. O JSON e o integral são fotografias consistentes independentes feitas em sequência; sob edição simultânea podem ter revisões ligeiramente diferentes. Não misture arquivos de conjuntos diferentes para reconstruir uma suposta fotografia única.

A rotina retém 28 conjuntos concluídos. Reiniciar frequentemente produz conjuntos adicionais; isso não garante 7 ou 28 dias de cobertura. As cópias anteriores a restaurações são mantidas fora dessa rotação. Um backup interrompido pode deixar um arquivo sem manifesto; ele não representa um conjunto concluído. Confira espaço e retenção também no destino externo.

Em Configurações, o status “Último conjunto automático” considera manifestos concluídos, não uma verificação contínua da integridade dos arquivos. SHA-256 detecta divergências acidentais; não autentica um manifesto que um atacante também possa substituir.

## Backup manual no servidor

Com as dependências instaladas e as variáveis do mesmo ambiente:

```sh
# Linux/macOS, na raiz do pacote
.venv/bin/python -m server.backup
# Windows
.venv\Scripts\python.exe -m server.backup
```

Em produção: `docker compose exec backup python -m server.backup`, executado na pasta `deploy`. Para cópia externa, use a ferramenta de armazenamento escolhida pela empresa. Exemplo de retirada manual, a partir de `deploy`:

```sh
docker compose cp backup:/var/lib/nexo/backups ./copia-protegida
```

Essa retirada não é um agendamento externo. Copie também `deploy/.env` para um cofre adequado, não para repositório de código. Não copie `nexo.db` sozinho enquanto o SQLite estiver ativo: use a API de backup fornecida, que considera as gravações do banco. A rotina usa a API `sqlite3.Connection.backup`: https://docs.python.org/3.13/library/sqlite3.html#sqlite3.Connection.backup

## Restauração integral SQLite

Primeiro ensaie em outra pasta com cópia dos arquivos e dados fictícios. O comando não restaura sobre processo ativo identificado pelo iniciador; também recusa arquivos WAL/SHM presentes. Essa é uma proteção auxiliar, não um detector universal de todos os processos.

1. Pare todas as instâncias com Ctrl+C. Não force a substituição de um banco aberto.
2. Preserve a pasta atual e verifique o SHA-256 do arquivo de origem com o manifesto.
3. Na pasta da instalação parada, execute, trocando o caminho pelo arquivo real:

```sh
.venv/bin/python -m server.backup --restore-sqlite data/backups/integral-ARQUIVO.sqlite --confirm RESTAURAR
```

No Windows, substitua `.venv/bin/python` por `.venv\Scripts\python.exe`.

O comando confere a integridade SQLite, o esquema e a identidade básica do banco. Cria cópia anterior, substitui o banco, limpa sessões/códigos/idempotência/limites de tentativa e registra um evento de recuperação. Reinicie e entre novamente. As contas e senhas existentes no backup voltam a vigorar. Uma conta desativada depois daquela cópia pode reaparecer ativa: revise usuários antes de liberar acesso.

Se restar `server.pid` depois de queda abrupta, confirme pelo gerenciador de processos que nenhum servidor usa a pasta antes de remover esse marcador. Se houver WAL/SHM, não os apague. Com o servidor realmente parado, um profissional pode abrir o banco, executar `PRAGMA wal_checkpoint(TRUNCATE);`, fechar todas as conexões e conferir se não houve bloqueio. Uma restauração bem-sucedida pode perder tudo que foi criado após o backup; reconcilie externamente.

## Restauração PostgreSQL — ensaio obrigatório

Este caminho está preparado, mas não foi executado no ambiente desta entrega. Use um banco **novo e isolado**, nunca a base de produção como primeira tentativa. Mantenha a mesma série principal entre cliente pg_dump/pg_restore e banco na receita. Faça inventário e cópia das configurações antes de trocar qualquer endereço.

Com `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` e `PGDATABASE` apontando para o banco de homologação vazio e credenciais fora do histórico do shell:

```sh
pg_restore --exit-on-error --single-transaction --no-owner --no-acl --dbname="$PGDATABASE" /caminho/backup.dump
psql --set=ON_ERROR_STOP=1 --dbname="$PGDATABASE" -c 'TRUNCATE TABLE sessions, password_resets, idempotency, rate_limits;'
```

Somente restaure arquivos de origem confiável. Dumps podem conter instruções de banco; a documentação oficial alerta para esse risco: https://www.postgresql.org/docs/17/app-pgrestore.html

Confira contagens, contas, vínculos, auditoria, valores e login em uma instância isolada do aplicativo. O ensaio não substitui teste de sistema operacional/volumes. Só depois planeje a troca da base, uma janela de manutenção e um caminho de retorno. Não use `docker compose down -v`: isso apaga volumes persistentes.

## Esqueci a senha de todos os administradores

Uma pessoa autorizada com acesso ao sistema operacional pode gerar um link privado, de uma hora e um único uso, para uma conta ativa existente:

```sh
.venv/bin/python -m server.admin administrador@suaempresa.com.br
# Na receita Docker, dentro de deploy:
docker compose exec app python -m server.admin administrador@suaempresa.com.br
```

O comando não cria contas, não reativa usuários e não muda o perfil. A emissão é auditada. Não grave o link em sistema público de chamados. Quem controla o servidor/banco consegue recuperar contas: proteja o acesso administrativo da infraestrutura.
