"""
Testes de interacao_ia_descricao.py — foco na lógica de cidade_texto em
gerar_texto_bruto(), que decide como o prompt de "feriado" descreve a
abrangência (nacional/estadual/municipal) pro modelo.
"""

from interacao_ia_descricao import gerar_texto_bruto


class _FakeModelo:
    def __init__(self):
        self.chamadas = []

    def invoke(self, prompt, **kwargs):
        self.chamadas.append(prompt)
        return type("_Resposta", (), {"content": "texto gerado de teste"})()


def _gerar(monkeypatch, **kwargs):
    fake = _FakeModelo()
    monkeypatch.setattr("interacao_ia_descricao.modelo", fake)
    gerar_texto_bruto(
        categoria="feriado",
        entidade="Feriado de Teste",
        fontes={"Wikipedia": {"conteudo": "algum conteúdo", "erro": None}},
        tom="informativo",
        **kwargs,
    )
    return fake.chamadas[0]


def test_municipal_com_cidade_cita_a_cidade(monkeypatch):
    prompt = _gerar(monkeypatch, cidade="Porto Alegre", abrangencia_feriado="municipal")
    assert "Porto Alegre" in prompt
    assert "feriado nacional" not in prompt.lower()


def test_estadual_sem_cidade_cita_o_estado_nao_nacional(monkeypatch):
    # Caso real que motivou isso: "Nossa Senhora da Apresentação" é
    # estadual (RN) mas sem cidade conhecida -- antes disso, caía no
    # fallback de "feriado nacional" errado.
    prompt = _gerar(monkeypatch, estado="RN", abrangencia_feriado="estadual")
    assert "RN" in prompt
    assert "não um feriado nacional" in prompt.lower()


def test_municipal_ou_estadual_sem_local_conhecido_nao_afirma_nacional(monkeypatch):
    prompt = _gerar(monkeypatch, abrangencia_feriado="municipal")
    assert "NÃO descreva como" in prompt or "não é nacional" in prompt.lower()
    assert "este é um feriado nacional" not in prompt.lower()


def test_nacional_sem_cidade_nem_estado(monkeypatch):
    prompt = _gerar(monkeypatch, abrangencia_feriado="nacional")
    assert "este é um feriado nacional" in prompt.lower()


def test_sem_abrangencia_nenhuma_informada_cai_no_padrao_nacional(monkeypatch):
    # Compatibilidade com chamadas antigas que não passam
    # abrangencia_feriado nenhuma (ex: testes/fluxos que só setam cidade).
    prompt = _gerar(monkeypatch)
    assert "este é um feriado nacional" in prompt.lower()
