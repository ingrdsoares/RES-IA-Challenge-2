from backend.crawler.historico_competencias import discover_months


def test_months_are_bounded_to_year_and_official_origin():
    raw=b'<div id="content-core"><a href="https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2020/janeiro">Janeiro</a><a href="https://evil.test/2020/fevereiro">Fevereiro</a><a href="https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2021/marco">Outro ano</a></div>'
    result=discover_months(raw,'https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2020',2020)
    assert len(result)==1 and result[0][0]=='2020-01'


def test_numeric_legacy_and_boundary():
    base='https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2023'
    raw=b'<div id="content-core"><a href="2023/01">Janeiro</a><a href="2023/fevereiro-2023">Fevereiro</a><a href="2023/agenda-tributaria-marco-2023">Marco</a><a href="20230/marco">Marco</a><a href="https://evil.test/2023/abril">Abril</a></div>'
    assert [p for p,u in discover_months(raw,base,2023)]==['2023-01','2023-02','2023-03']


def test_existing_snapshot_hash_and_date(tmp_path):
    import json
    import pytest
    from backend.crawler.historico_competencias import ingest_snapshot
    info=dict(url='https://www.gov.br/test',title='Agenda 2023',identity=['2023'])
    raw=b'<h1>Agenda 2023</h1><div id="content-core">Agenda 2023</div>'
    path=ingest_snapshot('test',info,raw,tmp_path)
    meta=path.with_name('metadados.json');first=json.loads(meta.read_bytes())
    assert ingest_snapshot('test',info,raw,tmp_path)==path
    assert json.loads(meta.read_bytes())['coletado_em']==first['coletado_em']
    path.write_text('alterado')
    with pytest.raises(ValueError,match='divergente'):ingest_snapshot('test',info,raw,tmp_path)
