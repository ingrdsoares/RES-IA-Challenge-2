from backend.crawler.obrigacoes import discover_month, discover_days


def test_month_discovery_keeps_real_case_and_official_host():
    raw=b'<div id="content-core"><a href="https://evil.test/2026/Novembro">Novembro</a><a href="2026/Novembro">Novembro</a></div>'
    assert discover_month(raw,'https://www.gov.br/agenda/2026','2026-11')=='https://www.gov.br/agenda/2026/Novembro'


def test_daily_discovery_excludes_other_years_files_and_external_hosts():
    url='https://www.gov.br/agenda/2026/Novembro'
    raw=('''<div id="content-core"><a href="'''+url+'''/dia-23-11-2026">23</a>
    <a href="'''+url+'''/diario">Diario</a><a href="https://www.gov.br/agenda/2024/outubro/declaracoes">Antigo</a>
    <a href="'''+url+'''/anexo.xlsx">XLSX</a><a href="https://evil.test/dia-23-11-2026">Falso</a></div>''').encode()
    result=discover_days(raw,url,'2026-11')
    assert set(result)=={url+'/dia-23-11-2026',url+'/diario'}


def test_collection_reports_individual_failure_and_keeps_service_and_references(tmp_path,monkeypatch):
    import httpx
    import backend.crawler.obrigacoes as module
    monkeypatch.setattr(module,'SERVICES',{'pgdas':{'title':'PGDAS','url':'https://example.test/service','identity':['PGDAS-D']}})
    annual=module.BASE+'/2026'
    monthly=annual+'/Novembro'
    pages={
        annual:f'<h1>2026</h1><div id="content-core"><a href="{monthly}">Novembro</a></div>',
        monthly:f'<h1>Agenda Tributaria</h1><div id="content-core">Novembro de 2026<a href="{monthly}/dia-23-11-2026">23</a><a href="{monthly}/dia-30-11-2026">30</a><a href="{monthly}/diario">Diario</a></div>',
        monthly+'/dia-23-11-2026':'<h1>Dia 23/11/2026</h1><div id="content-core"><table><tr><td>PGDAS-D Simples Nacional</td><td>Outubro/2026</td></tr></table></div>',
        monthly+'/diario':'<h1>Diário</h1><div id="content-core">Tributo de ocorrência diária.</div>',
        'https://example.test/service':'<h1>PGDAS-D</h1><div id="content-core">Texto do servico</div>'}
    def respond(request):
        html=pages.get(str(request.url))
        return httpx.Response(200,content=html.encode()) if html else httpx.Response(503)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report=module.collect('2026-11',tmp_path,client)
    assert report['total']==6
    assert sum(i['status']=='erro' for i in report['fontes'])==1
    assert report['fontes'][-1]['status']=='extraido'
    import json
    refs=json.loads((tmp_path/'2026-11/referencias.json').read_text(encoding='utf-8'))
    assert len(refs)==1
    assert refs[0]['data_pagina']=='2026-11-23'
    assert refs[0]['aplicabilidade']=='nao_avaliada'
