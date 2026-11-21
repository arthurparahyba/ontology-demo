"""Gera um relatório HTML que MOSTRA a semântica: regra aplicada, mudanças e células 'não aplicável'."""
from __future__ import annotations

import html
from pathlib import Path

from .compilador import Periodo, avisos_de_mudanca, membros_por_periodo

CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:980px;margin:32px auto;padding:0 20px;color:#1d2433;background:#fbfaf7}
h1{font-size:22px;margin-bottom:4px} .q{color:#5b6475;margin-top:0}
table{border-collapse:collapse;width:100%;margin:16px 0;background:#fff}
th,td{border-bottom:1px solid #e6e3dc;padding:8px 10px;text-align:left;font-size:14px}
th{background:#f1efe9;font-weight:600} td.n{text-align:right;font-variant-numeric:tabular-nums}
td.na{background:repeating-linear-gradient(45deg,#f6f3ec,#f6f3ec 6px,#ece7dc 6px,#ece7dc 12px);color:#8a6d3b;text-align:center;font-size:12px}
.aviso{background:#fff6e0;border-left:4px solid #e0a100;padding:10px 14px;margin:12px 0;font-size:14px}
.sup{background:#eef4ff;border-left:4px solid #3b6fd8;padding:10px 14px;margin:12px 0;font-size:14px}
.regra{font-size:13px;color:#3d4557} details{margin-top:18px} pre{background:#1d2433;color:#e8e6df;padding:14px;overflow:auto;font-size:12px;border-radius:6px}
.tag{display:inline-block;background:#e9e6de;border-radius:10px;padding:1px 8px;font-size:12px;margin-right:4px}
"""


def gerar(caminho: Path, pergunta: str, intencao: dict, sql: str, linhas: list[tuple], colunas: list[str],
          periodos: list[Periodo], interpretador: str) -> Path:
    e = html.escape
    rot = [p.rotulo for p in periodos]
    nobres = membros_por_periodo(periodos, "Bairro nobre")
    partes = [f"<h1>{e(pergunta)}</h1>",
              f"<p class='q'>Interpretado por: {e(interpretador)} · modo temporal: <b>{e(intencao['modo_temporal'])}</b></p>"]

    if intencao.get("suposicoes"):
        partes.append("<div class='sup'><b>Como entendi a pergunta</b><ul>" +
                      "".join(f"<li>{e(s)}</li>" for s in intencao["suposicoes"]) + "</ul></div>")
    for a in avisos_de_mudanca(periodos):
        partes.append(f"<div class='aviso'>⚠ {e(a)}</div>")

    if intencao["operacao"] == "contar" and intencao.get("agrupar_por") == "bairro":
        dados = {(b, p): q for b, p, q in linhas}
        bairros = sorted({b for b, _ in dados} | set().union(*nobres.values()) if nobres else {b for b, _ in dados})
        partes.append("<table><tr><th>Bairro</th>" + "".join(f"<th>{r}</th>" for r in rot) + "<th>Observação</th></tr>")
        for b in bairros:
            celulas, obs = [], []
            for r in rot:
                if r in nobres and b not in nobres[r]:
                    celulas.append(f"<td class='na' title='Bairro não classificado como nobre em {r}'>não era nobre</td>")
                    obs.append(f"fora da lista de bairros nobres em {r}")
                else:
                    celulas.append(f"<td class='n'>{dados.get((b, r), 0)}</td>")
            partes.append(f"<tr><td>{e(b)}</td>{''.join(celulas)}<td>{e('; '.join(obs))}</td></tr>")
        tot = "".join(f"<th class='n'>{sum(q for (_, p), q in dados.items() if p == r)}</th>" for r in rot)
        partes.append(f"<tr><th>Total</th>{tot}<th></th></tr></table>")
    else:
        partes.append("<table><tr>" + "".join(f"<th>{e(c)}</th>" for c in colunas) + "</tr>")
        for ln in linhas[:200]:
            partes.append("<tr>" + "".join(f"<td>{e(str(v))}</td>" for v in ln) + "</tr>")
        partes.append("</table>")
        if len(linhas) > 200:
            partes.append(f"<p class='regra'>… {len(linhas) - 200} linhas omitidas.</p>")

    partes.append("<h3>Regras aplicadas (proveniência)</h3><table><tr><th>Período</th><th>Conceito</th>"
                  "<th>Definição</th><th>Vigência</th><th>Responsável</th><th>Fonte</th></tr>")
    for p in periodos:
        for r in p.rastros:
            membros = f"<br><span class='regra'>{''.join(f'<span class=tag>{e(m)}</span>' for m in sorted(r.membros.values()))}</span>" if r.membros else ""
            partes.append(f"<tr><td>{p.rotulo}</td><td>{e(r.conceito)}</td><td>{e(r.rotulo_definicao)}{membros}</td>"
                          f"<td>{e(r.vigencia)}</td><td>{e(r.responsavel)}</td><td>{e(r.fonte)}</td></tr>")
    partes.append("</table>")
    partes.append(f"<details><summary>SQL gerado</summary><pre>{e(sql)}</pre></details>")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(f"<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'><title>{e(pergunta)}</title>"
                       f"<style>{CSS}</style></head><body>{''.join(partes)}</body></html>", encoding="utf-8")
    return caminho
