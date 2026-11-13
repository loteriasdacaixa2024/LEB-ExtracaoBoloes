(function () {
  const form = document.getElementById("form-extrator");
  const botao = document.getElementById("abrir");
  const painel = document.getElementById("painel");
  const mensagem = document.getElementById("mensagem");
  const raiz = window.APP_ROOT || "";

  function pintar(dados) {
    mensagem.textContent = dados.mensagem || "Aguardando neste computador.";
    painel.className = "status" + (dados.nivel ? " " + dados.nivel : "");
  }

  form.addEventListener("submit", async function (evento) {
    evento.preventDefault();
    if (botao.disabled) return;
    botao.disabled = true;
    botao.textContent = "Abrindo...";
    try {
      const resposta = await fetch(raiz + "/extrator/iniciar", { method: "POST" });
      const dados = await resposta.json();
      pintar(dados);
    } catch (erro) {
      pintar({
        nivel: "erro",
        mensagem: "Sem comunicação com o LEB.",
      });
    }
    botao.disabled = false;
    botao.textContent = "Abrir extrator neste PC";
  });
})();
