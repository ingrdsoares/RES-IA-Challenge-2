import json

from backend.refino.auditoria_extracao import auditar, auditar_ocorrencias, carregar_limites
from backend.refino.pipeline import load_policy

LIMITES = carregar_limites()


def _ocorrencia(folder, root, markdown, original_html=None, original_name='original.html'):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'metadados.json').write_text(json.dumps({'source_id': 'x', 'original': original_name}), encoding='utf8')
    if original_html is not None:
        (folder / original_name).write_bytes(original_html)
    md = folder / 'documento.md'
    md.write_text(markdown, encoding='utf8')
    return {'metadados_ref': (folder / 'metadados.json').relative_to(root).as_posix(),
            'markdown_ref': md.relative_to(root).as_posix(), 'id': folder.name}


def _html(texto, depois_do_body=b''):
    corpo = ('<p>' + texto + '</p>').encode('utf8')
    return b'<html><head><title>t</title></head><body>' + corpo + b'</body>' + depois_do_body + b'</html>'


def test_extracao_curta_e_reportada_sem_excluir(tmp_path):
    original = _html('Art. 1 ' + 'texto integral da norma ' * 400)
    occ = _ocorrencia(tmp_path / 'lei', tmp_path, '# Lei\n\nArt. 1 curto.\n', original)
    resultado = auditar(occ, tmp_path, LIMITES)
    assert 'extracao_curta' in resultado['problemas']
    assert resultado['razao_texto'] < 0.5


def test_extracao_completa_nao_gera_problema(tmp_path):
    texto = 'Art. 1 ' + 'texto integral da norma ' * 40
    occ = _ocorrencia(tmp_path / 'lei', tmp_path, '# Lei\n\n' + texto + '\n', _html(texto))
    resultado = auditar(occ, tmp_path, LIMITES)
    assert resultado['problemas'] == []
    assert resultado['razao_texto'] >= 0.5


def test_body_precoce_e_detectado_pelo_conteudo_depois_do_fechamento(tmp_path):
    texto = 'Art. 1 ' + 'norma ' * 50
    original = _html(texto, depois_do_body=b'<div>' + b'x' * 3000 + b'</div>')
    occ = _ocorrencia(tmp_path / 'lei', tmp_path, '# Lei\n\n' + texto + '\n', original)
    resultado = auditar(occ, tmp_path, LIMITES)
    assert 'body_precoce' in resultado['problemas']
    assert resultado['bytes_apos_body'] > 2000


def test_body_com_pouco_conteudo_depois_nao_gera_problema(tmp_path):
    texto = 'Art. 1 ' + 'norma ' * 50
    original = _html(texto, depois_do_body=b'<script>' + b'x' * 500 + b'</script>')
    occ = _ocorrencia(tmp_path / 'lei', tmp_path, '# Lei\n\n' + texto + '\n', original)
    assert 'body_precoce' not in auditar(occ, tmp_path, LIMITES)['problemas']


def test_sem_original_html_nao_gera_problema_nem_erro(tmp_path):
    occ = _ocorrencia(tmp_path / 'lei', tmp_path, '# Lei\n\nTexto.\n', original_html=None)
    resultado = auditar(occ, tmp_path, LIMITES)
    assert resultado['problemas'] == []
    assert resultado['razao_texto'] is None


def test_auditoria_so_grava_ocorrencias_com_problema_e_nao_altera_entrada(tmp_path):
    texto = 'Art. 1 ' + 'norma ' * 50
    ok = _ocorrencia(tmp_path / 'ok', tmp_path, '# Lei\n\n' + texto + '\n', _html(texto))
    curta = _ocorrencia(tmp_path / 'curta', tmp_path, '# Lei\n\nCurto.\n', _html('x ' * 2000))
    entrada = [dict(ok), dict(curta)]
    linhas = list(auditar_ocorrencias(entrada, tmp_path, LIMITES))
    assert [l['id'] for l in linhas] == ['curta']
    assert entrada == [ok, curta]


def test_limites_vem_de_politica_json():
    politica = load_policy()
    assert politica['auditoria_extracao']['razao_texto_minima'] == 0.5
    assert politica['auditoria_extracao']['bytes_apos_body_precoce'] == 2000
    assert carregar_limites() == politica['auditoria_extracao']
