document.addEventListener('DOMContentLoaded', function() {
    const gerenciaSelect = document.getElementById('gerencia2_id');
    const otdrCheckboxDiv = document.getElementById('otdr_checkbox_div');
    const otdrKmInputDiv = document.getElementById('otdr_km_input_div');
    const otdrCheckbox = document.getElementById('teste_otdr_em_curso');
    const otdrKmInput = document.getElementById('km_rompimento_otdr');

    // Mapeamento de IDs de gerência para nomes (você pode precisar ajustar esses IDs/nomes)
    // Esses IDs vêm do seu banco de dados, então é bom ter gerências de exemplo cadastradas.
    // Ex: Se NOKIA for ID 1, CISCO 2, HUAWEI_U2000 3, CISCO-EPNM 4
    const gerenciasOTDRRelevant = [
        'HUAWEI_U2000', // Exemplo: Gerência 3
        'CISCO-EPNM'    // Exemplo: Gerência 4
        // Adicione outras gerências relevantes que ativam a opção OTDR
    ];

    function toggleOtdrFields() {
        const selectedGerenciaId = gerenciaSelect.value;
        
        // Obter o nome da gerência selecionada para verificar se está na lista de "OTDR Relevant"
        // Esta parte é um pouco mais complexa em JS puro sem saber todos os nomes/IDs.
        // Uma forma robusta seria passar um dicionário gerencia_id -> nome_gerencia do Flask para o JS.
        // Por enquanto, vamos assumir que você terá os nomes correspondentes para testar.
        
        // Simulação de como você obteria o nome da gerência. 
        // No mundo real, você passaria `gerencias_map = {id: nome}` do Flask para o JS.
        const selectedOption = gerenciaSelect.options[gerenciaSelect.selectedIndex];
        const selectedGerenciaName = selectedOption ? selectedOption.text.toUpperCase() : '';

        // Mostra a div do checkbox OTDR se a gerência selecionada está na lista de relevância
        if (gerenciasOTDRRelevant.includes(selectedGerenciaName)) {
            otdrCheckboxDiv.style.display = 'block';
        } else {
            otdrCheckboxDiv.style.display = 'none';
            otdrCheckbox.checked = false; // Desmarca se a opção for escondida
        }

        // Mostra o campo de KM se o checkbox OTDR estiver marcado E visível
        if (otdrCheckbox.checked && otdrCheckboxDiv.style.display === 'block') {
            otdrKmInputDiv.style.display = 'block';
            otdrKmInput.setAttribute('required', 'required'); // Torna o campo obrigatório
        } else {
            otdrKmInputDiv.style.display = 'none';
            otdrKmInput.removeAttribute('required'); // Remove a obrigatoriedade
            otdrKmInput.value = ''; // Limpa o valor
        }
    }

    // Adiciona event listeners para mudanças nos selects/checkboxes
    if (gerenciaSelect) {
        gerenciaSelect.addEventListener('change', toggleOtdrFields);
    }
    if (otdrCheckbox) {
        otdrCheckbox.addEventListener('change', toggleOtdrFields);
    }

    // Chama a função uma vez no carregamento da página para definir o estado inicial
    toggleOtdrFields();
});
