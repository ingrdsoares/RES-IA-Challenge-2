import csv
import io
import json
import zipfile
import pytest
from backend.crawler.cnpj_df import sample, collect


def archive(path, values):
    text = io.StringIO()
    csv.writer(text, delimiter=';').writerows(values)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('dados.csv', text.getvalue().encode('latin-1'))


def est(root, uf='DF', status='02'):
    r = ['']*30
    r[0], r[1], r[2], r[5], r[19] = root, '0001', '99', status, uf
    return r


def fixture(tmp_path):
    e, c, s = [tmp_path/name for name in ('e.zip','c.zip','s.zip')]
    archive(e, [est('00000000','SP'), est('00000001',status='08'), est('00000002'), est('00000002'), est('00000003'), est('00000004')])
    archive(c, [[root, 'Empresa 12345678901', '', '', '', porte, ''] for root, porte in [('00000002','01'),('00000003','05'),('00000004','03')]])
    archive(s, [['00000002','N','','','S','','']])
    return e, c, s


def test_filters_dedup_join_and_missing(tmp_path):
    e,c,s = fixture(tmp_path)
    records, coverage = sample(e,[c],s,2,3)
    assert [r['cnpj_basico'] for r in records] == ['00000002','00000004']
    assert all(r['uf']=='DF' and r['situacao']=='02' and r['porte'] in ('01','03') for r in records)
    assert records[0]['opcao_simples']=='N'
    assert records[1]['opcao_simples'] is None and records[1]['opcao_mei'] is None
    assert not records[1]['registro_simples_encontrado']
    assert '12345678901' not in records[0]['razao_social']
    assert coverage['sem_registro_simples']==1
    assert records[0]['linhas_origem']['estabelecimentos']==3


def test_limits_and_missing_join(tmp_path):
    e,c,s=fixture(tmp_path)
    with pytest.raises(ValueError,match='Limites'):
        sample(e,[c],s,3,2)
    with pytest.raises(ValueError,match='Apenas'):
        sample(e,[c],s,3,3)


def test_bad_zip_and_layout(tmp_path):
    e,c,s=fixture(tmp_path)
    archive(e,[['bad']])
    with pytest.raises(ValueError,match='30 campos'):
        sample(e,[c],s,1,1)


def test_volume_1000(tmp_path):
    e,c,s=[tmp_path/n for n in ('e.zip','c.zip','s.zip')]
    roots=[f'{i:08d}' for i in range(1000)]
    archive(e,[est(r) for r in roots])
    archive(c,[[r,'Empresa','','','','01',''] for r in roots])
    archive(s,[[r,'S','','','N','',''] for r in roots])
    records, coverage=sample(e,[c],s,1000,1000)
    assert len(records)==len({r['cnpj_basico'] for r in records})==1000
    assert coverage['linhas_escaneadas']['simples']==1000


def test_snapshot_identity_and_corrupt_cache(tmp_path,monkeypatch):
    import backend.crawler.cnpj_df as module
    raw=tmp_path/'cnpj-ampliado'/'2026-10'/'raw'
    raw.mkdir(parents=True)
    e,c,s=fixture(tmp_path)
    for src,name in zip((e,c,s),('Estabelecimentos1.zip','Empresas2.zip','Simples.zip')):
        (raw/name).write_bytes(src.read_bytes())
    (raw/'Empresas1.zip').write_bytes(c.read_bytes())
    monkeypatch.setattr(module,'DATA',tmp_path)
    out=tmp_path/'output'
    first=collect(out,limit=1,candidates=3)
    assert collect(out,limit=1,candidates=3)==first
    second=collect(out,limit=2,candidates=3)
    assert second!=first
    original_meta=(first/'metadados.json').read_bytes()
    assert collect(out,limit=1,candidates=3)==first
    assert first.name in (out/'indice.md').read_text(encoding='utf-8')
    assert json.loads((out/'2026-10'/'manifesto.json').read_text(encoding='utf-8'))['snapshot']==first.name
    assert (first/'metadados.json').read_bytes()==original_meta
    meta=json.loads((first/'metadados.json').read_text(encoding='utf-8'))
    assert meta['filtros']['uf']=='DF' and len(meta['originais'])==4
    (first/'dados.md').write_text('alterado',encoding='utf-8')
    with pytest.raises(ValueError,match='Cache corrompido'):
        collect(out,limit=1,candidates=3)

def test_corrupt_original_preserved(tmp_path, monkeypatch):
    import backend.crawler.cnpj_df as module
    raw=tmp_path/'cnpj-ampliado'/'2026-10'/'raw'
    raw.mkdir(parents=True)
    bad=raw/'Estabelecimentos1.zip'
    bad.write_bytes(b'corrompido')
    e,c,s=fixture(tmp_path)
    for src,name in ((c,'Empresas2.zip'),(c,'Empresas1.zip'),(s,'Simples.zip')):
        (raw/name).write_bytes(src.read_bytes())
    monkeypatch.setattr(module,'DATA',tmp_path)
    with pytest.raises(zipfile.BadZipFile):
        collect(tmp_path/'output',limit=1,candidates=3)
    assert bad.read_bytes()==b'corrompido'
