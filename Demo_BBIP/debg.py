import sqlite3
import datetime
import pytz
import os

# Configuração
DATABASE_NAME = 'rede_db.sqlite'
LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo')

def get_server_info():
    """
    Retorna informações sobre o horário do servidor e fusos.
    """
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    local_now = datetime.datetime.now().astimezone(LOCAL_TIMEZONE)
    
    return {
        "UTC Time (Servidor)": utc_now.strftime('%Y-%m-%d %H:%M:%S'),
        "Local Time (Brasília)": local_now.strftime('%Y-%m-%d %H:%M:%S'),
        "Fuso Horário Configurado": str(LOCAL_TIMEZONE),
        "Database File Exists?": os.path.exists(DATABASE_NAME)
    }

def inspect_element_raw(nome_parcial):
    """
    Busca um elemento pelo nome e retorna EXATAMENTE o que está gravado.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM elementos WHERE nome_elemento LIKE ?", (f"%{nome_parcial}%",))
        rows = cursor.fetchall()
        
        resultados = []
        for row in rows:
            row_dict = dict(row)
            analise = "OK"
            if "'" in row_dict['nome_elemento'] or '"' in row_dict['nome_elemento']:
                analise = "PERIGO: Contém aspas!"
            
            resultados.append({
                "DADOS BRUTOS": row_dict,
                "ANÁLISE": analise
            })
            
        return resultados
    except Exception as e:
        return [{"ERRO": str(e)}]
    finally:
        conn.close()

def check_broken_links():
    """
    Verifica se existem links apontando para IDs inexistentes.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    report = []
    
    try:
        cursor.execute("""
            SELECT v.id, v.elemento_origem_id, v.elemento_destino_id 
            FROM vizinhanca v
            LEFT JOIN elementos e1 ON v.elemento_origem_id = e1.id
            LEFT JOIN elementos e2 ON v.elemento_destino_id = e2.id
            WHERE e1.id IS NULL OR e2.id IS NULL
        """)
        
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                report.append(f"ALERTA: ID {row[0]} aponta para fantasmas ({row[1]} -> {row[2]})")
        else:
            report.append("Tabela Vizinhança: OK")
            
    except Exception as e:
        report.append(f"Erro: {e}")
    finally:
        conn.close()

    return report

def diagnose_diagram_colors():
    """
    Explica por que um elemento está pintado de determinada cor.
    """
    import database
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    report = []
    now = datetime.datetime.now()
    report.append(f"--- DIAGNÓSTICO DE CORES ---")
    
    try:
        elements = database.get_all_diagram_elements()
        
        # Busca IDs de Links de Capacidade
        cursor.execute("SELECT elemento_a_id FROM links_capacidade UNION SELECT elemento_b_id FROM links_capacidade")
        link_cap_ids = {row[0] for row in cursor.fetchall()}
        
        count_affected = 0
        
        for elem in elements:
            is_link_cap = elem['id'] in link_cap_ids
            is_affected = str(elem.get('esta_afetado')) in ['1', 'True']
            
            if is_affected or is_link_cap:
                count_affected += 1
                name = elem['nome_elemento']
                date_str = elem.get('afetado_ate')
                event_type = elem.get('tipo_evento_ativo')
                
                status_msg = f"ELEMENTO: {name} (ID: {elem['id']})"
                if is_link_cap: status_msg += f" [É Link de Capacidade]"
                
                if is_affected:
                    status_msg += f"\n   - Afetado? SIM | Evento: '{event_type}' | Até: '{date_str}'"
                    is_active = False
                    if date_str:
                        try:
                            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                            if dt > now:
                                is_active = True
                                status_msg += f"\n   - Data: VÁLIDA (Expira em {dt - now})"
                            else:
                                status_msg += f"\n   - Data: EXPIRADA"
                        except:
                            is_active = True
                    else:
                        is_active = True
                    
                    if is_active:
                        if event_type == 'Falha de Link de Capacidade':
                            status_msg += "\n   -> COR: VERMELHO 🔴 (Crítico)"
                        else:
                            status_msg += "\n   -> COR: LARANJA 🟠 (Alarme)"
                    else:
                        if is_link_cap:
                            status_msg += "\n   -> COR: VIOLETA 🟣 (Link Normal)"
                        else:
                            status_msg += "\n   -> COR: CINZA ⚪ (Normal)"
                else:
                    status_msg += "\n   -> COR: VIOLETA 🟣 (Link Normal)"
                
                report.append(status_msg)
        
        if count_affected == 0:
            report.append("Nenhum elemento relevante encontrado.")
            
    except Exception as e:
        report.append(f"ERRO: {e}")
    finally:
        conn.close()
        
    return report

def inspect_link_capacidade_table():
    """
    Verifica a saúde da tabela links_capacidade (ATUALIZADO PARA SWAP).
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    report = []
    report.append("--- INSPEÇÃO DA TABELA LINKS_CAPACIDADE ---")
    
    try:
        # 1. Verifica Colunas
        cursor.execute("PRAGMA table_info(links_capacidade)")
        columns_info = cursor.fetchall()
        col_names = [col['name'] for col in columns_info]
        report.append(f"Colunas: {col_names}")
        
        # --- CORREÇÃO AQUI: Agora procuramos a coluna NOVA ---
        if 'swap_fibra_capacidade' not in col_names:
             # Se não achar a nova, verifica se tem a velha
             if 'detentor_site_id' in col_names:
                 report.append("🚨 ALERTA: Tabela está no formato ANTIGO. Use o Reset!")
             else:
                 report.append("🚨 ERRO CRÍTICO: Tabela irreconhecível.")
        else:
            report.append("✅ Schema: A coluna 'swap_fibra_capacidade' existe (Banco Atualizado!).")

        # 2. Contagem
        cursor.execute("SELECT COUNT(*) FROM links_capacidade")
        count = cursor.fetchone()[0]
        report.append(f"Total de Registros: {count}")
        
        # 3. Dados
        cursor.execute("SELECT * FROM links_capacidade ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        if rows:
            report.append("--- Últimos 5 Registros ---")
            for row in rows:
                report.append(dict(row))
        else:
            report.append("--- Tabela está VAZIA ---")

    except Exception as e:
        report.append(f"Erro: {e}")
    finally:
        conn.close()
        
    return report

def reset_link_capacidade_table():
    """
    APAGA e RECRIA a tabela links_capacidade.
    """
    import database
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DROP TABLE IF EXISTS links_capacidade")
        conn.commit()
        database.init_db()
        return {"success": True, "message": "Tabela resetada com sucesso (Schema Novo)."}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()

def force_expire_alarms():
    """
    Força expiração de alarmes (Viagem no Tempo).
    """
    import database
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE elementos SET esta_afetado = 0, afetado_ate = ? WHERE esta_afetado = 1", (yesterday,))
        conn.commit()
        return {"success": True, "message": "Todos os alarmes foram expirados."}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()
        
        
def audit_longa_distancia():
    """
    NOVA FUNÇÃO: Auditoria específica para o campo 'longa_distancia'.
    Compara o que a aplicação vê vs o que está no banco cru.
    """
    import database
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    report = []
    report.append("--- AUDITORIA DE LONGA DISTÂNCIA (LD) ---")
    
    try:
        # 1. VERIFICAÇÃO VIA APLICAÇÃO (O que o site recebe)
        elements_app = database.get_all_diagram_elements()
        ld_app_count = 0
        examples_app = []
        
        for elem in elements_app:
            # Verifica se o campo existe e se é verdadeiro
            if 'longa_distancia' in elem and elem['longa_distancia']:
                ld_app_count += 1
                if len(examples_app) < 3:
                    examples_app.append(f"{elem['nome_elemento']} (Valor: {elem['longa_distancia']})")
        
        report.append(f"1. Visão da Aplicação (Python):")
        report.append(f"   - Total de elementos com LD Ativo: {ld_app_count}")
        if examples_app:
            report.append(f"   - Exemplos: {', '.join(examples_app)}")
        else:
            report.append(f"   - ⚠️ NENHUM elemento detectado como Longa Distância pela aplicação.")

        # 2. VERIFICAÇÃO VIA BANCO CRU (A verdade absoluta)
        cursor.execute("SELECT count(*) as total FROM elementos WHERE longa_distancia = 1")
        ld_db_count = cursor.fetchone()['total']
        
        report.append(f"2. Visão do Banco de Dados (SQL Cru):")
        report.append(f"   - Total de linhas com longa_distancia=1: {ld_db_count}")
        
        if ld_db_count > 0:
            cursor.execute("SELECT nome_elemento FROM elementos WHERE longa_distancia = 1 LIMIT 3")
            examples_db = [row['nome_elemento'] for row in cursor.fetchall()]
            report.append(f"   - Exemplos no Banco: {', '.join(examples_db)}")
        
        # 3. VEREDITO
        report.append("--- CONCLUSÃO ---")
        if ld_app_count == ld_db_count and ld_app_count > 0:
            report.append("✅ SUCESSO: O Python está lendo corretamente o Banco.")
            report.append("   -> O problema está no Cache do Navegador ou no JavaScript (visualizar_enlace_diagrama.html).")
        elif ld_db_count > 0 and ld_app_count == 0:
            report.append("❌ ERRO CRÍTICO: O Banco tem dados, mas o Python não está lendo.")
            report.append("   -> O arquivo database.py provavelmente não foi atualizado ou reiniciado corretamente.")
        elif ld_db_count == 0:
            report.append("⚠️ ALERTA: O Banco de Dados diz que não há ninguém com Longa Distância=1.")
            
    except Exception as e:
        report.append(f"ERRO DURANTE AUDITORIA: {str(e)}")
    finally:
        conn.close()
        
    return report

def audit_stock_orphans():
    """
    Gera o relatório para o Item 8 do Debug.
    Mostra Candidatos (Perigo) e Itens já em Estoque (Seguro).
    """
    import database
    
    report = []
    
    # 1. Candidatos a Órfãos (Ainda aparecem no Databook erradamente)
    candidatos = database.get_orphan_candidates()
    
    report.append("--- CANDIDATOS A ESTOQUE (Flutuando no Databook) ---")
    if candidatos:
        report.append(f"⚠️ Encontrados {len(candidatos)} elementos isolados.")
        for c in candidatos:
            # Formato especial que o HTML vai ler para criar o botão
            # Usaremos um prefixo "ACTION:" para o HTML saber que é um botão
            report.append(f"ACTION_MOVE|{c['id']}|{c['nome_elemento']}")
    else:
        report.append("✅ Nenhum elemento flutuante detectado.")
        
    report.append("")
    
    # 2. Já em Estoque (Seguros)
    estoque = database.get_stock_items()
    report.append(f"--- JÁ EM ESTOQUE/SOBRAS ({len(estoque)}) ---")
    if estoque:
        for item in estoque:
            report.append(f"📦 {item['nome_elemento']} (Desde: {item['data_movimentacao']})")
            # Opcional: Botão para restaurar
            # report.append(f"ACTION_RESTORE|{item['id']}|Restaurar {item['nome_elemento']}")
    else:
        report.append("O estoque está vazio.")
        
    return report      


def audit_hierarchy():
    """
    Gera o relatório para o Item 9 do Debug.
    Lista elementos que estão em anéis de Longa Distância mas com flag LD=0.
    """
    import database
    
    report = []
    
    # Busca inconsistências
    inconsistencias = database.audit_hierarchy_inconsistencies()
    
    report.append("--- AUDITORIA DE HIERARQUIA (Regional vs Longa Distância) ---")
    
    if inconsistencias:
        report.append(f"⚠️ ALERTA: Encontrados {len(inconsistencias)} elementos com classificação incorreta.")
        report.append("(Eles estão em Anéis de Longa Distância, mas marcados como Regional)")
        
        for item in inconsistencias:
            # Formato especial para o HTML criar o botão de correção
            # Sintaxe: ACTION_FIX_HIERARCHY | ID | NOME | ANEL
            report.append(f"ACTION_FIX_HIERARCHY|{item['id']}|{item['nome_elemento']}|{item['nome_anel']}")
    else:
        report.append("✅ Tudo certo! Nenhum conflito de hierarquia encontrado.")
        
    return report

def diagnose_item_10_loader():
    """
    Item 10.1: Diagnóstico Focado em WDM_LD.
    """
    import database
    import sqlite3
    
    report = []
    report.append("--- DIAGNÓSTICO DO BUILDER (ITEM 10) ---")
    
    try:
        conn = sqlite3.connect(database.DATABASE_NAME)
        cursor = conn.cursor()
        
        # 1. Busca ESPECÍFICA por WDM_LD
        cursor.execute("SELECT id, nome_anel FROM aneis WHERE nome_anel LIKE '%WDM_LD%' ORDER BY nome_anel LIMIT 50")
        ld_rings = cursor.fetchall()
        
        if ld_rings:
            report.append(f"✅ SUCESSO: Encontrados {len(ld_rings)} anéis de Longa Distância (WDM_LD).")
            report.append("Exemplos encontrados:")
            for anel in ld_rings[:10]: # Mostra os 10 primeiros
                report.append(f"   - [ID: {anel[0]}] {anel[1]}")
            if len(ld_rings) > 10:
                report.append(f"   ... e mais {len(ld_rings)-10} anéis.")
        else:
            report.append("❌ ALERTA CRÍTICO: Nenhum anel com 'WDM_LD' no nome foi encontrado no banco.")
            
        conn.close()
        
    except Exception as e:
        report.append(f"❌ Erro ao acessar banco: {str(e)}")
        
    return report


def audit_accents():
    import database
    report = []
    
    bad_rings = database.audit_accented_names()
    
    report.append("--- AUDITORIA DE NOMES E ACENTOS (SANITIZAÇÃO) ---")
    
    if bad_rings:
        report.append(f"⚠️ Encontrados {len(bad_rings)} anéis com caracteres especiais.")
        for item in bad_rings:
            # Formato: ACTION_FIX_ACCENT | ID | NOME_VELHO | NOME_NOVO
            report.append(f"ACTION_FIX_ACCENT|{item['id']}|{item['original']}|{item['sugestao']}")
    else:
        report.append("✅ Tudo limpo! Nenhum anel com acentuação encontrado.")
        
    return report 