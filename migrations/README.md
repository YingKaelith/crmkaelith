# Banco e evolução do esquema

Esta é a primeira versão do servidor (aplicação 2.0.0; `schema_version=1`).
`server/database.py` contém o esquema inicial, criado por SQLAlchemy no primeiro
boot, antes de aceitar requisições. Não há uma coleção fictícia de migrações:
nenhuma atualização de banco de uma versão anterior de servidor foi necessária.

Não use `create_all` como mecanismo de alteração de tabelas existentes. Uma
próxima mudança de colunas precisa de migração versionada, backup verificado e
ensaio em cópia do banco; esta entrega não inclui Alembic. A aplicação recusa um
`schema_version` diferente de 1 em vez de executar sobre um banco desconhecido.

A migração da versão HTML 1.0 é de DADOS, pela tela Configurações > restaurar JSON,
e não de tabelas SQL. Ela foi testada com a fixture fictícia incluída nos testes.

Entidades de infraestrutura: workspace, users, sessions, password_resets,
records, audit_log, idempotency e rate_limits. Cada registro de negócio fica na
tabela records com `kind`, `data` JSON, revisão e chave de unicidade. Não é um
modelo totalmente normalizado por entidade. Os vínculos entre registros de
negócio são conferidos pelo serviço na mesma transação. Edições SQL diretas
ignoram essas regras; não use o banco como interface de cadastro.
