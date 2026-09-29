from grafo_descricao import _checar_regras, _rotear_por_categoria, no_coletar_lugar_generico, no_coletar_evento, no_revisor_ia


class _FakeModelo:
    """Substitui o ChatOpenAI inteiro (não dá pra sobrescrever só o método
    ".invoke" de uma instância pydantic — ChatOpenAI bloqueia atribuir
    atributo que não é um field declarado)."""

    def __init__(self, resposta):
        self._resposta = resposta
        self.chamadas = []

    def invoke(self, prompt, **kwargs):
        self.chamadas.append(prompt)
        return type("_Resposta", (), {"content": self._resposta})()


def _fontes(texto: str) -> dict:
    return {"Google_AIOverview": {"conteudo": texto, "erro": None}}


# --- roteamento por categoria -----------------------------------------------

def test_roteamento_reconhece_todas_as_categorias_implementadas():
    esperado = {
        "empresa": "coletar_empresa",
        "ponto_turistico": "coletar_ponto_turistico",
        "cidade": "coletar_cidade",
        "terminal_rodoviaria": "coletar_terminal_rodoviaria",
        "lugar_generico": "coletar_lugar_generico",
        "evento": "coletar_evento",
    }
    for categoria, no_esperado in esperado.items():
        assert _rotear_por_categoria({"categoria": categoria}) == no_esperado


def test_roteamento_categoria_desconhecida_cai_em_nao_implementada():
    assert _rotear_por_categoria({"categoria": "estado"}) == "categoria_nao_implementada"


def test_coletar_lugar_generico_chama_o_coletor_com_a_entidade(monkeypatch):
    # no_coletar_lugar_generico só repassa o resultado do coletor de
    # verdade (base_lugares_genericos.py, só Wikipédia) — sem chamar rede
    # de verdade aqui, só confere que a entidade certa é passada e o
    # "fontes" do coletor é repassado tal e qual.
    chamadas = []

    def _fake_coletar(nome_lugar):
        chamadas.append(nome_lugar)
        return {"lugar": nome_lugar, "fontes": {"Wikipedia": {"url": "u", "conteudo": "c", "erro": None}}}

    monkeypatch.setattr("grafo_descricao.coletar_lugar_generico", _fake_coletar)

    resultado = no_coletar_lugar_generico({"entidade": "Shopping Eldorado"})

    assert chamadas == ["Shopping Eldorado"]
    assert resultado == {"fontes": {"Wikipedia": {"url": "u", "conteudo": "c", "erro": None}}}


def test_coletar_evento_chama_o_coletor_com_entidade_e_cidade(monkeypatch):
    # Mesmo padrão de no_coletar_lugar_generico, mas também repassa
    # "cidade" — coletar_evento usa isso pra desambiguar eventos cujo nome
    # colide com uma versão internacional mais famosa (ver base_eventos.py).
    chamadas = []

    def _fake_coletar(nome_evento, cidade=None):
        chamadas.append((nome_evento, cidade))
        return {"evento": nome_evento, "fontes": {"Wikipedia": {"url": "u", "conteudo": "c", "erro": None}}}

    monkeypatch.setattr("grafo_descricao.coletar_evento", _fake_coletar)

    resultado = no_coletar_evento({"entidade": "Oktoberfest", "cidade": "Blumenau"})

    assert chamadas == [("Oktoberfest", "Blumenau")]
    assert resultado == {"fontes": {"Wikipedia": {"url": "u", "conteudo": "c", "erro": None}}}


def _state(texto_humanizado: str, **extra) -> dict:
    base = {"texto_humanizado": texto_humanizado, "categoria": "cidade", "tom": "informativo"}
    base.update(extra)
    return base


# --- palavra/frase banida -----------------------------------------------

def test_frase_banida_reprova():
    motivos = _checar_regras(_state("Prepare-se para memórias inesquecíveis nessa viagem."))
    assert any("banida" in m for m in motivos)


def test_texto_sem_frase_banida_nao_reprova_por_isso():
    motivos = _checar_regras(_state("Um texto qualquer, sem nenhuma frase proibida."))
    assert not any("banida" in m for m in motivos)


# --- limite de palavras ----------------------------------------------------

def test_estoura_limite_de_palavras():
    texto = " ".join(["palavra"] * 20)
    motivos = _checar_regras(_state(texto, media_palavras=10))
    assert any("acima do limite" in m for m in motivos)


def test_dentro_do_limite_de_palavras_nao_reprova():
    texto = " ".join(["palavra"] * 10)
    motivos = _checar_regras(_state(texto, media_palavras=10))
    assert not any("acima do limite" in m for m in motivos)


# --- sede (só empresa) ------------------------------------------------------

def test_sede_inventada_nao_grounded_reprova():
    fontes = _fontes("A empresa conecta Sao Paulo, Uberlandia e Goiania em suas rotas.")
    texto = "Com sede em São Paulo, a empresa se destaca no setor."
    motivos = _checar_regras(_state(texto, categoria="empresa", fontes=fontes))
    assert any("sede" in m for m in motivos)


def test_sede_confirmada_na_fonte_nao_reprova():
    fontes = _fontes("A empresa e sediada em Cascavel (PR) e atua em todo o Brasil.")
    texto = "Com sede em Cascavel, a empresa se destaca no setor."
    motivos = _checar_regras(_state(texto, categoria="empresa", fontes=fontes))
    assert not any("sede" in m for m in motivos)


def test_sem_alegacao_de_sede_nao_reprova():
    fontes = _fontes("A empresa atua em todo o Brasil.")
    texto = "A empresa se destaca no setor de transporte rodoviário."
    motivos = _checar_regras(_state(texto, categoria="empresa", fontes=fontes))
    assert not any("sede" in m for m in motivos)


# --- passagem/viagem (só empresa) -------------------------------------------

def test_linha_regular_sem_passagem_reprova():
    texto = "A empresa oferece uma viagem segura e confortável."
    motivos = _checar_regras(_state(
        texto, categoria="empresa",
        classificacao_tipo={"tipo": "linha_regular", "palavra": "passagem"},
    ))
    assert any("passagem" in m for m in motivos)


def test_linha_regular_com_passagem_no_plural_nao_reprova():
    texto = "Compre suas passagens com a empresa."
    motivos = _checar_regras(_state(
        texto, categoria="empresa",
        classificacao_tipo={"tipo": "linha_regular", "palavra": "passagem"},
    ))
    assert not any('só apareceu "viagem"' in m for m in motivos)


def test_linha_regular_promocional_sem_passagem_nao_reprova():
    # Tom "promocional" não tem mais parágrafo de compra (proibido citar a
    # Buser) — a exigência de "passagem" não faz sentido aqui, só nos
    # outros tons (onde ainda existe contexto de compra).
    texto = "A empresa oferece uma viagem segura e confortável."
    motivos = _checar_regras(_state(
        texto, categoria="empresa", tom="promocional",
        classificacao_tipo={"tipo": "linha_regular", "palavra": "passagem"},
    ))
    assert not any('só apareceu "viagem"' in m for m in motivos)


def test_hibrida_vendas_subtitulo_com_viagem_reprova():
    texto = "Reserve sua viagem com a empresa pela Buser.\n\nEla atua em todo o país.\n\nCompre sua passagem com facilidade."
    motivos = _checar_regras(_state(
        texto, categoria="empresa", tom="vendas",
        classificacao_tipo={"tipo": "hibrida", "palavra": "passagem"},
    ))
    assert any("subtítulo usa" in m for m in motivos)


def test_fretamento_puro_com_passagem_reprova():
    texto = "Compre sua passagem com a empresa de fretamento."
    motivos = _checar_regras(_state(
        texto, categoria="empresa",
        classificacao_tipo={"tipo": "fretamento", "palavra": "viagem"},
    ))
    assert any('deveria usar "viagem"' in m for m in motivos)


def test_fretamento_puro_com_verbo_comprar_reprova():
    texto = "Você pode comprar sua viagem com a empresa de fretamento."
    motivos = _checar_regras(_state(
        texto, categoria="empresa",
        classificacao_tipo={"tipo": "fretamento", "palavra": "viagem"},
    ))
    assert any("não deveria usar" in m for m in motivos)


def test_fretamento_puro_correto_nao_reprova():
    # 4 parágrafos de verdade: hoje TODOS os tons de empresa exigem alguma
    # contagem (vendas: 3-4, informativo/promocional: exatamente 4), então
    # não tem mais um tom que "escape" dessa checagem pra isolar só a
    # palavra — o texto de teste precisa estar completo mesmo.
    texto = (
        "Parágrafo um.\n\n"
        "Parágrafo dois.\n\n"
        "Reserve sua viagem com a empresa de fretamento.\n\n"
        "Parágrafo quatro."
    )
    motivos = _checar_regras(_state(
        texto, categoria="empresa", tom="informativo",
        classificacao_tipo={"tipo": "fretamento", "palavra": "viagem"},
    ))
    assert motivos == []


def test_ambigua_pode_usar_passagem_sem_reprovar():
    # "ambiguo" não é "fretamento" -> a checagem inversa não se aplica
    texto = (
        "Parágrafo um.\n\n"
        "Parágrafo dois.\n\n"
        "Compre sua passagem com a empresa.\n\n"
        "Parágrafo quatro."
    )
    motivos = _checar_regras(_state(
        texto, categoria="empresa", tom="informativo",
        classificacao_tipo={"tipo": "ambiguo", "palavra": "viagem"},
    ))
    assert motivos == []


# --- contagem de parágrafos (só empresa) ------------------------------------

def test_empresa_vendas_com_2_paragrafos_reprova():
    texto = "Parágrafo um.\n\nParágrafo dois."
    motivos = _checar_regras(_state(texto, categoria="empresa", tom="vendas"))
    assert any("parágrafos" in m for m in motivos)


def test_empresa_vendas_com_3_paragrafos_nao_reprova_por_estrutura():
    texto = "Parágrafo um.\n\nParágrafo dois.\n\nParágrafo três."
    motivos = _checar_regras(_state(texto, categoria="empresa", tom="vendas"))
    assert not any("parágrafos" in m for m in motivos)


def test_empresa_informativo_precisa_de_exatamente_4_paragrafos():
    tres_paragrafos = "Um.\n\nDois.\n\nTrês."
    motivos = _checar_regras(_state(tres_paragrafos, categoria="empresa", tom="informativo"))
    assert any("esperado sempre 4" in m for m in motivos)

    quatro_paragrafos = "Um.\n\nDois.\n\nTrês.\n\nQuatro."
    motivos = _checar_regras(_state(quatro_paragrafos, categoria="empresa", tom="informativo"))
    assert not any("esperado sempre 4" in m for m in motivos)


def test_empresa_promocional_aceita_3_a_4_paragrafos_igual_vendas():
    # "promocional" virou um formato curto (mesmo padrão de "vendas": 3 a
    # 4 parágrafos) — não exige mais sempre 4 como o informativo.
    dois_paragrafos = "Um.\n\nDois."
    motivos = _checar_regras(_state(dois_paragrafos, categoria="empresa", tom="promocional"))
    assert any("parágrafos" in m for m in motivos)

    tres_paragrafos = "Um.\n\nDois.\n\nTrês."
    motivos = _checar_regras(_state(tres_paragrafos, categoria="empresa", tom="promocional"))
    assert not any("parágrafos" in m for m in motivos)

    quatro_paragrafos = "Um.\n\nDois.\n\nTrês.\n\nQuatro."
    motivos = _checar_regras(_state(quatro_paragrafos, categoria="empresa", tom="promocional"))
    assert not any("parágrafos" in m for m in motivos)

    cinco_paragrafos = "Um.\n\nDois.\n\nTrês.\n\nQuatro.\n\nCinco."
    motivos = _checar_regras(_state(cinco_paragrafos, categoria="empresa", tom="promocional"))
    assert any("parágrafos" in m for m in motivos)


def test_empresa_promocional_reprova_se_citar_buser():
    texto = "Um.\n\nDois.\n\nTrês.\n\nAo comprar sua passagem pela Buser, você viaja tranquilo."
    motivos = _checar_regras(_state(texto, categoria="empresa", tom="promocional"))
    assert any("não pode citar a Buser" in m for m in motivos)


def test_empresa_promocional_sem_citar_buser_nao_reprova_por_isso():
    texto = "Um.\n\nDois.\n\nTrês.\n\nUma empresa de tradição no setor."
    motivos = _checar_regras(_state(texto, categoria="empresa", tom="promocional"))
    assert not any("não pode citar a Buser" in m for m in motivos)


def test_empresa_informativo_pode_citar_buser():
    # A regra é só do tom "promocional" — informativo/vendas continuam
    # citando a Buser normalmente (empresa parceira de verdade).
    texto = "Um.\n\nDois.\n\nTrês.\n\nAo comprar sua passagem pela Buser, você viaja tranquilo."
    motivos = _checar_regras(_state(texto, categoria="empresa", tom="informativo"))
    assert not any("não pode citar a Buser" in m for m in motivos)


def test_cidade_nao_exige_contagem_de_paragrafos():
    texto = "Só um parágrafo aqui."
    motivos = _checar_regras(_state(texto, categoria="cidade", tom="vendas"))
    assert not any("parágrafos" in m for m in motivos)


# --- revisor_ia: empresa/promocional pula o julgamento de tom ---------------

def test_revisor_ia_empresa_promocional_aprova_sem_chamar_modelo(monkeypatch):
    fake = _FakeModelo("não deveria ser chamado")
    monkeypatch.setattr("grafo_descricao.modelo", fake)

    resultado = no_revisor_ia({
        "categoria": "empresa", "tom": "promocional", "texto_humanizado": "qualquer texto",
    })

    assert resultado == {"revisao_ia": {"tom_ok": True, "motivos": []}}
    assert fake.chamadas == []


def test_revisor_ia_empresa_informativo_ainda_chama_modelo(monkeypatch):
    # A exceção é só pra empresa/promocional — outras combinações
    # continuam passando pelo julgamento de IA normalmente.
    fake = _FakeModelo('{"tom_ok": true, "motivos": []}')
    monkeypatch.setattr("grafo_descricao.modelo", fake)

    no_revisor_ia({"categoria": "empresa", "tom": "informativo", "texto_humanizado": "qualquer texto"})

    assert len(fake.chamadas) == 1


def test_revisor_ia_cidade_promocional_ainda_chama_modelo(monkeypatch):
    # A exceção é só pra categoria "empresa" — cidade/promocional continua
    # sendo julgada normalmente (ainda cita a Buser, não muda).
    fake = _FakeModelo('{"tom_ok": true, "motivos": []}')
    monkeypatch.setattr("grafo_descricao.modelo", fake)

    no_revisor_ia({"categoria": "cidade", "tom": "promocional", "texto_humanizado": "qualquer texto"})

    assert len(fake.chamadas) == 1
