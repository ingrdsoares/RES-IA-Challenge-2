"""
Script de Validação e Teste do Pipeline de Ingestão e Recuperação RAG.
Sócio Digital — RES-IA Challenge 2 (Ciência de Dados - Jhessica).
"""

import sys
from pathlib import Path

# Adiciona o diretório base ao sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.rag.ingest import IngestionPipeline
from src.rag.vector_store import LegalVectorStore


def run_pipeline_validation():
    print("=" * 70)
    print(" SÓCIO DIGITAL — TESTE DE INGESTÃO E RECUPERAÇÃO HIERÁRQUICA RAG")
    print(" Responsável: Jhessica (Ciência de Dados)")
    print("=" * 70)

    raw_dir = str(BASE_DIR / "data" / "raw")
    db_path = str(BASE_DIR / "data" / "processed" / "vector_index.db")
    manifest_path = str(BASE_DIR / "data" / "processed" / "manifest.json")

    # 1. Executa Ingestão
    print("\n[Etapa 1] Executando Ingestão e Chunking Hierárquico...")
    pipeline = IngestionPipeline(
        raw_dir=raw_dir,
        db_path=db_path,
        manifest_path=manifest_path,
        use_dense=True,  # Modelo multilíngue denso de embeddings (384 dimensões)
    )
    manifest = pipeline.run()

    stats = manifest.get("stats", {})
    print(f" -> Total de Chunks no Banco: {stats.get('total_chunks')}")
    print(f" -> Total de Artigos Mapeados: {stats.get('total_artigos')}")
    print(f" -> Tags Fiscais Encontradas: {', '.join(stats.get('available_tags', []))}")

    # 2. Testes Canônicos de Recuperação Factual
    vector_store = LegalVectorStore(db_path=db_path, use_dense=True)

    test_queries = [
        {
            "pergunta": "Qual é o limite de faturamento anual do MEI e o que acontece se ultrapassar 20%?",
            "artigo_esperado": "Art. 18-A",
            "tag": "mei",
        },
        {
            "pergunta": "Como calcular o Fator R para saber se a empresa entra no Anexo III ou Anexo V com folha de 28%?",
            "artigo_esperado": "Art. 18",
            "tag": "fator_r",
        },
        {
            "pergunta": "Qual é a data limite para entregar a declaração anual DASN-SIMEI do MEI?",
            "artigo_esperado": "Art. 106",
            "tag": "obrigacoes_acessorias",
        },
        {
            "pergunta": "O que é Certidão Positiva com Efeitos de Negativa CPEN e como ela comprova regularidade?",
            "artigo_esperado": "Art. 1º",
            "tag": "certidoes",
        },
    ]

    print("\n[Etapa 2] Executando Casos de Teste de Recuperação:")
    print("-" * 70)

    sucessos = 0
    for idx, t in enumerate(test_queries, 1):
        print(f"\n[Caso {idx}] Pergunta: \"{t['pergunta']}\"")
        results = vector_store.search(t["pergunta"], top_k=2)

        if not results:
            print("  [FALHA] Nenhum resultado retornado.")
            continue

        top_hit = results[0]
        print(f"  -> Top 1 Score: {top_hit['score']}")
        print(f"  -> Artigo Recuperado: {top_hit['artigo']}")
        print(f"  -> Documento: {top_hit['source_doc']}")
        print(f"  -> Tags: {top_hit['metadata'].get('tags')}")
        print(f"  -> Trecho do Conteúdo:\n     " + top_hit['raw_text'][:220].replace('\n', ' ') + "...")

        # Validação
        if t["artigo_esperado"] in top_hit["artigo"]:
            print("  [OK] Artigo correto recuperado com máxima relevância!")
            sucessos += 1
        else:
            print(f"  [AVISO] Esperava '{t['artigo_esperado']}', obteve '{top_hit['artigo']}'")

    print("\n" + "=" * 70)
    print(f" RESULTADO FINAL: {sucessos}/{len(test_queries)} casos recuperados com sucesso!")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline_validation()
