# Avaliação — 2026-11-21 14:52

Interpretador: **regras (offline)** · Acerto: **12/20** · Erros silenciosos: **5** · Recusas indevidas: **3**

| ID | Pergunta | Resultado | Observação |
| --- | --- | --- | --- |
| Q01 | Quantos clientes VIP temos neste ano? | ✓ certa |  |
| Q02 | Quantos clientes VIP tivemos no ano passado? | ✓ certa |  |
| Q03 | Quantos clientes VIP no ano passado e neste ano? | ✓ certa |  |
| Q04 | Quantos clientes VIP tivemos no ano passado e neste ano, por bairro? | ✓ certa |  |
| Q05 | Quantos clientes premium neste ano, por bairro? | ✗ recusa indevida | Esclarecimento necessário: Não reconheci o conceito de negócio. Qual grupo de clientes?; Conceito inexistente na ontologia: None |
| Q06 | Quantos top clientes tivemos nos últimos 2 anos? | ✓ certa |  |
| Q07 | Liste os e-mails dos clientes VIP dos últimos 2 anos | ✓ certa |  |
| Q08 | Liste os clientes VIP deste ano | ✓ certa |  |
| Q09 | Liste os clientes VIP do ano passado | ✓ certa |  |
| Q10 | Quantos clientes VIP no ano passado e neste ano, por bairro, usando a regra atual? | ✓ certa |  |
| Q11 | Quantos clientes VIP tivemos no ano passado pela regra atual? | ✓ certa |  |
| Q12 | Quantos clientes VIP nos últimos 3 anos? | ✓ recusa correta |  |
| Q13 | Quantos clientes especiais por bairro neste ano? | ✓ certa |  |
| Q14 | Qual a receita média dos clientes VIP neste ano? | ✗ ERRO SILENCIOSO | deveria recusar, mas respondeu 1 linha(s) |
| Q15 | Quantos clientes VIP tivemos em 2025? | ✗ ERRO SILENCIOSO | 1 faltando, 1 sobrando / ex. faltando: [('2025', 128)] / ex. sobrando: [('2026', 207)] |
| Q16 | Quantos bairros nobres existem neste ano? | ✗ recusa indevida | Esclarecimento necessário: Não reconheci o conceito de negócio. Qual grupo de clientes?; Conceito inexistente na ontologia: None |
| Q17 | Quantos clientes moram em bairro nobre neste ano? | ✗ ERRO SILENCIOSO | 1 faltando, 1 sobrando / ex. faltando: [('2026', 343)] / ex. sobrando: [('2026', 7)] |
| Q18 | Quantos clientes VIP no Meireles neste ano? | ✗ ERRO SILENCIOSO | 1 faltando, 1 sobrando / ex. faltando: [('2026', 21)] / ex. sobrando: [('2026', 207)] |
| Q19 | Quantos clientes VIP nos últimos 24 meses? | ✗ ERRO SILENCIOSO | deveria recusar, mas respondeu 1 linha(s) |
| Q20 | Liste todos os clientes cadastrados | ✗ recusa indevida | Esclarecimento necessário: Não reconheci o conceito de negócio. Qual grupo de clientes?; Conceito inexistente na ontologia: None |

## O que cada pergunta testa

- **Q01**: Caso básico: ano corrente avaliado na data de hoje.
- **Q02**: Ano fechado usa a lista de bairros de 2025.
- **Q03**: Dois períodos, cada um com a sua regra.
- **Q04**: O cenário principal: agrupamento por bairro com regras diferentes por ano.
- **Q05**: Sinônimo SKOS ('cliente premium').
- **Q06**: Sinônimo + 'últimos N anos'.
- **Q07**: Listagem: união dos VIP de cada ano (caso da campanha de e-mail).
- **Q08**: Listagem de um período só.
- **Q09**: Listagem de ano fechado.
- **Q10**: Modo definicao_atual: lista de 2026 aplicada a 2025, tempo de casa ainda medido em 2025.
- **Q11**: Modo definicao_atual num período só.
- **Q12**: Não existe lista de bairros nobres vigente em 2024: o certo é recusar, não inventar.
- **Q13**: Outro sinônimo, com a ordem das palavras trocada.
- **Q14**: Não há dado de receita: o certo é recusar.
- **Q15**: Ano escrito por extenso em vez de 'ano passado'.
- **Q16**: Pergunta sobre o conceito BairroNobre em si.
- **Q17**: Mistura de entidades: conta CLIENTES filtrados por um conceito de BAIRRO.
- **Q18**: Filtro por um bairro específico (o esquema de intenção não tem filtros).
- **Q19**: Janela móvel não é ano-calendário: ambíguo para as regras anuais, o certo é pedir esclarecimento.
- **Q20**: Pergunta simples sem conceito de negócio (fora da cobertura atual).
