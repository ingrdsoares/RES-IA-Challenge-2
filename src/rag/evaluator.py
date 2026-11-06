"""
Módulo de Avaliação Quantitativa e Benchmark de RAG para o Sócio Digital.
Frente: Ciência de Dados (Jhessica).
Finalidade: MLOps, governança métrica e comprovação de fidelidade (zero alucinação).
"""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.rag.service import RAGService, RespostaCopiloto


@dataclass
class EvaluationResult:
    id: str
    categoria: str
    pergunta: str
    deve_abster: bool
    se_absteve: bool
    guardrail_correto: bool
    artigos_esperados: List[str]
    artigos_retornados: List[str]
    context_recall: float
    context_precision: float
    faithfulness: float
    plano_3_passos_ok: bool
    crc_disclaimer_ok: bool
    aprovado: bool
    tempo_execucao_ms: float
    detalhes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkSummary:
    total_cenarios: int
    total_aprovados: int
    taxa_aprovacao_global: float
    context_recall_medio: float
    context_precision_medio: float
    faithfulness_medio: float
    guardrail_robustness: float
    conformidade_3_passos: float
    conformidade_crc: float
    tempo_medio_ms: float
    tempo_total_ms: float
    todos_aprovados: bool
    metadados_versao: Dict[str, Any] = field(default_factory=dict)
    cenarios: List[EvaluationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["cenarios"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in self.cenarios]
        return data


class RAGEvaluator:
    """
    Avaliador quantitativo do pipeline RAG + Motor Fiscal.
    Mede precisão, recall, fidelidade factual, robustez ética e conformidade legal.
    """

    def __init__(
        self,
        service: Optional[RAGService] = None,
        base_dir: Optional[Path] = None,
    ):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent.parent
        else:
            self.base_dir = Path(base_dir)

        self.service = service or RAGService(base_dir=self.base_dir)

    def carregar_ground_truth(self, caminho: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Carrega o dataset canônico de ground truth fiscal."""
        if caminho is None:
            caminho = self.base_dir / "data" / "benchmark" / "rag_ground_truth.json"

        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)

    def avaliar_cenario(self, cenario: Dict[str, Any]) -> EvaluationResult:
        """
        Avalia um cenário individual do benchmark contra os critérios canônicos.
        """
        cid = cenario["id"]
        cat = cenario.get("categoria", "geral")
        pergunta = cenario["pergunta"]
        ctx = cenario.get("contexto_empresa") or {}
        artigos_esperados = cenario.get("artigos_esperados", [])
        deve_abster = cenario.get("deve_abster", False)
        anexo_esperado = cenario.get("anexo_esperado")
        aliq_min = cenario.get("aliquota_esperada_min")
        aliq_max = cenario.get("aliquota_esperada_max")
        exige_3_passos = cenario.get("exige_3_passos", True)

        inicio = time.perf_counter()
        resposta: RespostaCopiloto = self.service.consultar(
            pergunta=pergunta,
            cnae=ctx.get("cnae"),
            faturamento_anual=ctx.get("faturamento_anual"),
            folha_anual=ctx.get("folha_anual"),
        )
        tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)

        # 1. Guardrail e Abstenção
        guardrail_correto = resposta.se_absteve == deve_abster

        # 2. Recuperação Vetorial (Context Recall & Context Precision)
        artigos_retornados = [f["artigo"] for f in resposta.fontes_citadas if f.get("artigo")]

        if deve_abster:
            context_recall = 1.0
            context_precision = 1.0
        elif not artigos_esperados:
            context_recall = 1.0
            context_precision = 1.0
        else:
            # Recall: todos os artigos esperados foram recuperados em algum chunk do Top K?
            encontrados = sum(
                1 for exp in artigos_esperados if any(exp in ret for ret in artigos_retornados)
            )
            context_recall = round(encontrados / len(artigos_esperados), 4)

            # Precision @ 1: o Top 1 chunk coincide com algum dos artigos esperados?
            top1 = artigos_retornados[0] if artigos_retornados else ""
            top1_ok = any(exp in top1 for exp in artigos_esperados)
            context_precision = 1.0 if top1_ok else 0.0

        # 3. Faithfulness (Fidelidade Factual e Ausência de Alucinação)
        faithfulness = 1.0
        erros_faithfulness = []

        if deve_abster:
            if not resposta.se_absteve:
                faithfulness = 0.0
                erros_faithfulness.append("Deveria ter se abstido e respondeu.")
        else:
            if resposta.se_absteve:
                faithfulness = 0.0
                erros_faithfulness.append("Falso positivo de abstenção em pergunta válida.")

            # Validação do Anexo Aplicado
            if anexo_esperado:
                anexo_obtido = (resposta.calculo_detalhado or {}).get("anexo_aplicado")
                if anexo_obtido != anexo_esperado:
                    faithfulness = 0.0
                    erros_faithfulness.append(
                        f"Anexo divergente: esperado {anexo_esperado}, obtido {anexo_obtido}"
                    )

            # Validação da Alíquota Efetiva
            if aliq_min is not None and aliq_max is not None:
                aliq_obtida = (resposta.calculo_detalhado or {}).get("aliquota_efetiva")
                if aliq_obtida is None or not (aliq_min <= aliq_obtida <= aliq_max):
                    faithfulness = 0.0
                    erros_faithfulness.append(
                        f"Alíquota {aliq_obtida} fora da faixa [{aliq_min}, {aliq_max}]"
                    )

        # 4. Conformidade Estrutural (3 passos e disclaimer CRC)
        plano_3_passos_ok = len(resposta.plano_3_passos) == 3 if exige_3_passos else True
        crc_disclaimer_ok = "CRC" in resposta.disclaimer_crc and len(resposta.disclaimer_crc) > 20

        # 5. Critério de Aprovação do Cenário
        aprovado = (
            guardrail_correto
            and context_recall >= 0.99
            and context_precision >= 0.99
            and faithfulness >= 0.99
            and plano_3_passos_ok
            and crc_disclaimer_ok
        )

        return EvaluationResult(
            id=cid,
            categoria=cat,
            pergunta=pergunta,
            deve_abster=deve_abster,
            se_absteve=resposta.se_absteve,
            guardrail_correto=guardrail_correto,
            artigos_esperados=artigos_esperados,
            artigos_retornados=artigos_retornados,
            context_recall=context_recall,
            context_precision=context_precision,
            faithfulness=faithfulness,
            plano_3_passos_ok=plano_3_passos_ok,
            crc_disclaimer_ok=crc_disclaimer_ok,
            aprovado=aprovado,
            tempo_execucao_ms=tempo_ms,
            detalhes={
                "diagnostico_trecho": resposta.diagnostico[:120] + "...",
                "calculo_detalhado": resposta.calculo_detalhado,
                "motivo_abstencao": resposta.motivo_abstencao,
                "erros_faithfulness": erros_faithfulness,
            },
        )

    def executar_benchmark(
        self,
        ground_truth_path: Optional[Path] = None,
        export_json_path: Optional[Path] = None,
    ) -> BenchmarkSummary:
        """
        Executa a suíte de benchmark completa, consolida os indicadores e exporta para JSON.
        """
        cenarios_raw = self.carregar_ground_truth(ground_truth_path)
        resultados: List[EvaluationResult] = []

        tempo_global_inicio = time.perf_counter()
        for raw in cenarios_raw:
            res = self.avaliar_cenario(raw)
            resultados.append(res)
        tempo_total_ms = round((time.perf_counter() - tempo_global_inicio) * 1000, 2)

        total = len(resultados)
        aprovados = sum(1 for r in resultados if r.aprovado)
        recalls = [r.context_recall for r in resultados]
        precisions = [r.context_precision for r in resultados]
        faithfulnesses = [r.faithfulness for r in resultados]
        guardrails = [1.0 if r.guardrail_correto else 0.0 for r in resultados]
        passos = [1.0 if r.plano_3_passos_ok else 0.0 for r in resultados]
        crcs = [1.0 if r.crc_disclaimer_ok else 0.0 for r in resultados]
        tempos = [r.tempo_execucao_ms for r in resultados]

        summary = BenchmarkSummary(
            total_cenarios=total,
            total_aprovados=aprovados,
            taxa_aprovacao_global=round(aprovados / total, 4) if total > 0 else 0.0,
            context_recall_medio=round(sum(recalls) / total, 4) if total > 0 else 0.0,
            context_precision_medio=round(sum(precisions) / total, 4) if total > 0 else 0.0,
            faithfulness_medio=round(sum(faithfulnesses) / total, 4) if total > 0 else 0.0,
            guardrail_robustness=round(sum(guardrails) / total, 4) if total > 0 else 0.0,
            conformidade_3_passos=round(sum(passos) / total, 4) if total > 0 else 0.0,
            conformidade_crc=round(sum(crcs) / total, 4) if total > 0 else 0.0,
            tempo_medio_ms=round(sum(tempos) / total, 2) if total > 0 else 0.0,
            tempo_total_ms=tempo_total_ms,
            todos_aprovados=(aprovados == total),
            metadados_versao={
                "frente": "Ciência de Dados (Jhessica)",
                "projeto": "Sócio Digital — RES-IA Challenge 2",
                "versao_rag": "2.0.0-factual-hybrid",
                "modelo_embeddings": "SentenceTransformers / Hybrid Fallback",
                "integracoes": [
                    "LegalVectorStore (SQLite)",
                    "FiscalCalculator (LC 123/2006)",
                    "TaxEntityExtractor (Regex + Semantics)",
                    "Guardrails Éticos e de Abstenção",
                ],
            },
            cenarios=resultados,
        )

        if export_json_path:
            p = Path(export_json_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"[RAGEvaluator] Resultados do benchmark exportados para {p}")

        return summary
