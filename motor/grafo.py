"""Carrega a ontologia + definições num único grafo RDF (rdflib)."""
from pathlib import Path

from rdflib import Graph, Namespace

RAIZ = Path(__file__).resolve().parent.parent
EX = Namespace("https://exemplo.com/ont#")
MAP = Namespace("https://exemplo.com/map#")
PROV = Namespace("http://www.w3.org/ns/prov#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

ARQUIVOS_PADRAO = [RAIZ / "ontologia" / "nucleo.ttl", RAIZ / "ontologia" / "definicoes.ttl"]


def carregar(*extras: str | Path) -> Graph:
    g = Graph()
    for arq in [*ARQUIVOS_PADRAO, *extras]:
        g.parse(arq, format="turtle")
    g.bind("ex", EX); g.bind("map", MAP); g.bind("prov", PROV); g.bind("skos", SKOS)
    return g
