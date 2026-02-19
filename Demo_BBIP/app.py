from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import database
import datetime
import pytz # Importe pytz
import json
from flask_moment import Moment
import sqlite3
import debg
import csv
import io

SERVER_MODE_ENGINEERING = False

LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo') # Exemplo para fuso horário de Brasília/São Paulo

# --- CORREÇÃO 1: Removido erro de digitação "Fapp" ---
app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True  # <-- FORÇA A LEITURA DO HTML
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # <-- FORÇA A LEITURA DE JS/CSS
# Chave secreta para proteger sessões e mensagens flash.
# MUITO IMPORTANTE: Altere para uma string complexa e única em produção.
app.secret_key = 'sua_chave_secreta_muito_segura_e_longa_aqui_1234567890abcdefGHIKLMNO_NOVA'

moment = Moment(app) # Inicializa Flask-Moment com a sua aplicação Flask

# --- FUNÇÃO AUXILIAR PARA VALIDAR NOMES ---
def is_valid_name(name):
    """Verifica se o nome contém caracteres inválidos."""
    invalid_chars = [':', '<', '>', '"']
    if any(char in name for char in invalid_chars):
        return False
    return True

# --- Custom Jinja2 Filters for Datetime ---
def _jinja2_filter_strptime(value, format_string):
    """Parses a string into a datetime object."""
    return datetime.datetime.strptime(value, format_string)

def _jinja2_filter_strftime(value, format_string):
    """Formats a datetime object into a string."""
    return value.strftime(format_string)

app.jinja_env.filters['strptime'] = _jinja2_filter_strptime
app.jinja_env.filters['strftime'] = _jinja2_filter_strftime
# ----------------------------------------



# --- INICIALIZAÇÃO DO BANCO de DADOS ---
database.init_db()
# ----------------------------------------

# Lista de gerências que podem ter OTDR relevante (definida globalmente)
GERENCIAS_OTDR_RELEVANTES = ['HUAWEI_U2000', 'CISCO-EPNM']


# ... (depois da sua função _jinja2_filter_strftime)

@app.template_filter('utc_to_local')
def utc_to_local(utc_dt_str):
    """Converte uma string de data/hora UTC do DB para o fuso local."""
    if not utc_dt_str:
        return ""
    try:
        # 1. Converte a string do DB (que está em UTC) para um objeto datetime
        utc_dt = datetime.datetime.strptime(utc_dt_str, '%Y-%m-%d %H:%M:%S')
        # 2. Informa ao objeto que ele é UTC
        utc_dt = pytz.utc.localize(utc_dt)
        # 3. Converte para o fuso horário local (America/Sao_Paulo)
        local_dt = utc_dt.astimezone(LOCAL_TIMEZONE)
        # 4. Formata
        return local_dt.strftime('%d/%m/%Y %H:%M:%S')
    except Exception as e:
        print(f"Erro ao converter data: {e}")
        return utc_dt_str # Retorna a string original em caso de erro


@app.route('/', methods=['GET', 'POST'])
def index():
    tipos_alarmes = database.get_all_tipos_alarmes()
    gerencias = database.get_all_gerencias()
    detentores_site = database.get_all_detentores_site()
    aneis = database.get_all_aneis()
    estados_enlace = database.get_all_estados_enlace()
    
    # --- NOVO: BUSCA OS TIPOS DE FALHA NO BANCO (PARA O DROPDOWN DINÂMICO) ---
    try:
        tipos_falhas_circuito = database.get_all_tipos_falha_circuito()
    except AttributeError:
        tipos_falhas_circuito = [] # Segurança caso a função não exista ainda
    # -------------------------------------------------------------------------

    prev_data = {}
    prefill_element_name = request.args.get('prefill_element_name')
    
    if request.method == 'GET':
        session.pop('final_quick_add_data', None)
        
        if prefill_element_name:
            prev_data['nome_elemento1'] = prefill_element_name
            element_details = database.get_element_details_by_name(prefill_element_name)
            if element_details and element_details.get('estado_atual_id'):
                prev_data['estado_origem_id_select'] = str(element_details['estado_atual_id'])
        else:
            prev_data = {}
    elif 'final_quick_add_data' in session:
        data_from_session = session['final_quick_add_data']
        prev_data['nome_elemento1'] = data_from_session.get('nome_elemento1', '')
        prev_data['nome_elemento2'] = data_from_session.get('nome_elemento2', '')
        prev_data['gerencia_id_comum'] = str(data_from_session.get('elemento1_gerencia_id', ''))
        prev_data['anel_id_select'] = str(data_from_session.get('anel_id', ''))
        prev_data['accid_lc_comum'] = data_from_session.get('accid_lc_comum', '')
        prev_data['longa_distancia_comum'] = 'on' if data_from_session.get('elemento1_longa_distancia') == 1 else ''
        prev_data['swap_fibra_info'] = data_from_session.get('swap_fibra_info', '')
        prev_data['tipo_alarme1_id_select'] = str(data_from_session.get('tipo_alarme1_id', ''))
        prev_data['tipo_alarmes2_ids_select'] = [str(x) for x in data_from_session.get('tipo_alarmes2_ids', [])]
        prev_data['estado_origem_id_select'] = str(data_from_session.get('estado_origem_id', ''))
        prev_data['estado_destino_id_select'] = str(data_from_session.get('estado_destino_id', ''))
        prev_data['teste_otdr_em_curso'] = 'on' if data_from_session.get('teste_otdr_em_curso') == 1 else ''
        prev_data['km_rompimento_otdr'] = data_from_session.get('km_rompimento_otdr', '')
        prev_data['info_extra'] = data_from_session.get('info_extra', '')
        prev_data['rascunho_texto'] = data_from_session.get('rascunho_texto', '')
    
    if prev_data.get('nome_elemento1') and not (prev_data.get('estado_origem_id_select') or prev_data.get('novo_estado_origem_nome')):
        element1_details = database.get_element_details_by_name(prev_data['nome_elemento1'])
        if element1_details and element1_details.get('estado_atual_id'):
            prev_data['estado_origem_id_select'] = str(element1_details['estado_atual_id'])

    if prev_data.get('nome_elemento2') and not (prev_data.get('estado_destino_id_select') or prev_data.get('novo_estado_destino_nome')):
        element2_details = database.get_element_details_by_name(prev_data['nome_elemento2'])
        if element2_details and element2_details.get('estado_atual_id'):
            prev_data['estado_destino_id_select'] = str(element2_details['estado_atual_id'])

    if request.method == 'POST':
        rascunho_texto = request.form.get('rascunho_texto', '').strip()

        # --- APLICAÇÃO DA SANITIZAÇÃO ---
        novo_tipo_alarme1_nome = sanitize_text(request.form.get('novo_tipo_alarme1_nome', ''))
        novo_anel_nome = sanitize_text(request.form.get('novo_anel_nome', ''))
        accid_lc_comum = sanitize_text(request.form.get('accid_lc_comum', ''))
        swap_fibra_info = sanitize_text(request.form.get('swap_fibra_info', ''))
        novo_tipo_alarme2_nome = sanitize_text(request.form.get('novo_tipo_alarme2_nome', ''))
        novo_estado_origem_nome = sanitize_text(request.form.get('novo_estado_origem_nome', ''))
        novo_estado_destino_nome = sanitize_text(request.form.get('novo_estado_destino_nome', ''))
        
        nome_elemento1 = sanitize_text(request.form['nome_elemento1'])
        nome_elemento2 = sanitize_text(request.form['nome_elemento2'])
        
        km_rompimento_otdr = request.form.get('km_rompimento_otdr', '').strip()
        info_extra = request.form.get('info_extra', '').strip()

        tipo_alarme1_id_selected = request.form.get('tipo_alarme1_id_select')
        
        final_tipo_alarme1_id = None
        if novo_tipo_alarme1_nome:
            final_tipo_alarme1_id, _ = database.get_or_create_tipo_alarme(novo_tipo_alarme1_nome, equipe_responsavel=None, eh_abertura_enlace_trigger=0)
        elif tipo_alarme1_id_selected:
            final_tipo_alarme1_id = int(tipo_alarme1_id_selected)

        gerencia_id_comum = request.form['gerencia_id_comum']
        anel_id_selected = request.form.get('anel_id_select')
        
        # --- Validação de Caracteres ---
        if not is_valid_name(novo_anel_nome) or not is_valid_name(accid_lc_comum) or not is_valid_name(swap_fibra_info):
            flash('Erro: Os campos de Anel, ACCID/LC ou Swap de Fibra contêm caracteres inválidos (:, <, >, ").', 'danger')
            return render_template('index.html', 
                                   tipos_alarmes=database.get_all_tipos_alarmes(), 
                                   gerencias=database.get_all_gerencias(), 
                                   detentores_site=database.get_all_detentores_site(),
                                   aneis=database.get_all_aneis(),
                                   estados_enlace=database.get_all_estados_enlace(),
                                   tipos_falhas_circuito=tipos_falhas_circuito, # <--- ADICIONADO
                                   prev_data=request.form,
                                   database=database,
                                   now=datetime.datetime.now())
        
        if not is_valid_name(nome_elemento1) or not is_valid_name(nome_elemento2):
            flash('Erro: O nome dos elementos não pode conter os caracteres :, <, >, " .', 'danger')
            return render_template('index.html', 
                                   tipos_alarmes=database.get_all_tipos_alarmes(), 
                                   gerencias=database.get_all_gerencias(), 
                                   detentores_site=database.get_all_detentores_site(),
                                   aneis=database.get_all_aneis(),
                                   estados_enlace=database.get_all_estados_enlace(),
                                   tipos_falhas_circuito=tipos_falhas_circuito, # <--- ADICIONADO
                                   prev_data=request.form,
                                   database=database,
                                   now=datetime.datetime.now())
        
        longa_distancia_comum = 1 if request.form.get('longa_distancia_comum') == 'on' else 0
        
        final_anel_id = None
        if novo_anel_nome:
            final_anel_id, _ = database.get_or_create_anel(novo_anel_nome)
        elif anel_id_selected:
            final_anel_id = int(anel_id_selected)

        tipo_alarmes2_ids_selected_str = request.form.getlist('tipo_alarmes2_ids_select')
        
        final_tipo_alarmes2_ids = []
        if novo_tipo_alarme2_nome:
            new_type_id, _ = database.get_or_create_tipo_alarme(novo_tipo_alarme2_nome, equipe_responsavel=None, eh_abertura_enlace_trigger=0)
            if new_type_id:
                final_tipo_alarmes2_ids.append(new_type_id)
        final_tipo_alarmes2_ids.extend([int(id) for id in tipo_alarmes2_ids_selected_str if id.isdigit()])

        estado_origem_id_selected = request.form.get('estado_origem_id_select')
        final_estado_origem_id = None
        if novo_estado_origem_nome:
            final_estado_origem_id, _ = database.get_or_create_estado_enlace(novo_estado_origem_nome)
        elif estado_origem_id_selected:
            final_estado_origem_id = int(estado_origem_id_selected)

        estado_destino_id_selected = request.form.get('estado_destino_id_select')
        final_estado_destino_id = None
        if novo_estado_destino_nome:
            final_estado_destino_id, _ = database.get_or_create_estado_enlace(novo_estado_destino_nome)
        elif estado_destino_id_selected:
            final_estado_destino_id = int(estado_destino_id_selected)

        teste_otdr_em_curso = 1 if request.form.get('teste_otdr_em_curso') == 'on' else 0
        report_type = request.form.get('report_type', 'padrao')

        # --- Validações de Obrigatoriedade ---
        if not final_tipo_alarme1_id:
            flash('Por favor, selecione um Tipo de Alarme para o Elemento 1 OU digite um nome para criar um novo.', 'danger')
            return render_template('index.html', tipos_alarmes=tipos_alarmes, gerencias=gerencias, detentores_site=detentores_site, aneis=aneis, estados_enlace=estados_enlace, tipos_falhas_circuito=tipos_falhas_circuito, prev_data=request.form, database=database, now=datetime.datetime.now())
        if not nome_elemento1 or not nome_elemento2 or not gerencia_id_comum or not final_anel_id:
            flash('Por favor, preencha todos os campos obrigatórios (Elementos, Gerência, Anel).', 'danger')
            return render_template('index.html', tipos_alarmes=tipos_alarmes, gerencias=gerencias, detentores_site=detentores_site, aneis=aneis, estados_enlace=estados_enlace, tipos_falhas_circuito=tipos_falhas_circuito, prev_data=request.form, database=database, now=datetime.datetime.now())
        if nome_elemento1 == nome_elemento2:
            flash('Erro: O Elemento Vizinho não pode ter o mesmo nome do Elemento 1.', 'danger')
            return render_template('index.html', tipos_alarmes=tipos_alarmes, gerencias=gerencias, detentores_site=detentores_site, aneis=aneis, estados_enlace=estados_enlace, tipos_falhas_circuito=tipos_falhas_circuito, prev_data=request.form, database=database, now=datetime.datetime.now())
        if not final_tipo_alarmes2_ids:
            flash('Por favor, selecione ao menos um Tipo de Alarme para o Elemento Vizinho OU digite um nome para criar um novo.', 'danger')
            return render_template('index.html', tipos_alarmes=tipos_alarmes, gerencias=gerencias, detentores_site=detentores_site, aneis=aneis, estados_enlace=estados_enlace, tipos_falhas_circuito=tipos_falhas_circuito, prev_data=request.form, database=database, now=datetime.datetime.now())
        if teste_otdr_em_curso and not km_rompimento_otdr:
            flash('Se "Teste OTDR em curso" estiver marcado, o "KM do Rompimento" é obrigatório.', 'danger')
            return render_template('index.html', tipos_alarmes=tipos_alarmes, gerencias=gerencias, detentores_site=detentores_site, aneis=aneis, estados_enlace=estados_enlace, tipos_falhas_circuito=tipos_falhas_circuito, prev_data=request.form, database=database, now=datetime.datetime.now())

        # Nome Curto
        nome_elemento1_curto = nome_elemento1[:17]
        nome_elemento2_curto = nome_elemento2[:17]

        # Prepara dados para etapa 2
        event_data = {
            'nome_elemento1': nome_elemento1,
            'nome_elemento1_curto': nome_elemento1_curto,
            'elemento1_gerencia_id': int(gerencia_id_comum),
            'elemento1_longa_distancia': longa_distancia_comum,
            'anel_id': final_anel_id,
            'tipo_alarme1_id': final_tipo_alarme1_id,
            'nome_elemento2': nome_elemento2,
            'nome_elemento2_curto': nome_elemento2_curto,
            'elemento2_gerencia_id': int(gerencia_id_comum),
            'elemento2_longa_distancia': longa_distancia_comum,
            'accid_lc_comum': accid_lc_comum,
            'swap_fibra_info': swap_fibra_info,
            'tipo_alarmes2_ids': final_tipo_alarmes2_ids,
            'estado_origem_id': final_estado_origem_id,
            'estado_destino_id': final_estado_destino_id,
            'teste_otdr_em_curso': teste_otdr_em_curso,
            'km_rompimento_otdr': km_rompimento_otdr,
            'info_extra': info_extra,
            'rascunho_texto': rascunho_texto,
            'report_type': report_type
        }
        session['final_quick_add_data'] = event_data
        
        flash('Dados de Elementos e Alarmes salvos. Finalize o relatório de evento.', 'success')
        return redirect(url_for('quick_add_step2_evento'))

    return render_template('index.html',
                           tipos_alarmes=tipos_alarmes, 
                           gerencias=gerencias, 
                           detentores_site=detentores_site,
                           aneis=aneis,
                           estados_enlace=estados_enlace,
                           
                           tipos_falhas_circuito=tipos_falhas_circuito, # <--- ADICIONADO
                           
                           prev_data=prev_data,
                           database=database,
                           now=datetime.datetime.now())



# --- Rota para a nova Etapa 2 (Finalização do Evento) ---
# EM app.py, SUBSTITUA A FUNÇÃO INTEIRA POR ESTA:



# --- Rotas de Cadastro Individual (EXISTENTES, com Adaptações para novos campos) ---

@app.route('/cadastrar_gerencia', methods=['GET', 'POST'])
def cadastrar_gerencia():
    """Permite cadastrar novas gerências de rede (e.g., NOKIA, CISCO)."""
    if request.method == 'POST': # ADICIONADO: Verifica se o método é POST
        nome_gerencia = request.form['nome_gerencia'] # ADICIONADO: Coleta nome_gerencia do formulário
        if database.add_gerencia(nome_gerencia):
            flash(f'Gerência "{nome_gerencia}" cadastrada com sucesso!', 'success')
            return redirect(url_for('consultar_gerencias'))
        else: # CORRIGIDO: Indentação do else
            flash(f'Erro: Gerência "{nome_gerencia}" já existe ou dados inválidos.', 'danger')
    return render_template('cadastrar_gerencia.html', now=datetime.datetime.now())



# @app.route('/cadastrar_anel', methods=['GET', 'POST']) removido para melhorar cadastrar_vizinho.html

# ATUALIZADO PARA FAZER REFERENCIA DE ALARME PAI E FILHO
@app.route('/cadastrar_tipo_alarme', methods=['GET', 'POST'])
@app.route('/editar_tipo_alarme/<int:tipo_alarme_id>', methods=['GET', 'POST'])
def cadastrar_ou_editar_tipo_alarme(tipo_alarme_id=None):
    tipo_alarme = None
    # Busca todos os tipos de alarme para popular o dropdown de "pai"
    todos_tipos_alarmes = database.get_all_tipos_alarmes()

    if tipo_alarme_id:
        tipo_alarme = database.get_tipo_alarme_by_id(tipo_alarme_id)
        if not tipo_alarme:
            flash('Tipo de Alarme não encontrado.', 'danger')
            return redirect(url_for('consultar_tipos_alarmes'))
        # Remove o próprio alarme da lista de possíveis pais para evitar auto-referência
        todos_tipos_alarmes = [ta for ta in todos_tipos_alarmes if ta['id'] != tipo_alarme_id]

    if request.method == 'POST':
        nome_tipo_alarme = request.form['nome_tipo_alarme']
        equipe_responsavel = request.form.get('equipe_responsavel')
        eh_abertura_enlace_trigger = 1 if request.form.get('eh_abertura_enlace_trigger') == 'on' else 0
        tipo_alarme_pai_id = request.form.get('tipo_alarme_pai_id')

        # Converte para int ou None
        final_pai_id = int(tipo_alarme_pai_id) if tipo_alarme_pai_id else None

        if not nome_tipo_alarme or not equipe_responsavel:
            flash('Erro: Nome do tipo de alarme e equipe responsável são obrigatórios.', 'danger')
        else:
            if tipo_alarme_id: # Edição
                if database.update_tipo_alarme(tipo_alarme_id, nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger, final_pai_id):
                    flash(f'Tipo de Alarme "{nome_tipo_alarme}" atualizado com sucesso!', 'success')
                    return redirect(url_for('consultar_tipos_alarmes'))
                else:
                    flash(f'Erro ao atualizar Tipo de Alarme "{nome_tipo_alarme}".', 'danger')
            else: # Cadastro
                if database.add_tipo_alarme(nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger, final_pai_id):
                    flash(f'Tipo de Alarme "{nome_tipo_alarme}" cadastrado com sucesso!', 'success')
                    return redirect(url_for('consultar_tipos_alarmes'))
                else:
                    flash(f'Erro: Tipo de Alarme "{nome_tipo_alarme}" já existe.', 'danger')

    return render_template('cadastrar_tipo_alarme.html', 
                           tipo_alarme=tipo_alarme, 
                           todos_tipos_alarmes=todos_tipos_alarmes, # Passa a lista para o template
                           now=datetime.datetime.now())
    

# Cadastrar e associar Anel junto a funcao
@app.route('/cadastrar_vizinho', methods=['GET', 'POST'])
def cadastrar_vizinho():
    """
    Permite cadastrar/atualizar uma vizinhança, criar/atualizar os elementos
    envolvidos e associá-los a um anel. Funciona como um cadastro rápido
    focado na topologia da rede, sem criar eventos.
    """
    elementos = database.get_all_elementos()
    gerencias = database.get_all_gerencias()
    aneis = database.get_all_aneis()
    estados_enlace = database.get_all_estados_enlace()

    if request.method == 'POST':
        # --- 1. Captura e Validação dos Nomes dos Elementos ---
        nome_elemento1 = request.form.get('nome_elemento1', '').strip()
        nome_elemento2 = request.form.get('nome_elemento2', '').strip()

        if not is_valid_name(nome_elemento1) or not is_valid_name(nome_elemento2):
            flash('Erro: O nome dos elementos não pode conter os caracteres :, <, >, " .', 'danger')
            return render_template('cadastrar_vizinho.html',
                                   elementos=elementos, aneis=aneis, gerencias=gerencias,
                                   estados_enlace=estados_enlace, prev_data=request.form,
                                   now=datetime.datetime.now())

        if not nome_elemento1 or not nome_elemento2 or nome_elemento1 == nome_elemento2:
            flash('Erro: Os nomes dos dois elementos são obrigatórios e não podem ser iguais.', 'danger')
            return redirect(url_for('cadastrar_vizinho'))

        # --- 2. Processamento dos Dados ---
        gerencia_id = request.form.get('gerencia_id')
        longa_distancia = 1 if request.form.get('longa_distancia_comum') == 'on' else 0
        swap_fibra_info = request.form.get('swap_fibra_info', '').strip()
        accid_lc = request.form.get('accid_lc_comum', '').strip() # CORREÇÃO: Captura o ACCID/LC

        estado_origem_id_val = request.form.get('estado_origem_id_select')
        estado_origem_id = int(estado_origem_id_val) if estado_origem_id_val else None

        estado_destino_id_val = request.form.get('estado_destino_id_select')
        estado_destino_id = int(estado_destino_id_val) if estado_destino_id_val else None

        anel_id_selected = request.form.get('anel_id_select')
        novo_anel_nome = request.form.get('novo_anel_nome', '').strip()
        final_anel_id = None
        if novo_anel_nome:
            final_anel_id, _ = database.get_or_create_anel(novo_anel_nome)
        elif anel_id_selected:
            final_anel_id = int(anel_id_selected)

        if not final_anel_id:
            flash('Erro: É obrigatório selecionar um anel ou criar um novo.', 'danger')
            return redirect(url_for('cadastrar_vizinho'))

        # --- 3. Salvar Dados no Banco ---
        try:
            elem1_id, _ = database.get_or_create_elemento(nome_elemento1, nome_elemento1[:17], gerencia_id, longa_distancia=longa_distancia, estado_atual_id=estado_origem_id)
            elem2_id, _ = database.get_or_create_elemento(nome_elemento2, nome_elemento2[:17], gerencia_id, longa_distancia=longa_distancia, estado_atual_id=estado_destino_id)

            # CORREÇÃO: Passa o accid_lc para a função add_vizinho
            database.add_vizinho(elem1_id, elem2_id, accid_lc=accid_lc, swap_fibra_info=swap_fibra_info)

            database.add_elemento_anel(elem1_id, final_anel_id)
            database.add_elemento_anel(elem2_id, final_anel_id)

            flash('Vizinhança e associação de anel salvas com sucesso!', 'success')
            return redirect(url_for('consultar_elementos'))

        except Exception as e:
            flash(f'Ocorreu um erro: {e}', 'danger')
            return redirect(url_for('cadastrar_vizinho'))

    return render_template('cadastrar_vizinho.html', 
                           elementos=elementos, aneis=aneis, gerencias=gerencias,
                           estados_enlace=estados_enlace, prev_data={},
                           now=datetime.datetime.now())


@app.route('/associar_elemento_anel', methods=['GET', 'POST'])
def associar_elemento_anel():
    """Permite associar um elemento a um anel e, opcionalmente, definir o provedor desse anel."""
    elementos = database.get_all_elementos()
    aneis = database.get_all_aneis()
    detentores_site = database.get_all_detentores_site() # Busca a lista de provedores

    if request.method == 'POST':
        elemento_id = int(request.form['elemento_id'])
        anel_id = int(request.form['anel_id'])
        detentor_id = request.form.get('detentor_site_id') # Pega o ID do provedor

        if not elemento_id or not anel_id:
            flash('Erro: Elemento e Anel são obrigatórios.', 'danger')
        else:
            # 1. Associa o elemento ao anel
            if database.add_elemento_anel(elemento_id, anel_id):
                flash('Elemento associado ao anel com sucesso!', 'success')
            else:
                flash('A associação do elemento ao anel já existia.', 'info')

            # 2. Se um provedor foi selecionado, atualiza o anel
            if detentor_id:
                if database.update_anel_provider(anel_id, int(detentor_id)):
                    flash('Provedor do anel atualizado com sucesso!', 'success')
                else:
                    flash('Não foi possível atualizar o provedor do anel.', 'warning')

            return redirect(url_for('consultar_elementos'))

    return render_template('associar_elemento_anel.html', 
                           elementos=elementos, 
                           aneis=aneis,
                           detentores_site=detentores_site, # Passa a lista para o template
                           now=datetime.datetime.now())






@app.route('/cadastrar_detentor_site', methods=['GET', 'POST'])
def cadastrar_detentor_site():
    """Permite cadastrar novos detentores de site."""
    if request.method == 'POST':
        nome_detentor = request.form['nome_detentor']
        if database.add_detentor_site(nome_detentor):
            flash(f'Provedor da Fibra "{nome_detentor}" cadastrado com sucesso!', 'success')
            return redirect(url_for('consultar_detentores_site'))
        else:
            flash(f'Erro: Provedor da Fibra "{nome_detentor}" já existe ou dados inválidos.', 'danger')
    return render_template('cadastrar_detentor_site.html', now=datetime.datetime.now())


# --- Rotas de Consulta ---
@app.route('/consultar_gerencias')
def consultar_gerencias():
    gerencias = database.get_all_gerencias()
    # ADICIONE ESTA LINHA:
    try:
        fabricantes = database.get_all_fabricantes_dados() 
    except AttributeError:
        fabricantes = []
    # E ATUALIZE O RETORNO:
    return render_template('consultar_gerencias.html', gerencias=gerencias, fabricantes=fabricantes, now=datetime.datetime.now())

@app.route('/consultar_elementos')
def consultar_elementos():
    elementos = database.get_all_elementos()
    return render_template('consultar_elementos.html', elementos=elementos, database=database, now=datetime.datetime.now())

@app.route('/detalhes_elemento/<int:elemento_id>')
def detalhes_elemento(elemento_id):
    elemento = database.get_elemento_by_id(elemento_id)
    if not elemento:
        flash('Elemento não encontrado.', 'danger')
        return redirect(url_for('consultar_elementos'))
    
    gerencia_nome = database.get_gerencia_by_id(elemento['gerencia_id'])
    detentor_nome = database.get_detentor_site_name_by_id(elemento['detentor_site_id'])
    aneis = database.get_aneis_do_elemento(elemento_id)
    vizinhos = database.get_vizinhos_do_elemento(elemento_id)
    alarmes = database.get_alarmes_do_elemento(elemento_id)
    estado_atual_nome = database.get_estado_enlace_name_by_id(elemento['estado_atual_id']) if elemento['estado_atual_id'] else 'Não definido'

    # NOVO: Coletar ACCID/LCs e Swap de Fibra de todos os vizinhos para exibição
    all_accid_lcs = []
    all_swap_fibras = []
    for vizinho in vizinhos:
        if vizinho.get('accid_lc'):
            all_accid_lcs.append(vizinho['accid_lc'])
        if vizinho.get('swap_fibra_info'):
            all_swap_fibras.append(vizinho['swap_fibra_info'])
    
    # Usar set() para remover duplicatas e depois join para formar uma string
    accid_lcs_display = ", ".join(sorted(list(set(all_accid_lcs)))) if all_accid_lcs else 'N/A'
    swap_fibras_display = ", ".join(sorted(list(set(all_swap_fibras)))) if all_swap_fibras else 'N/A'


    return render_template('detalhes_elemento.html', 
                           elemento=elemento, 
                           gerencia_nome=gerencia_nome,
                           detentor_nome=detentor_nome,
                           aneis=aneis, 
                           vizinhos=vizinhos,
                           alarmes=alarmes,
                           estado_atual_nome=estado_atual_nome,
                           accid_lcs_display=accid_lcs_display,   # NOVO: Passando para o template
                           swap_fibras_display=swap_fibras_display, # NOVO: Passando para o template
                           database=database,
                           now=datetime.datetime.now())

@app.route('/consultar_aneis')
def consultar_aneis():
    aneis = database.get_all_aneis()
    return render_template('consultar_aneis.html', aneis=aneis, now=datetime.datetime.now())

@app.route('/detalhes_anel/<int:anel_id>')
def detalhes_anel(anel_id):
    anel = database.get_anel_by_id(anel_id)
    if not anel:
        flash('Anel não encontrado.', 'danger')
        return redirect(url_for('consultar_aneis'))

    # Busca o nome do provedor (detentor)
    provedor_nome = database.get_detentor_site_name_by_id(anel.get('detentor_site_id'))

    elementos_no_anel = database.get_elementos_no_anel(anel_id)

    return render_template('detalhes_anel.html', 
                           anel=anel, 
                           elementos_no_anel=elementos_no_anel,
                           provedor_nome=provedor_nome, # Passa o nome para o template
                           database=database,
                           now=datetime.datetime.now())
    
    

@app.route('/consultar_tipos_alarmes')
def consultar_tipos_alarmes():
    # 1. Alarmes de TX (Antigos)
    tipos_alarmes = database.get_all_tipos_alarmes()
    
    # 2. Alarmes de Dados (Novos)
    # Busca direta na tabela alarmes_dados
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM alarmes_dados ORDER BY nome_alarme")
        alarmes_dados = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Erro ao buscar alarmes de dados: {e}")
        alarmes_dados = []
    finally:
        conn.close()

    return render_template('consultar_tipos_alarmes.html', 
                           tipos_alarmes=tipos_alarmes, 
                           alarmes_dados=alarmes_dados, # <--- ENVIANDO A LISTA QUE FALTAVA
                           now=datetime.datetime.now())


@app.route('/consultar_alarmes')
def consultar_alarmes():
    alarmes = database.get_all_alarmes()
    # 2. Alarmes de Dados (Novos)
    # Busca direta na tabela alarmes_dados
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM alarmes_dados ORDER BY nome_alarme")
        alarmes_dados = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Erro ao buscar alarmes de dados: {e}")
        alarmes_dados = []
    finally:
        conn.close()
    return render_template('consultar_alarmes.html', alarmes=alarmes, alarmes_dados=alarmes_dados, database=database, now=datetime.datetime.now())



# Relatorio Paginado por dia mes e ano
@app.route('/relatorio_eventos')
def relatorio_eventos():
    # Pega os parâmetros da URL, ou usa None se não existirem
    ano = request.args.get('ano', type=int)
    mes = request.args.get('mes', type=int)
    dia = request.args.get('dia', type=int)

    # Se nenhum filtro for aplicado, usa a data atual
    if ano is None and mes is None and dia is None:
        hoje = datetime.datetime.now(LOCAL_TIMEZONE)
        ano = hoje.year
        mes = hoje.month
        dia = hoje.day

    eventos = database.get_all_eventos(ano=ano, mes=mes, dia=dia)

    # Lógica para navegação de datas
    nav_dates = {}
    if ano and mes and dia:
        current_date = datetime.date(ano, mes, dia)
        nav_dates['prev_day'] = current_date - datetime.timedelta(days=1)
        nav_dates['next_day'] = current_date + datetime.timedelta(days=1)

    if ano and mes:
        # Primeiro dia do mês atual
        current_month_start = datetime.date(ano, mes, 1)
        # Último dia do mês anterior
        prev_month_end = current_month_start - datetime.timedelta(days=1)
        nav_dates['prev_month'] = prev_month_end
        # Primeiro dia do próximo mês
        next_month_start = (current_month_start + datetime.timedelta(days=32)).replace(day=1)
        nav_dates['next_month'] = next_month_start

    return render_template('relatorio_eventos.html', 
                           eventos=eventos, 
                           database=database, 
                           now=datetime.datetime.now(),
                           # Passa os filtros atuais e as datas de navegação para o template
                           filtro_ano=ano,
                           filtro_mes=mes,
                           filtro_dia=dia,
                           nav_dates=nav_dates
                           )


# NOVO: Rota para detalhes de um evento
# Em app.py, substitua a função inteira por esta:
@app.route('/detalhes_evento/<int:evento_id>')
def detalhes_evento(evento_id):
    evento = database.get_evento_by_id(evento_id)
    if not evento:
        flash('Evento não encontrado.', 'danger')
        return redirect(url_for('relatorio_eventos'))
    
    # --- NOVA LÓGICA DE FORMATAÇÃO (MAIS ROBUSTA) ---
    descricao_raw = evento.get('descricao', '')
    descricao_formatada = ''
    
    # Lista de cabeçalhos que iniciam seções de texto livre ou com formatação própria
    delimiters = [
        "Informações extras:",
        "--- Regra do Teste OTDR ---",
        "--- Rascunho ---"
    ]

    # Encontra a posição do primeiro delimitador que aparece no texto
    first_delimiter_pos = -1
    for d in delimiters:
        pos = descricao_raw.find(d)
        if pos != -1:
            if first_delimiter_pos == -1 or pos < first_delimiter_pos:
                first_delimiter_pos = pos
            
    if first_delimiter_pos != -1:
        # Divide a descrição no primeiro delimitador encontrado
        parte_estruturada = descricao_raw[:first_delimiter_pos]
        parte_livre = descricao_raw[first_delimiter_pos:]

        # Aplica o espaçamento duplo apenas na parte estruturada
        parte_estruturada_formatada = parte_estruturada.strip().replace('\n', '\n\n')

        # Reconstitui a descrição, juntando a parte formatada com a parte livre (que mantém a formatação original)
        descricao_formatada = parte_estruturada_formatada + '\n\n' + parte_livre
    else:
        # Se nenhum delimitador for encontrado, formata o texto inteiro como antes (fallback)
        descricao_formatada = descricao_raw.replace('\n', '\n\n')
    
    # --- FIM DA NOVA LÓGICA DE FORMATAÇÃO ---

    # O restante da função para buscar alarmes, elementos, etc., continua igual...
    alarmes_do_evento = []
    elementos_do_evento = []
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT ee.elemento_id FROM evento_elemento ee WHERE ee.evento_id = ?", (evento_id,))
    element_ids_in_event = [row[0] for row in cursor.fetchall()]

    if element_ids_in_event:
        for element_id in element_ids_in_event:
            elem_data = database.get_elemento_by_id(element_id)
            if elem_data:
                elemento_data = {
                    'id': elem_data['id'],
                    'nome_elemento': elem_data['nome_elemento'],
                    'gerencia_id': elem_data['gerencia_id'],
                    'nome_gerencia': database.get_gerencia_by_id(elem_data['gerencia_id']),
                    'detentor_site_id': elem_data['detentor_site_id'],
                    'nome_detentor': database.get_detentor_site_name_by_id(elem_data['detentor_site_id']) if elem_data['detentor_site_id'] else 'N/A',
                    'longa_distancia': elem_data['longa_distancia'],
                    'estado_atual': database.get_estado_enlace_name_by_id(elem_data['estado_atual_id']) if elem_data['estado_atual_id'] else 'N/A'
                }
                elementos_do_evento.append(elemento_data)

    accid_lc_for_display = 'N/A'
    swap_fibra_for_display = 'N/A'
    if len(elementos_do_evento) >= 2:
        nome_elemento1_evento = elementos_do_evento[0]['nome_elemento']
        nome_elemento2_evento = elementos_do_evento[1]['nome_elemento']
        vizinhança_details = database.get_vizinhança_details_by_element_names(nome_elemento1_evento, nome_elemento2_evento)
        if vizinhança_details:
            accid_lc_for_display = vizinhança_details.get('accid_lc', 'N/A')
            swap_fibra_for_display = vizinhança_details.get('swap_fibra_info', 'N/A')

    cursor.execute("""
        SELECT a.id, e.nome_elemento, ta.nome_tipo_alarme, ta.equipe_responsavel, a.descricao, a.data_hora
        FROM evento_alarme ea
        JOIN alarmes a ON ea.alarme_id = a.id
        JOIN elementos e ON a.elemento_id = e.id
        JOIN tipos_alarmes ta ON a.tipo_alarme_id = ta.id
        WHERE ea.evento_id = ?
    """, (evento_id,))
    for row in cursor.fetchall():
        alarmes_do_evento.append({
            'id': row[0],
            'nome_elemento': row[1],
            'tipo_alarme': row[2],
            'equipe_responsavel': row[3],
            'descricao': row[4],
            'data_hora': datetime.datetime.strptime(row[5], "%Y-%m-%d %H:%M:%S") if row[5] else None
        })
    conn.close()

    return render_template('detalhes_evento.html', 
                           evento=evento,
                           descricao_formatada=descricao_formatada, # Passando a nova variável formatada
                           alarmes_do_evento=alarmes_do_evento,
                           elementos_do_evento=elementos_do_evento,
                           accid_lc_for_display=accid_lc_for_display, 
                           swap_fibra_for_display=swap_fibra_for_display, 
                           now=datetime.datetime.now())    
    
    

# Alterado para a tecnica de machine learning
@app.route('/correlacionar_alarmes_evento/<int:evento_id>', methods=['GET', 'POST'])
def correlacionar_alarmes_evento(evento_id):
    """
    Página de "Ensino" (Etapa 3) - Versão Limpa (Sem Debug)
    """
    
    evento = database.get_evento_by_id(evento_id)
    if not evento:
        flash('Evento não encontrado.', 'danger')
        return redirect(url_for('relatorio_eventos'))

    # 1. Busca elementos/alarmes "Pai"
    elementos_do_evento_ids = database.get_elementos_de_evento(evento_id)
    alarmes_do_evento = database.get_alarmes_de_evento(evento_id)
    
    # 2. Busca LISTA 1: VIZINHOS FÍSICOS (IDs)
    vizinhos_ids = set()
    if elementos_do_evento_ids:
        for el_id in elementos_do_evento_ids:
            try:
                vizinhos_do_el = database.get_vizinhos_ids_por_elemento_id(el_id)
                if vizinhos_do_el:
                    vizinhos_ids.update(vizinhos_do_el)
            except Exception:
                pass # Ignora erros silenciosamente para não quebrar o fluxo
    
    vizinhos_ids.difference_update(elementos_do_evento_ids)
    vizinhos_ids_lista = list(vizinhos_ids)

    # 3. Busca LISTA 2: VIZINHOS DE SITE (Colocados)
    elementos_colocados = []
    if elementos_do_evento_ids:
        try:
            elementos_colocados = database.get_elementos_no_mesmo_site(elementos_do_evento_ids)
        except Exception:
            pass

    # 4. Cria um "Pool Total de Suspeitos"
    elementos_colocados_ids = [e['id'] for e in elementos_colocados]
    ids_totais_suspeitos = list(set(vizinhos_ids_lista + elementos_colocados_ids))
            
    # 5. Busca ALARMES CANDIDATOS (Agora busca no Pool Total)
    alarmes_candidatos = []
    if ids_totais_suspeitos:
        alarmes_candidatos = database.get_alarmes_ativos_em_elementos(ids_totais_suspeitos)
    
    # 6. Busca os DETALHES dos Vizinhos Físicos
    vizinhos_detalhes = []
    if vizinhos_ids_lista:
        try:
            vizinhos_detalhes = database.get_elementos_detalhes_por_ids(vizinhos_ids_lista)
        except Exception:
            pass
            
    # --- Lógica do POST (Ensino) ---
    if request.method == 'POST':
        alarmes_filhos_ids = request.form.getlist('alarme_filho_id')
        alarme_pai_principal_id = alarmes_do_evento[0]['id'] if alarmes_do_evento else None
        
        if alarme_pai_principal_id and alarmes_filhos_ids:
            try:
                for filho_id in alarmes_filhos_ids:
                    database.definir_alarme_pai(int(filho_id), alarme_pai_principal_id)
                flash(f'Aprendizado salvo! {len(alarmes_filhos_ids)} alarmes correlacionados.', 'success')
            except Exception as e:
                flash(f'Erro ao salvar correlação: {e}', 'danger')
        
        return redirect(url_for('relatorio_eventos'))
    
    # --- Lógica do GET (Renderização) ---
    return render_template('correlacionar_alarmes.html',
                           evento=evento,
                           alarmes_do_evento=alarmes_do_evento,
                           alarmes_candidatos=alarmes_candidatos,
                           vizinhos_detalhes=vizinhos_detalhes,
                           elementos_colocados=elementos_colocados, 
                           now=datetime.datetime.now())   
    
        
# Rota para atualizar título do evento (já existente)
@app.route('/update_event_title/<int:event_id>', methods=['POST'])
def update_event_title(event_id):
    data = request.get_json()
    new_title = data.get('new_title')

    if not new_title:
        return jsonify({'success': False, 'message': 'Novo título não fornecido.'}), 400

    try:
        success = database.update_event_title(event_id, new_title)
        if success:
            return jsonify({'success': True, 'message': 'Título do evento atualizado com sucesso!'}), 200
        else:
            return jsonify({'success': False, 'message': 'Evento não encontrado ou falha na atualização.'}), 404
    except Exception as e:
        print(f"Erro ao atualizar título do evento {event_id}: {e}")
        return jsonify({'success': False, 'message': f'Erro interno ao atualizar: {e}'}), 500

# Rota: Obter detalhes do elemento por nome (para AJAX)
@app.route('/get_element_details', methods=['POST'])
def get_element_details():
    element_name = request.json.get('element_name')
    if not element_name:
        return jsonify({'success': False, 'message': 'Nome do elemento não fornecido.'}), 400

    element_details = database.get_element_details_by_name(element_name)
    
    if element_details:
        return jsonify({'success': True, 'element': element_details}), 200
    else:
        return jsonify({'success': False, 'message': 'Elemento não encontrado.'}), 404


# NOVA ROTA: Obter detalhes da vizinhança por nomes de elementos (para AJAX)
@app.route('/get_vizinhança_details', methods=['POST'])
def get_vizinhança_details():
    element_origem_name = request.json.get('element_origem_name')
    element_destino_name = request.json.get('element_destino_name')

    if not element_origem_name or not element_destino_name:
        return jsonify({'success': False, 'message': 'Nomes dos elementos origem e destino são obrigatórios.'}), 400
    
    vizinhança_details = database.get_vizinhança_details_by_element_names(element_origem_name, element_destino_name)

    if vizinhança_details:
        return jsonify({'success': True, 'vizinhança': vizinhança_details}), 200
    else:
        return jsonify({'success': False, 'message': 'Vizinhança não encontrada.'}), 404


@app.route('/consultar_detentores_site')
def consultar_detentores_site():
    detentores = database.get_all_detentores_site()
    return render_template('consultar_detentores_site.html', detentores=detentores, now=datetime.datetime.now())

# NOVO: Rota para Visualização de Diagrama de Enlaces
# Em app.py, substitua a função inteira por esta:

@app.route('/visualizar_enlace_diagrama')
def visualizar_enlace_diagrama():
    # --- IMPORTS DE SEGURANÇA ---
    from collections import defaultdict
    import datetime
    import pytz
    
    try:
        local_tz = LOCAL_TIMEZONE
    except NameError:
        local_tz = pytz.timezone('America/Sao_Paulo')

    # 1. Busca dados iniciais
    try:
        all_elements = database.get_all_diagram_elements()
        all_vizinhancas_raw = database.get_all_vizinhancas_for_diagram()
        all_links_capacidade = database.get_all_links_capacidade_for_diagram()
        link_cap_element_ids = database.get_all_link_capacidade_element_ids() or set()
    except Exception as e:
        print(f"ERRO AO BUSCAR DADOS DO BANCO: {e}")
        return f"Erro no Banco de Dados: {e}", 500
    
    # Mapeamentos auxiliares para as arestas
    element_map = {elem['id']: elem for elem in all_elements}

    # --- Agrupamento por Nome Curto (Chassi) ---
    grouped_elements = defaultdict(list)
    for element in all_elements:
        full_name = element['nome_elemento'].strip()
        short_name = element.get('nome_elemento_curto', full_name).strip()
        if not short_name: short_name = full_name 
        grouped_elements[short_name].append(element)

    nodes = []
    
    # PROCESSAMENTO DOS NÓS (AGRUPADOS)
    for short_name, group in grouped_elements.items():
        
        # 1. Define o "Representante" (Prioridade: Link Cap -> Primeiro da lista)
        representative = group[0]
        group_has_link_cap = False
        
        # Ordena o group: Link de Capacidade primeiro (para aparecer no topo do card)
        group.sort(key=lambda x: x['id'] in link_cap_element_ids, reverse=True)
        
        # Flags do grupo
        group_is_active_failure = False
        group_failure_type = None
        
        # --- CONSTRUÇÃO DO HTML DETALHADO (CARD RICO) ---
        # Começamos a tabela do tooltip
        tooltip_content = "<div style='text-align:left; min-width:300px; font-family: sans-serif;'>"
        
        for elem in group:
            is_link_cap = elem['id'] in link_cap_element_ids
            if is_link_cap:
                group_has_link_cap = True
                representative = elem 
            
            # --- Lógica de Falha (Status) ---
            is_active = False 
            is_affected_str = str(elem.get('esta_afetado', '0'))
            
            if is_affected_str in ['1', 'True', 'true']:
                affected_until_str = elem.get('afetado_ate')
                if affected_until_str:
                    try:
                        if '.' in affected_until_str:
                             dt = datetime.datetime.strptime(affected_until_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        else:
                             dt = datetime.datetime.strptime(affected_until_str, "%Y-%m-%d %H:%M:%S")
                        dt = local_tz.localize(dt)
                        if dt > datetime.datetime.now(local_tz): is_active = True
                    except: is_active = True 
                else: is_active = True
                
                if is_active:
                    group_is_active_failure = True
                    tp = elem.get('tipo_evento_ativo')
                    if tp == 'Falha de Link de Capacidade': group_failure_type = tp
                    elif not group_failure_type: group_failure_type = tp

            # --- Busca Vizinhos Detalhados para este Sub-Elemento ---
            # Aqui acontece a mágica de mostrar "quem conecta com quem"
            vizinhos_detalhados = database.get_vizinhos_do_elemento(elem['id'])
            
            # --- Estilização do Bloco (Violeta se for Link Cap, Cinza se normal) ---
            border_color = "#8A2BE2" if is_link_cap else "#cccccc"
            bg_color = "#F8F0FF" if is_link_cap else "#f9f9f9"
            icon_role = "🟣 <b>LINK CAP</b>" if is_link_cap else "🔵"
            status_icon = "🔴 FALHA" if is_active else "✅ OK"
            
            tooltip_content += f"""
            <div style='border: 1px solid {border_color}; background-color: {bg_color}; border-radius: 4px; padding: 6px; margin-bottom: 6px;'>
                <div style='border-bottom: 1px dashed {border_color}; padding-bottom: 3px; margin-bottom: 3px;'>
                    <strong>{elem['nome_elemento']}</strong>
                </div>
                <div style='font-size: 11px; color: #333; margin-bottom: 4px;'>
                    {status_icon} | {icon_role}<br>
                    Ger: <b>{elem['nome_gerencia']}</b> | Est: <b>{elem['estado_atual'] or 'N/A'}</b><br>
                    Anéis: {elem['aneis_nomes'] or 'N/A'}
                </div>
            """
            
            # --- Lista de Vizinhos deste Sub-Elemento ---
            if vizinhos_detalhados:
                tooltip_content += "<div style='font-size: 10px; color: #555; margin-top: 2px;'><b>↳ Conecta com:</b><br>"
                for v in vizinhos_detalhados:
                    # Formata o vizinho: Nome + Estado + Anéis
                    v_estado = v.get('estado', 'N/A')
                    v_aneis = v.get('aneis', 'N/A')
                    # Nome do vizinho em negrito se for Link de Capacidade
                    v_nome_style = "font-weight:bold; color:#4B0082;" if is_link_cap else ""
                    
                    tooltip_content += f"&nbsp;&nbsp;🔗 <span style='{v_nome_style}'>{v['nome_elemento']}</span> <span style='color:#000;'>({v_estado})</span><br>"
                    if v_aneis and v_aneis != 'N/A':
                         tooltip_content += f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<i>Anéis: {v_aneis}</i>"
                    tooltip_content += f" | ACCID: {v['accid_lc'] or '--'}<br>"
                tooltip_content += "</div>"
            else:
                tooltip_content += "<div style='font-size: 10px; color: #aaa;'><i>Sem conexões físicas registradas</i></div>"
                
            tooltip_content += "</div>" # Fecha o bloco do elemento

        tooltip_content += "</div>" # Fecha o container geral

        # 2. Definição Visual do Nó
        label_visual = short_name
        if len(label_visual) > 15:
            parte_inicial = label_visual[:15]
            resto = label_visual[15:]
            if any(char.isdigit() for char in resto):
                label_visual = parte_inicial

        # Título HTML Final (Cabeçalho + Conteúdo Rico)
        title_html = f"<div style='font-size:14px; font-weight:bold; margin-bottom:5px;'>{short_name}</div>"
        
        # Adiciona dados Databook do representante no topo
        if representative.get('site_id') or representative.get('cidade'):
            title_html += "<div style='font-size:11px; color:#666; margin-bottom:8px; border-bottom:2px solid #ddd; padding-bottom:4px;'>"
            if representative.get('site_id'): title_html += f"Site ID: <b>{representative['site_id']}</b> "
            if representative.get('cidade'): title_html += f"| {representative.get('cidade')} - {representative.get('uf','')}"
            title_html += "</div>"
            
        title_html += tooltip_content
        
        # Flag para Javascript pintar o card (SIM/NÃO)
        if group_has_link_cap:
            title_html += "<div style='display:none;'>LINK DE CAPACIDADE</div>"

        node_properties = {
            'id': short_name, 
            'label': label_visual,
            'title': title_html, # Aqui vai o HTML completão
            'longa_distancia': representative['longa_distancia'], 
            'site_id': representative.get('site_id'),
            'cidade': representative.get('cidade'),
            'uf': representative.get('uf'),
            'endereco': representative.get('endereco')
        }

        # 3. Lógica de Cores (Prioridades)
        # Padrão
        node_properties['color'] = {'background': '#97c2fc', 'border': '#2B7CE9'}
        node_properties['borderWidth'] = 1

        if group_is_active_failure:
            if group_failure_type == 'Falha de Link de Capacidade':
                node_properties['color'] = {'background': '#FFC0CB', 'border': '#DC143C'} # Vermelho
                node_properties['borderWidth'] = 4
            elif group_failure_type and ('ROMPIMENTO' in str(group_failure_type).upper()):
                 node_properties['color'] = {'background': '#FF9800', 'border': '#F57C00'} # Laranja
                 node_properties['borderWidth'] = 4
            else:
                node_properties['color'] = {'background': '#FFF0E1', 'border': '#FF8C00'} # Laranja Gen
                node_properties['borderWidth'] = 4
        
        elif group_has_link_cap:
            node_properties['color'] = {'background': '#F8F0FF', 'border': '#8A2BE2'} # Violeta
            node_properties['borderWidth'] = 2

        # 4. O Halo Amarelo (Shadow) se houver agrupamento > 1
        if len(group) > 1:
            node_properties['shadow'] = {'enabled': True, 'color': '#FFD700', 'size': 15, 'x': 0, 'y': 0}
        else:
            node_properties['shadow'] = {'enabled': False}

        nodes.append(node_properties)

    # --- E. PROCESSAMENTO DE ARESTAS (Apontando para os nós agrupados) ---
    processed_edges = set()
    edges = []
    
    # 1. Vizinhanças Físicas
    for viz in all_vizinhancas_raw:
        source_elem = element_map.get(viz['elemento_origem_id'])
        target_elem = element_map.get(viz['elemento_destino_id'])
        
        if source_elem and target_elem:
            src_name = source_elem.get('nome_elemento_curto', source_elem['nome_elemento']).strip()
            if not src_name: src_name = source_elem['nome_elemento'].strip()
            
            tgt_name = target_elem.get('nome_elemento_curto', target_elem['nome_elemento']).strip()
            if not tgt_name: tgt_name = target_elem['nome_elemento'].strip()
            
            edge_tuple = tuple(sorted([src_name, tgt_name]))
            
            if edge_tuple not in processed_edges and src_name != tgt_name:
                edges.append({
                    'from': src_name, 'to': tgt_name, 
                    'label': viz['accid_lc'] if viz['accid_lc'] else '',
                    'title': f"ACCID/LC: {viz['accid_lc'] or 'N/A'}<br>Swap: {viz['swap_fibra_info'] or 'N/A'}",
                    'color': {'color': '#848484'}
                })
                processed_edges.add(edge_tuple)
                
    # 2. Links de Capacidade
    for link in all_links_capacidade:
         source_elem = element_map.get(link['elemento_a_id'])
         target_elem = element_map.get(link['elemento_b_id'])
         
         if source_elem and target_elem:
            src_name = source_elem.get('nome_elemento_curto', source_elem['nome_elemento']).strip()
            if not src_name: src_name = source_elem['nome_elemento'].strip()

            tgt_name = target_elem.get('nome_elemento_curto', target_elem['nome_elemento']).strip()
            if not tgt_name: tgt_name = target_elem['nome_elemento'].strip()
            
            edge_properties = {
                'from': src_name, 'to': tgt_name, 'label': 'Link Cap.', 'dashes': [5, 5], 'width': 3
            }
            
            # Checagem simplificada de falha no link
            source_in_fail = source_elem.get('tipo_evento_ativo') == 'Falha de Link de Capacidade'
            target_in_fail = target_elem.get('tipo_evento_ativo') == 'Falha de Link de Capacidade'

            if source_in_fail and target_in_fail:
                edge_properties['color'] = {'color': '#DC143C', 'highlight': '#FF6347'}
                edge_properties['title'] = f"<div style='background-color:#FFD2D2; padding:5px;'><b>Link EM FALHA</b><br>Prov: {link['nome_detentor']}</div>"
            else:
                edge_properties['color'] = {'color': '#8A2BE2', 'highlight': '#9932CC'}
                edge_properties['title'] = f"<div style='background-color:#E6E6FA; padding:5px;'><b>Link de Capacidade</b><br>Prov: {link['nome_detentor']}</div>"
            
            edges.append(edge_properties)
            

    return render_template('visualizar_enlace_diagrama.html', 
                           nodes_data=nodes, 
                           edges_data=edges, 
                           estados=database.get_all_estados_enlace(), # Se tiver usando BBIP
                           engineering_mode=SERVER_MODE_ENGINEERING,  # <--- AQUI
                           now=datetime.datetime.now())
    
    



@app.route('/consultar_estados_enlace')
def consultar_estados_enlace():
    estados = database.get_all_estados_enlace()
    return render_template('consultar_estados_enlace.html', estados=estados, now=datetime.datetime.now())


 

# ROTA ADICIONADA: Excluir um elemento e seus registros relacionados
@app.route('/excluir_elemento/<int:elemento_id>', methods=['POST'])
def excluir_elemento(elemento_id):
    if database.excluir_elemento_e_registros_relacionados(elemento_id):
        flash('Elemento e todos os registros relacionados foram excluídos com sucesso.', 'success')
    else:
        flash('Erro ao excluir o elemento. Verifique se o ID está correto.', 'danger')
    return redirect(url_for('consultar_elementos'))

# --- Rota de API para Autocomplete ---

@app.route('/search_elementos')
def search_elementos():
    """
    API que retorna uma lista de elementos em formato JSON
    para a funcionalidade de autocomplete.
    """
    query = request.args.get('q', '')
    if len(query) < 3: # Só busca se o usuário digitou pelo menos 3 caracteres
        return jsonify([])
    
    elementos = database.search_elementos_com_vizinho(query)
    return jsonify(elementos)

# --- Rota de API para Autocomplete Aneis ---
@app.route('/search_aneis')
def search_aneis():
    """
    API que retorna uma lista de anéis em formato JSON
    para a funcionalidade de autocomplete.
    """
    query = request.args.get('q', '')
    if len(query) < 2: # Pode buscar com 2 caracteres para nomes de anéis
        return jsonify([])
    
    aneis = database.search_aneis_by_name(query)
    return jsonify(aneis)


# ----------------- ROTA PARA NOVO DIAGRAMA BBIP -----------
# Em app.py, substitua a função inteira por esta:
# --- ROTA PRINCIPAL DO DIAGRAMA (MASTER ELAINE + PESQUISA ACCID + AGRUPAMENTO INTELIGENTE) ---
# --- ROTA PRINCIPAL DO DIAGRAMA (MASTER ELAINE + PESQUISA ACCID + AGRUPAMENTO INTELIGENTE) ---
# --- ROTA PRINCIPAL DO DIAGRAMA (MASTER ELAINE 2.0: FÍSICO + LÓGICO + GAPS) ---
# --- ROTA PRINCIPAL (MASTER ELAINE 2.0: FÍSICO + LÓGICO + GAPS DE CADASTRO) ---
# --- ROTA PRINCIPAL DO DIAGRAMA (MASTER ELAINE 3.0: FÍSICO + LÓGICO + GAPS + INJEÇÃO) ---
# --- ROTA PRINCIPAL (MASTER ELAINE 4.0: DETECÇÃO DE FALHA NA LINHA LÓGICA) ---
# --- ROTA PRINCIPAL DO DIAGRAMA (MASTER ELAINE ATUALIZADA: FÍSICO + LÓGICO + VISUALIZAÇÃO DE FALHAS) ---
# ==============================================================================
# --- ROTA DO MAPA (COM DIFERENCIAÇÃO FÍSICO x LÓGICO) ---
# ==============================================================================
# ==============================================================================
# --- ROTA DO MAPA (COM INTELIGÊNCIA VETORIAL / DIRECIONAL CORRIGIDA) ---
# ==============================================================================
@app.route('/visualizacao_bbip')
@app.route('/visualizacao_bbip')
def visualizacao_bbip():
    from collections import defaultdict
    import datetime 
    import pytz 
    import sqlite3 
    
    # 1. SETUP INICIAL & DADOS GERAIS
    try:
        local_tz = LOCAL_TIMEZONE
    except NameError:
        local_tz = pytz.timezone('America/Sao_Paulo')
    
    now = datetime.datetime.now(local_tz)

    all_elements = database.get_all_diagram_elements()
    all_vizinhancas_raw = database.get_all_vizinhancas_for_diagram()
    estados = database.get_all_estados_enlace()
    
    # --- 0. BUSCA LISTA DE ACCIDs COM FALHA (LÓGICA) ---
    accids_com_falha = set()
    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT accid FROM circuitos_dados 
            WHERE (tipo_falha IS NOT NULL AND tipo_falha != '')
               OR (status_origem_id IN (SELECT id FROM status_dados WHERE nome_status != 'UP'))
        """)
        for r in cursor.fetchall():
            if r[0]: accids_com_falha.add(r[0])
        conn.close()
    except Exception as e:
        print(f"Erro ao buscar falhas lógicas: {e}")

    # 1. MAPA DE CLUSTERS
    cluster_map = {}
    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, cluster_uf, cluster_regiao FROM elementos")
        for r in cursor.fetchall():
            uf = r[1] if r[1] else 'N/A'
            regiao = r[2] if r[2] else 'OUTROS'
            cluster_map[r[0]] = {'uf': uf, 'regiao': regiao}
        conn.close()
    except: pass

    # 2. CONTAGEM ROTEADORES
    router_counts = defaultdict(int)
    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT site_id, COUNT(*) FROM equipamentos_dados WHERE site_id IS NOT NULL AND site_id != '' GROUP BY site_id")
        for row in cursor.fetchall():
            if row[0]: router_counts[row[0].strip().upper()] = row[1]
        conn.close()
    except: pass

    # 3. PRÉ-PROCESSAMENTO: MAPA DE SITES
    sites_dict = defaultdict(list)
    element_id_to_site_name = {}
    
    # Dicionário para saber se o SITE tem alarme (para pintar o NÓ, não a linha)
    site_has_alarm_generic = defaultdict(bool)

    for elem in all_elements:
        nome_bruto = elem['nome_elemento'].strip().upper()
        parts = nome_bruto.split('-')
        if len(parts) >= 2: site_name = f"{parts[0]}-{parts[1]}"
        else: site_name = nome_bruto 
            
        sites_dict[site_name].append(elem)
        element_id_to_site_name[elem['id']] = site_name

        # Verifica se tem alarme ativo (para status do NÓ)
        if elem.get('esta_afetado') in [1, '1', True]:
            afetado_ate = elem.get('afetado_ate')
            is_active = True
            if afetado_ate:
                try:
                    dt_str = str(afetado_ate).split('.')[0]
                    event_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    event_time = local_tz.localize(event_dt)
                    # Regra de 8 horas também para os nós
                    limit_time = now - datetime.timedelta(hours=8)
                    if event_time < limit_time: is_active = False 
                except: pass 
            
            if is_active:
                site_has_alarm_generic[site_name] = True

    # 3.5 INJEÇÃO DE SITES LÓGICOS
    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT site_id FROM equipamentos_dados WHERE site_id IS NOT NULL AND site_id != ''")
        logical_sites = [row[0].strip().upper() for row in cursor.fetchall()]
        conn.close()

        for l_site in logical_sites:
            if l_site not in sites_dict:
                virtual_elem = {
                    'id': f"logical_{l_site}", 
                    'nome_elemento': f"Site Lógico {l_site}",
                    'site_id': l_site, 'tipo_icone': 'nuvem', 'is_logical_only': True, 'esta_afetado': 0
                }
                sites_dict[l_site].append(virtual_elem)
    except: pass

    # =========================================================================
    # --- OTIMIZAÇÃO DO MESSI: CACHE DE FALHAS FÍSICAS (Bulk Fetch) ---
    # =========================================================================
    # Em vez de consultar o banco dentro do loop, carregamos tudo aqui.
    physical_failure_map = {} # Chave: (site_a, site_b), Valor: Descrição do erro
    try:
        conn_opt = sqlite3.connect(database.DATABASE_NAME)
        cursor_opt = conn_opt.cursor()
        
        # Busca alarmes críticos das últimas 8 HORAS cruzando com vizinhança
        query_opt = """
            SELECT e_origem.nome_elemento, e_origem.site_id, 
                   e_destino.nome_elemento, e_destino.site_id,
                   a.descricao
            FROM alarmes a
            JOIN elementos e_origem ON a.elemento_id = e_origem.id
            JOIN vizinhanca v ON v.elemento_origem_id = e_origem.id
            JOIN elementos e_destino ON v.elemento_destino_id = e_destino.id
            WHERE 
                a.data_hora >= datetime('now', '-8 hours', 'localtime')
                AND (a.descricao LIKE '%Link Down%' OR a.descricao LIKE '%LOS%' OR a.descricao LIKE '%Rompimento%')
        """
        cursor_opt.execute(query_opt)
        rows_opt = cursor_opt.fetchall()
        
        for r in rows_opt:
            nm_orig, id_orig, nm_dest, id_dest, desc = r
            
            # Função local rápida para extrair nome do site (mesma lógica da Seção 3)
            def get_site_name_fast(nm, sid):
                if sid: return sid.strip().upper()
                p = nm.strip().upper().split('-')
                return f"{p[0]}-{p[1]}" if len(p) >= 2 else nm.strip().upper()

            s_a = get_site_name_fast(nm_orig, id_orig)
            s_b = get_site_name_fast(nm_dest, id_dest)
            
            # Salva nas duas direções para garantir o match
            physical_failure_map[(s_a, s_b)] = desc
            physical_failure_map[(s_b, s_a)] = desc
            
        conn_opt.close()
    except Exception as e:
        print(f"Erro no Cache Físico: {e}")
    # =========================================================================


    # 4. CONSTRUÇÃO DAS LINHAS
    connections_map = defaultdict(lambda: {
        'accids': [], 
        'count_fisico': 0, 
        'is_virtual': True 
    })

    # A. Vizinhanças FÍSICAS
    for viz in all_vizinhancas_raw:
        site_a = element_id_to_site_name.get(viz['elemento_origem_id'])
        site_b = element_id_to_site_name.get(viz['elemento_destino_id'])
        
        if site_a and site_b and site_a != site_b:
            pair_key = tuple(sorted((site_a, site_b)))
            connections_map[pair_key]['count_fisico'] += 1
            connections_map[pair_key]['is_virtual'] = False 

    # B. Processa Lógica
    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        
        # B1. Rota Detalhada
        cursor.execute("""
            SELECT r1.elemento_tx_id, r2.elemento_tx_id, c.accid
            FROM rota_circuitos_tx r1
            JOIN rota_circuitos_tx r2 ON r1.circuito_dados_id = r2.circuito_dados_id
            JOIN circuitos_dados c ON r1.circuito_dados_id = c.id
            WHERE r2.ordem_salto = r1.ordem_salto + 1
        """)
        for r in cursor.fetchall():
            id_orig, id_dest, accid = r[0], r[1], r[2]
            if id_orig and id_dest:
                site_a = element_id_to_site_name.get(id_orig)
                site_b = element_id_to_site_name.get(id_dest)
                if site_a and site_b and site_a != site_b:
                    pair_key = tuple(sorted((site_a, site_b)))
                    if accid: connections_map[pair_key]['accids'].append(accid)

        # B2. Conexão Direta
        cursor.execute("""
            SELECT ed1.site_id, ed2.site_id, c.accid
            FROM circuitos_dados c
            JOIN equipamentos_dados ed1 ON c.roteador_origem_id = ed1.id
            JOIN equipamentos_dados ed2 ON c.roteador_destino_id = ed2.id
            WHERE c.roteador_origem_id IS NOT NULL 
              AND c.roteador_destino_id IS NOT NULL
              AND c.id NOT IN (SELECT DISTINCT circuito_dados_id FROM rota_circuitos_tx)
        """)
        for r in cursor.fetchall():
            site_orig_raw, site_dest_raw, accid = r[0], r[1], r[2]
            if site_orig_raw and site_dest_raw:
                site_a = site_orig_raw.strip().upper()
                site_b = site_dest_raw.strip().upper()
                if site_a in sites_dict and site_b in sites_dict and site_a != site_b:
                    pair_key = tuple(sorted((site_a, site_b)))
                    if accid: connections_map[pair_key]['accids'].append(accid)

        conn.close()
    except Exception as e:
        print(f"Erro processando rotas: {e}")

    
    # C. Renderização Final das Arestas
    edges = []
    for (site_a, site_b), data in connections_map.items():
        unique_accids = list(set(data['accids']))
        has_traffic = len(unique_accids) > 0
        is_virtual = data['is_virtual']
        count_fisico = data['count_fisico']
        
        accid_search_string = ",".join(unique_accids)
        
        # --- LÓGICA VETORIAL OTIMIZADA (Check no Cache) ---
        is_physical_broken = False
        failure_desc = ""
        
        # Verifica se existe falha em A->B ou B->A no nosso mapa pré-carregado
        if (site_a, site_b) in physical_failure_map:
            is_physical_broken = True
            failure_desc = physical_failure_map[(site_a, site_b)]
        elif (site_b, site_a) in physical_failure_map:
            is_physical_broken = True
            failure_desc = physical_failure_map[(site_b, site_a)]
        
        # 2. Existe Falha Lógica?
        has_logical_failure = False
        for acc in unique_accids:
            if acc in accids_com_falha:
                has_logical_failure = True
                break

        # --- DEFINIÇÃO DE ESTILO DA LINHA ---
        
        # CASO 1: VERMELHO (Físico Confirmado NO LINK)
        if is_physical_broken:
            header_color = "#d32f2f" # Vermelho
            header_text = f"🚨 ROMPIMENTO FÍSICO: {failure_desc}"
            edge_color = {'color': '#FF0000', 'opacity': 1.0}
            edge_width = 5
            edge_dashes = True
            edge_shadow = {'enabled': True, 'color': '#FF0000', 'size': 15}
            
        # CASO 2: AMARELO (Lógico Puro / Físico OK neste trecho)
        elif has_logical_failure:
            header_color = "#FFA000"
            header_text = "⚠️ FALHA LÓGICA / DADOS"
            edge_color = {'color': '#FFC107', 'opacity': 1.0}
            edge_width = 4
            edge_dashes = [10, 10]
            edge_shadow = {'enabled': True, 'color': '#FFC107', 'size': 10}

        # CASO 3: GAP Lógico
        elif is_virtual and has_traffic:
            header_color = "#FBC02D"
            header_text = "ℹ️ CONEXÃO LÓGICA (GAP)"
            edge_color = {'color': '#FFD700', 'opacity': 0.6}
            edge_width = 2
            edge_dashes = True
            edge_shadow = False

        # CASO 4: OK
        elif not is_virtual and has_traffic:
            header_color = "#00acc1"
            header_text = "✅ CONEXÃO OPERACIONAL"
            edge_color = {'color': '#00e5ff', 'opacity': 1.0, 'highlight': '#00e5ff'}
            edge_width = 4
            edge_dashes = False
            edge_shadow = {'enabled': True, 'color': '#00e5ff', 'size': 10}
            
        else: # Escuro
            header_color = "#757575"
            header_text = "INFRAESTRUTURA FÍSICA"
            edge_color = {'color': '#cccccc', 'opacity': 0.4}
            edge_width = 1
            edge_dashes = False
            edge_shadow = False

        # --- HTML DO TOOLTIP ---
        lista_accid_html = ""
        top_accids = unique_accids[:10]
        for acc in top_accids:
            icon = "🔥" if acc in accids_com_falha else "🔌"
            style = "color:red; font-weight:bold;" if acc in accids_com_falha else ""
            lista_accid_html += f"<div style='{style}'>{icon} {acc}</div>"
        
        if len(unique_accids) > 10:
            lista_accid_html += f"<div style='color:#666;'>... e mais {len(unique_accids)-10}</div>"

        if not has_traffic:
             lista_accid_html = "<div style='color:#999; font-style:italic;'>Sem tráfego de dados registrado.</div>"

        html_title = f"""
        <div style='background:white; border:1px solid #999; border-radius:4px; font-family:sans-serif; min-width:220px; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);'>
            <div style='background:{header_color}; color:white; padding:8px; font-weight:bold; text-align:center;'>
                {header_text}
            </div>
            <div style='padding:10px; color:#333; font-size:12px;'>
                <div style='display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px;'>
                    <b>{site_a}</b> ⇄ <b>{site_b}</b>
                </div>
                
                <div style='background:#f5f5f5; padding:6px; border-radius:3px; margin-bottom:8px; border:1px solid #eee;'>
                    📡 Fibras Físicas: <b>{count_fisico}</b><br>
                    ⚡ Circuitos Lógicos: <b>{len(unique_accids)}</b>
                </div>
                
                <hr style='margin:5px 0; border:0; border-top:1px solid #eee;'>
                
                <div style='max-height:150px; overflow-y:auto; font-family:monospace; line-height:1.4;'>
                    {lista_accid_html}
                </div>
            </div>
        </div>
        """
        html_title = html_title.replace('\n', '')

        edge_config = {
            'from': site_a, 'to': site_b,
            'dashes': edge_dashes, 'accid_list': accid_search_string,
            'title': html_title, 'color': edge_color,
            'width': edge_width, 'shadow': edge_shadow,
            'has_circuit': has_traffic
        }
        edges.append(edge_config)

    # 5. PROCESSAMENTO DOS NÓS
    nodes = []
    for site_name, elements_inside in sites_dict.items():
        site_uf = "XX"
        for e in elements_inside:
            if 'id' in e and isinstance(e['id'], int) and e['id'] in cluster_map:
                u = cluster_map[e['id']]['uf']
                if u and u not in ['N/A', '']: site_uf = u; break
        
        # O Nó fica vermelho se o Site tiver alarme
        status = "CRITICAL" if site_has_alarm_generic[site_name] else "OK"
        
        qtd_routers = router_counts.get(site_name, 0)
        is_pure_logical = any(e.get('is_logical_only') for e in elements_inside)

        node = {
            'id': site_name, 'label': site_name, 'cluster_uf': site_uf,
            'title': f"<b>{site_name}</b><br>UF: {site_uf}<br>Status: {status}<br><hr>",
            'qtd_roteadores': qtd_routers,
            'tipo_icone': 'nuvem' if (qtd_routers > 0 or is_pure_logical) else 'site',
            'borderWidth': 2
        }
        
        if status == "CRITICAL":
            node['color'] = {'background': '#FFC0CB', 'border': '#DC143C'}
            node['borderWidth'] = 4
        elif is_pure_logical:
             node['color'] = {'background': '#E0F7FA', 'border': '#006064'}
             node['shape'] = 'cloud'
        elif qtd_routers > 0:
             node['color'] = {'background': '#F8F0FF', 'border': '#8A2BE2'}
        else:
             node['color'] = {'background': '#F8F0FF', 'border': '#8A2BE2'}

        nodes.append(node)

    return render_template('visualizacao_bbip.html', nodes_data=nodes, edges_data=edges, estados=estados, now=datetime.datetime.now())   
    
    
    
    
    
# --- Rota de API para Autocomplete de Tipos de Alarme ---
@app.route('/search_tipos_alarmes')
def search_tipos_alarmes():
    """
    API que retorna uma lista de tipos de alarme em JSON para o autocomplete.
    """
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])

    tipos_alarmes = database.search_tipos_alarmes_by_name(query)
    return jsonify(tipos_alarmes)
    

# --- ROTA PARA BACKUP DO BANCO DE DADOS ---
@app.route('/backup_db')
def backup_db():
    """
    Gera um backup do banco de dados para download do usuário.
    """
    try:
        # Cria um nome de arquivo com data e hora para o backup
        timestamp = datetime.datetime.now(LOCAL_TIMEZONE).strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"rede_db_backup_{timestamp}.sqlite"

        # Envia o arquivo para o usuário
        return send_file(
            database.DATABASE_NAME,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/x-sqlite3'
        )
    except Exception as e:
        flash(f'Ocorreu um erro ao gerar o backup: {e}', 'danger')
        return redirect(url_for('index'))
    
# ATERACAO PARA A TECNICA DE machine learning 
# Rota para quick evento.
@app.route('/quick_add_step2_evento', methods=['GET', 'POST'])
@app.route('/quick_add_step2_evento', methods=['GET', 'POST'])
def quick_add_step2_evento():
    final_data = session.get('final_quick_add_data')
    if not final_data:
        flash('Erro: Dados da etapa anterior não encontrados. Por favor, comece novamente.', 'danger')
        return redirect(url_for('index'))

    # --- 1. PREPARAÇÃO DOS DADOS (Funciona para GET e POST) ---
    
    # Tenta recuperar o rascunho do Form (POST) ou da Sessão (GET/Redirect)
    rascunho_texto = request.form.get('rascunho_texto')
    if rascunho_texto is None:
        rascunho_texto = final_data.get('rascunho_texto', '')
    
    # Recupera nomes e IDs para montar o texto
    nome_elemento1 = final_data['nome_elemento1']
    nome_elemento2 = final_data['nome_elemento2']
    anel_nome_obj = database.get_anel_by_id(final_data['anel_id'])
    anel_nome = anel_nome_obj['nome_anel'] if anel_nome_obj else '[Anel]'
    tipo_alarme1_nome = database.get_tipo_alarme_name_by_id(final_data['tipo_alarme1_id']) or '[Tipo Alarme 1]'
    estado_origem_nome = database.get_estado_enlace_name_by_id(final_data['estado_origem_id']) if final_data['estado_origem_id'] else '[Estado Origem]'
    estado_destino_nome = database.get_estado_enlace_name_by_id(final_data['estado_destino_id']) if final_data['estado_destino_id'] else '[Estado Destino]'
    report_type = final_data.get('report_type', 'padrao')
    otdr_em_curso = final_data.get('teste_otdr_em_curso') == 1
    km_rompimento = final_data.get('km_rompimento_otdr', '')

    # Gera Título
    titulo_evento_sugerido = f"Alarme {tipo_alarme1_nome} em {nome_elemento1} e {nome_elemento2} - Anel {anel_nome}"
    
    # Gera Descrição
    descricao_evento_parts = []
    
    first_line = ""
    if report_type == 'atenuacao':
        first_line = f'Atenuação entre "{estado_origem_nome}" para "{estado_destino_nome}". (ANEL: {anel_nome})'
    elif report_type == 'degradacao':
        first_line = f'Degradação entre "{estado_origem_nome}" para "{estado_destino_nome}". (ANEL: {anel_nome})'
    elif report_type == 'link_capacidade':
        first_line = f'Falha no link de capacidade entre "{estado_origem_nome}" para "{estado_destino_nome}". (ANEL: {anel_nome})'
    else:
        if otdr_em_curso:
            first_line = f'Rompimento de fibra entre "{estado_origem_nome}" para "{estado_destino_nome}". (ANEL: {anel_nome})'
        else:
            first_line = f'Abertura do Enlace entre "{estado_origem_nome}" para "{estado_destino_nome}". (ANEL: {anel_nome})'        
    descricao_evento_parts.append(first_line)

    alarmes2_nomes = [database.get_tipo_alarme_name_by_id(id) for id in final_data['tipo_alarmes2_ids']]
    alarmes2_texto = ', '.join(filter(None, alarmes2_nomes)) or "Não informados."

    descricao_evento_parts.append(f"\nELEMENTO 1: {nome_elemento1}")
    descricao_evento_parts.append(f"\nELEMENTO 2: {nome_elemento2}")
    descricao_evento_parts.append(f"\nAlarme Elemento 1: {tipo_alarme1_nome}")
    descricao_evento_parts.append(f"\nAlarmes Elemento Vizinho: {alarmes2_texto}")
    descricao_evento_parts.append(f"\nACCID/LC: {final_data.get('accid_lc_comum') or 'Não informado.'}")
    descricao_evento_parts.append(f"\nSwap de Fibra: {final_data.get('swap_fibra_info') or 'Não informado.'}")
    descricao_evento_parts.append(f"\nInformações extras: {final_data.get('info_extra') or 'Não há informações adicionais.'}")
    
    descricao_evento_parts.append("\n\n--- Regra do Teste OTDR ---")
    descricao_evento_parts.append(f"\nTeste OTDR em curso: {'Sim' if otdr_em_curso else 'Nao'}.")

    equipe_acaso = "equipe de Campo" if (final_data.get('swap_fibra_info') or '').upper() == 'TIM' else "equipe SOM"
    local_now = LOCAL_TIMEZONE.localize(datetime.datetime.now())
    proxima_atualizacao_dt = local_now + datetime.timedelta(minutes=90)
    proxima_atualizacao_texto = proxima_atualizacao_dt.strftime("%H:%M")
    
    if otdr_em_curso:
        km_otdr_info = km_rompimento if km_rompimento else '[informado no teste OTDR]'
        descricao_evento_parts.append(f"\nKM do Rompimento: {km_otdr_info}")
        descricao_evento_parts.append(f'\nRompimento de fibra está próximo ao KM {km_otdr_info} de "{estado_origem_nome}" para "{estado_destino_nome}".')
        
    descricao_evento_parts.append(f"\n\nAcionado {equipe_acaso}. Próxima atualização às: {proxima_atualizacao_texto}.")
    
    if rascunho_texto:
        descricao_evento_parts.append(f"\n\n--- Rascunho ---\n{rascunho_texto}")

    final_descricao_evento = "".join(descricao_evento_parts)

    # --- 2. EXECUÇÃO DO SALVAMENTO (Se for POST ou se já tivermos tudo) ---
    if request.method == 'POST' or request.method == 'GET':
        # Nota: Permitimos GET aqui para casos de redirecionamento onde o usuário
        # já confirmou na etapa anterior, ou se você quiser auto-salvar.
        # Se preferir que o GET apenas mostre a confirmação, coloque esta lógica
        # dentro de um 'if request.method == 'POST':'
        
        # Mas como o fluxo do QuickAdd é direto, vamos tentar salvar se for POST
        # Se for GET, apenas mostramos o template de confirmação (padrão Flask)
        if request.method == 'GET':
             return render_template('quick_add_step2_evento.html', final_data=final_data, titulo_evento_sugerido=titulo_evento_sugerido, final_descricao_evento=final_descricao_evento, database=database, now=datetime.datetime.now())

        try:
            # Prepara Datas
            data_hora_abertura_evento_str_db = local_now.strftime("%Y-%m-%d %H:%M:%S")
            proxima_atualizacao_db_format = proxima_atualizacao_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Garante/Cria Elementos
            elemento1_id, _ = database.get_or_create_elemento(final_data['nome_elemento1'], final_data['nome_elemento1_curto'], final_data['elemento1_gerencia_id'], longa_distancia=final_data['elemento1_longa_distancia'], estado_atual_id=final_data['estado_origem_id'])
            elemento2_id, _ = database.get_or_create_elemento(final_data['nome_elemento2'], final_data['nome_elemento2_curto'], final_data['elemento2_gerencia_id'], longa_distancia=final_data['elemento2_longa_distancia'], estado_atual_id=final_data['estado_destino_id'])

            if elemento1_id is None or elemento2_id is None:
                raise Exception("Falha ao obter/criar elementos.")

            # Associações Básicas
            database.add_elemento_anel(elemento1_id, final_data['anel_id'])
            database.add_elemento_anel(elemento2_id, final_data['anel_id'])
            database.add_vizinho(elemento1_id, elemento2_id, final_data['accid_lc_comum'], final_data['swap_fibra_info'])
            
            # Cria Alarmes
            database.add_alarme(elemento1_id, final_data['tipo_alarme1_id'], f"Alarme inicial do fluxo para {final_data['nome_elemento1']}")
            alarme1_id_criado = database.get_last_alarme_id(elemento1_id, final_data['tipo_alarme1_id'])
            
            alarmes_criados_ids_elemento2 = []
            for tipo_alarme_id in final_data['tipo_alarmes2_ids']:
                database.add_alarme(elemento2_id, tipo_alarme_id, f"Alarme do fluxo para {final_data['nome_elemento2']}")
                alarme2_id_criado = database.get_last_alarme_id(elemento2_id, tipo_alarme_id)
                if alarme2_id_criado: alarmes_criados_ids_elemento2.append(alarme2_id_criado)

            all_alarm_ids = [alarme1_id_criado] + alarmes_criados_ids_elemento2
            all_element_ids = [elemento1_id, elemento2_id]

            # Define Tipo de Evento
            tipo_evento_db = "Alarme de Hardware" 
            if otdr_em_curso:
                tipo_evento_db = "Rompimento de Fibra"
            elif final_data.get('report_type') == 'link_capacidade':
                 tipo_evento_db = "Falha de Link de Capacidade"
            elif final_data['nome_elemento1'] != final_data['nome_elemento2']:
                tipo_evento_db = "Abertura de Enlace"
            elif database.get_tipo_alarme_by_id(final_data['tipo_alarme1_id'])['eh_abertura_enlace_trigger']:
                tipo_evento_db = "Abertura de Enlace"

            # Salva Evento
            novo_evento_id = database.add_evento(
                titulo_evento_sugerido, final_descricao_evento, all_alarm_ids, all_element_ids, 
                final_data['estado_origem_id'], final_data['estado_destino_id'], 
                final_data['teste_otdr_em_curso'], final_data['km_rompimento_otdr'], 
                proxima_atualizacao_db_format, tipo_evento_db, 
                data_hora_abertura=data_hora_abertura_evento_str_db
            )
            
            if novo_evento_id: 
                # 1. ATUALIZA VISUAL (Cor Vermelha/Laranja)
                expiration_time = datetime.datetime.now() + datetime.timedelta(hours=8)
                expiration_time_str = expiration_time.strftime("%Y-%m-%d %H:%M:%S")
                for elem_id in all_element_ids:
                    database.update_element_affected_status(elem_id, 1, expiration_time_str)

                # 2. SALVA NA ESTRUTURA (Cor Violeta Futura) - O PULO DO GATO
                if final_data.get('report_type') == 'link_capacidade' and len(all_element_ids) >= 2:
                    # Usa o swap informado ou o rascunho como identificador
                    swap_info = final_data.get('swap_fibra_info') or rascunho_texto or "Via Quick Add"
                    
                    # Salva usando texto livre (Atualizado para o novo banco)
                    database.add_link_capacidade(all_element_ids[0], all_element_ids[1], "N/A", "N/A", swap_info)
                    print(f"DEBUG QUICK ADD: Link de Capacidade salvo na tabela estrutural!")

                flash('Evento registrado com sucesso!', 'success')
                session.pop('final_quick_add_data', None)
                return redirect(url_for('correlacionar_alarmes_evento', evento_id=novo_evento_id))
            else:
                raise Exception("Erro ao salvar o evento no banco de dados.")

        except Exception as e:
            flash(f'Ocorreu um erro ao finalizar o cadastro: {e}.', 'danger')
            return render_template('quick_add_step2_evento.html', final_data=final_data, titulo_evento_sugerido=titulo_evento_sugerido, final_descricao_evento=final_descricao_evento, database=database, now=datetime.datetime.now())

    return render_template('quick_add_step2_evento.html', final_data=final_data, titulo_evento_sugerido=titulo_evento_sugerido, final_descricao_evento=final_descricao_evento, database=database, now=datetime.datetime.now())



# ADICIONADO: Nova Rota para Cadastro de Falha de Hardware
# ADICIONADO: Nova Rota para Cadastro de Falha de Hardware
@app.route('/cadastrar_falha_hardware', methods=['GET', 'POST'])
def cadastrar_falha_hardware():
    # A LINHA ABAIXO FOI CORRIGIDA
    tipos_alarmes_fmmt = [ta for ta in database.get_all_tipos_alarmes() if ta.get('equipe_responsavel') and ta['equipe_responsavel'].upper() == 'FMMT']
    
    gerencias = database.get_all_gerencias()
    aneis = database.get_all_aneis()
    estados_enlace = database.get_all_estados_enlace()

    prev_data = {}

    if request.method == 'POST':
        # --- APLICAÇÃO DA SEGURANÇA (SANITIZAÇÃO) ---
        # Limpa todos os campos de texto para evitar quebra de diagramas
        rascunho_texto = request.form.get('rascunho_texto', '').strip() # Rascunho geralmente permitimos caracteres, mas usamos strip
        
        # Campos de texto livre que precisam de proteção rigorosa
        novo_tipo_alarme_nome = sanitize_text(request.form.get('novo_tipo_alarme_nome', ''))
        nome_elemento = sanitize_text(request.form['nome_elemento']) # Campo Obrigatório
        novo_anel_nome = sanitize_text(request.form.get('novo_anel_nome', ''))
        novo_estado_atual_nome = sanitize_text(request.form.get('novo_estado_atual_nome', ''))
        # --------------------------------------------

        # Captura dos IDs (que não precisam de sanitização de texto, pois são números)
        tipo_alarme_id_selected = request.form.get('tipo_alarme_id_select')
        gerencia_id = request.form['gerencia_id']
        anel_id_selected = request.form.get('anel_id_select')
        estado_atual_id_selected = request.form.get('estado_atual_id_select')
        
        # --- ADICIONE ESTA VALIDAÇÃO ---
        if not is_valid_name(nome_elemento):
            flash('Erro: O nome do elemento não pode conter os caracteres :, <, >, " .', 'danger')
            # O 'return render_template' abaixo é para recarregar a página com o erro
            return render_template('cadastrar_falha_hardware.html',
                                tipos_alarmes_fmmt=[ta for ta in database.get_all_tipos_alarmes() if ta.get('equipe_responsavel') and ta['equipe_responsavel'].upper() == 'FMMT'],
                                gerencias=database.get_all_gerencias(),
                                aneis=database.get_all_aneis(),
                                estados_enlace=database.get_all_estados_enlace(),
                                prev_data=request.form,
                                database=database,
                                now=datetime.datetime.now())
        # --- FIM DA VALIDAÇÃO ---        

        final_tipo_alarme_id = None
        if novo_tipo_alarme_nome:
            final_tipo_alarme_id, _ = database.get_or_create_tipo_alarme(novo_tipo_alarme_nome, equipe_responsavel='FMMT', eh_abertura_enlace_trigger=0)
        elif tipo_alarme_id_selected:
            # CORREÇÃO AQUI: Removido o '1' do nome da variável
            final_tipo_alarme_id = int(tipo_alarme_id_selected)

        final_anel_id = None
        if novo_anel_nome:
            final_anel_id, _ = database.get_or_create_anel(novo_anel_nome)
        elif anel_id_selected:
            final_anel_id = int(anel_id_selected)

        final_estado_atual_id = None
        if novo_estado_atual_nome:
            final_estado_atual_id, _ = database.get_or_create_estado_enlace(novo_estado_atual_nome)
        elif estado_atual_id_selected:
            final_estado_atual_id = int(estado_atual_id_selected)


        if not final_tipo_alarme_id:
            flash('Por favor, selecione um Tipo de Alarme OU digite um nome para criar um novo.', 'danger')
        elif not nome_elemento or not gerencia_id or not final_anel_id:
            flash('Por favor, preencha todos os campos obrigatórios (Elemento, Gerência, Anel).', 'danger')
        else:
            try:
                nome_elemento_curto = nome_elemento[:17]
                
                elemento_id, _ = database.get_or_create_elemento(
                    nome_elemento,
                    nome_elemento_curto,
                    int(gerencia_id),
                    detentor_site_id=None,
                    longa_distancia=0,
                    estado_atual_id=final_estado_atual_id
                )

                if elemento_id is None:
                    raise Exception("Falha ao obter/criar elemento.")

                if final_anel_id:
                    database.add_elemento_anel(elemento_id, final_anel_id)

                database.add_alarme(elemento_id, final_tipo_alarme_id, f"Alarme de hardware: {nome_elemento}")
                alarme_id_criado = database.get_last_alarme_id(elemento_id, final_tipo_alarme_id)
                if alarme_id_criado is None:
                    raise Exception("Falha ao obter ID do alarme recém-criado.")

                alarme_nome_para_report = database.get_tipo_alarme_name_by_id(final_tipo_alarme_id)
                titulo_evento = f"Falha de Hardware - {nome_elemento} - Alarme {alarme_nome_para_report}"
                
                estado_nome_para_report = database.get_estado_enlace_name_by_id(final_estado_atual_id) if final_estado_atual_id else "[Estado não informado]"
                anel_nome_para_report = database.get_anel_by_id(final_anel_id)['nome_anel'] if final_anel_id and database.get_anel_by_id(final_anel_id) else "[Anel não informado]"

                descricao_evento_parts = []
                descricao_evento_parts.append(f"Solicito apoio técnico para aferir Alarme \"{alarme_nome_para_report}\" em: \"{estado_nome_para_report}\".")
                descricao_evento_parts.append(f"Elemento pertence ao Anel: \"{anel_nome_para_report}\"")
                
                if rascunho_texto:
                    descricao_evento_parts.append(f"\n--- Rascunho ---\n{rascunho_texto}")
                
                descricao_evento = "\n".join(descricao_evento_parts)

                local_now = LOCAL_TIMEZONE.localize(datetime.datetime.now())
                proxima_atualizacao_dt = local_now + datetime.timedelta(minutes=180)
                proxima_atualizacao_db_format = proxima_atualizacao_dt.strftime("%Y-%m-%d %H:%M:%S")
                data_hora_abertura_evento_str_db = local_now.strftime("%Y-%m-%d %H:%M:%S")

                # --- CORREÇÃO DA LÓGICA DE ML ---
                # Captura o ID do novo evento
                novo_evento_id = database.add_evento(
                    titulo=titulo_evento,
                    descricao=descricao_evento,
                    alarmes_ids=[alarme_id_criado],
                    elementos_ids=[elemento_id],
                    estado_origem_id=final_estado_atual_id,
                    estado_destino_id=final_estado_atual_id,
                    teste_otdr_em_curso=0,           # Parâmetro 7
                    km_rompimento_otdr=None,         # Parâmetro 8
                    proxima_atualizacao=proxima_atualizacao_db_format, # Parâmetro 9
                    tipo_evento="Alarme de Hardware", # Parâmetro 10
                    data_hora_abertura=data_hora_abertura_evento_str_db # Parâmetro 11
                )

                if novo_evento_id: # Se o evento foi criado (retornou um ID)
                    if final_estado_atual_id:
                        database.update_elemento_estado(elemento_id, final_estado_atual_id)
                    
                    flash('Evento de Falha de Hardware cadastrado! Agora, vamos correlacionar.', 'success')
                    # Redireciona para a NOVA tela de ensino
                    return redirect(url_for('correlacionar_alarmes_evento', evento_id=novo_evento_id))
                else:
                    raise Exception("Erro ao cadastrar o evento de falha de hardware.")
                # --- FIM DA CORREÇÃO ---
                
                
            except Exception as e:
                flash(f'Ocorreu um erro ao cadastrar a Falha de Hardware: {e}.', 'danger')
            
            prev_data = request.form.to_dict()

    return render_template('cadastrar_falha_hardware.html',
                           tipos_alarmes_fmmt=tipos_alarmes_fmmt,
                           gerencias=gerencias,
                           aneis=aneis,
                           estados_enlace=estados_enlace,
                           prev_data=prev_data,
                           database=database,
                           now=datetime.datetime.now())

    


# --- ROTAS PARA LINK DE CAPACIDADE ---

@app.route('/cadastrar_link_capacidade', methods=['GET', 'POST'])
def cadastrar_link_capacidade():
    elementos = database.get_all_elementos()
    gerencias = database.get_all_gerencias()

    if request.method == 'POST':
        # --- 1. Captura e Validação dos Dados ---
        nome_elem_a = sanitize_text(request.form.get('nome_elemento_a', ''))
        nome_elem_b = sanitize_text(request.form.get('nome_elemento_b', ''))
        facilidades_a = sanitize_text(request.form.get('facilidades_a', ''))
        facilidades_b = sanitize_text(request.form.get('facilidades_b', ''))
        
        # NOVO CAMPO DE TEXTO
        swap_fibra_capacidade = sanitize_text(request.form.get('swap_fibra_capacidade', ''))

        # Verifica nomes
        if not is_valid_name(nome_elem_a) or not is_valid_name(nome_elem_b):
            flash('Erro: Nomes inválidos.', 'danger')
            return redirect(url_for('cadastrar_link_capacidade'))

        gerencia_id = request.form.get('gerencia_id')
        rascunho_texto = request.form.get('rascunho_texto', '').strip()

        if not all([nome_elem_a, nome_elem_b, gerencia_id]):
            flash('Campos obrigatórios: Elementos e Gerência.', 'danger')
        else:
            try:
                # --- 2. Criação/Obtenção de Itens no Banco ---
                elem_a_id, _ = database.get_or_create_elemento(nome_elem_a, nome_elem_a[:17], int(gerencia_id))
                elem_b_id, _ = database.get_or_create_elemento(nome_elem_b, nome_elem_b[:17], int(gerencia_id))

                # SALVA O LINK COM O TEXTO DO SWAP
                if not database.add_link_capacidade(elem_a_id, elem_b_id, facilidades_a, facilidades_b, swap_fibra_capacidade):
                    raise Exception("Erro ao salvar no banco.")

                # --- 3. Geração do Evento ---
                gerencia_nome = database.get_gerencia_by_id(int(gerencia_id)) or "[Gerência]"
                prov_display = swap_fibra_capacidade if swap_fibra_capacidade else "Proprietário"

                titulo_evento = f"Falha no Link de Capacidade ({prov_display})"

                local_now = LOCAL_TIMEZONE.localize(datetime.datetime.now())
                proxima_atualizacao_dt = local_now + datetime.timedelta(minutes=90)
                
                descricao_parts = [
                    f"Falha no Link de Capacidade ({prov_display}) entre \"{nome_elem_a}\" e \"{nome_elem_b}\"",
                    f"Gerência: {gerencia_nome}",
                    f"\nElemento A: {nome_elem_a} + Facilidades: {facilidades_a or 'N/A'}",
                    "X",
                    f"Elemento B: {nome_elem_b} + Facilidades: {facilidades_b or 'N/A'}",
                    f"\nSwap/Info: {swap_fibra_capacidade}",
                    f"\nAcionado equipe SOM."
                ]
                if rascunho_texto:
                    descricao_parts.append(f"\n\n--- Rascunho ---\n{rascunho_texto}")

                novo_evento_id = database.add_evento(
                    titulo=titulo_evento,
                    descricao="\n".join(descricao_parts),
                    alarmes_ids=[], 
                    elementos_ids=[elem_a_id, elem_b_id],
                    estado_origem_id=None,
                    estado_destino_id=None,
                    proxima_atualizacao=proxima_atualizacao_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    tipo_evento="Falha de Link de Capacidade",
                    data_hora_abertura=local_now.strftime("%Y-%m-%d %H:%M:%S")
                )

                if novo_evento_id:
                    # Atualiza status visual (Cor)
                    exp_time = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
                    database.update_element_affected_status(elem_a_id, 1, exp_time)
                    database.update_element_affected_status(elem_b_id, 1, exp_time)
                    
                    flash('Link de capacidade cadastrado com sucesso!', 'success')
                    return redirect(url_for('correlacionar_alarmes_evento', evento_id=novo_evento_id))
                else:
                    raise Exception("Falha ao criar evento.")

            except Exception as e:
                flash(f'Ocorreu um erro: {e}', 'danger')

    return render_template('cadastrar_link_capacidade.html',
                           elementos=elementos,
                           gerencias=gerencias, # Detentores não é mais necessário aqui
                           prev_data=request.form if request.method == 'POST' else {},
                           now=datetime.datetime.now())
        

@app.route('/consultar_links_capacidade')
def consultar_links_capacidade():
    links = database.get_all_links_capacidade()
    return render_template('consultar_links_capacidade.html', 
                           links=links, 
                           now=datetime.datetime.now())

@app.route('/excluir_link_capacidade/<int:link_id>', methods=['POST'])
def excluir_link_capacidade(link_id):
    if database.excluir_link_capacidade(link_id):
        flash('Link de capacidade excluído com sucesso.', 'success')
    else:
        flash('Erro ao excluir o link de capacidade.', 'danger')
    return redirect(url_for('consultar_links_capacidade'))


# --- FUNÇÃO DE SANITIZAÇÃO DE DADOS ---
def sanitize_text(text):
    """
    Substitui caracteres perigosos (:, <, >, ", `, ') por hífen (-).
    Remove espaços extras no início e fim.
    """
    if not text:
        return ""
    
    # Lista de caracteres que quebram o HTML/JS ou SQL
    forbidden_chars = [':', '<', '>', '"', '`', "'"]
    
    for char in forbidden_chars:
        text = text.replace(char, '-')
        
    return text.strip()






# --- ROTAS PARA O PAINEL ADMINISTRATIVO (ADMIN DB) ---

@app.route('/admin_db')
def admin_db():
    # Busca a lista de tabelas para o menu
    try:
        tables = database.get_all_tables()
    except AttributeError:
        # Fallback caso a função não exista no database.py ainda
        tables = [] 
    return render_template('admin_db.html', tables=tables, now=datetime.datetime.now())

@app.route('/api/get_table_content/<table_name>')
def api_get_table_content(table_name):
    # Rota API que retorna os dados da tabela em JSON
    content = database.get_table_data(table_name)
    return jsonify(content)

@app.route('/api/admin_update', methods=['POST'])
def api_admin_update():
    data = request.json
    table = data.get('table')
    id_val = data.get('id')
    col = data.get('column')
    val = data.get('value')
    
    if database.admin_update_cell(table, id_val, col, val):
        return jsonify({'success': True})
    return jsonify({'success': False}), 500

@app.route('/api/admin_delete', methods=['POST'])
def api_admin_delete():
    data = request.json
    table = data.get('table')
    id_val = data.get('id')
    
    if database.admin_delete_row(table, id_val):
        return jsonify({'success': True})
    return jsonify({'success': False}), 500  

# GESTAO DE DADOS DATABOOK
@app.route('/gestao_databook', methods=['GET', 'POST'])
def gestao_databook():
    # Se for salvar (POST)
    if request.method == 'POST':
        try:
            elem_id = request.form.get('id')
            site_id = request.form.get('site_id', '').upper().strip()
            sigla_cidade = request.form.get('sigla_cidade', '').upper().strip()
            cidade = request.form.get('cidade', '').strip()
            uf = request.form.get('uf', '').upper().strip()
            endereco = request.form.get('endereco', '').strip()

            if database.update_element_databook(elem_id, site_id, sigla_cidade, cidade, uf, endereco):
                flash(f'Dados do Databook atualizados para o elemento ID {elem_id}!', 'success')
            else:
                flash('Erro ao atualizar o banco de dados.', 'danger')
                
        except Exception as e:
            flash(f'Erro técnico: {e}', 'danger')
        
        return redirect(url_for('gestao_databook'))

    # Se for apenas ver (GET)
    elementos = database.get_elementos_databook_completo()
    return render_template('gestao_databook.html', elementos=elementos, now=datetime.datetime.now())  


# --- ROTA DE DEBUG (FERRAMENTA DO DESENVOLVEDOR) ---
# --- ROTA DE DEBUG (FERRAMENTA DO DESENVOLVEDOR) ---
@app.route('/debug_panel')
def debug_panel():
    """
    Renderiza uma página simples com o resultado dos testes do debg.py
    """
    # 1. Teste de Hora
    time_info = debg.get_server_info()
    
    # 2. Teste de Integridade
    integrity_check = debg.check_broken_links()
    
    # 3. Busca por MÚLTIPLOS caracteres suspeitos
    caracteres_proibidos = ["'", ",", ".", ":", "/"]
    suspeitos = [] 
    
    for char in caracteres_proibidos:
        resultado_busca = debg.inspect_element_raw(char)
        suspeitos.extend(resultado_busca)
    
   # 4. Diagnóstico de Cores
    try:
        color_diagnosis = debg.diagnose_diagram_colors()
    except Exception as e:
        color_diagnosis = [f"Erro ao gerar diagnóstico: {str(e)}"]

    if color_diagnosis is None:
        color_diagnosis = ["A função retornou vazio (None). Verifique o debg.py."]
        
    # 5. Inspeção de Links de Capacidade
    try:
        link_inspection = debg.inspect_link_capacidade_table()
    except AttributeError:
        link_inspection = ["Erro: Função inspect_link_capacidade_table não encontrada no debg.py"]
    except Exception as e:
        link_inspection = [f"Erro ao inspecionar links: {str(e)}"]    

    try:
        ld_audit = debg.audit_longa_distancia()
    except Exception as e:
        ld_audit = [f"Erro ao auditar LD: {str(e)}"]
        
    try:
        stock_audit = debg.audit_stock_orphans()
    except Exception as e:
        stock_audit = [f"Erro auditoria estoque: {e}"]   
        
    # 9. ITEM 9
    try:
        hierarchy_audit = debg.audit_hierarchy()
    except Exception as e:
        hierarchy_audit = [f"Erro auditoria hierarquia: {e}"]   
        
    try:
        loader_diag = debg.diagnose_item_10_loader()
    except:
        loader_diag = ["Erro no diagnóstico 10.1"]   
        
    try:
        accent_audit = debg.audit_accents()
    except:
        accent_audit = ["Erro na auditoria de acentos"]           

    # --- NOVO: ITEM 12.1 - BUSCA ROTEADORES PARA O RAIO-X ---
    try:
        routers_list = database.get_all_routers_debug()
    except Exception as e:
        print(f"Erro ao buscar routers debug: {e}")
        routers_list = [] # Evita quebrar a página se der erro no banco
    # --------------------------------------------------------
        
    # Atualize o retorno para incluir 'routers_list'
    return render_template('debug_panel.html', 
                           time_info=time_info, 
                           integrity_check=integrity_check,
                           suspeitos=suspeitos,
                           color_diagnosis=color_diagnosis,
                           link_inspection=link_inspection,
                           ld_audit=ld_audit,
                           stock_audit=stock_audit,
                           hierarchy_audit=hierarchy_audit,
                           loader_diag=loader_diag,
                           accent_audit=accent_audit,
                           routers_list=routers_list) # <--- PASSANDO AQUI
                        
    
@app.route('/api/debug/move_stock', methods=['POST'])
def api_move_stock():
    data = request.json
    elemento_id = data.get('id')
    nome = data.get('nome')
    
    # Chama a função do database para mover
    if database.move_to_stock(elemento_id, motivo="Via Debug Panel"):
        return jsonify({"success": True, "message": f"{nome} movido para Estoque/Sobras."})
    else:
        return jsonify({"success": False, "message": "Erro ao mover."}), 500


@app.route('/debug_ld')
def debug_ld():
    dados = database.debug_get_longa_distancia_network()
    return render_template('debug_ld.html', dados=dados)


@app.route('/debug/export_links_csv')
def debug_export_links_csv():
    """Gera e baixa o CSV dos links de capacidade."""
    data = database.export_links_capacidade_csv()
    
    # Cria o CSV na memória
    si = io.StringIO()
    if data:
        cw = csv.DictWriter(si, fieldnames=data[0].keys(), delimiter=';')
        cw.writeheader()
        cw.writerows(data)
    else:
        # CSV vazio com cabeçalho se não tiver dados
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Nome Elemento A", "Nome Elemento B", "Gerencia", "Facilidades A", "Facilidades B", "Swap/Provedor", "Aneis (Ref)", "Estado A", "Estado B"])

    output = io.BytesIO()
    # Codificação utf-8-sig para abrir com acentos no Excel
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"backup_links_capacidade_{timestamp}.csv"
    )
    
@app.route('/debug/import_links_csv', methods=['POST'])
def debug_import_links_csv():
    """Recebe o CSV e restaura os links."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nome de arquivo vazio'})

    try:
        # Lê o arquivo
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        csv_input = csv.DictReader(stream, delimiter=';')
        
        rows = list(csv_input)
        sucessos, erros = database.import_links_capacidade_from_csv_data(rows)
        
        msg = f"Importação concluída! {sucessos} links criados."
        if erros:
            msg += f" {len(erros)} erros (veja console/log)."
            print("Erros na importação:", erros)
            
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f"Erro ao processar CSV: {str(e)}"}), 500    

    
@app.route('/api/debug/reset_links', methods=['POST'])
def api_debug_reset_links():
    """
    Rota chamada pelo botão do Debug Panel para resetar a tabela.
    """
    resultado = debg.reset_link_capacidade_table()
    
    if resultado['success']:
        return jsonify(resultado)
    else:
        return jsonify(resultado), 500
    

# TUNEL DO TEMPO     
@app.route('/api/debug/expire_alarms', methods=['POST'])
def api_debug_expire_alarms():
    """
    Rota para expirar alarmes imediatamente.
    """
    resultado = debg.force_expire_alarms()
    
    if resultado['success']:
        return jsonify(resultado)
    else:
        return jsonify(resultado), 500    
    
    
@app.route('/api/debug/fix_hierarchy', methods=['POST'])
def api_fix_hierarchy():
    data = request.json
    elemento_id = data.get('id')
    nome = data.get('nome')
    
    if database.fix_hierarchy_status(elemento_id):
        return jsonify({"success": True, "message": f"Sucesso! {nome} agora é Longa Distância."})
    else:
        return jsonify({"success": False, "message": "Erro ao corrigir."}), 500    


# --- ROTAS PARA O CONSTRUTOR DE DATABOOK (ITEM 10) ---

@app.route('/api/debug/databook/get_section/<int:anel_id>')
def api_databook_get_section(anel_id):
    """Retorna todos os dados para montar o Databook Builder (Com Agrupamento Inteligente)."""
    
    # 1. Metadados do Cabeçalho
    metadata = database.get_anel_metadata(anel_id)
    
    # 2. Elementos Brutos do Anel
    elementos_brutos = database.get_elementos_no_anel(anel_id)
    
    # --- LÓGICA DE AGRUPAMENTO (OPTION A) ---
    grouped_nodes = {} # Chave: Nome Curto (17 chars), Valor: Lista de elementos
    node_id_map = {}   # De: ID Original -> Para: ID do Representante
    
    for e in elementos_brutos:
        # Define o nome curto para agrupamento (ex: CXS-ACZ01-CSW02)
        # Pega os primeiros 17 caracteres ou o nome todo se for menor
        short_name = e['nome_elemento'][:17] if len(e['nome_elemento']) >= 17 else e['nome_elemento']
        
        if short_name not in grouped_nodes:
            grouped_nodes[short_name] = []
        grouped_nodes[short_name].append(e)

    nodes = []
    
    # 3. Processa cada Grupo para criar 1 Nó Visual
    for short_name, grupo in grouped_nodes.items():
        # O representante é o primeiro da lista (usaremos o ID dele para o desenho)
        representante = grupo[0] 
        
        # Mapeia todos os IDs do grupo para o ID do representante (para os links funcionarem)
        for membro in grupo:
            node_id_map[membro['id']] = representante['id']

        # Busca detalhes extras do representante (ícone, passivo, cidade, etc)
        detalhe_rep = database.get_elemento_by_id(representante['id']) 
        
        # --- GERAÇÃO DO HTML TÉCNICO (QUEM CONECTA COM QUEM) ---
        # Isso gera o conteúdo detalhado para o Painel Lateral
        html_detalhes = f"<div style='border-bottom:1px solid #ccc; margin-bottom:5px; padding-bottom:5px;'><b>{short_name}</b></div>"
        
        for membro in grupo:
            # Busca vizinhos deste membro específico (ex: Line 1)
            vizinhos = database.get_vizinhos_do_elemento(membro['id'])
            
            html_detalhes += f"""
            <div style='background:#f9f9f9; border:1px solid #ddd; padding:5px; margin-bottom:5px; border-radius:4px; font-size:11px;'>
                <div style='font-weight:bold; color:#333;'>{membro['nome_elemento']}</div>
            """
            
            if vizinhos:
                html_detalhes += "<div style='margin-top:2px; color:#000;'>↳ <b>Conecta com:</b></div>"
                for v in vizinhos:
                    html_detalhes += f"<div style='padding-left:5px;'>🔗 {v['nome_elemento']}<br><span style='color:#777; font-size:10px;'>({v['accid_lc'] or '--'})</span></div>"
            else:
                html_detalhes += "<div style='color:#999; font-style:italic;'>Sem conexões ativas</div>"
                
            html_detalhes += "</div>"
        # -------------------------------------------------------

        # --- DEFINIÇÃO DA FORMA (SHAPE) ---
        shape = 'square' # Padrão
        icone_db = detalhe_rep.get('tipo_icone', 'roadm')
        
        if icone_db == 'switch': shape = 'triangle'
        elif icone_db == 'foadm': shape = 'box'
        elif icone_db == 'passivo': shape = 'dot'
        
        # Cor
        color = '#97c2fc'
        if detalhe_rep.get('is_passive') == 1:
            color = '#dddddd' 
            
        node_data = {
            'id': representante['id'],
            'label': short_name, # Rótulo padrão (será a Cidade se o JS processar)
            'shape': shape,
            'color': color,
            'vendor': database.detect_vendor_by_name(representante['nome_elemento']),
            
            # DADOS DO DATABOOK (Do representante)
            'cidade': detalhe_rep.get('cidade'), 
            'site_id': detalhe_rep.get('site_id'),
            'uf': detalhe_rep.get('uf'),
            'endereco': detalhe_rep.get('endereco'),
            'detentor': database.get_detentor_site_name_by_id(detalhe_rep.get('detentor_site_id')),
            
            # CAMPO ESPECIAL: O HTML com os detalhes de conexão
            'html_tecnico': html_detalhes
        }

        # --- INJETA COORDENADAS SE EXISTIREM ---
        if representante.get('x') is not None and representante.get('y') is not None:
            node_data['x'] = representante['x']
            node_data['y'] = representante['y']
            node_data['physics'] = False 

        nodes.append(node_data)

    # 4. Conexões (Edges) Agrupadas
    edges = []
    processed_pairs = set()
    
    # Verifica conexões de TODOS os elementos brutos
    for e in elementos_brutos:
        vizinhos = database.get_vizinhos_do_elemento(e['id'])
        
        for v in vizinhos:
            # Verifica se o vizinho faz parte do desenho atual (está mapeado)
            if v['id'] in node_id_map:
                # Descobre quem são os "Representantes" (Grupos) de Origem e Destino
                grp_origem = node_id_map[e['id']]
                grp_destino = node_id_map[v['id']]
                
                # Se forem grupos diferentes, cria o link
                if grp_origem != grp_destino:
                    pair_key = tuple(sorted([grp_origem, grp_destino]))
                    
                    if pair_key not in processed_pairs:
                        # Busca distância no banco
                        conn = sqlite3.connect(database.DATABASE_NAME)
                        cur = conn.cursor()
                        cur.execute("SELECT distancia_km FROM vizinhanca WHERE elemento_origem_id=? AND elemento_destino_id=?", (e['id'], v['id']))
                        row = cur.fetchone()
                        conn.close()
                        
                        km_label = f"{row[0]} km" if row and row[0] else ""
                        
                        edges.append({
                            'from': grp_origem, 
                            'to': grp_destino,
                            'label': km_label,
                            'font': {'align': 'top'},
                            'color': {'color': '#848484'}
                        })
                        processed_pairs.add(pair_key)

    return jsonify({'metadata': metadata, 'nodes': nodes, 'edges': edges})


@app.route('/api/debug/databook/save_position', methods=['POST'])
def api_databook_save_position():
    
    if not SERVER_MODE_ENGINEERING:
        return jsonify({"success": False, "message": "Modo Engenharia BLOQUEADO. Ative no Painel de Debug."}), 403
    
    """Salva a posição X,Y de um nó após o arraste."""
    data = request.json
    anel_id = data.get('anel_id')
    elemento_id = data.get('elemento_id')
    x = data.get('x')
    y = data.get('y')
    
    # Chama a função que você colocou corretamente no database.py
    if database.save_element_position(anel_id, elemento_id, x, y):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Erro ao salvar posição"}), 500


@app.route('/api/debug/databook/save_metadata', methods=['POST'])
def api_databook_save_metadata():
    data = request.json
    if database.save_anel_metadata(data):
        return jsonify({"success": True, "message": "Cabeçalho salvo!"})
    return jsonify({"success": False, "message": "Erro ao salvar."}), 500

@app.route('/api/debug/databook/add_node', methods=['POST'])
def api_databook_add_node():
    data = request.json
    nome = data.get('nome')
    anel_id = data.get('anel_id')
    tipo_icone = data.get('tipo_icone', 'roadm')
    is_passive = int(data.get('is_passive', 0))
    
    # 1. Cria ou recupera o elemento (Upsert)
    # Usa Longa Distancia = 1 pois é Databook Builder
    elem_id = database.add_elemento(nome, nome, 1, None, longa_distancia=1)
    
    if elem_id:
        # 2. Atualiza ícone e flag passivo
        database.update_element_icon(elem_id, tipo_icone, is_passive)
        
        # 3. Vincula ao Anel (Fundamental para aparecer no filtro)
        database.add_elemento_anel(elem_id, anel_id)
        
        return jsonify({"success": True, "message": "Elemento adicionado!"})
    return jsonify({"success": False, "message": "Erro ao criar elemento."}), 500

@app.route('/api/debug/databook/save_link', methods=['POST'])
def api_databook_save_link():
    
    if not SERVER_MODE_ENGINEERING:
        return jsonify({"success": False, "message": "Modo Engenharia BLOQUEADO."}), 403
    
    data = request.json
    origem_id = data.get('origem_id')
    destino_id = data.get('destino_id')
    km = data.get('km')
    
    # Cria vizinhança
    if database.add_vizinho(origem_id, destino_id):
        # Atualiza o KM
        database.update_link_distance(origem_id, destino_id, km)
        return jsonify({"success": True, "message": "Link criado com sucesso!"})
    return jsonify({"success": False, "message": "Erro ao criar link."}), 500


@app.route('/api/search_anel')
def api_search_anel():
    """
    Rota utilizada pelo Seletor de Anéis na visualização.
    - Se q='': Retorna TODOS os anéis (Modo Normal).
    - Se q='WDM_LD': Retorna anéis que contenham esse texto (Modo Databook).
    """
    termo = request.args.get('q', '').strip()
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        if not termo:
            # Modo Normal: Traz todos (Limitado a 500 para segurança de UI)
            cursor.execute("SELECT id, nome_anel FROM aneis ORDER BY nome_anel ASC LIMIT 500")
        else:
            # Modo Databook ou Busca Específica: Filtra pelo nome
            cursor.execute("SELECT id, nome_anel FROM aneis WHERE nome_anel LIKE ? ORDER BY nome_anel ASC", (f'%{termo}%',))
            
        resultados = [dict(row) for row in cursor.fetchall()]
        return jsonify(resultados)
        
    except Exception as e:
        return jsonify([])
    finally:
        conn.close()

@app.route('/api/debug/fix_accent', methods=['POST'])
def api_fix_accent():
    data = request.json
    
    sucesso, mensagem = database.fix_accented_name(data['id'], data['novo_nome'])
    
    if sucesso:
        return jsonify({"success": True, "message": mensagem})
    else:
        return jsonify({"success": False, "message": mensagem}), 500
    
    
# --- ROTAS DE EXCLUSÃO PARA O BUILDER (ITEM 10) ---

@app.route('/api/debug/databook/delete_link', methods=['POST'])
def api_databook_delete_link():
    
    if not SERVER_MODE_ENGINEERING:
        return jsonify({"success": False, "message": "Modo Engenharia BLOQUEADO."}), 403
    
    data = request.json
    origem_id = data.get('origem_id')
    destino_id = data.get('destino_id')
    
    # Remove da tabela de vizinhança
    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Deleta nos dois sentidos para garantir
        cursor.execute("DELETE FROM vizinhanca WHERE elemento_origem_id=? AND elemento_destino_id=?", (origem_id, destino_id))
        cursor.execute("DELETE FROM vizinhanca WHERE elemento_origem_id=? AND elemento_destino_id=?", (destino_id, origem_id))
        conn.commit()
        return jsonify({"success": True, "message": "Link removido!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/debug/databook/remove_node_from_ring', methods=['POST'])
def api_databook_remove_node_from_ring():
    data = request.json
    elemento_id = data.get('elemento_id')
    anel_id = data.get('anel_id')
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # 1. Remove a associação com este anel
        cursor.execute("DELETE FROM elemento_anel WHERE elemento_id=? AND anel_id=?", (elemento_id, anel_id))
        
        # 2. Opcional: Remove links órfãos desse elemento (Segurança)
        # Se ele não estiver em mais nenhum anel, talvez devêssemos apagar vizinhança?
        # Por enquanto, vamos apenas tirar do anel para não quebrar outros desenhos.
        
        conn.commit()
        return jsonify({"success": True, "message": "Elemento removido do desenho!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


# --- ROTAS DE CONTROLE DE MODO ENGENHARIA ---

@app.route('/api/admin/get_engineering_mode')
def get_engineering_mode():
    return jsonify({'enabled': SERVER_MODE_ENGINEERING})

@app.route('/api/admin/toggle_engineering_mode', methods=['POST'])
def toggle_engineering_mode():
    global SERVER_MODE_ENGINEERING
    data = request.json
    # Define o modo com base no que veio do botão (True/False)
    SERVER_MODE_ENGINEERING = data.get('enabled', False)
    state = "HABILITADO 🔓" if SERVER_MODE_ENGINEERING else "BLOQUEADO 🔒"
    print(f"--- MODO ENGENHARIA {state} ---")
    return jsonify({'success': True, 'enabled': SERVER_MODE_ENGINEERING})
        

@app.route('/api/debug/databook/update_node_details', methods=['POST'])
def api_databook_update_node_details():
    data = request.json
    elemento_id = data.get('id')
    novo_nome = data.get('nome')
    novo_icone = data.get('tipo_icone')
    is_passive = int(data.get('is_passive', 0))
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Atualiza nome, ícone e flag passivo
        cursor.execute("""
            UPDATE elementos 
            SET nome_elemento = ?, tipo_icone = ?, is_passive = ? 
            WHERE id = ?
        """, (novo_nome, novo_icone, is_passive, elemento_id))
        conn.commit()
        return jsonify({"success": True, "message": "Dados atualizados!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()
        
# --- NOVAS ROTAS PARA O PAINEL DE EDIÇÃO LATERAL (DATABOOK) ---

@app.route('/api/debug/databook/get_node_details/<int:elemento_id>')
def api_databook_get_node_details(elemento_id):
    """
    Retorna os dados cadastrais do elemento para preencher o formulário lateral.
    Nota: Não precisa de trava de segurança pois é apenas leitura.
    """
    elem = database.get_elemento_by_id(elemento_id)
    if elem:
        return jsonify({
            'success': True,
            'id': elem['id'],
            'nome_elemento': elem['nome_elemento'],
            'site_id': elem.get('site_id', ''),
            'cidade': elem.get('cidade', ''),
            'uf': elem.get('uf', ''),
            'endereco': elem.get('endereco', ''),
            'detentor': database.get_detentor_site_name_by_id(elem.get('detentor_site_id'))
        })
    return jsonify({'success': False, 'message': 'Elemento não encontrado'}), 404


@app.route('/api/debug/databook/save_node_details', methods=['POST'])
def api_databook_save_node_details():
    # --- SEGURANÇA: SÓ SALVA SE MODO ENGENHARIA ESTIVER LIGADO ---
    if not SERVER_MODE_ENGINEERING:
        return jsonify({"success": False, "message": "Modo Engenharia BLOQUEADO. Ative no Painel de Debug."}), 403
    # -------------------------------------------------------------

    """Salva os dados editados no painel lateral."""
    data = request.json
    try:
        # Extrai a sigla do Site ID (primeiros caracteres) se não for passada explicitamente
        site_id = data.get('site_id', '').strip().upper()
        sigla_cidade = site_id[:4] if len(site_id) >= 4 else site_id
        
        nome_detentor = data.get('detentor', '').strip().upper()
        detentor_id = None
        
        if nome_detentor:
            # Conecta para achar ou criar o ID do detentor
            conn = sqlite3.connect(database.DATABASE_NAME)
            cursor = conn.cursor()
            try:
                # 1. Tenta achar o ID
                cursor.execute("SELECT id FROM detentores_site WHERE nome_detentor = ?", (nome_detentor,))
                res = cursor.fetchone()
                if res:
                    detentor_id = res[0]
                else:
                    # 2. Se não existe, cria!
                    cursor.execute("INSERT INTO detentores_site (nome_detentor) VALUES (?)", (nome_detentor,))
                    conn.commit()
                    detentor_id = cursor.lastrowid
            finally:
                conn.close()
        
        sucesso = database.update_element_databook(
            elem_id=data.get('id'),
            site_id=site_id,
            sigla_cidade=sigla_cidade,
            cidade=data.get('cidade', '').strip(),
            uf=data.get('uf', '').strip().upper(),
            endereco=data.get('endereco', '').strip(),
            detentor_site_id=detentor_id
            
        )
        
        if sucesso:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Erro ao atualizar no banco.'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500        
        
# =========================================================================
# --- NOVAS ROTAS DO MÓDULO TRANSPORTE DADOS (BBIP) ---
# =========================================================================

# 1. API para buscar dados auxiliares (Status, Fabricantes)
@app.route('/api/dados/get_auxiliary_info')
def api_dados_get_auxiliary_info():
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, nome_status FROM status_dados ORDER BY id")
        status_list = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT id, nome_fabricante FROM fabricantes_dados ORDER BY nome_fabricante")
        fabricantes_list = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT id, nome_alarme FROM alarmes_dados ORDER BY nome_alarme")
        alarmes_list = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({
            'status': status_list, 
            'fabricantes': fabricantes_list, 
            'alarmes': alarmes_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# 2. API para buscar Roteadores (Autocomplete)
@app.route('/api/dados/search_router')
def api_dados_search_router():
    query = request.args.get('q', '').strip()
    if len(query) < 2: return jsonify([])
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, hostname, site_id, ip_gerencia 
            FROM equipamentos_dados 
            WHERE hostname LIKE ? 
            LIMIT 10
        """, (f'%{query}%',))
        results = [dict(row) for row in cursor.fetchall()]
        return jsonify(results)
    finally:
        conn.close()
        

# =========================================================================
# --- ROTAS DE CADASTRO AUXILIAR DE DADOS ---
# =========================================================================

# 1. Cadastro de Fabricantes (Cisco, Huawei, etc)
@app.route('/cadastrar_fabricante_dados', methods=['POST'])
def cadastrar_fabricante_dados():
    nome_fabricante = request.form.get('nome_fabricante', '').strip().upper()
    
    if not nome_fabricante:
        flash('Nome do fabricante é obrigatório.', 'danger')
        return redirect(url_for('cadastrar_gerencia')) # Volta para a mesma tela
        
    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO fabricantes_dados (nome_fabricante) VALUES (?)", (nome_fabricante,))
        conn.commit()
        flash(f'Fabricante "{nome_fabricante}" cadastrado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Erro: Fabricante "{nome_fabricante}" já existe.', 'warning')
    except Exception as e:
        flash(f'Erro técnico: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('cadastrar_gerencia')) # Redireciona para a tela unificada



# --- ROTA QUE ESTÁ FALTANDO: CADASTRO DE ALARMES DE DADOS (BLOCO AZUL) ---
@app.route('/cadastrar_alarme_dados', methods=['POST'])
def cadastrar_alarme_dados():
    nome_alarme = request.form.get('nome_alarme_dados', '').strip().upper()
    
    if not nome_alarme:
        flash('Nome do alarme é obrigatório.', 'danger')
        # Redireciona de volta para a página de cadastro
        return redirect(url_for('cadastrar_ou_editar_tipo_alarme'))
        
    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO alarmes_dados (nome_alarme) VALUES (?)", (nome_alarme,))
        conn.commit()
        flash(f'Alarme de Dados "{nome_alarme}" cadastrado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Erro: Alarme "{nome_alarme}" já existe.', 'warning')
    except Exception as e:
        flash(f'Erro técnico: {e}', 'danger')
    finally:
        conn.close()
        
    # Redireciona para a tela de admin de alarmes
    return redirect(url_for('cadastrar_ou_editar_tipo_alarme'))


# 2. Cadastro de Alarmes de Dados (BBIP)
# --- ROTA PARA CADASTRAR TIPO DE FALHA DE CIRCUITO (SERVIÇO) ---
@app.route('/cadastrar_tipo_falha', methods=['POST'])
def cadastrar_tipo_falha():
    nome_falha = request.form.get('nome_tipo_falha', '').strip()
    
    if not nome_falha:
        flash('A descrição da falha é obrigatória.', 'danger')
        # Retorna para a tela de admin de alarmes
        return redirect(url_for('cadastrar_ou_editar_tipo_alarme'))

    # ATUALIZAÇÃO: Salva na tabela correta tipos_falha_circuito
    if database.add_tipo_falha_circuito(nome_falha):
        flash(f'Tipo de Falha "{nome_falha}" cadastrado com sucesso!', 'success')
    else:
        flash(f'Erro: O tipo de falha "{nome_falha}" já existe.', 'warning')

    return redirect(url_for('consultar_tipos_alarmes'))


# 3. Rota Principal de Cadastro de Circuito de Dados
# ATUALIZADA: Corrige o erro de "Database Locked" usando a mesma conexão para tudo
# 3. Rota Principal de Cadastro de Circuito de Dados
# ATUALIZADA: Com sanitização de texto e proteção contra Database Lock
@app.route('/cadastrar_circuito_dados', methods=['POST'])
def cadastrar_circuito_dados():
    data = request.json
    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        # A. Cria/Recupera Roteador Origem (COM SANITIZAÇÃO)
        hostname_origem = sanitize_text(data.get('origem_hostname', ''))
        fab_id_origem = data.get('origem_fabricante_id')
        
        cursor.execute("SELECT id FROM equipamentos_dados WHERE hostname = ?", (hostname_origem,))
        res = cursor.fetchone()
        if res:
            id_origem = res[0]
        else:
            cursor.execute("INSERT INTO equipamentos_dados (hostname, fabricante_id) VALUES (?, ?)", (hostname_origem, fab_id_origem))
            id_origem = cursor.lastrowid
            
        # B. Cria/Recupera Roteador Destino (Se houver) (COM SANITIZAÇÃO)
        id_destino = None
        hostname_destino = sanitize_text(data.get('destino_hostname', ''))
        if hostname_destino:
            fab_id_destino = data.get('destino_fabricante_id')
            cursor.execute("SELECT id FROM equipamentos_dados WHERE hostname = ?", (hostname_destino,))
            res = cursor.fetchone()
            if res:
                id_destino = res[0]
            else:
                cursor.execute("INSERT INTO equipamentos_dados (hostname, fabricante_id) VALUES (?, ?)", (hostname_destino, fab_id_destino))
                id_destino = cursor.lastrowid
        
        # C. Cria o Circuito (Incidente)
        # Sanitiza ACCID e Observações
        accid_sanitized = sanitize_text(data.get('accid', ''))
        obs_sanitized = data.get('observacoes', '') # Observações pode ter caracteres especiais, mas idealmente limpamos aspas perigosas se for usar em JS
        # obs_sanitized = sanitize_text(obs_sanitized) # Descomente se quiser ser rígido

        cursor.execute("""
            INSERT INTO circuitos_dados (
                accid, roteador_origem_id, roteador_destino_id, 
                status_origem_id, status_destino_id, 
                alarme_origem_id, alarme_destino_id, 
                tipo_falha, observacoes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            accid_sanitized, id_origem, id_destino,
            data.get('origem_status_id'), data.get('destino_status_id'),
            data.get('origem_alarme_id'), data.get('destino_alarme_id'),
            data.get('tipo_falha'), obs_sanitized
        ))
        circuito_id = cursor.lastrowid
        
        # D. Salva a Rota TX (Saltos)
        hops = data.get('rota_tx_ids', []) # Lista de IDs de elementos TX
        rota_textual = [] 
        
        for i, elem_tx_id in enumerate(hops):
            cursor.execute("""
                INSERT INTO rota_circuitos_tx (circuito_dados_id, ordem_salto, elemento_tx_id)
                VALUES (?, ?, ?)
            """, (circuito_id, i+1, elem_tx_id))
            # Busca nome para o relatório textual
            cursor.execute("SELECT nome_elemento FROM elementos WHERE id = ?", (elem_tx_id,))
            res_nome = cursor.fetchone()
            if res_nome: rota_textual.append(res_nome[0])
            
        # E. GERA O TEXTO E CRIA O EVENTO NA LISTA GERAL (USANDO A MESMA CONEXÃO!)
        # Helper interno para buscar nomes usando o CURSOR ATUAL
        def get_name_internal(table, col, id_val):
            if not id_val: return "N/A"
            cursor.execute(f"SELECT {col} FROM {table} WHERE id=?", (id_val,))
            r = cursor.fetchone()
            return r[0] if r else "N/A"

        accid_display = accid_sanitized or "N/A"
        tipo_falha = data.get('tipo_falha')
        
        stA = get_name_internal('status_dados', 'nome_status', data.get('origem_status_id'))
        fabA = get_name_internal('fabricantes_dados', 'nome_fabricante', data.get('origem_fabricante_id'))
        almA = get_name_internal('alarmes_dados', 'nome_alarme', data.get('origem_alarme_id'))
        
        dest_info = "(Destino: Ponta única/Cliente/Nuvem)"
        if id_destino:
            stB = get_name_internal('status_dados', 'nome_status', data.get('destino_status_id'))
            fabB = get_name_internal('fabricantes_dados', 'nome_fabricante', data.get('destino_fabricante_id'))
            almB = get_name_internal('alarmes_dados', 'nome_alarme', data.get('destino_alarme_id'))
            dest_info = f" indo ate (Roteador B (Destino): {hostname_destino}. Status: {stB}, Fabricante: {fabB}, Alarme Ativo: {almB})"
            
        rota_str = " -> ".join(rota_textual) if rota_textual else "Não informada"

        descricao_final = f"""Solicito apoio técnico para verificação de alarme no ACCID Dados (Circuito): "{accid_display}" com a falha de "Tipo de Falha: {tipo_falha}".

O circuito começa em (Roteador A (Origem): {hostname_origem}. Status: {stA}, Fabricante: {fabA}, Alarme Ativo: {almA}){dest_info}.

Onde a rota física passa por (ROTA FÍSICA (ELEMENTOS TX UTILIZADOS)):
{rota_str}

Informações Extras / Rascunho:
{obs_sanitized}
"""
        # --- INSERÇÃO DIRETA NA TABELA EVENTOS (Evita o Lock) ---
        local_now = datetime.datetime.now(LOCAL_TIMEZONE)
        titulo_evento = f"Incidente DADOS - ACCID: {accid_display} - {tipo_falha}"
        data_abertura = local_now.strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO eventos (
                titulo, descricao, data_hora_abertura, 
                estado_origem_id, estado_destino_id, 
                teste_otdr_em_curso, km_rompimento_otdr, 
                proxima_atualizacao, tipo_evento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            titulo_evento, descricao_final, data_abertura, 
            None, None, 0, None, None, "DADOS"
        ))
        
        novo_evento_id = cursor.lastrowid
        
        # F. VÍNCULO: Atualiza o ID do Evento na tabela Circuitos
        try:
            cursor.execute("ALTER TABLE circuitos_dados ADD COLUMN evento_id INTEGER")
        except:
            pass # Coluna já existe

        cursor.execute("UPDATE circuitos_dados SET evento_id = ? WHERE id = ?", (novo_evento_id, circuito_id))
            
        conn.commit()
        
        # RETORNA O ID DO NOVO EVENTO PARA O FRONT-END REDIRECIONAR
        return jsonify({
            'success': True, 
            'message': 'Circuito de Dados registrado e Evento criado com sucesso!',
            'redirect_url': url_for('detalhes_evento_dados', evento_id=novo_evento_id)
        })
        
    except Exception as e:
        conn.rollback()
        print(f"ERRO CRÍTICO NO CADASTRO DE DADOS: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# --- ROTA PARA CRIAR ELEMENTO PROVISÓRIO (DADOS) ---
@app.route('/api/criar_elemento_provisorio', methods=['POST'])
def api_criar_elemento_provisorio():
    data = request.json
    nome_bruto = data.get('nome_elemento', '').strip()
    nome_sanitizado = sanitize_text(nome_bruto) # Segurança
    
    if not nome_sanitizado:
        return jsonify({'success': False, 'message': 'Nome inválido.'}), 400

    conn = sqlite3.connect(database.DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        # 1. Verifica se já existe (para evitar duplicidade no clique duplo)
        cursor.execute("SELECT id, nome_elemento FROM elementos WHERE nome_elemento = ?", (nome_sanitizado,))
        existente = cursor.fetchone()
        if existente:
            return jsonify({'success': True, 'element': {'id': existente[0], 'nome_elemento': existente[1]}})

        # 2. Busca uma Gerência "Default" (Genérica) ou a primeira disponível
        # Tenta achar uma gerência chamada 'GENERICO', 'OUTROS' ou pega a ID 1
        cursor.execute("SELECT id FROM gerencias WHERE nome_gerencia LIKE '%GENERICO%' OR nome_gerencia LIKE '%OUTROS%' LIMIT 1")
        gerencia_res = cursor.fetchone()
        
        if gerencia_res:
            gerencia_id = gerencia_res[0]
        else:
            # Se não tem genérica, pega a primeira que existir (ex: a ID 1)
            cursor.execute("SELECT id FROM gerencias LIMIT 1")
            first_ger = cursor.fetchone()
            gerencia_id = first_ger[0] if first_ger else 1 # Fallback total

        # 3. Insere o Elemento Provisório (Cinza/Passivo)
        # is_passive = 1 (Cinza no mapa)
        # longa_distancia = 0
        cursor.execute("""
            INSERT INTO elementos (
                nome_elemento, nome_elemento_curto, gerencia_id, 
                tipo_icone, is_passive, longa_distancia
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_sanitizado, nome_sanitizado[:17], gerencia_id, 'passivo', 1, 0))
        
        novo_id = cursor.lastrowid
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Elemento provisório criado!',
            'element': {'id': novo_id, 'nome_elemento': nome_sanitizado}
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()
        
        
        
# --- ROTA PARA O RAIO-X DA FIBRA ---
@app.route('/api/diagrama/raio_x_link', methods=['POST'])
def api_raio_x_link():
    data = request.json
    origem = data.get('origem') # Nome do nó de origem (do diagrama)
    destino = data.get('destino') # Nome do nó de destino
    
    if not origem or not destino:
        return jsonify({'success': False, 'message': 'Origem ou Destino inválidos'})
        
    circuitos = database.get_circuitos_afetados_por_link(origem, destino)
    
    return jsonify({
        'success': True,
        'circuitos': circuitos,
        'total': len(circuitos)
    })        


# --- ROTA PARA DETALHES DO SITE (CLIQUE NO NÓ BBIP) ---
# --- ROTA PARA DETALHES DO SITE (ATUALIZADA: TRAZ FÍSICO + LÓGICO) ---
# --- ROTA PARA DETALHES DO SITE (COM LÓGICA DE 8 HORAS + DADOS FÍSICOS) ---
@app.route('/api/diagrama/detalhes_site_bbip', methods=['POST'])
def api_detalhes_site_bbip():
    import datetime
    import pytz
    import sqlite3 
    
    # Configuração de Fuso Horário para o cálculo
    try:
        local_tz = LOCAL_TIMEZONE
    except NameError:
        local_tz = pytz.timezone('America/Sao_Paulo')
    
    now = datetime.datetime.now(local_tz)

    data = request.json
    nome_site = data.get('nome_site') # Ex: ITZ-PBO01
    
    if not nome_site:
        return jsonify({'success': False, 'message': 'Nome do site inválido'})
    
    # 1. Busca Circuitos Passantes (Raw do banco)
    circuitos_raw = database.get_circuitos_por_site(nome_site)
    
    # --- [NOVO] PROCESSAMENTO INTELIGENTE DE STATUS (REGRA DE 8 HORAS) ---
    circuitos_processados = []
    
    for c in circuitos_raw:
        # Copia o dicionário para não alterar o original
        c_novo = dict(c)
        
        # Pega a data de criação do incidente
        data_criacao_str = c.get('data_criacao')
        status_original = c.get('tipo_falha', 'Desconhecido')
        
        status_final = status_original
        cor_status = "red" # Padrão para falha recente
        
        if data_criacao_str:
            try:
                # Converte string do banco para datetime
                dt_evento = datetime.datetime.strptime(str(data_criacao_str), "%Y-%m-%d %H:%M:%S")
                
                # Prepara 'now' para comparação (remove fuso se necessário para evitar conflito)
                now_naive = now.replace(tzinfo=None)
                diff = now_naive - dt_evento
                horas_passadas = diff.total_seconds() / 3600
                
                # REGRA DE OURO: SE PASSOU DE 8 HORAS -> LINK UP
                if horas_passadas > 8:
                    status_final = "Link UP / Normalizado (Auto)"
                    cor_status = "green"
                else:
                    # Menos de 8 horas, mantém o erro original
                    cor_status = "red"
                    
            except Exception as e:
                # Em caso de erro na data, mantém o original por segurança
                pass
        
        # Adiciona campos visuais para o Frontend usar no Pop-up
        c_novo['status_visual'] = status_final
        c_novo['cor_status'] = cor_status
        
        circuitos_processados.append(c_novo)

    # 2. Busca Elementos Físicos neste Site + Seus Vizinhos (MANTIDO DO SEU CÓDIGO)
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    equipamentos_detalhados = []
    
    try:
        # A. Encontra todos os elementos que pertencem a este site
        cursor.execute("""
            SELECT id, nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id, estado_atual_id 
            FROM elementos 
            WHERE site_id = ? OR nome_elemento LIKE ?
            ORDER BY nome_elemento
        """, (nome_site, f"{nome_site}%"))
        elementos_locais = [dict(row) for row in cursor.fetchall()]
        
        # B. Para cada elemento local, busca seus vizinhos
        for elem in elementos_locais:
            # Busca nome da gerência para exibir bonito
            nome_gerencia = database.get_gerencia_by_id(elem['gerencia_id'])
            
            # Busca vizinhos usando a função poderosa que já existe no database.py
            vizinhos = database.get_vizinhos_do_elemento(elem['id'])
            
            equipamentos_detalhados.append({
                'nome': elem['nome_elemento'],
                'gerencia': nome_gerencia,
                'vizinhos': vizinhos # Lista de dicionários com {nome_elemento, accid_lc, anéis...}
            })
            
    except Exception as e:
        print(f"Erro ao buscar detalhes físicos: {e}")
    finally:
        conn.close()
    
    return jsonify({
        'success': True,
        'circuitos': circuitos_processados, # Agora retorna a lista processada com status "verde" se antigo
        'equipamentos': equipamentos_detalhados, 
        'total_circuitos': len(circuitos_processados),
        'total_equipamentos': len(equipamentos_detalhados)
    })    
    
# --- ROTA PARA RODAR O CORRETOR DE ROTEADORES (HUD MATRIX) ---
# Adicione isso no app.py
#from corrigir_roteadores import sync_router_sites # Importa a função do script que criamos

#

# --- FUNÇÕES DE INTELIGÊNCIA DE REDE (DIAGNÓSTICO DE FALHA FÍSICA) ---

def extrair_raiz_nome(nome_completo):
    """
    Remove sufixos técnicos (-HWW, -SHELF, etc) para encontrar o site raiz.
    Ex: 'CHI-CAGO-HWW01-SHELF01' -> 'CHI-CAGO'
    Ex: 'LOS-ANGELES-HWW02' -> 'LOS-ANGELES'
    """
    if not nome_completo: return ""
    
    # Lista de termos que indicam o fim do nome do site e início do código técnico
    termos_tecnicos = ['-HWW', '-SHELF', '-PORT', '-ROADM', '-ODU', '-ETH', '-TRANS', '-OA', '-FIU']
    
    nome_raiz = nome_completo.upper()
    for termo in termos_tecnicos:
        if termo in nome_raiz:
            nome_raiz = nome_raiz.split(termo)[0]
            break
            
    return nome_raiz.strip()

def buscar_alarme_impactante(elemento_rota_nome):
    """
    Busca se existe algum alarme crítico (LOS, Link Down, Rompimento) 
    em qualquer equipamento que comece com o nome do elemento da rota.
    Retorna um dicionário com os detalhes ou None.
    """
    raiz = extrair_raiz_nome(elemento_rota_nome)
    if len(raiz) < 3: return None # Proteção contra nomes muito curtos ou vazios
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # A mágica do SQL: LIKE 'CHI-CAGO%' vai pegar HWW01, HWW02, Shelf, Porta...
        # Filtramos por alarmes que indicam queda física severa.
        cursor.execute("""
            SELECT a.descricao, e.nome_elemento, ta.nome_tipo_alarme
            FROM alarmes a
            JOIN elementos e ON a.elemento_id = e.id
            JOIN tipos_alarmes ta ON a.tipo_alarme_id = ta.id
            WHERE e.nome_elemento LIKE ? 
            AND (
                ta.nome_tipo_alarme IN ('LOS', 'Link Down', 'Rompimento Fibra (TX)', 'OTS_LOS', 'OSC_LOS') 
                OR a.descricao LIKE '%Link Down%' 
                OR a.descricao LIKE '%LOS%'
                OR a.descricao LIKE '%Rompimento%'
            )
            ORDER BY a.data_hora DESC LIMIT 1
        """, (raiz + '%',))
        
        alarme = cursor.fetchone()
        
        if alarme:
            return {
                'elemento_afetado': alarme['nome_elemento'],
                'descricao': f"{alarme['nome_tipo_alarme']} - {alarme['descricao']}",
                'raiz_detectada': raiz
            }
    except Exception as e:
        print(f"Erro ao buscar alarme impactante: {e}")
    finally:
        conn.close()
        
    return None


# 4. Rota para Detalhes Específicos de DADOS (COM INTELIGÊNCIA)
# ==============================================================================
# --- FUNÇÕES DE INTELIGÊNCIA DE REDE (DIAGNÓSTICO VETORIAL) ---
# ==============================================================================

def extrair_site_generico(nome_completo):
    """
    Extrai apenas o NOME DO SITE, removendo qualquer código de máquina.
    Ex: 'LOS-ANGELES-HWW02-SHELF...' -> 'LOS-ANGELES'
    Ex: 'CHI-CAGO-HWW01' -> 'CHI-CAGO'
    """
    if not nome_completo: return ""
    # Termos que indicam o início do código da máquina
    termos_corte = ['-HWW', '-ROADM', '-SHELF', '-PORT', '-OSP', '-SLOT', '-ODU']
    
    nome = nome_completo.upper()
    for t in termos_corte:
        if t in nome:
            nome = nome.split(t)[0]
            break
    return nome.strip()

def verificar_falha_no_link(site_a_nome, site_b_nome):
    """
    Verifica se existe algum alarme CRÍTICO em um equipamento do Site A
    que tenha conexão física direta com o Site B.
    """
    if not site_a_nome or not site_b_nome: return None
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Busca alarmes críticos no Site A
        # (Lógica: Pega alarmes de Link Down, LOS, Rompimento)
        cursor.execute("""
            SELECT a.descricao, e.nome_elemento, e.id as elem_id
            FROM alarmes a
            JOIN elementos e ON a.elemento_id = e.id
            WHERE e.nome_elemento LIKE ? 
            AND (a.descricao LIKE '%Link Down%' OR a.descricao LIKE '%LOS%' OR a.descricao LIKE '%Rompimento%')
            ORDER BY a.data_hora DESC
        """, (site_a_nome + '%',))
        
        alarmes_candidatos = cursor.fetchall()
        
        # 2. Para cada equipamento alarmado, verifica se ele aponta para o Site B
        for alarme in alarmes_candidatos:
            elem_id_alarmado = alarme['elem_id']
            
            # Busca vizinhos desse equipamento específico na tabela de vizinhança
            cursor.execute("""
                SELECT e_viz.nome_elemento 
                FROM vizinhanca v
                JOIN elementos e_viz ON v.elemento_destino_id = e_viz.id
                WHERE v.elemento_origem_id = ?
            """, (elem_id_alarmado,))
            
            vizinhos = cursor.fetchall()
            
            # Verifica se algum vizinho pertence ao Site B
            for viz in vizinhos:
                site_vizinho = extrair_site_generico(viz['nome_elemento'])
                
                # A MÁGICA: Se o vizinho do equipamento quebrado for o Site B...
                if site_vizinho == site_b_nome:
                    return {
                        'titulo': f"ROMPIMENTO ENTRE {site_a_nome} E {site_b_nome}",
                        'mensagem': f"O equipamento <b>{alarme['nome_elemento']}</b> (em {site_a_nome}) apresenta falha crítica e ele é o responsável pela conexão com <b>{site_b_nome}</b>.<br>Diagnóstico: <i>{alarme['descricao']}</i>."
                    }
                    
    except Exception as e:
        print(f"Erro na verificação vetorial: {e}")
    finally:
        conn.close()
        
    return None

# ==============================================================================
# --- ROTA DE DETALHES COM INTELIGÊNCIA VETORIAL ---
# ==============================================================================
# ==============================================================================
# --- ROTA DE DETALHES COM ALERTA AMARELO (LÓGICO) OU VERMELHO (FÍSICO) ---
# ==============================================================================
@app.route('/detalhes_evento_dados/<int:evento_id>')
def detalhes_evento_dados(evento_id):
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    evento = database.get_evento_by_id(evento_id)
    if not evento:
        flash('Evento não encontrado.', 'danger')
        conn.close() 
        return redirect(url_for('relatorio_eventos'))
        
    circuito = None
    hops = []
    correlacoes = [] 
    alerta_impacto = None # Vermelho (Físico)
    alerta_logico = None  # Amarelo (Dados)

    try:
        # 1. Busca Dados do Circuito
        query = """
            SELECT c.*, 
                e1.hostname as orig_host, f1.nome_fabricante as orig_fab, s1.nome_status as orig_status, a1.nome_alarme as orig_alarme,
                e2.hostname as dest_host, f2.nome_fabricante as dest_fab, s2.nome_status as dest_status, a2.nome_alarme as dest_alarme
            FROM circuitos_dados c
            LEFT JOIN equipamentos_dados e1 ON c.roteador_origem_id = e1.id
            LEFT JOIN fabricantes_dados f1 ON e1.fabricante_id = f1.id
            LEFT JOIN status_dados s1 ON c.status_origem_id = s1.id
            LEFT JOIN alarmes_dados a1 ON c.alarme_origem_id = a1.id
            LEFT JOIN equipamentos_dados e2 ON c.roteador_destino_id = e2.id
            LEFT JOIN fabricantes_dados f2 ON e2.fabricante_id = f2.id
            LEFT JOIN status_dados s2 ON c.status_destino_id = s2.id
            LEFT JOIN alarmes_dados a2 ON c.alarme_destino_id = a2.id
            WHERE c.evento_id = ?
        """
        cursor.execute(query, (evento_id,))
        circuito_row = cursor.fetchone()
        
        if circuito_row:
            circuito = dict(circuito_row)

            # 2. Busca Rota TX (Hops)
            cursor.execute("""
                SELECT r.ordem_salto, e.nome_elemento, e.id as elem_id
                FROM rota_circuitos_tx r
                JOIN elementos e ON r.elemento_tx_id = e.id
                WHERE r.circuito_dados_id = ?
                ORDER BY r.ordem_salto
            """, (circuito['id'],))
            hops = [dict(row) for row in cursor.fetchall()]
            
            # --- 3. DIAGNÓSTICO DE FALHA FÍSICA (Vermelho) ---
            if len(hops) > 1:
                for i in range(len(hops) - 1):
                    salto_atual = hops[i]
                    salto_prox = hops[i+1]
                    site_a = extrair_site_generico(salto_atual['nome_elemento'])
                    site_b = extrair_site_generico(salto_prox['nome_elemento'])
                    
                    impacto = verificar_falha_no_link(site_a, site_b)
                    if impacto:
                        alerta_impacto = {
                            'status': 'CRITICO',
                            'titulo': impacto['titulo'],
                            'mensagem': impacto['mensagem']
                        }
                        break 

            # --- 4. DIAGNÓSTICO DE FALHA LÓGICA (Amarelo) ---
            # Se não achou falha física, mas o circuito está ruim...
            if not alerta_impacto:
                # Verifica se tem status DOWN ou tipo de falha preenchido
                tem_problema = False
                if circuito.get('tipo_falha'): tem_problema = True
                if circuito.get('orig_status') != 'UP' and circuito.get('orig_status') != 'N/A': tem_problema = True
                
                if tem_problema:
                    alerta_logico = {
                        'status': 'ALERTA',
                        'titulo': f"FALHA LÓGICA / DADOS",
                        'mensagem': f"O circuito <b>{circuito['accid']}</b> está inoperante, mas a infraestrutura física (fibra) nos trechos cadastrados parece íntegra.<br>Verifique configurações de roteamento, BGP ou falha de equipamento lógico."
                    }

    except Exception as e:
        print(f"Erro ao buscar detalhes dados: {e}")
        flash(f'Erro: {str(e)}', 'danger')
    finally:
        conn.close()
        
    return render_template('detalhes_evento_dados.html', 
                           evento=evento, 
                           circuito=circuito, 
                           hops=hops,
                           correlacoes=correlacoes,
                           alerta_impacto=alerta_impacto,
                           alerta_logico=alerta_logico, # Passamos o novo alerta
                           now=datetime.datetime.now())    
    
    
    
# --- ROTA: ITEM 13 - AUDITORIA DE CLUSTERIZAÇÃO (GEOGRAFIA) ---
@app.route('/api/debug/audit_clusters', methods=['GET'])
def api_debug_audit_clusters():
    import sqlite3
    import re # Para lidar com traço E underline ao mesmo tempo
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    report = []
    
    try:
        cursor.execute("SELECT id, nome_elemento FROM elementos ORDER BY nome_elemento")
        elementos = cursor.fetchall()
        
        for elem in elementos:
            nome_bruto = elem['nome_elemento'].strip().upper()
            
            # 1. Normalização: Troca underline por traço para facilitar
            # E remove espaços extras
            nome_limpo = re.sub(r'[_]', '-', nome_bruto)
            partes = nome_limpo.split('-')
            
            # Lógica de Classificação Solicitada
            cluster_uf = "N/A"
            cluster_cidade = "N/A" # Região Macro (Início)
            cluster_bairro = "N/A" # Detalhe (Meio)
            
            qtd_partes = len(partes)
            
            if qtd_partes >= 3:
                # Padrão: CIDADE - BAIRRO - ... - UF
                # Ex: SPO-IBI-SP
                cluster_cidade = partes[0] # Primeiro (Esquerda)
                cluster_uf = partes[-1]    # Último (Direita)
                
                # O Bairro é tudo que sobrou no meio (pode ter mais de um nome)
                cluster_bairro = "-".join(partes[1:-1])
                
            elif qtd_partes == 2:
                # Padrão Curto: CIDADE-UF ou CIDADE-BAIRRO
                # Vamos tentar adivinhar se o último é UF
                ultimo = partes[-1]
                if len(ultimo) == 2: # Provavel UF
                    cluster_cidade = partes[0]
                    cluster_uf = ultimo
                    cluster_bairro = "--"
                else:
                    cluster_cidade = partes[0]
                    cluster_bairro = partes[1]
                    cluster_uf = "??"
            else:
                # Sem traços (Nome único)
                cluster_cidade = nome_bruto
                # Tenta pegar UF dos 2 ultimos chars se nada der certo
                if len(nome_bruto) > 3:
                    cluster_uf = nome_bruto[-2:]

            # Validação Visual
            status = "✅ OK"
            if len(cluster_uf) != 2:
                status = "⚠️ UF ESTRANHA"
            if cluster_cidade == "N/A":
                status = "❌ ERRO FORMATO"

            report.append({
                'id': elem['id'],
                'nome_original': nome_bruto,
                'cidade_detectada': cluster_cidade,
                'bairro_detectado': cluster_bairro,
                'uf_detectada': cluster_uf,
                'status': status
            })
            
        return jsonify({'success': True, 'report': report})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()
        
        
        
# --- ROTA: ITEM 13 - GESTÃO DE CLUSTERS (AGRUPAMENTO INTELIGENTE + CORREÇÃO) ---
@app.route('/api/debug/manage_clusters', methods=['POST'])
def api_debug_manage_clusters():
    import sqlite3
    import re
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    action = request.json.get('action') # 'preview' ou 'save'
    report = []
    updates_count = 0
    
    # Lista de UFs para validação
    valid_ufs = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']

    try:
        # 1. Garante colunas de Cluster
        try:
            cursor.execute("ALTER TABLE elementos ADD COLUMN cluster_uf TEXT")
            cursor.execute("ALTER TABLE elementos ADD COLUMN cluster_regiao TEXT")
            conn.commit()
        except sqlite3.OperationalError: pass

        # 2. Busca dados COM JOIN na tabela 'estados_enlace' (O Pulo do Gato)
        # O campo 'local_estrangeiro' virá preenchido (ex: MONTANHAS-RN) se houver vínculo
        cursor.execute("""
            SELECT 
                e.id, 
                e.nome_elemento, 
                e.uf, 
                e.cidade, 
                ee.nome_estado as local_estrangeiro
            FROM elementos e
            LEFT JOIN estados_enlace ee ON e.estado_atual_id = ee.id
        """)
        elementos = cursor.fetchall()
        
        for elem in elementos:
            nome_bruto = elem['nome_elemento'].strip().upper()
            
            # --- A. LÓGICA DE UF (NÍVEL 1) ---
            cluster_uf = "N/A"
            origem_uf = "N/A"

            # 1. Prioridade Máxima: Tabela 'estados_enlace' (Vínculo ID 29 -> "MONTANHAS-RN")
            if elem['local_estrangeiro']:
                local_raw = elem['local_estrangeiro'].strip().upper()
                # Tenta pegar as ultimas 2 letras (RN)
                if len(local_raw) >= 2:
                    candidato = local_raw[-2:]
                    if candidato in valid_ufs:
                        cluster_uf = candidato
                        origem_uf = f"Vínculo ({local_raw})"
            
            # 2. Se falhar, tenta coluna UF do próprio elemento
            if cluster_uf == "N/A" and elem['uf'] and len(elem['uf'].strip()) == 2:
                cluster_uf = elem['uf'].strip().upper()
                origem_uf = "Cadastro Direto"
            
            # 3. Se falhar, tenta extrair do Nome do Elemento (Último Recurso)
            if cluster_uf == "N/A":
                partes_nome = re.split(r'[-_]', nome_bruto)
                if len(partes_nome) > 2 and partes_nome[-1] in valid_ufs:
                    cluster_uf = partes_nome[-1]
                    origem_uf = "Nome (Sufixo)"

            # --- B. LÓGICA DE REGIÃO (NÍVEL 2) ---
            nome_limpo = re.sub(r'[_]', '-', nome_bruto)
            partes = nome_limpo.split('-')
            cluster_regiao = "OUTROS"
            
            if len(partes) >= 2:
                parte_1 = partes[0]
                parte_2_bruta = partes[1]
                parte_2_limpa = re.sub(r'\d+', '', parte_2_bruta) # Remove numeros
                if not parte_2_limpa: parte_2_limpa = parte_2_bruta
                cluster_regiao = f"{parte_1}-{parte_2_limpa}"
            else:
                cluster_regiao = partes[0]

            # Relatório
            report.append({
                'id': elem['id'],
                'original': nome_bruto,
                'regiao': cluster_regiao,
                'uf': cluster_uf,
                'origem_uf': origem_uf
            })

            # Salvar no Banco
            if action == 'save':
                # Aqui aproveitamos e salvamos na coluna 'uf' oficial se ela estiver vazia!
                sql_extra = ""
                params = [cluster_regiao, cluster_uf, elem['id']]
                
                if cluster_uf != "N/A" and (not elem['uf']):
                    sql_extra = ", uf = ?"
                    params.insert(2, cluster_uf) # Insere UF na lista de parametros

                cursor.execute(f"UPDATE elementos SET cluster_regiao=?, cluster_uf=? {sql_extra} WHERE id=?", params)
                updates_count += 1

        if action == 'save':
            conn.commit()
            return jsonify({'success': True, 'message': f"Sucesso! {updates_count} registros processados e recuperados.", 'report': report[:100]})
        else:
            return jsonify({'success': True, 'report': report})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()       


# --- ROTA: ITEM 12.2 - DETETIVE SHERLOCK (LOCALIZAÇÃO VIA TOPOLOGIA & NOME) ---
@app.route('/api/debug/sherlock_locate_routers', methods=['POST'])
def api_sherlock_locate_routers():
    import sqlite3
    
    conn = sqlite3.connect(database.DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Facilita acessar colunas por nome
    cursor = conn.cursor()
    
    log_msgs = []
    updates_count = 0
    
    # Função auxiliar interna para extrair Site do Nome (A mágica do 2.0)
    def extrair_site_do_nome(nome_elemento):
        if not nome_elemento: return None
        # Lógica: Pega "BBB-BBB" de "BBB-BBB01-HW..."
        # Divide pelos traços e tenta pegar as 2 primeiras partes
        partes = nome_elemento.split('-')
        if len(partes) >= 2:
            # Reconstrói o prefixo (Ex: SPO-IBI)
            return f"{partes[0]}-{partes[1]}".upper()
        # Se não tiver traço suficiente, devolve a primeira parte ou o nome todo
        return partes[0].upper()

    try:
        # 1. Busca todos os circuitos de dados com roteadores definidos
        cursor.execute("""
            SELECT id, accid, roteador_origem_id, roteador_destino_id 
            FROM circuitos_dados 
            WHERE roteador_origem_id IS NOT NULL OR roteador_destino_id IS NOT NULL
        """)
        circuitos = cursor.fetchall()
        
        for circ in circuitos:
            circ_id = circ['id']
            accid = circ['accid']
            rot_orig_id = circ['roteador_origem_id']
            rot_dest_id = circ['roteador_destino_id']
            
            # 2. Busca a Rota TX ordenada
            cursor.execute("""
                SELECT e.id, e.site_id, e.nome_elemento 
                FROM rota_circuitos_tx r
                JOIN elementos e ON r.elemento_tx_id = e.id
                WHERE r.circuito_dados_id = ?
                ORDER BY r.ordem_salto ASC
            """, (circ_id,))
            
            rota = cursor.fetchall()
            
            if not rota:
                continue 
            
            # --- ANÁLISE DE ORIGEM ---
            if rot_orig_id:
                primeiro_salto = rota[0]
                # Tenta pegar da coluna oficial primeiro
                site_final = primeiro_salto['site_id']
                
                # SE ESTIVER VAZIO, USA A LÓGICA DE EXTRAÇÃO DO NOME
                if not site_final:
                    site_final = extrair_site_do_nome(primeiro_salto['nome_elemento'])
                
                if site_final:
                    # Atualiza Roteador Origem
                    cursor.execute("""
                        UPDATE equipamentos_dados 
                        SET site_id = ? 
                        WHERE id = ? AND (site_id IS NULL OR site_id = '')
                    """, (site_final, rot_orig_id))
                    
                    if cursor.rowcount > 0:
                        updates_count += 1
                        log_msgs.append(f"📍 Roteador Origem (ID {rot_orig_id}) fixado em: {site_final}")

            # --- ANÁLISE DE DESTINO ---
            if rot_dest_id:
                ultimo_salto = rota[-1]
                # Tenta pegar da coluna oficial
                site_final = ultimo_salto['site_id']
                
                # SE ESTIVER VAZIO, EXTRAI DO NOME
                if not site_final:
                    site_final = extrair_site_do_nome(ultimo_salto['nome_elemento'])
                
                if site_final:
                    # Atualiza Roteador Destino
                    cursor.execute("""
                        UPDATE equipamentos_dados 
                        SET site_id = ? 
                        WHERE id = ? AND (site_id IS NULL OR site_id = '')
                    """, (site_final, rot_dest_id))
                    
                    if cursor.rowcount > 0:
                        updates_count += 1
                        log_msgs.append(f"📍 Roteador Destino (ID {rot_dest_id}) fixado em: {site_final}")

        conn.commit()
        
        msg_final = f"Sherlock finalizou! {updates_count} roteadores localizados com sucesso."
        if updates_count == 0:
            msg_final += " (Nenhum roteador precisou de atualização ou faltam rotas cadastradas)."
            
        return jsonify({'success': True, 'message': msg_final, 'details': log_msgs})

    except Exception as e:
        print(f"Erro Sherlock: {e}")
        return jsonify({'success': False, 'message': f"Erro interno: {str(e)}"}), 500
    finally:
        conn.close()   
        
        
        
# --- ROTA PARA AUDITORIA DE UF (ITEM 13.1 - BLINDADA) ---
# --- ROTA 13.1: AUDITORIA DE UF (SEM ADIVINHAÇÃO - APENAS LISTAR VAZIOS) ---
# --- ROTA 13.1: AUDITORIA DE UF (CORREÇÃO VIA TABELA ESTADOS_ENLACE) ---
@app.route('/api/debug/audit_uf_mismatch', methods=['POST'])
def audit_uf_mismatch():
    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        
        # 1. Busca elementos onde a UF está vazia/inválida
        # E faz JOIN com a tabela estados_enlace para ver se a UF está escondida lá
        cursor.execute("""
            SELECT 
                e.id, 
                e.nome_elemento, 
                e.cluster_uf, 
                ee.nome_estado as estado_enlace_nome
            FROM elementos e
            LEFT JOIN estados_enlace ee ON e.estado_atual_id = ee.id
            WHERE e.cluster_uf IS NULL 
               OR e.cluster_uf = '' 
               OR e.cluster_uf = 'N/A'
               OR length(e.cluster_uf) > 2
        """)
        elements = cursor.fetchall()
        
        mismatches = []
        
        # Lista de UFs válidas
        valid_ufs = [
            'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
            'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'
        ]

        for row in elements:
            el_id = row[0]
            nome = row[1]
            # current_uf = row[2] (Inválido)
            estado_enlace_nome = row[3] # Ex: "SOROCABA-SP" ou "Ativo"
            
            suggested_uf = ""
            found_reason = ""

            # LÓGICA: Tenta extrair UF do nome que está na tabela estados_enlace
            if estado_enlace_nome:
                # Limpa e padroniza
                texto_sujo = estado_enlace_nome.strip().upper()
                
                # Tenta separar por traço (ex: "CAXIAS-RJ")
                parts = texto_sujo.split('-')
                if len(parts) > 1:
                    candidate = parts[-1].strip() # Pega a última parte
                    # Verifica se é uma UF válida (2 letras)
                    if len(candidate) == 2 and candidate in valid_ufs:
                        suggested_uf = candidate
                        found_reason = f"Via Cadastro ({texto_sujo})"

            # Se não achou lá, tenta a lógica de fallback pelo nome do elemento (menos confiável)
            if not suggested_uf and nome:
                nome_clean = nome.strip().upper()
                parts_nome = nome_clean.split('-')
                if len(parts_nome) > 0:
                    sigla = parts_nome[0]
                    # Mapeamento simples de siglas conhecidas
                    mapa_siglas = {'RJO': 'RJ', 'SPO': 'SP', 'BHZ': 'MG', 'CTA': 'PR', 'POA': 'RS', 'SSA': 'BA', 'REC': 'PE', 'FOR': 'CE', 'BSB': 'DF', 'MAN': 'AM', 'BEL': 'PA'}
                    if sigla in mapa_siglas:
                        suggested_uf = mapa_siglas[sigla]
                        found_reason = f"Via Sigla ({sigla})"

            mismatches.append({
                'id': el_id,
                'nome': nome,
                'current_uf': 'VAZIO',
                'suggested_uf': suggested_uf if suggested_uf else '', 
                'reason': found_reason
            })
        
        conn.close()
        return jsonify({'success': True, 'mismatches': mismatches})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# --- ROTA PARA SALVAR A CORREÇÃO MANUAL ---
# --- ROTA PARA SALVAR A CORREÇÃO MANUAL DE UF (ITEM 13.1) ---
@app.route('/api/debug/fix_element_uf', methods=['POST'])
def fix_element_uf():
    data = request.json
    el_id = data.get('id')
    new_uf = data.get('uf')
    
    # Validação e Sanitização
    if not new_uf:
        return jsonify({'success': False, 'message': 'A UF não pode ser vazia.'})

    # Força maiúscula e limita a 2 caracteres (Padrão de Cluster)
    # Ex: "sp " vira "SP", "usa" vira "US"
    uf_clean = new_uf.strip().upper()[:2]

    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        
        # Atualiza o cluster_uf e, se a coluna 'uf' original estiver vazia, atualiza ela também
        cursor.execute("""
            UPDATE elementos 
            SET cluster_uf = ?,
                uf = COALESCE(NULLIF(uf, ''), ?) 
            WHERE id = ?
        """, (uf_clean, uf_clean, el_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'uf_saved': uf_clean})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
        

# --- ROTA NOVA: BUSCAR DADOS DO CIRCUITO POR ACCID ---
@app.route('/api/dados/buscar_circuito_completo', methods=['POST'])
def api_buscar_circuito_completo():
    data = request.json
    accid = data.get('accid')
    
    if not accid:
        return jsonify({'success': False, 'message': 'ACCID não informado'})
        
    result = database.get_full_circuit_data_by_accid(accid)
    
    if result:
        return jsonify({'success': True, 'circuito': result['circuito'], 'rota': result['rota']})
    else:
        return jsonify({'success': False, 'message': 'Circuito não encontrado'})
        
            
if __name__ == '__main__':
    app.run(debug=True)