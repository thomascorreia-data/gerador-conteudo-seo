"""
Testes de formatos/faq/grafo_faq.py — revisor determinístico (quantidade +
respeito ao foco), a lógica de retry/esgotamento, e o humanizador de FAQ em
interacao_ia_faq.py. Nada aqui chama a OpenAI de verdade.
"""

from grafo_faq import (
    _checar_regras,
    _apos_revisor,
    _apos_revisor_ia,
    _decidir_retry_ou_esgotado,
    _motivos_da_reprovacao,
    no_revisor,
    no_revisor_ia,
    no_incrementar_tentativa,
    MAX_TENTATIVAS,
)
from interacao_ia_faq import humanizar_faq


def _par(pergunta: str, resposta: str) -> dict:
    return {"pergunta": pergunta, "resposta": resposta}


class _FakeModelo:
    """Substitui o ChatOpenAI inteiro (não dá pra sobrescrever só o método
    ".invoke" de uma instância pydantic — ChatOpenAI bloqueia atribuir
    atributo que não é um field declarado). `resposta_ou_funcao` pode ser
    uma string fixa (.content) ou uma função(prompt, **kwargs) -> string."""

    def __init__(self, resposta_ou_funcao):
        self._resposta_ou_funcao = resposta_ou_funcao
        self.chamadas = []

    def invoke(self, prompt, **kwargs):
        self.chamadas.append(prompt)
        conteudo = (
            self._resposta_ou_funcao(prompt, **kwargs)
            if callable(self._resposta_ou_funcao)
            else self._resposta_ou_funcao
        )
        resposta = type("_Resposta", (), {"content": conteudo})()
        return resposta


def _state(perguntas: list, foco: str = "geral", quantidade_perguntas: int = None, **extra) -> dict:
    base = {
        "perguntas_humanizadas": perguntas,
        "foco": foco,
        "quantidade_perguntas": quantidade_perguntas if quantidade_perguntas is not None else len(perguntas),
    }
    base.update(extra)
    return base


# --- quantidade de perguntas -------------------------------------------------

def test_quantidade_certa_nao_reprova():
    perguntas = [_par("P1", "R1"), _par("P2", "R2")]
    motivos = _checar_regras(_state(perguntas, quantidade_perguntas=2))
    assert not any("esperado exatamente" in m for m in motivos)


def test_quantidade_a_menos_reprova():
    perguntas = [_par("P1", "R1")]
    motivos = _checar_regras(_state(perguntas, quantidade_perguntas=3))
    assert any("esperado exatamente 3" in m for m in motivos)


def test_quantidade_a_mais_reprova():
    perguntas = [_par("P1", "R1"), _par("P2", "R2"), _par("P3", "R3")]
    motivos = _checar_regras(_state(perguntas, quantidade_perguntas=2))
    assert any("esperado exatamente 2" in m for m in motivos)


# --- respeito ao foco (palavra-chave) ---------------------------------------

def test_foco_geral_aceita_qualquer_assunto():
    perguntas = [
        _par("Posso levar meu pet?", "Não, animais não são permitidos."),
        _par("Como faço pra comprar minha passagem?", "Pelo site ou app da Buser."),
    ]
    motivos = _checar_regras(_state(perguntas, foco="geral"))
    assert not any("foge do foco" in m for m in motivos)


def test_foco_compra_reprova_pergunta_de_regras():
    perguntas = [
        _par("Como faço pra comprar minha passagem?", "Pelo site ou app da Buser."),
        _par("Posso levar meu pet na viagem?", "Não, animais não são permitidos nessa linha."),
    ]
    motivos = _checar_regras(_state(perguntas, foco="compra"))
    assert any("foge do foco 'compra'" in m for m in motivos)


def test_foco_compra_nao_reprova_perguntas_so_de_compra():
    perguntas = [
        _par("Como faço pra comprar minha passagem?", "Pelo site ou app da Buser."),
        _par("Posso cancelar minha compra?", "Sim, o cancelamento é gratuito dentro do prazo."),
    ]
    motivos = _checar_regras(_state(perguntas, foco="compra"))
    assert not any("foge do foco" in m for m in motivos)


def test_foco_regras_reprova_pergunta_de_compra():
    perguntas = [
        _par("Qual o limite de bagagem?", "Até 30 kg de mala despachada."),
        _par("Como faço pra comprar minha passagem?", "Pelo site ou app da Buser."),
    ]
    motivos = _checar_regras(_state(perguntas, foco="regras"))
    assert any("foge do foco 'regras'" in m for m in motivos)


def test_foco_compra_nao_reprova_mencao_solta_a_embarque():
    # Caso real testado ao vivo: uma resposta de cancelamento/remarcação
    # menciona "embarque" só pra marcar o prazo ("até 3 horas antes do
    # embarque") — isso não é uma pergunta sobre REGRAS de embarque, é
    # compra normal, e não pode reprovar por causa dessa palavra solta.
    perguntas = [
        _par(
            "É possível remarcar ou cancelar minha passagem?",
            "Sim, você pode remarcar ou cancelar online até 3 horas antes do embarque.",
        ),
    ]
    motivos = _checar_regras(_state(perguntas, foco="compra"))
    assert not any("foge do foco" in m for m in motivos)


def test_foco_regras_nao_reprova_mencao_de_pagamento_so_na_resposta():
    # Caso real testado ao vivo: uma resposta sobre bagagem extra menciona
    # "pagamento" e "segurança" só de passagem ("pagamento via QR Code",
    # "por motivos de segurança") — isso não é a resposta fugindo pro
    # assunto de compra, é só vocabulário incidental. Só a PERGUNTA importa.
    perguntas = [
        _par(
            "Qual é o limite de bagagem permitido?",
            "Para bagagem extra, o pagamento pode ser feito via QR Code, "
            "respeitando as normas de segurança e logística do veículo.",
        ),
    ]
    motivos = _checar_regras(_state(perguntas, foco="regras"))
    assert not any("foge do foco" in m for m in motivos)


def test_foco_regras_nao_reprova_mencao_de_cartao_so_na_resposta():
    # Outro caso real: "cartão do Passe Livre" (documento de PCD) contém a
    # palavra "cartão", mas não é "cartão de crédito" (assunto de compra).
    perguntas = [
        _par(
            "Quais são as regras de gratuidade para PCD?",
            "É preciso apresentar o cartão do Passe Livre no embarque.",
        ),
    ]
    motivos = _checar_regras(_state(perguntas, foco="regras"))
    assert not any("foge do foco" in m for m in motivos)


def test_foco_regras_nao_reprova_perguntas_so_de_regras():
    perguntas = [
        _par("Qual o limite de bagagem?", "Até 30 kg de mala despachada."),
        _par("Posso levar meu pet?", "Só animais de apoio, com documentação."),
    ]
    motivos = _checar_regras(_state(perguntas, foco="regras"))
    assert not any("foge do foco" in m for m in motivos)


# --- pergunta "meta" (não é FAQ de verdade) ---------------------------------

def test_pergunta_meta_reprova_mesmo_no_foco_geral():
    perguntas = [
        _par("Posso levar meu pet?", "Não, animais não são permitidos."),
        _par(
            "Onde posso tirar dúvidas sobre minha viagem?",
            "Entre em contato com a empresa pelos canais de atendimento do site.",
        ),
    ]
    motivos = _checar_regras(_state(perguntas, foco="geral"))
    assert any("pergunta \"meta\"" in m for m in motivos)


def test_pergunta_sem_sinal_de_meta_nao_reprova():
    perguntas = [_par("Posso levar meu pet?", "Não, animais não são permitidos.")]
    motivos = _checar_regras(_state(perguntas, foco="geral"))
    assert not any("pergunta \"meta\"" in m for m in motivos)


def test_pergunta_meta_reprova_mesmo_quando_resposta_e_generica():
    # A resposta desse tipo de pergunta costuma ser só encaminhamento — o
    # sinal confiável é a PERGUNTA em si ("como entro em contato"), não
    # precisa de nenhuma frase específica na resposta pra reprovar.
    perguntas = [_par("Como entro em contato com a Expresso JK?", "Veja o site oficial.")]
    motivos = _checar_regras(_state(perguntas, foco="regras"))
    assert any("pergunta \"meta\"" in m for m in motivos)


# --- revisor_ia: sempre chama a API, mesmo pro foco "geral" -----------------
# (foco "geral" não tem assunto pra restringir, mas ainda tem pergunta
# "meta" pra pegar — ver comentário de PROMPT_REVISOR_IA em grafo_faq.py)

def test_revisor_ia_chama_modelo_mesmo_no_foco_geral(monkeypatch):
    fake = _FakeModelo('{"foco_ok": false, "motivos": ["pergunta meta disfarçada"]}')
    monkeypatch.setattr("grafo_faq.modelo", fake)

    resultado = no_revisor_ia({"foco": "geral", "perguntas_humanizadas": [_par("P1", "R1")]})

    assert len(fake.chamadas) == 1
    assert resultado == {"revisao_ia": {"foco_ok": False, "motivos": ["pergunta meta disfarçada"]}}


def test_revisor_ia_chama_modelo_pro_foco_compra(monkeypatch):
    fake = _FakeModelo('{"foco_ok": false, "motivos": ["fala de bagagem"]}')
    monkeypatch.setattr("grafo_faq.modelo", fake)

    resultado = no_revisor_ia({
        "foco": "compra",
        "perguntas_humanizadas": [_par("P1", "R1")],
    })

    assert len(fake.chamadas) == 1
    assert resultado == {"revisao_ia": {"foco_ok": False, "motivos": ["fala de bagagem"]}}


def test_revisor_ia_resposta_nao_json_e_tratada_como_aprovada(monkeypatch):
    monkeypatch.setattr("grafo_faq.modelo", _FakeModelo("isso não é um JSON"))

    resultado = no_revisor_ia({"foco": "regras", "perguntas_humanizadas": [_par("P1", "R1")]})
    assert resultado["revisao_ia"]["foco_ok"] is True


# --- retry / esgotamento (mesmo padrão de grafo_descricao) -------------------

def test_apos_revisor_aprovado_retorna_aprovado():
    assert _apos_revisor({"revisao": {"aprovado": True}, "tentativas": 0}) == "aprovado"


def test_apos_revisor_reprovado_tenta_de_novo_antes_do_teto():
    state = {"revisao": {"aprovado": False, "motivos": ["x"]}, "tentativas": 0}
    assert _apos_revisor(state) == "tentar_de_novo"


def test_apos_revisor_reprovado_esgota_no_teto():
    state = {"revisao": {"aprovado": False, "motivos": ["x"]}, "tentativas": MAX_TENTATIVAS - 1}
    assert _apos_revisor(state) == "esgotado"


def test_apos_revisor_ia_aprovado():
    assert _apos_revisor_ia({"revisao_ia": {"foco_ok": True}, "tentativas": 0}) == "aprovado"


def test_apos_revisor_ia_reprovado_tenta_de_novo():
    assert _apos_revisor_ia({"revisao_ia": {"foco_ok": False}, "tentativas": 0}) == "tentar_de_novo"


def test_decidir_retry_ou_esgotado_bate_com_max_tentativas():
    for i in range(MAX_TENTATIVAS - 1):
        assert _decidir_retry_ou_esgotado({"tentativas": i}) == "tentar_de_novo"
    assert _decidir_retry_ou_esgotado({"tentativas": MAX_TENTATIVAS - 1}) == "esgotado"


def test_motivos_da_reprovacao_soma_determinístico_e_ia():
    state = {
        "revisao": {"aprovado": False, "motivos": ["motivo do determinístico"]},
        "revisao_ia": {"foco_ok": False, "motivos": ["motivo da ia"]},
    }
    motivos = _motivos_da_reprovacao(state)
    assert "motivo do determinístico" in motivos
    assert "motivo da ia" in motivos


def test_no_incrementar_tentativa_soma_um_e_guarda_motivos():
    state = {
        "tentativas": 1,
        "revisao": {"aprovado": False, "motivos": ["falhou"]},
        "revisao_ia": None,
    }
    resultado = no_incrementar_tentativa(state)
    assert resultado["tentativas"] == 2
    assert resultado["motivos_reprovacao"] == ["falhou"]


def test_no_revisor_limpa_revisao_ia_anterior():
    resultado = no_revisor(_state([_par("P1", "R1")], foco="geral", quantidade_perguntas=1))
    assert resultado["revisao"]["aprovado"] is True
    assert resultado["revisao_ia"] is None


# --- humanizar_faq (interacao_ia_faq.py) ------------------------------------

def test_humanizar_faq_lista_vazia_devolve_vazia():
    assert humanizar_faq([]) == []


def test_humanizar_faq_usa_resposta_do_modelo_quando_contagem_bate(monkeypatch):
    resposta = '[{"pergunta": "P1 reescrita", "resposta": "R1 reescrita"}]'
    monkeypatch.setattr("interacao_ia_faq.modelo", _FakeModelo(resposta))

    resultado = humanizar_faq([_par("P1", "R1")])
    assert resultado == [_par("P1 reescrita", "R1 reescrita")]


def test_humanizar_faq_com_contagem_diferente_devolve_original(monkeypatch):
    # Simula a humanização "quebrando" a contagem (juntou dois pares em um
    # só) — mais seguro devolver o original do que arriscar o revisor
    # reprovar por uma quantidade errada que a própria humanização causou.
    resposta = '[{"pergunta": "Só uma pergunta juntada", "resposta": "R"}]'
    monkeypatch.setattr("interacao_ia_faq.modelo", _FakeModelo(resposta))

    original = [_par("P1", "R1"), _par("P2", "R2")]
    resultado = humanizar_faq(original)
    assert resultado == original


def test_humanizar_faq_com_erro_no_modelo_devolve_original(monkeypatch):
    def _explode(*a, **k):
        raise RuntimeError("rate limit")

    monkeypatch.setattr("interacao_ia_faq.modelo", _FakeModelo(_explode))

    original = [_par("P1", "R1")]
    assert humanizar_faq(original) == original
