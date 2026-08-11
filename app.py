import streamlit as st
import sqlite3
import pandas as pd
import random
import os
import json
import re
from pathlib import Path
from datetime import datetime
from google import genai

# ==========================================
# CONFIGURAÇÃO DE CAMINHOS (PREPARADO PARA NUVEM)
# ==========================================
PASTA_PROJETO = Path("dados_sistema")
PASTA_PROJETO.mkdir(exist_ok=True)
PASTA_FOLHAS = PASTA_PROJETO / "folhas"
PASTA_FOLHAS.mkdir(exist_ok=True)
DB_FILE = PASTA_PROJETO / "reunioes.db"

st.set_page_config(page_title="Gestão de Reuniões", layout="centered", initial_sidebar_state="collapsed")

# ==========================================
# CSS: CORES FIXAS E BLINDADAS CONTRA O MODO ESCURO
# ==========================================
st.markdown('''
<style>
    /* Força o fundo geral padronizado */
    .stApp { 
        background: linear-gradient(135deg, #cbd5e1 0%, #f1f5f9 100%) !important; 
    }
    #MainMenu, header, footer {visibility: hidden;}

    h1 { color: #0f172a !important; text-align: center; font-weight: 800; margin-bottom: 25px; margin-top: -30px; font-size: 1.8rem;}
    h3 { color: #1e293b !important; font-size: 1.4rem; font-weight: 700; margin-bottom: 15px;}
    h4 { color: #334155 !important; font-size: 1.15rem; font-weight: 700; margin-bottom: 15px; margin-top: 10px;}
    
    /* Caixa de Login Blindada */
    .login-box {
        background: #ffffff !important;
        padding: 30px;
        border-radius: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
        margin-top: 20px;
        border: 1px solid #cbd5e1;
    }

    /* Corrige as caixas de texto para nunca ficarem escuras de forma errada */
    .stTextInput input {
        background-color: #f8fafc !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 12px !important;
    }

    /* Labels dos inputs visíveis */
    .stTextInput label {
        color: #334155 !important;
        font-weight: 600;
    }

    /* Cards do Menu SPA */
    div.stButton > button[kind="primary"] {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 18px;
        padding: 20px 10px;
        box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.05);
        height: 120px;
        color: #334155 !important;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        width: 100%;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.1);
        color: #3b82f6 !important;
        border-color: #3b82f6 !important;
    }
    
    /* Container Principal */
    .card-container {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        margin-top: 10px;
        border: 1px solid #e2e8f0;
    }
    
    /* Design do Engajamento */
    .eng-card {
        background: #ffffff !important;
        border-radius: 16px;
        padding: 20px;
        margin-top: 15px;
        margin-bottom: 10px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }
    .eng-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .eng-name { font-weight: 800; color: #1e293b !important; font-size: 1.15rem; }
    .eng-pct { font-weight: 800; color: #4338ca !important; font-size: 1.15rem; }
    
    .eng-bar-bg { background: #e2e8f0; border-radius: 10px; height: 10px; width: 100%; overflow: hidden; margin-bottom: 15px;}
    .eng-bar-fill { background: #4338ca; height: 100%; border-radius: 10px; transition: width 0.5s ease;}
    
    .eng-stats { display: flex; gap: 10px; font-size: 0.85rem; margin-bottom: 15px; }
    .badge-p { background: #dcfce7; color: #15803d; padding: 6px 12px; border-radius: 12px; font-weight: 700; }
    .badge-f { background: #fee2e2; color: #b91c1c; padding: 6px 12px; border-radius: 12px; font-weight: 700; }
    
    /* Sanfona Customizada */
    details.custom-dropdown {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        overflow: hidden;
    }
    details.custom-dropdown summary {
        padding: 12px 15px;
        font-size: 0.95rem;
        color: #475569 !important;
        cursor: pointer;
        font-weight: 600;
        list-style: none;
        display: flex;
        align-items: center;
        transition: background-color 0.2s;
    }
    details.custom-dropdown summary:hover { background-color: #f1f5f9; }
    details.custom-dropdown summary::-webkit-details-marker { display: none; }
    details.custom-dropdown summary::before {
        content: "›"; font-size: 1.2rem; margin-right: 10px; transition: transform 0.2s;
    }
    details.custom-dropdown[open] summary::before { transform: rotate(90deg); }
    
    .dropdown-content { padding: 15px; border-top: 1px solid #e2e8f0; background-color: #ffffff !important; }
    .hist-line { font-size: 0.9rem; margin-bottom: 8px; color: #334155 !important; }
    
</style>
''', unsafe_allow_html=True)

# Banco de Dados
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS participantes (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE, nome TEXT, documento TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS reunioes (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, motivo TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS presencas (id INTEGER PRIMARY KEY AUTOINCREMENT, reuniao_id INTEGER, participante_id INTEGER, status TEXT)")
    conn.commit()
    conn.close()

init_db()

# ==========================================
# SISTEMA DE LOGIN (SEGURANÇA)
# ==========================================
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #0f172a; margin-bottom: 20px;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
    
    with st.form("form_login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)
        
        if submit:
            # Puxa dos segredos do Streamlit se houver, senão usa padrão
            try:
                u_cad = st.secrets["USER_LOGIN"]
                s_cad = st.secrets["USER_PASS"]
            except Exception:
                u_cad = "admin"
                s_cad = "admin123"
                
            if usuario == u_cad and senha == s_cad:
                st.session_state["logado"] = True
                st.rerun()
            else:
                st.error("Credenciais incorretas. Tente novamente.")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# Variáveis de Navegação
if "pagina_ativa" not in st.session_state:
    st.session_state["pagina_ativa"] = "menu"
if "edit_id" not in st.session_state:
    st.session_state["edit_id"] = None

# ==========================================
# MODAL PARA EDITAR REUNIÕES
# ==========================================
@st.dialog("✏️ Editar Reunião")
def modal_editar_reuniao(reuniao_id):
    conn = sqlite3.connect(DB_FILE)
    r = pd.read_sql(f"SELECT data, motivo FROM reunioes WHERE id={reuniao_id}", conn).iloc[0]
    
    nova_data = st.text_input("Data da Reunião", value=r['data'])
    novo_motivo = st.text_input("Motivo da Reunião", value=r['motivo'])
    
    st.markdown("#### Lista de Presença")
    participantes = pd.read_sql("""
        SELECT p.id, p.nome, p.codigo, pr.status
        FROM participantes p
        LEFT JOIN presencas pr ON p.id = pr.participante_id AND pr.reuniao_id = ?
    """, conn, params=(reuniao_id,))
    
    presentes_atuais = participantes[participantes['status'] == 'Presente']['id'].tolist()
    opcoes_nomes = {row['id']: f"{row['nome']} (Cód: {row['codigo']})" for _, row in participantes.iterrows()}
    
    presentes_selecionados = st.multiselect(
        "Selecione as pessoas que estavam PRESENTES:",
        options=list(opcoes_nomes.keys()),
        format_func=lambda x: opcoes_nomes[x],
        default=presentes_atuais
    )
    
    if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
        c = conn.cursor()
        c.execute("UPDATE reunioes SET data=?, motivo=? WHERE id=?", (nova_data, novo_motivo, reuniao_id))
        
        for _, p_row in participantes.iterrows():
            p_id = p_row['id']
            novo_status = 'Presente' if p_id in presentes_selecionados else 'Ausente'
            
            check = c.execute("SELECT id FROM presencas WHERE reuniao_id=? AND participante_id=?", (reuniao_id, p_id)).fetchone()
            if check:
                c.execute("UPDATE presencas SET status=? WHERE id=?", (novo_status, check[0]))
            else:
                c.execute("INSERT INTO presencas (reuniao_id, participante_id, status) VALUES (?, ?, ?)", (reuniao_id, p_id, novo_status))
                
        conn.commit()
        conn.close()
        st.success("Reunião atualizada com sucesso!")
        st.rerun()

# ==========================================
# TELA 1: MENU PRINCIPAL
# ==========================================
if st.session_state["pagina_ativa"] == "menu":
    st.title("Gestão de Reuniões")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("👥\nMembros", type="primary", use_container_width=True):
            st.session_state["pagina_ativa"] = "participantes"
            st.rerun()
    with col2:
        if st.button("📊\nEngajamento", type="primary", use_container_width=True):
            st.session_state["pagina_ativa"] = "historico"
            st.rerun()
    with col3:
        if st.button("📸\nLançar", type="primary", use_container_width=True):
            st.session_state["pagina_ativa"] = "lancar"
            st.rerun()
            
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("Desconectar do Sistema", use_container_width=True):
        st.session_state["logado"] = False
        st.rerun()

# ==========================================
# TELA 2: CONTEÚDO DOS CARDS
# ==========================================
else:
    if st.button("⬅️ Voltar ao Menu", type="secondary"):
        st.session_state["pagina_ativa"] = "menu"
        st.session_state["edit_id"] = None
        st.rerun()

    # --- 1. PARTICIPANTES ---
    if st.session_state["pagina_ativa"] == "participantes":
        st.markdown("### 👥 Gestão de Membros")
        
        if st.session_state["edit_id"]:
            conn = sqlite3.connect(DB_FILE)
            p_atual = conn.execute("SELECT id, nome, documento, codigo FROM participantes WHERE id = ?", (st.session_state["edit_id"],)).fetchone()
            conn.close()
            if p_atual:
                st.info(f"Editando: {p_atual[1]}")
                with st.form("form_edicao"):
                    novo_nome = st.text_input("Nome", value=p_atual[1])
                    novo_doc = st.text_input("Documento", value=p_atual[2] if p_atual[2] else "")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Salvar"):
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("UPDATE participantes SET nome=?, documento=? WHERE id=?", (novo_nome, novo_doc, st.session_state["edit_id"]))
                        conn.commit()
                        conn.close()
                        st.session_state["edit_id"] = None
                        st.rerun()
                    if c2.form_submit_button("Cancelar"):
                        st.session_state["edit_id"] = None
                        st.rerun()
        else:
            st.markdown("#### ➕ Novo Membro")
            with st.form("form_cad", clear_on_submit=True):
                nome = st.text_input("Nome Completo")
                doc = st.text_input("Documento (CPF/RG)")
                if st.form_submit_button("Salvar Cadastro", use_container_width=True):
                    if nome:
                        cod = str(random.randint(100000, 999999))
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("INSERT INTO participantes (codigo, nome, documento) VALUES (?, ?, ?)", (cod, nome, doc))
                        conn.commit()
                        conn.close()
                        st.success("Cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.warning("O nome é obrigatório.")

        st.divider()
        st.markdown("#### Membros Cadastrados", unsafe_allow_html=True)
        conn = sqlite3.connect(DB_FILE)
        df_part = pd.read_sql("SELECT * FROM participantes ORDER BY nome", conn)
        conn.close()

        if not df_part.empty:
            for _, row in df_part.iterrows():
                with st.container(border=True):
                    col_texto, col_edit, col_del = st.columns([7, 1, 1])
                    with col_texto:
                        st.markdown(f"**{row['nome']}**")
                        st.caption(f"Cód: {row['codigo']} | Doc: {row['documento'] or 'N/A'}")
                    with col_edit:
                        if st.button("✏️", key=f"e_{row['id']}"):
                            st.session_state["edit_id"] = row['id']
                            st.rerun()
                    with col_del:
                        if st.button("❌", key=f"d_{row['id']}"):
                            conn = sqlite3.connect(DB_FILE)
                            conn.execute("DELETE FROM participantes WHERE id=?", (row['id'],))
                            conn.commit()
                            conn.close()
                            st.rerun()
        else:
            st.info("Nenhum participante.")

    # --- 2. HISTÓRICO E FREQUÊNCIA ---
    elif st.session_state["pagina_ativa"] == "historico":
        st.markdown("### 📈 Painel de Engajamento")
        
        conn = sqlite3.connect(DB_FILE)
        
        st.markdown("#### 📅 Histórico de Reuniões Realizadas")
        st.markdown("<p style='color: #64748b; font-size: 0.9rem; margin-top: -10px;'>Explore quem esteve presente ou edite caso haja erro na leitura.</p>", unsafe_allow_html=True)
        
        df_reunioes = pd.read_sql("SELECT id, data, motivo FROM reunioes ORDER BY id DESC", conn)
        
        if not df_reunioes.empty:
            with st.container(height=350, border=True):
                for _, reuniao in df_reunioes.iterrows():
                    col_detalhes, col_editar = st.columns([85, 15])
                    
                    with col_detalhes:
                        html_reuniao = f"""<details class="custom-dropdown" style="margin-bottom: 5px; margin-top: 5px;">
<summary>📌 {reuniao['data']} - {reuniao['motivo']}</summary>
<div class="dropdown-content">"""
                        
                        df_presencas = pd.read_sql(f"""
                            SELECT p.nome, pr.status 
                            FROM presencas pr 
                            JOIN participantes p ON p.id = pr.participante_id 
                            WHERE pr.reuniao_id = {reuniao['id']}
                            ORDER BY pr.status DESC, p.nome ASC
                        """, conn)
                        
                        if not df_presencas.empty:
                            for _, p in df_presencas.iterrows():
                                if p['status'] == "Presente":
                                    html_reuniao += f"<div class='hist-line'>✅ <b>{p['nome']}</b></div>"
                                else:
                                    html_reuniao += f"<div class='hist-line' style='color:#94a3b8;'>❌ <span style='text-decoration:line-through;'>{p['nome']}</span></div>"
                        else:
                            html_reuniao += "<div class='hist-line'>Sem registros.</div>"
                            
                        html_reuniao += "</div></details>"
                        st.markdown(html_reuniao, unsafe_allow_html=True)
                        
                    with col_editar:
                        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                        if st.button("✏️", key=f"edit_r_{reuniao['id']}", help="Editar reunião"):
                            modal_editar_reuniao(reuniao['id'])
        else:
            st.info("Nenhuma reunião registrada ainda.")

        st.divider()

        st.markdown("#### Frequência por Participante")
        busca = st.text_input("🔍 Buscar participante...", placeholder="Digite o nome e aperte Enter para filtrar")
        
        df_freq = pd.read_sql('''
            SELECT 
                p.id, p.nome, p.codigo,
                COUNT(pr.id) as total_reunioes,
                SUM(CASE WHEN pr.status = 'Presente' THEN 1 ELSE 0 END) as presencas,
                SUM(CASE WHEN pr.status = 'Ausente' THEN 1 ELSE 0 END) as faltas
            FROM participantes p
            LEFT JOIN presencas pr ON p.id = pr.participante_id
            GROUP BY p.id
            ORDER BY presencas DESC
        ''', conn)
        
        if busca:
            df_freq = df_freq[df_freq['nome'].str.contains(busca, case=False, na=False)]

        total_reunioes_banco = conn.execute("SELECT COUNT(id) FROM reunioes").fetchone()[0]

        if not df_freq.empty and total_reunioes_banco > 0:
            for _, row in df_freq.iterrows():
                pres = row['presencas'] or 0
                faltas = row['faltas'] or 0
                total = pres + faltas
                pct = int((pres / total) * 100) if total > 0 else 0
                
                historico_html = ""
                detalhes = pd.read_sql(f"""
                    SELECT r.data, r.motivo, pr.status 
                    FROM presencas pr
                    JOIN reunioes r ON pr.reuniao_id = r.id
                    WHERE pr.participante_id = {row['id']}
                    ORDER BY r.id DESC
                """, conn)
                
                if not detalhes.empty:
                    for _, det in detalhes.iterrows():
                        if det['status'] == "Presente":
                            historico_html += f"<div class='hist-line'>🔹 <b>{det['data']}</b> - {det['motivo']} • <span style='color: #15803d; font-weight: 700;'>Presença</span></div>"
                        else:
                            historico_html += f"<div class='hist-line'>🔸 <b>{det['data']}</b> - {det['motivo']} • <span style='color: #b91c1c; font-weight: 700;'>Falta</span></div>"
                else:
                    historico_html = "<div class='hist-line'>Sem histórico para exibir.</div>"

                card_html = f"""<div class="eng-card">
<div class="eng-header">
<span class="eng-name">👤 {row['nome']} <span style="font-size: 0.85em; color: #94a3b8; font-weight: 500;">(Cód: {row['codigo']})</span></span>
<span class="eng-pct">{pct}%</span>
</div>
<div class="eng-bar-bg"><div class="eng-bar-fill" style="width: {pct}%;"></div></div>
<div class="eng-stats">
<span class="badge-p">{pres} Presenças</span>
<span class="badge-f">{faltas} Faltas</span>
</div>
<details class="custom-dropdown">
<summary>Ver lista de presenças de {row['nome']}</summary>
<div class="dropdown-content">
{historico_html}
</div>
</details>
</div>"""
                st.markdown(card_html, unsafe_allow_html=True)
                
        elif total_reunioes_banco == 0:
            st.info("Lance uma reunião primeiro para gerar as estatísticas.")
        else:
            st.warning(f"Nenhum participante encontrado com o nome '{busca}'.")
            
        conn.close()

    # --- 3. LANÇAR REUNIÃO ---
    elif st.session_state["pagina_ativa"] == "lancar":
        st.markdown("### 📸 Leitura Inteligente")
        st.write("Fotografe a folha. A IA fará o resto.")
        
        conn = sqlite3.connect(DB_FILE)
        participantes_IA = conn.execute("SELECT id, codigo, nome, documento FROM participantes").fetchall()
        conn.close()

        if not participantes_IA:
            st.warning("Cadastre participantes primeiro.")
        else:
            foto_arquivo = st.camera_input(" ")
            
            if foto_arquivo is not None:
                st.write("") 
                if st.button("🚀 Processar Folha", type="primary", use_container_width=True):
                    with st.spinner("Analisando assinaturas (Gemini 3.1)..."):
                        try:
                            img_path = PASTA_FOLHAS / "temp_folha.jpg"
                            with open(img_path, "wb") as f:
                                f.write(foto_arquivo.getbuffer())
                                
                            api_key = os.environ.get("GEMINI_API_KEY")
                            try:
                                if not api_key:
                                    api_key = st.secrets["GEMINI_API_KEY"]
                            except Exception:
                                pass
                                
                            if not api_key:
                                api_key = "COLE_SUA_CHAVE_AQUI"
                                
                            if api_key == "COLE_SUA_CHAVE_AQUI":
                                st.error("Software sem chave da API do Gemini configurada nos Secrets!")
                                st.stop()
                                
                            client = genai.Client(api_key=api_key)
                            lista_ref = "\n".join([f"ID:{p[0]} | Cód: {p[1]} | Doc: {p[3]}" for p in participantes_IA])
                            
                            prompt = f"""
                            You are an auditor. Analyze this handwritten attendance sheet.
                            Reference list: {lista_ref}
                            Look for the Code (Cód) or Document (Doc) on the sheet.
                            Extract the date (DD/MM/AAAA) and reason/topic (motivo).
                            Return JSON: {{"data": "DD/MM/AAAA", "motivo": "theme", "identificados": ["code_or_doc"]}}
                            """
                            
                            myfile = client.files.upload(file=str(img_path))
                            response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=[myfile, prompt])
                            client.files.delete(name=myfile.name)
                            
                            match_json = re.search(r"\{.*\}", response.text, re.DOTALL)
                            if match_json:
                                dados = json.loads(match_json.group(0))
                                data_lida = dados.get("data") or datetime.today().strftime('%d/%m/%Y')
                                motivo_lido = dados.get("motivo", "Reunião Geral")
                                identificados = dados.get("identificados", [])
                                
                                conn = sqlite3.connect(DB_FILE)
                                cursor = conn.cursor()
                                cursor.execute("CREATE TABLE IF NOT EXISTS reunioes (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, motivo TEXT)")
                                cursor.execute("CREATE TABLE IF NOT EXISTS presencas (id INTEGER PRIMARY KEY AUTOINCREMENT, reuniao_id INTEGER, participante_id INTEGER, status TEXT)")
                                cursor.execute("INSERT INTO reunioes (data, motivo) VALUES (?, ?)", (data_lida, motivo_lido))
                                reuniao_id = cursor.lastrowid
                                
                                for p_id, p_cod, p_nome, p_doc in participantes_IA:
                                    foi_encontrado = (p_cod in identificados) or (p_doc and p_doc in identificados)
                                    status = "Presente" if foi_encontrado else "Ausente"
                                    cursor.execute("INSERT INTO presencas (reuniao_id, participante_id, status) VALUES (?, ?, ?)", (reuniao_id, p_id, status))
                                    
                                conn.commit()
                                conn.close()
                                
                                st.success(f"Salvo! Data: {data_lida} - {motivo_lido}")
                            else:
                                st.error("Erro na leitura da IA.")
                        except Exception as e:
                            st.error(f"Erro: {e}")
