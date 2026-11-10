from backend.cleaning.limpeza_html import limpar_html, processar_arquivo

HTML = """<html><head><title>x</title><script>menu()</script></head><body>
<p>Art. 1º A contribuição
incide sobre <strike>a receita bruta <a href="velha.htm">(Redação dada)</a></strike> o faturamento.</p>
<p><strike>Art. 2º Revogado.</strike></p>
<p>Veja a <a href="/leis/l1.htm">Lei 1</a> e <a href="#art3">art. 3</a>.<br>Fim&nbsp;&amp; tudo</p>
<table><tr><th>Faixa</th><th>Alíquota</th></tr><tr><td>1</td><td>4%</td></tr></table>
</body></html>"""


def test_separa_strike_do_texto_vigente():
    r = limpar_html(HTML)
    assert "receita bruta" not in r.limpo and "Revogado" not in r.limpo
    assert "Art. 1º A contribuição incide sobre o faturamento." in r.limpo
    assert r.trechos_removidos == 2
    assert "a receita bruta [(Redação dada)](velha.htm)" in r.removido
    assert "Art. 2º Revogado." in r.removido


def test_sem_tags_html_e_links_em_markdown():
    r = limpar_html(HTML, base_url="https://x.gov.br/a/b.htm")
    assert "<" not in r.limpo and "<" not in r.removido
    assert "menu()" not in r.limpo
    assert "[Lei 1](https://x.gov.br/leis/l1.htm)" in r.limpo
    assert "[art. 3](#art3)" in r.limpo
    assert "Fim & tudo" in r.limpo
    assert "Faixa | Alíquota" in r.limpo and "1 | 4%" in r.limpo


def test_strike_aninhado_conta_uma_vez_e_tags_configuraveis():
    r = limpar_html("<p>a <strike>b <strike>c</strike></strike> d <del>e</del></p>")
    assert r.trechos_removidos == 1 and r.removido.strip() == "b c"
    r = limpar_html("<p>a <del>e</del></p>", strike_tags=("strike", "del"))
    assert r.limpo.strip() == "a" and r.removido.strip() == "e"


def test_decodifica_cp1252_e_grava_arquivos(tmp_path):
    src = tmp_path / "lei.html"
    src.write_bytes("<p>Redação <strike>velha</strike></p>".encode("cp1252"))
    limpo, removido, _ = processar_arquivo(src, tmp_path / "out")
    assert limpo.name == "lei.limpo.md" and removido.name == "lei.removido.md"
    assert limpo.read_text(encoding="utf-8").strip() == "Redação"
    assert removido.read_text(encoding="utf-8").strip() == "velha"


def test_sem_strike_gera_removido_vazio():
    r = limpar_html("<p>texto</p>")
    assert r.removido == "" and r.trechos_removidos == 0
