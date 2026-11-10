import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from backend.crawler import retencoes_defesa_setores as mod

def row(i):
    return {'idAto':i,'tipoAto':{'idTipoAto':72,'siglaTipoAto':'SC'}}

def test_cap_and_theme_membership():
    payload={'atos':[row(1),row(2)],'quantidadeTotal':2,'quantidadePaginas':1}
    with TemporaryDirectory() as folder, patch.object(mod,'QUERIES',{'a':'x','b':'y'}), patch.object(mod.rfb,'cached',return_value=json.dumps(payload)):
        found,reports,errors=mod.discover(None,Path(folder),1,1,0)
    assert not errors
    assert list(found)==[1]
    assert found[1]['temas']==['a','b']
    assert reports['b']['selecionados']==1
    assert not reports['b']['completa']

def test_repeated_page_is_failure():
    payload={'atos':[row(1)],'quantidadeTotal':2,'quantidadePaginas':2}
    with TemporaryDirectory() as folder, patch.object(mod,'QUERIES',{'a':'x'}), patch.object(mod.rfb,'cached',return_value=json.dumps(payload)):
        found,reports,errors=mod.discover(None,Path(folder),2,10,0)
    assert len(errors)==1
    assert 'repetida' in errors[0]['erro']
    assert not reports['a']['completa']

def test_invalid_type_rejected():
    payload={'atos':[{'idAto':1}],'quantidadeTotal':1,'quantidadePaginas':1}
    with TemporaryDirectory() as folder, patch.object(mod,'QUERIES',{'a':'x'}), patch.object(mod.rfb,'cached',return_value=json.dumps(payload)):
        found,reports,errors=mod.discover(None,Path(folder),1,10,0)
    assert not found
    assert errors
