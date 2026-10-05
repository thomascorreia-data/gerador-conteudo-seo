"""
Envia o FAQ gerado pra API de páginas de empresa da Buser (produção): cada
chamada SUBSTITUI o FAQ inteiro da página pelo que for mandado aqui — o
que estava cadastrado antes some, fica só o que vier na lista.

Entrada: o JSON exportado da interface (botão "baixar .json" depois de
"Gerar conteúdo com IA" com formato FAQ) — uma lista de itens, cada um já
com "company_slug" e "faqs" (lista de {"question", "answer"}) prontos,
no mesmo formato que formatos/gerando.py preenche pra item de FAQ. Um
arquivo pode trazer 1 empresa ou várias — todo item que tiver os dois
campos é enviado, os outros (erro de geração, outro formato) são pulados.

Método e endpoint (por empresa):
    POST {BASE_URL}/api/pages/integration/company-pages/<company_slug>/faqs
    Body: {"faqs": [{"question": "...", "answer": "..."}, ...]}

Respostas esperadas:
    200 - sucesso, devolve {"id", "company_slug", "faqs_count"}
    404 - a empresa não tem página cadastrada ainda
    400 - alguma pergunta sem "question" ou "answer"
    401 - API key ausente ou inválida

Arquivamento: depois de um envio REAL (sem --dry-run) em que TODAS as
empresas do arquivo deram certo, o JSON de entrada é movido pra
enviando_faq_empresas/jsons_enviados/ — mesmo padrão de
enviando_descricao_empresas/lotes_enviados/, pra não precisar mover nada
na mão nem reenviar o mesmo arquivo por engano depois.

Uso:
    ./venv/bin/python enviando-faq.py caminho.json --dry-run
    ./venv/bin/python enviando-faq.py caminho.json --dry-run --limite 1
    ./venv/bin/python enviando-faq.py caminho.json --limite 1   # testa só a 1a, de verdade
    ./venv/bin/python enviando-faq.py caminho.json             # envia tudo, de verdade
"""

import argparse
import json
import os
import shutil
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.buser.com.br"
API_KEY_HEADER = "X-API-KEY"

_DIR_SCRIPT = os.path.dirname(os.path.abspath(__file__))
PASTA_JSONS_ENVIADOS = os.path.join(_DIR_SCRIPT, "jsons_enviados")

API_KEY = os.getenv("BUSER_API_KEY")


def _headers():
    return {API_KEY_HEADER: API_KEY, "Content-Type": "application/json"}


def carregar_itens(caminho: str) -> list:
    """Lê o JSON exportado da interface e devolve só os itens prontos pra
    enviar: precisa ter "company_slug" e "faqs" (lista não vazia) — item
    de outro formato, ou de FAQ que deu erro na geração, não tem esses
    campos e é ignorado aqui (não trava o resto do arquivo)."""
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    itens = []
    for item in dados:
        company_slug = item.get("company_slug")
        faqs = item.get("faqs")
        if not company_slug or not faqs:
            continue
        itens.append({
            "nome": item.get("tema") or company_slug,
            "company_slug": company_slug,
            "faqs": faqs,
        })
    return itens


def enviar_faq(item: dict, dry_run: bool) -> bool:
    """Devolve True se deu certo (200) ou é dry-run, False se deu erro."""
    slug = item["company_slug"]
    endpoint = f"{BASE_URL}/api/pages/integration/company-pages/{slug}/faqs"
    payload = {"faqs": item["faqs"]}

    if dry_run:
        print(f"[DRY-RUN] {item['nome']!r} -> company_slug={slug!r} ({len(item['faqs'])} pergunta(s))")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return True

    resposta = requests.post(endpoint, headers=_headers(), json=payload, timeout=30)

    print(f"{item['nome']} ({slug}): {resposta.status_code}")
    if resposta.status_code >= 400:
        print(f"  -> {resposta.text[:300]}")
        return False
    return True


def arquivar(caminho: str) -> None:
    os.makedirs(PASTA_JSONS_ENVIADOS, exist_ok=True)
    destino = os.path.join(PASTA_JSONS_ENVIADOS, os.path.basename(caminho))
    shutil.move(caminho, destino)
    print(f"-> arquivo 100% sem erro, movido pra {destino}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json", metavar="CAMINHO", help="JSON exportado da interface (baixar .json)")
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que seria enviado, não chama a API")
    parser.add_argument("--limite", type=int, default=None, help="processa só as N primeiras empresas (pra teste)")
    args = parser.parse_args()

    if not args.dry_run and not API_KEY:
        sys.exit("BUSER_API_KEY não configurada no .env")

    itens = carregar_itens(args.json)
    if args.limite:
        itens = itens[: args.limite]

    if not itens:
        print("Nenhum item com company_slug + faqs encontrado nesse JSON.")
        return

    print(f"{len(itens)} empresa(s) a processar ({'dry-run' if args.dry_run else 'ENVIO REAL para ' + BASE_URL}).\n")

    sucesso = 0
    for item in itens:
        if enviar_faq(item, dry_run=args.dry_run):
            sucesso += 1
        if not args.dry_run:
            time.sleep(0.5)

    if not args.dry_run:
        print(f"\n{sucesso}/{len(itens)} FAQ(s) enviado(s) com sucesso.")
        if sucesso == len(itens):
            arquivar(args.json)


if __name__ == "__main__":
    main()
