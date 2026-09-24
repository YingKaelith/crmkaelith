# Relatório de evolução · Nexo CRM Mono 2.2 · Business Operating System

## 1. Objetivo deste incremento

Esta versão é o primeiro incremento do plano de evolução do CRM para um **Business Operating System**. A regra adotada foi preservar a aplicação existente, reutilizar suas entidades e mecanismos de segurança e introduzir primeiro os conceitos operacionais que dão visibilidade imediata sobre responsabilidade, prazo, bloqueio, dependência e próxima ação.

Ela **não reescreve o CRM** e **não cria módulos “v2” paralelos**.

## 2. Arquitetura encontrada

### Backend

- FastAPI.
- SQLAlchemy 2.
- SQLite para instalação local e configuração prevista para PostgreSQL em produção.
- Autenticação por sessão no servidor.
- Hash de senha Argon2.
- Proteções existentes de CSRF, origem, CSP, rate limiting e validação server-side.
- Revisão otimista por registro para impedir sobrescrita silenciosa de edição concorrente.
- Auditoria, idempotência e rotinas de backup.

### Frontend

- JavaScript sem framework, HTML e CSS próprios.
- PWA com cache restrito a recursos públicos; dados autenticados não são armazenados offline.
- Layout responsivo e navegação existente reutilizados.

### Modelo de dados atual

O banco usa tabelas relacionais para infraestrutura e segurança (`workspace`, `users`, `sessions`, `password_resets`, `audit_log`, `idempotency`, `rate_limits`) e uma tabela genérica `records` para os objetos de negócio.

Os tipos de negócio já existentes são:

- clientes;
- oportunidades;
- propostas;
- projetos;
- tarefas;
- contratos/recorrências;
- lançamentos financeiros;
- interações.

Cada registro de negócio possui JSON validado pelo domínio, revisão e chave própria. Por isso, este incremento conseguiu adicionar campos operacionais sem alterar a estrutura SQL.

## 3. Dados existentes e compatibilidade

A base fornecida foi tratada como dado a preservar. Uma **cópia** do SQLite real foi carregada e validada pela versão 2.2, sem regravar o arquivo original durante o teste.

A cópia validada continha clientes, propostas, projetos, tarefas e interações. Todos os registros anteriores continuam válidos porque os novos campos são opcionais e recebem comportamento compatível quando ausentes.

## 4. O que foi implementado

### Meu Dia

Nova área `#my-day`, construída sobre os registros existentes. Consolida:

- tarefas do usuário para hoje;
- tarefas atrasadas;
- “Bloqueado por mim”;
- “Bloqueado por outros”;
- follow-ups comerciais;
- aprovações representadas pelo status da tarefa;
- itens aguardando cliente;
- vencimentos financeiros disponíveis ao perfil.

### Próxima ação

Foi adicionada a clientes, projetos e tarefas. O objetivo é impedir que itens operacionais fiquem sem continuidade explícita.

### Saúde do cliente

Clientes agora suportam o indicador gerencial:

- Saudável;
- Atenção;
- Risco.

O valor é revisável pela equipe e não é calculado automaticamente neste incremento.

### Cliente 360

A ficha existente foi evoluída para **Cliente 360**, sem criar outro cadastro de cliente. Ela consolida:

- status e saúde;
- responsável;
- próxima ação e prazo;
- projetos ativos;
- tarefas atrasadas;
- aprovações pendentes;
- bloqueios;
- projetos e próximas ações;
- linha do tempo baseada nos registros já existentes;
- financeiro em aberto conforme permissões.

### Tarefas operacionais

Foram adicionados campos para:

- progresso;
- próxima ação;
- aprovador;
- participantes;
- dependências;
- responsável por desbloquear;
- motivo do bloqueio;
- data do bloqueio;
- coordenadas do Flow Map.

Os status de tarefa agora incluem:

- Não iniciada;
- Planejada;
- Em andamento;
- Em revisão;
- Aguardando aprovação;
- Aguardando cliente;
- Bloqueada;
- Concluída;
- Cancelada.

### Dependências e bloqueios

O servidor valida:

- existência da tarefa predecessora;
- proibição de autorreferência;
- dependências no mesmo projeto e cliente quando estes vínculos existem;
- ausência de ciclos no grafo de tarefas;
- motivo obrigatório ao marcar a tarefa explicitamente como bloqueada;
- indicação de pessoa ou dependência capaz de desbloquear.

A interface também impede exclusão direta de uma tarefa que ainda é dependência de outra.

### Flow Map

Nova área `#flow-map` que usa **os mesmos projetos e tarefas reais**.

Recursos deste incremento:

- projeto como nó raiz;
- tarefas como nós operacionais;
- conexões derivadas de `dependsOn`;
- status, responsável, prazo, progresso, próxima ação e bloqueio nos nós;
- zoom;
- centralização;
- rolagem/pan do canvas;
- arrastar nós;
- persistência das coordenadas no próprio registro da tarefa;
- abertura do projeto e edição da tarefa a partir do mapa;
- adaptação para celular sem criar overflow horizontal da página.

O nó não duplica a tarefa: ele é somente uma representação visual do registro existente.

## 5. Banco e migrations

### Decisão deste incremento

**Nenhuma migration SQL foi necessária.**

A razão é estrutural: os novos atributos pertencem a entidades já existentes e o modelo atual armazena os registros de negócio como JSON validado na tabela `records`. Criar novas tabelas apenas para estes campos introduziria duplicação e complexidade sem benefício imediato.

O `schema_version` do banco permanece `1`.

### Quando uma migration será necessária

Uma migration formal deverá ser criada quando a próxima fase introduzir estruturas que não cabem de forma segura no modelo atual, por exemplo:

- arquivos e versões de arquivos;
- relações de arquivo com múltiplas entidades;
- comentários polimórficos;
- aprovações com histórico próprio;
- handoffs e solicitações como objetos independentes;
- permissões granulares RBAC;
- organizações/workspaces múltiplos;
- automações e execuções;
- incidentes e monitoramento;
- workflow nodes/edges normalizados, caso o volume torne a representação atual insuficiente.

Essas mudanças devem elevar o `schema_version` e ser acompanhadas de migration reversível quando tecnicamente possível.

## 6. Segurança e compatibilidade preservadas

Continuam sendo reutilizados:

- autenticação e sessões existentes;
- validação no servidor;
- permissões por perfil;
- CSRF e same-origin;
- rate limiting;
- CSP;
- revisão otimista;
- auditoria;
- backup;
- política do PWA que não coloca dados de negócio no cache público.

Nenhuma senha, token ou credencial de terceiros foi adicionada aos registros de negócio.

## 7. Testes executados

### Regressão automatizada

- `python -m pytest -q`: **106 testes aprovados**.
- `node tests/test_service_worker.mjs`: **12 verificações aprovadas**.
- Testes específicos novos cobrem persistência dos campos operacionais, dependências válidas, dependência inexistente, dependência entre projetos, ciclo, autorreferência e regras de bloqueio.

### Navegador

O fluxo de navegador chegou a **30 verificações funcionais aprovadas**, incluindo:

- criação de projeto e tarefas;
- dependência real entre tarefas;
- Flow Map com persistência da posição do nó;
- Meu Dia;
- Cliente 360;
- operação compartilhada entre perfis;
- conflito de edição;
- restauração de backup;
- responsividade das 15 áreas em 390 px;
- ausência de erro JavaScript durante o fluxo.

O executor do ambiente demorou além do limite no encerramento do processo do Chromium após imprimir todas as verificações; por isso o relatório automático antigo de `tests/evidence/browser-results.json` não foi promovido como evidência desta versão. As verificações funcionais foram observadas como aprovadas antes do teardown.

### Compatibilidade com os dados fornecidos

Uma cópia de `data/nexo.db` foi lida pelo código 2.2 e passou pela validação completa do domínio com os registros existentes preservados.

## 8. O que ainda não foi implementado do plano mestre

O escopo mestre é muito maior que este incremento. Permanecem, entre outros:

- central de arquivos com object storage, versões e URLs assinadas;
- comentários polimórficos e menções;
- Inbox completa e notificações persistentes;
- aprovações como entidade própria e histórico de versões;
- handoffs formais e solicitações entre áreas;
- conteúdo, calendário editorial e criativos versionados;
- campanhas e métricas de Meta/Google/TikTok;
- desenvolvimento, backlog, sprints, deploys e QA;
- incidentes, infraestrutura e monitoramento;
- RBAC granular por permissão;
- portal do cliente;
- knowledge base e SOPs;
- templates/workflows completos;
- time tracking e capacidade;
- tags e custom fields globais;
- busca em linguagem natural;
- automações trigger/condição/ação;
- assistente de IA;
- realtime entre sessões.

## 9. Próxima sequência recomendada

1. **Arquivos + comentários + histórico operacional**: são a base de colaboração real entre os três sócios.
2. **Aprovações + handoffs + solicitações**: formalizam a passagem Estratégia → Criação → Operações.
3. **RBAC granular + Organization**: preparar segurança e estrutura para crescimento sem transformar prematuramente o produto em SaaS.
4. **Conteúdo/Criação + Tráfego + Desenvolvimento**: especializar as áreas sobre as entidades compartilhadas.
5. **Inbox, notificações, automações e realtime**: acelerar a operação depois que os objetos e permissões estiverem estáveis.

## 10. Critério usado

A versão 2.2 melhora a capacidade de responder rapidamente:

- o que preciso fazer;
- o que está atrasado;
- o que está bloqueado;
- o que estou bloqueando;
- quem é responsável;
- qual é a próxima ação;
- do que uma tarefa depende;
- como o trabalho se conecta dentro de um projeto.

Isso foi feito sobre a base existente, mantendo a Single Source of Truth e sem duplicar fisicamente clientes, projetos ou tarefas.
