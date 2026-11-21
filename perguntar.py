"""
Pipeline completo:  pergunta -> contexto (da ontologia) -> intenção (LLM)
                    -> validação -> SQL (compilador) -> banco -> relatório com proveniência

Uso:
    python perguntar.py "Quantos clientes VIP tivemos no ano passado e neste ano, por bairro?"
    python perguntar.py --demo        # roda os cenários de exemplo
"""
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import duckdb

from dados.criar_banco import BANCO, criar
from motor.compilador import Compilador, ErroSemantico, avisos_de_mudanca
from motor.grafo import carregar
from motor.interpretador import interpretar, validar_intencao
from motor import relatorio

HOJE = date(2026, 11, 21)  # fixo para a demo ser reprodutível; troque por date.today()
SAIDA = Path(__file__).resolve().parent / "saida"

CENARIOS = [
    "Quantos clientes VIP tivemos no ano passado e neste ano, por bairro?",
    "Liste os e-mails dos clientes VIP dos últimos 2 anos",
    "Quantos clientes VIP no ano passado e neste ano, por bairro, usando a regra atual?",
]


def _slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60]


def executar(pergunta: str, g=None) -> dict:
    """Roda o pipeline e devolve tudo o que aconteceu. Não imprime nada (usado pela avaliação)."""
    g = g or carregar()
    intencao, contexto, origem = interpretar(g, pergunta, HOJE)
    r = {"pergunta": pergunta, "intencao": intencao, "contexto": contexto, "origem": origem,
         "status": None, "motivo": None, "sql": None, "colunas": [], "linhas": [], "periodos": []}
    erros = validar_intencao(g, intencao)
    if erros:
        r.update(status="recusada", motivo="; ".join(erros))
        return r
    try:
        sql, periodos = Compilador(g).compilar(intencao, HOJE)
    except ErroSemantico as e:
        r.update(status="recusada", motivo=str(e))
        return r
    con = duckdb.connect(str(BANCO), read_only=True)
    try:
        cur = con.execute(sql)
        r.update(status="ok", sql=sql, colunas=[d[0] for d in cur.description],
                 linhas=cur.fetchall(), periodos=periodos)
    finally:
        con.close()
    return r


def perguntar(pergunta: str, mostrar_contexto: bool = False) -> Path | None:
    print("=" * 78, f"\nPERGUNTA: {pergunta}")
    r = executar(pergunta)
    if mostrar_contexto:
        print("\n--- CAMADA DE CONTEXTO enviada ao LLM ---\n" + r["contexto"])
    print(f"\n--- INTENÇÃO ({r['origem']}) ---\n" + json.dumps(r["intencao"], ensure_ascii=False, indent=2))
    if r["status"] != "ok":
        print("\n✗ Pergunta recusada:", r["motivo"])
        return None
    print("\n--- SQL GERADO ---\n" + r["sql"])
    print(f"\n--- RESULTADO ({len(r['linhas'])} linhas) ---")
    for ln in r["linhas"][:15]:
        print("  ", ln)
    for a in avisos_de_mudanca(r["periodos"]):
        print("⚠", a)
    arq = relatorio.gerar(SAIDA / f"{_slug(pergunta)}.html", pergunta, r["intencao"], r["sql"],
                          r["linhas"], r["colunas"], r["periodos"], r["origem"])
    print("\nRelatório:", arq)
    return arq


if __name__ == "__main__":
    if not BANCO.exists():
        criar()
    args = [a for a in sys.argv[1:] if a != "--contexto"]
    if not args or args[0] == "--demo":
        for i, c in enumerate(CENARIOS):
            perguntar(c, mostrar_contexto=(i == 0))
    else:
        perguntar(" ".join(args), mostrar_contexto="--contexto" in sys.argv)
