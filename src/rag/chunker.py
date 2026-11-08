"""
Chunker Hierárquico Especializado para Legislação e Documentos Fiscais.
Desenvolvido para a solução Sócio Digital (RES-IA Challenge 2 - Ciência de Dados).

Estratégia de Chunking Conforme Plano de Entrega:
1. Segmentação Hierárquica Jurídica:
   - Preservação da unidade de sentido de Artigos, Caputs, Parágrafos (§), Incisos e Alíneas.
   - Suporte a documentos estruturados sem artigos (manuais, FAQs, acórdãos e portarias).
2. Janela de Tamanho Máximo e Sobreposição:
   - Limite máximo por chunk: até 2.000 caracteres.
   - Sobreposição contextual (overlap): 200 caracteres quando houver necessidade de fracionamento.
3. Injeção de Contexto (Context Injection):
   - Cada chunk recebe cabeçalho explícito com Fonte, Document ID, Artigo, Parágrafo e Tema,
     ancorando semanticamente o embedding (Qwen3-Embedding 1024d) e o LLM (Qwen3 8B).
4. Extração de Metadados Fiscais Especializados:
   - Tags para MEI, Simples Nacional, Lucro Presumido, Fator R, Prazos/DASN, ISS/DF, ICMS/DF, CPEN/CND e Jurisprudência.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LegalChunk:
    chunk_id: str
    source_doc: str
    artigo: str
    paragrafo: str
    tema: str
    content: str
    raw_text: str
    document_id: str = ""
    title: str = ""
    reference_date: Optional[str] = None
    effective_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_doc": self.source_doc,
            "title": self.title,
            "artigo": self.artigo,
            "paragrafo": self.paragrafo,
            "tema": self.tema,
            "content": self.content,
            "raw_text": self.raw_text,
            "reference_date": self.reference_date,
            "effective_date": self.effective_date,
            "metadata": self.metadata,
        }

    def to_qdrant_point(self, vector: List[float], point_id: Any = None) -> Dict[str, Any]:
        """Converte o chunk para o formato de ponto indexável no Qdrant (matching Source schema)."""
        pid = point_id if point_id is not None else self.chunk_id
        return {
            "id": pid,
            "vector": vector,
            "payload": {
                "text": self.content,
                "source": self.source_doc[:2048],
                "title": (self.title or self.source_doc)[:256],
                "document_id": self.document_id or None,
                "chunk_id": self.chunk_id,
                "reference_date": self.reference_date,
                "effective_date": self.effective_date,
                "artigo": self.artigo or None,
                "paragrafo": self.paragrafo or None,
                "tema": self.tema or None,
                "tags": self.metadata.get("tags", []),
            },
        }


class LegalHierarchicalChunker:
    """
    Parser e Chunker com consciência da estrutura legislativa brasileira e manuais técnicos.
    Parâmetros oficiais: até 2.000 caracteres por chunk com sobreposição de 200 caracteres.
    """

    # Sensível a maiúsculas e sem "da/do/,..." depois: "art. 8º da LC 87" em início de linha é citação.
    # ponytail: citação entre aspas de outra norma ("Art. 8° Integra...") ainda vira rótulo;
    # separar exige saber o que é transcrição.
    ARTICLE_REGEX = re.compile(
        r"(?:^|\n)(?:###?\s*)?((?:Art|ART)\.\s*\d+[-A-Za-zºo°\.]*(?:\s*,\s*§\s*[\d\wºo\.-]+)?(?:\s*\([^\)]+\))?)"
        r"(?!\w)(?!\s*,)(?!\s+(?:d[aeo]s?|dest[ae]|dess[ae]|e|ou|a|ao|à)\s)",
        re.MULTILINE,
    )
    PARAGRAPH_REGEX = re.compile(
        r"(?:^|\n)(§\s*\d+[-A-Za-zºo\.]*|Parágrafo\s+único)",
        re.MULTILINE | re.IGNORECASE,
    )
    CHAPTER_REGEX = re.compile(
        r"(?:^|\n)##\s*(CAPÍTULO|SEÇÃO|TÍTULO)\s+([^\n]+)",
        re.MULTILINE | re.IGNORECASE,
    )
    SECTION_HEADER_REGEX = re.compile(
        r"(?:^|\n)(#{1,4}\s+[^\n]+)",
        re.MULTILINE,
    )

    def __init__(
        self,
        max_chunk_chars: int = 2000,
        min_chunk_chars: int = 150,
        overlap_chars: int = 200,
    ):
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.overlap_chars = overlap_chars

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
            "obrigacoes_acessorias": [
                "dasn-simei",
                "declaração anual",
                "31 de maio",
                "dctfweb",
                "efd-reinf",
                "defis",
                "pgdas-d",
            ],
            "parcelamento": ["parcelamento", "60 parcelas", "dívida ativa", "pgfn", "regularize"],
            "certidoes": ["cnd", "cpen", "certidão negativa", "regularidade fiscal"],
            "tributos_das": ["irpj", "csll", "pis", "cofins", "cpp", "iss", "icms", "das"],
            "exclusao": ["termo de exclusão", "notificação", "30 dias"],
            "lucro_presumido": [
                "lucro presumido",
                "presunção de 8%",
                "presunção de 32%",
                "lei 9.249",
                "lei 9.430",
                "in 1700",
            ],
            "iss_df": [
                "iss/df",
                "distrito federal",
                "decreto 25.508",
                "decreto 25508",
                "nota fiscal avulsa",
                "nfse df",
                "sefaz-df",
            ],
            "icms_df": [
                "icms/df",
                "decreto 43.982",
                "decreto 43982",
                "substituição tributária",
                "difal",
                "ricms",
            ],
            "calendario_df": [
                "calendário fiscal",
                "vencimento",
                "portaria 11.460",
                "decreto 48.117",
                "data limite",
            ],
            "jurisprudencia": [
                "carf",
                "acórdão",
                "stj",
                "súmula",
                "recurso especial",
                "pejotização",
            ],
        }
        for category, keywords in mapping.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(category)
        return tags

    def chunk_document(
        self,
        text: str,
        source_doc: str,
        document_id: str = "",
        title: str = "",
        reference_date: Optional[str] = None,
        effective_date: Optional[str] = None,
    ) -> List[LegalChunk]:
        """
        Segmenta o documento respeitando os limites hierárquicos:
        - Se contiver artigos formais (Art. X), usa divisão legal por artigos e parágrafos.
        - Se for documento técnico/manual/faq/acórdão, segmenta por seções markdown com sobreposição de 200 caracteres.
        """
        doc_id = document_id or self._sanitize_id(source_doc)
        doc_title = title or source_doc

        has_articles = bool(self.ARTICLE_REGEX.search(text))

        if has_articles:
            return self._chunk_legislative_document(
                text=text,
                source_doc=source_doc,
                document_id=doc_id,
                title=doc_title,
                reference_date=reference_date,
                effective_date=effective_date,
            )
        else:
            return self._chunk_structured_document(
                text=text,
                source_doc=source_doc,
                document_id=doc_id,
                title=doc_title,
                reference_date=reference_date,
                effective_date=effective_date,
            )

    def _chunk_legislative_document(
        self,
        text: str,
        source_doc: str,
        document_id: str,
        title: str,
        reference_date: Optional[str],
        effective_date: Optional[str],
    ) -> List[LegalChunk]:
        """Segmentação de diplomas legislativos por Artigos, Caputs e Parágrafos."""
        chunks: List[LegalChunk] = []
        sections = self._split_by_articles(text)

        for sec in sections:
            artigo_label = sec["artigo"]
            capitulo_label = sec.get("capitulo", "Geral")
            tema_label = sec.get("tema", artigo_label)
            art_text = sec["content"].strip()

            if not art_text:
                continue

            if len(art_text) <= self.max_chunk_chars:
                chunk_id = f"{document_id}_{self._sanitize_id(artigo_label)}"
                enriched_content = (
                    f"[DOCUMENTO: {document_id} | FONTE: {source_doc} | CAPÍTULO: {capitulo_label} | ARTIGO: {artigo_label} | TEMA: {tema_label}]\n"
                    f"{art_text}"
                )
                tags = self.extract_tax_tags(enriched_content)
                chunks.append(
                    LegalChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        source_doc=source_doc,
                        title=title,
                        artigo=artigo_label,
                        paragrafo="",
                        tema=tema_label,
                        content=enriched_content,
                        raw_text=art_text,
                        reference_date=reference_date,
                        effective_date=effective_date,
                        metadata={
                            "document_id": document_id,
                            "capitulo": capitulo_label,
                            "tags": tags,
                            "char_count": len(enriched_content),
                            "is_subchunk": False,
                        },
                    )
                )
            else:
                sub_chunks = self._split_article_by_paragraphs(
                    art_text=art_text,
                    artigo_label=artigo_label,
                    capitulo_label=capitulo_label,
                    tema_label=tema_label,
                    source_doc=source_doc,
                    document_id=document_id,
                    title=title,
                    reference_date=reference_date,
                    effective_date=effective_date,
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
                    articles.append(
                        {
                            "artigo": current_artigo,
                            "capitulo": current_capitulo,
                            "tema": current_tema,
                            "content": "\n".join(current_lines),
                        }
                    )
                    current_lines = []
                    current_artigo = "Preâmbulo / Introdução"
                    current_tema = "Abertura"
                current_capitulo = line.strip("# ").strip()
                continue

            art_match = self.ARTICLE_REGEX.search(line)
            if art_match:
                if current_lines:
                    articles.append(
                        {
                            "artigo": current_artigo,
                            "capitulo": current_capitulo,
                            "tema": current_tema,
                            "content": "\n".join(current_lines),
                        }
                    )
                    current_lines = []

                matched_raw = art_match.group(1).strip()
                if "(" in matched_raw and ")" in matched_raw:
                    parts = matched_raw.split("(")
                    current_artigo = parts[0].strip()
                    current_tema = parts[1].replace(")", "").strip()
                else:
                    current_artigo = matched_raw
                    current_tema = matched_raw

                # O título markdown vira só rótulo; no corpo, o número do artigo fica.
                if line.lstrip().startswith("#"):
                    clean_line = self.ARTICLE_REGEX.sub("", line).strip("# ").strip()
                else:
                    clean_line = line.strip()
                if clean_line:
                    current_lines.append(clean_line)
            else:
                current_lines.append(line)

        if current_lines:
            articles.append(
                {
                    "artigo": current_artigo,
                    "capitulo": current_capitulo,
                    "tema": current_tema,
                    "content": "\n".join(current_lines),
                }
            )

        return articles

    def _split_article_by_paragraphs(
        self,
        art_text: str,
        artigo_label: str,
        capitulo_label: str,
        tema_label: str,
        source_doc: str,
        document_id: str,
        title: str,
        reference_date: Optional[str],
        effective_date: Optional[str],
    ) -> List[LegalChunk]:
        """Subdivide artigos extensos preservando o Caput como âncora contextual e overlap."""
        paragraphs = re.split(r"(?=\n(?:§\s*\d+|Parágrafo\s+único))", art_text)
        sub_chunks: List[LegalChunk] = []

        caput = paragraphs[0].strip() if paragraphs else ""
        caput_anchor = caput[:200] + "..." if len(caput) > 200 else caput

        for idx, p in enumerate(paragraphs):
            p_clean = p.strip()
            if not p_clean:
                continue

            p_match = self.PARAGRAPH_REGEX.search(p_clean)
            paragrafo_label = p_match.group(1) if p_match else f"Trecho {idx + 1}"

            context_header = (
                f"[DOCUMENTO: {document_id} | FONTE: {source_doc} | CAPÍTULO: {capitulo_label} | ARTIGO: {artigo_label} | "
                f"PARÁGRAFO: {paragrafo_label} | TEMA: {tema_label}]\n"
                f"Contexto do Artigo: {caput_anchor}\n"
            )

            if len(context_header + p_clean) > self.max_chunk_chars:
                window_chunks = self._sliding_window_split(
                    text=p_clean,
                    header=context_header,
                    base_id=f"{document_id}_{self._sanitize_id(artigo_label)}_p{idx + 1}",
                    source_doc=source_doc,
                    document_id=document_id,
                    title=title,
                    artigo_label=artigo_label,
                    paragrafo_label=paragrafo_label,
                    tema_label=tema_label,
                    reference_date=reference_date,
                    effective_date=effective_date,
                )
                sub_chunks.extend(window_chunks)
            else:
                full_chunk_text = context_header + p_clean
                chunk_id = f"{document_id}_{self._sanitize_id(artigo_label)}_p{idx + 1}"
                tags = self.extract_tax_tags(full_chunk_text)
                sub_chunks.append(
                    LegalChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        source_doc=source_doc,
                        title=title,
                        artigo=artigo_label,
                        paragrafo=paragrafo_label,
                        tema=tema_label,
                        content=full_chunk_text,
                        raw_text=p_clean,
                        reference_date=reference_date,
                        effective_date=effective_date,
                        metadata={
                            "document_id": document_id,
                            "capitulo": capitulo_label,
                            "paragrafo": paragrafo_label,
                            "tags": tags,
                            "is_subchunk": True,
                            "char_count": len(full_chunk_text),
                        },
                    )
                )

        return sub_chunks

    def _chunk_structured_document(
        self,
        text: str,
        source_doc: str,
        document_id: str,
        title: str,
        reference_date: Optional[str],
        effective_date: Optional[str],
    ) -> List[LegalChunk]:
        """Segmentação de manuais, resoluções, acórdãos e calendários por seções estruturadas."""
        chunks: List[LegalChunk] = []

        raw_sections = re.split(r"(?=\n#{1,3}\s+)", text)
        section_idx = 1

        for raw_sec in raw_sections:
            sec_clean = raw_sec.strip()
            if not sec_clean:
                continue

            first_line = sec_clean.split("\n", 1)[0].strip("# ")
            tema = first_line if first_line else f"Seção {section_idx}"

            context_header = f"[DOCUMENTO: {document_id} | FONTE: {source_doc} | SEÇÃO: {tema}]\n"

            if len(context_header + sec_clean) <= self.max_chunk_chars:
                chunk_id = f"{document_id}_sec{section_idx}"
                full_text = context_header + sec_clean
                tags = self.extract_tax_tags(full_text)
                chunks.append(
                    LegalChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        source_doc=source_doc,
                        title=title,
                        artigo=f"Seção: {tema[:60]}",
                        paragrafo="",
                        tema=tema,
                        content=full_text,
                        raw_text=sec_clean,
                        reference_date=reference_date,
                        effective_date=effective_date,
                        metadata={
                            "document_id": document_id,
                            "tags": tags,
                            "char_count": len(full_text),
                            "is_subchunk": False,
                        },
                    )
                )
            else:
                window_chunks = self._sliding_window_split(
                    text=sec_clean,
                    header=context_header,
                    base_id=f"{document_id}_sec{section_idx}",
                    source_doc=source_doc,
                    document_id=document_id,
                    title=title,
                    artigo_label=f"Seção: {tema[:60]}",
                    paragrafo_label="",
                    tema_label=tema,
                    reference_date=reference_date,
                    effective_date=effective_date,
                )
                chunks.extend(window_chunks)

            section_idx += 1

        return chunks

    def _sliding_window_split(
        self,
        text: str,
        header: str,
        base_id: str,
        source_doc: str,
        document_id: str,
        title: str,
        artigo_label: str,
        paragrafo_label: str,
        tema_label: str,
        reference_date: Optional[str],
        effective_date: Optional[str],
    ) -> List[LegalChunk]:
        """Aplica janela deslizante de até max_chunk_chars com sobreposição de overlap_chars."""
        header_len = len(header)
        max_body_len = max(self.max_chunk_chars - header_len - 20, 300)
        overlap = self.overlap_chars

        parts = []
        start = 0
        text_len = len(text)
        part_idx = 1

        while start < text_len:
            end = min(start + max_body_len, text_len)
            if end < text_len:
                last_newline = text.rfind("\n", start, end)
                if last_newline != -1 and last_newline > start + (max_body_len // 2):
                    end = last_newline
                else:
                    last_space = text.rfind(" ", start, end)
                    if last_space != -1 and last_space > start + (max_body_len // 2):
                        end = last_space

            slice_text = text[start:end].strip()
            if slice_text:
                full_chunk_text = header + slice_text
                chunk_id = f"{base_id}_w{part_idx}"
                tags = self.extract_tax_tags(full_chunk_text)
                parts.append(
                    LegalChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        source_doc=source_doc,
                        title=title,
                        artigo=artigo_label,
                        paragrafo=paragrafo_label,
                        tema=tema_label,
                        content=full_chunk_text,
                        raw_text=slice_text,
                        reference_date=reference_date,
                        effective_date=effective_date,
                        metadata={
                            "document_id": document_id,
                            "tags": tags,
                            "is_subchunk": True,
                            "window_part": part_idx,
                            "char_count": len(full_chunk_text),
                        },
                    )
                )
                part_idx += 1

            if end >= text_len:
                break
            start = max(end - overlap, start + 1)

        return parts

    @staticmethod
    def _sanitize_id(text: str) -> str:
        clean = re.sub(r"[^\w\d]+", "_", text.lower()).strip("_")
        return clean
