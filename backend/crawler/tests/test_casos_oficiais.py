from backend.crawler.casos_oficiais import excerpts


def test_literal_spans_and_page_reference():
    text='# Manual\n## Página 3\nExemplo 1\nReceita R$ 1.000,00 e cálculo.\nOutra linha.\n'
    result=excerpts(text)
    assert len(result)==1 and result[0]['pagina']=='Página 3'
    r=result[0]
    assert r['texto']=='\n'.join(text.splitlines()[r['linha_inicio']-1:r['linha_fim']])
    assert excerpts('Índice: exemplos de apuração')==[]


def test_duplicate_source_markdown_is_one_candidate_set(tmp_path):
    import json
    from backend.crawler.casos_oficiais import collect
    for name in ('a','b'):
        folder=tmp_path/'manuais'/name;folder.mkdir(parents=True)
        (folder/'original.html').write_bytes(b'official')
        (folder/'documento.md').write_text('## Página 1\nExemplo 1\nReceita R$ 1.000,00',encoding='utf8')
        (folder/'metadados.json').write_text(json.dumps({'source_url':'https://example.gov.br'}))
    report=collect(tmp_path)
    assert report['documentos_fonte']==1 and report['candidatos']==1
