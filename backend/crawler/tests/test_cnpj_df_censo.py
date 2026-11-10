import json
from backend.crawler.cnpj_df_censo import select_establishments, select_companies, select_options
from backend.crawler.tests.test_cnpj_df import archive, est


def test_multilot_join_filters_and_absence(tmp_path):
    e=tmp_path/'e.zip'; c=tmp_path/'c.zip'; s=tmp_path/'s.zip'
    archive(e,[est('00000001'),est('00000001'),est('00000002','SP'),est('00000003'),est('00000004',status='08')])
    roots,coverage=select_establishments(e)
    assert set(roots)=={'00000001','00000003'} and coverage['linhas']==5
    archive(c,[['00000001','Empresa 12345678901','','','','01',''],['00000003','Grande','','','','05','']])
    companies,count=select_companies(c,set(roots))
    assert list(companies)==['00000001'] and '[CPF omitido]' in companies['00000001']['razao_social']
    archive(s,[['00000001','N','','','S','','']])
    options,count=select_options(s,set(roots))
    assert options['00000001']['opcao_simples']=='N' and '00000003' not in options


def test_all_lots_publish_and_resume(tmp_path,monkeypatch):
    import backend.crawler.cnpj_df_censo as module
    from backend.crawler.catalogo import audit_snapshot,Hasher
    monkeypatch.setattr(module,'DATA',tmp_path)
    raw=tmp_path/'cnpj-ampliado'/'2026-10'/'raw';raw.mkdir(parents=True)
    for i in range(10):
        root=f'{i:08d}'
        archive(raw/f'Estabelecimentos{i}.zip',[est(root)])
        archive(raw/f'Empresas{i}.zip',[[root,'Empresa','','','','01','']])
    archive(raw/'Simples.zip',[['00000000','N','','','S','','']])
    out=tmp_path/'output';first=module.collect(out)
    assert first['registros']==10 and first['sem_registro_simples']==9
    assert len(first['cobertura_lotes'])==21
    assert module.collect(out)['coletado_em']==first['coletado_em']
    mp=next(out.rglob('metadados.json'))
    assert audit_snapshot(json.loads(mp.read_bytes()),mp,tmp_path,Hasher())['problemas']==[]
    derived=mp.parent/'registros.json';derived.write_bytes(b'alterado')
    import pytest
    with pytest.raises(ValueError,match='Derivado divergente'):module.collect(out)
