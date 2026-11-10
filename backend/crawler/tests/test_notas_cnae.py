import json
from unittest.mock import patch
import pytest
from backend.crawler.notas_cnae import parse_notes, coverage, INFO
from backend.crawler.manuais import ingest

def test_index_excludes_other_parts_and_inline_references():
    notes=parse_notes('## Página 43\n0111-3/01 Estrutura\n## Página 101\n0111-3/01 Cultivo de arroz\n- referência (0111-3/02)\n## Página 528\nU 9900-8/00 Organismos\n## Página 531\n0111-3/99 Histórico\n')
    assert [n['codigo'] for n in notes]==['0111301','9900800']
    assert notes[0]['pagina_pdf_inicio']==101

def test_duplicate_and_empty_index_fail():
    with pytest.raises(ValueError,match='repetido'):
        parse_notes('## Página 101\n0111-3/01 Arroz\n0111-3/01 Arroz\n')
    with pytest.raises(ValueError,match='Nenhum'):
        parse_notes('## Página 40\n0111-3/01 Arroz\n')

def test_coverage_exposes_exact_differences():
    with patch('backend.crawler.notas_cnae.parse_cnaes',return_value=[{'codigo':'0111301'},{'codigo':'0111399'}]):
        result=coverage([{'codigo':'0111301'},{'codigo':'0111302'}],b'api')
    assert result['comuns']==1
    assert result['somente_api']==['0111399']
    assert result['somente_pdf']==['0111302']
    assert result['cobertura_completa_api'] is False

def test_wrong_publication_rejected(tmp_path):
    with patch('backend.crawler.manuais.extract_pdf',return_value=[{'pagina':1,'texto':'Anexo tributário Simples Nacional','tabelas':[]}]):
        with pytest.raises(ValueError,match='identidade'):
            ingest('cnae',b'%PDF-wrong',tmp_path,source_info=INFO)
    assert not list(tmp_path.rglob('original.pdf'))


def test_multiline_title_stops_before_explanatory_note():
    notes = parse_notes('## Página 132\nA 0210-1/99 Produção de produtos em florestas\nplantadas\nEsta subclasse compreende:\n- produção\n## Página 146\n0729-4/04 Extração de minerais não\nferrosos não especificados anteriormente\nEsta subclasse compreende:\n- extração\n')
    assert notes[0]['titulo'] == 'Produção de produtos em florestas plantadas'
    assert notes[1]['titulo'].endswith('ferrosos não especificados anteriormente')
    assert 'compreende' not in notes[1]['titulo']
