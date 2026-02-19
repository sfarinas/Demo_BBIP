import sqlite3

DATABASE_NAME = 'rede.db'  # Confirme se o nome do seu banco é esse mesmo

def sync_router_sites():
    print("--- INICIANDO SINCRONIZAÇÃO DE ROTEADORES (HUD MATRIX) ---")
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # 1. Garante que a coluna site_id existe na tabela de roteadores
        try:
            cursor.execute("ALTER TABLE equipamentos_dados ADD COLUMN site_id TEXT")
            print("✅ Coluna 'site_id' criada na tabela equipamentos_dados.")
        except sqlite3.OperationalError:
            print("ℹ️ A coluna 'site_id' já existe (Ok).")

        # 2. O PULO DO GATO: Atualiza o site_id do roteador procurando pelo nome dele na tabela de elementos
        # Ex: Se o roteador chama 'BBB-BBB01-HW01-1', ele pega o site_id do elemento com esse nome.
        query_update = """
        UPDATE equipamentos_dados
        SET site_id = (
            SELECT site_id 
            FROM elementos 
            WHERE elementos.nome_elemento = equipamentos_dados.hostname
               OR elementos.nome_elemento_curto = equipamentos_dados.hostname
            LIMIT 1
        )
        WHERE site_id IS NULL OR site_id = '';
        """
        
        cursor.execute(query_update)
        linhas = cursor.rowcount
        conn.commit()
        
        print(f"🚀 SUCESSO! {linhas} roteadores foram vinculados aos seus Sites.")
        
        if linhas == 0:
            print("⚠️ Nenhum roteador atualizado. Verifique se os 'hostnames' dos roteadores batem com os 'nomes' dos elementos.")

    except Exception as e:
        print(f"❌ Erro ao sincronizar: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    sync_router_sites()