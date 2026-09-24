> **Nota da edição 2.1:** este documento descreve a base Equipe e a implantação local/servidor próprio. A nova rota Render e suas diferenças de armazenamento estão em `PUBLICAR-AGORA.md`; PWA e tema estão em `MONO-E-APLICATIVO.md`; resultados atuais em `RELATORIO-2.1.md`.

# API HTTP · versão 2.0.0

API da própria aplicação, na mesma origem do frontend. Não é uma API pública com chaves de integração ou OAuth. Requer sessão por cookie, `Origin` exata em métodos de alteração e `X-CSRF-Token` nas alterações autenticadas. Não abra CORS nem compartilhe cookies para integrar outros serviços.

Erros são JSON com `message`. 401 indica sessão ausente/expirada; 403, origem/CSRF/perfil; 409, conflito ou identificador já usado; 422, validação; 429, tentativas em excesso; 503, banco ocupado/indisponível. Nenhum cliente deve interpretar uma falha de conexão como confirmação de gravação.

## Rotas

| Método e rota | Finalidade | Acesso |
|---|---|---|
| GET `/api/health` | Disponibilidade e versão | Público; host permitido |
| GET `/api/bootstrap` | Saber se falta o primeiro administrador | Público |
| POST `/api/setup` | Primeira empresa e administrador | Código de instalação; apenas uma vez |
| POST `/api/login` | Criar sessão | E-mail/senha; origem e limite de tentativas |
| GET `/api/session` | Perfil, permissões, dados e CSRF | Sessão |
| GET `/api/state` | Snapshot filtrado por perfil | Sessão |
| POST `/api/heartbeat` | Registrar atividade de sessão | Sessão + CSRF |
| POST `/api/logout` | Revogar a sessão atual | Sessão + CSRF |
| POST `/api/password/change` | Trocar senha, revogar outras sessões | Senha atual + CSRF |
| POST `/api/password/reset` | Ativar/recuperar conta | Código privado de uma hora |
| GET `/api/users` | Listar contas | Administrador |
| POST `/api/users` | Criar conta e emitir ativação | Administrador + CSRF |
| PATCH `/api/users/{id}` | Nome, perfil e ativação/desativação | Administrador + CSRF |
| POST `/api/users/{id}/reset` | Emitir novo código de acesso | Administrador + CSRF |
| POST `/api/transactions` | Criar/editar/excluir registros atomicamente | Perfil autorizado + CSRF |
| GET `/api/backup` | JSON de negócio | Administrador |
| POST `/api/import/preview` | Conferir backup antes de substituir | Administrador + CSRF |
| POST `/api/import` | Substituir dados de negócio | Administrador + CSRF + revisão + confirmação |
| GET `/api/audit?limit=50&before=123` | Eventos em ordem decrescente | Administrador |
| GET `/api/admin/status` | Ambiente e data do último conjunto de backup | Administrador |

`GET /api/backup` registra um evento de exportação na auditoria; não gera cópia integral nem agenda tarefa. A importação escreve uma cópia de recuperação antes de substituir o negócio. A API não inclui endpoints para executar SQL, escolher nomes de arquivos no servidor ou restaurar o banco integral via navegador.

## Transação

O snapshot contém `data`, `user`, `permissions` e `serverDate`. Cada registro contém `_rev`. O cliente deve usar a revisão lida, não uma constante. O exemplo abaixo é a forma de uma atualização sobre um registro previamente consultado:

```python
import secrets
import httpx

base = "http://127.0.0.1:8765"  # Ambiente local próprio, nunca um endpoint desconhecido.
with httpx.Client(base_url=base, headers={"Origin": base}, timeout=30) as client:
    # Obtenha credenciais por prompt protegido ou cofre; não fixe senhas no código.
    import getpass
    email = input("E-mail: ").strip()
    login = client.post("/api/login", json={"email": email, "password": getpass.getpass()})
    login.raise_for_status()
    client.headers["X-CSRF-Token"] = login.json()["csrf"]
    response = client.get("/api/state")
    response.raise_for_status()
    clients = response.json()["data"]["clients"]
    if not clients:
        raise SystemExit("Cadastre um cliente fictício pela interface antes deste exemplo.")
    record = dict(clients[0])
    record["notes"] = "Observação fictícia de um teste autorizado."
    body = {
        "requestId": secrets.token_hex(16),
        "upserts": [{"kind": "clients", "record": record, "expectedRevision": record["_rev"]}],
        "deletes": [],
    }
    changed = client.post("/api/transactions", json=body)
    if changed.status_code == 409:
        raise SystemExit("Conflito: consulte de novo e revise antes de salvar.")
    changed.raise_for_status()
    client.post("/api/logout", json={}).raise_for_status()
```

O exemplo modifica uma observação: use apenas uma instalação de testes. Em caso de timeout, preserve o corpo e `requestId` e consulte/reenvie na mesma conta para obter o resultado idempotente; não crie outro identificador sem conferir. Não faça uma repetição infinita automática.

Um `upsert` requer `kind`, registro completo e `expectedRevision=0` na criação ou a revisão atual na atualização. Exclusão requer `kind`, `id` e `expectedRevision`. Os tipos são `clients`, `deals`, `proposals`, `projects`, `tasks`, `contracts`, `entries`, `activities`. Campos aceitos e enums estão em `server/domain.py` e exemplos completos em `tests/conftest.py`.

O servidor impede campos desconhecidos. Datas operacionais são `YYYY-MM-DD`; competência, `YYYY-MM`; valores monetários, centavos inteiros. `_rev` é dado técnico, não uma sequência editável pelo usuário. IDs devem usar letras/números/hífen/sublinhado e ter até 80 caracteres. A revisão retornada deve substituir a anterior depois de gravar.

## Aceite e referências

Ao alterar uma proposta para `accepted`, inclua na mesma transação o cliente com `status=active` e, se houver, a oportunidade com `stage=won`, `closedAt` válido e valor igual ao total aprovado. O servidor verifica essas condições e rejeita estados pela metade. A criação posterior do projeto é explícita. A API não cria cobrança ou recebimento automaticamente ao aceitar proposta.

Quando um perfil de Operação edita projeto, recebe `budgetCents=0` e `dealId=''`; o servidor preserva os valores reais. Não tente preencher campos ocultos por API. A autorização é conferida antes da persistência. Interações invisíveis não podem ser editadas adivinhando seu ID.

## Importação

Envie `{ "data": backup }` à prévia. A resposta fornece contagens e `revision`. Para confirmar, envie `{ "data": backup, "confirmation": "RESTAURAR", "expectedRevision": revision }`. Se alguém alterou a base, obtenha nova prévia. **Não mescla.** Usuários e auditoria são preservados; os registros de negócio são substituídos.

Não há compatibilidade genérica com qualquer CRM. A importação implementada aceita o formato Nexo schema 1 e foi testada com a fixture da versão local. Uma migração de outro produto exige mapeamento explícito.


## Recursos públicos acrescentados na 2.1

`GET /manifest.webmanifest`, `GET /sw.js`, `GET /offline.html`, `GET /assets/pwa.js`, `GET /icons/{arquivo permitido}` e `GET /robots.txt`. Não expõem dados de negócio. `GET /api/admin/status` acrescenta `backupMode` (`local` ou `managed`); esse campo informa configuração, não valida a política do provedor.
