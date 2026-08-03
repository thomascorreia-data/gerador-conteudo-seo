"""
Liga a API e já abre a interface no navegador — um comando só.

Uso:
    python start.py

Isso substitui rodar "uvicorn api.app:app --reload --port 8000" manualmente
e depois abrir o navegador na mão. Pra encerrar tudo, é só apertar Ctrl+C
nesta janela do terminal (isso derruba a API também).

Requisitos (mesmos de antes):
    pip install fastapi uvicorn
"""

import subprocess
import sys
import time
import webbrowser

PORTA = 8000
URL_APP = f"http://127.0.0.1:{PORTA}/interface/gerador-json.html"


def main():
    print(f"Iniciando a API em http://127.0.0.1:{PORTA} ...")

    # Sobe o uvicorn como um processo separado (sem --reload: reload é útil
    # em desenvolvimento ativo do código da API, mas causa recarregamentos
    # e reaberturas de aba indesejadas nesse uso do dia a dia).
    processo = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.app:app", "--port", str(PORTA)]
    )

    try:
        # Dá um tempo para a API terminar de subir antes de abrir o navegador.
        time.sleep(2)
        print(f"Abrindo {URL_APP} no navegador...")
        webbrowser.open(URL_APP)

        print("\nTudo rodando. Pressione Ctrl+C aqui para encerrar.\n")
        processo.wait()  # mantém o script vivo enquanto a API estiver de pé

    except KeyboardInterrupt:
        print("\nEncerrando a API...")
        processo.terminate()
        processo.wait()
        print("Encerrado.")


if __name__ == "__main__":
    main()