from src.rag.chunker import LegalHierarchicalChunker
from src.rag.csv_para_qdrant import limpar_segmentos


def rotulos(texto):
    return [c.artigo for c in LegalHierarchicalChunker().chunk_document(texto, "Doc")]


def test_citacao_em_inicio_de_linha_nao_vira_artigo():
    texto = "Art. 1º Regra geral\nnos termos do\nart. 8º da Lei Complementar nº 87\nArt. 2º Outra."
    assert rotulos(texto) == ["Art. 1º", "Art. 2º"]


def test_citacao_com_maiuscula_seguida_de_da_nao_vira_artigo():
    texto = "Art. 1º Regra.\nArt. 150 da Constituição Federal veda.\nArt. 2º Outra."
    assert rotulos(texto) == ["Art. 1º", "Art. 2º"]


def test_numero_nao_e_cortado_para_escapar_da_citacao():
    assert rotulos("Art. 1º Regra.\nArt. 130 da Lei citada.") == ["Art. 1º"]


def test_documento_so_com_citacao_usa_divisao_estruturada():
    chunks = LegalHierarchicalChunker().chunk_document("Conforme\nart. 8º da LC 87.", "Doc")
    assert chunks[0].artigo.startswith("Seção")


def test_corpo_preserva_numero_do_artigo():
    chunk = LegalHierarchicalChunker().chunk_document("Art. 8° Integra a base.", "Doc")[0]
    assert chunk.artigo == "Art. 8°"
    assert "Art. 8° Integra a base." in chunk.raw_text


def test_titulo_markdown_de_artigo_nao_duplica_no_corpo():
    chunk = LegalHierarchicalChunker().chunk_document("## Art. 13\n\nA base é.", "Doc")[0]
    assert chunk.artigo == "Art. 13"
    assert chunk.raw_text == "A base é."


def test_segmento_repetido_identico_sai_e_cabecalho_some():
    texto = (
        "## Segmento 1 — versão 1\n\nTexto A.\n\n"
        "## Segmento 2 — versão 1\n\nTexto B.\n\n"
        "## Segmento 1 — versão 1\n\nTexto A.\n"
    )
    limpo = limpar_segmentos(texto)
    assert limpo.count("Texto A.") == 1
    assert limpo.count("Texto B.") == 1
    assert "Segmento" not in limpo


def test_versoes_diferentes_ficam_marcadas_e_nada_e_inferido():
    texto = "## Segmento 1 — versão 1\n\nAntigo.\n\n## Segmento 1 — versão 2\n\nNovo.\n"
    limpo = limpar_segmentos(texto)
    assert "Antigo." in limpo and "Novo." in limpo
    assert "[Versão 1 deste trecho]" in limpo and "[Versão 2 deste trecho]" in limpo


def test_mesmo_segmento_com_corpo_diferente_nao_e_perdido():
    texto = "## Segmento 1 — versão 1\n\nA.\n\n## Segmento 1 — versão 1\n\nB.\n"
    limpo = limpar_segmentos(texto)
    assert "A." in limpo and "B." in limpo


def test_texto_antes_do_primeiro_segmento_e_sem_segmento_ficam_iguais():
    assert limpar_segmentos("Sem segmentos.\n") == "Sem segmentos.\n"
    assert limpar_segmentos("Início.\n\n## Segmento 1 — versão 1\n\nA.\n").startswith("Início.")
