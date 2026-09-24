> **Nota da edição 2.1:** este documento descreve a base Equipe e a implantação local/servidor próprio. A nova rota Render e suas diferenças de armazenamento estão em `PUBLICAR-AGORA.md`; PWA e tema estão em `MONO-E-APLICATIVO.md`; resultados atuais em `RELATORIO-2.1.md`.

# Operação e migração

## Sua primeira hora de uso

Comece com uma base vazia e dados fictícios. Em Configurações, ajuste empresa, contatos, responsáveis, meta e cor. Responsáveis são nomes para atribuição; não limitam acesso à carteira. Criar uma conta pode acrescentar seu nome à lista de responsáveis; mudar o nome de uma conta não renomeia atribuições antigas automaticamente.

Simule um contrato mensal de marketing e um projeto avulso de programação. Para cada um, cadastre cliente, oportunidade e proposta. Registre aceite, crie projeto e tarefas, registre receita e liquide com a data efetiva. No contrato mensal, gere a competência explicitamente. Confira valores e vínculos antes de introduzir registros reais.

## Clientes e conversas

Mantenha um cadastro por cliente; a mesma empresa pode ter vários contatos informados no campo de observações, oportunidades, projetos e mensalidades. O modelo principal possui uma pessoa de contato por cadastro, não um catálogo de contatos múltiplos com entidade própria. Documento/telefone não são verificados em órgãos externos.

Na ficha, **Registrar conversa** permite selecionar a visibilidade: compartilhada, Comercial, Financeiro ou privada, conforme seu perfil. Administradores podem consultar todas; uma interação privada não é enviada aos outros perfis pela API. Novas conversas manuais do administrador começam privadas; selecione “Todos os perfis” quando a equipe realmente precisar delas. Conversas automáticas de vendas e financeiro recebem classificação pelo servidor. Notas gerais do cliente, descrições de projetos e tarefas são compartilhadas entre quem consulta o respectivo módulo: não use esses campos para senhas, credenciais ou informação reservada a outra área.

## Comercial e propostas

Uma oportunidade aberta deve ter responsável operacionalmente definido, próximo contato e data; a aplicação exige próxima ação e data. A oportunidade pode ser marketing, programação, combinada ou outro serviço, e ter cobrança mensal, por projeto ou por horas. O valor da oportunidade não é anualizado automaticamente.

Em uma proposta, registre quantidade, valor unitário, desconto, escopo e exclusões. A interface calcula o total; o servidor confere os valores e a coerência do aceite. Aceitar uma proposta ativa o cliente e atualiza a oportunidade vinculada na mesma transação. O envio, o aceite e a assinatura são registros manuais, não comprovação eletrônica de consentimento. A impressão usa o recurso do navegador; não existe serviço de geração de PDF no servidor.

Uma venda ganha pode criar um projeto e seis tarefas de modelo. Esse checklist é um ponto de partida, não uma metodologia obrigatória. Selecione os modelos e revise os prazos. Encerrar tarefas não encerra automaticamente um projeto. Não exclua clientes vinculados a projetos, propostas ou pagamentos: a validação impede registros órfãos. Prefira inativar quando precisar preservar histórico.

## Financeiro e recorrências

O painel usa regime de caixa por data efetiva de recebimento/pagamento. “Valor em negociação” é uma medida comercial, não saldo disponível. Horas são lançadas manualmente; não existe cronômetro ou custo automático por colaborador.

A geração mensal cria uma receita aberta por contrato/competência, com unicidade verificada também no servidor. Cancelar um lançamento não faz o sistema recriá-lo silenciosamente. Para uma correção, revise o registro existente. Contratos pausados/cancelados e vigência influenciam a seleção da geração na interface. Não existe job que cobre clientes mensalmente ou envie boletos: o agendamento de backup é independente da geração financeira.

O valor líquido de entradas e saídas é saldo de caixa, não lucro contábil. Use um sistema fiscal/contábil apropriado quando necessário, fora deste CRM.

## Perfis

| Recurso | Administrador | Comercial | Operação | Financeiro |
|---|---|---|---|---|
| Clientes | Edita | Edita | Consulta | Consulta |
| Oportunidades e propostas | Edita | Edita | Sem acesso | Sem acesso |
| Projetos | Edita | Edita | Edita; sem valor e vínculo comercial | Consulta, incluindo valor de referência |
| Tarefas/agenda | Edita | Edita | Edita | Sem acesso |
| Receitas/despesas e contratos mensais | Edita | Sem acesso | Sem acesso | Edita |
| Interações | Todas | Compartilhadas/Comercial | Compartilhadas | Compartilhadas/Financeiro |
| Relatórios | Todos | Comerciais | Operacionais | Financeiros |
| Configurações, contas, backup e auditoria | Sim | Não | Não | Não |

O perfil não significa aprovação em dois níveis: quem pode editar um módulo também pode excluir seus registros, quando não há vínculos que impeçam. Desativar uma conta ou mudar seu perfil revoga suas sessões. O último administrador ativo não pode ser removido/desativado por essa tela. Convém ter um segundo administrador autorizado para contingência.

## Trabalho simultâneo e rede

As telas consultam alterações a cada 12 segundos quando não há editor, busca ou configurações não salvas. Não é atualização por WebSocket. Dois usuários podem alterar registros diferentes; o mesmo registro é protegido por revisão. Ao encontrar conflito, a aplicação recusa a gravação e preserva os campos do formulário: copie o necessário, feche-o, atualize a base e refaça a edição sobre a versão vigente. Não há mesclagem automática.

Se a resposta de uma gravação não chegar, use “Reconectar e conferir” na mesma sessão/aba. A transação pendente pode ser reenviada com o mesmo identificador, sem duplicar a aplicação. Recarregar/fechar a página descarta esse identificador guardado só em memória; confira os dados no servidor antes de repetir a ação. Não há modo offline, fila persistente ou recuperação garantida de textos digitados após fechar o navegador.

Sessões duram no máximo oito horas e expiram após duas horas de inatividade. Alterações de senha invalidam outras sessões; uma recuperação de senha invalida todas. Em computador compartilhado, encerre a conta e feche a página. Manter um formulário aberto não impede expiração.

## Migrar a versão HTML anterior

1. Na versão 1.0, exporte um backup JSON e guarde uma cópia intocada. Não basta copiar o arquivo HTML: os dados antigos estão no navegador.
2. Na nova instalação, crie a conta administradora, faça um backup da base atual e abra Configurações > restaurar backup.
3. Selecione o JSON, confira as quantidades e digite RESTAURAR. **A importação substitui os registros de negócio, não mescla.** Contas e auditoria da nova instalação são preservadas.
4. O servidor grava uma cópia da base anterior antes de substituir. Interações antigas sem classificação tornam-se privadas ao administrador. Reclassifique manualmente apenas o que deve ficar compartilhado.
5. Confira contagem de clientes, valores, vínculos, tarefas e contratos. A fixture fornecida é fictícia; seus próprios dados precisam de conferência.

O arquivo de importação pela interface tem limite de 12 MB. Não use edição manual do JSON para contornar uma rejeição sem entender os vínculos e as regras. CSV importa somente clientes, com prévia e mapeamento da versão da interface; não substitui uma migração completa.
