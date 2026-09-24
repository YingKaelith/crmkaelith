# Nexo CRM Mono 2.1.0

## Alterações

- Identidade monocromática aplicada ao CRM, login, propostas e telas mobile.
- Paleta editável documentada em `design/`, com estados identificados por texto.
- Manifesto, ícones e instruções para instalação como aplicativo web.
- Aviso de desconexão e tela offline genérica; sem cache de dados de clientes.
- Atualizações do aplicativo pedem confirmação e respeitam formulários não salvos.
- Receita de hospedagem Render paga + PostgreSQL, sem dependência do computador do usuário.
- Validação de configuração de produção, origem HTTPS e modo de backup gerenciado.
- Verificador de publicação somente de leitura e guia de homologação.

## Estado

A versão foi executada com SQLite. A infraestrutura pública ainda não foi criada. Docker, PostgreSQL hospedado, HTTPS real e instalação nativa da PWA precisam de homologação externa. Consulte `docs/RELATORIO-2.1.md` e `docs/PUBLICAR-AGORA.md`.

Nenhum dado real, senha padrão, assinatura de hospedagem ou certificado privado está incluído. O pacote não instala as dependências de terceiros: o iniciador ou Docker deve obtê-las conforme os arquivos de requisitos.
