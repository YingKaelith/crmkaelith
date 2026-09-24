# Nexo Mono · Design e instalação

## Paleta

| Papel | Cor |
|---|---|
| Ações principais, navegação e marca | `#111111` |
| Texto principal | `#171717` |
| Cartões e superfícies | `#FFFFFF` |
| Fundo da aplicação | `#F7F7F7` |
| Texto secundário | `#666666` |
| Bordas e divisórias | `#E5E5E5` |

As tonalidades intermediárias também são neutras. A interface não usa um filtro global para disfarçar cores; tokens e valores literais foram adaptados. O tema permanece monocromático mesmo ao importar um backup antigo com destaque roxo. A configuração de cor livre foi substituída pela apresentação da paleta Mono. A propriedade antiga é preservada no formato dos dados para compatibilidade.

Status continuam identificados por palavras. Destaques usam bordas, preenchimentos, ícones e espessuras. Não é preciso interpretar vermelho, verde ou azul. Os gráficos mantêm legendas e os relatórios oferecem os valores em tabelas. Não foi realizada uma auditoria integral de acessibilidade.

## Comportamento como aplicativo

`web/manifest.webmanifest` define nome, ícones, escopo e abertura `standalone`. O cabeçalho HTML inclui manifesto, ícones Apple e cor do tema. `web/pwa.js` disponibiliza instruções e a instalação nativa quando o navegador oferece o evento correspondente.

A instalação depende do suporte do navegador e de uma origem segura (HTTPS na publicação; loopback é permitido para desenvolvimento). Não há APK, publicação em loja, aplicativo iOS nativo ou notificações push nesta entrega.

O CRM instalado usa as mesmas contas, permissões e base do site. Ele não prolonga a sessão indefinidamente. A política de sessão continua a da edição Equipe. O servidor online não depende de uma aba do administrador aberta.

## Sem conexão

O indicador “Servidor ativo” significa que uma requisição recente obteve resposta. Não significa que campos ainda em edição foram salvos. A aplicação consulta saúde da API, escuta falhas reais de requisição e avisa quando não consegue se conectar.

Dados de negócio não são persistidos no cache offline. O service worker guarda apenas a tela genérica `offline.html` e cinco ícones públicos. Requisições de API, login, alterações e backups não são armazenadas nem colocadas em fila. Se uma navegação falhar, é apresentada uma tela para reconectar; não uma cópia desatualizada do CRM.

**A edição exige internet.** Um formulário aberto é preservado na memória da aba durante uma falha, mas fechar ou recarregar a aba pode perder campos não salvos. Não há sincronização de alterações offline em segundo plano. A mensagem de gravação só é emitida após confirmação do servidor, mantendo o tratamento existente de transações sem resposta.

## Atualização

Uma nova versão do service worker não solicita recarregamento automático. Ela pode assumir após o fechamento das janelas antigas ou mediante comando explícito no diálogo de instalação. A atualização iniciada pelo usuário é bloqueada quando o CRM detecta campos alterados, gravação em andamento ou transação sem confirmação. Esse bloqueio não impede que uma pessoa force o fechamento da aba pelo navegador.

O cache usa um nome versionado. Em futuras releases, atualize também a constante `CACHE` em `web/sw.js`. A ativação remove apenas caches antigos com o prefixo do próprio Nexo. A API mantém `Cache-Control: no-store`; o cache explícito do service worker é limitado aos arquivos públicos enumerados.

## Validação

Consulte `RELATORIO-2.1.md`: fluxo visual por ponte HTTP, testes HTTP reais da API local e execução da lógica do service worker em ambiente simulado. A política do Chromium disponível bloqueou navegação nativa para loopback. A instalação real em Chrome/Edge/Safari e o funcionamento de cookies HTTPS públicos continuam sendo testes obrigatórios na implantação.
