from backend.crawler.fontes_recuperadas import candidates, ALTERNATIVA

def test_only_timeouts_and_public_alternative_are_retried():
    records=[{'url':'https://acordaos.economia.gov.br/a.pdf','status':'erro'}, {'url':'https://scon.stj.jus.br/SCON/GetPDFINFJ?edicao=0872','status':'erro'}, {'url':'https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?a=1','status':'erro'}, {'url':'https://acordaos.economia.gov.br/ok.pdf','status':'extraido'}]
    result=list(candidates({'documentos':records}))
    assert len(result)==2
    assert result[1]['url']==ALTERNATIVA
    assert result[1]['url_anterior']==records[1]['url']
    assert records[1]['url']!=ALTERNATIVA
