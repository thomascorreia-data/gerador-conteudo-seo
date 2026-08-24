"""
Setup compartilhado por toda a suíte de testes — roda antes de qualquer
teste ser coletado/importado.

1) Chaves de API falsas: alguns módulos (interacao_ia_descricao.py,
   interpretador_descricao.py) levantam ValueError na IMPORTAÇÃO se
   OPENAI_API_KEY não estiver setada. Os testes aqui são todos de lógica
   pura (não chamam a API de verdade), então uma chave falsa é suficiente
   pra passar da importação — e evita que a suíte dependa de rede, custo
   ou segredo nenhum, seja local ou em CI. Setado ANTES de qualquer
   load_dotenv() interno dos módulos: por padrão, load_dotenv() não
   sobrescreve uma env var que já existe, então isso "vence" mesmo se
   houver um .env real na máquina.
2) sys.path: os módulos de formatos/descricao/ fazem imports simples entre
   si (ex: "from interpretador_descricao import ..."), não qualificados
   como pacote — precisam que a própria pasta esteja em sys.path, o mesmo
   truque já usado em formatos/gerando.py.
"""

import os
import sys

os.environ.setdefault("OPENAI_API_KEY", "sk-test-0000000000000000000000000000000000000000")
os.environ.setdefault("SERPAPI_API_KEY", "test-dummy-serpapi-key")

_DIR_TESTS = os.path.dirname(os.path.abspath(__file__))
_DIR_RAIZ = os.path.dirname(_DIR_TESTS)
_DIR_FORMATOS = os.path.join(_DIR_RAIZ, "formatos")
_DIR_DESCRICAO = os.path.join(_DIR_FORMATOS, "descricao")

for _dir in (_DIR_RAIZ, _DIR_FORMATOS, _DIR_DESCRICAO):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
