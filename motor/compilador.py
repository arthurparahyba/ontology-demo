"""
COMPILADOR SEMÂNTICO: transforma uma INTENÇÃO (expressa no vocabulário da
ontologia) em SQL, resolvendo cada conceito pela definição vigente na data.

Ponto-chave da arquitetura: o LLM NÃO escreve a regra de negócio no SQL.
Ele só diz "quero ClienteVIP, em 2025 e 2026, contado por bairro".
Quem sabe o que é VIP — em cada época — é a ontologia; quem gera SQL é este
código determinístico, testável e auditável.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from .grafo import EX, MAP, PROV, SKOS


class ErroSemantico(Exception):
    pass


@dataclass
class Rastro:
    """Proveniência: qual definição foi usada, para qual conceito, em que data."""
    conceito: str
    definicao: str
    rotulo_definicao: str
    vigencia: str
    responsavel: str
    fonte: str
    data_regra: date
    membros: dict[int, str] | None = None  # quando o critério é uma lista


@dataclass
class Periodo:
    rotulo: str
    data_ref: date       # data em que os FATOS são avaliados (ex.: tempo de casa)
    data_regra: date     # data cuja DEFINIÇÃO vigente é aplicada
    rastros: list[Rastro] = field(default_factory=list)


class Compilador:
    def __init__(self, g: Graph):
        self.g = g

    # ---------------------------------------------------------------- helpers
    def _rotulo(self, n) -> str:
        for p in (SKOS.prefLabel, RDFS.label):
            v = self.g.value(n, p)
            if v is not None:
                return str(v)
        return str(n).split("#")[-1]

    def _tabela_de(self, classe: URIRef) -> tuple[str, str]:
        """Tabela/chave de uma classe; sobe por rdfs:subClassOf (BairroNobre -> Bairro)."""
        atual = classe
        while atual is not None:
            t = self.g.value(atual, MAP.tabela)
            if t is not None:
                return str(t), str(self.g.value(atual, MAP.chave))
            atual = self.g.value(atual, RDFS.subClassOf)
        raise ErroSemantico(f"Sem mapeamento para o banco: {self._rotulo(classe)}")

    def resolver_conceito(self, nome: str) -> URIRef:
        uri = EX[nome]
        if (uri, RDF.type, EX.ConceitoDeNegocio) not in self.g:
            raise ErroSemantico(f"Conceito desconhecido na ontologia: {nome}")
        return uri

    # ------------------------------------------------ definição vigente (tempo)
    def definicao_vigente(self, conceito: URIRef, quando: date) -> URIRef:
        q = """
        SELECT ?d WHERE {
          ?d ex:define ?c ; ex:vigenteDe ?ini .
          OPTIONAL { ?d ex:vigenteAte ?fim }
          FILTER (?ini <= ?quando && (!BOUND(?fim) || ?fim >= ?quando))
        }"""
        res = [r.d for r in self.g.query(q, initNs={"ex": EX},
               initBindings={"c": conceito, "quando": Literal(quando, datatype=XSD.date)})]
        if not res:
            raise ErroSemantico(f"Nenhuma definição de '{self._rotulo(conceito)}' vigente em {quando}.")
        if len(res) > 1:
            raise ErroSemantico(f"Definições conflitantes de '{self._rotulo(conceito)}' em {quando}: {res}")
        return res[0]

    def _rastro(self, conceito, d, data_regra, membros=None) -> Rastro:
        ini = self.g.value(d, EX.vigenteDe)
        fim = self.g.value(d, EX.vigenteAte)
        return Rastro(
            conceito=self._rotulo(conceito), definicao=str(d).split("#")[-1],
            rotulo_definicao=self._rotulo(d),
            vigencia=f"{ini} → {fim or 'atual'}",
            responsavel=self._rotulo(self.g.value(d, PROV.wasAttributedTo)),
            fonte=str(self.g.value(d, PROV.hadPrimarySource) or "—"),
            data_regra=data_regra, membros=membros)

    # ------------------------------------------- conceito -> condição SQL
    def condicao(self, conceito: URIRef, alias: str, p: Periodo) -> str:
        d = self.definicao_vigente(conceito, p.data_regra)
        partes, membros = [], None
        for crit in self.g.objects(d, EX.criterio):
            tipo = self.g.value(crit, RDF.type)

            if tipo == EX.CriterioTempoDeCasa:
                n = int(self.g.value(crit, EX.anosMinimos))
                col = self.g.value(EX.dataCadastro, MAP.coluna)
                # tempo de casa é FATO: avaliado na data de referência do período
                partes.append(f"{alias}.{col} <= DATE '{p.data_ref}' - INTERVAL {n} YEAR")

            elif tipo == EX.CriterioPertenceA:
                prop = self.g.value(crit, EX.viaPropriedade)
                alvo = self.g.value(crit, EX.conceito)
                fk = self.g.value(prop, MAP.colunaFK)
                tab, chave = self._tabela_de(self.g.value(prop, RDFS.range))
                sub = f"s{len(alias)}"
                # COMPOSIÇÃO: resolve o conceito-alvo (BairroNobre) recursivamente
                cond_alvo = self.condicao(alvo, sub, p)
                partes.append(f"{alias}.{fk} IN (SELECT {sub}.{chave} FROM {tab} {sub} WHERE {cond_alvo})")

            elif tipo == EX.CriterioLista:
                _, chave = self._tabela_de(conceito)
                membros = {int(self.g.value(m, EX.codigoNoBanco)): self._rotulo(m)
                           for m in self.g.objects(crit, EX.membro)}
                ids = ", ".join(str(i) for i in sorted(membros))
                partes.append(f"{alias}.{chave} IN ({ids})")

            else:
                raise ErroSemantico(f"Tipo de critério não suportado: {tipo}")

        p.rastros.append(self._rastro(conceito, d, p.data_regra, membros))
        return "\n      AND ".join(partes) if partes else "TRUE"

    # ----------------------------------------------- intenção -> SQL completo
    def compilar(self, intencao: dict, hoje: date) -> tuple[str, list[Periodo]]:
        conceito = self.resolver_conceito(intencao["conceito"])
        tab_cli, chave_cli = self._tabela_de(conceito)
        modo = intencao.get("modo_temporal", "como_era")
        if modo not in ("como_era", "definicao_atual"):
            raise ErroSemantico(f"modo_temporal inválido: {modo}")

        periodos = []
        for pr in intencao["periodos"]:
            ref = date.fromisoformat(pr["data_ref"])
            periodos.append(Periodo(pr["rotulo"], ref, ref if modo == "como_era" else hoje))

        ctes = []
        for p in periodos:
            cond = self.condicao(conceito, "c", p)
            ctes.append(
                f"p_{p.rotulo} AS (\n  SELECT c.{chave_cli} AS cliente_id, '{p.rotulo}' AS periodo\n"
                f"  FROM {tab_cli} c\n  WHERE {cond}\n)")
        uniao = "\n  UNION ALL ".join(f"SELECT * FROM p_{p.rotulo}" for p in periodos)
        ctes.append(f"membros AS (\n  {uniao}\n)")

        fk = self.g.value(EX.resideEm, MAP.colunaFK)
        tab_b, chave_b = self._tabela_de(EX.Bairro)
        juncao = (f"FROM membros m\nJOIN {tab_cli} c ON c.{chave_cli} = m.cliente_id\n"
                  f"JOIN {tab_b} b ON b.{chave_b} = c.{fk}")

        op, grupo = intencao.get("operacao", "contar"), intencao.get("agrupar_por")
        if op == "contar" and grupo == "bairro":
            corpo = (f"SELECT b.nome AS bairro, m.periodo, COUNT(*) AS quantidade\n{juncao}\n"
                     "GROUP BY b.nome, m.periodo\nORDER BY b.nome, m.periodo")
        elif op == "contar":
            corpo = "SELECT m.periodo, COUNT(*) AS quantidade\nFROM membros m\nGROUP BY m.periodo\nORDER BY m.periodo"
        elif op == "listar":
            col_email = self.g.value(EX.email, MAP.coluna)
            corpo = (f"SELECT c.nome, c.{col_email} AS email, b.nome AS bairro,\n"
                     "       string_agg(m.periodo, ', ' ORDER BY m.periodo) AS vip_em\n"
                     f"{juncao}\nGROUP BY c.{chave_cli}, c.nome, c.{col_email}, b.nome\nORDER BY c.nome")
        else:
            raise ErroSemantico(f"Operação/agrupamento não suportado: {op}/{grupo}")

        return "WITH " + ",\n".join(ctes) + "\n" + corpo, periodos


def avisos_de_mudanca(periodos: list[Periodo]) -> list[str]:
    """Compara as definições usadas entre períodos e explica o que mudou."""
    avisos = []
    por_conceito: dict[str, list[tuple[Periodo, Rastro]]] = {}
    for p in periodos:
        for r in p.rastros:
            por_conceito.setdefault(r.conceito, []).append((p, r))
    for conceito, itens in por_conceito.items():
        for (pa, ra), (pb, rb) in zip(itens, itens[1:]):
            if ra.definicao == rb.definicao:
                continue
            msg = f"'{conceito}' usa definições diferentes: {pa.rotulo} → {ra.rotulo_definicao}; {pb.rotulo} → {rb.rotulo_definicao}."
            if ra.membros is not None and rb.membros is not None:
                entrou = sorted(set(rb.membros.values()) - set(ra.membros.values()))
                saiu = sorted(set(ra.membros.values()) - set(rb.membros.values()))
                if entrou:
                    msg += f" Entraram em {pb.rotulo}: {', '.join(entrou)}."
                if saiu:
                    msg += f" Saíram em {pb.rotulo}: {', '.join(saiu)}."
            avisos.append(msg)
    return avisos


def membros_por_periodo(periodos: list[Periodo], conceito_rotulo: str) -> dict[str, set[str]]:
    out = {}
    for p in periodos:
        for r in p.rastros:
            if r.conceito == conceito_rotulo and r.membros is not None:
                out[p.rotulo] = set(r.membros.values())
    return out
