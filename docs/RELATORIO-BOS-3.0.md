# Nexo CRM Mono 3.0 · Business Operating System

## Escopo desta entrega

A versão 3.0 amplia a base 2.2 sem reescrever o monólito. O sistema continua usando FastAPI, SQLAlchemy, o agregado `records`, autenticação por sessão, revisão otimista, auditoria, backups e PWA existentes.

### Núcleo preservado

- clientes, oportunidades, propostas, projetos, tarefas, recorrências, financeiro e interações;
- Meu Dia, Cliente 360 e Flow Map;
- autenticação, recuperação de acesso, perfis, CSRF/origin, CSP, rate limiting e auditoria;
- SQLite local e PostgreSQL em produção;
- backup/importação compatível com backups 2.x.

### Domínios BOS persistentes adicionados

A mesma tabela `records` passa a suportar, com validação server-side e revisão/auditoria: estratégias, metas, KPIs, conteúdos, campanhas, aprovações, solicitações, handoffs, reuniões, decisões, base de conhecimento, processos/SOPs, incidentes, automações, integrações, domínios, hospedagem, desenvolvimento, bugs, deploys, change requests, arquivos, comentários, notificações, apontamentos de horas e checklists.

Todos aceitam vínculos opcionais a cliente/projeto, responsável, status, prioridade, prazo, próxima ação, tags, visibilidade e dados estruturados específicos. O campo estruturado rejeita chaves com aparência de senha, token, segredo, API key ou private key.

### Central de arquivos

- upload real de arquivos até 16 MB na edição monolítica;
- allowlist de MIME;
- bytes em `data/uploads`, fora do banco;
- metadados no `records`;
- download autenticado;
- vínculo a cliente/projeto e visibilidade;
- auditoria do upload.

Para arquivos maiores ou operação horizontal, a recomendação continua sendo Object Storage compatível com S3/R2/Supabase Storage.

### Quatro visões

O topo permite alternar entre:

1. Visão geral;
2. Comercial & estratégia;
3. Criação & conteúdo;
4. Tráfego, operações & tecnologia.

As visões filtram a navegação, não criam bancos paralelos. A preferência de interface é lembrada localmente por usuário; nenhum dado de negócio é gravado no navegador.

### Portal do cliente

Existe o perfil `Cliente`, obrigatoriamente vinculado a um cliente específico por `user_scopes`. O isolamento é aplicado no servidor. O portal recebe apenas dados daquele cliente nos módulos autorizados e pode criar aprovações, solicitações, comentários e arquivos vinculados ao próprio cliente. Arquivos do portal precisam de visibilidade `client`.

### Busca e colaboração

A busca global percorre todos os módulos autorizados. A área Inbox & colaboração consolida solicitações, handoffs, aprovações, reuniões, decisões, comentários e notificações. As mudanças continuam sincronizadas por polling seguro, sem cachear respostas autenticadas no service worker.

## Compatibilidade e migração

A expansão dos domínios operacionais usa o modelo JSON validado já existente, portanto não cria tabelas paralelas como `tasks_v2`. A única adição relacional necessária é `user_scopes`, para garantir isolamento do portal de cliente. A migration está em `migrations/0002_business_os_3.sql`.

Backups 2.x sem os novos arrays são normalizados pelo servidor para listas vazias durante a importação.

## Validação executada

- 112 testes Python aprovados;
- 12 testes do service worker aprovados;
- sintaxe Python e JavaScript validada;
- base SQLite fornecida validada em modo somente leitura pelo domínio 3.0;
- fluxo visual legado executado até 25 verificações aprovadas antes do limite externo de execução, sem falha funcional registrada até esse ponto.

## Limites técnicos explícitos

Integrações com Meta Ads, Google Ads, TikTok Ads, WhatsApp, e-mail, Slack, Teams, provedores de monitoramento e IA dependem de credenciais/serviços externos e não são habilitadas automaticamente. A versão 3.0 entrega os registros, estados e arquitetura para essas integrações, mas não inventa tokens nem executa ações externas sem configuração humana.

2FA também não é ativado automaticamente nesta base porque não há provedor/segredo TOTP configurado. O sistema mantém sessão segura, Argon2, CSRF/origin e recuperação individual por token de uso único.

A edição monolítica não pretende substituir contabilidade, assinatura eletrônica, emissão fiscal, provedor de pagamentos ou Secret Manager.
