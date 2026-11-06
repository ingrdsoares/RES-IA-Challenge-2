import hashlib
import json
from datetime import datetime, timezone

import pytest

from backend.crawler.legislacao import SOURCES, ingest, parse_lc123, parse_cgsn140


@pytest.fixture
def law_html():
    return '''<html><meta charset="utf-8"><body><script>menu()</script>
    <p>LEI COMPLEMENTAR Nº 123, DE 14 DE DEZEMBRO DE 2006</p>
    <p>Art. 1º Texto <strike>anterior</strike> atualizado.</p>
    <p>§ 1º Condição aplicável.</p><p>Art. 2º Segundo artigo.</p>
    <p>ANEXO I</p><table><tr><th>Faixa</th><th>Alíquota</th></tr>
    <tr><td>1</td><td>4%</td></tr></table></body></html>'''.encode()


@pytest.fixture
def resolution():
    return {'idAto': 92278, 'epigrafeCompleta': 'Resolução CGSN nº 140, de 22 de maio de 2018',
            'visao': 'multivigente', 'integro': True, 'dataPublicacao': '2018-05-24',
            'ementas': [], 'outrosSegmentos': [
                {'idSegmento': 1, 'ordemSegmentoAto': 1, 'textoIntegra': 'Art. 1º Redação anterior.', 'tachado': True},
                {'idSegmento': 2, 'ordemSegmentoAto': 2, 'textoIntegra': 'Art. 1º Redação nova.', 'agendado': True},
                {'idSegmento': 3, 'ordemSegmentoAto': 3, 'textoIntegra': 'Art. 2º Texto.'}]}


def test_html_preserves_articles_strike_and_tables(law_html):
    text = parse_lc123(law_html)
    assert '## Art. 1' in text
    assert '§ 1º Condição aplicável.' in text
    assert '~~anterior~~' in text
    assert '| 1 | 4% |' in text
    assert '## ANEXO I' in text
    assert 'menu()' not in text


@pytest.mark.parametrize('raw', [b'<html>Acesso negado</html>', b'<app-root></app-root>', b'<p>Art. 1 Outra lei</p>'])
def test_rejects_wrong_or_empty_html(raw):
    with pytest.raises(ValueError):
        parse_lc123(raw)


def test_resolution_preserves_segment_status(resolution):
    text = parse_cgsn140(json.dumps(resolution).encode())
    assert 'segmento-1' in text and 'segmento-2' in text
    assert 'TACHADO NA FONTE' in text
    assert 'AGENDADO NA FONTE' in text
    assert 'Redação anterior' in text and 'Redação nova' in text


@pytest.mark.parametrize('field,value', [('idAto', 123), ('visao', 'vigente'), ('integro', False), ('outrosSegmentos', [])])
def test_rejects_wrong_resolution(resolution, field, value):
    resolution[field] = value
    with pytest.raises(ValueError):
        parse_cgsn140(json.dumps(resolution).encode())


def test_snapshot_preserves_raw_and_repeats_without_overwrite(law_html, tmp_path):
    instant = datetime(2026, 11, 3, tzinfo=timezone.utc)
    path = ingest('lc123', law_html, tmp_path, collected_at=instant)
    assert (path.parent / 'original.html').read_bytes() == law_html
    text = path.read_text(encoding='utf-8')
    assert hashlib.sha256(law_html).hexdigest() in text
    assert SOURCES['lc123']['url'] in text
    assert 'vigencia: nao_verificada' in text
    assert ingest('lc123', law_html, tmp_path) == path
    assert path.read_text(encoding='utf-8') == text


def test_invalid_response_never_writes(tmp_path):
    with pytest.raises(ValueError):
        ingest('lc123', b'<p>Acesso negado</p>', tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_disk_failure_keeps_previous_version(law_html, tmp_path, monkeypatch):
    from pathlib import Path
    previous = ingest('lc123', law_html, tmp_path)
    content = previous.read_bytes()
    def fail(*args, **kwargs):
        raise OSError('disco cheio')
    monkeypatch.setattr(Path, 'write_text', fail)
    with pytest.raises(OSError):
        ingest('lc123', law_html.replace(b'Segundo', b'Terceiro'), tmp_path)
    assert previous.read_bytes() == content
    assert len(list((tmp_path / 'lc123').iterdir())) == 1


def test_preserves_multiple_versions_of_same_segment(resolution):
    resolution['outrosSegmentos'][0]['versaoSegmento'] = 1
    resolution['outrosSegmentos'][1]['idSegmento'] = 1
    resolution['outrosSegmentos'][1]['versaoSegmento'] = 2
    text = parse_cgsn140(json.dumps(resolution).encode())
    assert 'segmento-1-v1' in text and 'segmento-1-v2' in text
    assert 'Redação anterior' in text and 'Redação nova' in text


def test_resolution_lists_external_annex_without_claiming_download(resolution):
    resolution['outrosSegmentos'][0]['arquivoBinario'] = {
        'idArquivoBinario': 48430, 'nomeArquivoBinario': 'Anexo I.pdf'}
    text = parse_cgsn140(json.dumps(resolution).encode())
    assert 'Anexo I.pdf' in text
    assert 'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/92278/anexo/48430' in text
    assert 'não foi baixado' in text


def test_lgpd_preserves_lettered_articles_and_amendment_annotations():
    from backend.crawler.legislacao import parse_lgpd
    raw='''<meta charset="utf-8"><p>LEI Nº 13.709, DE 14 DE AGOSTO DE 2018</p>
    <p>Art. 1º Tratamento de dados pessoais.</p>
    <p>Art. 55-A. Autoridade nacional. (Redação dada por alteração posterior)</p>
    <p>Art. 65. <strike>Redação anterior</strike> Texto atualizado.</p>'''.encode()
    text=parse_lgpd(raw)
    assert '## Art. 55-A' in text
    assert 'Redação dada por alteração posterior' in text
    assert '~~Redação anterior~~' in text
    assert 'Tratamento de dados pessoais.' in text


def test_lgpd_rejects_other_law(law_html):
    from backend.crawler.legislacao import parse_lgpd
    with pytest.raises(ValueError):parse_lgpd(law_html)


def test_lgpd_ingest_uses_its_own_parser_and_source(tmp_path):
    from backend.crawler.legislacao import SOURCES,ingest
    raw='<p>LEI Nº 13.709, DE 14 DE AGOSTO DE 2018</p><p>Art. 1º Dados pessoais.</p>'.encode()
    path=ingest('lgpd',raw,tmp_path)
    text=path.read_text(encoding='utf-8')
    assert SOURCES['lgpd']['url'] in text
    assert '## Art. 1º' in text
    assert (path.parent/'original.html').read_bytes()==raw


def test_ec132_selects_normative_content_and_preserves_quoted_changes():
    from backend.crawler.legislacao import parse_ec132
    raw='''<h1>EMENDA CONSTITUCIONAL Nº 132, DE 2023</h1><nav>Menu externo</nav>
    <div class="textoNorma"><p>Art. 1º A Constituição passa a vigorar com alterações:</p>
    <p>"Art. 156-A. Texto constitucional alterado."</p><p>Art. 23. Produção de efeitos futuros.</p></div>'''.encode()
    text=parse_ec132(raw)
    assert 'Menu externo' not in text
    assert '156-A' in text and 'Produção de efeitos futuros' in text
    assert '## Art. 1º' in text


def test_lc214_preserves_tables_and_source_identity():
    from backend.crawler.legislacao import parse_lc214
    raw='''<p>LEI COMPLEMENTAR Nº 214, DE 16 DE JANEIRO DE 2025</p>
    <p>Art. 1º IBS e CBS.</p><p>ANEXO I</p>
    <table><tr><th>Código</th><th>Descrição</th></tr><tr><td>01</td><td>Texto</td></tr></table>'''.encode()
    text=parse_lc214(raw)
    assert '| 01 | Texto |' in text
    assert '## ANEXO I' in text
    with pytest.raises(ValueError):parse_lc214(raw.replace(b'214',b'123'))


def test_ec132_recognizes_articles_separated_only_by_line_breaks():
    from backend.crawler.legislacao import parse_ec132
    raw='''<h1>EMENDA CONSTITUCIONAL Nº 132, DE 2023</h1><div class="textoNorma"><div class="texto">
    Art. 1º Primeira alteração.<br><br>Art. 2º Segunda alteração.<br><br>
    <dir>"Art. 156-A. Texto da Constituição citado."</dir>
    <p>Art. 23. Produção de efeitos.</p></div></div>'''.encode()
    text=parse_ec132(raw)
    assert '## Art. 1º' in text and '## Art. 2º' in text and '## Art. 23' in text
    assert '156-A' in text


def test_ec132_keeps_boundary_after_legacy_indentation_blocks():
    from backend.crawler.legislacao import parse_ec132
    raw='''<h1>EMENDA CONSTITUCIONAL Nº 132, DE 2023</h1><div class="textoNorma"><div class="texto">
    Art. 1º Primeira alteração.<br><dir>"Art. 43. Texto constitucional." (NR)</dir>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Art. 2º Segunda alteração.<br><p>Art. 23. Efeitos.</p></div></div>'''.encode()
    assert '## Art. 2º' in parse_ec132(raw)


def test_ctn_preserves_articles_annotations_and_lettered_numbers():
    from backend.crawler.legislacao import parse_ctn
    raw='''<p>LEI Nº 5.172, DE 25 DE OUTUBRO DE 1966</p><p>Art. 1º Sistema Tributário Nacional.</p>
    <p>Art. 185-A. Dispositivo acrescido. (Incluído por lei complementar)</p>
    <p>Art. 218. <strike>Texto anterior</strike> Disposições finais.</p>'''.encode()
    text=parse_ctn(raw)
    assert '## Art. 185-A' in text
    assert 'Incluído por lei complementar' in text
    assert '~~Texto anterior~~' in text


def test_ctn_rejects_another_law(law_html):
    from backend.crawler.legislacao import parse_ctn
    with pytest.raises(ValueError):parse_ctn(law_html)


def test_ctn_ingest_uses_own_source_and_preserves_original(tmp_path):
    from backend.crawler.legislacao import SOURCES,ingest
    raw='<p>LEI Nº 5.172, DE 25 DE OUTUBRO DE 1966</p><p>Art. 1º Texto.</p>'.encode()
    path=ingest('ctn',raw,tmp_path)
    assert (path.parent/'original.html').read_bytes()==raw
    text=path.read_text(encoding='utf-8')
    assert SOURCES['ctn']['url'] in text and 'texto_atualizado_camara' in text


def test_lc116_preserves_articles_and_service_list_codes():
    from backend.crawler.legislacao import parse_lc116
    raw='''<p>LEI COMPLEMENTAR Nº 116, DE 31 DE JULHO DE 2003</p><p>Art. 1º ISS.</p>
    <p>Lista de serviços anexa à Lei Complementar nº 116, de 31 de julho de 2003.</p>
    <p>1 - Serviços de informática.</p><p>1.01 - Análise e desenvolvimento de sistemas. (Redação conforme fonte)</p>
    <p>40 - Serviços finais.</p><p>40.01 - Obras sob encomenda.</p>'''.encode()
    text=parse_lc116(raw)
    assert '## Art. 1º' in text
    assert '1.01' in text and '40.01' in text
    assert 'Redação conforme fonte' in text


def test_lc116_rejects_missing_service_annex():
    from backend.crawler.legislacao import parse_lc116
    raw='<p>LEI COMPLEMENTAR Nº 116, DE 31 DE JULHO DE 2003</p><p>Art. 1º Texto incompleto.</p>'.encode()
    with pytest.raises(ValueError,match='lista'):parse_lc116(raw)


def test_lc116_rejects_other_law(law_html):
    from backend.crawler.legislacao import parse_lc116
    with pytest.raises(ValueError):parse_lc116(law_html)
