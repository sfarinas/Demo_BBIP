// O script precisa ser executado após o carregamento do DOM
document.addEventListener('DOMContentLoaded', function() {
    const alturaInput = document.getElementById('altura-canvas');
    const aplicarBtn = document.getElementById('aplicar-altura-btn');
    const networkContainer = document.getElementById('network-diagram');
    
    // Obtém o canvas que está dentro do container do diagrama
    function getCanvasElement() {
        return networkContainer.querySelector('canvas');
    }

    // Função para aplicar a altura
    function aplicarAltura() {
        const novaAltura = alturaInput.value;
        const canvas = getCanvasElement();
        if (canvas) {
            // Aplica a nova altura ao estilo do elemento canvas
            canvas.style.height = novaAltura + 'px';

            // NOVO: Acessar o objeto 'network' para forçar o redraw
            // É necessário que o objeto 'network' esteja disponível globalmente
            // ou seja exposto de alguma forma. A forma mais simples aqui
            // é assumir que ele está em window.network.
            if (window.network) {
                // A biblioteca Vis.js tem um método para redimensionar.
                // Usamos 'redraw' para forçar a atualização da visualização.
                window.network.redraw();
                // Alternativamente, network.fit() também pode ser usado para ajustar a visualização.
            } else {
                console.warn('Objeto Vis.js network não encontrado para redimensionamento.');
            }
        } else {
            console.error('Elemento canvas não encontrado no container do diagrama.');
        }
    }
    
    // Ouve o clique do botão
    if (aplicarBtn) {
        aplicarBtn.addEventListener('click', aplicarAltura);
    }

    // Opcional: Ouve a tecla Enter no campo de texto para aplicar a altura
    if (alturaInput) {
        alturaInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault(); // Evita a submissão do formulário se houver um
                aplicarAltura();
            }
        });
    }

    // Aplica a altura inicial definida no input ao carregar a página
    window.addEventListener('load', () => {
        // Encontra o canvas após o Vis.js ter renderizado
        setTimeout(aplicarAltura, 500); // Um pequeno delay para garantir que o canvas foi criado
    });
});
