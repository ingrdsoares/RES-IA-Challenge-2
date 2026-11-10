"""
Pipeline de Ingestão de Dados Fiscais Estruturados (CNAEs e Tabelas do Simples Nacional).
Sócio Digital — RES-IA Challenge 2 (Engenharia de Dados & Dev - Lucas).
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class FiscalIngestionPipeline:
    def __init__(
        self,
        raw_tabelas_path: str,
        raw_cnaes_path: str,
        db_path: str,
        manifest_path: str,
    ):
        self.raw_tabelas_path = Path(raw_tabelas_path)
        self.raw_cnaes_path = Path(raw_cnaes_path)
        self.db_path = Path(db_path)
        self.manifest_path = Path(manifest_path)

    @staticmethod
    def _compute_sha256(filepath: Path) -> str:
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def run(self) -> Dict[str, Any]:
        print("[FiscalIngestion] Iniciando ingestão das tabelas do Simples e base de CNAEs...")

        if not self.raw_tabelas_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {self.raw_tabelas_path}")
        if not self.raw_cnaes_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {self.raw_cnaes_path}")

        with open(self.raw_tabelas_path, "r", encoding="utf-8") as f:
            tabelas_data = json.load(f)

        with open(self.raw_cnaes_path, "r", encoding="utf-8") as f:
            cnaes_data = json.load(f)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # 1. Tabela de Parâmetros Gerais
        cur.execute(
            """
            CREATE TABLE parametros_fiscais (
                chave TEXT PRIMARY KEY,
                valor_texto TEXT,
                valor_numerico REAL,
                descricao TEXT
            )
            """
        )

        cur.executemany(
            """
            INSERT INTO parametros_fiscais (chave, valor_texto, valor_numerico, descricao)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("versao_legal", tabelas_data["versao_legal"], None, "Fundamentação legal"),
                (
                    "limite_anual_simples",
                    None,
                    tabelas_data["limite_anual_simples"],
                    "Teto anual do Simples Nacional (R$)",
                ),
                (
                    "limite_anual_mei",
                    None,
                    tabelas_data["limite_anual_mei"],
                    "Teto anual do MEI (R$)",
                ),
                (
                    "tolerancia_limite_mei",
                    None,
                    tabelas_data["tolerancia_limite_mei_percentual"],
                    "Tolerância de 20% do MEI",
                ),
                (
                    "salario_minimo_referencia",
                    None,
                    tabelas_data["salario_minimo_referencia"],
                    "Salário Mínimo de Referência",
                ),
                (
                    "mei_inss_percentual",
                    None,
                    tabelas_data["mei_taxas"]["inss_percentual"],
                    "Alíquota INSS sobre Salário Mínimo",
                ),
                (
                    "mei_icms_fixo",
                    None,
                    tabelas_data["mei_taxas"]["icms_fixo"],
                    "Taxa fixa mensal ICMS",
                ),
                (
                    "mei_iss_fixo",
                    None,
                    tabelas_data["mei_taxas"]["iss_fixo"],
                    "Taxa fixa mensal ISS",
                ),
            ],
        )

        # 2. Tabela dos Anexos do Simples Nacional
        cur.execute(
            """
            CREATE TABLE faixas_simples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anexo TEXT NOT NULL,
                nome_anexo TEXT NOT NULL,
                tipo_anexo TEXT NOT NULL,
                sujeito_fator_r INTEGER NOT NULL,
                faixa INTEGER NOT NULL,
                de REAL NOT NULL,
                ate REAL NOT NULL,
                aliquota_nominal REAL NOT NULL,
                parcela_deduzir REAL NOT NULL,
                reparticao_json TEXT NOT NULL
            )
            """
        )

        cur.execute("CREATE INDEX idx_faixas_anexo ON faixas_simples(anexo, faixa)")
        cur.execute("CREATE INDEX idx_faixas_valores ON faixas_simples(anexo, de, ate)")

        total_faixas = 0
        for anexo_key, anexo_val in tabelas_data["anexos"].items():
            nome = anexo_val["nome"]
            tipo = anexo_val["tipo"]
            fator_r = 1 if anexo_val.get("sujeito_fator_r", False) else 0

            for fx in anexo_val["faixas"]:
                cur.execute(
                    """
                    INSERT INTO faixas_simples (
                        anexo, nome_anexo, tipo_anexo, sujeito_fator_r,
                        faixa, de, ate, aliquota_nominal, parcela_deduzir, reparticao_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        anexo_key,
                        nome,
                        tipo,
                        fator_r,
                        fx["faixa"],
                        fx["de"],
                        fx["ate"],
                        fx["aliquota_nominal"],
                        fx["parcela_deduzir"],
                        json.dumps(fx.get("reparticao", {}), ensure_ascii=False),
                    ),
                )
                total_faixas += 1

        # 3. Tabela de CNAEs
        cur.execute(
            """
            CREATE TABLE cnaes (
                codigo TEXT PRIMARY KEY,
                codigo_limpo TEXT NOT NULL UNIQUE,
                descricao TEXT NOT NULL,
                setor TEXT NOT NULL,
                anexo_padrao TEXT NOT NULL,
                sujeito_fator_r INTEGER NOT NULL,
                permitido_simples INTEGER NOT NULL,
                permitido_mei INTEGER NOT NULL,
                ocupacao_mei TEXT,
                tributos_json TEXT NOT NULL
            )
            """
        )

        cur.execute("CREATE INDEX idx_cnaes_codigo_limpo ON cnaes(codigo_limpo)")
        cur.execute("CREATE INDEX idx_cnaes_mei ON cnaes(permitido_mei)")
        cur.execute("CREATE INDEX idx_cnaes_anexo ON cnaes(anexo_padrao)")
        cur.execute("CREATE INDEX idx_cnaes_fator_r ON cnaes(sujeito_fator_r)")

        # 4. Tabela Virtual FTS5 para busca textual ultra-rápida
        cur.execute(
            """
            CREATE VIRTUAL TABLE cnaes_fts USING fts5(
                codigo,
                descricao,
                setor,
                ocupacao_mei,
                content='cnaes',
                content_rowid='rowid'
            )
            """
        )

        total_cnaes = 0
        total_mei_permitidos = 0
        total_fator_r = 0

        for item in cnaes_data:
            codigo = item["codigo"]
            codigo_limpo = "".join(filter(str.isdigit, codigo))
            sujeito_fator_r = 1 if item.get("sujeito_fator_r", False) else 0
            permitido_simples = 1 if item.get("permitido_simples", True) else 0
            permitido_mei = 1 if item.get("permitido_mei", False) else 0
            ocupacao_mei = item.get("ocupacao_mei")
            tributos = json.dumps(item.get("tributos", []), ensure_ascii=False)

            cur.execute(
                """
                INSERT INTO cnaes (
                    codigo, codigo_limpo, descricao, setor, anexo_padrao,
                    sujeito_fator_r, permitido_simples, permitido_mei, ocupacao_mei, tributos_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo,
                    codigo_limpo,
                    item["descricao"],
                    item.get("setor", "Outros"),
                    item["anexo_padrao"],
                    sujeito_fator_r,
                    permitido_simples,
                    permitido_mei,
                    ocupacao_mei,
                    tributos,
                ),
            )

            # Popula FTS5
            cur.execute(
                """
                INSERT INTO cnaes_fts (rowid, codigo, descricao, setor, ocupacao_mei)
                VALUES (last_insert_rowid(), ?, ?, ?, ?)
                """,
                (
                    codigo,
                    item["descricao"],
                    item.get("setor", "Outros"),
                    ocupacao_mei or "",
                ),
            )

            total_cnaes += 1
            if permitido_mei:
                total_mei_permitidos += 1
            if sujeito_fator_r:
                total_fator_r += 1

        conn.commit()
        conn.close()

        # 5. Manifesto de Ingestão e Governança de Dados
        manifest = {
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "pipeline": "FiscalIngestionPipeline",
            "db_path": str(self.db_path),
            "hashes": {
                "tabelas_simples_nacional.json": self._compute_sha256(self.raw_tabelas_path),
                "cnaes_base.json": self._compute_sha256(self.raw_cnaes_path),
            },
            "stats": {
                "total_anexos": len(tabelas_data["anexos"]),
                "total_faixas": total_faixas,
                "total_cnaes": total_cnaes,
                "total_cnaes_permitidos_mei": total_mei_permitidos,
                "total_cnaes_sujeitos_fator_r": total_fator_r,
                "anexos_disponiveis": list(tabelas_data["anexos"].keys()),
            },
        }

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"[FiscalIngestion] Sucesso! Banco gerado em {self.db_path}")
        print(
            f"[FiscalIngestion] {total_faixas} faixas indexadas e {total_cnaes} CNAEs catalogados."
        )
        return manifest
