# --- Biblioteca padrão do Python ---
import os
import re
import json
import random
from pathlib import Path
from datetime import datetime

# --- Bibliotecas externas ---
import streamlit as st
import pandas as pd
import gspread
from google import genai
from google.oauth2.service_account import Credentials

# ==========================================
# CONFIGURAÇÃO DE CAMINHOS (só usado pra imagem temporária)
# ==========================================
PASTA_PROJETO = Path("dados_sistema")
PASTA_PROJETO.mkdir(exist_ok=True)
PASTA_FOLHAS = PASTA_PROJETO / "folhas"
PASTA_FOLHAS.mkdir(exist_ok=True)

st.set_page_config(page_title="Gestão de Reuniões", layout="centered", initial_sidebar_state="collapsed")

# BLINDAGEM DE CORES - Força o modo claro no celular/Brave.
# Importante: a defesa principal contra o tema escuro é o arquivo
# .streamlit/config.toml (base = "light"), que trava o tema no motor
# do próprio Streamlit. Este bloco aqui é uma segunda camada, cobrindo
# html/body (que alguns navegadores pintam de escuro antes do CSS
# customizado carregar, mesmo com config.toml certo).
st.markdown("""
    <meta name="color-scheme" content="light">
    <style>
        :root, html, body {
            color-scheme: light !important;
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CSS: ESTILO PREMIUM E BLINDADO (sem alterações)
# ==========================================
st.markdown('''
<style>
    .stApp { 
        background: linear-gradient(135deg, #cbd5e1 0%, #f1f5f9 100%) !important; 
    }
    #MainMenu, header, footer {visibility: hidden;}

    h1 { color: #0f172a !important; text-align: center; font-weight: 800; margin-bottom: 25px; margin-top: -30px; font-size: 1.8rem;}
    h3 { color: #1e293b !important; font-size: 1.4rem; font-weight: 700; margin-bottom: 15px;}
    h4 { color: #334155 !important; font-size: 1.15rem; font-weight: 700; margin-bottom: 15px; margin-top: 10px;}
    
    .stTextInput input {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 12px !important;
    }

    .stTextInput label {
        color: #334155 !important;
        font-weight: 600;
    }

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
    
    .card-container {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        margin-top: 10px;
        border: 1px solid #e2e8f0;
    }
    
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

# ==========================================
# CONEXÃO COM GOOGLE SHEETS
# ==========================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PART_HEADERS = ["id", "codigo", "nome", "documento"]
REUNIAO_HEADERS = ["id", "data", "motivo"]
PRESENCA_HEADERS = ["id", "reuniao_id", "participante_id", "status"]


@st.cache_resource
def conectar_planilha():
    """Abre a planilha configurada nos Secrets. Cacheada: só conecta 1x por sessão de servidor."""
    creds_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_url(st.secrets["SHEET_URL"])


def get_ws(nome_aba, headers):
    """Devolve a aba (worksheet) pelo nome, criando-a com os cabeçalhos
    passados caso ainda não exista. Assim o app nunca quebra por falta
    de uma aba, mesmo numa planilha nova."""
    sh = conectar_planilha()
    try:
        ws = sh.worksheet(nome_aba)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nome_aba, rows=2000, cols=len(headers))
        ws.append_row(headers)
    return ws


def carregar_tabela(nome_aba, headers):
    """Lê a aba inteira de uma vez (1 chamada de API) e devolve como DataFrame + a worksheet."""
    ws = get_ws(nome_aba, headers)
    registros = ws.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty:
        df = pd.DataFrame(columns=headers)
    else:
        for col in ["id", "reuniao_id", "participante_id"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df, ws


def proximo_id(df):
    """Como o Google Sheets não tem autoincremento como o SQLite tinha,
    calculamos o próximo ID manualmente: maior ID atual + 1."""
    if df.empty or df["id"].isna().all():
        return 1
    return int(df["id"].max()) + 1


def init_planilha():
    """Garante que as 3 abas existem assim que o app sobe, evitando que
    o primeiro clique do usuário esbarre numa aba inexistente."""
    get_ws("participantes", PART_HEADERS)
    get_ws("reunioes", REUNIAO_HEADERS)
    get_ws("presencas", PRESENCA_HEADERS)


init_planilha()

# ==========================================
# SISTEMA DE LOGIN (SEGURANÇA)
# ==========================================
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.markdown("<br><br>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("<h2 style='text-align: center; color: #0f172a; margin-bottom: 20px;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)

        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)

            if submit:
                # Sem fallback: se USER_LOGIN/USER_PASS não estiverem nos Secrets, o app
                # não deixa logar com uma senha padrão previsível.
                if "USER_LOGIN" not in st.secrets or "USER_PASS" not in st.secrets:
                    st.error("Login não configurado. Peça para configurar USER_LOGIN e USER_PASS nos Secrets do Streamlit.")
                    st.stop()

                u_cad = st.secrets["USER_LOGIN"]
                s_cad = st.secrets["USER_PASS"]

                if usuario == u_cad and senha == s_cad:
                    st.session_state["logado"] = True
                    st.rerun()
                else:
                    st.error("Credenciais incorretas. Tente novamente.")

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
    """Deixa editar a data/motivo de uma reunião e recalcular quem estava
    presente. Carrega as 3 tabelas de uma vez (em vez de uma consulta por
    pessoa) para economizar chamadas de API do Sheets."""
    df_reunioes, ws_reunioes = carregar_tabela("reunioes", REUNIAO_HEADERS)
    df_part, _ = carregar_tabela("participantes", PART_HEADERS)
    df_pres, ws_pres = carregar_tabela("presencas", PRESENCA_HEADERS)

    r = df_reunioes[df_reunioes["id"] == reuniao_id].iloc[0]

    nova_data = st.text_input("Data da Reunião", value=r["data"])
    novo_motivo = st.text_input("Motivo da Reunião", value=r["motivo"])

    st.markdown("#### Lista de Presença")
    pres_desta_reuniao = df_pres[df_pres["reuniao_id"] == reuniao_id]
    presentes_atuais = pres_desta_reuniao[pres_desta_reuniao["status"] == "Presente"]["participante_id"].tolist()
    opcoes_nomes = {int(row["id"]): f"{row['nome']} (Cód: {row['codigo']})" for _, row in df_part.iterrows()}

    presentes_selecionados = st.multiselect(
        "Selecione as pessoas que estavam PRESENTES:",
        options=list(opcoes_nomes.keys()),
        format_func=lambda x: opcoes_nomes[x],
        default=presentes_atuais,
    )

    if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
        linha_r = int(df_reunioes.index[df_reunioes["id"] == reuniao_id][0]) + 2
        ws_reunioes.update(f"B{linha_r}:C{linha_r}", [[nova_data, novo_motivo]])

        prox_id_pres = proximo_id(df_pres)
        for _, p_row in df_part.iterrows():
            p_id = int(p_row["id"])
            novo_status = "Presente" if p_id in presentes_selecionados else "Ausente"
            existente = df_pres[(df_pres["reuniao_id"] == reuniao_id) & (df_pres["participante_id"] == p_id)]

            if not existente.empty:
                linha_p = int(existente.index[0]) + 2
                ws_pres.update(f"D{linha_p}", [[novo_status]])
            else:
                ws_pres.append_row([prox_id_pres, reuniao_id, p_id, novo_status])
                prox_id_pres += 1

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

        df_part, ws_part = carregar_tabela("participantes", PART_HEADERS)

        if st.session_state["edit_id"]:
            p_atual_df = df_part[df_part["id"] == st.session_state["edit_id"]]
            if not p_atual_df.empty:
                p_atual = p_atual_df.iloc[0]
                st.info(f"Editando: {p_atual['nome']}")
                with st.form("form_edicao"):
                    novo_nome = st.text_input("Nome", value=p_atual["nome"])
                    novo_doc = st.text_input("Documento", value=p_atual["documento"] if p_atual["documento"] else "")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Salvar"):
                        linha = int(df_part.index[df_part["id"] == st.session_state["edit_id"]][0]) + 2
                        ws_part.update(f"C{linha}:D{linha}", [[novo_nome, novo_doc]])
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
                        novo_id = proximo_id(df_part)
                        cod = str(random.randint(100000, 999999))
                        ws_part.append_row([novo_id, cod, nome, doc])
                        st.success("Cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.warning("O nome é obrigatório.")

        st.divider()
        st.markdown("#### Membros Cadastrados", unsafe_allow_html=True)
        df_part, ws_part = carregar_tabela("participantes", PART_HEADERS)

        if not df_part.empty:
            for _, row in df_part.sort_values("nome").iterrows():
                with st.container(border=True):
                    col_texto, col_edit, col_del = st.columns([7, 1, 1])
                    with col_texto:
                        st.markdown(f"**{row['nome']}**")
                        st.caption(f"Cód: {row['codigo']} | Doc: {row['documento'] or 'N/A'}")
                    with col_edit:
                        if st.button("✏️", key=f"e_{row['id']}"):
                            st.session_state["edit_id"] = int(row["id"])
                            st.rerun()
                    with col_del:
                        if st.button("❌", key=f"d_{row['id']}"):
                            linha = int(df_part.index[df_part["id"] == row["id"]][0]) + 2
                            ws_part.delete_rows(linha)
                            st.rerun()
        else:
            st.info("Nenhum participante.")

    # --- 2. HISTÓRICO E FREQUÊNCIA ---
    elif st.session_state["pagina_ativa"] == "historico":
        st.markdown("### 📈 Painel de Engajamento")

        df_part, _ = carregar_tabela("participantes", PART_HEADERS)
        df_reunioes, _ = carregar_tabela("reunioes", REUNIAO_HEADERS)
        df_pres, _ = carregar_tabela("presencas", PRESENCA_HEADERS)

        st.markdown("#### 📅 Histórico de Reuniões Realizadas")
        st.markdown("<p style='color: #64748b; font-size: 0.9rem; margin-top: -10px;'>Explore quem esteve presente ou edite caso haja erro na leitura.</p>", unsafe_allow_html=True)

        df_reunioes_ordenado = df_reunioes.sort_values("id", ascending=False) if not df_reunioes.empty else df_reunioes

        if not df_reunioes_ordenado.empty:
            with st.container(height=350, border=True):
                for _, reuniao in df_reunioes_ordenado.iterrows():
                    col_detalhes, col_editar = st.columns([85, 15])

                    with col_detalhes:
                        html_reuniao = f"""<details class="custom-dropdown" style="margin-bottom: 5px; margin-top: 5px;">
<summary>📌 {reuniao['data']} - {reuniao['motivo']}</summary>
<div class="dropdown-content">"""

                        pres_desta = df_pres[df_pres["reuniao_id"] == reuniao["id"]].merge(
                            df_part[["id", "nome"]], left_on="participante_id", right_on="id", suffixes=("", "_p")
                        )
                        if not pres_desta.empty:
                            pres_desta = pres_desta.sort_values(["status", "nome"], ascending=[False, True])
                            for _, p in pres_desta.iterrows():
                                if p["status"] == "Presente":
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
                            modal_editar_reuniao(int(reuniao["id"]))
        else:
            st.info("Nenhuma reunião registrada ainda.")

        st.divider()

        st.markdown("#### Frequência por Participante")
        busca = st.text_input("🔍 Buscar participante...", placeholder="Digite o nome e aperte Enter para filtrar")

        if not df_pres.empty:
            resumo = df_pres.groupby("participante_id")["status"].value_counts().unstack(fill_value=0)
            resumo = resumo.rename(columns={"Presente": "presencas", "Ausente": "faltas"})
        else:
            resumo = pd.DataFrame(columns=["presencas", "faltas"])

        df_freq = df_part.merge(resumo, left_on="id", right_index=True, how="left")
        for col in ["presencas", "faltas"]:
            if col not in df_freq.columns:
                df_freq[col] = 0
        df_freq["presencas"] = df_freq["presencas"].fillna(0).astype(int)
        df_freq["faltas"] = df_freq["faltas"].fillna(0).astype(int)
        df_freq = df_freq.sort_values("presencas", ascending=False)

        if busca:
            df_freq = df_freq[df_freq["nome"].str.contains(busca, case=False, na=False)]

        total_reunioes_banco = len(df_reunioes)

        if not df_freq.empty and total_reunioes_banco > 0:
            for _, row in df_freq.iterrows():
                pres = int(row["presencas"])
                faltas = int(row["faltas"])
                total = pres + faltas
                pct = int((pres / total) * 100) if total > 0 else 0

                detalhes = df_pres[df_pres["participante_id"] == row["id"]].merge(
                    df_reunioes[["id", "data", "motivo"]], left_on="reuniao_id", right_on="id", suffixes=("", "_r")
                )

                historico_html = ""
                if not detalhes.empty:
                    detalhes = detalhes.sort_values("reuniao_id", ascending=False)
                    for _, det in detalhes.iterrows():
                        if det["status"] == "Presente":
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

    # --- 3. LANÇAR REUNIÃO ---
    elif st.session_state["pagina_ativa"] == "lancar":
        st.markdown("### 📸 Leitura Inteligente")
        st.write("Fotografe a folha. A IA fará o resto.")

        df_part, _ = carregar_tabela("participantes", PART_HEADERS)

        if df_part.empty:
            st.warning("Cadastre participantes primeiro.")
        else:
            foto_arquivo = st.camera_input(" ")

            if foto_arquivo is not None:
                st.write("")
                if st.button("🚀 Processar Folha", type="primary", use_container_width=True):
                    with st.spinner("Analisando assinaturas (Gemini 3.1)..."):
                        img_path = PASTA_FOLHAS / "temp_folha.jpg"
                        try:
                            with open(img_path, "wb") as f:
                                f.write(foto_arquivo.getbuffer())

                            api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
                            if not api_key:
                                st.error("Chave da API do Gemini não configurada nos Secrets!")
                                st.stop()

                            client = genai.Client(api_key=api_key)
                            lista_ref = "\n".join(
                                [f"ID:{p['id']} | Cód: {p['codigo']} | Doc: {p['documento']}" for _, p in df_part.iterrows()]
                            )

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

                                df_reunioes, ws_reunioes = carregar_tabela("reunioes", REUNIAO_HEADERS)
                                novo_reuniao_id = proximo_id(df_reunioes)
                                ws_reunioes.append_row([novo_reuniao_id, data_lida, motivo_lido])

                                df_pres, ws_pres = carregar_tabela("presencas", PRESENCA_HEADERS)
                                prox_id_pres = proximo_id(df_pres)
                                linhas_novas = []
                                for _, p in df_part.iterrows():
                                    foi_encontrado = (p["codigo"] in identificados) or (p["documento"] and p["documento"] in identificados)
                                    status = "Presente" if foi_encontrado else "Ausente"
                                    linhas_novas.append([prox_id_pres, novo_reuniao_id, int(p["id"]), status])
                                    prox_id_pres += 1
                                ws_pres.append_rows(linhas_novas)

                                st.success(f"Salvo! Data: {data_lida} - {motivo_lido}")
                            else:
                                st.error("Erro na leitura da IA.")
                        except Exception as e:
                            # Não exibimos o erro técnico completo pro usuário (pode vazar detalhes internos).
                            print(f"[ERRO lancar reuniao] {e}")
                            st.error("Não foi possível processar a folha. Tente novamente ou avise o responsável do sistema.")
                        finally:
                            if img_path.exists():
                                img_path.unlink()
