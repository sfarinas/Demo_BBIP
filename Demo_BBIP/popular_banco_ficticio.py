import sqlite3
import datetime
import os
import random

# CONFIGURAÇÃO DE VOLUME
QTD_SITES_MASSA = 60       
QTD_CIRCUITOS_MASSA = 150  
DB_NAME = 'rede_db_demo.sqlite'

def criar_schema(conn):
    cursor = conn.cursor()
    print("--- 1. Criando Tabelas Estruturais Completas...")

    # Tabelas Base
    cursor.execute("CREATE TABLE IF NOT EXISTS gerencias (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_gerencia TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS detentores_site (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_detentor TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS estados_enlace (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_estado TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS fabricantes_dados (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_fabricante TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS status_dados (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_status TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS tipos_alarmes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_tipo_alarme TEXT, equipe_responsavel TEXT, eh_abertura_enlace_trigger INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS alarmes_dados (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_alarme TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS aneis (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_anel TEXT, detentor_site_id INTEGER)")

    # Tabela Elementos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS elementos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_elemento TEXT NOT NULL,
            nome_elemento_curto TEXT,  
            site_id TEXT,
            uf TEXT,
            cidade TEXT,
            tipo_icone TEXT DEFAULT 'roadm',
            cluster_uf TEXT,
            cluster_regiao TEXT,
            gerencia_id INTEGER DEFAULT 1,
            estado_atual_id INTEGER DEFAULT 1,
            detentor_site_id INTEGER DEFAULT 1,
            anel_id INTEGER DEFAULT 1,
            esta_afetado INTEGER DEFAULT 0,
            afetado_ate DATETIME,
            longa_distancia INTEGER DEFAULT 0,
            is_passive INTEGER DEFAULT 0
        )
    ''')

    # Equipamentos Dados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipamentos_dados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL,
            site_id TEXT,
            fabricante_id INTEGER,
            ip_gerencia TEXT
        )
    ''')

    # Vizinhança
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vizinhanca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elemento_origem_id INTEGER,
            elemento_destino_id INTEGER,
            distancia_km REAL,
            accid_lc TEXT,
            swap_fibra_info TEXT
        )
    ''')

    # Circuitos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS circuitos_dados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accid TEXT,
            roteador_origem_id INTEGER,
            roteador_destino_id INTEGER,
            status_origem_id INTEGER,
            status_destino_id INTEGER,
            tipo_falha TEXT,
            evento_id INTEGER,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Rota Circuitos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rota_circuitos_tx (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circuito_dados_id INTEGER,
            ordem_salto INTEGER,
            elemento_tx_id INTEGER
        )
    ''')

    # --- CORREÇÃO AQUI: Tabela Alarmes Completa ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alarmes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elemento_id INTEGER,
            tipo_alarme_id INTEGER,
            descricao TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            alarme_pai_id INTEGER,      -- COLUNA QUE FALTAVA
            status_id INTEGER DEFAULT 1, -- 1=Ativo, 2=Reconhecido, 3=Limpo
            ack_usuario TEXT,
            ack_data_hora DATETIME
        )
    ''')

    # Eventos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            descricao TEXT,
            data_hora_abertura DATETIME,
            proxima_atualizacao DATETIME,
            tipo_evento TEXT,
            estado_origem_id INTEGER,
            estado_destino_id INTEGER,
            teste_otdr_em_curso INTEGER DEFAULT 0  -- <-- A COLUNA FALTANTE AQUI
        )
    ''')
    
    # Associações
    cursor.execute("CREATE TABLE IF NOT EXISTS evento_elemento (evento_id INTEGER, elemento_id INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS evento_alarme (evento_id INTEGER, alarme_id INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS elemento_anel (elemento_id INTEGER, anel_id INTEGER)")

    conn.commit()

def popular_dados(conn):
    c = conn.cursor()
    print("--- 2. Inserindo Lookups...")
    c.execute("INSERT INTO gerencias (nome_gerencia) VALUES ('WAYNE-NET'), ('STARK-IND'), ('SHIELD-OPS')")
    c.execute("INSERT INTO detentores_site (nome_detentor) VALUES ('WAYNE ENTERPRISES'), ('LEXCORP'), ('S.H.I.E.L.D.'), ('ACME CORP')")
    c.execute("INSERT INTO status_dados (id, nome_status) VALUES (1, 'UP'), (2, 'DOWN')")
    c.execute("INSERT INTO fabricantes_dados (id, nome_fabricante) VALUES (1, 'CISCO'), (2, 'HUAWEI'), (3, 'NOKIA'), (4, 'JUNIPER')")
    c.execute("INSERT INTO tipos_alarmes (nome_tipo_alarme, equipe_responsavel) VALUES ('LOS', 'CAMPO'), ('Link Down', 'NOC')")
    c.execute("INSERT INTO aneis (nome_anel) VALUES ('CORE-LESTE'), ('CORE-OESTE'), ('ANEL-METRO')")

    print("--- 3. Criando CORE da Rede (Cenários Reais)...")
    core_sites = [
        ('GOTHAM-HWW01', 'GOTHAM', 'NJ', 'Gotham City'),
        ('GOTHAM-HWW02', 'GOTHAM', 'NJ', 'Gotham City'), 
        ('METROPOLIS-CSCO01', 'METROPOLIS', 'NY', 'Metropolis'),
        ('WAKANDA-HWW01', 'WAKANDA', 'AF', 'Birnin Zana'),
        ('ATLANTIS-HWW01', 'ATLANTIS', 'OC', 'Poseidonis'),
        ('STAR-LABS-HWW01', 'STAR-LABS', 'MO', 'Central City')
    ]
    
    tx_ids = [] 
    tx_map = {} 
    
    for nome, site_id, uf, cid in core_sites:
        c.execute("""
            INSERT INTO elementos (nome_elemento, nome_elemento_curto, site_id, uf, cidade, gerencia_id, tipo_icone, cluster_uf, cluster_regiao, detentor_site_id, anel_id) 
            VALUES (?, ?, ?, ?, ?, 1, 'roadm', ?, 'CORE', 1, 1)
        """, (nome, nome[:10], site_id, uf, cid, uf))
        lid = c.lastrowid
        tx_map[nome] = lid
        tx_ids.append(lid)

    print(f"--- 4. Gerando {QTD_SITES_MASSA} Sites Regionais (Massa de Dados)...")
    ufs = ['NY', 'NJ', 'TX', 'CA', 'FL', 'NV']
    cidades_base = ['Springfield', 'Shelbyville', 'Smallville', 'Riverdale', 'Hill Valley', 'Vice City']
    
    generated_tx_ids = []
    
    for i in range(1, QTD_SITES_MASSA + 1):
        uf = random.choice(ufs)
        cid = random.choice(cidades_base)
        nome = f"POP-{uf}-{cid.upper()}-{i:03d}"
        site_id = f"POP-{uf}-{i:03d}"
        detentor = random.randint(1, 4)
        
        c.execute("""
            INSERT INTO elementos (nome_elemento, nome_elemento_curto, site_id, uf, cidade, gerencia_id, tipo_icone, cluster_uf, cluster_regiao, detentor_site_id, anel_id) 
            VALUES (?, ?, ?, ?, ?, 2, 'site', ?, 'ACESSO', ?, 2)
        """, (nome, nome[:12], site_id, uf, cid, uf, detentor))
        generated_tx_ids.append(c.lastrowid)

    print("--- 5. Criando Roteadores e Conectando Massa...")
    all_routers = []
    
    # Roteadores Core
    core_routers = [
        ('BAT-ROUTER-01', 'GOTHAM', 1),
        ('LEX-CORP-SW01', 'METROPOLIS', 1),
        ('SHURI-GW01', 'WAKANDA', 2),
        ('AQUA-R01', 'ATLANTIS', 2),
        ('JOKER-UNKNOWN', '', 1)
    ]
    rot_map = {}
    for host, site, fab in core_routers:
        c.execute("INSERT INTO equipamentos_dados (hostname, site_id, fabricante_id) VALUES (?, ?, ?)", (host, site, fab))
        rid = c.lastrowid
        rot_map[host] = rid
        all_routers.append(rid)

    # Roteadores Massa
    for idx, tx_id in enumerate(generated_tx_ids):
        c.execute("SELECT site_id FROM elementos WHERE id = ?", (tx_id,))
        s_id = c.fetchone()[0]
        hostname = f"RTR-{s_id}"
        fab = random.randint(1, 4)
        c.execute("INSERT INTO equipamentos_dados (hostname, site_id, fabricante_id) VALUES (?, ?, ?)", (hostname, s_id, fab))
        all_routers.append(c.lastrowid)
        
        pai_id = random.choice(tx_ids) 
        dist = random.randint(10, 500)
        c.execute("INSERT INTO vizinhanca (elemento_origem_id, elemento_destino_id, distancia_km) VALUES (?, ?, ?)", (tx_id, pai_id, dist))
        
        if random.random() < 0.3 and idx > 0:
            vizinho_id = generated_tx_ids[idx-1]
            c.execute("INSERT INTO vizinhanca (elemento_origem_id, elemento_destino_id, distancia_km) VALUES (?, ?, ?)", (tx_id, vizinho_id, 20))

    # Conexões Core
    c.execute("INSERT INTO vizinhanca (elemento_origem_id, elemento_destino_id, distancia_km) VALUES (?, ?, 50)", (tx_map['GOTHAM-HWW02'], tx_map['METROPOLIS-CSCO01']))
    c.execute("INSERT INTO vizinhanca (elemento_origem_id, elemento_destino_id, distancia_km) VALUES (?, ?, 8000)", (tx_map['WAKANDA-HWW01'], tx_map['ATLANTIS-HWW01']))

    print(f"--- 6. Gerando {QTD_CIRCUITOS_MASSA} Circuitos Aleatórios...")
    for _ in range(QTD_CIRCUITOS_MASSA):
        r_a = random.choice(all_routers)
        r_b = random.choice(all_routers)
        if r_a != r_b:
            accid = f"CKT-RANDOM-{random.randint(1000, 9999)}"
            c.execute("INSERT INTO circuitos_dados (accid, roteador_origem_id, roteador_destino_id, status_origem_id) VALUES (?, ?, ?, 1)", (accid, r_a, r_b))

    print("--- 7. Recriando Cenários Específicos...")
    
    # CENÁRIO 1: VERMELHO
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Alarme com campos extras para não quebrar
    c.execute("INSERT INTO alarmes (elemento_id, descricao, data_hora, status_id) VALUES (?, 'Link Down - Fiber Cut', ?, 1)", (tx_map['GOTHAM-HWW02'], now_str))
    
    futuro = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE elementos SET esta_afetado=1, afetado_ate=? WHERE id=?", (futuro, tx_map['GOTHAM-HWW02']))
    
    c.execute("""
        INSERT INTO circuitos_dados (accid, roteador_origem_id, roteador_destino_id, status_origem_id, tipo_falha, data_criacao)
        VALUES ('CKT-JUSTICE-01', ?, ?, 2, 'Link Down', ?)
    """, (rot_map['BAT-ROUTER-01'], rot_map['LEX-CORP-SW01'], now_str))
    ckt_red = c.lastrowid
    c.execute("INSERT INTO rota_circuitos_tx (circuito_dados_id, ordem_salto, elemento_tx_id) VALUES (?, 1, ?)", (ckt_red, tx_map['GOTHAM-HWW02']))
    c.execute("INSERT INTO rota_circuitos_tx (circuito_dados_id, ordem_salto, elemento_tx_id) VALUES (?, 2, ?)", (ckt_red, tx_map['METROPOLIS-CSCO01']))

    # CENÁRIO 2: AMARELO
    c.execute("""
        INSERT INTO circuitos_dados (accid, roteador_origem_id, roteador_destino_id, status_origem_id, tipo_falha, data_criacao)
        VALUES ('CKT-VIBRANIUM-007', ?, ?, 2, 'Protocol Down', ?)
    """, (rot_map['SHURI-GW01'], rot_map['AQUA-R01'], now_str))
    ckt_yel = c.lastrowid
    c.execute("INSERT INTO rota_circuitos_tx (circuito_dados_id, ordem_salto, elemento_tx_id) VALUES (?, 1, ?)", (ckt_yel, tx_map['WAKANDA-HWW01']))
    c.execute("INSERT INTO rota_circuitos_tx (circuito_dados_id, ordem_salto, elemento_tx_id) VALUES (?, 2, ?)", (ckt_yel, tx_map['ATLANTIS-HWW01']))

    # CENÁRIO 3: NUVEM
    c.execute("""
        INSERT INTO circuitos_dados (accid, roteador_origem_id, roteador_destino_id, status_origem_id, data_criacao)
        VALUES ('CKT-DARK-WEB', ?, ?, 1, ?)
    """, (rot_map['BAT-ROUTER-01'], rot_map['JOKER-UNKNOWN'], now_str))

    conn.commit()
    print("--- SUCESSO FINAL! Banco Massivo Gerado (Compatível com App Atual). ---")

if __name__ == '__main__':
    if os.path.exists(DB_NAME):
        try:
            os.remove(DB_NAME)
        except:
            print(f"AVISO: Não foi possível deletar {DB_NAME}. Feche o App e tente de novo.")
    
    conn = sqlite3.connect(DB_NAME)
    criar_schema(conn)
    popular_dados(conn)
    conn.close()