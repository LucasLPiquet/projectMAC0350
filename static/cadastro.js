async function enviarUsuario() {
    const dados = {
        nome: document.getElementById('nome').value,
        senha: document.getElementById('senha').value
    };

    const resposta = await fetch('/usuarios', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(dados)
    });

    if (resposta.ok) {
        const resultado = await resposta.json();
        alert("Usuário " + resultado.nome + " criado!");
        window.location.href = "/";
    } else {
        alert("Erro ao enviar!");
    }
}