# ontology-demo — "Cliente VIP" com ontologia + LLM

Um protótipo pequeno e executável para entender, na prática, **ontologia, knowledge graph, camada semântica e camada de contexto** aplicados a um caso real: executivos perguntando em linguagem natural sobre dados analíticos.

## O problema

"Liste os clientes da região X" o LLM acerta só olhando o esquema do banco. Já **"clientes VIP"** não aparece como coluna em lugar nenhum. É um conceito de negócio:

- **VIP** = cliente com ≥ 5 anos de casa **e** que mora em **bairro nobre**;
- **bairro nobre** é outro conceito, definido por uma lista que **muda todo ano** (5 bairros em 2025, 7 em 2026);
- então a pergunta "VIP do ano passado vs. deste ano, por bairro" precisa aplicar **a regra vigente em cada ano** e **avisar** quando um bairro não era considerado no ano anterior.

## A arquitetura (e onde cada conceito mora)

```
pergunta ──► [CAMADA DE CONTEXTO] ──► LLM ──► INTENÇÃO (JSON no vocabulário da ontologia)
              montada a partir da                 │
              ontologia                           ▼
                                        [validação contra a ontologia]
                                                  │
              [ONTOLOGIA + KG de definições] ──►  COMPILADOR SEMÂNTICO ──► SQL ──► DuckDB
               (vigência, composição,             (determinístico)                  │
                proveniência)                                                       ▼
                                                             relatório com regra aplicada + avisos
```

| Conceito | Arquivo | O que é aqui |
|---|---|---|
| **Banco / esquema físico** | `dados/criar_banco.py` | Tabelas `cliente` e `bairro`. Não tem coluna "vip". |
| **Ontologia (T-Box)** | `ontologia/nucleo.ttl` | Classes e relações em OWL (`Cliente`, `Bairro`, `resideEm`, `ClienteVIP ⊑ Cliente`), sinônimos em SKOS e o mapeamento para o banco. |
| **Knowledge graph (A-Box)** | `ontologia/definicoes.ttl` | Os fatos: bairros como indivíduos e as **versões das regras**, com vigência, responsável e fonte (PROV-O). |
| **Regras de qualidade** | `ontologia/shapes.ttl` | SHACL: toda definição tem vigência, dono e critério, e duas versões do mesmo conceito não podem ter vigências sobrepostas. |
| **Camada semântica** | `motor/compilador.py` | Transforma conceito de negócio em SQL, sempre do mesmo jeito. |
| **Camada de contexto** | `motor/interpretador.py` → `montar_contexto` | O pacote que o LLM recebe: conceitos, sinônimos, versões, dimensões, data de hoje e regras de interpretação temporal. |
| **Guardrail** | `validar_intencao` + `validar.py` | O JSON do LLM e o grafo só passam se forem coerentes com a ontologia. |
| **Explicabilidade** | `motor/relatorio.py` | O relatório mostra as suposições, a regra usada em cada período, o que mudou e o SQL. |

**O princípio central:** o LLM **não escreve a regra de negócio no SQL**. Ele só traduz a pergunta para o vocabulário da ontologia. A regra fica no grafo, versionada e com dono, e o SQL sai de um código determinístico.

## Dois modos temporais

- `como_era` (padrão): 2025 usa a lista de 2025 e 2026 usa a de 2026. É o modo para responder "quantos VIP eu *tinha*".
- `definicao_atual`: aplica a regra de hoje a todos os anos. É o modo para responder "pelo critério atual, como seria 2025?".

Os fatos, como o tempo de casa, são sempre avaliados na data do período. Só a **regra** muda de data, e essa é a diferença entre "tempo do fato" e "tempo da regra".

## Rodando

```bash
pip install -r requirements.txt
python dados/criar_banco.py
python perguntar.py --demo                    # 3 cenários; relatórios em saida/*.html
python perguntar.py "Quantos clientes premium neste ano, por bairro?"
python validar.py                             # SHACL no grafo oficial
python validar.py testes/definicao_com_erros.ttl   # vê a validação barrando um cadastro errado
```

Por padrão a demo usa um **interpretador de regras offline** no lugar do LLM. Para usar o Claude: `pip install anthropic` e `export ANTHROPIC_ONTOLOGY_API_KEY=...` (`ANTHROPIC_API_KEY` também funciona). O resto do pipeline não muda, e é esse o ponto.

## Avaliação (bateria de referência)

`avaliacao/perguntas.json` tem 20 perguntas com o gabarito em SQL escrito **à mão**, independente do compilador. Algumas perguntas exigem que o sistema **recuse**, como as que pedem um dado que não existe ou as ambíguas.

```bash
python avaliar.py --detalhes     # gera saida/avaliacao-regras.md ou saida/avaliacao-llm.md
python testes/teste_injecao.py   # garante que intenções maliciosas não chegam ao SQL
```

Cada resposta é classificada como certa, recusa correta, **erro silencioso** (respondeu errado com cara de certo, o pior caso) ou recusa indevida. Baseline com o interpretador offline: **12/20**, com 5 erros silenciosos. Rode com a sua chave e compare.

Regra do projeto: nenhuma mudança na ontologia, no prompt ou no compilador entra sem rodar `avaliar.py` antes e depois.

## Exercícios sugeridos (cada um ensina um conceito)

1. **Nova versão de regra:** crie `def_vip_v2` a partir de 2026 com 4 anos de casa. Lembre de fechar a `v1` com `vigenteAte`, senão o SHACL acusa sobreposição.
2. **Novo conceito composto:** `ClienteEmRisco` (sem compra há 12 meses). Você vai precisar de uma tabela `pedido`, de um novo tipo de critério e de ensinar o compilador.
3. **SPARQL puro:** abra o grafo e pergunte "quais conceitos dependem de BairroNobre?" (análise de impacto).
4. **Cliente que mudou de bairro:** transforme `cliente.bairro_id` numa tabela histórica (SCD tipo 2). É temporalidade nos *fatos*, não só nas regras.
5. **Trocar o compilador caseiro por padrões:** substitua o `map:` por R2RML e consulte via **Ontop**, ou exporte as métricas para **dbt MetricFlow / Cube**.
6. **Expor como ferramenta MCP:** `listar_conceitos`, `explicar_conceito`, `consultar(intencao)`.
