"""
Gerenciamento de Vector Store e Embeddings para o Sócio Digital.
Frente de Ciência de Dados (Jhessica).

Suporta:
- Embeddings multilíngues densos via SentenceTransformers (ou fallback TF-IDF/sklearn).
- Persistência em banco relacional/vetorial local (SQLite + vetores serializados).
- Filtragem por metadados fiscais (ex.: tags={'mei'}, tipo='lei_complementar').
"""

import json
import math
import re
import sqlite3
import struct
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import numpy as np
except Exception:  # pragma: no cover - fallback leve para ambientes sem numpy
    np = None

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
        self._fallback_to_python = np is None
        self._fallback_vocab = None
        self._fallback_idf = None
        self._init_model()
        self._init_db()

    def _init_model(self):
        """Inicializa o modelo de embedding com fallback gracioso se não houver rede."""
        if self.use_dense and not self._fallback_to_python:
            try:
                from sentence_transformers import SentenceTransformer
                try:
                    self.model = SentenceTransformer(self.model_name, local_files_only=True)
                except Exception:
                    self.model = SentenceTransformer(self.model_name)
                print(f"[VectorStore] Modelo de embeddings denso carregado: {self.model_name}")
            except Exception as e:
                print(f"[VectorStore] Aviso: fallback para embedding TF-IDF/Count devido a: {e}")
                self.use_dense = False

        if not self.use_dense:
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                self.tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
                self.model = None
                print("[VectorStore] Uso de TF-IDF com sklearn habilitado.")
            except Exception as e:
                self.tfidf = None
                self.model = None
                self._fallback_to_python = True
                print(f"[VectorStore] Aviso: usando fallback puro em Python devido a: {e}")

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[\wÀ-ÿ]+", text.lower())

    def _encode_fallback(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        all_tokens = []
        for text in texts:
            all_tokens.extend(self._tokenize(text))

        vocab = sorted(set(all_tokens))
        self._fallback_vocab = {token: idx for idx, token in enumerate(vocab)}

        doc_freq = {token: 0 for token in vocab}
        for text in texts:
            present = set()
            for token in self._tokenize(text):
                if token in self._fallback_vocab and token not in present:
                    doc_freq[token] += 1
                    present.add(token)

        total_docs = max(len(texts), 1)
        self._fallback_idf = []
        for token in vocab:
            idf = math.log((1 + total_docs) / (1 + doc_freq.get(token, 0))) + 1.0
            self._fallback_idf.append(idf)

        vectors = []
        for text in texts:
            counts = {}
            for token in self._tokenize(text):
                counts[token] = counts.get(token, 0) + 1

            vec = [0.0] * len(vocab)
            for token, count in counts.items():
                if token in self._fallback_vocab:
                    idx = self._fallback_vocab[token]
                    vec[idx] = count * self._fallback_idf[idx]

            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)

        return vectors

    @staticmethod
    def _serialize_embedding(emb):
        if np is not None:
            return np.asarray(emb, dtype=np.float32).tobytes()
        return struct.pack(f"{len(emb)}f", *[float(x) for x in emb])

    @staticmethod
    def _deserialize_embedding(blob):
        if np is not None:
            return np.frombuffer(blob, dtype=np.float32)
        num_floats = len(blob) // 4
        return list(struct.unpack(f"{num_floats}f", blob))

    @staticmethod
    def _dot_product(a, b):
        if np is not None:
            return float(np.dot(a, b))
        return sum(x * y for x, y in zip(a, b))

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

    def encode(self, texts: List[str]):
        """Gera vetores normalizados para os textos fornecidos."""
        if self.use_dense and self.model is not None and np is not None:
            embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return embeddings.astype(np.float32)

        if self._fallback_to_python:
            return self._encode_fallback(texts)

        if self.tfidf is not None:
            if not hasattr(self, "tfidf_fitted") or not self.tfidf_fitted:
                matrix = self.tfidf.fit_transform(texts)
                self.tfidf_fitted = True
            else:
                matrix = self.tfidf.transform(texts)
            arr = matrix.toarray().astype(np.float32)
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return arr / norms

        return self._encode_fallback(texts)

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
                emb_blob = self._serialize_embedding(emb)

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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chunk_id, source_doc, artigo, paragrafo, tema, content, raw_text, metadata_json, embedding
                FROM legal_chunks
            """)
            rows = cursor.fetchall()

        if not rows:
            return []

        query_vec = self.encode([query])[0]

        results = []
        for row in rows:
            chunk_id, source_doc, artigo, paragrafo, tema, content, raw_text, meta_json, emb_blob = row
            metadata = json.loads(meta_json) if meta_json else {}

            if filter_tags:
                chunk_tags = set(metadata.get("tags", []))
                if not any(tag.lower() in chunk_tags for tag in filter_tags):
                    continue

            query_tokens = [w.lower().strip("?,.:;()\"'!") for w in query.split() if len(w) > 2]
            content_lower = content.lower()
            matches = sum(1 for token in query_tokens if token in content_lower)
            lexical_ratio = (matches / len(query_tokens)) if query_tokens else 0.0

            vec = self._deserialize_embedding(emb_blob)
            if len(vec) == len(query_vec):
                similarity = self._dot_product(query_vec, vec)
            else:
                similarity = lexical_ratio

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
