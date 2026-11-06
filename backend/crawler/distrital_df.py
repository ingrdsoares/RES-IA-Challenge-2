"""Fontes oficiais do Distrito Federal: ISS, retenções e NFS-e."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import ssl
import unicodedata
import httpx
from bs4 import BeautifulSoup
import pypdfium2
from backend.crawler.legislacao import _convert

DEFAULT_OUTPUT=Path(__file__).parent/"data"/"distrital-df"
NFSE="https://www.receita.fazenda.df.gov.br/aplicacoes/CartaServicos/servico.cfm?codServico=1202&codSubCategoria=346"
RETENCAO="https://www.receita.fazenda.df.gov.br/aplicacoes/CartaServicos/servico.cfm?codServico=1049&codSubCategoria=271"
SOURCES={
 "decreto25508":dict(title="Decreto DF nº 25.508/2005 — Regulamento do ISS",url="https://www.sinj.df.gov.br/sinj/Norma/46110/exec_dec_25508_2005_rep.html",selector="#div_texto",identity=["decreto no 25 508 de 19 de janeiro de 2005"],kind="legislacao",view="texto_compilado_sinj"),
 "decreto43982":dict(title="Decreto DF nº 43.982/2022 — Sistema de Gestão do ISS",url="https://www.sinj.df.gov.br/sinj/Norma/21388bb5ed9443dc8a7d64b4e3d5c77a/Decreto_43982_05_12_2022.html",selector="#div_texto",identity=["decreto no 43 982 de 05 de dezembro de 2022"],kind="legislacao",view="texto_compilado_sinj"),
 "nfse-informacoes":dict(title="Receita DF — NFS-e: informações e documentação",url=NFSE,selector=".conteudo_servico",identity=["nota fiscal de servicos eletronica","distrito federal"],kind="orientacao",view="pagina_servico"),
 "retencao-informacoes":dict(title="Receita DF — Manual do Substituto/Responsável Tributário do ISS",url=RETENCAO,selector=".conteudo_servico",identity=["manual substituto","substituicao tributaria do iss"],kind="orientacao",view="pagina_servico"),
 "faq-iss":dict(title="Receita DF — Perguntas frequentes do ISS/NFS-e",url="https://iss.fazenda.df.gov.br/online/Default/PerguntasFrequentes.aspx",selector="body",identity=["perguntas frequentes","distrito federal","nfs e"],kind="orientacao",view="perguntas_respostas"),
 "comunicado-nacional":dict(title="Economia DF — Ambiente de produção da NFS-e no padrão nacional",url="https://economia.df.gov.br/w/comunicado-disponibilizacao-do-ambiente-de-producao-da-nfs-e-no-padrao-nacional",selector=".materia",identity=["nfs e","padrao nacional","producao"],kind="orientacao",view="comunicado"),
 "manual-retencao":dict(title="Manual do Substituto/Responsável Tributário do ISS — novembro/2024",url="https://static.fazenda.df.gov.br/arquivos/servico-1049/Manual_ST_ISS_novembro_20241.pdf",format="pdf",identity=["manual","iss","substituto"],kind="manual",view="pdf",catalog_url=RETENCAO),
 "manual-integracao":dict(title="Manual de integração NFS-e — Nota Control v1.01",url="https://www.notacontrol.com.br/download/nfse/Manual_integracao_v101.pdf",format="pdf",identity=["manual","integracao","nfs"],kind="manual_fornecedor",view="pdf",catalog_url=NFSE,publicador="Nota Control — fornecedor; documento vinculado pela Receita DF"),
}

def normalize(text):
    text="".join(c for c in unicodedata.normalize("NFKD",text) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+"," ",text).strip()

def parse_html(source,raw):
    info=SOURCES[source]
    markup=raw.decode("utf-8-sig")
    if info["kind"]=="legislacao":
        # SINJ omite </p> em milhares de blocos; impedir aninhamento artificial.
        markup=re.sub(r"(?i)(<p(?:\s[^>]*|)>)",r"</p>\1",markup)
    soup=BeautifulSoup(markup,"html.parser")
    content=soup.select_one(info["selector"])
    if content is None: raise ValueError("Bloco documental ausente")
    plain=normalize(" ".join(h.get_text(" ",strip=True) for h in content.find_all("h1"))) if info["kind"]=="legislacao" else normalize(content.get_text(" ",strip=True))
    if not all(token in plain for token in info["identity"]): raise ValueError("Identidade documental divergente")
    for node in content.select(".strike"):
        node.name="del"
    articles=0
    if info["kind"]=="legislacao":
        for block in list(content.find_all("p")):
            if block.find_parent("table"): continue
            text=" ".join(block.get_text(" ",strip=True).split())
            match=re.match(r"Art\.\s*\d+(?:[º°o])?(?:-[A-Z]+)?|ANEXO\s+[IVXLCDM]+",text,re.I)
            if match:
                heading=soup.new_tag("h2");heading.string=match.group();block.insert_before(heading);articles+=1
        if not articles: raise ValueError("Norma sem artigos reconhecíveis")
    markdown=_convert(str(content),info["url"])
    return markdown,dict(artigos_anexos=articles,tabelas=len(content.find_all("table")),tachados=len(content.find_all(["s","del","strike"])),caracteres_reposicao_na_fonte=raw.count(b"\xef\xbf\xbd"))

def parse_pdf(source,raw):
    if not raw.startswith(b"%PDF-"): raise ValueError("Resposta não é PDF")
    with pypdfium2.PdfDocument(raw) as pdf:
        pages=[]
        for index in range(len(pdf)):
            page=pdf[index];textpage=page.get_textpage()
            pages.append(textpage.get_text_range());textpage.close();page.close()
    if not all(token in normalize(" ".join(pages[:4])) for token in SOURCES[source]["identity"]): raise ValueError("Identidade do PDF divergente")
    if not any(text.strip() for text in pages): raise ValueError("PDF sem texto; OCR necessário")
    body="\n\n".join(f"## Página {i}\n\n"+text.replace("\r\n","\n") for i,text in enumerate(pages,1))
    return body,dict(paginas=len(pages),paginas_sem_texto=[i for i,text in enumerate(pages,1) if not text.strip()],extrator="pypdfium2",tabelas="nao_reconstruidas",revisao_tabelas="pendente_no_original")

def ingest(source,raw,output=DEFAULT_OUTPUT):
    info=SOURCES[source];extension=info.get("format","html");digest=hashlib.sha256(raw).hexdigest()
    target=Path(output)/source/digest;result=target/"documento.md"
    if target.exists():
        meta=json.loads((target/"metadados.json").read_bytes())
        if (target/f"original.{extension}").read_bytes()!=raw or not result.is_file() or meta["sha256"]!=digest or meta["source_url"]!=info["url"]: raise ValueError("Versão existente incompleta ou divergente")
        return result
    body,stats=parse_pdf(source,raw) if extension=="pdf" else parse_html(source,raw)
    meta=dict(source_id=source,titulo=info["title"],source_url=info["url"],catalog_url=info.get("catalog_url",info["url"]),publicador=info.get("publicador","Governo do Distrito Federal"),jurisdicao="Distrito Federal",tipo=info["kind"],visao=info["view"],camada="A" if info["kind"]=="legislacao" else "B",coletado_em=datetime.now(timezone.utc).isoformat(),sha256=digest,status="extraido",vigencia="nao_verificada",revisao_humana="pendente",**stats)
    if stats.get("paginas_sem_texto"):meta["status"]="ocr_pendente"
    front="\n".join(f"{k}: {json.dumps(v,ensure_ascii=False)}" for k,v in meta.items())
    text=f'---\n{front}\n---\n\n# {info["title"]}\n\n[Original](original.{extension}) · [Metadados](metadados.json)\n\n> Distrito Federal. Vigência não verificada; revisão humana pendente. Texto histórico e tachados preservados; coleta não define qual versão se aplica. Manuais e páginas de serviço são orientação. PDF: tabelas, imagens e telas exigem conferência no original.\n\n{body}\n'
    target.mkdir(parents=True)
    (target/f"original.{extension}").write_bytes(raw)
    result.write_bytes(text.encode("utf-8"))
    (target/"metadados.json").write_bytes(json.dumps(meta,ensure_ascii=False,indent=2).encode("utf-8"))
    return result

def _ssl_context():
    # Windows mantém cadeias governamentais que podem faltar no bundle certifi.
    context=ssl.create_default_context()
    if hasattr(ssl,"enum_certificates"):
        for cert,encoding,trust in ssl.enum_certificates("ROOT"):
            if encoding=="x509_asn" and (trust is True or ssl.Purpose.SERVER_AUTH.oid in trust):
                context.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(cert))
    return context

def collect(output=DEFAULT_OUTPUT,sources=None,client=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);records=[]
    with httpx.Client(timeout=60,follow_redirects=True,verify=_ssl_context()) if client is None else client as session:
        for source in sources or SOURCES:
            try:
                response=session.get(SOURCES[source]["url"]);response.raise_for_status()
                path=ingest(source,response.content,output)
                records.append(dict(json.loads((path.parent/"metadados.json").read_bytes()),markdown=path.relative_to(output).as_posix()))
            except (httpx.HTTPError,ValueError,OSError,UnicodeError) as exc:
                records.append(dict(source_id=source,source_url=SOURCES[source]["url"],status="erro",erro=str(exc)))
            print(source,records[-1]["status"],flush=True)
    report=dict(total=len(records),extraidos=sum(r["status"]=="extraido" for r in records),falhas=sum(r["status"]=="erro" for r in records),documentos=records)
    (output/"manifesto.json").write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode("utf-8"))
    lines=["# ISS e NFS-e — Distrito Federal","","> Vigência não verificada. Revisão humana pendente. Fontes de legislação, orientação e fornecedor identificadas nos metadados.",""]
    for r in records:
        lines.append(f'- [{r["source_id"]}]({r["markdown"]}) — {r["status"]}' if "markdown" in r else f'- {r["source_id"]}: ERRO — {r["erro"]}')
    (output/"indice.md").write_bytes(("\n".join(lines)+"\n").encode("utf-8"))
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT);parser.add_argument("--source",choices=["all",*SOURCES],default="all");args=parser.parse_args()
    report=collect(args.output,None if args.source=="all" else [args.source]);print(json.dumps(report,ensure_ascii=False,indent=2));return int(bool(report["falhas"]))

if __name__=="__main__":raise SystemExit(main())
