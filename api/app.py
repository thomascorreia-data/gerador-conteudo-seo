"""
API HTTP pequena que expõe a função `normalizar_lote` (de transformacaoJson.py)
como um endpoint, para ser chamada pela interface HTML (ou por qualquer outro
cliente) sem precisar rodar o script Python manualmente a cada vez.

Como rodar:
    pip install fastapi uvicorn
    uvicorn api:app --reload --port 8000

Depois disso, a API fica disponível em:
    http://127.0.0.1:8000/normalizar   (POST)

Documentação automática (Swagger) em:
    http://127.0.0.1:8000/docs
"""

from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from formatos.transformacaoJson import normalizar_lote
from formatos.gerando import gerar_conteudo

app = FastAPI(title="API Prensa — Normalização de Entrada")

# Libera chamadas vindas do navegador (útil se a interface for aberta como
# arquivo local em vez de servida por aqui). Em produção, troque "*" pela
# origem real do seu front-end.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequisicaoNormalizar(BaseModel):
    # Aceita o JSON de entrada inteiro (envelope + Temas) como veio da interface.
    # Usamos Dict[str, Any] em vez de um schema rígido porque os nomes dos
    # campos variam (acento, espaço, etc.) e isso já é tratado dentro de
    # normalizar_lote.
    payload: Dict[str, Any]


class RequisicaoGerar(BaseModel):
    # Recebe a lista já normalizada (o "resultado" devolvido por /normalizar).
    itens: List[Dict[str, Any]]

app.mount("/interface", StaticFiles(directory="interface"), name="interface")

@app.get("/health")
def health():
    """Endpoint simples para checar se a API está no ar."""
    return {"status": "ok"}

@app.post("/normalizar")
def normalizar(requisicao: RequisicaoNormalizar):
    try:
        resultado, avisos = normalizar_lote(requisicao.payload)
    except ValueError as erro:
        # Erro de validação do próprio conteúdo enviado (ex: "Temas" ausente)
        raise HTTPException(status_code=400, detail=str(erro))
    except Exception as erro:
        # Qualquer outro erro inesperado
        raise HTTPException(status_code=500, detail=f"Erro interno: {erro}")

    return {
        "resultado": resultado,
        "avisos": avisos,
        "total_itens": len(resultado),
    }


@app.post("/gerar")
def gerar(requisicao: RequisicaoGerar):
    try:
        resultados = gerar_conteudo(requisicao.itens)
    except Exception as erro:
        raise HTTPException(status_code=500, detail=f"Erro interno: {erro}")

    return {
        "resultados": resultados,
        "total_itens": len(resultados),
    }
