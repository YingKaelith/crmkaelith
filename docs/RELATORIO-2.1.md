# Relatório · Nexo CRM Mono 2.1.0

## Estado da entrega

Interface monocromática e infraestrutura de PWA implementadas. Receita Render e iniciador de hospedagem incluídos. **Nenhum serviço público foi implantado, nenhuma conta de provedor foi acessada e nenhum custo foi autorizado.** A publicação externa continua pendente.

## Resultados desta execução

| Grupo | Resultado | O que representa |
|---|---|---|
| Python / pytest | **100 aprovados** | Testes de API e regras com SQLite, autenticação, permissões, conflitos, importação, backups locais, iniciador, recursos de PWA e configuração de hospedagem. |
| Fluxo Chromium | **27 verificações aprovadas** | Interface real com uma ponte HTTP entre o navegador e a API local. Não é navegação nativa nem teste de cookies HTTPS em navegador. |
| Service worker / Node | **12 aprovados** | Código real do worker executado em VM, com rede e CacheStorage explicitamente simulados. Não instala uma PWA. |
| Verificador de publicação | **13 verificações aprovadas localmente** | O novo iniciador `server.run` respondeu em loopback e o script somente de leitura verificou os recursos e o bloqueio de acesso não autenticado. |
| Blueprint | **Leitura YAML e asserções locais aprovadas** | Arquivo parseável, planos pagos declarados, origem privada do banco, token gerado, caminho do Dockerfile e health check configurados. Não validado pela API/schema da Render. |

Não some esses grupos como uma auditoria única ou certificação. Os escopos e níveis de simulação são diferentes.

## Ambiente e evidências

Python 3.13.5, Chromium 144.0.7559.96, Node 22.16.0 e Linux. Dependências Python já disponíveis nas versões fixadas no pacote. Todos os dados dos testes são fictícios. Não foram usados dados de clientes da empresa.

Evidências em `tests/evidence/2.1/`: `python-results.xml`, `browser-results.json`, `service-worker-results.json`, `http-check-local.json`, `blueprint-local-checks.json` e capturas da interface. Os resultados da edição anterior ficam em `tests/evidence/2.0/` como histórico, não como evidência da 2.1.

## Limitação de navegador observada

Foi tentado `python tests/browser_flow.py --native`. A navegação para loopback foi bloqueada pelo Chromium do ambiente com `ERR_BLOCKED_BY_ADMINISTRATOR`, antes de abrir o aplicativo. A evidência dessa tentativa está em `native-browser-blocked.txt`.

O fluxo aprovado usa `set_content` para carregar os arquivos reais de interface e uma ponte HTTP para a API temporária. O login e as alterações atingem a API real, mas o navegador não gerencia o transporte e os cookies como faria na publicação. O service worker não é registrado nativamente nesse modo. Erros de History API específicos da origem `about:blank` da ponte podem ser tratados como mensagens de interface; não foram usados para alegar funcionamento nativo. As capturas de login foram feitas após limpar mensagens transitórias.

## Verificações de interface

1. Instalação pela interface, criação do administrador e abertura do painel vazio
2. Configurações persistidas no servidor e valor brasileiro 30.000 convertido corretamente
3. Cadastro de cliente por formulário, persistido no banco
4. Oportunidade híbrida, próximo contato obrigatório e valor em centavos
5. Proposta com quantidade decimal, desconto e conteúdo HTML exibido como texto
6. Aceite atualiza venda e cliente atomicamente, sem criar recebimento fictício
7. Venda convertida em projeto com seis tarefas do serviço combinado
8. Conclusão de tarefa salva no servidor e integrada ao progresso do projeto
9. Agenda mensal com seis semanas e tarefas do projeto
10. Liquidação manual de receita com data e forma de pagamento
11. Geração de mensalidade e bloqueio de duplicação na mesma competência
12. Administrador cria conta e gera código de ativação individual de uso único
13. Sessão independente vê o mesmo cliente, sem módulo financeiro nem valor do projeto
14. Alteração de tarefa pela Operação aparece na base compartilhada do administrador
15. Conversa marcada privada pela interface é omitida da resposta da API para Operação
16. Conflito real de edição recusa sobrescrita e mantém os campos não salvos no formulário
17. Migração do backup local com prévia, confirmação e preservação de contas
18. Backup antigo com destaque roxo mantém o tema Mono; cores renderizadas são neutras
19. Instruções de instalação abrem e distinguem aplicativo de hospedagem
20. Atualização do aplicativo é bloqueada enquanto há campos não salvos
21. Aviso de desconexão e recuperação da rede preservam o formulário em edição
22. Auditoria exibida com autor, ações e campos alterados
23. Treze áreas renderizadas em 390 px sem transbordamento horizontal da página
24. Instruções de instalação cabem em 390 px com rolagem e fechamento acessível
25. Cadastro completo de cliente na janela de celular
26. Saída pela interface revoga a sessão no servidor
27. Fluxos exercitados sem erro JavaScript não tratado

## Verificações da lógica offline

1. Instalação não força ativação nem recarregamento
2. Cache inicial limitado a seis recursos públicos
3. Ativação limpa somente versões antigas do próprio cache
4. Leituras autenticadas não são interceptadas nem armazenadas
5. Login e alterações não entram em fila nem em cache
6. Tokens em consulta não entram no cache público
7. Navegação online vem da rede, não de cópia de dados
8. Falha de rede apresenta a tela offline genérica
9. API navegada diretamente nunca recebe uma resposta offline fictícia
10. Ícone público continua disponível offline
11. Navegar não adiciona documentos ou dados de usuário ao cache
12. Atualização só é ativada mediante mensagem explícita

## Revisão visual

Foram examinadas as capturas de painel desktop, login desktop, login mobile e instruções de instalação em janela estreita. Foram corrigidos o estilo de campos de senha, o espaçamento do título mobile e a rolagem das instruções. A checagem por estilos calculados confirmou cores neutras após importar um backup antigo com destaque roxo. Isso não constitui uma auditoria integral de acessibilidade.

## Ainda não executado

- Build e execução Docker; instalação do driver psycopg e integração PostgreSQL.
- Validação do Blueprint pela Render, criação de serviços, cobrança e domínio público.
- Certificado HTTPS real, cookies de produção em navegador, DNS e mudança de domínio.
- Instalação de PWA em Chrome/Edge/Safari ou celular físico, atualização entre duas releases realmente instaladas e cache em navegador nativo.
- Recuperação gerenciada do PostgreSQL, exportação integral do provedor e recuperação de desastre externo.
- Teste de carga, pentest, auditoria integral de acessibilidade ou conformidade e disponibilidade contínua em produção.

O teste local não elimina essas etapas. A receita inicial tem uma instância de aplicação e um banco primário; não é uma configuração redundante nem garantia de 100% de disponibilidade.

## Critérios de homologação da implantação

Criar dois usuários em dispositivos diferentes, testar acessos permitidos e bloqueados, confirmar a persistência após reinício do serviço, acessar pelo celular com o computador de instalação desligado, instalar a PWA real, testar a tela offline sem expor dados, confirmar a atualização sem perda de edição e restaurar uma cópia do PostgreSQL em outra instância. Definir responsáveis por alertas, contas do provedor, pagamento e backups externos.

## Reproduzir

```bash
pip install -r requirements-test.txt
python -m pytest -q --junitxml=tests/evidence/2.1/python-results.xml
node tests/test_service_worker.mjs
# Use NEXO_BROWSER_OUTPUT para indicar onde salvar novas capturas.
python tests/browser_flow.py
# Em ambiente que permita navegação nativa:
python tests/browser_flow.py --native
# Somente leitura, depois da publicação:
python scripts/verificar_publicacao.py https://SEU-ENDERECO.onrender.com
```

Os testes de fluxo criam um servidor e base temporários. Nunca redirecione testes de escrita a uma base operacional. O verificador de publicação é separado e não faz login nem modifica dados.

## Conferência do pacote de entrega

O ZIP foi extraído em uma pasta nova. Todos os hashes da cópia extraída foram conferidos, três arquivos JavaScript passaram pela checagem de sintaxe, e `python -m server.run` iniciou o aplicativo extraído com uma base SQLite temporária. O verificador somente de leitura aprovou as 13 checagens HTTP nessa cópia. Isso usa as dependências já disponíveis no ambiente e não é um teste de instalação Docker ou de hospedagem pública.

O guia e a página de paleta também foram renderizados em 1440 e 390 pixels: imagens carregadas, sem transbordamento horizontal de página e sem erros JavaScript. As capturas e os resultados estão em `tests/evidence/2.1/`.
