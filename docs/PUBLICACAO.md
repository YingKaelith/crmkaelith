> **Nota da edição 2.1:** este documento descreve a base Equipe e a implantação local/servidor próprio. A nova rota Render e suas diferenças de armazenamento estão em `PUBLICAR-AGORA.md`; PWA e tema estão em `MONO-E-APLICATIVO.md`; resultados atuais em `RELATORIO-2.1.md`.

# Publicação da versão de equipe

**Situação desta entrega:** código de publicação incluído; PostgreSQL, construção das imagens Docker, certificados e acesso por domínio não foram executados no ambiente de desenvolvimento usado aqui. Nenhuma conta externa foi criada, nenhum serviço foi contratado e não existe uma URL pública entregue. Faça a homologação abaixo antes de usar dados reais.

## Arquitetura de publicação fornecida

Navegadores → Caddy/HTTPS → aplicação FastAPI → PostgreSQL. Um serviço separado gera backups. A interface e a API usam a mesma origem; não há CORS aberto. Uma instalação atende uma empresa. O Compose não publica a porta do banco ou da aplicação; somente 80/443 do proxy. É uma instalação de nó único, sem alta disponibilidade, failover, fila distribuída ou réplicas.

É necessário um servidor controlado pela empresa com Docker Engine e Compose, domínio/subdomínio, DNS configurável, portas 80/443 acessíveis para o proxy e armazenamento persistente. O responsável técnico deve conferir os requisitos do provedor, firewall, atualizações, capacidade e custos; esta entrega não estima preços nem contrata recursos.

O código de servidor é Python, não uma função serverless. **Não basta enviar a pasta web para uma hospedagem de arquivos.** A API e o banco precisam permanecer disponíveis.

## Preparar sem dados reais

Na raiz do pacote, execute:

```sh
python3 scripts/preparar_deploy.py
```

O assistente pergunta domínio e e-mail técnico e gera `deploy/.env` com segredos aleatórios. Não sobrescreve um arquivo existente. Guarde-o em um cofre controlado pela empresa. No Windows, confira as permissões do arquivo explicitamente. Não envie o `.env` completo em conversas, tickets ou commits.

O domínio é apenas o nome, por exemplo `crm.suaempresa.com.br`, sem `https://`, caminho ou porta. O script não registra domínio, não ajusta DNS e não publica nada. Configure A/AAAA no DNS para o servidor conforme seu provedor. Remova entradas IPv6 incorretas em vez de presumir que o certificado funcionará.

Em `deploy`:

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 app backup proxy
```

A construção exige acesso a registros de imagens e repositórios de pacotes. Imagens usam séries principais (`python:3.13`, `postgres:17`, `caddy:2`); não estão fixadas em digest nem foram reproduzidas neste ambiente. Antes de liberação, revise versões, execute testes, registre os digests homologados e mantenha uma rotina de atualização. As dependências Python principais estão fixadas; não há lock completo de todas as dependências transitivas.

O script `01-init-database.sh` cria a conta `nexo` sem privilégios de superusuário para a aplicação e permite a criação das tabelas no esquema público. A conta `postgres` tem segredo separado. **O script só roda em um volume novo.** Alterar o `.env` não troca automaticamente senhas em um banco já inicializado: planeje rotação SQL e atualização das conexões.

Caddy pode obter certificados e fazer redirecionamento HTTPS quando domínio, DNS e conectividade estão corretos. Não foi verificado um certificado real nesta entrega. Consulte a documentação oficial: https://caddyserver.com/docs/automatic-https

A aplicação exige `NEXO_ENV=production`, origem HTTPS e um banco não SQLite no caminho de produção. O Compose fornece PostgreSQL. Cookies de produção usam `Secure`, `HttpOnly` e `SameSite=Strict`, e o servidor confere a origem configurada. Não desative essas restrições para mascarar erro de domínio.

## Primeiro acesso

Abra o domínio no navegador, confira HTTPS sem erro e crie o primeiro administrador usando o valor de `NEXO_SETUP_TOKEN` do cofre/arquivo local. Escolha senha exclusiva; não reutilize o código de instalação como senha. Não existe registro público depois da instalação.

Crie uma conta para cada pessoa em Equipe e acessos. Não compartilhe a conta administradora. Ativação/recuperação usa links privados válidos por uma hora; não há SMTP. Os links são credenciais temporárias: entregue por canal privado e não os coloque em capturas públicas.

## Critérios de liberação: execute, não apenas marque

| Verificação | Evidência exigida |
|---|---|
| Duas contas em computadores/navegadores diferentes | Cliente criado em uma sessão aparece na outra após atualização |
| Acesso por perfil | Operação não lê valores do projeto pela API; Comercial não consulta lançamentos; Financeiro não consulta propostas |
| Edições simultâneas | Registros distintos salvam; mesma revisão desatualizada retorna conflito sem sobrescrever |
| Sessão real | Login, logout, expiração, alteração de senha e desativação funcionam via HTTPS e cookies do navegador |
| CSRF e origem | Requisições de outra origem ou sem token de proteção não alteram registros |
| Fluxo comercial | Proposta → aceite → projeto → tarefas → receita, sem confundir aceite com recebimento |
| Mensalidade | Duas tentativas da mesma competência não geram cobranças duplicadas |
| Backup PostgreSQL | Conjunto completo gerado, copiado externamente e restaurado em banco novo de teste |
| Continuidade | Reiniciar containers preserva registros e contas; indisponibilidade de banco gera erro, não confirmação falsa |
| Observabilidade | Pessoa responsável monitora falhas da API, idade dos backups, espaço, HTTPS e custos |

O relatório incluído não substitui essas verificações no ambiente real. `tests/browser_flow.py --native` é fornecido para uso local com Chromium sem restrição de navegação; ele cria seu próprio banco de teste, não valida diretamente um domínio externo. Para a publicação, execute os mesmos cenários manualmente ou adapte uma suíte separada a uma instalação descartável. Nunca direcione os testes à base real da empresa.

## Backups e manutenção

O serviço de backup tenta gerar um conjunto ao iniciar e a cada seis horas. A aplicação mostra a data do último manifesto concluído; isso não é um monitor externo. Configure retirada para outro armazenamento e ensaie a restauração do PostgreSQL conforme `BACKUPS.md`. Defina quem pode restaurar, quem guarda as credenciais e quem decide a perda de dados aceitável.

**Não execute `docker compose down -v` em produção**: volumes são persistência. Para reiniciar, use `docker compose restart`. Antes de atualizar, gere e confira backup, teste a nova versão em cópia isolada, leia `migrations/README.md` e defina retorno. A versão inicial não inclui migrações automáticas de tabelas futuras.

O limite por IP usa o endereço observado diretamente pelo servidor. Nesta receita, a aplicação não confia em cabeçalhos encaminhados; as tentativas vistas atrás do proxy compartilham o limite de 40/15 minutos, além do limite por conta de 12/15 minutos. Para equipes ou cenários maiores, um profissional deve configurar confiança somente no proxy conhecido e testar proteção contra falsificação; não habilite confiança irrestrita em cabeçalhos vindos da internet.

Não há MFA, detecção externa de intrusão, redundância, monitoramento contratado, pen test independente ou promessa de conformidade. Uma revisão de segurança e operação continua necessária antes de tratar dados sensíveis em produção.
