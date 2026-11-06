import hashlib
import json
from pathlib import Path
import httpx
import pytest
from backend.crawler import ibge_indicadores as ibge, sebrae

def sample():
    fields=['NC','NN','MC','MN','V','D1C','D1N','D2C','D2N','D3C','D3N']
    rows=[dict(zip(fields,['1','Brasil','1','Milhões de Reais','..','1','Brasil',var,'Variável',year,year])) for var in ['9808','9812'] for year in ['2021','2022','2023']]
    return [dict(zip(fields,fields)),*rows]

def test_sidra_preserves_bytes_codes_units_and_missing_markers(tmp_path):
    raw=json.dumps(sample(),ensure_ascii=False).encode()
    path=ibge.ingest('pib',raw,tmp_path)
    assert (path.parent/'original.json').read_bytes()==raw
    meta=json.loads((path.parent/'metadados.json').read_text(encoding='utf-8'))
    assert meta['registros']==6 and meta['sha256']==hashlib.sha256(raw).hexdigest()
    assert meta['periodos']==['2021','2022','2023']
    assert '..' in path.read_text(encoding='utf-8')

@pytest.mark.parametrize('change',['duplicate','territory','period','variable','incomplete','empty'])
def test_sidra_rejects_wrong_or_incomplete_slice(tmp_path,change):
    data=sample()
    if change=='duplicate':data[-1]=data[1]
    elif change=='territory':data[1]['D1C']='35'
    elif change=='period':data[1]['D3C']='2025'
    elif change=='variable':data[1]['D2C']='99'
    elif change=='incomplete':data.pop()
    else:data=[]
    with pytest.raises(ValueError):ibge.ingest('pib',json.dumps(data).encode(),tmp_path)
    assert not list(tmp_path.iterdir())

def test_sidra_failure_still_writes_manifest(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(503))) as client:r=ibge.collect(['pib'],tmp_path,client)
    assert r['indicadores'][0]['status']=='erro'
    assert (tmp_path/'manifesto.json').exists()

def test_sebrae_rejects_redirected_html_not_pdf(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,text='<html>portal</html>'))) as client:r=sebrae.collect(['sobrevivencia-2020'],tmp_path,client)
    assert r['estudos'][0]['status']=='erro'
    assert not list(tmp_path.rglob('original.pdf'))

def test_sebrae_uses_own_source_metadata(tmp_path,monkeypatch):
    raw=(Path(__file__).parent/'fixtures/cgsn140-anexo-i.pdf').read_bytes()
    monkeypatch.setitem(sebrae.SOURCES,'test',{'title':'Estudo de teste','url':'https://datasebrae.com.br/test.pdf','identity':['anexo i'],'kind':'estudo','publicador':'Sebrae / DataSebrae','camada':'B','catalog_url':'https://datasebrae.com.br/'})
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=raw))) as client:r=sebrae.collect(['test'],tmp_path,client)
    meta=r['estudos'][0]
    assert meta['publicador']=='Sebrae / DataSebrae' and meta['status']=='extraido'
    assert meta['sha256']==hashlib.sha256(raw).hexdigest()
    assert meta['markdown'] in (tmp_path/'indice.md').read_text(encoding='utf-8')
