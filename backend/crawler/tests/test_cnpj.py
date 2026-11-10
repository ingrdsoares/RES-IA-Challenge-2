import csv
import io
import json
from pathlib import Path
import zipfile

import pytest

from backend.crawler.cnpj import parse_empresas, parse_auxiliary, ingest_empresas, ingest_auxiliary, latest_competence


def make_zip(rows):
    text=io.StringIO(newline='')
    csv.writer(text,delimiter=';',quoting=csv.QUOTE_ALL,lineterminator='\n').writerows(rows)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:z.writestr('DADOS.CSV',text.getvalue().encode('latin-1'))
    return out.getvalue()


@pytest.fixture
def empresas(tmp_path):
    raw=make_zip([['00000001','Comércio Exemplo','2062','49','1000,00','05',''],
                  ['00AB0002','Micro Comércio','2135','50','100,00','01',''],
                  ['00000003','Pequena Empresa','2062','49','1000,00','03','']])
    path=tmp_path/'Empresas1.zip';path.write_bytes(raw)
    return path


def test_sample_filters_declared_size_and_preserves_alphanumeric_base(empresas):
    rows,scanned=parse_empresas(empresas,limit=1)
    assert len(rows)==1 and scanned==2
    assert rows[0]['cnpj_basico']=='00AB0002'
    assert rows[0]['razao_social']=='Micro Comércio'
    assert rows[0]['porte']=='01'
    assert 'uf' not in rows[0] and 'optante_mei' not in rows[0]


def test_requires_all_seven_columns(tmp_path):
    path=tmp_path/'bad.zip';path.write_bytes(make_zip([['00000001','Faltam colunas']]))
    with pytest.raises(ValueError):parse_empresas(path,limit=100)


def test_invalid_limits_are_rejected(empresas):
    for value in [0,-1,10001]:
        with pytest.raises(ValueError):parse_empresas(empresas,limit=value)


def test_auxiliary_preserves_codes_and_accents():
    rows=parse_auxiliary(make_zip([['0001','São Paulo'],['0002','A|B']]))
    assert rows[0]=={'codigo':'0001','descricao':'São Paulo'}


def test_duplicate_auxiliary_code_is_rejected():
    with pytest.raises(ValueError):parse_auxiliary(make_zip([['01','A'],['01','B']]))


def test_sample_snapshot_is_traceable_and_limit_is_part_of_identity(empresas,tmp_path):
    output=tmp_path/'out'
    first=ingest_empresas(empresas,output,competence='2026-10',limit=1)
    text=first.read_text(encoding='utf-8')
    assert '00AB0002' in text and 'cnpj_basico' in text
    meta=json.loads((first.parent/'metadados.json').read_text(encoding='utf-8'))
    assert meta['competencia']=='2026-10' and meta['linhas_lidas']==2 and meta['registros']==1
    before=first.read_bytes()
    assert ingest_empresas(empresas,output,competence='2026-10',limit=1)==first
    assert first.read_bytes()==before
    assert ingest_empresas(empresas,output,competence='2026-10',limit=2)!=first


def test_auxiliary_writes_original_and_markdown(tmp_path):
    raw=make_zip([['0001','São Paulo']])
    path=ingest_auxiliary('municipios',raw,tmp_path,competence='2026-10')
    assert (path.parent/'original.zip').read_bytes()==raw
    assert '| 0001 | São Paulo |' in path.read_text(encoding='utf-8')


def test_latest_competence_uses_only_valid_month_directories():
    raw=b'<d:multistatus xmlns:d="DAV:"><d:response><d:href>/public.php/webdav/2026-09/</d:href></d:response><d:response><d:href>/public.php/webdav/2026-10/</d:href></d:response><d:response><d:href>/public.php/webdav/2026-99/</d:href></d:response></d:multistatus>'
    assert latest_competence(raw)=='2026-10'


def test_download_cleans_file_when_stream_exceeds_limit(tmp_path):
    import httpx
    from backend.crawler.cnpj import download
    target=tmp_path/'partial.zip'
    transport=httpx.MockTransport(lambda r:httpx.Response(200,stream=httpx.ByteStream(b'1234567890')))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError,match='limite'):
            download(client,'https://example.test/data.zip',target,max_bytes=5)
    assert not target.exists()


def test_invalid_csv_never_publishes_snapshot(tmp_path):
    raw=make_zip([['01','A','EXTRA']])
    with pytest.raises(ValueError):ingest_auxiliary('municipios',raw,tmp_path,competence='2026-10')
    assert list(tmp_path.iterdir())==[]


def test_write_failure_keeps_previous_sample(empresas,tmp_path,monkeypatch):
    output=tmp_path/'out'
    previous=ingest_empresas(empresas,output,competence='2026-10',limit=1)
    before=previous.read_bytes()
    def fail(*args,**kwargs):raise OSError('disco cheio')
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(OSError):ingest_empresas(empresas,output,competence='2026-10',limit=2)
    assert previous.read_bytes()==before
    assert not list(output.rglob('.coleta-*'))


def test_invalid_month_listing_fails_with_clear_validation_error():
    with pytest.raises(ValueError):latest_competence(b'<html>erro')
