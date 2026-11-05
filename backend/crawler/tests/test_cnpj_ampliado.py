import csv
import io
import zipfile
import pytest
from backend.crawler.cnpj_ampliado import sample, FILES

def archive(path, rows):
    text=io.StringIO();writer=csv.writer(text,delimiter=';');writer.writerows(rows)
    with zipfile.ZipFile(path,'w') as z:z.writestr('dados.csv',text.getvalue().encode('latin-1'))

def test_join_active_small_and_missing_options(tmp_path):
    def est(root,status='02'):
        row=['']*30;row[0]=root;row[1]='0001';row[2]='99';row[5]=status;row[11]='1234567';row[19]='SP';return row
    archive(tmp_path/FILES[0],[est('00000000','08'),est('00000001'),est('00000001'),est('00000002'),est('00000003')])
    archive(tmp_path/FILES[1],[['00000001','Empresa A','','','','01',''],['00000002','Grande','','','','05',''],['00000003','Empresa C','','','','03','']])
    archive(tmp_path/FILES[2],[['00000001','N','','','S','20200101','']])
    result=sample(tmp_path,2,3)
    assert [r['cnpj'] for r in result]==['00000001000199','00000003000199']
    assert result[0]['opcao_simples']=='N' and result[0]['opcao_mei']=='S'
    assert result[1]['opcao_simples'] is None and not result[1]['registro_simples_encontrado']
    assert result[0]['linhas_origem']['estabelecimentos']==2

def test_reject_wrong_layout(tmp_path):
    archive(tmp_path/FILES[0],[['incompleto']])
    with pytest.raises(ValueError,match='30 campos'):sample(tmp_path,1,1)

def test_reject_limits(tmp_path):
    with pytest.raises(ValueError,match='Limites'):sample(tmp_path,2,1)
