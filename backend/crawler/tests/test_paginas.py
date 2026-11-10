import json
import pytest
from backend.crawler.paginas import parse_page, ingest


@pytest.fixture
def page():
    return '''<html><meta charset="utf-8"><h1>Dia 23/11/2026</h1><nav>Menu externo</nav>
    <div id="content-core"><script>bad()</script><p>Agenda oficial <a href="base">Fundamento</a></p>
    <table><tr><td rowspan="2">DAS</td><td>Simples Nacional</td></tr><tr><td colspan="2">Outubro/2026</td></tr></table></div></html>'''.encode()


@pytest.fixture
def info():
    return {'title':'Agenda diária','url':'https://www.gov.br/agenda/2026/Novembro/dia-23-11-2026',
            'identity':['23/11/2026'],'camada':'A','kind':'agenda_diaria','periodo':'2026-11'}


def test_preserves_literal_cells_and_excludes_navigation(page,info):
    data=parse_page(page,info)
    assert len(data['tabelas'])==1
    rows=data['tabelas'][0]['linhas']
    assert rows[0]['celulas'][0]['rowspan']==2
    assert rows[1]['celulas'][0]['colspan']==2
    assert 'Menu externo' not in data['markdown'] and 'bad()' not in data['markdown']
    assert 'https://www.gov.br/agenda/2026/Novembro/base' in data['markdown']
    assert 'DAS' in data['markdown']


def test_service_parser_prefers_service_content():
    raw=b'<h1>Declarar DEFIS</h1><div id="content-core"><div class="header">Avaliacao</div><div class="servico-content">DEFIS: texto oficial</div></div>'
    data=parse_page(raw,{'url':'https://www.gov.br/service','identity':['defis']})
    assert 'texto oficial' in data['markdown'] and 'Avaliacao' not in data['markdown']


def test_rejects_error_page_and_wrong_identity(page,info):
    with pytest.raises(ValueError):parse_page(b'<html>Acesso negado</html>',info)
    with pytest.raises(ValueError):parse_page(page,{**info,'identity':['outro documento']})


def test_snapshot_preserves_raw_and_tables_and_reuses_version(page,info,tmp_path):
    path=ingest('agenda-dia23',info,page,tmp_path)
    assert (path.parent/'original.html').read_bytes()==page
    tables=json.loads((path.parent/'tabelas.json').read_text(encoding='utf-8'))
    assert tables[0]['linhas'][0]['celulas'][0]['texto']=='DAS'
    before=path.read_bytes()
    assert ingest('agenda-dia23',info,page,tmp_path)==path
    assert path.read_bytes()==before


def test_write_failure_keeps_previous_page(page,info,tmp_path,monkeypatch):
    from pathlib import Path
    first=ingest('agenda-dia23',info,page,tmp_path)
    before=first.read_bytes()
    def fail(*args,**kwargs):raise OSError('disco cheio')
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(OSError):ingest('agenda-dia23',info,page+b'\n',tmp_path)
    assert first.read_bytes()==before
    assert not list(tmp_path.rglob('.coleta-*'))

def test_rejects_content_removed_as_navigation():
    raw=b'<h1>Parcelamento MEI</h1><div id="content"><nav>Parcelamento MEI</nav></div>'
    with pytest.raises(ValueError):parse_page(raw,{'url':'https://www.gov.br/test','content_selector':'#content','identity':['MEI']})

@pytest.mark.parametrize('field,value',[('sha256','WRONG'),('source_url','https://wrong.test'),('source_id','outro')])
def test_reuse_rejects_divergent_metadata(page,info,tmp_path,field,value):
    path=ingest('agenda-dia23',info,page,tmp_path)
    mp=path.parent/'metadados.json';meta=json.loads(mp.read_text(encoding='utf-8'));meta[field]=value;mp.write_text(json.dumps(meta),encoding='utf-8')
    with pytest.raises(ValueError,match='incompleta ou divergente'):ingest('agenda-dia23',info,page,tmp_path)

def test_reuse_rejects_missing_metadata(page,info,tmp_path):
    path=ingest('agenda-dia23',info,page,tmp_path);(path.parent/'metadados.json').unlink()
    with pytest.raises(ValueError,match='incompleta ou divergente'):ingest('agenda-dia23',info,page,tmp_path)
