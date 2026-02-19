import sqlite3
import datetime
import pytz
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta

DATABASE_NAME = 'rede_db_demo.sqlite'
LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo')

def init_db():
    """Inicializa o banco de dados e cria as tabelas se não existirem."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    
    
    # =========================================================================
    # 1. TABELAS BÁSICAS DE TX (LEGADO & FUNCIONAIS)
    # =========================================================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gerencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_gerencia TEXT NOT NULL UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detentores_site (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_detentor TEXT NOT NULL UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aneis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_anel TEXT NOT NULL UNIQUE
        )
    ''')
    try: cursor.execute("ALTER TABLE aneis ADD COLUMN detentor_site_id INTEGER REFERENCES detentores_site(id)")
    except sqlite3.OperationalError: pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estados_enlace (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_estado TEXT NOT NULL UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tipos_alarmes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_tipo_alarme TEXT NOT NULL UNIQUE,
            equipe_responsavel TEXT DEFAULT 'N/A',
            eh_abertura_enlace_trigger INTEGER DEFAULT 0
        )
    ''')
    try: cursor.execute("ALTER TABLE tipos_alarmes ADD COLUMN tipo_alarme_pai_id INTEGER REFERENCES tipos_alarmes(id)")
    except sqlite3.OperationalError: pass

    # 2. TABELA ELEMENTOS (TX - Principal)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS elementos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_elemento TEXT NOT NULL UNIQUE,
            nome_elemento_curto TEXT,
            gerencia_id INTEGER NOT NULL,
            detentor_site_id INTEGER,
            longa_distancia INTEGER DEFAULT 0,
            estado_atual_id INTEGER,
            FOREIGN KEY (gerencia_id) REFERENCES gerencias(id),
            FOREIGN KEY (detentor_site_id) REFERENCES detentores_site(id),
            FOREIGN KEY (estado_atual_id) REFERENCES estados_enlace(id)
        )
    ''')
    
    # Colunas de Status (Afetado)
    try:
        cursor.execute("ALTER TABLE elementos ADD COLUMN esta_afetado INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE elementos ADD COLUMN afetado_ate DATETIME")
    except sqlite3.OperationalError: pass

    # --- ATUALIZAÇÃO DATABOOK (NOVAS COLUNAS TX) ---
    try: cursor.execute("ALTER TABLE elementos ADD COLUMN site_id TEXT") 
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elementos ADD COLUMN sigla_cidade TEXT") 
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elementos ADD COLUMN cidade TEXT") 
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elementos ADD COLUMN uf TEXT") 
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elementos ADD COLUMN endereco TEXT") 
    except sqlite3.OperationalError: pass
    # ----------------------------------------------

    # 3. TABELAS DE RELACIONAMENTO TX
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS links_capacidade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elemento_a_id INTEGER NOT NULL,
            elemento_b_id INTEGER NOT NULL,
            facilidades_a TEXT,
            facilidades_b TEXT,
            swap_fibra_capacidade TEXT, 
            FOREIGN KEY (elemento_a_id) REFERENCES elementos(id),
            FOREIGN KEY (elemento_b_id) REFERENCES elementos(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alarmes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elemento_id INTEGER NOT NULL,
            tipo_alarme_id INTEGER NOT NULL,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            descricao TEXT,
            alarme_pai_id INTEGER,
            FOREIGN KEY (elemento_id) REFERENCES elementos(id),
            FOREIGN KEY (tipo_alarme_id) REFERENCES tipos_alarmes(id),
            FOREIGN KEY (alarme_pai_id) REFERENCES alarmes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vizinhanca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elemento_origem_id INTEGER NOT NULL,
            elemento_destino_id INTEGER NOT NULL,
            accid_lc TEXT,
            swap_fibra_info TEXT DEFAULT 'TIM',
            UNIQUE (elemento_origem_id, elemento_destino_id),
            FOREIGN KEY (elemento_origem_id) REFERENCES elementos(id),
            FOREIGN KEY (elemento_destino_id) REFERENCES elementos(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS elemento_anel (
            elemento_id INTEGER NOT NULL,
            anel_id INTEGER NOT NULL,
            PRIMARY KEY (elemento_id, anel_id),
            FOREIGN KEY (elemento_id) REFERENCES elementos(id),
            FOREIGN KEY (anel_id) REFERENCES aneis(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            data_hora_abertura DATETIME,
            estado_origem_id INTEGER,
            estado_destino_id INTEGER,
            teste_otdr_em_curso INTEGER DEFAULT 0,
            km_rompimento_otdr REAL,
            proxima_atualizacao DATETIME,
            tipo_evento TEXT,
            FOREIGN KEY (estado_origem_id) REFERENCES estados_enlace(id),
            FOREIGN KEY (estado_destino_id) REFERENCES estados_enlace(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evento_alarme (
            evento_id INTEGER NOT NULL,
            alarme_id INTEGER NOT NULL,
            PRIMARY KEY (evento_id, alarme_id),
            FOREIGN KEY (evento_id) REFERENCES eventos(id),
            FOREIGN KEY (alarme_id) REFERENCES alarmes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evento_elemento (
            evento_id INTEGER NOT NULL,
            elemento_id INTEGER NOT NULL,
            PRIMARY KEY (evento_id, elemento_id),
            FOREIGN KEY (evento_id) REFERENCES eventos(id),
            FOREIGN KEY (elemento_id) REFERENCES elementos(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estoque_sobras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elemento_id INTEGER NOT NULL,
            data_movimentacao TEXT,
            motivo TEXT,
            FOREIGN KEY(elemento_id) REFERENCES elementos(id)
        )
    ''')
    
    # --- METADADOS DO DATABOOK (ANÉIS) ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aneis_info_extra (
            anel_id INTEGER PRIMARY KEY,
            coerencia TEXT,
            matriz_otn INTEGER DEFAULT 0,
            swap_info TEXT,
            complemento_tecnologia TEXT,
            status_construcao TEXT DEFAULT 'rascunho',
            FOREIGN KEY(anel_id) REFERENCES aneis(id)
        )
    ''')

    # --- COLUNAS PARA O VISUAL DO DATABOOK TX ---
    try: cursor.execute("ALTER TABLE vizinhanca ADD COLUMN distancia_km REAL")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elementos ADD COLUMN tipo_icone TEXT DEFAULT 'roadm'") 
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elementos ADD COLUMN is_passive INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE vizinhanca ADD COLUMN swap_complemento TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elemento_anel ADD COLUMN x INTEGER")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE elemento_anel ADD COLUMN y INTEGER")
    except sqlite3.OperationalError: pass

    # =========================================================================
    # --- NOVO: TABELAS PARA O MÓDULO TRANSPORTE DADOS (BBIP) ---
    # =========================================================================
    
    # 1. Status de Equipamentos (UP, DOWN, ETC)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS status_dados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_status TEXT NOT NULL UNIQUE
    )
    ''')

    # 2. Fabricantes de Dados (Cisco, Huawei, etc)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fabricantes_dados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_fabricante TEXT NOT NULL UNIQUE
    )
    ''')

    # 3. Catálogo de Alarmes de Dados
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alarmes_dados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_alarme TEXT NOT NULL UNIQUE
    )
    ''')

    # 4. Equipamentos de Dados (Roteadores)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS equipamentos_dados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hostname TEXT NOT NULL UNIQUE,
        fabricante_id INTEGER,
        site_id TEXT, 
        ip_gerencia TEXT,
        FOREIGN KEY(fabricante_id) REFERENCES fabricantes_dados(id)
    )
    ''')

    # 5. Circuitos de Dados (O Incidente/Monitoramento)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS circuitos_dados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        accid TEXT,
        roteador_origem_id INTEGER,
        roteador_destino_id INTEGER,
        status_origem_id INTEGER,
        status_destino_id INTEGER,
        alarme_origem_id INTEGER,
        alarme_destino_id INTEGER,
        tipo_falha TEXT,
        observacoes TEXT,
        data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(roteador_origem_id) REFERENCES equipamentos_dados(id),
        FOREIGN KEY(roteador_destino_id) REFERENCES equipamentos_dados(id),
        FOREIGN KEY(status_origem_id) REFERENCES status_dados(id),
        FOREIGN KEY(status_destino_id) REFERENCES status_dados(id),
        FOREIGN KEY(alarme_origem_id) REFERENCES alarmes_dados(id),
        FOREIGN KEY(alarme_destino_id) REFERENCES alarmes_dados(id)
    )
    ''')

    # 6. Rota Lógica sobre Física (Saltos TX)
    # Esta tabela liga o Circuito de Dados aos Elementos de TX existentes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rota_circuitos_tx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        circuito_dados_id INTEGER,
        ordem_salto INTEGER,
        elemento_tx_id INTEGER,
        FOREIGN KEY(circuito_dados_id) REFERENCES circuitos_dados(id),
        FOREIGN KEY(elemento_tx_id) REFERENCES elementos(id)
    )
    ''')

    conn.commit()
    conn.close()
    
    # Chama a função de seed (popula defaults) logo após criar
    seed_dados_defaults()
    init_tabela_falhas_circuito()

def seed_dados_defaults():
    """Popula as tabelas auxiliares de Dados com valores padrão."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Status Padrão
        status_list = ['UP', 'DOWN', 'INACESSIVEL', 'NAO EXISTE']
        for s in status_list:
            cursor.execute("INSERT OR IGNORE INTO status_dados (nome_status) VALUES (?)", (s,))
            
        # Fabricantes Padrão
        fabricantes = ['CISCO', 'HUAWEI', 'NOKIA', 'JUNIPER', 'DATACOM', 'EXTREME']
        for f in fabricantes:
            cursor.execute("INSERT OR IGNORE INTO fabricantes_dados (nome_fabricante) VALUES (?)", (f,))
            
        # Alarmes Comuns de DADOS
        alarmes = ['INTERFACE DOWN', 'BGP DOWN', 'OSPF DOWN', 'LATENCIA ALTA', 'PACKET LOSS', 'CRC ERROR', 'REBOOT', 'FALHA DE ENERGIA']
        for a in alarmes:
            cursor.execute("INSERT OR IGNORE INTO alarmes_dados (nome_alarme) VALUES (?)", (a,))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao popular defaults de dados: {e}")

def normalize_name_string(text):
    """
    Remove acentos e caracteres especiais, padronizando para maiúsculas.
    Ex: 'Seção Paraná' -> 'SECAO PARANA'
    """
    if not text: return ""
    # Normaliza para decompor caracteres (ex: 'ç' vira 'c' + cedilha)
    normalized = unicodedata.normalize('NFD', text)
    # Filtra apenas o que não é marca de acento e converte para maiúscula
    cleaned = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return cleaned.upper()
    

# --- Funções de Adição/Criação/Atualização ---
def add_gerencia(nome_gerencia):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO gerencias (nome_gerencia) VALUES (?)", (nome_gerencia,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
        
def get_or_create_anel(nome_anel, detentor_site_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM aneis WHERE nome_anel = ?", (nome_anel,))
    result = cursor.fetchone()
    if result:
        conn.close()
        return result[0], False
    else:
        # Agora inclui o detentor_site_id no INSERT
        cursor.execute("INSERT INTO aneis (nome_anel, detentor_site_id) VALUES (?, ?)", (nome_anel, detentor_site_id))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id, True
    

def update_anel_provider(anel_id, detentor_site_id):
    """Atualiza o provedor de um anel existente."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE aneis SET detentor_site_id = ? WHERE id = ?", (detentor_site_id, anel_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Erro ao atualizar provedor do anel {anel_id}: {e}")
        return False
    finally:
        conn.close()    
        

def get_or_create_gerencia(nome_gerencia):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM gerencias WHERE nome_gerencia = ?", (nome_gerencia,))
    result = cursor.fetchone()
    if result:
        conn.close()
        return result[0], False
    else:
        cursor.execute("INSERT INTO gerencias (nome_gerencia) VALUES (?)", (nome_gerencia,))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id, True

def add_elemento(nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id=None, longa_distancia=0, estado_atual_id=None):
    """
    Adiciona um novo elemento OU atualiza um existente (Upsert).
    Corrige o problema de não conseguir alterar Longa Distância se o nome já existe.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Garante que longa_distancia seja 0 ou 1
    ld_value = 1 if (longa_distancia in [1, '1', True, 'True']) else 0

    try:
        # Tenta INSERIR um novo
        cursor.execute("""
            INSERT INTO elementos (nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id, longa_distancia, estado_atual_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id, ld_value, estado_atual_id))
        conn.commit()
        return cursor.lastrowid

    except sqlite3.IntegrityError:
        # SE DER ERRO DE DUPLICIDADE (Já existe):
        # 1. Recupera o ID do elemento existente
        cursor.execute("SELECT id FROM elementos WHERE nome_elemento = ?", (nome_elemento,))
        row = cursor.fetchone()
        
        if row:
            elem_id = row[0]
            # 2. Força a ATUALIZAÇÃO dos dados (Aqui está a correção!)
            # Atualizamos tudo, menos o nome (que é a chave única)
            cursor.execute("""
                UPDATE elementos SET 
                    nome_elemento_curto = ?,
                    gerencia_id = ?,
                    detentor_site_id = ?,
                    longa_distancia = ?,
                    estado_atual_id = ?
                WHERE id = ?
            """, (nome_elemento_curto, gerencia_id, detentor_site_id, ld_value, estado_atual_id, elem_id))
            conn.commit()
            return elem_id
        return None
    finally:
        conn.close()

def get_or_create_elemento(nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id=None, longa_distancia=0, estado_atual_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM elementos WHERE nome_elemento = ?", (nome_elemento,))
    result = cursor.fetchone()
    if result:
        conn.close()
        return result[0], False
    else:
        cursor.execute("""
            INSERT INTO elementos (nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id, longa_distancia, estado_atual_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id, longa_distancia, estado_atual_id))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id, True

def update_elemento(elemento_id, nome_elemento, gerencia_id, detentor_site_id, longa_distancia, estado_atual_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    nome_elemento_curto = nome_elemento[:17] if nome_elemento else ''
    try:
        cursor.execute("""
            UPDATE elementos SET 
                nome_elemento = ?, 
                nome_elemento_curto = ?,
                gerencia_id = ?, 
                detentor_site_id = ?, 
                longa_distancia = ?,
                estado_atual_id = ?
            WHERE id = ?
        """, (nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id, longa_distancia, estado_atual_id, elemento_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def add_anel(nome_anel):
    nome_limpo = normalize_name_string(nome_anel)
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO aneis (nome_anel) VALUES (?)", (nome_limpo,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
        
def get_or_create_anel(nome_anel, detentor_site_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    nome_limpo = normalize_name_string(nome_anel) # Normaliza
    
    # Busca pelo nome limpo
    cursor.execute("SELECT id FROM aneis WHERE nome_anel = ?", (nome_limpo,))
    result = cursor.fetchone()
    
    if result:
        conn.close()
        return result[0], False
    else:
        # --- CORREÇÃO AQUI EMBAIXO ---
        # Adicionei ", detentor_site_id" na lista de colunas
        cursor.execute("INSERT INTO aneis (nome_anel, detentor_site_id) VALUES (?, ?)", (nome_limpo, detentor_site_id))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id, True

def add_tipo_alarme(nome_tipo_alarme, equipe_responsavel='N/A', eh_abertura_enlace_trigger=0, tipo_alarme_pai_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO tipos_alarmes (nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger, tipo_alarme_pai_id) 
            VALUES (?, ?, ?, ?)
        """, (nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger, tipo_alarme_pai_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_or_create_tipo_alarme(nome_tipo_alarme, equipe_responsavel='N/A', eh_abertura_enlace_trigger=0):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tipos_alarmes WHERE nome_tipo_alarme = ?", (nome_tipo_alarme,))
    result = cursor.fetchone()
    if result:
        conn.close()
        return result[0], False
    else:
        cursor.execute("INSERT INTO tipos_alarmes (nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger) VALUES (?, ?, ?)",
                    (nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id, True

def add_vizinho(elemento_origem_id, elemento_destino_id, accid_lc=None, swap_fibra_info='TIM'):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO vizinhanca (elemento_origem_id, elemento_destino_id, accid_lc, swap_fibra_info) VALUES (?, ?, ?, ?)",
                        (elemento_origem_id, elemento_destino_id, accid_lc, swap_fibra_info))
        cursor.execute("INSERT OR IGNORE INTO vizinhanca (elemento_origem_id, elemento_destino_id, accid_lc, swap_fibra_info) VALUES (?, ?, ?, ?)",
                        (elemento_destino_id, elemento_origem_id, accid_lc, swap_fibra_info))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def add_elemento_anel(elemento_id, anel_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO elemento_anel (elemento_id, anel_id) VALUES (?, ?)", (elemento_id, anel_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def add_alarme(elemento_id, tipo_alarme_id, descricao, alarme_pai_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO alarmes (elemento_id, tipo_alarme_id, descricao, alarme_pai_id) VALUES (?, ?, ?, ?)",
                    (elemento_id, tipo_alarme_id, descricao, alarme_pai_id))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def add_detentor_site(nome_detentor):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO detentores_site (nome_detentor) VALUES (?)", (nome_detentor,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def add_estado_enlace(nome_estado):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO estados_enlace (nome_estado) VALUES (?)", (nome_estado,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_or_create_estado_enlace(nome_estado):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM estados_enlace WHERE nome_estado = ?", (nome_estado,))
    result = cursor.fetchone()
    if result:
        conn.close()
        return result[0], False
    else:
        cursor.execute("INSERT INTO estados_enlace (nome_estado) VALUES (?)", (nome_estado,))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id, True

def add_evento(titulo, descricao, alarmes_ids, elementos_ids, estado_origem_id, estado_destino_id,
            teste_otdr_em_curso=0, km_rompimento_otdr=None, proxima_atualizacao=None, tipo_evento=None, data_hora_abertura=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO eventos (titulo, descricao, data_hora_abertura, estado_origem_id, estado_destino_id,
                            teste_otdr_em_curso, km_rompimento_otdr, proxima_atualizacao, tipo_evento)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (titulo, descricao, data_hora_abertura, estado_origem_id, estado_destino_id,
            teste_otdr_em_curso, km_rompimento_otdr, proxima_atualizacao, tipo_evento))
        
        evento_id = cursor.lastrowid

        for alarme_id in alarmes_ids:
            cursor.execute("INSERT INTO evento_alarme (evento_id, alarme_id) VALUES (?, ?)", (evento_id, alarme_id))
        
        for elemento_id in elementos_ids:
            cursor.execute("INSERT INTO evento_elemento (evento_id, elemento_id) VALUES (?, ?)", (evento_id, elemento_id))

        conn.commit()
        return evento_id
    except Exception as e:
        print(f"Erro ao adicionar evento: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def update_event_title(event_id, new_title):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE eventos SET titulo = ? WHERE id = ?", (new_title, event_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Erro ao atualizar título do evento: {e}")
        return False
    finally:
        conn.close()

def update_elemento_estado(elemento_id, estado_id):
    """Atualiza o estado_atual_id de um elemento."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE elementos SET estado_atual_id = ? WHERE id = ?", (estado_id, elemento_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Erro ao atualizar estado do elemento {elemento_id}: {e}")
        return False
    finally:
        conn.close()
        
def update_element_affected_status(elemento_id, esta_afetado, afetado_ate):
    """
    Atualiza o status de 'afetado' de um elemento específico.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE elementos SET esta_afetado = ?, afetado_ate = ?
            WHERE id = ?
        """, (esta_afetado, afetado_ate, elemento_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Erro ao atualizar status de afetação do elemento {elemento_id}: {e}")
        return False
    finally:
        conn.close()

def get_last_alarme_id(elemento_id, tipo_alarme_id):
    """
    Retorna o ID do último alarme inserido para um elemento e tipo de alarme específicos.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM alarmes
            WHERE elemento_id = ? AND tipo_alarme_id = ?
            ORDER BY data_hora DESC
            LIMIT 1
        """, (elemento_id, tipo_alarme_id))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Erro ao obter o último ID de alarme: {e}")
        return None
    finally:
        conn.close()

# --- Funções de Consulta ---

def get_all_gerencias():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_gerencia FROM gerencias ORDER BY nome_gerencia")
    gerencias = [{'id': row[0], 'nome_gerencia': row[1]} for row in cursor.fetchall()]
    conn.close()
    return gerencias

def get_gerencia_by_id(gerencia_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nome_gerencia FROM gerencias WHERE id = ?", (gerencia_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_elementos():
    """
    Retorna todos os elementos com detalhes de gerência, provedor, longa distância,
    estado atual, ACCID/LCs, Swaps de Fibra e NOMES dos anéis,
    agrupados por elemento.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            e.id,
            e.nome_elemento,
            e.nome_elemento_curto,
            g.nome_gerencia,
            ds.nome_detentor,
            e.longa_distancia,
            se.nome_estado,
            e.estado_atual_id,
            GROUP_CONCAT(DISTINCT v.accid_lc) AS accid_lcs,
            GROUP_CONCAT(DISTINCT v.swap_fibra_info) AS swap_fibras,
            GROUP_CONCAT(DISTINCT a.nome_anel) AS aneis_nomes
        FROM elementos e
        JOIN gerencias g ON e.gerencia_id = g.id
        LEFT JOIN detentores_site ds ON e.detentor_site_id = ds.id
        LEFT JOIN estados_enlace se ON e.estado_atual_id = se.id
        LEFT JOIN vizinhanca v ON (e.id = v.elemento_origem_id OR e.id = v.elemento_destino_id)
        LEFT JOIN elemento_anel ea ON e.id = ea.elemento_id
        LEFT JOIN aneis a ON ea.anel_id = a.id
        GROUP BY e.id
        ORDER BY e.nome_elemento
    """)
    elementos = []
    for row in cursor.fetchall():
        elementos.append({
            'id': row[0],
            'nome_elemento': row[1],
            'nome_elemento_curto': row[2],
            'nome_gerencia': row[3],
            'nome_detentor': row[4],
            'longa_distancia': bool(row[5]),
            'estado_atual': row[6],
            'estado_atual_id': row[7],
            'accid_lcs': row[8] if row[8] else 'N/A',
            'swap_fibras': row[9] if row[9] else 'N/A',
            'aneis_nomes': row[10] if row[10] else 'N/A'
        })
    conn.close()
    return elementos

    
def get_all_diagram_elements():
    """
    Retorna elementos para o diagrama com a REGRA DE OURO (8 HORAS).
    Mantém Databook e Elementos Isolados visíveis.
    
    ATUALIZADO: Adicionado 'tipo_icone' e 'qtd_roteadores' para o 
    novo Filtro Lógico (L3) e HUD do modo Matrix.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # A ORDEM DESSAS COLUNAS É A CHAVE PARA O FUNCIONAMENTO
    query = """
        SELECT
            e.id,                         -- 0
            e.nome_elemento,              -- 1
            e.nome_elemento_curto,        -- 2
            g.nome_gerencia,              -- 3
            ds.nome_detentor,             -- 4
            e.longa_distancia,            -- 5
            se.nome_estado,               -- 6
            e.estado_atual_id,            -- 7
            GROUP_CONCAT(DISTINCT v_out.accid_lc) AS accid_lcs,        -- 8
            GROUP_CONCAT(DISTINCT v_out.swap_fibra_info) AS swap_fibras, -- 9
            GROUP_CONCAT(DISTINCT a.nome_anel) AS aneis_nomes,         -- 10
            e.esta_afetado,               -- 11
            e.afetado_ate,                -- 12
            (                             -- 13
                SELECT ev.tipo_evento
                FROM eventos ev
                JOIN evento_elemento ee ON ev.id = ee.evento_id
                WHERE ee.elemento_id = e.id
                ORDER BY ev.data_hora_abertura DESC
                LIMIT 1
            ) AS tipo_evento_ativo,
            e.site_id,                    -- 14 (DATABOOK)
            e.sigla_cidade,               -- 15 (DATABOOK)
            e.cidade,                     -- 16 (DATABOOK)
            e.uf,                         -- 17 (DATABOOK)
            e.endereco,                   -- 18 (DATABOOK)
            (                             -- 19 (DATA DO EVENTO PARA REGRA 8H)
                SELECT ev.data_hora_abertura
                FROM eventos ev
                JOIN evento_elemento ee ON ev.id = ee.evento_id
                WHERE ee.elemento_id = e.id
                ORDER BY ev.data_hora_abertura DESC
                LIMIT 1
            ) AS data_evento_recente,
            e.tipo_icone,                 -- 20 (NOVO: Ícone visual nuvem/predio)
            (                             -- 21 (NOVO: Contagem Roteadores para HUD/L3)
                SELECT COUNT(*) 
                FROM equipamentos_dados ed 
                WHERE ed.site_id = e.site_id
            ) AS qtd_roteadores
        FROM elementos e
        JOIN gerencias g ON e.gerencia_id = g.id
        LEFT JOIN detentores_site ds ON e.detentor_site_id = ds.id
        LEFT JOIN estados_enlace se ON e.estado_atual_id = se.id
        LEFT JOIN vizinhanca v_out ON e.id = v_out.elemento_origem_id
        LEFT JOIN elemento_anel ea ON e.id = ea.elemento_id
        LEFT JOIN aneis a ON ea.anel_id = a.id
        
        WHERE 1=1 -- Truque para iniciar o WHERE e facilitar a adição de filtros abaixo
        
        -- *** FILTRO DE SEGURANÇA ***
        AND e.id NOT IN (SELECT elemento_id FROM estoque_sobras)
        -- *********************************
        
        GROUP BY e.id
        ORDER BY e.nome_elemento
    """
    
    cursor.execute(query)
    elementos = []
    
    # Define o limite de tempo (Agora - 8 horas)
    limite_tempo = datetime.now() - timedelta(hours=8)
    
    for row in cursor.fetchall():
        # Captura dados brutos
        esta_afetado = row[11]
        tipo_evento = row[13] if len(row) > 13 else None
        data_evento_str = row[19] if len(row) > 19 else None 
        
        # Mapeamento seguro das colunas do Databook
        site_id = row[14] if len(row) > 14 else None
        sigla_cidade = row[15] if len(row) > 15 else None
        cidade = row[16] if len(row) > 16 else None
        uf = row[17] if len(row) > 17 else None
        endereco = row[18] if len(row) > 18 else None
        
        # Mapeamento seguro das Novas Colunas (Matrix/L3)
        tipo_icone = row[20] if len(row) > 20 else 'predio'
        qtd_roteadores = row[21] if len(row) > 21 else 0

        # --- A LÓGICA DAS 8 HORAS (O CÉREBRO) ---
        if esta_afetado == 1 and data_evento_str:
            try:
                # Tenta converter a string do banco para data
                data_evento = datetime.strptime(data_evento_str, '%Y-%m-%d %H:%M:%S')
                
                # Se o evento for VELHO (antes do limite de 8h atrás)
                if data_evento < limite_tempo:
                    esta_afetado = 0  # Força ficar VERDE/NORMAL visualmente
                    tipo_evento = None # Remove o texto do alarme visualmente
            except Exception as e:
                pass

        elementos.append({
            'id': row[0],
            'nome_elemento': row[1],
            'nome_elemento_curto': row[2],
            'nome_gerencia': row[3],
            'nome_detentor': row[4],
            'longa_distancia': bool(row[5]),
            'estado_atual': row[6],
            'estado_atual_id': row[7],
            'accid_lcs': row[8] if row[8] else 'N/A',
            'swap_fibras': row[9] if row[9] else 'N/A',
            'aneis_nomes': row[10] if row[10] else 'N/A',
            
            'esta_afetado': esta_afetado, 
            'afetado_ate': row[12],
            'tipo_evento_ativo': tipo_evento,
            
            # DADOS DO DATABOOK
            'site_id': site_id,
            'sigla_cidade': sigla_cidade,
            'cidade': cidade,
            'uf': uf,
            'endereco': endereco,
            
            # NOVOS DADOS PARA O MODO MATRIX / L3
            'tipo_icone': tipo_icone,
            'qtd_roteadores': qtd_roteadores
        })
        
    conn.close()
    return elementos



def get_element_details_by_name(element_name):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.nome_elemento, e.nome_elemento_curto, e.gerencia_id, e.detentor_site_id, e.longa_distancia, e.estado_atual_id
        FROM elementos e
        WHERE e.nome_elemento = ?
    """, (element_name,))
    element_row = cursor.fetchone()

    if not element_row:
        conn.close()
        return None

    element_details = {
        'id': element_row[0],
        'nome_elemento': element_row[1],
        'nome_elemento_curto': element_row[2],
        'gerencia_id': element_row[3],
        'detentor_site_id': element_row[4],
        'longa_distancia': bool(element_row[5]),
        'estado_atual_id': element_row[6],
        'aneis_ids': []
    }

    cursor.execute("""
        SELECT anel_id FROM elemento_anel WHERE elemento_id = ?
    """, (element_details['id'],))
    aneis_ids = [row[0] for row in cursor.fetchall()]
    element_details['aneis_ids'] = aneis_ids

    conn.close()
    return element_details

def get_elemento_by_id(elemento_id):
    """
    Retorna detalhes de um elemento pelo ID.
    ATUALIZADO: Agora retorna também dados do Databook (Cidade, Site ID, etc) e Ícone.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nome_elemento, nome_elemento_curto, gerencia_id, detentor_site_id, longa_distancia, estado_atual_id, 
               tipo_icone, is_passive, site_id, sigla_cidade, cidade, uf, endereco
        FROM elementos WHERE id = ?
    """, (elemento_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'nome_elemento': row[1],
            'nome_elemento_curto': row[2],
            'gerencia_id': row[3],
            'detentor_site_id': row[4],
            'longa_distancia': bool(row[5]),
            'estado_atual_id': row[6],
            'tipo_icone': row[7],
            'is_passive': row[8],
            # NOVOS CAMPOS DATABOOK
            'site_id': row[9],
            'sigla_cidade': row[10],
            'cidade': row[11],
            'uf': row[12],
            'endereco': row[13]
        }
    return None

def get_elemento_id_by_name(nome_elemento):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM elementos WHERE nome_elemento = ?", (nome_elemento,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_vizinhança_details_by_element_names(nome_elemento_origem, nome_elemento_destino):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT v.accid_lc, v.swap_fibra_info
            FROM vizinhanca v
            JOIN elementos e_origem ON v.elemento_origem_id = e_origem.id
            JOIN elementos e_destino ON v.elemento_destino_id = e_destino.id
            WHERE (e_origem.nome_elemento = ? AND e_destino.nome_elemento = ?)
               OR (e_origem.nome_elemento = ? AND e_destino.nome_elemento = ?)
            LIMIT 1
        """, (nome_elemento_origem, nome_elemento_destino, nome_elemento_destino, nome_elemento_origem))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {'accid_lc': result[0], 'swap_fibra_info': result[1]}
        return None
    except Exception as e:
        print(f"Erro ao buscar detalhes da vizinhança: {e}")
        return None
    finally:
        conn.close()

def get_all_aneis():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_anel FROM aneis ORDER BY nome_anel")
    aneis = [{'id': row[0], 'nome_anel': row[1]} for row in cursor.fetchall()]
    conn.close()
    return aneis

def get_anel_by_id(anel_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_anel FROM aneis WHERE id = ?", (anel_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'id': row[0], 'nome_anel': row[1]}
    return None

def get_elementos_no_anel(anel_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # A CORREÇÃO ESTÁ AQUI EMBAIXO: Mudei 'v.accid_lcs' para 'v.accid_lc'
    cursor.execute("""
        SELECT
            e.id,
            e.nome_elemento,
            g.nome_gerencia,
            e.longa_distancia,
            GROUP_CONCAT(DISTINCT v.accid_lc) AS accid_lcs, 
            GROUP_CONCAT(DISTINCT v.swap_fibra_info) AS swap_fibras,
            ea.x,
            ea.y
        FROM elementos e
        JOIN elemento_anel ea ON e.id = ea.elemento_id
        JOIN gerencias g ON e.gerencia_id = g.id
        LEFT JOIN vizinhanca v ON (e.id = v.elemento_origem_id OR e.id = v.elemento_destino_id)
        WHERE ea.anel_id = ?
        GROUP BY e.id, e.nome_elemento, g.nome_gerencia, e.longa_distancia, ea.x, ea.y
        ORDER BY e.nome_elemento
    """, (anel_id,))
    
    elementos = []
    for row in cursor.fetchall():
        elementos.append({
            'id': row[0],
            'nome_elemento': row[1],
            'nome_gerencia': row[2],
            'longa_distancia': bool(row[3]),
            'accid_lcs': row[4] if row[4] else 'N/A',
            'swap_fibras': row[5] if row[5] else 'N/A',
            'x': row[6], # Pode ser None
            'y': row[7]  # Pode ser None
        })
    conn.close()
    return elementos


def save_element_position(anel_id, elemento_id, x, y):
    """Salva a posição X,Y de um elemento dentro de um anel específico."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE elemento_anel 
            SET x = ?, y = ? 
            WHERE anel_id = ? AND elemento_id = ?
        """, (int(x), int(y), anel_id, elemento_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao salvar posição: {e}")
        return False
    finally:
        conn.close()

# ATUALIZADO PARA FAZER REFERENCIA DE ALARME PAI E FILHO
def get_all_tipos_alarmes():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Adicionamos um LEFT JOIN para buscar o nome do alarme pai
    cursor.execute("""
        SELECT 
            ta.id, 
            ta.nome_tipo_alarme, 
            ta.equipe_responsavel, 
            ta.eh_abertura_enlace_trigger,
            parent.nome_tipo_alarme as nome_pai
        FROM tipos_alarmes ta
        LEFT JOIN tipos_alarmes parent ON ta.tipo_alarme_pai_id = parent.id
        ORDER BY ta.nome_tipo_alarme
    """)
    tipos = []
    for row in cursor.fetchall():
        tipos.append({
            'id': row[0],
            'nome_tipo_alarme': row[1],
            'equipe_responsavel': row[2],
            'eh_abertura_enlace_trigger': bool(row[3]),
            'nome_pai': row[4] # Novo campo
        })
    conn.close()
    return tipos

# ATUALIZADO PARA FAZER REFERENCIA DE ALARME PAI E FILHO
def get_tipo_alarme_by_id(tipo_alarme_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger, tipo_alarme_pai_id FROM tipos_alarmes WHERE id = ?", (tipo_alarme_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'nome_tipo_alarme': row[1],
            'equipe_responsavel': row[2],
            'eh_abertura_enlace_trigger': bool(row[3]),
            'tipo_alarme_pai_id': row[4] # Novo campo
        }
    return None

def get_tipo_alarme_name_by_id(tipo_alarme_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nome_tipo_alarme FROM tipos_alarmes WHERE id = ?", (tipo_alarme_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ATUALIZADO PARA FAZER REFERENCIA DE ALARME PAI E FILHO
def update_tipo_alarme(tipo_alarme_id, nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger, tipo_alarme_pai_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE tipos_alarmes SET 
                nome_tipo_alarme = ?, 
                equipe_responsavel = ?, 
                eh_abertura_enlace_trigger = ?,
                tipo_alarme_pai_id = ?
            WHERE id = ?
        """, (nome_tipo_alarme, equipe_responsavel, eh_abertura_enlace_trigger, tipo_alarme_pai_id, tipo_alarme_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_all_detentores_site():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_detentor FROM detentores_site ORDER BY nome_detentor")
    detentores = [{'id': row[0], 'nome_detentor': row[1]} for row in cursor.fetchall()]
    conn.close()
    return detentores

def get_detentor_site_name_by_id(detentor_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nome_detentor FROM detentores_site WHERE id = ?", (detentor_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_estados_enlace():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_estado FROM estados_enlace ORDER BY nome_estado")
    estados = [{'id': row[0], 'nome_estado': row[1]} for row in cursor.fetchall()]
    conn.close()
    return estados

def get_estado_enlace_name_by_id(estado_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nome_estado FROM estados_enlace WHERE id = ?", (estado_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_eventos(ano=None, mes=None, dia=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # O LEFT JOIN é fundamental aqui para trazer eventos sem estado (DADOS)
    query = """
        SELECT e.id, e.titulo, e.descricao, e.data_hora_abertura,
            se_origem.nome_estado AS estado_origem_nome,
            se_destino.nome_estado AS estado_destino_nome,
            e.teste_otdr_em_curso, e.km_rompimento_otdr, e.proxima_atualizacao, e.tipo_evento
        FROM eventos e
        LEFT JOIN estados_enlace se_origem ON e.estado_origem_id = se_origem.id
        LEFT JOIN estados_enlace se_destino ON e.estado_destino_id = se_destino.id
    """

    conditions = []
    params = []

    if ano:
        conditions.append("strftime('%Y', e.data_hora_abertura) = ?")
        params.append(str(ano))
    if mes:
        conditions.append("strftime('%m', e.data_hora_abertura) = ?")
        params.append(str(mes).zfill(2))
    if dia:
        conditions.append("strftime('%d', e.data_hora_abertura) = ?")
        params.append(str(dia).zfill(2))

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY e.data_hora_abertura DESC"

    cursor.execute(query, params)

    eventos = []
    for row in cursor.fetchall():
        # BLINDAGEM: Garante que não quebre se a data vier nula ou mal formatada
        data_abertura = None
        if row[3]:
            try:
                # CORREÇÃO: Removido o ".datetime" extra. Agora chama datetime.strptime direto.
                dt_obj = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S")
                data_abertura = LOCAL_TIMEZONE.localize(dt_obj)
            except ValueError:
                data_abertura = None 

        prox_att = None
        if row[8]:
            try:
                # CORREÇÃO: Removido o ".datetime" extra aqui também.
                dt_obj = datetime.strptime(row[8], "%Y-%m-%d %H:%M:%S")
                prox_att = LOCAL_TIMEZONE.localize(dt_obj)
            except ValueError:
                prox_att = None

        evento = {
            'id': row[0],
            'titulo': row[1],
            'descricao': row[2],
            'data_hora_abertura': data_abertura,
            # BLINDAGEM: Se vier None do banco, coloca 'N/A' para não quebrar o HTML
            'estado_origem_nome': row[4] if row[4] else "N/A", 
            'estado_destino_nome': row[5] if row[5] else "N/A",
            'teste_otdr_em_curso': bool(row[6]),
            'km_rompimento_otdr': row[7],
            'proxima_atualizacao': prox_att,
            'tipo_evento': row[9]
        }
        eventos.append(evento)
    conn.close()
    return eventos



def get_evento_by_id(evento_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.titulo, e.descricao, e.data_hora_abertura,
            se_origem.nome_estado AS estado_origem_nome,
            se_destino.nome_estado AS estado_destino_nome,
            e.teste_otdr_em_curso, e.km_rompimento_otdr, e.proxima_atualizacao, e.tipo_evento
        FROM eventos e
        LEFT JOIN estados_enlace se_origem ON e.estado_origem_id = se_origem.id
        LEFT JOIN estados_enlace se_destino ON e.estado_destino_id = se_destino.id
        WHERE e.id = ?
    """, (evento_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'titulo': row[1],
            'descricao': row[2],
            # CORREÇÃO AQUI: removido um ".datetime" extra
            'data_hora_abertura': LOCAL_TIMEZONE.localize(datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S")) if row[3] else None,
            'estado_origem_nome': row[4],
            'estado_destino_nome': row[5],
            'teste_otdr_em_curso': bool(row[6]),
            'km_rompimento_otdr': row[7],
            # CORREÇÃO AQUI TAMBÉM: removido um ".datetime" extra
            'proxima_atualizacao': LOCAL_TIMEZONE.localize(datetime.strptime(row[8], "%Y-%m-%d %H:%M:%S")) if row[8] else None,
            'tipo_evento': row[9]
        }
    return None

def get_aneis_do_elemento(elemento_id):
    """
    Retorna todos os anéis aos quais um elemento está associado.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.nome_anel
        FROM aneis a
        JOIN elemento_anel ea ON a.id = ea.anel_id
        WHERE ea.elemento_id = ?
        ORDER BY a.nome_anel
    """, (elemento_id,))
    aneis = [{'id': row[0], 'nome_anel': row[1]} for row in cursor.fetchall()]
    conn.close()
    return aneis

def get_all_alarmes():
    """
    Retorna todos os alarmes com detalhes dos elementos e tipos de alarmes relacionados,
    incluindo o nome do alarme pai, se houver.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.id, 
            a.elemento_id, 
            e.nome_elemento, 
            a.tipo_alarme_id, 
            ta.nome_tipo_alarme, 
            ta.equipe_responsavel,
            a.data_hora, 
            a.descricao, 
            a.alarme_pai_id,
            tap.nome_tipo_alarme AS nome_alarme_pai_tipo,
            ep.nome_elemento AS nome_alarme_pai_elemento
        FROM alarmes a
        JOIN elementos e ON a.elemento_id = e.id
        JOIN tipos_alarmes ta ON a.tipo_alarme_id = ta.id
        LEFT JOIN alarmes ap ON a.alarme_pai_id = ap.id
        LEFT JOIN tipos_alarmes tap ON ap.tipo_alarme_id = tap.id
        LEFT JOIN elementos ep ON ap.elemento_id = ep.id
        ORDER BY a.data_hora DESC
    """)
    alarmes = []
    for row in cursor.fetchall():
        alarme = {
            'id': row[0],
            'elemento_id': row[1],
            'nome_elemento': row[2],
            'tipo_alarme_id': row[3],
            'nome_tipo_alarme': row[4],
            'equipe_responsavel': row[5],
            'data_hora': row[6],
            'descricao': row[7],
            'alarme_pai_id': row[8]
        }
        if row[8] is not None and row[9] is not None and row[10] is not None:
            alarme['nome_alarme_pai'] = f"{row[10]} - {row[9]}"
        else:
            alarme['nome_alarme_pai'] = None
        alarmes.append(alarme)
    conn.close()
    return alarmes   

def get_vizinhos_do_elemento(elemento_id):
    """
    Retorna os vizinhos de um elemento, incluindo detalhes como gerência, detentor,
    longa distância, ACCID/LC, swap de fibra, ESTADO e ANÉIS.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            e.id, 
            e.nome_elemento, 
            g.nome_gerencia, 
            ds.nome_detentor, 
            e.longa_distancia,
            v.accid_lc,
            v.swap_fibra_info,
            se.nome_estado,                     -- NOVO: Nome do Estado
            GROUP_CONCAT(DISTINCT a.nome_anel)  -- NOVO: Lista de Anéis
        FROM vizinhanca v
        JOIN elementos e ON v.elemento_destino_id = e.id
        JOIN gerencias g ON e.gerencia_id = g.id
        LEFT JOIN detentores_site ds ON e.detentor_site_id = ds.id
        LEFT JOIN estados_enlace se ON e.estado_atual_id = se.id  -- Join para Estado
        LEFT JOIN elemento_anel ea ON e.id = ea.elemento_id       -- Join para Anéis
        LEFT JOIN aneis a ON ea.anel_id = a.id
        WHERE v.elemento_origem_id = ?
        GROUP BY e.id  -- Agrupamento necessário por causa do GROUP_CONCAT dos anéis
        ORDER BY e.nome_elemento
    """, (elemento_id,))
    
    vizinhos = []
    for row in cursor.fetchall():
        vizinhos.append({
            'id': row[0],
            'nome_elemento': row[1],
            'nome_gerencia': row[2],
            'nome_detentor': row[3],
            'longa_distancia': bool(row[4]),
            'accid_lc': row[5],
            'swap_fibra_info': row[6],
            'estado': row[7] if row[7] else 'N/A',  # NOVO CAMPO
            'aneis': row[8] if row[8] else 'N/A'    # NOVO CAMPO
        })
    conn.close()
    return vizinhos   

def get_all_vizinhancas_for_diagram():
    """
    Retorna todas as relações de vizinhança com ACCID/LC e Swap de Fibra,
    útil para construir arestas em um diagrama.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            v.elemento_origem_id, 
            v.elemento_destino_id, 
            v.accid_lc, 
            v.swap_fibra_info
        FROM vizinhanca v
        ORDER BY v.elemento_origem_id, v.elemento_destino_id
    """)
    vizinhancas = []
    for row in cursor.fetchall():
        vizinhancas.append({
            'elemento_origem_id': row[0],
            'elemento_destino_id': row[1],
            'accid_lc': row[2],
            'swap_fibra_info': row[3]
        })
    conn.close()
    return vizinhancas 

def get_alarmes_do_elemento(elemento_id):
    """
    Retorna todos os alarmes associados a um elemento específico,
    incluindo detalhes do tipo de alarme e, se aplicável, do alarme pai.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.id, 
            a.elemento_id, 
            e.nome_elemento, 
            a.tipo_alarme_id, 
            ta.nome_tipo_alarme, 
            ta.equipe_responsavel,
            a.data_hora, 
            a.descricao, 
            a.alarme_pai_id,
            tap.nome_tipo_alarme AS nome_alarme_pai_tipo,
            ep.nome_elemento AS nome_alarme_pai_elemento
        FROM alarmes a
        JOIN elementos e ON a.elemento_id = e.id
        JOIN tipos_alarmes ta ON a.tipo_alarme_id = ta.id
        LEFT JOIN alarmes ap ON a.alarme_pai_id = ap.id
        LEFT JOIN tipos_alarmes tap ON ap.tipo_alarme_id = tap.id
        LEFT JOIN elementos ep ON ap.elemento_id = ep.id
        WHERE a.elemento_id = ?
        ORDER BY a.data_hora DESC
    """, (elemento_id,))
    alarmes = []
    for row in cursor.fetchall():
        alarme = {
            'id': row[0],
            'elemento_id': row[1],
            'nome_elemento': row[2],
            'tipo_alarme_id': row[3],
            'nome_tipo_alarme': row[4],
            'equipe_responsavel': row[5],
            'data_hora': row[6],
            'descricao': row[7],
            'alarme_pai_id': row[8]
        }
        if row[8] is not None and row[9] is not None and row[10] is not None:
            alarme['nome_alarme_pai'] = f"{row[10]} - {row[9]}"
        else:
            alarme['nome_alarme_pai'] = None
        alarmes.append(alarme)
    conn.close()
    return alarmes

# --- Funções de Exclusão ---

def excluir_elemento_e_registros_relacionados(elemento_id):
    """
    Exclui um elemento e todos os seus registros relacionados em outras tabelas.
    A ordem da exclusão é importante para respeitar as chaves estrangeiras.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Inicia uma transação
        cursor.execute("BEGIN TRANSACTION")

        # 1. Obter todos os alarmes associados ao elemento para limpar a tabela evento_alarme
        cursor.execute("SELECT id FROM alarmes WHERE elemento_id = ?", (elemento_id,))
        alarmes_ids_tuples = cursor.fetchall()
        if alarmes_ids_tuples:
            alarmes_ids = [item[0] for item in alarmes_ids_tuples]
            # Converte para uma string de placeholders para a cláusula IN
            placeholders = ','.join('?' for _ in alarmes_ids)
            cursor.execute(f"DELETE FROM evento_alarme WHERE alarme_id IN ({placeholders})", alarmes_ids)

        # 2. Excluir da tabela 'alarmes'
        cursor.execute("DELETE FROM alarmes WHERE elemento_id = ?", (elemento_id,))

        # 3. Excluir da tabela 'vizinhanca' (onde o elemento é origem ou destino)
        cursor.execute("DELETE FROM vizinhanca WHERE elemento_origem_id = ? OR elemento_destino_id = ?", (elemento_id, elemento_id))

        # 4. Excluir da tabela 'elemento_anel'
        cursor.execute("DELETE FROM elemento_anel WHERE elemento_id = ?", (elemento_id,))
        
        # 5. Excluir da tabela 'evento_elemento'
        cursor.execute("DELETE FROM evento_elemento WHERE elemento_id = ?", (elemento_id,))

        # 6. Finalmente, excluir o próprio elemento da tabela 'elementos'
        cursor.execute("DELETE FROM elementos WHERE id = ?", (elemento_id,))

        # Confirma a transação
        conn.commit()
        return True

    except sqlite3.Error as e:
        # Se ocorrer qualquer erro, desfaz todas as operações
        conn.rollback()
        print(f"Erro ao excluir elemento {elemento_id}: {e}")
        return False
    finally:
        conn.close()
        
        
# --- Funções de Busca (Autocomplete) ---

def search_elementos_com_vizinho(search_term):
    """
    Busca elementos cujos nomes correspondem a um termo de pesquisa (LIKE)
    e retorna o nome do primeiro vizinho encontrado para cada um.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    #  LEFT JOIN para garantir que elementos sem vizinhos também sejam retornados.
    # GROUP BY e MAX garantem que pegamos apenas um vizinho para simplificar o autocomplete.
    query = """
        SELECT 
            e1.nome_elemento, 
            MAX(e2.nome_elemento) as nome_vizinho
        FROM elementos e1
        LEFT JOIN vizinhanca v ON e1.id = v.elemento_origem_id
        LEFT JOIN elementos e2 ON v.elemento_destino_id = e2.id
        WHERE e1.nome_elemento LIKE ?
        GROUP BY e1.id, e1.nome_elemento
        ORDER BY e1.nome_elemento
        LIMIT 10
    """
    try:
        # O termo de pesquisa é envolvido por '%' para encontrar correspondências em qualquer parte do nome
        cursor.execute(query, ('%' + search_term + '%',))
        results = [{'nome_elemento': row[0], 'nome_vizinho': row[1]} for row in cursor.fetchall()]
        return results
    except Exception as e:
        print(f"Erro ao buscar elementos: {e}")
        return []
    finally:
        conn.close()       
        
# --- Funções de Busca (Autocomplete para Aneis) ---        
def search_aneis_by_name(search_term):
    """
    Busca anéis por nome ou por critério de Longa Distância.
    
    LÓGICA INTELIGENTE:
    - Se search_term == 'WDM_LD': Traz anéis que têm 'WDM_LD' no nome 
      OU anéis que possuem elementos marcados como Longa Distância (flag=1).
    - Se search_term for Vazio: Traz todos os anéis (Modo Normal).
    - Se tiver texto: Filtra pelo nome digitado.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        # --- CENÁRIO 1: MODO DATABOOK (Filtro Inteligente) ---
        if search_term == 'WDM_LD':
            query = """
                SELECT DISTINCT a.id, a.nome_anel 
                FROM aneis a
                LEFT JOIN elemento_anel ea ON a.id = ea.anel_id
                LEFT JOIN elementos e ON ea.elemento_id = e.id
                WHERE 
                   (a.nome_anel LIKE '%WDM_LD%') -- Pelo Nome Padrão
                   OR 
                   (e.longa_distancia = 1)        -- Pela Flag (Exceções)
                ORDER BY a.nome_anel
                LIMIT 300
            """
            cursor.execute(query)
        
        # --- CENÁRIO 2: MODO NORMAL (Trazer Tudo) ---
        elif not search_term:
            query = """
                SELECT id, nome_anel 
                FROM aneis 
                ORDER BY nome_anel 
                LIMIT 500
            """
            cursor.execute(query)
            
        # --- CENÁRIO 3: BUSCA ESPECÍFICA (Autocomplete digitado) ---
        else:
            query = """
                SELECT id, nome_anel 
                FROM aneis 
                WHERE nome_anel LIKE ?
                ORDER BY nome_anel
                LIMIT 100
            """
            cursor.execute(query, ('%' + search_term + '%',))

        results = [{'id': row[0], 'nome_anel': row[1]} for row in cursor.fetchall()]
        return results

    except Exception as e:
        print(f"Erro ao buscar anéis: {e}")
        return []
    finally:
        conn.close()
        
        
# --- Funções de Busca (Autocomplete para Tipos de Alarme) ---
def search_tipos_alarmes_by_name(search_term):
    """
    Busca tipos de alarme cujos nomes correspondem a um termo de pesquisa (LIKE).
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    query = """
        SELECT id, nome_tipo_alarme 
        FROM tipos_alarmes 
        WHERE nome_tipo_alarme LIKE ?
        ORDER BY nome_tipo_alarme
        LIMIT 10
    """
    try:
        cursor.execute(query, ('%' + search_term + '%',))
        results = [{'id': row[0], 'nome_tipo_alarme': row[1]} for row in cursor.fetchall()]
        return results
    except Exception as e:
        print(f"Erro ao buscar tipos de alarmes: {e}")
        return []
    finally:
        conn.close()
        
# CRIAR LINK DE CAPACIDADE        
def add_link_capacidade(elemento_a_id, elemento_b_id, facilidades_a, facilidades_b, swap_fibra_capacidade):
    """Adiciona um novo link de capacidade (Atualizado para swap texto)."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO links_capacidade (elemento_a_id, elemento_b_id, facilidades_a, facilidades_b, swap_fibra_capacidade)
            VALUES (?, ?, ?, ?, ?)
        """, (elemento_a_id, elemento_b_id, facilidades_a, facilidades_b, swap_fibra_capacidade))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao adicionar link de capacidade: {e}")
        return False
    finally:
        conn.close()

# SELECT PARA O LINK DE CAPACIDADE
def get_all_links_capacidade():
    """Retorna todos os links de capacidade."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            lc.id,
            e1.nome_elemento as nome_elemento_a,
            e2.nome_elemento as nome_elemento_b,
            lc.facilidades_a,
            lc.facilidades_b,
            lc.swap_fibra_capacidade
        FROM links_capacidade lc
        JOIN elementos e1 ON lc.elemento_a_id = e1.id
        JOIN elementos e2 ON lc.elemento_b_id = e2.id
        ORDER BY lc.id DESC
    """)
    links = [{
        'id': row[0],
        'nome_elemento_a': row[1],
        'nome_elemento_b': row[2],
        'facilidades_a': row[3],
        'facilidades_b': row[4],
        'swap_fibra_capacidade': row[5] # Agora pegamos o texto direto
    } for row in cursor.fetchall()]
    conn.close()
    return links


def get_all_links_capacidade_for_diagram():
    """Retorna links para o diagrama."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            lc.elemento_a_id,
            lc.elemento_b_id,
            lc.swap_fibra_capacidade
        FROM links_capacidade lc
    """)
    links = [{
        'elemento_a_id': row[0],
        'elemento_b_id': row[1],
        'nome_detentor': row[2] or 'N/A' # Usamos o swap como "nome" para exibir no diagrama
    } for row in cursor.fetchall()]
    conn.close()
    return links 


def get_elementos_de_evento(evento_id):
    """Retorna uma lista de IDs de elementos associados a um evento específico."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT elemento_id FROM evento_elemento WHERE evento_id = ?", (evento_id,))
    element_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return element_ids   
        

def get_aneis_com_sites():
    """
    Busca todos os anéis e retorna um dicionário com o nome de cada anel
    e uma lista dos prefixos de site únicos que pertencem a ele.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    query = """
        SELECT
            a.nome_anel,
            e.nome_elemento
        FROM aneis a
        JOIN elemento_anel ea ON a.id = ea.anel_id
        JOIN elementos e ON ea.elemento_id = e.id
        WHERE e.id IN (
            SELECT elemento_origem_id FROM vizinhanca
            UNION
            SELECT elemento_destino_id FROM vizinhanca
        )
        ORDER BY a.nome_anel
    """
    cursor.execute(query)
    
    # Usa defaultdict(set) para agrupar sites únicos por anel
    aneis_sites = defaultdict(set)
    for nome_anel, nome_elemento in cursor.fetchall():
        try:
            # Assumindo que o prefixo são as duas primeiras partes do nome
            # Ex: 'RJO-ROC01-NKW03' -> 'RJO-ROC01'
            site_prefix = "-".join(nome_elemento.strip().split('-')[:2])
            aneis_sites[nome_anel].add(site_prefix)
        except IndexError:
            continue
    
    conn.close()
    
    # Converte os sets em listas para o retorno final
    return {nome_anel: list(sites) for nome_anel, sites in aneis_sites.items()}

def get_elementos_de_evento(evento_id):
    """Retorna uma lista de IDs de elementos associados a um evento específico."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT elemento_id FROM evento_elemento WHERE evento_id = ?", (evento_id,))
    element_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return element_ids

def get_all_link_capacidade_element_ids():
    """Retorna um set com os IDs de todos os elementos que fazem parte de algum link de capacidade."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT elemento_a_id FROM links_capacidade
        UNION
        SELECT elemento_b_id FROM links_capacidade
    """)
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids

def get_vizinhos_ids_por_elemento_id(elemento_id):
    """
    Retorna um conjunto (set) de IDs de elementos vizinhos,
    buscando tanto em 'vizinhanca' quanto em 'links_capacidade'.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    vizinhos_ids = set()

    try:
        # 1. Busca na tabela 'vizinhanca'
        cursor.execute("""
            SELECT elemento_destino_id FROM vizinhanca WHERE elemento_origem_id = ?
        """, (elemento_id,))
        for row in cursor.fetchall():
            vizinhos_ids.add(row[0])
            
        cursor.execute("""
            SELECT elemento_origem_id FROM vizinhanca WHERE elemento_destino_id = ?
        """, (elemento_id,))
        for row in cursor.fetchall():
            vizinhos_ids.add(row[0])

        # 2. Busca na tabela 'links_capacidade'
        cursor.execute("""
            SELECT elemento_b_id FROM links_capacidade WHERE elemento_a_id = ?
        """, (elemento_id,))
        for row in cursor.fetchall():
            vizinhos_ids.add(row[0])

        cursor.execute("""
            SELECT elemento_a_id FROM links_capacidade WHERE elemento_b_id = ?
        """, (elemento_id,))
        for row in cursor.fetchall():
            vizinhos_ids.add(row[0])

    except Exception as e:
        print(f"Erro ao buscar vizinhos para o elemento {elemento_id}: {e}")
    finally:
        conn.close()

    # Remove o próprio ID da lista, caso ele tenha aparecido (pouco provável, mas é uma garantia)
    vizinhos_ids.discard(elemento_id)
    
    return list(vizinhos_ids) # Retorna como uma lista


def excluir_link_capacidade(link_id):
    """Exclui um link de capacidade específico pelo seu ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM links_capacidade WHERE id = ?", (link_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Erro ao excluir link de capacidade: {e}")
        return False
    finally:
        conn.close()
        
# Alterado para a tecnica de machine learning
def get_alarmes_de_evento(evento_id):
    """
    Retorna uma lista de dicionários dos alarmes associados a um evento.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    alarmes = []
    try:
        cursor.execute("""
            SELECT 
                a.id, a.descricao, a.data_hora,
                e.nome_elemento,
                ta.nome_tipo_alarme
            FROM alarmes a
            JOIN evento_alarme ea ON a.id = ea.alarme_id
            JOIN elementos e ON a.elemento_id = e.id
            JOIN tipos_alarmes ta ON a.tipo_alarme_id = ta.id
            WHERE ea.evento_id = ?
            ORDER BY a.data_hora DESC
        """, (evento_id,))
        
        alarmes = [{
            'id': row[0],
            'descricao': row[1],
            'data_hora': row[2],
            'nome_elemento': row[3],
            'nome_tipo_alarme': row[4]
        } for row in cursor.fetchall()]
        
    except Exception as e:
        print(f"Erro ao buscar alarmes do evento {evento_id}: {e}")
    finally:
        conn.close()
    return alarmes


# Alterado para a tecnica de machine learning
def get_alarmes_ativos_em_elementos(lista_elementos_ids):
    """
    Busca alarmes recentes (últimas 24h) nos elementos fornecidos
    que AINDA NÃO têm um alarme pai definido.
    Estes são os "candidatos a filhos".
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    alarmes_candidatos = []
    
    if not lista_elementos_ids:
        return []
        
    # Cria os placeholders (?) para a consulta SQL
    placeholders = ','.join('?' for _ in lista_elementos_ids)
    
    try:
        cursor.execute(f"""
            SELECT 
                a.id, a.descricao, a.data_hora,
                e.nome_elemento,
                ta.nome_tipo_alarme
            FROM alarmes a
            JOIN elementos e ON a.elemento_id = e.id
            JOIN tipos_alarmes ta ON a.tipo_alarme_id = ta.id
            WHERE a.elemento_id IN ({placeholders})
              AND a.alarme_pai_id IS NULL
              AND a.data_hora >= datetime('now', '-24 hours')
            ORDER BY a.data_hora DESC
        """, tuple(lista_elementos_ids))
        
        alarmes_candidatos = [{
            'id': row[0],
            'descricao': row[1],
            'data_hora': row[2],
            'nome_elemento': row[3],
            'nome_tipo_alarme': row[4]
        } for row in cursor.fetchall()]
        
    except Exception as e:
        print(f"Erro ao buscar alarmes candidatos: {e}")
    finally:
        conn.close()
    return alarmes_candidatos


def get_elementos_detalhes_por_ids(lista_ids):
    """
    Retorna uma lista de dicionários com detalhes de elementos
    baseado em uma lista de IDs.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    elementos = []
    
    if not lista_ids:
        return []

    placeholders = ','.join('?' for _ in lista_ids)
    
    try:
        cursor.execute(f"""
            SELECT 
                e.id, e.nome_elemento, g.nome_gerencia, se.nome_estado
            FROM elementos e
            LEFT JOIN gerencias g ON e.gerencia_id = g.id
            LEFT JOIN estados_enlace se ON e.estado_atual_id = se.id
            WHERE e.id IN ({placeholders})
            ORDER BY e.nome_elemento
        """, tuple(lista_ids))
        
        elementos = [{
            'id': row[0],
            'nome_elemento': row[1],
            'nome_gerencia': row[2],
            'estado_atual': row[3] or 'N/A'
        } for row in cursor.fetchall()]
        
    except Exception as e:
        print(f"Erro ao buscar detalhes dos elementos por IDs: {e}")
    finally:
        conn.close()
    return elementos


def get_elementos_no_mesmo_site(lista_elementos_ids):
    """
    Busca outros elementos que estão no "mesmo site" (baseado no prefixo do nome)
    que os elementos da lista de IDs fornecida.
    
    Ex: Se o ID 30 é 'RJO-ROC01-NKW03', busca por 'RJO-ROC01%'.
    """
    if not lista_elementos_ids:
        return []

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # 1. Descobrir os prefixos dos sites dos elementos do evento
    placeholders = ','.join('?' for _ in lista_elementos_ids)
    cursor.execute(f"""
        SELECT DISTINCT nome_elemento FROM elementos WHERE id IN ({placeholders})
    """, tuple(lista_elementos_ids))
    
    nomes_elementos = [row[0] for row in cursor.fetchall()]
    
    site_prefixes = set()
    for nome in nomes_elementos:
        try:
            # Assumindo que o prefixo são as duas primeiras partes do nome
            # Ex: 'RJO-ROC01-NKW03' -> 'RJO-ROC01'
            prefixo = "-".join(nome.strip().split('-')[:2])
            site_prefixes.add(prefixo)
        except Exception:
            continue # Ignora nomes mal formados
            
    if not site_prefixes:
        conn.close()
        return []

    # 2. Buscar TODOS os elementos que começam com esses prefixos
    #    e que NÃO SÃO os elementos originais do evento.
    query_parts = []
    params = []
    
    for prefix in site_prefixes:
        query_parts.append("e.nome_elemento LIKE ?")
        params.append(prefix + '%')
        
    # Constrói a cláusula WHERE para os prefixos
    where_clause_prefixes = " OR ".join(query_parts)
    
    # Constrói a cláusula WHERE para excluir os elementos originais
    placeholders_exclude = ','.join('?' for _ in lista_elementos_ids)
    params.extend(lista_elementos_ids)
    
    elementos_colocados = []
    try:
        query = f"""
            SELECT 
                e.id, e.nome_elemento, g.nome_gerencia, se.nome_estado
            FROM elementos e
            LEFT JOIN gerencias g ON e.gerencia_id = g.id
            LEFT JOIN estados_enlace se ON e.estado_atual_id = se.id
            WHERE ({where_clause_prefixes})
              AND e.id NOT IN ({placeholders_exclude})
            ORDER BY e.nome_elemento
        """
        
        cursor.execute(query, tuple(params))
        
        elementos_colocados = [{
            'id': row[0],
            'nome_elemento': row[1],
            'nome_gerencia': row[2],
            'estado_atual': row[3] or 'N/A'
        } for row in cursor.fetchall()]
        
    except Exception as e:
        print(f"Erro ao buscar elementos colocados: {e}")
    finally:
        conn.close()
        
    return elementos_colocados






def definir_alarme_pai(alarme_filho_id, alarme_pai_id):
    """
    Define a relação pai-filho na tabela de alarmes.
    Esta é a função de "aprendizado".
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE alarmes SET alarme_pai_id = ? WHERE id = ?
        """, (alarme_pai_id, alarme_filho_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao definir alarme pai: {e}")
        return False
    finally:
        conn.close()       
        
        
        
 
# --- FUNÇÕES PARA O PAINEL ADMINISTRATIVO (ADMIN DB) ---

def get_all_tables():
    """Retorna uma lista com o nome de todas as tabelas do banco."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def get_table_data(table_name):
    """
    Retorna as colunas e todos os dados de uma tabela específica.
    CUIDADO: Valide o table_name antes de chamar isso para evitar SQL Injection.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Permite acessar colunas pelo nome
    cursor = conn.cursor()
    
    try:
        # Busca dados
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Pega nome das colunas
        if cursor.description:
            columns = [description[0] for description in cursor.description]
        else:
            columns = []
            
        data = [dict(row) for row in rows]
        return {'columns': columns, 'data': data}
    except Exception as e:
        print(f"Erro ao ler tabela {table_name}: {e}")
        return {'columns': [], 'data': []}
    finally:
        conn.close()

def admin_update_cell(table_name, id_value, column_name, new_value):
    """Atualiza uma célula específica de qualquer tabela."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Nota: Em produção, validar se table_name e column_name são válidos é crucial.
        query = f"UPDATE {table_name} SET {column_name} = ? WHERE id = ?"
        cursor.execute(query, (new_value, id_value))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar admin: {e}")
        return False
    finally:
        conn.close()

def admin_delete_row(table_name, id_value):
    """Deleta uma linha inteira de qualquer tabela pelo ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        query = f"DELETE FROM {table_name} WHERE id = ?"
        cursor.execute(query, (id_value,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao deletar admin: {e}")
        return False
    finally:
        conn.close()
        
        
def update_element_databook(elem_id, site_id, sigla_cidade, cidade, uf, endereco, detentor_site_id=None):
    """Atualiza as informações de Databook de um elemento."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Tenta atualizar as colunas. 
        # Query segura
        sql = """
            UPDATE elementos
            SET site_id = ?, 
                sigla_cidade = ?, 
                cidade = ?, 
                uf = ?, 
                endereco = ?,
                detentor_site_id = ?
            WHERE id = ?
        """
        
        cursor.execute(sql, (site_id, sigla_cidade, cidade, uf, endereco, detentor_site_id, elem_id))
        
        if cursor.rowcount == 0:
            print(f"Aviso: Elemento ID {elem_id} não encontrado para update.")
            conn.close()
            return False
            
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.OperationalError as e:
        print(f"ERRO DE SQL (Coluna faltando?): {e}")
        return False
    except Exception as e:
        print(f"Erro ao atualizar Databook no DB: {e}")
        return False

def get_elementos_databook_completo():
    """Retorna lista para a gestão do Databook (incluindo campos vazios)."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nome_elemento, site_id, sigla_cidade, cidade, uf, endereco 
        FROM elementos 
        ORDER BY nome_elemento ASC
    """)
    # Converte para lista de dicionários
    colunas = ['id', 'nome_elemento', 'site_id', 'sigla_cidade', 'cidade', 'uf', 'endereco']
    resultados = []
    for row in cursor.fetchall():
        resultados.append(dict(zip(colunas, row)))
    conn.close()
    return resultados


def debug_get_longa_distancia_network():
    """
    Retorna todos os elementos marcados como Longa Distância
    e seus respectivos vizinhos para diagnóstico.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Busca quem é LD=1 e quem está conectado a ele (vizinho)
    # Trazemos também o status LD do vizinho para saber se a conexão é Híbrida ou Pura
    query = """
        SELECT 
            e_origem.id AS id_origem,
            e_origem.nome_elemento AS nome_origem,
            e_origem.longa_distancia AS ld_origem,
            
            e_destino.id AS id_destino,
            e_destino.nome_elemento AS nome_destino,
            e_destino.longa_distancia AS ld_destino
            
        FROM elementos e_origem
        -- Junta com a vizinhança para ver as conexões
        LEFT JOIN vizinhanca v ON e_origem.id = v.elemento_origem_id
        -- Junta com elementos de novo para pegar o nome do vizinho
        LEFT JOIN elementos e_destino ON v.elemento_destino_id = e_destino.id
        
        WHERE e_origem.longa_distancia = 1
        ORDER BY e_origem.nome_elemento
    """
    
    cursor.execute(query)
    resultados = []
    for row in cursor.fetchall():
        resultados.append({
            'id_origem': row[0],
            'nome_origem': row[1],
            'ld_origem': bool(row[2]),
            
            'id_destino': row[3],
            'nome_destino': row[4] if row[4] else "SEM VIZINHO (ILHADO)",
            'ld_destino': bool(row[5]) if row[5] is not None else False
        })
    
    conn.close()
    return resultados   


# --- FUNÇÕES PARA GESTÃO DE ESTOQUE/SOBRAS (NOVO) ---

def get_orphan_candidates():
    """
    Lista elementos que são Longa Distância (LD=1) MAS não têm vizinhos.
    E que AINDA NÃO estão na tabela de estoque.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Lógica: É LD=1, NÃO está em vizinhança, NÃO está em links, NÃO está em estoque
    query = """
        SELECT e.id, e.nome_elemento, e.cidade, e.site_id
        FROM elementos e
        WHERE e.longa_distancia = 1
        AND e.id NOT IN (SELECT elemento_origem_id FROM vizinhanca)
        AND e.id NOT IN (SELECT elemento_destino_id FROM vizinhanca)
        AND e.id NOT IN (SELECT elemento_a_id FROM links_capacidade)
        AND e.id NOT IN (SELECT elemento_b_id FROM links_capacidade)
        AND e.id NOT IN (SELECT elemento_id FROM estoque_sobras)
    """
    cursor.execute(query)
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

def move_to_stock(elemento_id, motivo="Sem vizinho detectado"):
    """
    Move um elemento para a tabela de estoque (quarentena).
    Isso fará ele sumir do Databook imediatamente.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        data_hoje = datetime.datetime.now(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO estoque_sobras (elemento_id, data_movimentacao, motivo) VALUES (?, ?, ?)", 
                       (elemento_id, data_hoje, motivo))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao mover para estoque: {e}")
        return False
    finally:
        conn.close()

def get_stock_items():
    """Retorna tudo que está no estoque."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = """
        SELECT s.*, e.nome_elemento 
        FROM estoque_sobras s
        JOIN elementos e ON s.elemento_id = e.id
        ORDER BY s.data_movimentacao DESC
    """
    cursor.execute(query)
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

def restore_from_stock(stock_id):
    """Remove do estoque, fazendo o elemento voltar a aparecer se for LD."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM estoque_sobras WHERE id = ?", (stock_id,))
    conn.commit()
    conn.close()
    
    # --- FUNÇÕES PARA AUDITORIA DE HIERARQUIA (ITEM 9) ---

def audit_hierarchy_inconsistencies():
    """
    Procura elementos que estão em anéis de Longa Distância (WDM_LD_...)
    mas que estão cadastrados com longa_distancia = 0.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT DISTINCT e.id, e.nome_elemento, a.nome_anel, e.longa_distancia
        FROM elementos e
        JOIN elemento_anel ea ON e.id = ea.elemento_id
        JOIN aneis a ON ea.anel_id = a.id
        WHERE (a.nome_anel LIKE 'WDM_LD_%' OR a.nome_anel = 'WDM_AG_CT_SEÇÃO_A')
        AND e.longa_distancia = 0
    """
    
    cursor.execute(query)
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

def fix_hierarchy_status(elemento_id):
    """
    Corrige um elemento específico, forçando longa_distancia = 1.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE elementos SET longa_distancia = 1 WHERE id = ?", (elemento_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao corrigir hierarquia: {e}")
        return False
    finally:
        conn.close()
        

# --- FUNÇÕES DO CONSTRUTOR DE DATABOOK (ITEM 10) ---

def detect_vendor_by_name(nome_elemento):
    """
    Detecta o fornecedor baseada na string do nome (Regra de Negócio).
    """
    nome = nome_elemento.upper()
    if 'CSW' in nome: return 'CISCO'
    if 'IFW' in nome or 'CTW' in nome: return 'INFINERA'
    if 'HWW' in nome or 'THW' in nome or 'HWP' in nome: return 'HUAWEI'
    if 'NKW' in nome: return 'NOKIA'
    return 'GENERICO'

def get_anel_metadata(anel_id):
    """Busca as informações de cabeçalho do Databook (Coerência, OTN, etc)."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM aneis_info_extra WHERE anel_id = ?", (anel_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    else:
        # Retorna padrão vazio se não existir
        return {
            'anel_id': anel_id, 'coerencia': '', 'matriz_otn': 0, 
            'swap_info': '', 'complemento_tecnologia': '', 'status_construcao': 'rascunho'
        }

def save_anel_metadata(data):
    """Salva ou atualiza os dados do cabeçalho do anel."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Tenta inserir ou substituir (REPLACE INTO é atalho do SQLite para Upsert)
        cursor.execute("""
            REPLACE INTO aneis_info_extra (anel_id, coerencia, matriz_otn, swap_info, complemento_tecnologia, status_construcao)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (data['anel_id'], data['coerencia'], data['matriz_otn'], data['swap_info'], data['complemento_tecnologia'], data['status_construcao']))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao salvar metadata anel: {e}")
        return False
    finally:
        conn.close()

def update_element_icon(elemento_id, tipo_icone, is_passive):
    """Atualiza o ícone visual do elemento (Quadrado, Triangulo, etc)."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE elementos SET tipo_icone = ?, is_passive = ? WHERE id = ?", 
                       (tipo_icone, is_passive, elemento_id))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()

def update_link_distance(origem_id, destino_id, km):
    """Atualiza a distância (KM) entre dois vizinhos."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Atualiza nos dois sentidos para garantir consistência visual
        cursor.execute("UPDATE vizinhanca SET distancia_km = ? WHERE elemento_origem_id = ? AND elemento_destino_id = ?", (km, origem_id, destino_id))
        cursor.execute("UPDATE vizinhanca SET distancia_km = ? WHERE elemento_origem_id = ? AND elemento_destino_id = ?", (km, destino_id, origem_id))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()

def create_passive_element(nome, anel_id, cidade_ref):
    """
    Cria um elemento passivo/genérico (ex: Passagem ou '...-LD') para compor o desenho.
    """
    # Usa a função existente mas força os flags de passivo/LD
    # Primeiro criamos o elemento
    novo_id = add_elemento(nome, nome, 1, None, longa_distancia=1) # Gerencia ID 1 provisório
    
    if novo_id:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        # Marca como passivo e ícone 'passivo' (bolinha pequena)
        cursor.execute("UPDATE elementos SET is_passive = 1, tipo_icone = 'passivo' WHERE id = ?", (novo_id,))
        # Associa ao anel para aparecer no filtro
        cursor.execute("INSERT OR IGNORE INTO elemento_anel (elemento_id, anel_id) VALUES (?, ?)", (novo_id, anel_id))
        
        # Tenta atualizar cidade se fornecida (para ajudar na localização)
        if cidade_ref:
            cursor.execute("UPDATE elementos SET cidade = ? WHERE id = ?", (cidade_ref, novo_id))
            
        conn.commit()
        conn.close()
        return novo_id
    return None        


# --- FUNÇÕES PARA SANITIZAÇÃO DE NOMES (ITEM 11) ---

def audit_accented_names():
    """
    Procura anéis que tenham caracteres acentuados ou especiais.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, nome_anel FROM aneis")
    all_rings = cursor.fetchall()
    
    bad_rings = []
    for ring in all_rings:
        original = ring['nome_anel']
        cleaned = normalize_name_string(original)
        
        # Se o limpo for diferente do original, achamos um "sujo"
        if original != cleaned:
            bad_rings.append({
                'id': ring['id'],
                'original': original,
                'sugestao': cleaned
            })
            
    conn.close()
    return bad_rings

def fix_accented_name(anel_id_sujo, novo_nome_limpo):
    """
    Tenta renomear o anel sujo para o limpo.
    SE O LIMPO JÁ EXISTIR: Faz a FUSÃO (Move os elementos e apaga o sujo).
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        # TENTATIVA 1: Simplesmente renomear (cenário ideal)
        cursor.execute("UPDATE aneis SET nome_anel = ? WHERE id = ?", (novo_nome_limpo, anel_id_sujo))
        conn.commit()
        return True, "Nome corrigido com sucesso!"

    except sqlite3.IntegrityError:
        # TENTATIVA 2: O nome limpo já existe! Vamos fazer a FUSÃO.
        print(f"Detectada duplicidade para '{novo_nome_limpo}'. Iniciando fusão...")
        
        try:
            # 1. Descobre o ID do anel limpo que já existe
            cursor.execute("SELECT id FROM aneis WHERE nome_anel = ?", (novo_nome_limpo,))
            row = cursor.fetchone()
            if not row:
                return False, "Erro estranho: Diz que existe mas não achei o ID."
            
            anel_id_limpo = row[0]
            
            # 2. Transfere os elementos do Sujo para o Limpo
            # O 'OR IGNORE' serve para não dar erro se o elemento já estiver nos dois (muito raro)
            cursor.execute("UPDATE OR IGNORE elemento_anel SET anel_id = ? WHERE anel_id = ?", (anel_id_limpo, anel_id_sujo))
            
            # 3. Transfere metadados (Item 10) se houver
            cursor.execute("UPDATE OR IGNORE aneis_info_extra SET anel_id = ? WHERE anel_id = ?", (anel_id_limpo, anel_id_sujo))
            
            # 4. Limpeza das sobras (elementos que já estavam nos dois ou dados redundantes)
            cursor.execute("DELETE FROM elemento_anel WHERE anel_id = ?", (anel_id_sujo,))
            cursor.execute("DELETE FROM aneis_info_extra WHERE anel_id = ?", (anel_id_sujo,))
            
            # 5. Apaga o anel Sujo (Agora ele está vazio e inútil)
            cursor.execute("DELETE FROM aneis WHERE id = ?", (anel_id_sujo,))
            
            conn.commit()
            return True, f"Fusão realizada! Elementos movidos para o anel existente ID {anel_id_limpo}."
            
        except Exception as e:
            print(f"Erro na fusão: {e}")
            conn.rollback()
            return False, f"Erro ao tentar fundir anéis: {e}"
                
    finally:
        conn.close()
        
        
        
# --- FUNÇÕES PARA EXPORTAR/IMPORTAR LINKS DE CAPACIDADE (ITEM 5.1 e 5.2) ---

def export_links_capacidade_csv():
    """
    Gera uma lista de dicionários com os dados textuais dos links de capacidade.
    Trazemos nomes em vez de IDs para facilitar a portabilidade.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Buscamos dados ricos para o CSV ficar completo como você pediu
    query = """
        SELECT 
            e1.nome_elemento as elemento_a,
            e2.nome_elemento as elemento_b,
            g.nome_gerencia,
            lc.facilidades_a,
            lc.facilidades_b,
            lc.swap_fibra_capacidade,
            -- Trazemos anéis e estados apenas para referência no Excel
            (SELECT group_concat(nome_anel) FROM aneis a JOIN elemento_anel ea ON a.id = ea.anel_id WHERE ea.elemento_id = e1.id) as aneis_a,
            se1.nome_estado as estado_a,
            se2.nome_estado as estado_b
        FROM links_capacidade lc
        JOIN elementos e1 ON lc.elemento_a_id = e1.id
        JOIN elementos e2 ON lc.elemento_b_id = e2.id
        LEFT JOIN gerencias g ON e1.gerencia_id = g.id
        LEFT JOIN estados_enlace se1 ON e1.estado_atual_id = se1.id
        LEFT JOIN estados_enlace se2 ON e2.estado_atual_id = se2.id
    """
    cursor.execute(query)
    
    # Nomes das colunas para o CSV
    columns = [
        "Nome Elemento A", "Nome Elemento B", "Gerencia", 
        "Facilidades A", "Facilidades B", "Swap/Provedor", 
        "Aneis (Ref)", "Estado A", "Estado B"
    ]
    
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    
    conn.close()
    return data

def get_all_fabricantes_dados():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_fabricante FROM fabricantes_dados ORDER BY nome_fabricante")
    fabs = [{'id': row[0], 'nome_fabricante': row[1]} for row in cursor.fetchall()]
    conn.close()
    return fabs


# --- FUNÇÃO DE INTELIGÊNCIA / CORRELAÇÃO ---
def verificar_correlacao_tx(circuito_dados_id):
    """
    O PULO DO GATO:
    Verifica se algum elemento da rota física (TX) deste circuito 
    está envolvido em eventos de infraestrutura (Rompimento, HW) recentes.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # A Query Mágica:
        # 1. Pega os elementos da rota deste circuito (rota_circuitos_tx)
        # 2. Cruza com elementos afetados em eventos (evento_elemento)
        # 3. Filtra eventos que NÃO sejam de DADOS (queremos achar a causa física)
        # 4. Filtra eventos recentes (últimas 24h) para não pegar histórico velho
        
        query = """
            SELECT DISTINCT 
                e.id as evento_id, 
                e.titulo, 
                e.tipo_evento, 
                e.data_hora_abertura,
                el.nome_elemento as elemento_afetado,
                r.ordem_salto
            FROM rota_circuitos_tx r
            JOIN evento_elemento ee ON r.elemento_tx_id = ee.elemento_id
            JOIN eventos e ON ee.evento_id = e.id
            JOIN elementos el ON r.elemento_tx_id = el.id
            WHERE r.circuito_dados_id = ?
              AND e.tipo_evento NOT IN ('DADOS') 
              AND e.data_hora_abertura >= datetime('now', '-24 hours', 'localtime')
            ORDER BY r.ordem_salto
        """
        
        cursor.execute(query, (circuito_dados_id,))
        resultados = [dict(row) for row in cursor.fetchall()]
        
        return resultados

    except Exception as e:
        print(f"Erro na correlação: {e}")
        return []
    finally:
        conn.close()
        
        
        
# --- RAIO-X DA FIBRA (CRUZAMENTO FÍSICO x LÓGICO) ---
# --- 1. RAIO-X DA FIBRA (CORRIGIDO: SEM DUPLICATAS) ---
def get_circuitos_afetados_por_link(nome_origem, nome_destino):
    """
    Retorna quais circuitos de dados passam pela fibra que conecta 
    o nó 'nome_origem' ao nó 'nome_destino'.
    
    ATUALIZADA: Usa GROUP BY para agrupar circuitos com o mesmo ACCID,
    evitando que testes repetidos (mesmo ACCID, IDs diferentes) poluam a lista.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # 1. Resolve os Nomes (Short Names) para IDs reais
        cursor.execute("SELECT id FROM elementos WHERE nome_elemento LIKE ? OR nome_elemento_curto = ?", (f"{nome_origem}%", nome_origem))
        ids_origem = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT id FROM elementos WHERE nome_elemento LIKE ? OR nome_elemento_curto = ?", (f"{nome_destino}%", nome_destino))
        ids_destino = [r[0] for r in cursor.fetchall()]

        if not ids_origem or not ids_destino:
            return []

        # 2. A Query do Raio-X (COM GROUP BY ACCID)
        pl_orig = ','.join('?' * len(ids_origem))
        pl_dest = ','.join('?' * len(ids_destino))

        query = f"""
            SELECT 
                c.accid, 
                MAX(c.tipo_falha) as tipo_falha, 
                MAX(e1.hostname) as origem, 
                MAX(e2.hostname) as destino,
                COUNT(c.id) as qtd_registros
            FROM rota_circuitos_tx r1
            JOIN rota_circuitos_tx r2 ON r1.circuito_dados_id = r2.circuito_dados_id
            JOIN circuitos_dados c ON r1.circuito_dados_id = c.id
            LEFT JOIN equipamentos_dados e1 ON c.roteador_origem_id = e1.id
            LEFT JOIN equipamentos_dados e2 ON c.roteador_destino_id = e2.id
            WHERE 
                (
                    (r1.elemento_tx_id IN ({pl_orig}) AND r2.elemento_tx_id IN ({pl_dest}))
                    OR 
                    (r1.elemento_tx_id IN ({pl_dest}) AND r2.elemento_tx_id IN ({pl_orig}))
                )
                AND ABS(r1.ordem_salto - r2.ordem_salto) = 1
            GROUP BY c.accid
        """
        
        params = ids_origem + ids_destino + ids_destino + ids_origem
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        print(f"Erro no Raio-X: {e}")
        return []
    finally:
        conn.close()


def get_circuitos_por_site(nome_site):
    """
    Busca todos os circuitos que passam por qualquer elemento deste site.
    JÁ ESTÁ CORRETA (COM GROUP BY).
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # 1. Acha elementos do site (por nome aproximado ou site_id)
        cursor.execute("""
            SELECT id FROM elementos 
            WHERE site_id = ? OR nome_elemento LIKE ?
        """, (nome_site, f"{nome_site}%"))
        ids_elementos = [r[0] for r in cursor.fetchall()]
        
        if not ids_elementos: return []
        
        pl_elem = ','.join('?' * len(ids_elementos))
        
        # 2. Busca circuitos onde esses elementos são Salto, Origem ou Destino
        query = f"""
            SELECT 
                c.accid, 
                MAX(c.tipo_falha) as tipo_falha,
                MAX(e.nome_elemento) as elemento_encontrado
            FROM rota_circuitos_tx r
            JOIN circuitos_dados c ON r.circuito_dados_id = c.id
            JOIN elementos e ON r.elemento_tx_id = e.id
            WHERE r.elemento_tx_id IN ({pl_elem})
            GROUP BY c.accid
        """
        cursor.execute(query, ids_elementos)
        return [dict(row) for row in cursor.fetchall()]
        
    except Exception as e:
        print(f"Erro circuitos por site: {e}")
        return []
    finally:
        conn.close()
        
        
def get_all_routers_debug():
    """
    Retorna todos os roteadores para o Debug Panel (Item 12.1).
    ATUALIZADO: Faz JOIN com fabricante para mostrar o nome real (Cisco/Huawei)
    e trata possíveis erros de coluna.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    routers = []
    try:
        # Tenta buscar fazendo o JOIN correto com a tabela de fabricantes
        # Isso garante que veremos "CISCO" e não apenas um ID numérico ou erro
        # Trocamos ip_loopback por ip_gerencia que é mais comum no seu padrão
        cursor.execute("""
            SELECT 
                ed.id, 
                ed.hostname, 
                ed.ip_gerencia, 
                fd.nome_fabricante, 
                ed.modelo, 
                ed.site_id
            FROM equipamentos_dados ed
            LEFT JOIN fabricantes_dados fd ON ed.fabricante_id = fd.id
            ORDER BY ed.hostname ASC
        """)
        
        for row in cursor.fetchall():
            routers.append({
                'id': row[0],
                'hostname': row[1] if row[1] else "Sem Hostname",
                'ip': row[2] if row[2] else "N/A",
                'vendor': row[3] if row[3] else "Genérico", # Agora vem do JOIN
                'modelo': row[4] if row[4] else "",
                'site_id_atual': row[5]  # O campo mais importante para o Debug
            })
            
    except Exception as e:
        # Fallback de segurança: Se der erro no SQL (ex: colunas antigas), 
        # tenta pegar o básico sem JOIN para não quebrar a tela
        try:
            cursor.execute("SELECT id, hostname, 'N/A', 'N/A', 'N/A', site_id FROM equipamentos_dados")
            for row in cursor.fetchall():
                routers.append({
                    'id': row[0], 'hostname': row[1], 'ip': 'N/A', 
                    'vendor': 'N/A', 'modelo': 'N/A', 'site_id_atual': row[5]
                })
        except:
            print(f"Erro crítico ao buscar roteadores debug: {e}")
            return []

    finally:
        conn.close()
        
    return routers        


# --- FUNÇÃO NOVA: BUSCAR CIRCUITO COMPLETO POR ACCID (PARA AUTO-PREENCHIMENTO) ---
def get_full_circuit_data_by_accid(accid):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Busca dados do circuito e roteadores
        cursor.execute("""
            SELECT 
                c.id, c.accid, c.observacoes,
                
                e1.hostname as orig_host, e1.id as orig_id,
                f1.id as orig_fab_id, s1.id as orig_status_id, 
                
                e2.hostname as dest_host, e2.id as dest_id,
                f2.id as dest_fab_id, s2.id as dest_status_id

            FROM circuitos_dados c
            LEFT JOIN equipamentos_dados e1 ON c.roteador_origem_id = e1.id
            LEFT JOIN fabricantes_dados f1 ON e1.fabricante_id = f1.id
            LEFT JOIN status_dados s1 ON c.status_origem_id = s1.id
            
            LEFT JOIN equipamentos_dados e2 ON c.roteador_destino_id = e2.id
            LEFT JOIN fabricantes_dados f2 ON e2.fabricante_id = f2.id
            LEFT JOIN status_dados s2 ON c.status_destino_id = s2.id
            
            WHERE c.accid = ?
            LIMIT 1
        """, (accid,))
        
        row = cursor.fetchone()
        if not row: return None
        
        circuito_data = dict(row)
        
        # 2. Busca Rota TX (Saltos)
        cursor.execute("""
            SELECT e.id, e.nome_elemento
            FROM rota_circuitos_tx r
            JOIN elementos e ON r.elemento_tx_id = e.id
            WHERE r.circuito_dados_id = ?
            ORDER BY r.ordem_salto
        """, (circuito_data['id'],))
        
        rota = [dict(r) for r in cursor.fetchall()]
        
        return {'circuito': circuito_data, 'rota': rota}

    except Exception as e:
        print(f"Erro ao buscar circuito completo: {e}")
        return None
    finally:
        conn.close()
        
        
# ==============================================================================
# --- GESTÃO DE TIPOS DE FALHA DE CIRCUITO (CAMADA DE SERVIÇO - ACCID) ---
# ==============================================================================

def init_tabela_falhas_circuito():
    """Cria a tabela de tipos de falha se não existir e popula com padrões."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tipos_falha_circuito (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_falha TEXT UNIQUE NOT NULL,
            descricao TEXT,
            gravidade INTEGER DEFAULT 1 -- 1: Baixa, 2: Média, 3: Alta (Crítica)
        )
    ''')
    
    # Carga Inicial (Seed) - Padrões de Mercado
    cursor.execute("SELECT count(*) FROM tipos_falha_circuito")
    if cursor.fetchone()[0] == 0:
        iniciais = [
            ('Link Down / Queda', 'Interrupção total do serviço', 3),
            ('Atenuação / CRC', 'Perda de pacotes por qualidade do sinal', 2),
            ('Latência Alta', 'Atraso na comunicação (>100ms)', 2),
            ('Packet Loss', 'Perda de pacotes intermitente', 2),
            ('BGP Flap', 'Oscilação no protocolo de roteamento', 3),
            ('Rompimento Fibra (TX)', 'Corte físico identificado na rede de transporte', 3)
        ]
        cursor.executemany("INSERT INTO tipos_falha_circuito (nome_falha, descricao, gravidade) VALUES (?, ?, ?)", iniciais)
        print("--- Tabela tipos_falha_circuito inicializada com padrões. ---")

    conn.commit()
    conn.close()

# Chame esta função dentro do seu init_db() principal ou rode uma vez:
# init_tabela_falhas_circuito() 

def add_tipo_falha_circuito(nome_falha, descricao=None):
    """Adiciona um novo tipo de falha de circuito."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO tipos_falha_circuito (nome_falha, descricao) VALUES (?, ?)", (nome_falha.strip(), descricao))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_tipos_falha_circuito():
    """Retorna todas as falhas cadastradas para o dropdown."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tipos_falha_circuito ORDER BY nome_falha ASC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()  
        
        
        
# --- ADICIONE ISSO NO FINAL DO ARQUIVO database.py ---

def get_all_physical_failures_last_8h():
    """
    Retorna um SET de tuplas (site_a, site_b) que possuem falha FÍSICA
    (Link Down, LOS, Rompimento) nas últimas 8 horas.
    Otimizado para evitar N+1 queries.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Busca alarmes físicos recentes (regra de 8h)
    # Ajuste os filtros 'LIKE' conforme os nomes reais dos seus alarmes de TX
    query = """
        SELECT e.nome_elemento
        FROM alarmes a
        JOIN elementos e ON a.elemento_id = e.id
        WHERE a.data_hora >= datetime('now', '-8 hours', 'localtime')
          AND (
               a.descricao LIKE '%Link Down%' 
            OR a.descricao LIKE '%LOS%' 
            OR a.descricao LIKE '%Rompimento%'
            OR a.descricao LIKE '%E1%'
          )
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    failures = set()
    # Aqui precisamos de uma lógica para saber quais SITES esse elemento conecta.
    # Como seu sistema parece basear a falha no elemento de link, 
    # vou assumir que precisamos cruzar isso no app.py ou 
    # que o nome do elemento ajuda.
    # Pela sua lógica anterior, você verificava se existia alarme no link entre A e B.
    
    # Para simplificar e não quebrar a lógica complexa de nomes:
    # Vamos retornar um dicionário ou lista de elementos com falha
    # e deixamos o Python fazer o "match" rápido na memória.
    
    broken_elements = {row[0] for row in rows} 
    return broken_elements              
        

# --- 2. BUSCA DE ELEMENTOS PARA DIAGRAMA (CORRIGIDO: TRAZ ISOLADOS) ---
def import_links_capacidade_from_csv_data(csv_rows):
    """
    Recebe uma lista de linhas (dicts) do CSV e insere no banco.
    Retorna (sucessos, erros).
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    sucessos = 0
    erros = []
    
    for i, row in enumerate(csv_rows):
        try:
            nome_a = row.get("Nome Elemento A", "").strip()
            nome_b = row.get("Nome Elemento B", "").strip()
            fac_a = row.get("Facilidades A", "")
            fac_b = row.get("Facilidades B", "")
            swap = row.get("Swap/Provedor", "")
            
            if not nome_a or not nome_b:
                continue

            # 1. Descobre os IDs ATUAIS baseados nos nomes
            cursor.execute("SELECT id FROM elementos WHERE nome_elemento = ?", (nome_a,))
            res_a = cursor.fetchone()
            
            cursor.execute("SELECT id FROM elementos WHERE nome_elemento = ?", (nome_b,))
            res_b = cursor.fetchone()
            
            if res_a and res_b:
                id_a = res_a[0]
                id_b = res_b[0]
                
                # 2. Insere na tabela (Evita duplicatas se já existir exatamente igual)
                # Verifica se já existe
                cursor.execute("""
                    SELECT id FROM links_capacidade 
                    WHERE (elemento_a_id = ? AND elemento_b_id = ?) 
                       OR (elemento_a_id = ? AND elemento_b_id = ?)
                """, (id_a, id_b, id_b, id_a))
                
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO links_capacidade (elemento_a_id, elemento_b_id, facilidades_a, facilidades_b, swap_fibra_capacidade)
                        VALUES (?, ?, ?, ?, ?)
                    """, (id_a, id_b, fac_a, fac_b, swap))
                    sucessos += 1
                else:
                    erros.append(f"Linha {i+1}: Link já existe entre {nome_a} e {nome_b}")
            else:
                erros.append(f"Linha {i+1}: Elemento não encontrado ({nome_a} ou {nome_b})")
                
        except Exception as e:
            erros.append(f"Linha {i+1}: Erro técnico - {str(e)}")
            
    conn.commit()
    conn.close()
    return sucessos, erros