from base_empresas import _classificar_tipo_empresa, _slug


def _fontes(texto: str) -> dict:
    """Monta um dict de fontes no mesmo formato que coletar_empresa produz,
    com o texto de teste dentro de "conteudo" — é só isso que
    _classificar_tipo_empresa lê."""
    return {"Google_AIOverview": {"conteudo": texto, "erro": None}}


def test_linha_regular_pura():
    fontes = _fontes("A Eucatur opera linhas regulares em todo o país.")
    resultado = _classificar_tipo_empresa(fontes, "Eucatur")
    assert resultado["tipo"] == "linha_regular"
    assert resultado["palavra"] == "passagem"
    assert "Eucatur" in resultado["instrucao"]


def test_hibrida_quando_menciona_os_dois():
    fontes = _fontes("Opera linhas regulares de ônibus e também realiza fretamento para excursões.")
    resultado = _classificar_tipo_empresa(fontes, "Brasil Bus")
    assert resultado["tipo"] == "hibrida"
    assert resultado["palavra"] == "passagem"


def test_fretamento_puro():
    fontes = _fontes("Agência especializada em fretamento e turismo para excursões.")
    resultado = _classificar_tipo_empresa(fontes, "Allestur")
    assert resultado["tipo"] == "fretamento"
    assert resultado["palavra"] == "viagem"


def test_ambiguo_quando_fonte_nao_ajuda():
    fontes = _fontes("Empresa de transporte rodoviário reconhecida no mercado.")
    resultado = _classificar_tipo_empresa(fontes, "Empresa X")
    assert resultado["tipo"] == "ambiguo"
    assert resultado["palavra"] == "viagem"


def test_fontes_vazias_dao_ambiguo():
    resultado = _classificar_tipo_empresa({}, "Empresa Sem Fonte")
    assert resultado["tipo"] == "ambiguo"


def test_slug_remove_acento_espaco_e_pontuacao():
    assert _slug("Expresso JK") == "expressojk"
    assert _slug("Brasil Bus") == "brasilbus"
    assert _slug("São José Ltda.") == "saojoseltda"
