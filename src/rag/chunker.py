"""
Chunker Hierárquico Especializado para Legislação e Documentos Fiscais.
Desenvolvido para a solução Sócio Digital (RES-IA Challenge 2 - Ciência de Dados).

Evita o "chunking ingênuo" por quantidade cega de caracteres, preservando:
1. A integridade do Artigo, Parágrafo e Incisos.
2. Injeção de Contexto (Context Injection) em cada chunk para que o embedding
   e o LLM compreendam de qual lei e artigo o trecho se origina.
3. Extração automatizada de metadados fiscais (CNAE, MEI, Simples, Fator R, etc.).
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class LegalChunk:
    chunk_id: str
    source_doc: str
    artigo: str
    paragrafo: str
    tema: str
    content: str
    raw_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_doc": self.source_doc,
            "artigo": self.artigo,
            "paragrafo": self.paragrafo,
            "tema": self.tema,
            "content": self.content,
            "raw_text": self.raw_text,
            "metadata": self.metadata,
        }


class LegalHierarchicalChunker:
    """
    Parser e Chunker com consciência da estrutura legislativa brasileira.
    """

    ARTICLE_REGEX = re.compile(
        r"(?:^|\n)(?:###?\s*)?(Art\.\s*\d+[-A-Za-zºo\.]*(?:\s*,\s*§\s*[\d\wºo\.-]+)?(?:\s*\([^\)]+\))?)",
        re.MULTILINE | re.IGNORECASE,
    )
    PARAGRAPH_REGEX = re.compile(
        r"(?:^|\n)(§\s*\d+[-A-Za-zºo\.]*|Parágrafo\s+único)",
        re.MULTILINE | re.IGNORECASE,
    )
    CHAPTER_REGEX = re.compile(
        r"(?:^|\n)##\s*(CAPÍTULO|SEÇÃO|TÍTULO)\s+([^\n]+)",
        re.MULTILINE | re.IGNORECASE,
    )

    def __init__(self, max_chunk_chars: int = 1200, min_chunk_chars: int = 150):
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars

    def extract_tax_tags(self, text: str) -> List[str]:
        """Detecta categorias fiscais relevantes a partir do vocabulário tributário."""
        text_lower = text.lower()
        tags = []
        mapping = {
            "mei": ["mei", "microempreendedor individual", "simei"],
            "simples_nacional": ["simples nacional", "lc 123", "cgsn"],
            "fator_r": ["fator r", "folha de salários", "anexo iii", "anexo v"],
            "limite_faturamento": ["receita bruta", "81.000", "360.000", "4.800.000", "rbt12"],
            "desenquadramento": ["desenquadramento", "excesso de receita", "20%"],
            "obrigacoes_acessorias": ["dasn-simei", "declaração anual", "31 de maio"],
            "parcelamento": ["parcelamento", "60 parcelas", "dívida ativa", "pgfn"],
            "certidoes": ["cnd", "cpen", "certidão negativa", "regularidade fiscal"],
            "tributos_das": ["irpj", "csll", "pis", "cofins", "cpp", "iss", "icms", "das"],
            "exclusao": ["termo de exclusão", "notificação", "30 dias"],
        }
        for category, keywords in mapping.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(category)
        return tags

    def chunk_document(self, text: str, source_doc: str) -> List[LegalChunk]:
        """
        Segmenta o documento respeitando os limites dos artigos e parágrafos.
        """
        chunks: List[LegalChunk] = []

        # Divide o texto principal por blocos de artigo
        sections = self._split_by_articles(text)

        for sec in sections:
            artigo_label = sec["artigo"]
            capitulo_label = sec.get("capitulo", "Geral")
            tema_label = sec.get("tema", artigo_label)
            art_text = sec["content"].strip()

            if not art_text:
                continue

            # Se o artigo completo couber dentro do tamanho máximo, mantém íntegro
            if len(art_text) <= self.max_chunk_chars:
                chunk_id = f"{self._sanitize_id(source_doc)}_{self._sanitize_id(artigo_label)}"
                enriched_content = (
                    f"[FONTE: {source_doc} | CAPÍTULO: {capitulo_label} | ARTIGO: {artigo_label} | TEMA: {tema_label}]\n"
                    f"{art_text}"
                )
                tags = self.extract_tax_tags(enriched_content)
                chunks.append(
                    LegalChunk(
                        chunk_id=chunk_id,
                        source_doc=source_doc,
                        artigo=artigo_label,
                        paragrafo="",
                        tema=tema_label,
                        content=enriched_content,
                        raw_text=art_text,
                        metadata={
                            "capitulo": capitulo_label,
                            "tags": tags,
                            "char_count": len(enriched_content),
                        },
                    )
                )
            else:
                # Artigo longo (ex: Art. 18 ou Art. 18-A) -> quebra hierárquica por parágrafos/incisos
                sub_chunks = self._split_article_by_paragraphs(
                    art_text=art_text,
                    artigo_label=artigo_label,
                    capitulo_label=capitulo_label,
                    tema_label=tema_label,
                    source_doc=source_doc,
                )
                chunks.extend(sub_chunks)

        return chunks

    def _split_by_articles(self, text: str) -> List[Dict[str, str]]:
        """Extrai os blocos correspondentes a cada artigo no markdown."""
        lines = text.split("\n")
        articles = []
        current_artigo = "Preâmbulo / Introdução"
        current_capitulo = "Geral"
        current_tema = "Abertura"
        current_lines = []

        for line in lines:
            chap_match = self.CHAPTER_REGEX.search(line)
            if chap_match:
                if current_lines and current_artigo != "Preâmbulo / Introdução":
                    articles.append({
                        "artigo": current_artigo,
                        "capitulo": current_capitulo,
                        "tema": current_tema,
                        "content": "\n".join(current_lines),
                    })
                    current_lines = []
                    current_artigo = "Preâmbulo / Introdução"
                    current_tema = "Abertura"
                current_capitulo = line.strip("# ").strip()
                continue

            art_match = self.ARTICLE_REGEX.search(line)
            if art_match:
                if current_lines:
                    articles.append({
                        "artigo": current_artigo,
                        "capitulo": current_capitulo,
                        "tema": current_tema,
                        "content": "\n".join(current_lines),
                    })
                    current_lines = []

                matched_raw = art_match.group(1).strip()
                if "(" in matched_raw and ")" in matched_raw:
                    parts = matched_raw.split("(")
                    current_artigo = parts[0].strip()
                    current_tema = parts[1].replace(")", "").strip()
                else:
                    current_artigo = matched_raw
                    current_tema = matched_raw

                # Se a linha contiver texto após o marcador do artigo, inclui
                clean_line = self.ARTICLE_REGEX.sub("", line).strip("# ").strip()
                if clean_line:
                    current_lines.append(clean_line)
            else:
                current_lines.append(line)

        if current_lines:
            articles.append({
                "artigo": current_artigo,
                "capitulo": current_capitulo,
                "tema": current_tema,
                "content": "\n".join(current_lines),
            })

        return articles

    def _split_article_by_paragraphs(
        self,
        art_text: str,
        artigo_label: str,
        capitulo_label: str,
        tema_label: str,
        source_doc: str,
    ) -> List[LegalChunk]:
        """Subdivide artigos extensos preservando o Caput como âncora contextual."""
        paragraphs = re.split(r"(?=\n(?:§\s*\d+|Parágrafo\s+único))", art_text)
        sub_chunks: List[LegalChunk] = []

        # O primeiro elemento costuma ser o Caput do artigo
        caput = paragraphs[0].strip() if paragraphs else ""
        caput_anchor = caput[:200] + "..." if len(caput) > 200 else caput

        for idx, p in enumerate(paragraphs):
            p_clean = p.strip()
            if not p_clean:
                continue

            p_match = self.PARAGRAPH_REGEX.search(p_clean)
            paragrafo_label = p_match.group(1) if p_match else f"Trecho {idx+1}"

            # Injeta o cabeçalho contextual completo
            context_header = (
                f"[FONTE: {source_doc} | CAPÍTULO: {capitulo_label} | ARTIGO: {artigo_label} | "
                f"PARÁGRAFO: {paragrafo_label} | TEMA: {tema_label}]\n"
                f"Contexto do Artigo: {caput_anchor}\n"
            )

            full_chunk_text = context_header + p_clean
            chunk_id = f"{self._sanitize_id(source_doc)}_{self._sanitize_id(artigo_label)}_p{idx+1}"
            tags = self.extract_tax_tags(full_chunk_text)

            sub_chunks.append(
                LegalChunk(
                    chunk_id=chunk_id,
                    source_doc=source_doc,
                    artigo=artigo_label,
                    paragrafo=paragrafo_label,
                    tema=tema_label,
                    content=full_chunk_text,
                    raw_text=p_clean,
                    metadata={
                        "capitulo": capitulo_label,
                        "paragrafo": paragrafo_label,
                        "tags": tags,
                        "is_subchunk": True,
                        "char_count": len(full_chunk_text),
                    },
                )
            )

        return sub_chunks

    @staticmethod
    def _sanitize_id(text: str) -> str:
        clean = re.sub(r"[^\w\d]+", "_", text.lower()).strip("_")
        return clean
