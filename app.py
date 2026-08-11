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
# CONFIGURAÇÃO DE CAMINHOS
# ==========================================
PASTA_PROJETO = Path("dados_sistema")
PASTA_PROJETO.mkdir(exist_ok=True)
PASTA_FOLHAS = PASTA_PROJETO / "folhas"
PASTA_FOLHAS.mkdir(exist_ok=True)
DB_FILE = PASTA_PROJETO / "reunioes.db"

st.set_page_config(page_title="Gestão de Reuniões", layout="centered", initial_sidebar_state="collapsed")

# FORÇA O MODO CLARO PARA EVITAR BUGS DE COR NO CELULAR
st.markdown("""
    <meta name="color-scheme" content="light">
    <style>
        :root { color-scheme: light !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CSS: ESTILO PREMIUM E BLINDADO
# ==========================================
st.markdown('''
<style>
    .stApp { background: linear-gradient(135deg, #cbd5e1 0%, #f1f5f9 100%) !important; }
    #MainMenu, header, footer {visibility: hidden;}

    h1 { color: #0f172a !important; text-align: center; font-weight: 800; margin-bottom: 25px; margin-top: -30px; font-size: 1.8rem;}
    h3 { color: #1e293b !important; font-size: 1.4rem; font-weight: 700; margin-bottom: 15px;}
    h4 { color: #334155 !important; font-size: 1.15rem; font-weight: 700; margin-bottom: 15px; margin-top: 10px;}
    
    .stTextInput input { background-color: #ffffff !important; color: #0f172a !important; border: 1px solid #cbd5e1 !important; border-radius: 12px !important; }
    .stTextInput label { color: #334155 !important; font-weight: 600; }

    div.stButton > button[kind="primary"] {
        background: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 18px;
        padding: 20px 10px; box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.05);
        height: 120px; color: #334155 !important; width: 100%;
    }
    
    .card-container { background-color: #ffffff !important; padding: 25px; border-radius: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); }
    
    .eng-card { background: #ffffff !important; border-radius: 16px; padding: 20px; margin-top: 15px; border: 1px solid #e2e8f0; }
    .eng-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .eng-name { font-weight: 800; color: #1e293b !important; font-size: 1.15rem; }
    .eng-pct { font-weight: 800; color: #4338ca !important; font-size: 1.15rem; }
    .eng-bar-bg { background: #e2e8f0; border-radius: 10px; height: 10px; width: 100%; overflow: hidden; margin-bottom: 15px;}
    .eng-bar-fill { background: #4338ca; height: 100%; border-radius: 10px; }
    .badge-p { background: #dcfce7; color: #15803d; padding: 6px 12px; border-radius: 12px; font-weight: 700; }
    .badge-f { background: #fee2e2; color: #b91c1c; padding: 6px 12px; border-radius: 12px; font-weight: 700; }
    
    details.custom-dropdown { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
    details.custom-dropdown summary { padding: 12px 15px; color: #475569 !important; cursor: pointer; font-weight: 600; list-style: none; }
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
# SISTEMA DE LOGIN
# ==========================================
if "logado" not in st.session_state: st.session_state["logado"] = False

if not st.session_state["logado"]:
    with st.container():
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #0f172a;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                if usuario == st.secrets.get("USER_LOGIN", "admin") and senha == st.secrets.get("USER_PASS", "admin123"):
                    st.session_state["logado"] = True
                    st.rerun()
                else: st.error("Credenciais incorretas.")
    st.stop()

# ==========================================
# TELA 1 e 2
# ==========================================
if "pagina_ativa" not in st.session_state: st.session_state["pagina_ativa"] = "menu"
if "edit_id" not in st.session_state: st.session_state["edit_id"] = None

@st.dialog("✏️ Editar Reunião")
def modal_editar_reuniao(reuniao_id):
    conn = sqlite3.connect(DB_FILE)
    r = pd.read_sql(f"SELECT data, motivo FROM reunioes WHERE id={reuniao_id}", conn).iloc[0]
    nova_data = st.text_input("Data", value=r['data'])
    novo_motivo = st.text_input("Motivo", value=r['motivo'])
    participantes = pd.read_sql("SELECT p.id, p.nome, p.codigo, pr.status FROM participantes p LEFT JOIN presencas pr ON p.id = pr.participante_id AND pr.reuniao_id = ?", conn, params=(reuniao_id,))
    presentes_atuais = participantes[participantes['status'] == 'Presente']['id'].tolist()
    presentes_selecionados = st.multiselect("Presentes:", options=participantes['id'].tolist(), format_func=lambda x: f"{participantes.loc[participantes['id']==x, 'nome'].values[0]} ({participantes.loc[participantes['id']==x, 'codigo'].values[0]})", default=presentes_atuais)
    if st.button("💾 Salvar"):
        c = conn.cursor()
        c.execute("UPDATE reunioes SET data=?, motivo=? WHERE id=?", (nova_data, novo_motivo, reuniao_id))
        for _, p in participantes.iterrows():
            stt = 'Presente' if p['id'] in presentes_selecionados else 'Ausente'
            c.execute("INSERT OR REPLACE INTO presencas (reuniao_id, participante_id, status) VALUES (?, ?, ?)", (reuniao_id, p['id'], stt))
        conn.commit(); conn.close(); st.rerun()

if st.session_state["pagina_ativa"] == "menu":
    st.title("Gestão de Reuniões")
    c1, c2, c3 = st.columns(3)
    if c1.button("👥 Membros", type="primary", use_container_width=True): st.session_state["pagina_ativa"] = "participantes"; st.rerun()
    if c2.button("📊 Engajamento", type="primary", use_container_width=True): st.session_state["pagina_ativa"] = "historico"; st.rerun()
    if c3.button("📸 Lançar", type="primary", use_container_width=True): st.session_state["pagina_ativa"] = "lancar"; st.rerun()
else:
    if st.button("⬅️ Voltar"): st.session_state["pagina_ativa"] = "menu"; st.rerun()
    
    if st.session_state["pagina_ativa"] == "participantes":
        st.markdown("### 👥 Membros")
        with st.form("form_cad", clear_on_submit=True):
            nome = st.text_input("Nome"); doc = st.text_input("Documento")
            if st.form_submit_button("Cadastrar", use_container_width=True):
                conn = sqlite3.connect(DB_FILE)
                conn.execute("INSERT INTO participantes (codigo, nome, documento) VALUES (?, ?, ?)", (str(random.randint(100000, 999999)), nome, doc))
                conn.commit(); conn.close(); st.rerun()
        conn = sqlite3.connect(DB_FILE)
        df_p = pd.read_sql("SELECT * FROM participantes", conn)
        for _, row in df_p.iterrows():
            with st.container(border=True): st.markdown(f"**{row['nome']}** - Cód: {row['codigo']}")
        conn.close()

    elif st.session_state["pagina_ativa"] == "historico":
        conn = sqlite3.connect(DB_FILE)
        st.markdown("#### 📅 Histórico")
        with st.container(height=300, border=True):
            for _, r in pd.read_sql("SELECT * FROM reunioes ORDER BY id DESC", conn).iterrows():
                st.markdown(f"📌 {r['data']} - {r['motivo']}")
                if st.button("✏️", key=f"r_{r['id']}"): modal_editar_reuniao(r['id'])
        
        st.markdown("#### Frequência")
        busca = st.text_input("🔍 Buscar participante...")
        df_f = pd.read_sql("SELECT p.id, p.nome, p.codigo, SUM(CASE WHEN pr.status='Presente' THEN 1 ELSE 0 END) as presencas, SUM(CASE WHEN pr.status='Ausente' THEN 1 ELSE 0 END) as faltas FROM participantes p LEFT JOIN presencas pr ON p.id=pr.participante_id GROUP BY p.id", conn)
        if busca: df_f = df_f[df_f['nome'].str.contains(busca, case=False)]
        for _, row in df_f.iterrows():
            st.markdown(f"<div class='eng-card'><b>{row['nome']}</b> (Cód: {row['codigo']})<br>✅ {row['presencas']} | ❌ {row['faltas']}</div>", unsafe_allow_html=True)
        conn.close()

    elif st.session_state["pagina_ativa"] == "lancar":
        foto = st.camera_input(" ")
        if foto and st.button("🚀 Processar", type="primary", use_container_width=True):
            st.info("Processando...")
