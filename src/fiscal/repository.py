"""
Repositório de Acesso a Dados Fiscais (SQLite).
Sócio Digital — RES-IA Challenge 2 (Lucas).
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, List, Optional

from src.fiscal.models import CNAEItem, FaixaSimples


class FiscalRepository:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Banco fiscal não encontrado em: {db_path}. Execute a ingestão antes."
            )

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_cnae_by_codigo(self, codigo: str) -> Optional[CNAEItem]:
        """Busca CNAE por código formatado (ex: '6201-5/01') ou numérico limpo (ex: '6201501')."""
        codigo_limpo = "".join(filter(str.isdigit, codigo))
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT codigo, codigo_limpo, descricao, setor, anexo_padrao,
                       sujeito_fator_r, permitido_simples, permitido_mei, ocupacao_mei, tributos_json
                FROM cnaes
                WHERE codigo = ? OR codigo_limpo = ?
                """,
                (codigo.strip(), codigo_limpo),
            )
            row = cur.fetchone()
            if not row:
                return None

            return CNAEItem(
                codigo=row["codigo"],
                codigo_limpo=row["codigo_limpo"],
                descricao=row["descricao"],
                setor=row["setor"],
                anexo_padrao=row["anexo_padrao"],
                sujeito_fator_r=bool(row["sujeito_fator_r"]),
                permitido_simples=bool(row["permitido_simples"]),
                permitido_mei=bool(row["permitido_mei"]),
                ocupacao_mei=row["ocupacao_mei"],
                tributos=json.loads(row["tributos_json"]),
            )

    def search_cnaes(self, query: str, limit: int = 10) -> List[CNAEItem]:
        """Busca flexível de CNAE por palavras-chave na descrição, ocupação MEI ou código."""
        query_str = query.strip()
        if not query_str:
            return []

        with self._get_connection() as conn:
            cur = conn.cursor()

            # Tenta via FTS5 primeiro
            try:
                # Sanitiza query para FTS5
                sanitized_fts = " ".join([f'"{term}"*' for term in query_str.split() if term])
                cur.execute(
                    """
                    SELECT c.codigo, c.codigo_limpo, c.descricao, c.setor, c.anexo_padrao,
                           c.sujeito_fator_r, c.permitido_simples, c.permitido_mei, c.ocupacao_mei, c.tributos_json
                    FROM cnaes c
                    JOIN cnaes_fts f ON c.rowid = f.rowid
                    WHERE cnaes_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (sanitized_fts, limit),
                )
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                rows = []

            # Se não encontrou por FTS5, tenta LIKE tradicional
            if not rows:
                pattern = f"%{query_str}%"
                cur.execute(
                    """
                    SELECT codigo, codigo_limpo, descricao, setor, anexo_padrao,
                           sujeito_fator_r, permitido_simples, permitido_mei, ocupacao_mei, tributos_json
                    FROM cnaes
                    WHERE descricao LIKE ? OR ocupacao_mei LIKE ? OR codigo LIKE ? OR setor LIKE ?
                    LIMIT ?
                    """,
                    (pattern, pattern, pattern, pattern, limit),
                )
                rows = cur.fetchall()

            results = []
            for row in rows:
                results.append(
                    CNAEItem(
                        codigo=row["codigo"],
                        codigo_limpo=row["codigo_limpo"],
                        descricao=row["descricao"],
                        setor=row["setor"],
                        anexo_padrao=row["anexo_padrao"],
                        sujeito_fator_r=bool(row["sujeito_fator_r"]),
                        permitido_simples=bool(row["permitido_simples"]),
                        permitido_mei=bool(row["permitido_mei"]),
                        ocupacao_mei=row["ocupacao_mei"],
                        tributos=json.loads(row["tributos_json"]),
                    )
                )
            return results

    def list_mei_cnaes(self, limit: int = 50) -> List[CNAEItem]:
        """Retorna lista de CNAEs permitidos no enquadramento MEI."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT codigo, codigo_limpo, descricao, setor, anexo_padrao,
                       sujeito_fator_r, permitido_simples, permitido_mei, ocupacao_mei, tributos_json
                FROM cnaes
                WHERE permitido_mei = 1
                ORDER BY ocupacao_mei ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
            return [
                CNAEItem(
                    codigo=r["codigo"],
                    codigo_limpo=r["codigo_limpo"],
                    descricao=r["descricao"],
                    setor=r["setor"],
                    anexo_padrao=r["anexo_padrao"],
                    sujeito_fator_r=bool(r["sujeito_fator_r"]),
                    permitido_simples=bool(r["permitido_simples"]),
                    permitido_mei=bool(r["permitido_mei"]),
                    ocupacao_mei=r["ocupacao_mei"],
                    tributos=json.loads(r["tributos_json"]),
                )
                for r in rows
            ]

    def get_faixas_by_anexo(self, anexo: str) -> List[FaixaSimples]:
        """Retorna as faixas de um determinado anexo (I, II, III, IV ou V)."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT faixa, de, ate, aliquota_nominal, parcela_deduzir, reparticao_json
                FROM faixas_simples
                WHERE UPPER(anexo) = UPPER(?)
                ORDER BY faixa ASC
                """,
                (anexo.strip(),),
            )
            rows = cur.fetchall()
            return [
                FaixaSimples(
                    faixa=r["faixa"],
                    de=r["de"],
                    ate=r["ate"],
                    aliquota_nominal=r["aliquota_nominal"],
                    parcela_deduzir=r["parcela_deduzir"],
                    reparticao=json.loads(r["reparticao_json"]),
                )
                for r in rows
            ]

    def get_faixa_adequada(self, anexo: str, rbt12: float) -> Optional[FaixaSimples]:
        """Localiza a faixa tributária exata com base no faturamento acumulado dos últimos 12 meses (RBT12)."""
        faixas = self.get_faixas_by_anexo(anexo)
        if not faixas:
            return None

        # RBT12 até o início da primeira faixa
        if rbt12 <= 0:
            return faixas[0]

        for fx in faixas:
            if fx.de <= rbt12 <= fx.ate:
                return fx

        # Se ultrapassou a última faixa (4.800.000), retorna a última faixa
        return faixas[-1]

    def get_parametro(self, chave: str) -> Any:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT valor_texto, valor_numerico FROM parametros_fiscais WHERE chave = ?",
                (chave,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return (
                row["valor_numerico"] if row["valor_numerico"] is not None else row["valor_texto"]
            )
