from grafo_descricao import _checar_regras, _rotear_por_categoria, no_coletar_lugar_generico, no_coletar_evento


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


def test_empresa_promocional_tambem_precisa_de_exatamente_4_paragrafos():
    tres_paragrafos = "Um.\n\nDois.\n\nTrês."
    motivos = _checar_regras(_state(tres_paragrafos, categoria="empresa", tom="promocional"))
    assert any("esperado sempre 4" in m for m in motivos)

    quatro_paragrafos = "Um.\n\nDois.\n\nTrês.\n\nQuatro."
    motivos = _checar_regras(_state(quatro_paragrafos, categoria="empresa", tom="promocional"))
    assert not any("esperado sempre 4" in m for m in motivos)


def test_cidade_nao_exige_contagem_de_paragrafos():
    texto = "Só um parágrafo aqui."
    motivos = _checar_regras(_state(texto, categoria="cidade", tom="vendas"))
    assert not any("parágrafos" in m for m in motivos)


# --- negrito (só empresa) ----------------------------------------------------

def test_negrito_de_nome_da_empresa_sozinho_nao_reprova_mais():
    # Antes era bloqueado; agora é só preferência no prompt (ver Guirro
    # Transporte, testado ao vivo: um texto bom foi reprovado 3x só por
    # isso) — o revisor não trava mais nesse caso específico.
    texto = "A **Guirro Transporte** atua em todo o Brasil."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Guirro Transporte"))
    assert not any("nome da empresa" in m for m in motivos)


def test_negrito_de_ano_isolado_reprova():
    texto = "Fundada em **1964**, a empresa é tradicional."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert any("palavra só" in m for m in motivos)


def test_negrito_com_lista_longa_reprova():
    # 4+ itens (2+ vírgulas) = lista longa de verdade (cidades/rotas).
    texto = "A empresa conecta **São Paulo, Campinas, Brasília e Goiânia**."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert any("parece uma lista longa" in m for m in motivos)


def test_negrito_com_enumeracao_curta_de_3_itens_nao_reprova():
    # 3 itens (1 vírgula só) é o padrão BOM de combinar benefícios/comodidades
    # numa frase só (ex: "ar-condicionado, Wi-Fi e sanitários") — não pode
    # ser confundido com a lista longa que a regra acima pega.
    texto = "A frota conta com **ar-condicionado, Wi-Fi e sanitários** modernos."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert not any("lista" in m for m in motivos)


def test_negrito_repetido_reprova_uma_vez_so_mesmo_repetindo_varias_vezes():
    texto = "A **Eucatur** é tradicional. A **Eucatur** também é segura. Viaje com a **Eucatur**."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    motivos_repeticao = [m for m in motivos if "aparece" in m and "no texto" in m]
    assert len(motivos_repeticao) == 1
    assert "3x" in motivos_repeticao[0]


def test_negrito_em_frase_chave_nao_reprova():
    texto = (
        "A empresa é uma das **maiores e mais tradicionais empresas do Brasil**, "
        "com **linhas regulares interestaduais**."
    )
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert not any("negrito" in m for m in motivos)


def test_negrito_com_mais_de_8_palavras_reprova():
    # Visto ao vivo: sem essa checagem, o modelo negritava a frase inteira
    # (14-16 palavras) em vez de só a parte essencial.
    texto = (
        "A **Eucatur é uma das mais tradicionais empresas de transporte rodoviário "
        "de passageiros do Brasil**, atuando sob regulamentação da ANTT."
    )
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert any("longo demais" in m for m in motivos)


def test_negrito_com_exatamente_8_palavras_nao_reprova():
    texto = "A empresa se destaca por **oferecer linhas regulares de ônibus modernas e seguras**."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert not any("longo demais" in m for m in motivos)


def test_texto_sem_negrito_nenhum_nao_reprova_por_isso():
    # A regra permite deixar um parágrafo sem negrito quando não há frase
    # que valha destacar — texto sem NENHUM "**...**" não pode reprovar.
    texto = "A empresa opera linhas regulares interestaduais com segurança."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert not any("negrito" in m for m in motivos)


def test_contagem_de_palavras_vazada_reprova():
    # Bug visto ao vivo: o modelo copiou a anotação didática "(N palavras)"
    # do exemplo do prompt pro texto de verdade.
    texto = "A empresa opera **linhas regulares** (5 palavras) com segurança."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert any("contagem de palavras" in m for m in motivos)


def test_contagem_de_palavras_sem_parenteses_nao_reprova():
    texto = "A empresa opera **linhas regulares interestaduais** com segurança."
    motivos = _checar_regras(_state(texto, categoria="empresa", entidade="Eucatur"))
    assert not any("contagem de palavras" in m for m in motivos)


def test_negrito_fora_da_categoria_empresa_nao_e_checado():
    # A regra de negrito é específica de empresa — não faz sentido aplicar
    # a mesma checagem pra cidade/ponto turístico/etc, que nem têm essa
    # instrução no prompt.
    texto = "A **Salvador** é conhecida por sua história."
    motivos = _checar_regras(_state(texto, categoria="cidade", entidade="Salvador"))
    assert not any("negrito" in m for m in motivos)
