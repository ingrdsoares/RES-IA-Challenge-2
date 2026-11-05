from backend.crawler.citacoes import extrair_citacoes
from backend.crawler.normas_id import identidade_titulo


def test_contexto_federal_gera_hipotese_federal():
    c = extrair_citacoes('nos termos da Lei nº 10.833, de 29 de dezembro de 2003', 'federal')[0]
    assert c.norma.chave == 'federal:lei:-:10833:2003' and c.candidatas_jurisdicao == ('federal',)


def test_texto_df_sem_mencao_tem_duas_candidatas():
    c = extrair_citacoes('conforme a Lei nº 4.567/2011', 'df')[0]
    assert set(c.candidatas_jurisdicao) == {'df', 'federal'}


def test_mencao_expressa_ao_df_vence_contexto():
    c = extrair_citacoes('Lei Distrital nº 4.567/2011', 'federal')[0]
    assert c.candidatas_jurisdicao == ('df',)


def test_orgao_e_tipos_novos():
    r = extrair_citacoes('Portaria RFB nº 12/2020 e Ato Declaratório Executivo Cosit nº 3/2021', 'federal')
    assert [x.norma.orgao for x in r] == ['rfb', 'cosit'] and [x.norma.tipo for x in r] == ['portaria', 'ade']


def test_nao_confunde_tipos_compostos():
    assert extrair_citacoes('Decreto-Lei nº 1.598/1977', 'federal')[0].norma.tipo == 'dl'
    assert extrair_citacoes('Lei Complementar nº 123/2006', 'federal')[0].norma.tipo == 'lc'


def test_numero_pequeno_sem_ano_e_ruido():
    assert extrair_citacoes('a lei 12 trata', 'federal') == []


def test_uma_citacao_por_norma():
    r = extrair_citacoes('Lei 9.718/1998 ... novamente a Lei nº 9.718, de 1998', 'federal')
    assert len(r) == 1


def test_ano_com_digito_extra_nao_vira_ano():
    assert identidade_titulo('Lei 9718, de 19981').ano is None


def _chave(texto):
    r = extrair_citacoes(texto, 'federal')
    return [x.norma.chave for x in r]


def test_lc_com_marcador_sem_ano():
    assert _chave('Lei Complementar nº 123') == ['federal:lc:-:123:?']


def test_lc_sigla_sem_ano():
    assert _chave('conforme LC 116') == ['federal:lc:-:116:?']


def test_in_rfb_sem_ano():
    assert _chave('Instrução Normativa RFB nº 971') == ['federal:in:rfb:971:?']


def test_ec_sem_ano():
    assert _chave('a EC 132') == ['federal:ec:-:132:?']


def test_ajuste_sinief_sem_ano():
    assert _chave('Ajuste SINIEF 7') == ['confaz:ajuste_sinief:-:7:?']


def test_decreto_com_marcador_sem_ano():
    assert _chave('Decreto nº 435') == ['federal:decreto:-:435:?']


def test_decreto_sem_marcador_sem_ano_e_ruido():
    assert _chave('Decreto 435') == []
