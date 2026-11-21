"""
AVALIAÇÃO: roda a bateria de referência (avaliacao/perguntas.json) pelo pipeline
e compara com o gabarito escrito à mão.

    python avaliar.py              # usa o LLM se a chave estiver definida; senão, as regras offline
    python avaliar.py --detalhes   # mostra também o que foi obtido em cada erro

Cada pergunta cai numa de quatro classes:
    ✓ certa            respondeu e o resultado bate com o gabarito
    ✓ recusa correta   o gabarito manda recusar e o sistema recusou
    ✗ ERRO SILENCIOSO  respondeu algo diferente do gabarito (o pior caso: parece certo)
    ✗ recusa indevida  havia resposta certa e o sistema não respondeu
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb

from dados.criar_banco import BANCO, criar
from motor.grafo import carregar
from perguntar import SAIDA, executar

RAIZ = Path(__file__).resolve().parent
ROTULOS = {"certa": "✓ certa", "recusa_correta": "✓ recusa correta",
           "erro_silencioso": "✗ ERRO SILENCIOSO", "recusa_indevida": "✗ recusa indevida"}


def _forma_obtida(intencao: dict) -> str:
    if intencao.get("operacao") == "listar":
        return "lista_emails"
    return "por_bairro" if intencao.get("agrupar_por") == "bairro" else "por_periodo"


def _normalizar(forma: str, linhas: list, colunas: list | None = None) -> set:
    if forma == "lista_emails":
        i = colunas.index("email") if colunas and "email" in colunas else 0
        return {str(l[i]) for l in linhas}
    return {tuple(int(v) if isinstance(v, (int, float)) else str(v) for v in l) for l in linhas}


def avaliar(detalhes: bool = False) -> dict:
    g = carregar()
    casos = json.loads((RAIZ / "avaliacao" / "perguntas.json").read_text(encoding="utf-8"))["perguntas"]
    con = duckdb.connect(str(BANCO), read_only=True)
    resultados = []
    for c in casos:
        r = executar(c["pergunta"], g)
        nota = ""
        if c["forma"] == "recusa":
            classe = "recusa_correta" if r["status"] == "recusada" else "erro_silencioso"
            if classe == "erro_silencioso":
                nota = f"deveria recusar, mas respondeu {len(r['linhas'])} linha(s)"
        elif r["status"] == "recusada":
            classe, nota = "recusa_indevida", r["motivo"]
        else:
            esperado = _normalizar(c["forma"], con.execute(c["sql"]).fetchall())
            forma = _forma_obtida(r["intencao"])
            obtido = _normalizar(forma, r["linhas"], r["colunas"])
            if forma != c["forma"]:
                classe, nota = "erro_silencioso", f"formato {forma}, esperado {c['forma']}"
            elif obtido == esperado:
                classe = "certa"
            else:
                classe = "erro_silencioso"
                falta, sobra = esperado - obtido, obtido - esperado
                nota = f"{len(falta)} faltando, {len(sobra)} sobrando"
                if detalhes:
                    nota += f" | ex. faltando: {sorted(falta)[:3]} | ex. sobrando: {sorted(sobra)[:3]}"
        resultados.append({**c, "classe": classe, "nota": nota, "origem": r["origem"],
                           "intencao": r["intencao"]})
    con.close()
    return {"resultados": resultados, "origem": resultados[0]["origem"] if resultados else "?"}


def relatorio_md(av: dict) -> str:
    res = av["resultados"]
    cont = {k: sum(1 for r in res if r["classe"] == k) for k in ROTULOS}
    acerto = cont["certa"] + cont["recusa_correta"]
    linhas = [f"# Avaliação — {datetime.now():%Y-%m-%d %H:%M}", "",
              f"Interpretador: **{av['origem']}** · Acerto: **{acerto}/{len(res)}** · "
              f"Erros silenciosos: **{cont['erro_silencioso']}** · Recusas indevidas: **{cont['recusa_indevida']}**", "",
              "| ID | Pergunta | Resultado | Observação |", "| --- | --- | --- | --- |"]
    for r in res:
        linhas.append(f"| {r['id']} | {r['pergunta']} | {ROTULOS[r['classe']]} | {r['nota'].replace('|', '/')} |")
    linhas += ["", "## O que cada pergunta testa", ""] + [f"- **{r['id']}**: {r['testa']}" for r in res]
    return "\n".join(linhas) + "\n"


if __name__ == "__main__":
    if not BANCO.exists():
        criar()
    av = avaliar(detalhes="--detalhes" in sys.argv)
    for r in av["resultados"]:
        print(f"{r['id']}  {ROTULOS[r['classe']]:<20} {r['pergunta']}" + (f"\n      → {r['nota']}" if r["nota"] else ""))
    md = relatorio_md(av)
    SAIDA.mkdir(exist_ok=True)
    nome = "avaliacao-llm.md" if av["origem"] == "LLM" else "avaliacao-regras.md"
    (SAIDA / nome).write_text(md, encoding="utf-8")
    print("\n" + md.splitlines()[2])
    print(f"Relatório: saida/{nome}")
