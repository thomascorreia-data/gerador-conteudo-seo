"""
Envia as descrições geradas (empresas_descricoes.xlsx) pra API de páginas de
empresa da Buser (produção): cria (POST) ou atualiza (PATCH, se já existir)
a company-page de cada empresa.

Mapeamento planilha -> API:
    Slug                  -> company_slug (vem pronto da planilha, não é mais adivinhado do nome)
    Descrição Vendas      -> summary_text
    Descrição Informativo -> about_text

Uso:
    ./venv/bin/python enviando--buser.py --dry-run          # só mostra o que seria enviado
    ./venv/bin/python enviando--buser.py --dry-run --limite 3
    ./venv/bin/python enviando--buser.py --limite 1          # envia só a 1a empresa, de verdade
    ./venv/bin/python enviando--buser.py                     # envia todas, de verdade
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict

import requests
from dotenv import load_dotenv
from openpyxl import load_workbook

load_dotenv()

BASE_URL = "https://www.buser.com.br"
ENDPOINT = f"{BASE_URL}/api/pages/integration/company-pages"
XLSX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "empresas_descricoes.xlsx")

API_KEY = os.getenv("BUSER_API_KEY")


PREFIXO_TEMA_EMPRESA = re.compile(r"^\s*empresa\s+", re.IGNORECASE)


def slugify(nome: str) -> str:
    """Mesma receita usada em formatos/transformacaoJson.py: sem acento,
    minúsculo, qualquer sequência de não-alfanumérico vira um único '-'."""
    # Remove o prefixo "Empresa " (usado só como pista de categoria na hora
    # de digitar o tema, ex: "Empresa Esmeraldas Turismo") antes de slugificar
    # — senão o slug sai como "empresa-esmeraldas-turismo" em vez do slug
    # real da empresa em produção ("esmeraldas-turismo").
    nome = PREFIXO_TEMA_EMPRESA.sub("", nome)
    texto = unicodedata.normalize("NFKD", nome)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto


def carregar_empresas(caminho: str) -> list:
    """Lê o xlsx com 4 colunas: Slug, Nome da Empresa, Descrição Informativo,
    Descrição Vendas. O slug agora vem pronto na planilha — não é mais
    adivinhado a partir do nome (slugify só fica pro caminho de JSON, que
    não tem essa coluna)."""
    wb = load_workbook(caminho, data_only=True)
    ws = wb.active
    linhas = list(ws.iter_rows(values_only=True))
    _cabecalho, *dados = linhas

    empresas = []
    for slug, nome, informativo, vendas in dados:
        if not nome or not slug:
            continue
        empresas.append({
            "nome": nome,
            "company_slug": str(slug).strip(),
            "summary_text": (vendas or "").strip(),
            "about_text": (informativo or "").strip(),
        })
    return empresas


def carregar_empresas_de_json(caminho: str) -> list:
    """Lê o JSON exportado pela interface (baixar .json): uma lista achatada
    de itens, um por (tema, tom) — ex: "Empresa X" aparece 2x, um item com
    tom="Vendas" e outro com tom="Informativo". Agrupa por "tema" pra montar
    uma empresa só com os dois textos, do mesmo jeito que carregar_empresas()
    faz a partir das duas colunas do xlsx."""
    with open(caminho, encoding="utf-8") as arquivo:
        itens = json.load(arquivo)

    por_tema = defaultdict(dict)
    for item in itens:
        tema = item.get("tema")
        tom = (item.get("tom") or "").strip().lower()
        texto = (item.get("conteudo_gerado") or "").strip()
        if not tema or not texto:
            continue
        por_tema[tema][tom] = texto

    empresas = []
    for tema, textos in por_tema.items():
        empresas.append({
            "nome": tema,
            "company_slug": slugify(tema),
            "summary_text": textos.get("vendas", ""),
            "about_text": textos.get("informativo", ""),
        })
    return empresas


def _headers():
    return {"X-API-KEY": API_KEY, "Content-Type": "application/json"}


def quebras_para_html(texto: str) -> str:
    """O campo espera HTML, não texto puro — troca cada quebra de linha por
    <br>, então "par.1\\n\\npar.2" (parágrafos separados por linha em branco)
    vira "par.1<br><br>par.2"."""
    return texto.replace("\n", "<br>")


def enviar(empresa: dict, dry_run: bool) -> None:
    slug = empresa["company_slug"]
    payload = {
        "company_slug": slug,
        "summary_text": quebras_para_html(empresa["summary_text"]),
        "contact_text": " ",
        "contact_email": " ",
        "about_text": quebras_para_html(empresa["about_text"]),
        "faqs": [],
    }

    if dry_run:
        print(f"[DRY-RUN] {empresa['nome']!r} -> slug={slug!r}")
        # json.dumps (não um print cru) de propósito: é a mesma serialização
        # que requests.post(json=payload) faz por baixo — se o "\n\n" for
        # pra sobreviver na requisição real, tem que aparecer aqui como
        # "\n\n" literal dentro da string (é assim que JSON representa
        # quebra de linha; ao ser lido de volta, volta a virar quebra real).
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    resposta = requests.post(ENDPOINT, headers=_headers(), json=payload, timeout=30)

    if resposta.status_code == 409:
        # Empresa já tem página: cai pro PATCH (update parcial) em vez de falhar.
        resposta = requests.patch(
            f"{ENDPOINT}/{slug}",
            headers=_headers(),
            json={"summary_text": payload["summary_text"], "about_text": payload["about_text"]},
            timeout=30,
        )
        acao = "PATCH (já existia)"
    else:
        acao = "POST"

    print(f"{empresa['nome']} ({slug}) [{acao}]: {resposta.status_code}")
    if resposta.status_code >= 400:
        print(f"  -> {resposta.text[:300]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que seria enviado, não chama a API")
    parser.add_argument("--limite", type=int, default=None, help="processa só as N primeiras empresas (pra teste)")
    parser.add_argument("--json", metavar="CAMINHO", help="lê de um .json exportado pela interface em vez do xlsx padrão")
    args = parser.parse_args()

    if not args.dry_run and not API_KEY:
        sys.exit("BUSER_API_KEY não configurada no .env")

    if args.json:
        empresas = carregar_empresas_de_json(args.json)
    else:
        empresas = carregar_empresas(XLSX_PATH)
    if args.limite:
        empresas = empresas[: args.limite]

    print(f"{len(empresas)} empresa(s) a processar ({'dry-run' if args.dry_run else 'ENVIO REAL para ' + BASE_URL}).\n")
    for empresa in empresas:
        enviar(empresa, dry_run=args.dry_run)
        if not args.dry_run:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
