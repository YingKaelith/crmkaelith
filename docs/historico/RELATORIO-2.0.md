# Relatório de testes — Nexo CRM Equipe 2.0.0

## Resultado da última execução

**68 testes Python aprovados, sem falhas, e 22 verificações de fluxo da interface aprovadas.** Não são resultados de produção nem garantia de ausência de defeitos.

A suíte Python inclui API, domínio, permissões, sessões, concorrência, backup integral SQLite e iniciador real. Tempo registrado no XML: 18.44 segundos. A suíte de interface usou Chromium 144.0.7559.96, Playwright e uma API HTTP real com banco temporário. Ambiente: Python 3.13.5, Linux. Testes executados em 19/09/2026 no horário de São Paulo; os timestamps técnicos em UTC podem indicar 20/09.

Evidência bruta: `tests/evidence/api-results.xml` e `tests/evidence/browser-results.json`. Capturas em PNG na mesma pasta. Todas as pessoas, empresas, valores e credenciais de teste são fictícios. O pacote não inclui um banco preenchido com dados reais ou credenciais da infraestrutura.

## Limitação importante dos testes de navegador

O Chromium disponível neste ambiente bloqueia navegação a URLs por política administrativa. A política não foi alterada. Por isso, o modo executado foi **bridge**, não uma navegação nativa completa: Playwright carregou o HTML, CSS e JavaScript do aplicativo, e uma ponte de transporte enviou as requisições a um servidor FastAPI real, com um cliente HTTP e jar de cookies independente por página.

Isso verifica formulários, cliques, renderização, comportamento de interface, comunicação com a API, persistência compartilhada e respostas de erro. **Não verifica o transporte de cookies pelo navegador, aplicação da CSP de página, TLS, DNS, impressão/downloads nativos ou acesso físico de dois computadores.** A suíte de API verifica atributos de cookies, origem, CSRF, cabeçalhos e autorização separadamente. O modo `--native` está fornecido para repetição em ambiente que permita navegação, mas não foi executado aqui.

## Cobertura do servidor

Autenticação com senha hash; criação única da empresa; limites de tentativa; exigência de sessão; origem e CSRF; logout; expiração absoluta/inatividade; troca e recuperação de senha; uso único de código; desativação e mudança de perfil; proteção do último administrador; operações por perfil; remoção de campos financeiros e comerciais; interações privadas; validação de datas, centavos, formatos e campos; rejeição de referências órfãs e cruzadas; aceite atômico; códigos de proposta e mensalidades únicas; conflitos por revisão; duas transações concorrentes reais sobre um registro; edições distintas; reenvio idempotente; histórico de auditoria; importação com revisão e cópia anterior; restauração de JSON preservando contas; rotas estáticas e limite de corpo.

Backup: JSON de negócio, cópia integral SQLite, integridade, SHA-256, permissões de arquivos, retirada de sessões da cópia, retenção de conjuntos, preservação de cópias anteriores a restauração, restauração offline com contas e histórico, bloqueios de confirmação/processo, rejeição de banco de outro formato e não publicação de manifesto em falha. Recuperação pelo console emite token auditado e de uso único.

O iniciador foi executado em subprocesso no Linux com dependências já instaladas (`--no-install --no-browser`), respondeu por HTTP, criou conta e realizou backup automático; encerrou removendo o marcador de processo. Não foi executada a instalação automática de pacotes pela internet em um computador limpo, nem os atalhos nativamente em Windows/macOS.

## Fluxos de interface aprovados

1. Instalação pela interface, criação do administrador e abertura do painel vazio.
2. Configurações persistidas no servidor e valor brasileiro 30.000 convertido corretamente.
3. Cadastro de cliente por formulário, persistido no banco.
4. Oportunidade híbrida, próximo contato obrigatório e valor em centavos.
5. Proposta com quantidade decimal, desconto e conteúdo HTML exibido como texto.
6. Aceite atualiza venda e cliente atomicamente, sem criar recebimento fictício.
7. Venda convertida em projeto com seis tarefas do serviço combinado.
8. Conclusão de tarefa salva no servidor e integrada ao progresso do projeto.
9. Agenda mensal com seis semanas e tarefas do projeto.
10. Liquidação manual de receita com data e forma de pagamento.
11. Geração de mensalidade e bloqueio de duplicação na mesma competência.
12. Administrador cria conta e gera código de ativação individual de uso único.
13. Sessão independente vê o mesmo cliente, sem módulo financeiro nem valor do projeto.
14. Alteração de tarefa pela Operação aparece na base compartilhada do administrador.
15. Conversa marcada privada pela interface é omitida da resposta da API para Operação.
16. Conflito real de edição recusa sobrescrita e mantém os campos não salvos no formulário.
17. Migração do backup local com prévia, confirmação e preservação de contas.
18. Auditoria exibida com autor, ações e campos alterados.
19. Treze áreas renderizadas em 390 px sem transbordamento horizontal da página.
20. Cadastro completo de cliente na janela de celular.
21. Saída pela interface revoga a sessão no servidor.
22. Fluxos exercitados sem erro JavaScript não tratado.

## Verificações complementares

`node --check web/app.js` e compilação Python concluídos sem erros. `deploy/compose.yaml` foi lido por parser YAML e os serviços foram inspecionados estaticamente. **Não houve execução de `docker compose up`, construção de imagens ou validação do schema pelo Docker Compose neste ambiente.** O arquivo de backup local fictício foi migrado pela interface; não há garantia de compatibilidade com dados de outro formato.

As telas administrativas foram percorridas em 390 px sem transbordamento horizontal do documento; tabelas/quadros podem rolar dentro de seus contêineres. Isso não equivale a teste em aparelho físico, Safari/iOS, Firefox ou a auditoria de acessibilidade. A impressão de propostas já existe no frontend, mas não foi validada como impressão/download nativo nesta rodada.

## Não executado ou não comprovado

PostgreSQL/psycopg em runtime, pg_dump/pg_restore, restauração PostgreSQL, Docker/Caddy, DNS/HTTPS, cookies/CSP em navegador nativo, duas máquinas físicas, instalação do zero por internet, envio externo (não implementado), backup externo agendado, pen test independente, varredura completa de vulnerabilidades, fuzzing extensivo, teste de carga ou de longa duração e certificações legais. Também não há teste de equivalência exaustiva de todos os relatórios e importações CSV em todos os casos possíveis.

A existência de 10.000 registros permitidos por entidade é um limite de entrada, não desempenho medido. A versão deve ser homologada no volume real antes da migração integral. Não confunda as 22 verificações encadeadas do roteiro de browser com 22 instalações independentes.

## Reproduzir em ambiente descartável

Na raiz do pacote, após instalar Python e criar um ambiente isolado:

```sh
python -m pip install -r requirements-test.txt
python -m pytest tests/test_api.py tests/test_backup.py tests/test_launcher.py -q --junitxml=tests/evidence/api-results.xml
node --check web/app.js
```

Para os fluxos visuais, disponibilize um executável Chromium e configure `CHROMIUM_PATH` quando não estiver em `/usr/bin/chromium`. Em Linux com Chromium nesse caminho:

```sh
python tests/browser_flow.py
# Em ambiente que permita navegação normal:
python tests/browser_flow.py --native
```

O modo padrão é a ponte descrita, não um teste nativo de ponta a ponta. O script cria servidor e banco temporários e os encerra ao terminar. Usa a porta 8876; o teste do iniciador usa 8879. Evite executar cópias desses scripts simultaneamente nas mesmas portas. O aplicativo local usa 8765. A integração visual usa credenciais fictícias definidas no teste, não existe uma senha padrão no produto.

## Casos Python executados

- `tests.test_api.test_setup_and_secure_cookie_headers` — aprovado.
- `tests.test_api.test_setup_cannot_be_reused` — aprovado.
- `tests.test_api.test_unauthenticated_cannot_access_any_data` — aprovado.
- `tests.test_api.test_wrong_origin_and_missing_csrf_blocked` — aprovado.
- `tests.test_api.test_login_uses_generic_error_and_no_password_echo` — aprovado.
- `tests.test_api.test_password_is_argon2id_not_plaintext` — aprovado.
- `tests.test_api.test_client_persisted_between_independent_sessions` — aprovado.
- `tests.test_api.test_allowed_create_update_and_server_timestamps` — aprovado.
- `tests.test_api.test_atomic_rollback_on_invalid_child` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[clients-name-]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[clients-email-invalid-email]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[clients-website-javascript:alert(1)]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[deals-nextAction-]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[deals-valueCents-1.25]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[deals-valueCents-True]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[deals-stage-unknown]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[projects-dueDate-2026-02-30]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[tasks-spentHours--2]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[contracts-dueDay-32]` — aprovado.
- `tests.test_api.test_invalid_fields_rejected_on_server[entries-valueCents-0]` — aprovado.
- `tests.test_api.test_lost_deal_needs_reason` — aprovado.
- `tests.test_api.test_future_payment_rejected_without_partial_write` — aprovado.
- `tests.test_api.test_same_record_optimistic_conflict` — aprovado.
- `tests.test_api.test_distinct_records_do_not_have_false_conflicts` — aprovado.
- `tests.test_api.test_concurrent_sessions_only_one_wins_same_record` — aprovado.
- `tests.test_api.test_idempotency_replay_does_not_duplicate` — aprovado.
- `tests.test_api.test_delete_referenced_client_blocked` — aprovado.
- `tests.test_api.test_cross_client_relation_rejected` — aprovado.
- `tests.test_api.test_accept_proposal_requires_atomic_sale_transition` — aprovado.
- `tests.test_api.test_discount_and_proposal_code_rules` — aprovado.
- `tests.test_api.test_recurring_duplicate_and_link_lock` — aprovado.
- `tests.test_api.test_role_write_boundaries[sales-entries]` — aprovado.
- `tests.test_api.test_role_write_boundaries[operations-deals]` — aprovado.
- `tests.test_api.test_role_write_boundaries[finance-proposals]` — aprovado.
- `tests.test_api.test_role_write_boundaries[operations-clients]` — aprovado.
- `tests.test_api.test_role_write_boundaries[finance-tasks]` — aprovado.
- `tests.test_api.test_hidden_modules_not_returned_by_api` — aprovado.
- `tests.test_api.test_operations_budget_redaction_and_preservation` — aprovado.
- `tests.test_api.test_finance_can_write_ledger_not_clients` — aprovado.
- `tests.test_api.test_activity_financial_visibility_and_idor` — aprovado.
- `tests.test_api.test_admin_audit_records_actor_and_fields` — aprovado.
- `tests.test_api.test_last_admin_guard` — aprovado.
- `tests.test_api.test_disable_user_revokes_existing_sessions` — aprovado.
- `tests.test_api.test_role_change_revokes_sessions_immediately` — aprovado.
- `tests.test_api.test_reset_token_one_time_and_new_password` — aprovado.
- `tests.test_api.test_expired_reset_token_rejected` — aprovado.
- `tests.test_api.test_change_password_rotates_current_session_revokes_others` — aprovado.
- `tests.test_api.test_logout_invalidates_server_session` — aprovado.
- `tests.test_api.test_absolute_and_idle_session_expiry` — aprovado.
- `tests.test_api.test_rate_limit_survives_clients` — aprovado.
- `tests.test_api.test_backup_excludes_auth_and_restores_business_links` — aprovado.
- `tests.test_api.test_import_legacy_visibility_conservative` — aprovado.
- `tests.test_api.test_restore_detects_change_after_preview` — aprovado.
- `tests.test_api.test_invalid_import_does_not_replace` — aprovado.
- `tests.test_api.test_settings_revision_conflict` — aprovado.
- `tests.test_api.test_unknown_and_polluting_properties_rejected` — aprovado.
- `tests.test_api.test_static_allowlist_and_host_check` — aprovado.
- `tests.test_api.test_request_size_limit` — aprovado.
- `tests.test_backup.test_backup_json_and_full_db` — aprovado.
- `tests.test_backup.test_business_only_backup` — aprovado.
- `tests.test_backup.test_backup_retention_preserves_recovery_files` — aprovado.
- `tests.test_backup.test_offline_full_restore_revokes_sessions_and_preserves_accounts` — aprovado.
- `tests.test_backup.test_restore_requires_explicit_confirmation_and_stopped_server` — aprovado.
- `tests.test_backup.test_restore_rejects_non_crm_database` — aprovado.
- `tests.test_backup.test_failed_backup_does_not_publish_manifest` — aprovado.
- `tests.test_backup.test_minimum_backup_retention` — aprovado.
- `tests.test_backup.test_console_recovery_issues_audited_one_use_token` — aprovado.
- `tests.test_launcher.test_launcher_http_setup_and_automatic_backup` — aprovado.

## Conferência do pacote distribuído

O ZIP foi extraído para uma pasta temporária, seus hashes foram conferidos e o iniciador extraído foi executado com dependências já presentes. O servidor respondeu por HTTP, criou administrador e base vazia, entregou o JavaScript, gerou conjunto de backup automático e encerrou sem deixar o marcador de processo. A integridade do ZIP passou. Esta verificação adicional não foi incluída na contagem de 68 testes Python. Evidência: `tests/evidence/package-validation.json`.
