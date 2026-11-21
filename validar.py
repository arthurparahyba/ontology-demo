"""
Valida o grafo de definições com SHACL.
    python validar.py                                  # grafo oficial
    python validar.py testes/definicao_com_erros.ttl   # simula alguém cadastrando algo errado
"""
import sys

from pyshacl import validate
from rdflib import Graph

from motor.grafo import RAIZ, carregar

dados = carregar(*sys.argv[1:])
shapes = Graph().parse(RAIZ / "ontologia" / "shapes.ttl", format="turtle")
ok, _, texto = validate(dados, shacl_graph=shapes, ont_graph=dados, inference="rdfs", advanced=True)
print("✓ Grafo válido." if ok else texto)
sys.exit(0 if ok else 1)
