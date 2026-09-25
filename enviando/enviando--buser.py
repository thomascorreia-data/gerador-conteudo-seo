"""
Envia as descrições geradas pra API de páginas de empresa da Buser
(produção): cria (POST) ou atualiza (PATCH, se já existir) a company-page
de cada empresa.

Fluxo por PASTA (sem precisar renomear nada na mão):
    enviando/lotes/           <- solte aqui qualquer .xlsx novo (qualquer nome)
    enviando/lotes_enviados/  <- pra onde um arquivo vai sozinho, DEPOIS de
                                  processado, só se TODAS as empresas dele
                                  deram certo (sem nenhum erro 400/500)

Rodando o script, ele lê TODOS os .xlsx de enviando/lotes/, manda cada
empresa (POST -> se já existir, cai pro PATCH) e só arquiva o arquivo que
terminou 100% sem erro. Se sobrar erro (ex: slug errado), o arquivo FICA em
lotes/ — corrija o slug direto nele e rode de novo, sem mover nada na mão.

Mapeamento planilha -> API:
    Slug                  -> company_slug (vem pronto da planilha)
    Descrição Vendas      -> summary_text
    Descrição Informativo -> about_text

Uso:
    ./venv/bin/python enviando--buser.py --dry-run          # só mostra o que seria enviado
    ./venv/bin/python enviando--buser.py --dry-run --limite 3
    ./venv/bin/python enviando--buser.py --limite 1          # envia só a 1a empresa, de verdade
    ./venv/bin/python enviando--buser.py                     # envia tudo que estiver em lotes/, de verdade
    ./venv/bin/python enviando--buser.py --json caminho.json # modo antigo, um arquivo só, sem mexer em lotes/
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

_DIR_ENVIANDO = os.path.dirname(os.path.abspath(__file__))
PASTA_LOTES = os.path.join(_DIR_ENVIANDO, "lotes")
PASTA_LOTES_ENVIADOS = os.path.join(_DIR_ENVIANDO, "lotes_enviados")

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


def limpar_slug(slug: str) -> str:
    """Remove o segmento "empresa" do slug, onde quer que apareça (sufixo,
    meio, etc.) — visto ao vivo: a planilha às vezes traz nomes genéricos
    tipo "Nobre Empresa"/"Scatur Empresa" (usados como placeholder na hora
    de identificar que o tema é uma empresa), e o slug resultante
    ("nobre-empresa") não existe de verdade no banco da Buser (só
    "nobre"). Junta hífens duplos que sobrarem depois de remover o segmento."""
    segmentos = [s for s in slug.split("-") if s.lower() != "empresa"]
    return "-".join(segmentos)


def listar_lotes_pendentes() -> list:
    """Lista os .xlsx em enviando/lotes/, em ordem alfabética (determinística
    entre rodadas). Cria a pasta na hora se ainda não existir (primeira vez
    rodando depois dessa mudança)."""
    os.makedirs(PASTA_LOTES, exist_ok=True)
    os.makedirs(PASTA_LOTES_ENVIADOS, exist_ok=True)
    return sorted(
        os.path.join(PASTA_LOTES, nome)
        for nome in os.listdir(PASTA_LOTES)
        if nome.lower().endswith(".xlsx") and not nome.startswith("~$")  # ~$ = lock file do Excel aberto
    )


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
            "company_slug": limpar_slug(str(slug).strip()),
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


def enviar(empresa: dict, dry_run: bool) -> bool:
    """Devolve True se deu certo (2xx) ou é dry-run, False se deu erro —
    quem chama usa isso pra decidir se o ARQUIVO inteiro pode ser arquivado
    em lotes_enviados/ (só quando NENHUMA empresa dele falhou)."""
    slug = empresa["company_slug"]
    payload = {
        "company_slug": slug,
        "summary_text": quebras_para_html(empresa["summary_text"]),
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
        return True

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
        return False
    return True


def processar_arquivo(caminho: str, dry_run: bool, limite: int = None) -> bool:
    """Envia todas as empresas de um arquivo. Devolve True (arquivo 100%
    sem erro, pode arquivar) ou False (sobrou erro, arquivo fica onde está)."""
    print(f"\n=== {os.path.basename(caminho)} ===")
    empresas = carregar_empresas(caminho)
    if limite:
        empresas = empresas[:limite]

    print(f"{len(empresas)} empresa(s) neste arquivo ({'dry-run' if dry_run else 'ENVIO REAL para ' + BASE_URL}).")

    tudo_certo = True
    for empresa in empresas:
        deu_certo = enviar(empresa, dry_run=dry_run)
        tudo_certo = tudo_certo and deu_certo
        if not dry_run:
            time.sleep(0.5)

    return tudo_certo


def arquivar(caminho: str) -> None:
    destino = os.path.join(PASTA_LOTES_ENVIADOS, os.path.basename(caminho))
    os.rename(caminho, destino)
    print(f"  -> arquivo 100% sem erro, movido pra {os.path.relpath(destino, _DIR_ENVIANDO)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que seria enviado, não chama a API")
    parser.add_argument("--limite", type=int, default=None, help="processa só as N primeiras empresas de CADA arquivo (pra teste)")
    parser.add_argument("--json", metavar="CAMINHO", help="lê de um .json exportado pela interface, em vez da pasta enviando/lotes/")
    args = parser.parse_args()

    if not args.dry_run and not API_KEY:
        sys.exit("BUSER_API_KEY não configurada no .env")

    if args.json:
        empresas = carregar_empresas_de_json(args.json)
        if args.limite:
            empresas = empresas[: args.limite]
        print(f"{len(empresas)} empresa(s) a processar ({'dry-run' if args.dry_run else 'ENVIO REAL para ' + BASE_URL}).\n")
        for empresa in empresas:
            enviar(empresa, dry_run=args.dry_run)
            if not args.dry_run:
                time.sleep(0.5)
        return

    arquivos = listar_lotes_pendentes()
    if not arquivos:
        print(f"Nenhum .xlsx encontrado em {os.path.relpath(PASTA_LOTES, _DIR_ENVIANDO)}/ — nada a fazer.")
        return

    print(f"{len(arquivos)} arquivo(s) pendente(s) em {os.path.relpath(PASTA_LOTES, _DIR_ENVIANDO)}/")

    for caminho in arquivos:
        tudo_certo = processar_arquivo(caminho, dry_run=args.dry_run, limite=args.limite)
        if not args.dry_run and tudo_certo:
            arquivar(caminho)


if __name__ == "__main__":
    main()
