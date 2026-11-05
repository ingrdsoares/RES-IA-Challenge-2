from backend.crawler.normas_id import NormaId, identidade_titulo


def test_grafias_da_mesma_lei_geram_uma_chave():
    grafias = ['Lei 9.718/98', 'Lei nº 9718, de 27 de novembro de 1998', 'LEI N.º 9.718/1998', 'Lei nº 9718, de 1998']
    assert {identidade_titulo(g, 'federal').chave for g in grafias} == {'federal:lei:-:9718:1998'}


def test_abreviacoes_de_titulo():
    assert identidade_titulo('lc214', 'federal').numero == 214
    assert identidade_titulo('lc214', 'federal').tipo == 'lc'
    assert identidade_titulo('Port. 27/2022', 'federal') == NormaId('portaria', 27, 2022, 'federal', None)
    assert identidade_titulo('Decreto DF nº 25.508/2005').chave == 'df:decreto:-:25508:2005'
    assert identidade_titulo('Resol. 140/2018', 'federal').tipo == 'resol_cgsn'


def test_mesmo_numero_em_jurisdicoes_diferentes_nao_colide():
    assert identidade_titulo('Lei nº 1.254/1996', 'df').chave != identidade_titulo('Lei nº 1.254/1996', 'federal').chave


def test_titulo_sem_norma_nao_identifica():
    assert identidade_titulo('Anexo recuperado — 38212-anexo-23069') is None
    assert identidade_titulo('Solução de Consulta Cosit nº 100, de 28 de setembro de 2020') is None


def test_tipos_e_orgao():
    assert identidade_titulo('Lei Complementar nº 123/2006', 'federal').tipo == 'lc'
    assert identidade_titulo('Decreto-Lei 406/68', 'federal').tipo == 'dl'
    assert identidade_titulo('Instrução Normativa RFB nº 1.700/2017', 'federal').chave == 'federal:in:rfb:1700:2017'
    assert identidade_titulo('Convênio ICMS 142/18').chave == 'confaz:convenio_icms:-:142:2018'


def test_ato_conjunto():
    n = identidade_titulo('Portaria Conjunta RFB/PGFN nº 1/2020', 'federal')
    assert (n.tipo, n.numero, n.ano, n.orgao) == ('portaria', 1, 2020, 'rfb/pgfn')
    assert identidade_titulo('Portaria Conjunta nº 1/2020', 'federal').orgao is None


def test_titulo_que_apenas_menciona_norma_nao_identifica():
    assert identidade_titulo('Regulamenta a Lei nº 9.430/96', 'federal') is None


def test_mencao_df_vence_parametro():
    assert identidade_titulo('Decreto DF nº 25.508/2005', 'federal').jurisdicao == 'df'
