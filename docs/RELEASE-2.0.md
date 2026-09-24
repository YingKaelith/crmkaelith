# Release 2.0.0

## Entregue

Servidor FastAPI/SQLAlchemy; contas e perfis; armazenamento compartilhado; API de
transações; autorização no servidor; revisão de registros; repetição idempotente;
auditoria; ativação/recuperação; controles de sessão e CSRF; rotina de backup;
restauração integral SQLite; importação do JSON local; interface adaptada e
responsiva; iniciador Python; receita de publicação e testes reproduzíveis.

## Preservado

Clientes, comercial, propostas, projetos, tarefas/agenda, horas manuais, financeiro,
recorrências, relatórios, busca, exportação CSV, importação CSV de clientes,
configurações e dados fictícios identificados. Não foi criado um módulo vazio para
substituir os fluxos originais; o frontend foi conectado à API.

## Não entregue como serviço

Hospedagem, domínio, certificados reais, PostgreSQL homologado, banco com dados da
empresa, contas em provedores externos, monitoramento contratado, backup externo
agendado, integração WhatsApp/anúncios/bancos, MFA, portal do cliente e operação
assistida em produção. Nada foi contratado ou publicado em nome da empresa.

## Próxima liberação

A versão local permite testar e operar no computador com o servidor ativo. Para
acesso de vários computadores, a receita precisa de homologação no ambiente da
empresa. Os critérios verificáveis estão em PUBLICACAO.md, não dependem apenas de
um layout aprovado. Preserve o controle anterior até conferir a migração real.
