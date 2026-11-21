"""
Cria o banco analítico de exemplo (DuckDB): tabelas `bairro` e `cliente`.

Repare: NÃO existe coluna "vip" nem "bairro_nobre". Esses são conceitos de
negócio — interpretações — e vão morar na ontologia, não no banco.
"""
import random
from datetime import date, timedelta
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent
BANCO = RAIZ / "empresa.duckdb"

BAIRROS = [
    (1, "Meireles"), (2, "Aldeota"), (3, "Cocó"), (4, "Varjota"),
    (5, "Guararapes"), (6, "Dionísio Torres"), (7, "Mucuripe"),
    (8, "Centro"), (9, "Benfica"), (10, "Parangaba"), (11, "Montese"),
    (12, "Messejana"),
]

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Hugo",
         "Íris", "João", "Karen", "Lucas", "Marina", "Nelson", "Olívia", "Paulo",
         "Rafaela", "Sérgio", "Tânia", "Vitor"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Lima", "Pereira", "Costa", "Rocha",
              "Almeida", "Barbosa", "Cavalcante", "Holanda", "Bezerra"]


def criar(n_clientes: int = 600, semente: int = 42) -> Path:
    rnd = random.Random(semente)
    if BANCO.exists():
        BANCO.unlink()
    con = duckdb.connect(str(BANCO))
    con.execute("CREATE TABLE bairro (id INTEGER PRIMARY KEY, nome VARCHAR, cidade VARCHAR)")
    con.executemany("INSERT INTO bairro VALUES (?, ?, 'Fortaleza')", BAIRROS)
    con.execute("""
        CREATE TABLE cliente (
            id INTEGER PRIMARY KEY,
            nome VARCHAR,
            email VARCHAR,
            data_cadastro DATE,
            bairro_id INTEGER REFERENCES bairro(id)
        )""")
    inicio = date(2014, 1, 1)
    fim = date(2026, 11, 1)
    linhas = []
    for i in range(1, n_clientes + 1):
        nome = f"{rnd.choice(NOMES)} {rnd.choice(SOBRENOMES)}"
        email = f"cliente{i:04d}@exemplo.com"
        dc = inicio + timedelta(days=rnd.randint(0, (fim - inicio).days))
        linhas.append((i, nome, email, dc, rnd.randint(1, len(BAIRROS))))
    con.executemany("INSERT INTO cliente VALUES (?, ?, ?, ?, ?)", linhas)
    con.close()
    return BANCO


if __name__ == "__main__":
    print("Banco criado em", criar())
