"""
INTERPRETADOR: pergunta em linguagem natural -> INTENÇÃO estruturada.

Aqui entra o LLM. Repare em duas coisas:
1. A "camada de contexto" é montada A PARTIR DA ONTOLOGIA (montar_contexto):
   conceitos, sinônimos, definições vigentes, dimensões, data de hoje.
2. O LLM devolve JSON no vocabulário da ontologia — não SQL. Esse JSON é
   validado antes de ir para o compilador.

Se ANTHROPIC_ONTOLOGY_API_KEY (ou ANTHROPIC_API_KEY) estiver definida e o pacote `anthropic` instalado, usa o
Claude. Senão, usa um interpretador de regras simples (para a demo rodar
offline) — que, note, também tira os sinônimos da ontologia.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

from rdflib import Graph
from rdflib.namespace import RDF, RDFS

from .grafo import EX, PROV, SKOS

ESQUEMA_INTENCAO = """{
  "conceito": "<nome local do conceito, ex.: ClienteVIP>",
  "operacao": "contar" | "listar",
  "agrupar_por": "bairro" | null,
  "periodos": [{"rotulo": "2025", "data_ref": "AAAA-MM-DD"}, ...],
  "modo_temporal": "como_era" | "definicao_atual",
  "suposicoes": ["<cada interpretação que você fez e o usuário deveria saber>"],
  "precisa_esclarecer": null | "<pergunta ao usuário, se ambíguo demais>"
}"""


def montar_contexto(g: Graph, hoje: date) -> str:
    """A CAMADA DE CONTEXTO, concretamente: o pacote de conhecimento que o LLM recebe."""
    linhas = [f"Data de hoje: {hoje.isoformat()}. Ano corrente: {hoje.year} (em andamento).", "",
              "CONCEITOS DE NEGÓCIO (use o nome local exato no JSON):"]
    for c in g.subjects(RDF.type, EX.ConceitoDeNegocio):
        nome = str(c).split("#")[-1]
        sin = ", ".join(sorted(str(a) for a in g.objects(c, SKOS.altLabel)))
        linhas.append(f"- {nome} — \"{g.value(c, SKOS.prefLabel)}\" (sinônimos: {sin})")
        linhas.append(f"    definição: {g.value(c, SKOS.definition)}")
        for d in g.subjects(EX.define, c):
            resp = g.value(g.value(d, PROV.wasAttributedTo), RDFS.label)
            linhas.append(f"    versão {g.value(d, EX.vigenteDe)} → {g.value(d, EX.vigenteAte) or 'atual'} "
                          f"(responsável: {resp})")
    linhas += ["", "DIMENSÕES DISPONÍVEIS PARA AGRUPAR: bairro", "",
               "REGRAS DE INTERPRETAÇÃO:",
               "- Período anual fechado: data_ref = 31/12 do ano. Ano corrente: data_ref = hoje.",
               "- 'ano passado' = ano corrente - 1. 'últimos N anos' = os N anos até o corrente, inclusive.",
               "- modo_temporal 'como_era' (padrão): cada período usa a definição vigente NAQUELE período.",
               "- modo_temporal 'definicao_atual': só se o usuário pedir explicitamente a regra/critério atual.",
               "- Registre em 'suposicoes' toda interpretação não literal."]
    return "\n".join(linhas)


def _prompt(contexto: str, pergunta: str) -> str:
    return (f"Você traduz perguntas de executivos em INTENÇÕES de consulta. Não escreva SQL.\n\n"
            f"{contexto}\n\nResponda APENAS com um JSON neste formato:\n{ESQUEMA_INTENCAO}\n\n"
            f"Pergunta: {pergunta}")


def _chave_api() -> str | None:
    """Aceita uma variável específica do projeto ou a padrão do SDK."""
    return os.getenv("ANTHROPIC_ONTOLOGY_API_KEY") or os.getenv("ANTHROPIC_API_KEY")


def _via_llm(prompt: str) -> dict:
    import anthropic  # opcional
    cli = anthropic.Anthropic(api_key=_chave_api())
    resp = cli.messages.create(model=os.getenv("MODELO", "claude-sonnet-5-5"), max_tokens=800,
                               messages=[{"role": "user", "content": prompt}])
    texto = resp.content[0].text
    return json.loads(texto[texto.find("{"): texto.rfind("}") + 1])


def _via_regras(g: Graph, pergunta: str, hoje: date) -> dict:
    """Substituto offline do LLM. Simplório de propósito — mas usa os sinônimos SKOS."""
    q = pergunta.lower()
    conceito = None
    for c in g.subjects(RDF.type, EX.ConceitoDeNegocio):
        rotulos = [str(g.value(c, SKOS.prefLabel))] + [str(a) for a in g.objects(c, SKOS.altLabel)]
        if any(r.lower() in q for r in rotulos) and (c, RDF.type, EX.ConceitoDeNegocio) in g:
            if conceito is None or str(c).endswith("ClienteVIP"):
                conceito = str(c).split("#")[-1]
    sup = []
    ano = hoje.year
    m = re.search(r"últimos (\d+) anos", q)
    if m:
        anos = list(range(ano - int(m.group(1)) + 1, ano + 1))
        sup.append(f"'últimos {m.group(1)} anos' interpretado como {anos[0]}–{anos[-1]}.")
    elif "ano passado" in q:
        anos = [ano - 1, ano] if re.search(r"(neste|este|desse|deste) ano", q) else [ano - 1]
    else:
        anos = [ano]
    periodos = [{"rotulo": str(a), "data_ref": (hoje if a == ano else date(a, 12, 31)).isoformat()} for a in anos]
    if ano in anos:
        sup.append(f"{ano} ainda não terminou: avaliado em {hoje.isoformat()}.")
    modo = "definicao_atual" if re.search(r"(regra|critério|definição) (atual|de hoje|vigente hoje)", q) else "como_era"
    sup.append("Cada ano usa a definição vigente naquele ano." if modo == "como_era"
               else "A definição vigente hoje foi aplicada a todos os períodos.")
    return {
        "conceito": conceito,
        "operacao": "listar" if re.search(r"\b(liste|listar|lista|e-?mails?|enviar)\b", q) else "contar",
        "agrupar_por": "bairro" if "por bairro" in q else None,
        "periodos": periodos, "modo_temporal": modo, "suposicoes": sup,
        "precisa_esclarecer": None if conceito else "Não reconheci o conceito de negócio. Qual grupo de clientes?",
    }


def validar_intencao(g: Graph, it: dict) -> list[str]:
    """Guardrail: o JSON do LLM só passa se fizer sentido para a ontologia."""
    erros = []
    if it.get("precisa_esclarecer"):
        erros.append("Esclarecimento necessário: " + it["precisa_esclarecer"])
    if not it.get("conceito") or (EX[it["conceito"]], RDF.type, EX.ConceitoDeNegocio) not in g:
        erros.append(f"Conceito inexistente na ontologia: {it.get('conceito')}")
    if it.get("agrupar_por") not in (None, "bairro"):
        erros.append(f"Dimensão não suportada: {it['agrupar_por']}")
    if not it.get("periodos"):
        erros.append("Nenhum período informado.")
    return erros


def interpretar(g: Graph, pergunta: str, hoje: date) -> tuple[dict, str, str]:
    contexto = montar_contexto(g, hoje)
    if _chave_api():
        try:
            return _via_llm(_prompt(contexto, pergunta)), contexto, "LLM"
        except Exception as e:  # sem rede, sem pacote etc.
            print(f"[aviso] LLM indisponível ({e}); usando interpretador de regras.")
    return _via_regras(g, pergunta, hoje), contexto, "regras (offline)"
