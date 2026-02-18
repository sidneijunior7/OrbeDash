import streamlit as st
import pandas as pd
import os, json, time
from openai import OpenAI
import pymysql
import include.users_database as udb
from dotenv import load_dotenv
load_dotenv()
# Dependência: tvdatafeed (usa websocket internamente)
from tvDatafeed import TvDatafeed, Interval
#st.write(st.session_state)
# ======================================================================
# CONFIGURAÇÃO INICIAL
# ======================================================================
PRESETS_FILE = "presets.json"
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

st.set_page_config(
    page_title='Raidan Data Collector + AI Agent (TradingView)',
    layout='wide',
    initial_sidebar_state='expanded',
)

# -------------------------------------------------------------------
# FUNÇÃO DE LOGOUT
# -------------------------------------------------------------------
def logout():
    st.session_state.logged_in = False
    st.session_state.expiration = 0
    st.session_state.email = ''

    from streamlit_cookies_controller import CookieController
    CookieController().set('logged_in', False)
    CookieController().set('user_email', '')
    CookieController().set('expiration', 0)

    with st.spinner("#### Encerrando Sessão ..."):
        time.sleep(2)

    st.rerun()
# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------
if 'resposta' not in st.session_state:
    st.session_state.resposta = None

# ======================================================================
# HELPERS: TradingView collector
# ======================================================================

# Observação: mapping de símbolos — ajuste conforme necessário.
# Entrada esperada pelo usuário (na UI): lista de símbolos separados por vírgula.
# Você pode passar símbolos do TradingView já no formato EXCHANGE:SYMBOL (ex: "BMF:WIN$N" ou "BMFBOVESPA:WIN1!").
# Se o usuário passar "WIN$N" o código tentará mapear automaticamente para "WIN1!" na BMFBOVESPA.
DEFAULT_TV_MAPPING = {
    "WIN$N": ("WIN1!", "BMFBOVESPA"),
    "WDO$N": ("WDO1!", "BMFBOVESPA"),
    "DI1$N": ("DI1!", "BMFBOVESPA"),
    # adicione outras traduções se quiser
}

def parse_user_symbol(sym: str):
    """
    Recebe 'WIN$N' ou 'BMFBOVESPA:WIN1!' ou 'EXCHANGE:SYMBOL'.
    Retorna (symbol, exchange).
    """
    s = sym.strip()
    if ":" in s:
        symbol, exchange = s.split(":", 1)
        return symbol.strip(), exchange.strip()
    # fallback para mapping
    if s in DEFAULT_TV_MAPPING:
        return DEFAULT_TV_MAPPING[s]
    # heurística: tratar pontos como exchange e parte após . como symbol (ex: "BMF.WIN1!")
    if "." in s:
        ex, sym = s.split(".", 1)
        return sym.strip(), ex.strip()
    # se tudo falhar, assume símbolo puro e BMFBOVESPA
    return s, "BMFBOVESPA"

def collect_tv_all(ativos_b3, ativos_fx, bars, tv_username=None, tv_password=None):
    """
    Coleta séries históricas de TradingView via tvDatafeed.
    Retorna DataFrame concatenado com colunas: symbol, exchange, datetime, open, high, low, close, volume
    - bars: número de barras a coletar (por símbolo)
    """
    # tvdatafeed aceita credenciais (opcional). Se None, tenta anonymous (pode falhar para alguns símbolos).
    if tv_username and tv_password:
        tv = TvDatafeed(tv_username, tv_password)
    else:
        tv = TvDatafeed()  # anonymous mode (pode funcionar para muitos símbolos)

    frames = []
    # helper para buscar lista de símbolos
    def fetch_list(symbol_list, label):
        for s in symbol_list:
            sym = s.strip()
            if not sym:
                continue
            symbol, exchange = parse_user_symbol(sym)
            try:
                # Usamos Interval.in_1_minute; ajuste se quiser outro intervalo
                # tv.get_hist(symbol, exchange, interval=Interval.in_1_minute, n_bars=bars)
                df = tv.get_hist(symbol, exchange, interval=Interval.in_1_minute, n_bars=bars)
                if df is None or df.empty:
                    st.warning(f"Nenhum dado para {symbol}:{exchange}")
                    continue
                # tvDatafeed retorna index datetime
                df = df.reset_index().rename(columns={"index":"datetime"})
                df["symbol"] = symbol
                df["exchange"] = exchange
                # normalizar colunas
                df = df[["symbol","exchange","datetime","open","high","low","close","volume"]]
                frames.append(df)
                time.sleep(0.2)  # throttle leve
            except Exception as e:
                st.error(f"Erro coletando {symbol}:{exchange} — {e}")
    fetch_list(ativos_b3, "B3")
    fetch_list(ativos_fx, "FX")
    if frames:
        df_all = pd.concat(frames, ignore_index=True)
        # garantir ordenação e formatação
        df_all = df_all.sort_values(["symbol","datetime"]).reset_index(drop=True)
        # transformar datetime para ISO UTC if tz-aware
        if not pd.api.types.is_datetime64_any_dtype(df_all["datetime"]):
            df_all["datetime"] = pd.to_datetime(df_all["datetime"])
        df_all["timestamp_utc"] = df_all["datetime"].dt.tz_localize(None).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return df_all
    return pd.DataFrame()

# ======================================================================
# UTILIDADES (mesmas do seu app)
# ======================================================================
def load_file_text(path: str) -> str:
    """Lê arquivo inteiro em texto."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def ask_agent_with_inline_csv(prompt: str, path: str, model: str) -> str:
    """Envia CSV inline via Responses API."""
    csv_text = load_file_text(path)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Aqui está o dataset em CSV:\n\n```csv\n{csv_text}\n```"}
        ]
    )
    return response.output_text

# def carregar_presets() -> dict:
#     if os.path.exists(PRESETS_FILE):
#         with open(PRESETS_FILE, "r", encoding="utf-8") as f:
#             return json.load(f)
#     return {}
#
# def salvar_preset(nome: str, dados: dict):
#     presets = carregar_presets()
#     presets[nome] = dados
#     with open(PRESETS_FILE, "w", encoding="utf-8") as f:
#         json.dump(presets, f, ensure_ascii=False, indent=4)
#
# def deletar_preset(nome: str):
#     presets = carregar_presets()
#     if nome in presets:
#         del presets[nome]
#         with open(PRESETS_FILE, "w", encoding="utf-8") as f:
#             json.dump(presets, f, ensure_ascii=False, indent=4)
#=======================================================================
#   NOVA INTERFACE DE PRESET
#=======================================================================
def listar_presets() -> dict:
    conn = udb.create_connection()
    if conn is None:
        return {}

    query = """
        SELECT name, config
        FROM presets
        WHERE user_id = %s
        ORDER BY name
    """

    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(query, (st.session_state.user_id,))
        rows = cursor.fetchall()

    conn.close()

    return {
        row["name"]: json.loads(row["config"])
        for row in rows
    }

    return {row["name"]: json.loads(row["config"]) for row in rows}
def salvar_preset(nome: str, dados: dict):
    conn = udb.create_connection()
    if conn is None:
        return False

    query = """
        INSERT INTO presets (user_id, name, config)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            config = VALUES(config),
            updated_at = CURRENT_TIMESTAMP
    """

    with conn.cursor() as cursor:
        cursor.execute(
            query,
            (
                st.session_state.user_id,
                nome,
                json.dumps(dados, ensure_ascii=False)
            )
        )
        conn.commit()

    conn.close()
    return True
def deletar_preset(nome: str):
    conn = udb.create_connection()
    if conn is None:
        return False

    query = """
        DELETE FROM presets
        WHERE user_id = %s AND name = %s
    """

    with conn.cursor() as cursor:
        cursor.execute(
            query,
            (st.session_state.user_id, nome)
        )
        conn.commit()

    conn.close()
    return True

# ======================================================================
# UI (muito parecido com o seu original)
# ======================================================================

if 'logged_in' in st.session_state and st.session_state.logged_in:
    conn = udb.create_connection()
    name = udb.get_user_info(conn, "user_name", "users", st.session_state.email)[0][0]

    st.sidebar.write(f"👋 Bem-vindo, {(name.split()[0]).capitalize()}")
    conn.close()
    if st.sidebar.button("Sair", icon=':material/logout:', type='primary'):
        logout()
    st.sidebar.write('---')

    if st.session_state.resposta is None:
        st.title("Assistente de Pré-Mercado (TradingView)")
        conn = udb.create_connection()
        st.session_state.user_id = udb.get_user_info(conn, "id", "users", st.session_state.email)[0][0]
        conn.close()

        defaults = {
            "ativos_b3": "WIN1!:BMFBOVESPA,WDO1!:BMFBOVESPA,EWZ:NYSE,PBR:NYSE,VALE:NYSE,ITUB:NYSE,BBD:NYSE,BR20:DJCFD",
            "ativos_fx": "US500:TICKMILL,US30:TICKMILL,USTEC:TICKMILL,DXY:TICKMILL,CL1!:NYMEX,NIKKEI225:VANTAGE,KOSPI:TVC,FEF1!:SGX,ASX:IG",
            "ativo_alvo": "WIN1!:BMFBOVESPA",
            "bars": 100,
            "model": "gpt-5-2025-08-07"
        }

        st.sidebar.subheader("🔧 Configuração")
        presets = listar_presets()
        preset_names = list(presets.keys())
        novo_nome_preset = st.sidebar.text_input("Nome da sua Configuração")
        preset_selected = st.sidebar.selectbox("Carregar Configuração", ["Nenhum"] + preset_names)
        if preset_selected != "Nenhum":
            defaults.update(presets[preset_selected])

        # Inputs principais
        col1, col2 = st.columns(2, gap='large')
        with col1:
            with st.expander("Fontes de Dados B3", expanded=True):
                st.session_state.ativos_b3 = st.text_input("Ativos B3", defaults["ativos_b3"])
        with col2:
            with st.expander("Fontes de Dados FX / Globais", expanded=True):
                st.session_state.ativos_fx = st.text_input("Ativos FX", defaults["ativos_fx"])

        st.session_state.ativo_alvo = st.text_input("Ativo alvo", defaults["ativo_alvo"])
        st.session_state.bars = st.sidebar.slider("Número de barras", 1, 500, defaults["bars"])
        model_list = ["gpt-5", "gpt-5-2025-08-07", "gpt-5.1", "gpt-5.1-chat-latest", "gpt-5-pro", "gpt-5-nano", "o3-pro", "gpt-4.1"]
        st.session_state.model = st.sidebar.selectbox("Modelo", model_list, index=model_list.index(defaults["model"]))

        if st.sidebar.button("💾 Salvar Preset"):
            if not novo_nome_preset:
                st.sidebar.error("Informe um nome para o preset")
            else:
                salvar_preset(novo_nome_preset, defaults)
                st.sidebar.success("Preset salvo com sucesso")
                st.rerun()
        if preset_selected != "Nenhum":
            if st.sidebar.button("🗑️ Deletar Preset"):
                deletar_preset(preset_selected)
                st.sidebar.success("Preset removido")
                st.rerun()


        # if st.sidebar.button("Salvar Configuração"):
        #     if novo_nome_preset.strip():
        #         dados = {
        #             "ativos_b3": st.session_state.get("ativos_b3", defaults["ativos_b3"]),
        #             "ativos_fx": st.session_state.get("ativos_fx", defaults["ativos_fx"]),
        #             "ativo_alvo": st.session_state.get("ativo_alvo", defaults["ativo_alvo"]),
        #             "bars": st.session_state.get("bars", defaults["bars"]),
        #             "model": st.session_state.get("model", defaults["model"]),
        #         }
        #         salvar_preset(novo_nome_preset.strip(), dados)
        #         st.sidebar.success("Preset salvo!")
        #     else:
        #         st.sidebar.error("Digite um nome para o preset.")

        # if preset_selected != "Nenhum":
        #     if st.sidebar.button("Excluir preset"):
        #         deletar_preset(preset_selected)
        #         st.sidebar.warning("Preset deletado!")

        # credenciais TradingView (opcional)
        #with st.expander("Credenciais TradingView (opcional)"):
            #st.info("Se o fetch anon falhar para certos símbolos, informe usuário/senha do TradingView aqui via st.secrets ou inputs.")
            #tv_user = st.text_input("TV username (opcional)")
            #tv_pass = st.text_input("TV password (opcional)", type="password")

        def build_system_prompt(ativo_alvo: str) -> str:
            formato_saida = '''\nFormato de saída (obrigatório — responda exatamente neste formato):
                            {
                              "timestamp_utc": "YYYY-MM-DDTHH:MM:SS",
                              "trend_summary": "frase curta",
                              "trade_ideas": [
                                {
                                  "id": 1,
                                  "direction": "LONG" | "SHORT",
                                  "entry_price": number,
                                  "target_price": number,
                                  "stop_price": number,
                                  "position_size_pct": number,
                                  "confidence_pct": number,
                                  "rationale": "2-4 linhas explicando micro+macro",
                                  "invalidating_signals": ["evento1","nivel tecnico X"]
                                }
                              ],
                              "key_indicators_used": ["lista curta de indicadores"],
                              "assumptions": ["assump1","assump2"]
                            }'''
            system_prompt_2 = f'''
                            Você é um analista quantitativo com foco em operações de daytrade em {ativo_alvo}.
Seu papel é enviar as melhores sugestões de preços de compra e de venda do mini índice de acordo com o fechamento do pregão anterior e com base nas informações dos ativos correlacionados com esse mercado (ex.: Juros, Petróleo, Ferro, Milho, Nasdaq, Nikkei)

Importante ter informações micro e macro para que possamos entender os movimentos do mercado e especular sobre o que poderá acontecer durante o dia.

Resumindo:

0. Estabeleça quais os ativos mais relevantes para sabermos o que poderá acontecer com o índice ibovespa futuro;

1. Aguarde o usuário enviar todos os dados;

2. Pense por algum tempo e faça uma relação cruzada de informações, verifique as datas para ver se não houveram feriados;

3. Sugira uma principal operação do dia, compra ou de venda desse ativo com alvos de, pelo menos, 0.22% mas traga os alvos e stops em pontos;
                            '''
            return system_prompt_2+formato_saida

        st.sidebar.divider()
        if st.sidebar.button("Executar Automação", type='primary'):
            # 1. coleta
            try:
                with st.spinner("Coletando dados via TradingView (tvdatafeed)..."):
                    ativos_b3_list = [a.strip() for a in st.session_state.ativos_b3.split(",") if a.strip()]
                    ativos_fx_list = [a.strip() for a in st.session_state.ativos_fx.split(",") if a.strip()]
                    df_tv = collect_tv_all(ativos_b3_list, ativos_fx_list, st.session_state.bars, "" or None, "" or None)
            except Exception as e:
                st.error(f"Erro ao coletar TV: {e}")
                df_tv = pd.DataFrame()

            if df_tv.empty:
                st.warning("Nenhum dado coletado. Verifique símbolos/credenciais.")
                st.stop()

            # 2. salva CSV
            df_all = df_tv.copy()
            os.makedirs("data", exist_ok=True)
            csv_path = os.path.join("data", "generated_tv.csv")
            df_all.to_csv(csv_path, index=False)
            st.toast(f"CSV salvo em {csv_path}")

            # 3. envia para agente
            with st.spinner("Consultando agente..."):
                prompt = build_system_prompt(st.session_state.ativo_alvo)
                try:
                    resposta = ask_agent_with_inline_csv(prompt, csv_path, st.session_state.model)
                except Exception as e:
                    st.error(f"Erro chamando o agente: {e}")
                    st.stop()

            st.session_state.resposta = resposta
            st.rerun()

    else:
        st.set_page_config(initial_sidebar_state='collapsed', layout="wide")
        st.logo(r'images/logo_white.png')

        if st.sidebar.button('Nova Consulta'):
            st.session_state.resposta = None
            st.rerun()

        # ---------------------------------------------------------
        # Verifica se existe resposta na session_state
        # ---------------------------------------------------------
        if "resposta" not in st.session_state:
            st.warning("Nenhum dado encontrado em `st.session_state.resposta`.")
            st.stop()

        # ---------------------------------------------------------
        # Trata caso seja string JSON
        # ---------------------------------------------------------
        raw = st.session_state.resposta

        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except Exception as e:
                st.error("Falha ao converter JSON da resposta:")
                st.code(raw)
                st.error(e)
                st.stop()
        else:
            data = raw

        # ---------------------------------------------------------
        # Cabeçalho com timestamp e resumo da tendência
        # ---------------------------------------------------------
        st.caption(f'Data e hora da consulta {pd.to_datetime(data.get("timestamp_utc", "-"), yearfirst=True).strftime("%d/%m/%Y %H:%M")}')
        st.subheader(f"Resumo do Cenário")
        st.write(data.get("trend_summary", "-"))

        # ---------------------------------------------------------
        # Tabela das Trade Ideas
        # ---------------------------------------------------------
        trade_ideas = data.get("trade_ideas", [])

        if trade_ideas:
            st.header("Operações Sugeridas")
            col1, col2 = st.columns([0.65,0.35], gap='small')
            for t in trade_ideas:
                with col1:
                    # Escolhe cor conforme direção
                    color = "#4CAF50" if t.get("direction") == "LONG" else "#FF5252"
                    txt_direcao = "COMPRA" if t.get("direction") == "LONG" else "VENDA"

                    st.html(
                        f"""
                                        <div style="
                                            padding: 18px;
                                            border-radius: 12px;
                                            margin-bottom: 15px;
                                            border: 1px solid #333;
                                            background-color: #1e1e1e;
                                        ">
                                            <h3 style="margin: 0; color: {color};">{txt_direcao} — Operação #{t.get('id')}</h3>
                                            <hr style="opacity: 0.2;">
    
                                            <div style="display: flex; gap: 1em; flex-wrap: wrap;">
    
                                                <div style="flex: 1;">
                                                    <div style="color: #aaa;">Entrada</div>
                                                    <div style="font-size: 18px; font-weight: 600;">{t.get("entry_price"):.0f}</div>
                                                </div>
    
                                                <div style="flex: 1;">
                                                    <div style="color: #aaa;">Alvo</div>
                                                    <div style="font-size: 18px; font-weight: 600;">{t.get("target_price"):.0f} <a style="font-size: 12px">({abs(t.get("entry_price")-t.get("target_price"))} pts)</a></div>
                                                </div>
    
                                                <div style="flex: 1;">
                                                    <div style="color: #aaa;">Stop</div>
                                                    <div style="font-size: 18px; font-weight: 600;">{t.get("stop_price"):.0f} <a style="font-size: 12px">({abs(t.get("entry_price")-t.get("stop_price"))} pts)</a></div>
                                                </div>
    
                                                <div style="flex: 1;">
                                                    <div style="color: #aaa;">Risco (%)</div>
                                                    <div style="font-size: 18px; font-weight: 600;">{t.get("position_size_pct")}%</div>
                                                </div>
    
                                                <div style="flex: 1;">
                                                    <div style="color: #aaa;">Confiança (%)</div>
                                                    <div style="font-size: 20px; font-weight: 600;">{t.get("confidence_pct")}%</div>
                                                </div>
    
                                            </div>
                                        </div>
                                        """
                    )

                with col2:
                    # ---------------------------------------------------------
                    # Expansores individuais das operações
                    # ---------------------------------------------------------
                    with st.expander(f'Detalhes da Operação #{t.get("id")} — {"COMPRA" if t.get("direction") == "LONG" else "VENDA"}', icon=f':material/description:'):
                        st.subheader("Racional")
                        st.write(t.get("rationale", "-"))

                        st.subheader("Sinais de Invalidação")
                        for inv in t.get("invalidating_signals", []):
                            st.markdown(f"- {inv}")

        c1, c2 = st.columns(2)
        with c1:
            # ---------------------------------------------------------
            # Indicadores usados
            # ---------------------------------------------------------
            st.header("Indicadores Utilizados")
            indicators = data.get("key_indicators_used", [])
            for ind in indicators:
                st.markdown(f"- {ind}")

        with c2:
            # ---------------------------------------------------------
            # Premissas
            # ---------------------------------------------------------
            st.header("Premissas da Análise")
            assumptions = data.get("assumptions", [])
            for asm in assumptions:
                st.markdown(f"- {asm}")
else:
    from streamlit_cookies_controller import CookieController
    cookies = CookieController().getAll()

    if 'cookies' in st.session_state and st.session_state.cookies is not None:
        if st.session_state.cookies['logged_in']:
            st.session_state['logged_in'] = st.session_state['cookies']['logged_in']
            st.session_state['email'] = st.session_state['cookies']['user_email']
            st.session_state['access_lvl'] = st.session_state['cookies']['access_lvl']
            st.session_state['expiration'] = st.session_state['cookies']['expiration']
            st.rerun()
        else:
            st.switch_page('login.py')


