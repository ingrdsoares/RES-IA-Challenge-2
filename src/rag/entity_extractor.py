"""
Extrator de Entidades Fiscais e Classificador Heurístico de Intenção Tributária.
Sócio Digital — RES-IA Challenge 2 (Frente de Ciência de Dados - Jhessica).

Responsável por:
1. Extrair entidades fiscais estruturadas (CNPJ, CNAE, Anexos, Valores Monetários,
   Percentuais, Regimes, Obrigações, Certidões e Dispositivos Legais).
2. Inferir o contexto financeiro de valores (RBT12, faturamento mensal, folha 12m, débitos).
3. Classificar a intenção primária do usuário (Fator R, MEI, Simples, Regularização).
4. Gerar parâmetros prontos para o motor determinístico (FiscalCalculator) e
   tags de filtragem para o banco vetorial (LegalVectorStore).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TaxEntity:
    tipo: str  # cnae, cnpj, regime, anexo, valor_monetario, percentual, obrigacao, certidao, lei
    valor: Any
    texto_original: str
    inicio: int
    fim: int
    confianca: float = 1.0
    metadados: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FiscalExtractionResult:
    texto_original: str
    intencao_primaria: str  # calculo_simples, fator_r, enquadramento_mei, desenquadramento_mei, etc.
    confianca_intencao: float
    cnaes: List[Dict[str, Any]] = field(default_factory=list)
    cnpjs: List[str] = field(default_factory=list)
    regimes: List[str] = field(default_factory=list)
    portes: List[str] = field(default_factory=list)
    anexos: List[str] = field(default_factory=list)
    valores_monetarios: List[Dict[str, Any]] = field(default_factory=list)
    percentuais: List[Dict[str, Any]] = field(default_factory=list)
    obrigacoes: List[str] = field(default_factory=list)
    certidoes: List[str] = field(default_factory=list)
    dispositivos_legais: List[str] = field(default_factory=list)
    tags_rag: List[str] = field(default_factory=list)
    tag_foco: Optional[str] = None
    query_expandida: str = ""
    parametros_calculo: Dict[str, Any] = field(default_factory=dict)
    todas_entidades: List[TaxEntity] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "texto_original": self.texto_original,
            "intencao_primaria": self.intencao_primaria,
            "confianca_intencao": self.confianca_intencao,
            "cnaes": self.cnaes,
            "cnpjs": self.cnpjs,
            "regimes": self.regimes,
            "portes": self.portes,
            "anexos": self.anexos,
            "valores_monetarios": self.valores_monetarios,
            "percentuais": self.percentuais,
            "obrigacoes": self.obrigacoes,
            "certidoes": self.certidoes,
            "dispositivos_legais": self.dispositivos_legais,
            "tags_rag": self.tags_rag,
            "tag_foco": self.tag_foco,
            "query_expandida": self.query_expandida,
            "parametros_calculo": self.parametros_calculo,
        }


class TaxEntityExtractor:
    """
    Extrator de entidades fiscais de alta performance e determinístico para o Sócio Digital.
    Dispensa dependências externas pesadas e executa em milissegundos.
    """

    # 1. Padrões de Códigos Fiscais
    CNAE_FORMATADO_REGEX = re.compile(r"\b(\d{4}-\d/\d{2})\b")
    CNAE_DIGITOS_REGEX = re.compile(r"(?:cnae\s*[:=]?\s*|\bcódigo\s+)(\d{7})\b", re.IGNORECASE)
    CNPJ_FORMATADO_REGEX = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")
    CNPJ_DIGITOS_REGEX = re.compile(r"(?:cnpj\s*[:=]?\s*)(\d{14})\b", re.IGNORECASE)

    # 2. Padrões de Anexos
    ANEXO_REGEX = re.compile(r"\banexo\s+([ivx]+|[1-5])\b", re.IGNORECASE)

    # 3. Padrões Monetários Brasileiros (ex: R$ 81.000,00 | R$ 81 mil | 360 mil | 4,8 milhões)
    VALOR_MOEDA_REGEX = re.compile(
        r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d+)?)\s*(milh[oõ]es|milh[aã]o|mil|k)?\b",
        re.IGNORECASE,
    )

    # 4. Padrões de Percentual (ex: 28% | 20,5 % | 0,28)
    PERCENTUAL_REGEX = re.compile(r"\b(\d+(?:[,\.]\d+)?)\s*%", re.IGNORECASE)

    # 5. Dicionários Semânticos de Regimes e Portes
    REGIMES_MAP = {
        "mei": ["mei", "microempreendedor individual", "simei"],
        "simples_nacional": ["simples nacional", "super simples", "simples"],
        "lucro_presumido": ["lucro presumido"],
        "lucro_real": ["lucro real"],
    }

    PORTES_MAP = {
        "mei": ["microempreendedor", "microempreendedor individual"],
        "me": ["microempresa", " micro empresa ", " me "],
        "epp": ["empresa de pequeno porte", " epp "],
    }

    # 6. Dicionários de Obrigações, Certidões e Documentos Fiscais
    OBRIGACOES_MAP = {
        "dasn_simei": ["dasn-simei", "dasn simei", "dasn", "declaração anual do mei", "declaracao anual"],
        "das": ["guia das", "das avulso", "das mei", "das-mei", "documento de arrecadação"],
        "defis": ["defis", "declaração de informações socioeconômicas"],
        "pgdas_d": ["pgdas-d", "pgdas"],
        "parcelamento": ["parcelamento", "60 parcelas", "parcela mínima", "reparcelamento"],
    }

    CERTIDOES_MAP = {
        "cnd": ["cnd", "certidão negativa de débitos", "certidão negativa"],
        "cpen": ["cpen", "certidão positiva com efeitos de negativa", "positiva com efeito de negativa"],
        "divida_ativa": ["dívida ativa", "divida ativa", "pgfn", "procuradoria-geral"],
        "termo_exclusao": ["termo de exclusão", "notificação de exclusão", "aviso de exclusão", "dte-sn"],
    }

    LEIS_MAP = {
        "lc_123_2006": ["lc 123", "lc 123/2006", "lei complementar 123", "estatuto da microempresa"],
        "res_cgsn_140": ["resolução cgsn 140", "cgsn 140", "resolucao 140"],
        "art_18_a": ["art. 18-a", "artigo 18-a", "art 18a"],
        "art_18": ["art. 18", "artigo 18"],
        "art_3": ["art. 3º", "art. 3", "artigo 3"],
        "art_106": ["art. 106", "artigo 106"],
        "art_131": ["art. 131", "artigo 131"],
    }

    def __init__(self, fiscal_repository: Optional[Any] = None):
        """
        Opcionalmente recebe um FiscalRepository para enriquecer CNAEs com descrição,
        anexo padrão e elegibilidade ao MEI/Fator R.
        """
        self.fiscal_repo = fiscal_repository

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Remove acentos e converte para minúsculas para correspondência semântica robusta."""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

    def extract(self, text: str) -> FiscalExtractionResult:
        """
        Extrai todas as entidades fiscais, identifica a intenção e monta os parâmetros de cálculo.
        """
        if not text:
            return FiscalExtractionResult(
                texto_original="",
                intencao_primaria="consulta_geral",
                confianca_intencao=0.0,
            )

        entities: List[TaxEntity] = []

        # 1. CNPJs
        cnpjs = self._extract_cnpjs(text, entities)

        # 2. CNAEs
        cnaes = self._extract_cnaes(text, entities)

        # 3. Anexos
        anexos = self._extract_anexos(text, entities)

        # 4. Regimes e Portes
        regimes, portes = self._extract_regimes_e_portes(text, entities)

        # 5. Obrigações e Certidões
        obrigacoes = self._extract_mapped_terms(text, self.OBRIGACOES_MAP, "obrigacao", entities)
        certidoes = self._extract_mapped_terms(text, self.CERTIDOES_MAP, "certidao", entities)
        leis = self._extract_mapped_terms(text, self.LEIS_MAP, "lei", entities)

        # 6. Valores Monetários e Percentuais
        valores_monetarios = self._extract_currency_values(text, entities)
        percentuais = self._extract_percentages(text, entities)

        # 7. Classificação de Intenção e Parâmetros de Cálculo
        intencao, confianca = self._classify_intent(
            text=text,
            cnaes=cnaes,
            anexos=anexos,
            regimes=regimes,
            obrigacoes=obrigacoes,
            certidoes=certidoes,
            valores=valores_monetarios,
            percentuais=percentuais,
        )

        parametros_calculo = self._build_calculation_parameters(
            cnaes=cnaes,
            anexos=anexos,
            valores=valores_monetarios,
            percentuais=percentuais,
            intencao=intencao,
        )

        tags_rag = self._derive_rag_tags(
            intencao=intencao,
            regimes=regimes,
            anexos=anexos,
            obrigacoes=obrigacoes,
            certidoes=certidoes,
            parametros=parametros_calculo,
        )

        tag_foco = self._determine_focus_tag(intencao, tags_rag, parametros_calculo)
        query_expandida = self._build_expanded_query(
            text=text,
            cnaes=cnaes,
            intencao=intencao,
            tag_foco=tag_foco,
            parametros=parametros_calculo,
        )

        return FiscalExtractionResult(
            texto_original=text,
            intencao_primaria=intencao,
            confianca_intencao=confianca,
            cnaes=cnaes,
            cnpjs=cnpjs,
            regimes=regimes,
            portes=portes,
            anexos=anexos,
            valores_monetarios=valores_monetarios,
            percentuais=percentuais,
            obrigacoes=obrigacoes,
            certidoes=certidoes,
            dispositivos_legais=leis,
            tags_rag=tags_rag,
            tag_foco=tag_foco,
            query_expandida=query_expandida,
            parametros_calculo=parametros_calculo,
            todas_entidades=entities,
        )

    def _determine_focus_tag(
        self,
        intencao: str,
        tags_rag: List[str],
        parametros: Dict[str, Any],
    ) -> Optional[str]:
        """Identifica a tag mais específica e prioritária para rotear o RAG com precisão cirúrgica."""
        if intencao == "fator_r" or parametros.get("sujeito_fator_r"):
            return "fator_r"
        if intencao == "desenquadramento_mei":
            return "desenquadramento"
        if intencao == "obrigacoes_acessorias":
            return "obrigacoes_acessorias"
        if intencao == "regularizacao_pendencias":
            return "certidoes" if "certidoes" in tags_rag else "parcelamento"
        if "mei" in tags_rag:
            return "mei"
        if "simples_nacional" in tags_rag:
            return "simples_nacional"
        return tags_rag[0] if tags_rag else None

    def _build_expanded_query(
        self,
        text: str,
        cnaes: List[Dict[str, Any]],
        intencao: str,
        tag_foco: Optional[str],
        parametros: Dict[str, Any],
    ) -> str:
        """Expande a consulta léxica com sinônimos legais e descrições estruturadas (Query Expansion)."""
        expansions = [text]

        # Injeta descrição de CNAE
        for c in cnaes:
            desc = c.get("descricao")
            if desc and desc.lower() not in text.lower():
                expansions.append(desc)

        # Injeta termos conceituais legais conforme o foco
        if tag_foco == "fator_r" or parametros.get("sujeito_fator_r"):
            expansions.append("Fator R folha de salários 28% Anexo III Anexo V Art. 18")
        elif tag_foco == "desenquadramento":
            expansions.append("desenquadramento MEI excesso de receita 20% Art. 18-A")
        elif tag_foco == "obrigacoes_acessorias":
            expansions.append("DASN-SIMEI declaração anual 31 de maio prazo Art. 106")
        elif tag_foco == "certidoes":
            expansions.append("Certidão Negativa CND CPEN regularidade fiscal Art. 1º")

        return " ".join(expansions)

    # =========================================================================
    # Métodos de Extração Especializados
    # =========================================================================

    def _extract_cnpjs(self, text: str, entities: List[TaxEntity]) -> List[str]:
        found = []
        for match in self.CNPJ_FORMATADO_REGEX.finditer(text):
            cnpj = match.group(1)
            found.append(cnpj)
            entities.append(TaxEntity(
                tipo="cnpj",
                valor=cnpj,
                texto_original=match.group(0),
                inicio=match.start(),
                fim=match.end(),
                confianca=1.0,
            ))
        for match in self.CNPJ_DIGITOS_REGEX.finditer(text):
            cnpj_raw = match.group(1)
            cnpj_fmt = f"{cnpj_raw[:2]}.{cnpj_raw[2:5]}.{cnpj_raw[5:8]}/{cnpj_raw[8:12]}-{cnpj_raw[12:]}"
            if cnpj_fmt not in found:
                found.append(cnpj_fmt)
                entities.append(TaxEntity(
                    tipo="cnpj",
                    valor=cnpj_fmt,
                    texto_original=match.group(0),
                    inicio=match.start(),
                    fim=match.end(),
                    confianca=0.95,
                ))
        return found

    def _extract_cnaes(self, text: str, entities: List[TaxEntity]) -> List[Dict[str, Any]]:
        cnaes = []
        found_codes = set()

        # CNAEs formatados (ex: 6201-5/01)
        for match in self.CNAE_FORMATADO_REGEX.finditer(text):
            codigo = match.group(1)
            found_codes.add(codigo)
            item = {"codigo": codigo, "codigo_limpo": "".join(filter(str.isdigit, codigo))}
            self._enrich_cnae_item(item)
            cnaes.append(item)
            entities.append(TaxEntity(
                tipo="cnae",
                valor=item,
                texto_original=match.group(0),
                inicio=match.start(),
                fim=match.end(),
                confianca=1.0,
                metadados=item,
            ))

        # CNAEs de 7 dígitos precedidos de identificador
        for match in self.CNAE_DIGITOS_REGEX.finditer(text):
            digs = match.group(1)
            codigo_fmt = f"{digs[:4]}-{digs[4]}/{digs[5:]}"
            if codigo_fmt not in found_codes:
                found_codes.add(codigo_fmt)
                item = {"codigo": codigo_fmt, "codigo_limpo": digs}
                self._enrich_cnae_item(item)
                cnaes.append(item)
                entities.append(TaxEntity(
                    tipo="cnae",
                    valor=item,
                    texto_original=match.group(0),
                    inicio=match.start(),
                    fim=match.end(),
                    confianca=0.9,
                    metadados=item,
                ))

        # Se houver repositório, tenta busca semântica por descrição de atividade se nenhum CNAE foi achado
        if not cnaes and self.fiscal_repo is not None:
            norm_text = self._normalize_text(text)
            keywords = ["software", "programador", "salao de beleza", "cabeleireiro", "eletricista", "comercio", "restaurante"]
            for kw in keywords:
                if kw in norm_text:
                    results = self.fiscal_repo.search_cnaes(kw, limit=1)
                    if results:
                        best = results[0]
                        item = {
                            "codigo": best.codigo,
                            "codigo_limpo": best.codigo_limpo,
                            "descricao": best.descricao,
                            "anexo_padrao": best.anexo_padrao,
                            "sujeito_fator_r": best.sujeito_fator_r,
                            "permitido_mei": best.permitido_mei,
                            "inferido_por_termo": kw,
                        }
                        cnaes.append(item)
                        break

        return cnaes

    def _enrich_cnae_item(self, item: Dict[str, Any]):
        """Adiciona metadados fiscais se o repositório estiver disponível."""
        if self.fiscal_repo:
            cnae_model = self.fiscal_repo.get_cnae_by_codigo(item["codigo"])
            if cnae_model:
                item["descricao"] = cnae_model.descricao
                item["setor"] = cnae_model.setor
                item["anexo_padrao"] = cnae_model.anexo_padrao
                item["sujeito_fator_r"] = cnae_model.sujeito_fator_r
                item["permitido_mei"] = cnae_model.permitido_mei
                item["permitido_simples"] = cnae_model.permitido_simples
                item["ocupacao_mei"] = cnae_model.ocupacao_mei

    def _extract_anexos(self, text: str, entities: List[TaxEntity]) -> List[str]:
        anexos = []
        map_romanos = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
        for match in self.ANEXO_REGEX.finditer(text):
            raw_val = match.group(1).upper()
            anexo_normalizado = map_romanos.get(raw_val, raw_val)
            if anexo_normalizado in ["I", "II", "III", "IV", "V"] and anexo_normalizado not in anexos:
                anexos.append(anexo_normalizado)
                entities.append(TaxEntity(
                    tipo="anexo",
                    valor=anexo_normalizado,
                    texto_original=match.group(0),
                    inicio=match.start(),
                    fim=match.end(),
                    confianca=1.0,
                ))
        return anexos

    def _extract_regimes_e_portes(self, text: str, entities: List[TaxEntity]) -> tuple[List[str], List[str]]:
        norm_text = f" {self._normalize_text(text)} "
        regimes = []
        portes = []

        for reg_id, synonyms in self.REGIMES_MAP.items():
            for syn in synonyms:
                pattern = rf"\b{re.escape(syn)}\b"
                if re.search(pattern, norm_text):
                    if reg_id not in regimes:
                        regimes.append(reg_id)
                    entities.append(TaxEntity(
                        tipo="regime",
                        valor=reg_id,
                        texto_original=syn,
                        inicio=0,
                        fim=0,
                        confianca=0.95,
                    ))
                    break

        for porte_id, synonyms in self.PORTES_MAP.items():
            for syn in synonyms:
                pattern = rf"\b{re.escape(syn.strip())}\b"
                if re.search(pattern, norm_text):
                    if porte_id not in portes:
                        portes.append(porte_id)
                    break

        return regimes, portes

    def _extract_mapped_terms(
        self,
        text: str,
        mapping: Dict[str, List[str]],
        entity_type: str,
        entities: List[TaxEntity],
    ) -> List[str]:
        norm_text = f" {self._normalize_text(text)} "
        found = []
        for term_id, synonyms in mapping.items():
            for syn in synonyms:
                pattern = rf"\b{re.escape(syn)}\b"
                match = re.search(pattern, norm_text)
                if match:
                    if term_id not in found:
                        found.append(term_id)
                    entities.append(TaxEntity(
                        tipo=entity_type,
                        valor=term_id,
                        texto_original=syn,
                        inicio=match.start(),
                        fim=match.end(),
                        confianca=0.9,
                    ))
                    break
        return found

    def _extract_currency_values(self, text: str, entities: List[TaxEntity]) -> List[Dict[str, Any]]:
        """Extrai valores monetários inferindo se são faturamento anual, mensal, folha ou débito."""
        valores = []

        # Posições já ocupadas por entidades como CNPJ e CNAE
        occupied_spans = [(e.inicio, e.fim) for e in entities if e.tipo in ("cnpj", "cnae")]

        # Encontra menções numéricas
        for match in self.VALOR_MOEDA_REGEX.finditer(text):
            m_start, m_end = match.start(), match.end()

            # Evita sobreposição com CNPJs e CNAEs já extraídos
            if any(start <= m_start < end or start < m_end <= end for start, end in occupied_spans):
                continue

            # Se for seguido imediatamente por '/' ou '-', é fragmento de código (ex: 6201- ou /0001)
            if m_end < len(text) and text[m_end] in ("/", "-"):
                continue
            if m_start > 0 and text[m_start - 1] in ("/", "-"):
                continue

            num_str = match.group(1).replace(".", "").replace(",", ".")
            multiplicador = match.group(2)

            try:
                val = float(num_str)
            except ValueError:
                continue

            # Multiplicadores textuais
            if multiplicador:
                mult_lower = multiplicador.lower()
                if "milh" in mult_lower:
                    val *= 1_000_000.0
                elif mult_lower in ["mil", "k"]:
                    val *= 1_000.0

            full_span = match.group(0).strip()
            tem_cifrao = "R$" in text[max(0, m_start - 4):m_end]

            # Ignora números se seguidos por unidades não monetárias (ex: "60 parcelas", "30 dias", "12 meses")
            next_text = text[m_end:min(len(text), m_end + 15)].lower()
            if not tem_cifrao and not multiplicador:
                if re.match(r"\s*(?:parcelas?|dias?|meses|mês|anos?|artigos?|art\.?)\b", next_text):
                    continue
                # Se não tem cifrão nem multiplicador e for pequeno, descarta
                if val < 50.0:
                    continue

            # Contexto textual direcionado (à esquerda define a natureza do valor; à direita define o período)
            left_context = self._normalize_text(text[max(0, m_start - 55):m_start])
            right_context = self._normalize_text(text[m_end:min(len(text), m_end + 30)])

            # Classificação semântica
            categoria_inferida = "geral"

            # 1. Folha de pagamento / Salários / Pró-labore (verificado prioritariamente no contexto à esquerda)
            if any(k in left_context for k in ["folha", "salario", "salarios", "pro-labore", "pro labore", "equipe", "funcionarios"]):
                categoria_inferida = "folha_pagamento"
            # 2. Débitos e dívidas
            elif any(k in left_context for k in ["divida", "debito", "debitos", "pendencia", "atraso", "devendo", "multa"]):
                categoria_inferida = "debito"
            # 3. Faturamento / Receita com indicativo anual ou mensal
            elif any(k in left_context for k in ["fatur", "receita", "ganh", "venda", "teto", "limite", "rbt12", "acumulad"]):
                if any(k in left_context or k in right_context for k in ["ano", "anual", "acumulad", "12 mes", "rbt12"]):
                    categoria_inferida = "faturamento_anual"
                elif any(k in left_context or k in right_context for k in ["mes", "mensal", "por mes"]):
                    categoria_inferida = "faturamento_mensal"
                else:
                    categoria_inferida = "faturamento_anual" if val >= 50_000.0 else "faturamento_mensal"
            # 4. Contexto temporal direto
            elif any(k in left_context or right_context.startswith(f" {k}") or right_context.startswith(k) for k in ["no ano", "ao ano", "por ano", "anual", "acumulado"]):
                categoria_inferida = "faturamento_anual"
            elif any(k in left_context or right_context.startswith(f" {k}") or right_context.startswith(k) for k in ["no mes", "ao mes", "por mes", "mensal"]):
                categoria_inferida = "faturamento_mensal"

            item = {
                "valor": round(val, 2),
                "texto_original": full_span,
                "categoria": categoria_inferida,
                "posicao": (m_start, m_end),
            }
            valores.append(item)
            entities.append(TaxEntity(
                tipo="valor_monetario",
                valor=item["valor"],
                texto_original=full_span,
                inicio=m_start,
                fim=m_end,
                confianca=0.9,
                metadados={"categoria": categoria_inferida},
            ))

        return valores

    def _extract_percentages(self, text: str, entities: List[TaxEntity]) -> List[Dict[str, Any]]:
        percentuais = []
        for match in self.PERCENTUAL_REGEX.finditer(text):
            num_str = match.group(1).replace(",", ".")
            try:
                val = float(num_str)
            except ValueError:
                continue

            window_start = max(0, match.start() - 40)
            window_end = min(len(text), match.end() + 40)
            context = self._normalize_text(text[window_start:window_end])

            tipo_perc = "geral"
            if "fator" in context or abs(val - 28.0) < 0.01:
                tipo_perc = "fator_r"
            elif "excesso" in context or "ultrapass" in context or abs(val - 20.0) < 0.01:
                tipo_perc = "tolerancia_mei"
            elif "aliquota" in context:
                tipo_perc = "aliquota"

            item = {
                "percentual": val,
                "fracao": round(val / 100.0, 4),
                "tipo": tipo_perc,
                "texto_original": match.group(0),
            }
            percentuais.append(item)
            entities.append(TaxEntity(
                tipo="percentual",
                valor=val,
                texto_original=match.group(0),
                inicio=match.start(),
                fim=match.end(),
                confianca=0.95,
                metadados={"tipo": tipo_perc},
            ))

        return percentuais

    # =========================================================================
    # Classificação Heurística de Intenção e Parâmetros
    # =========================================================================

    def _classify_intent(
        self,
        text: str,
        cnaes: List[Dict[str, Any]],
        anexos: List[str],
        regimes: List[str],
        obrigacoes: List[str],
        certidoes: List[str],
        valores: List[Dict[str, Any]],
        percentuais: List[Dict[str, Any]],
    ) -> tuple[str, float]:
        norm = self._normalize_text(text)

        # 1. Regra Fator R
        if "fator r" in norm or (anexos and "V" in anexos and "III" in anexos) or any(p["tipo"] == "fator_r" for p in percentuais):
            return "fator_r", 0.95

        # 2. Desenquadramento MEI
        if "mei" in regimes and any(k in norm for k in ["desenquadr", "estourou", "passou do limite", "ultrapassou", "excesso"]):
            return "desenquadramento_mei", 0.95

        # 3. Regularização, Débitos e Certidões
        if certidoes or any(k in norm for k in ["regulariz", "divida", "pendencia", "cnd", "cpen", "parcelar", "exclusao"]):
            return "regularizacao_pendencias", 0.90

        # 4. Obrigações Acessórias e Prazos (DASN, DAS, Prazos)
        if obrigacoes or any(k in norm for k in ["prazo", "vencimento", "declaracao anual", "quando pagar", "dia 20", "31 de maio"]):
            return "obrigacoes_acessorias", 0.90

        # 5. Cálculo / Simulação do Simples Nacional
        if (cnaes or anexos or valores) and any(k in norm for k in ["quanto vou pagar", "aliquota", "calcular", "simular", "imposto", "das"]):
            return "calculo_simples", 0.85

        # 6. Enquadramento de MEI Geral
        if "mei" in regimes or any(k in norm for k in ["posso ser mei", "limite mei", "81 mil", "abrir mei"]):
            return "enquadramento_mei", 0.85

        return "consulta_geral", 0.60

    def _build_calculation_parameters(
        self,
        cnaes: List[Dict[str, Any]],
        anexos: List[str],
        valores: List[Dict[str, Any]],
        percentuais: List[Dict[str, Any]],
        intencao: str,
    ) -> Dict[str, Any]:
        """
        Estrutura parâmetros matemáticos prontos para invocar o FiscalCalculator.
        """
        params: Dict[str, Any] = {}

        # CNAE
        if cnaes:
            params["cnae_codigo"] = cnaes[0]["codigo"]
            params["anexo_padrao"] = cnaes[0].get("anexo_padrao")
            params["sujeito_fator_r"] = cnaes[0].get("sujeito_fator_r", False)
        elif anexos:
            params["anexo_padrao"] = anexos[0]

        # Separação de valores
        anual_vals = [v for v in valores if v["categoria"] == "faturamento_anual"]
        for v in valores:
            cat = v["categoria"]
            val = v["valor"]
            if cat == "faturamento_anual":
                # Se for o valor canônico de 81.000 no MEI e houver outro faturamento, registra como teto
                if abs(val - 81000.0) < 0.01 and len(anual_vals) > 1:
                    params["limite_referencia_mei"] = val
                else:
                    params["rbt12"] = val
            elif cat == "faturamento_mensal":
                params["faturamento_mes"] = val
            elif cat == "folha_pagamento":
                params["folha_12m"] = val
            elif cat == "debito":
                params["valor_debito"] = val

        # Se houver apenas o valor de 81.000 como faturamento anual
        if "rbt12" not in params and "limite_referencia_mei" in params:
            params["rbt12"] = params["limite_referencia_mei"]

        # Heurística se não houver categoria explícita:
        # Se temos apenas um valor elevado (> 80.000), costuma ser faturamento anual
        valores_gerais = [v["valor"] for v in valores if v["categoria"] == "geral"]
        if "rbt12" not in params and valores_gerais:
            max_val = max(valores_gerais)
            if max_val >= 50_000.0 or len(valores_gerais) == 1:
                params["rbt12"] = max_val
                valores_gerais.remove(max_val)

        if "faturamento_mes" not in params and valores_gerais:
            params["faturamento_mes"] = min(valores_gerais)

        # Fator R explícito
        for p in percentuais:
            if p["tipo"] == "fator_r":
                params["fator_r_declarado"] = p["fracao"]

        # Se tivermos folha e RBT12, pré-calcula o Fator R
        if "folha_12m" in params and "rbt12" in params and params["rbt12"] > 0:
            params["fator_r_calculado"] = round(params["folha_12m"] / params["rbt12"], 4)

        return params

    def _derive_rag_tags(
        self,
        intencao: str,
        regimes: List[str],
        anexos: List[str],
        obrigacoes: List[str],
        certidoes: List[str],
        parametros: Dict[str, Any],
    ) -> List[str]:
        """Gera as tags compatíveis com o LegalVectorStore."""
        tags = set()

        if "mei" in regimes or "mei" in intencao:
            tags.add("mei")
        if "simples_nacional" in regimes or intencao == "calculo_simples":
            tags.add("simples_nacional")
            tags.add("tributos_das")
        if intencao == "fator_r" or parametros.get("sujeito_fator_r"):
            tags.add("fator_r")
        if intencao == "desenquadramento_mei":
            tags.add("mei")
            tags.add("desenquadramento")
            tags.add("limite_faturamento")
        if intencao == "obrigacoes_acessorias" or obrigacoes:
            tags.add("obrigacoes_acessorias")
        if intencao == "regularizacao_pendencias" or certidoes:
            tags.add("certidoes")
            tags.add("parcelamento")

        return sorted(list(tags))
