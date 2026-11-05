from fastapi import FastAPI

DESCRIPTION = (
    "Aproximadamente 95% a 99% das empresas ativas no Brasil são micro e pequenos negócios. "
    "A falta de formação contábil gera dependência cega do contador e terror fiscal nos "
    "empreendedores. O Sócio Digital é uma aplicação inteligente de copiloto fiscal."
)

app = FastAPI(
    title="Sócio Digital - Copiloto de Gestão Fiscal",
    description=DESCRIPTION,
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}
