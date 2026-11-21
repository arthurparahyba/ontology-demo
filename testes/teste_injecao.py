"""
Teste de regressão: uma intenção maliciosa (como um LLM manipulado poderia gerar)
não pode chegar ao banco.   Rode:  python testes/teste_injecao.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.compilador import Compilador, ErroSemantico  # noqa: E402
from motor.grafo import carregar  # noqa: E402
from motor.interpretador import validar_intencao  # noqa: E402

g = carregar()
HOJE = date(2026, 11, 21)
base = {"conceito": "ClienteVIP", "operacao": "contar", "agrupar_por": None,
        "modo_temporal": "como_era", "precisa_esclarecer": None}

ataques = {
    "rótulo com aspas": {**base, "periodos": [{"rotulo": "2025' UNION SELECT email FROM cliente --",
                                                "data_ref": "2025-12-31"}]},
    "rótulo com ponto e vírgula": {**base, "periodos": [{"rotulo": "x; DROP TABLE cliente",
                                                          "data_ref": "2025-12-31"}]},
    "data inválida": {**base, "periodos": [{"rotulo": "2025", "data_ref": "2025-12-31' OR 1=1"}]},
    "conceito com IRI estranho": {**base, "conceito": "ClienteVIP> . ?x ?y ?z", "periodos": [
                                  {"rotulo": "2025", "data_ref": "2025-12-31"}]},
    "operação desconhecida": {**base, "operacao": "apagar", "periodos": [
                              {"rotulo": "2025", "data_ref": "2025-12-31"}]},
}

falhas = 0
for nome, it in ataques.items():
    barrado_validador = bool(validar_intencao(g, it))
    try:
        Compilador(g).compilar(it, HOJE)
        barrado_compilador = False
    except (ErroSemantico, ValueError):
        barrado_compilador = True
    ok = barrado_validador and barrado_compilador
    falhas += not ok
    print(f"{'✓' if ok else '✗'} {nome}: validador={'barrou' if barrado_validador else 'DEIXOU PASSAR'}, "
          f"compilador={'barrou' if barrado_compilador else 'DEIXOU PASSAR'}")

print("\nTodos os ataques foram barrados nas duas camadas." if not falhas else f"\n{falhas} falha(s)!")
sys.exit(1 if falhas else 0)
