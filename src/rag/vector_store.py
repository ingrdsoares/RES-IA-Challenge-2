"""
Gerenciamento de Vector Store e Embeddings para o Sócio Digital.
Frente de Ciência de Dados (Jhessica).

Suporta:
- Embeddings multilíngues densos via SentenceTransformers (ou fallback TF-IDF/sklearn).
- Persistência em banco relacional/vetorial local (SQLite + vetores serializados).
- Filtragem por metadados fiscais (ex.: tags={'mei'}, tipo='lei_complementar').
"""

import json
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

from .chunker import LegalChunk


class LegalVectorStore:
    """
    Armazenamento vetorial leve, determinístico e autônomo com persistência SQLite.
    """

    def __init__(
        self,
        db_path: str = "data/processed/vector_index.db",
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        use_dense: bool = True,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.use_dense = use_dense
        self.model = None
        self._init_model()
        self._init_db()

    def _init_model(self):
        """Inicializa o modelo de embedding com fallback gracioso se não houver rede."""
        if self.use_dense:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                print(f"[VectorStore] Modelo de embeddings denso carregado: {self.model_name}")
            except Exception as e:
                print(f"[VectorStore] Aviso: fallback para embedding TF-IDF/Count devido a: {e}")
                self.use_dense = False

        if not self.use_dense:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
            self.model = None

    def _init_db(self):
        """Cria as tabelas de armazenamento dos chunks e vetores."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legal_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_doc TEXT,
                    artigo TEXT,
                    paragrafo TEXT,
                    tema TEXT,
                    content TEXT,
                    raw_text TEXT,
                    metadata_json TEXT,
                    embedding BLOB
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artigo ON legal_chunks(artigo)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON legal_chunks(source_doc)")
            conn.commit()

    def encode(self, texts: List[str]) -> np.ndarray:
        """Gera vetores normalizados para os textos fornecidos."""
        if self.use_dense and self.model is not None:
            embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return embeddings.astype(np.float32)
        else:
            # Fallback com TF-IDF normalizado
            if not hasattr(self, "tfidf_fitted") or not self.tfidf_fitted:
                matrix = self.tfidf.fit_transform(texts)
                self.tfidf_fitted = True
            else:
                matrix = self.tfidf.transform(texts)
            arr = matrix.toarray().astype(np.float32)
            # Normalização L2
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return arr / norms

    def add_chunks(self, chunks: List[LegalChunk]):
        """Adiciona e indexa chunks na base vetorial."""
        if not chunks:
            return

        texts_to_embed = [c.content for c in chunks]
        embeddings = self.encode(texts_to_embed)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for chunk, emb in zip(chunks, embeddings):
                meta_json = json.dumps(chunk.metadata, ensure_ascii=False)
                emb_blob = emb.tobytes()

                cursor.execute("""
                    INSERT OR REPLACE INTO legal_chunks (
                        chunk_id, source_doc, artigo, paragrafo, tema,
                        content, raw_text, metadata_json, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk.chunk_id,
                    chunk.source_doc,
                    chunk.artigo,
                    chunk.paragrafo,
                    chunk.tema,
                    chunk.content,
                    chunk.raw_text,
                    meta_json,
                    emb_blob,
                ))
            conn.commit()

        print(f"[VectorStore] {len(chunks)} chunks indexados com sucesso em {self.db_path}.")

    def search(
        self,
        query: str,
        top_k: int = 3,
        filter_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executa busca semântica por similaridade de cosseno com filtragem opcional.
        """
        # Carrega os chunks do SQLite
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chunk_id, source_doc, artigo, paragrafo, tema, content, raw_text, metadata_json, embedding
                FROM legal_chunks
            """)
            rows = cursor.fetchall()

        if not rows:
            return []

        # Vetoriza a consulta do usuário
        query_vec = self.encode([query])[0]

        results = []
        for row in rows:
            chunk_id, source_doc, artigo, paragrafo, tema, content, raw_text, meta_json, emb_blob = row
            metadata = json.loads(meta_json) if meta_json else {}

            # Filtro por tags se solicitado
            if filter_tags:
                chunk_tags = set(metadata.get("tags", []))
                if not any(tag.lower() in chunk_tags for tag in filter_tags):
                    continue

            # Reconstrói vetor e calcula similaridade
            vec = np.frombuffer(emb_blob, dtype=np.float32)
            if len(vec) != len(query_vec):
                continue

            similarity = float(np.dot(query_vec, vec))

            # Boost léxico para termos tributários e siglas normativas (ex: DASN-SIMEI, CPEN, Fator R)
            query_tokens = [w.lower().strip("?,.:;()\"'!") for w in query.split() if len(w) > 2]
            content_lower = content.lower()
            matches = sum(1 for token in query_tokens if token in content_lower)
            lexical_ratio = (matches / len(query_tokens)) if query_tokens else 0.0

            # Score Híbrido: 70% semântico denso + 30% correspondência léxica exata
            hybrid_score = round(0.70 * similarity + 0.30 * lexical_ratio, 4)

            results.append({
                "chunk_id": chunk_id,
                "score": hybrid_score,
                "dense_score": round(similarity, 4),
                "lexical_score": round(lexical_ratio, 4),
                "source_doc": source_doc,
                "artigo": artigo,
                "paragrafo": paragrafo,
                "tema": tema,
                "content": content,
                "raw_text": raw_text,
                "metadata": metadata,
            })

        # Ordena por score decrescente
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """Estatísticas do índice vetorial."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COUNT(DISTINCT artigo), COUNT(DISTINCT source_doc) FROM legal_chunks")
            total_chunks, total_artigos, total_docs = cursor.fetchone()

            cursor.execute("SELECT metadata_json FROM legal_chunks")
            all_tags = set()
            for (meta_json,) in cursor.fetchall():
                meta = json.loads(meta_json) if meta_json else {}
                for tag in meta.get("tags", []):
                    all_tags.add(tag)

        return {
            "total_chunks": total_chunks,
            "total_artigos": total_artigos,
            "total_docs": total_docs,
            "available_tags": sorted(list(all_tags)),
            "db_path": str(self.db_path),
        }
