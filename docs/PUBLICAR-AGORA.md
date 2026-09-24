# Nexo CRM Mono 3.0 · Publicação para a equipe

**Objetivo:** um endereço HTTPS que continue disponível quando o computador do administrador estiver desligado. O aplicativo fica em um servidor de hospedagem; cada pessoa entra com sua própria conta. Instalar o ícone no celular é opcional e não substitui a hospedagem.

**Estado da entrega:** código e configuração preparados; nenhuma conta de provedor foi criada, nenhuma cobrança foi autorizada e nenhum endereço público foi publicado nesta entrega. Docker, PostgreSQL hospedado e HTTPS público precisam ser homologados na conta da empresa.

## Rota principal: Render com serviço web e PostgreSQL pagos

O arquivo `render.yaml`, na raiz, descreve os dois recursos. O serviço web usa Docker e a API existente; o banco é separado do sistema de arquivos do contêiner. Não selecione **Static Site**: esta aplicação precisa executar o servidor Python.

A configuração inicial escolhe uma instância web `0.5c-512mb`, um PostgreSQL `0.1c-256mb` com 5 GB, uma instância de aplicação e a região `virginia` para ambos. É um ponto de partida para piloto de equipe pequena, não um dimensionamento validado por carga. Os identificadores foram conferidos na documentação oficial em setembro de 2026. Confira a oferta vigente no painel antes de aprovar.

**Há custo recorrente de hospedagem, banco e eventualmente armazenamento/tráfego. O preço não está incluído no pacote. Confira o total calculado pelo provedor antes de confirmar a criação.** Nenhuma senha real está no código.

### 1. Colocar o código em uma conta da empresa

Extraia o ZIP e envie o **conteúdo da pasta** a um repositório Git privado da empresa. Não envie apenas o ZIP. Na raiz do repositório devem aparecer `render.yaml`, `README.md`, `requirements.txt`, `server/`, `web/` e `deploy/`.

Não envie `data/`, backups reais, `.env`, senhas, links de ativação de usuários ou chaves privadas. O `.gitignore` incluído reduz o risco em envios via Git, mas não impede que arquivos sejam enviados manualmente por engano. Confira os arquivos antes de publicar.

### 2. Criar a infraestrutura no provedor

Entre no painel da Render com uma conta controlada pela empresa. Abra **New → Blueprint**, conecte o repositório privado e use `render.yaml`. Revise os dois recursos e os custos. Só então confirme a criação.

O Blueprint liga a variável `DATABASE_URL` à conexão privada do PostgreSQL e gera `NEXO_SETUP_TOKEN`. O acesso externo direto ao banco fica desabilitado pela lista `ipAllowList: []`. O aplicativo recebe sua origem pública de `RENDER_EXTERNAL_URL`; não é preciso adivinhar o subdomínio atribuído pelo provedor.

A receita deixa a publicação automática a cada alteração de código **desligada**. Depois do primeiro deploy, novas versões devem passar por testes e ser publicadas manualmente pelo painel. Isso evita colocar uma alteração não revisada em produção apenas porque foi enviada ao repositório.

### 3. Abrir o endereço e criar a primeira conta

Aguarde a conclusão do deploy e o serviço responder à verificação de saúde. Abra o endereço HTTPS mostrado no painel do serviço web.

Na área de variáveis de ambiente do serviço, consulte **NEXO_SETUP_TOKEN**. Digite esse valor somente na tela de primeira instalação do seu próprio CRM. Cadastre a empresa, seu nome, e-mail e uma senha exclusiva. Não existe senha padrão.

O token é um segredo da instalação. Não envie ao chat, não publique no repositório e não distribua à equipe. Os outros integrantes recebem contas próprias, não o token administrativo.

### 4. Validar antes de colocar dados reais

No computador da pessoa responsável pela instalação, execute este teste somente de leitura:

```bash
python scripts/verificar_publicacao.py https://SEU-ENDERECO.onrender.com --output verificacao-publicacao.json
```

Substitua o endereço ilustrativo pelo endereço real do painel. O teste confere a página, a API, o manifesto, os ícones, os cabeçalhos e o bloqueio de dados sem login. Ele **não** comprova disponibilidade futura, segurança completa, backup restaurável ou instalação nativa.

Em seguida, faça um piloto com dados fictícios: entre como administrador, cadastre um cliente, crie outra conta em **Equipe e acessos**, envie o link de ativação por canal privado e abra essa conta em outro dispositivo. Confira acesso compartilhado e restrições de perfil. Desligue o computador usado na instalação e acesse o CRM pelo celular em outra rede. Esse último teste demonstra que o serviço não depende daquele computador.

### 5. Conferir backups e recuperação

O Blueprint usa `NEXO_BACKUP_MODE=managed`. Isso informa ao CRM que a política de recuperação deve ser conferida no provedor; **não é uma confirmação automática de que seus backups foram auditados**.

O PostgreSQL pago da Render tem recuperação gerenciada, conforme a política vigente do plano. Abra a seção de recuperação do banco, confirme a janela disponível e faça uma restauração de teste em **outra instância** antes de confiar dados importantes. Não restaure sobre a base ativa para experimentar.

A pasta `/tmp/nexo` do aplicativo é temporária. As cópias JSON geradas antes de uma importação podem desaparecer em reinícios e deploys; não são um arquivo permanente de recuperação. Os registros principais e contas ficam no PostgreSQL, não nessa pasta. Mantenha também cópias externas protegidas. O JSON exportado pelo CRM guarda negócios e vínculos; não inclui contas, senhas ou auditoria. Para recuperação integral, use a cópia do PostgreSQL.

### 6. Liberar para a equipe e instalar como aplicativo

Crie cada usuário em **Equipe e acessos**, escolhendo o perfil adequado. Envie a cada pessoa seu link de ativação, por canal privado. Depois da ativação, todos utilizam o mesmo endereço do CRM.

No próprio sistema, o botão **Instalar aplicativo** explica a instalação. Em Chrome/Edge compatíveis, poderá aparecer um botão nativo; em iPhone/iPad, o guia explica o menu Compartilhar do Safari. O modo instalado abre com ícone e janela própria onde houver suporte. **Nenhum integrante precisa instalar Python ou manter um terminal aberto.** Python continua necessário apenas para executar o servidor em modo local, não para acessar o serviço publicado.

## Disponibilidade: o que foi e não foi preparado

A receita usa recursos pagos, sem a suspensão por inatividade do serviço web Free. O endpoint `/api/health` consulta o banco e está configurado para as verificações do provedor. A documentação da Render descreve reinicialização de instâncias que falham repetidamente nos health checks.

Isso é infraestrutura de operação contínua, **não garantia de 100% de disponibilidade**. A configuração inicial tem uma instância de aplicação e um banco primário, sem redundância multirregião. Falhas, manutenção, limites de capacidade ou falta de pagamento podem afetar o serviço. Configure alertas para um responsável, acompanhe espaço em disco e confirme periodicamente a recuperação dos backups. Um monitor externo adicional não foi contratado nem configurado nesta entrega.

Não tente manter uma hospedagem gratuita acordada com acessos artificiais. O plano Free da Render tem restrições incompatíveis com esse objetivo, incluindo suspensão após inatividade e limitações no banco.

## Domínio próprio, opcional

Primeiro valide o endereço HTTPS fornecido pelo provedor. Depois, cadastre um único domínio canônico, configure DNS conforme o painel e confirme o certificado. Defina `NEXO_ORIGIN` com a origem completa, por exemplo `https://crm.suaempresa.example`, sem caminho, parâmetros ou barra final, e publique novamente.

A validação de origem é deliberadamente restrita. Ao mudar o domínio, endereços alternativos podem ser recusados pelo servidor; atualize links e reinstale o atalho/PWA a partir do domínio definitivo. Não libere origens curinga para contornar erros de configuração. A receita não cobre múltiplos domínios simultâneos.

## Migração dos seus dados anteriores

Exporte um backup JSON no Nexo anterior. Na nova instância, crie o administrador e use **Configurações → Importar / restaurar**. Confira os totais antes de confirmar. **A importação substitui os registros de negócio da instância de destino; não mescla bases.** Contas da nova instância e sua auditoria são preservadas. Notas antigas sem classificação de visibilidade são restritas ao administrador.

Esse caminho não transfere contas e senhas de SQLite para PostgreSQL. Recrie as contas da equipe e entregue novos links de ativação. Uma atualização de código sobre um PostgreSQL 2.0 já existente não exige nova estrutura de tabelas nesta edição, mas continua exigindo backup integral e homologação antes da troca.

## Alternativa técnica: servidor próprio

O pacote preserva `deploy/compose.yaml`, PostgreSQL, Caddy e a rotina de backup da edição anterior. Essa opção exige administração do servidor, DNS, firewall, cópias externas e atualizações. Consulte `PUBLICACAO.md`. A nova rota Render dispensa a administração do sistema operacional, mas não dispensa validação e responsabilidade sobre contas, dados e pagamentos.

## Fontes oficiais conferidas nesta entrega

- Blueprint e campos de configuração: https://render.com/docs/blueprint-spec
- Origem pública atribuída ao serviço: https://render.com/docs/environment-variables
- Restrições da modalidade Free: https://render.com/docs/free
- Health checks e reinicialização: https://render.com/docs/health-checks
- Recuperação do PostgreSQL: https://render.com/docs/postgresql-backups
- Preços vigentes para conferência no painel: https://render.com/pricing
- Instalação de aplicativos web: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable

Os arquivos descrevem uma implantação proposta. A aceitação do Blueprint pelo provedor, a cobrança, o deploy real e o teste em dispositivos pertencem à etapa de homologação externa.
