> **Nota da edição 2.1:** este documento descreve a base Equipe e a implantação local/servidor próprio. A nova rota Render e suas diferenças de armazenamento estão em `PUBLICAR-AGORA.md`; PWA e tema estão em `MONO-E-APLICATIVO.md`; resultados atuais em `RELATORIO-2.1.md`.

# Arquitetura, controles e limites

## Componentes

`web/app.js` mantém estado apenas em memória, renderiza a interface e envia transações por HTTP. `server/app.py` autentica, autoriza, gerencia usuários, processa operações e entrega os arquivos estáticos. `server/domain.py` valida campos, valores, datas, enums e vínculos. `server/database.py` define o esquema SQLAlchemy. `server/backup.py` cria snapshots e cópias integrais. `server/admin.py` fornece recuperação com acesso ao console da infraestrutura.

O banco é SQLite no iniciador local e PostgreSQL na receita de publicação. O caminho SQLite foi executado. O dialeto PostgreSQL é configurado via SQLAlchemy/psycopg, mas não teve teste runtime nesta entrega. Não considere a mera existência da URL PostgreSQL como prova de homologação.

## Modelo e consistência

`records` guarda um documento JSON validado por entidade, seu tipo, revisão e chave de unicidade. `workspace` guarda configurações, metadados e revisão global. Usuários, sessões, códigos temporários, idempotência, limites de tentativa e auditoria têm tabelas próprias. É um banco relacional com documentos de negócio, não um modelo completamente normalizado por cliente/projeto/pagamento.

A API aplica um delta por transação, não substitui a base inteira a cada edição. Ela bloqueia a linha do espaço de trabalho antes de ler o agregado, constrói o estado candidato completo, valida vínculos e grava tudo ou nada. Em SQLite, a transação reserva a escrita por atualização; em PostgreSQL, o código usa bloqueio de linha. Não há filas independentes de gravação por cliente: as escritas da empresa são serializadas.

Cada registro leva `_rev`. A API exige `expectedRevision`; se outro usuário mudou aquele registro, responde 409. Alterações de registros distintos podem ser combinadas sem um conflito global artificial. Configurações têm revisão própria. A importação integral exige a revisão global observada na prévia.

`requestId` com hash de conteúdo e identificação do usuário evita reaplicar a mesma transação. A tabela de idempotência é limpa após 30 dias. Não reutilize identificadores para conteúdo diferente. Isso não é uma garantia de processamento de pagamentos externos: não há integração bancária.

Valores são inteiros em centavos. Itens de propostas usam quantidade decimal, com arredondamento por item. A aplicação verifica a soma, desconto e relações no aceite. Chaves de proposta e contrato/competência são únicas. Relacionamentos entre registros de negócio são validados pela aplicação, dentro da transação, não por chaves estrangeiras SQL em campos JSON. Não escreva registros diretamente por SQL sem as mesmas validações.

## Autenticação e autorização

Senhas usam Argon2id com memória de 64 MiB, custo temporal 3 e paralelismo 2. Não há senha padrão ou cadastro público. Uma chave de instalação permite criar somente o primeiro administrador. Códigos de ativação/recuperação são aleatórios, guardados como hash, válidos por uma hora e de uso único.

Sessões são opacas, aleatórias e armazenadas por hash no servidor. A sessão expira em oito horas ou após duas horas de inatividade. Há cookies HttpOnly/SameSite Strict; o modo de produção acrescenta Secure e prefixo `__Host-`. O código não guarda senhas ou dados de negócio em localStorage. Senhas continuam sujeitas à segurança do dispositivo e de eventuais gerenciadores/autopreenchimento do navegador.

Todas as mutações HTTP exigem origem exata. Mutações autenticadas também verificam token CSRF. A API verifica perfil, módulo e visibilidade do registro; a interface apenas reflete essas permissões. Não há isolamento por proprietário/carteira, multiempresa, escopo por projeto ou aprovação em duas etapas.

Operação recebe valores de referência zerados e vínculos comerciais removidos da resposta; a interface exibe restrição/oculta esses campos. Ao editar projeto por Operação, o servidor preserva o valor e vínculo reais. Não envia dados financeiros para depois escondê-los apenas com CSS. Interações possuem classificação própria. Notas gerais e escopos não são analisados semanticamente: quem inserir segredo em texto compartilhado pode expô-lo a quem consulta aquele módulo.

Alteração de perfil/desativação revoga sessões. Alterar senha exige a atual e revoga outras sessões. Recuperar senha revoga todas. O último administrador ativo é protegido contra desativação pela aplicação, mas quem controla o banco ou o sistema operacional continua sendo uma autoridade sobre os dados.

## Outros controles implementados

Limites de corpo (16 MB), quantidade de registros/operações, comprimentos de texto e profundidade JSON; allowlist de campos e rotas estáticas; bloqueio de propriedades perigosas; mensagens genéricas de autenticação; limitação de tentativas persistida no banco; parâmetros SQLAlchemy; escape HTML na interface; CSP sem JavaScript inline em produção; proteção de origem/host; cabeçalhos no-store, nosniff e anti-enquadramento.

Alguns estilos inline existem e são permitidos na CSP. Não há promessa de proteção absoluta contra XSS. A ponte de browser usada nos testes não executou as regras de CSP como cabeçalho de página; os cabeçalhos foram inspecionados pela suíte de API. Navegação nativa em HTTPS deve ser validada na implantação.

Auditoria registra usuário, ação, tipo/identificador e nomes de campos alterados. Não guarda um diff completo de valores anteriores, nem dados de senha/código. É auditável na aplicação, mas não imutável contra alguém com acesso direto ao banco. Excluir registros não equivale a apagamento em backups ou logs; a empresa precisa de política própria de retenção.

## Limites e trabalho não executado

Não houve auditoria independente, teste de intrusão, fuzzing extensivo, teste de carga, benchmark, validação do PostgreSQL/Docker/HTTPS, revisão jurídica ou certificação. A aplicação não declara conformidade com uma lei ou norma específica.

Limites de segurança de formato (10.000 registros por entidade, até 10.000 alterações por transação, 12 MB na importação de interface) não são compromissos de desempenho. A aplicação lê e valida o agregado, envia snapshots completos e consulta alterações periodicamente; bases grandes exigirão paginação, filtros no servidor, mais índices e outra estratégia de sincronização. A lista de responsáveis tem limite de 60 nomes; isso não é uma capacidade simultânea de usuários testada.

Sem criptografia dos campos em repouso, MFA/SSO, alertas externos, SMTP, antivírus de uploads (não há upload), serviço de arquivos, sincronização offline, monitoramento de disponibilidade ou alta disponibilidade. O isolamento dos backups, disco e contas da infraestrutura é responsabilidade da implantação. O relógio operacional usa America/Sao_Paulo; timestamps técnicos são UTC.

## Referências primárias consultadas

Estas fontes orientam padrões e configuração; não representam uma certificação do código entregue.

- OWASP, gestão de sessões: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP, armazenamento de senhas: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- FastAPI, implantação com containers: https://fastapi.tiangolo.com/deployment/docker/
- SQLAlchemy, dialeto PostgreSQL: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- Python, API de backup SQLite: https://docs.python.org/3.13/library/sqlite3.html#sqlite3.Connection.backup
- PostgreSQL 17, pg_dump/pg_restore: https://www.postgresql.org/docs/17/app-pgdump.html e https://www.postgresql.org/docs/17/app-pgrestore.html
- Caddy, HTTPS automático: https://caddyserver.com/docs/automatic-https
