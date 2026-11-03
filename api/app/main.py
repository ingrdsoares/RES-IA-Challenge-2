from fastapi import FastAPI

app = FastAPI(title="RES-IA-Challenge-2", description="Aproximadamente 95% a 99% das empresas ativas no Brasil são micro e pequenos negócios. A falta de formação contábil gera dependência cega do contador e terror fiscal nos empreendedores. O Sócio Digital é uma aplicação inteligente que:")


@app.get("/health")
def health():
    return {"status": "ok"}
