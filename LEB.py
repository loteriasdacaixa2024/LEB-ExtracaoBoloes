# -*- coding: utf-8 -*-
"""LEB — painel local da extração de bolões.

Não há serviço do Windows: o extrator abre o Edge na sessão de quem está
no computador e espera o código do e-mail. Um serviço não tem essa tela.
"""
from __future__ import annotations

import os
import subprocess
import threading

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA_IMG = os.path.join(RAIZ, "static", "img")
BAT_EXTRATOR = os.path.join(RAIZ, "iniciar_servidores_boloes.bat")
PORTA = int(os.environ.get("LEB_PORT") or "8088")
HOST = os.environ.get("LEB_HOST") or "127.0.0.1"

SIGLA = "LEB"
NOME = "Extração de Bolões"
NODE = "LEB"

_lock = threading.Lock()
_estado = {
    "mensagem": "Aguardando neste computador.",
    "nivel": "",
}


def criar_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    @app.context_processor
    def _marca():
        return {
            "sigla": SIGLA,
            "nome": NOME,
            "node": NODE,
            "pode_iniciar": _cliente_local(),
        }

    @app.get("/")
    def inicio():
        return render_template("painel.html")

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(PASTA_IMG, "Faveicon.ico")

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "node": NODE, "porta": PORTA})

    @app.post("/extrator/iniciar")
    def iniciar_extrator():
        if not _cliente_local():
            return jsonify({
                "ok": False,
                "nivel": "erro",
                "mensagem": (
                    "A extração só abre neste computador. "
                    "Use o atalho LEB da área de trabalho ou http://127.0.0.1:8088/"
                ),
            }), 403
        if not os.path.isfile(BAT_EXTRATOR):
            return jsonify({
                "ok": False,
                "nivel": "erro",
                "mensagem": "Não encontrei iniciar_servidores_boloes.bat.",
            }), 500
        with _lock:
            # O .bat e a unica janela. Ele nao abre o Windows Terminal nem o servidor.
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "Extrator de Boloes", BAT_EXTRATOR],
                cwd=RAIZ,
                shell=False,
            )
            _estado["nivel"] = "sucesso"
            _estado["mensagem"] = (
                "Uma janela do extrator foi aberta neste computador.\n"
                "1. Digite o código do e-mail no Edge\n"
                "2. Clique em Enviar\n"
                "3. No menu, digite C"
            )
            resposta = {"ok": True, **_estado}
        return jsonify(resposta)

    return app


def _cliente_local() -> bool:
    encaminhado = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = encaminhado or (request.remote_addr or "")
    return ip in {"127.0.0.1", "::1"}


app = criar_app()


if __name__ == "__main__":
    print(f"{NODE}  http://127.0.0.1:{PORTA}/")
    print("Público  https://marciofernandomaia.com.br/leb/")
    app.run(host=HOST, port=PORTA, debug=False, threaded=True, use_reloader=False)
