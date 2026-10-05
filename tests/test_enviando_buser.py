"""
Testes de enviando/enviando--buser.py — só limpar_slug() (lógica pura, sem
chamar a API de produção). O arquivo tem hífen duplo no nome (não é um
identificador Python válido), então é carregado via importlib em vez de um
"from enviando--buser import ..." normal.
"""

import importlib.util
import os

_CAMINHO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "enviando", "enviando_descricao_empresas", "enviando--buser.py",
)
_spec = importlib.util.spec_from_file_location("enviando_buser", _CAMINHO)
enviando_buser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enviando_buser)

limpar_slug = enviando_buser.limpar_slug


def test_limpar_slug_remove_segmento_empresa():
    assert limpar_slug("nobre-empresa") == "nobre"
    assert limpar_slug("empresa-esmeraldas-turismo") == "esmeraldas-turismo"


def test_limpar_slug_remove_segmento_onibus():
    # Caso real: nomes tipo "Planalto Empresa Ônibus" (placeholder usado
    # quando não se sabe um nome mais específico) viram slug real SEM
    # nenhum dos dois segmentos — confirmado ao vivo em ~37 empresas de um
    # lote só, sempre com esse mesmo padrão.
    assert limpar_slug("planalto-empresa-onibus") == "planalto"
    assert limpar_slug("704-empresa-onibus") == "704"
    assert limpar_slug("xavier-empresa-onibus") == "xavier"


def test_limpar_slug_nao_mexe_em_slug_sem_placeholder():
    assert limpar_slug("viacao-itapemirim") == "viacao-itapemirim"
    assert limpar_slug("expresso-de-prata") == "expresso-de-prata"


def test_limpar_slug_nao_remove_onibus_solto_sem_vir_de_empresa():
    # Regressão real: "onibus" removido indiscriminadamente quebrou o slug
    # de uma empresa cujo nome de verdade contém a palavra (não é
    # placeholder nenhum aqui, não tem "empresa" na frase).
    assert limpar_slug("passagens-de-onibus-online") == "passagens-de-onibus-online"





def test_limpar_slug_junta_hifens_duplos_que_sobram():
    assert limpar_slug("rio-tinto-empresa-onibus") == "rio-tinto"
