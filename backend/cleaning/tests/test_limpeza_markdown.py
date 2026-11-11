from backend.cleaning.limpeza_markdown import limpar_markdown

CABECALHO = "Manual de Orientação do Leiaute 9 da ECD"


def test_tira_ruido_e_preserva_estrutura():
    paginas = "\n".join(f"{CABECALHO}\nPágina {i}\nTexto da página {i}." for i in range(6))
    md = (
        "## CAPÍTULO I\n**Art. 1º** Veja a [Lei 123](https://planalto.gov.br/l123.htm)"
        " e https://www.gov.br/x.\n"
        "~~Art. 2º Revogado.~~\n> Marcadores da fonte: tachado\nTexto   velho.\n"
        "|  |  |\n|---|---|\n| Faixa | 4% |\nDOCUMENTO VALIDADO\nAssinado digitalmente por X\n"
        "![logo](a.png)\n\n\n\n" + paginas
    )
    r = limpar_markdown(md)
    assert "Art. 1º Veja a Lei 123 e ." in r
    assert "http" not in r and "logo" not in r and "**" not in r
    assert "~~Art. 2º Revogado.~~" in r and "> Marcadores da fonte: tachado" in r
    assert "## CAPÍTULO I" in r and "| Faixa | 4% |" in r and "|  |  |" not in r
    assert CABECALHO not in r and "Página" not in r and "DOCUMENTO" not in r
    assert "Assinado" not in r and "Texto da página 5." in r
    assert "Texto velho." in r and "\n\n\n" not in r
