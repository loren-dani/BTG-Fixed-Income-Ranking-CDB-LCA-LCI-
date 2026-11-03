import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Ranking de Renda Fixa | BTG", layout="wide")
ROOT = Path(__file__).resolve().parent
BASE = ROOT / "data" / "BTG_Consolidado.xlsx"
TAXAS = ROOT / "data" / "taxas_macro.csv"

@st.cache_data(show_spinner="Carregando títulos...")
def carregar_titulos():
    df = pd.read_excel(BASE, sheet_name="Base_Consolidada")
    df.columns = df.columns.str.strip()
    df["Data_Emissao"] = pd.to_datetime(df["Data_Emissao"], errors="coerce")
    df["Data Vencimento"] = pd.to_datetime(df["Data Vencimento"], errors="coerce")
    df["Taxa"] = pd.to_numeric(df["Taxa"], errors="coerce")
    return df

@st.cache_data(show_spinner=False)
def carregar_taxas():
    if not TAXAS.exists():
        return None
    t = pd.read_csv(TAXAS)
    exigidas = {"Data", "Selic", "IPCA_12m"}
    if not exigidas.issubset(t.columns):
        raise ValueError(f"taxas_macro.csv precisa conter: {', '.join(sorted(exigidas))}")
    t["Data"] = pd.to_datetime(t["Data"], errors="coerce")
    for c in ("Selic", "IPCA_12m"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    return t.dropna(subset=["Data"]).sort_values("Data")

@st.cache_data(show_spinner=False)
def preparar(df, data_ref, selic, ipca, choque_selic_pp, fator):
    d = df.loc[df["Data_Emissao"].eq(data_ref)].copy()
    d["DU"] = np.busday_count(
        d["Data_Emissao"].values.astype("datetime64[D]"),
        d["Data Vencimento"].values.astype("datetime64[D]")
    )
    d = d.loc[d["DU"] > 0].copy()
    # Choque de 0,25 ponto percentual na taxa Selic (25 pontos-base).
    # Converte-se para variação RELATIVA antes de aplicar fator 2,5 ao IPCA.
    selic_cenario = selic + choque_selic_pp
    if selic <= 0 or selic_cenario <= 0:
        raise ValueError("A Selic inicial e a projetada devem ser positivas.")
    delta_rel = selic_cenario / selic - 1
    ipca_cenario = ipca * (1 + fator * delta_rel)
    if ipca_cenario <= -100:
        raise ValueError("Cenário de IPCA inválido (menor ou igual a -100%).")
    idx = d["Indexador"].fillna("").astype(str).str.upper().str.strip()
    taxa = d["Taxa"]
    # As taxas de emissão são percentuais ao ano. Projeção ilustrativa
    # com indexadores anuais constantes e sem calendário de pagamentos.
    a = np.full(len(d), np.nan)
    is_pct = idx.eq("%CDI")
    is_cdi_spread = idx.eq("CDI + A.A.")
    is_cdi = idx.eq("CDI")
    is_ipca_spread = idx.eq("IPCA + A.A.")
    is_ipca = idx.eq("IPCA")
    is_pre = idx.isin(["PRE", "", "NAN"])
    a[is_pct] = selic_cenario * taxa[is_pct] / 100
    a[is_cdi_spread] = ((1 + selic_cenario/100) * (1 + taxa[is_cdi_spread]/100) - 1) * 100
    a[is_ipca_spread] = ((1 + ipca_cenario/100) * (1 + taxa[is_ipca_spread]/100) - 1) * 100
    # CDI e IPCA sem spread explícito: não presumir interpretação da coluna Taxa
    a[is_pre] = taxa[is_pre]
    d["Taxa_Bruta_Indicativa"] = a
    anos = d["DU"] / 252
    rendimento = (1 + d["Taxa_Bruta_Indicativa"] / 100) ** anos - 1
    prazo_dias = (d["Data Vencimento"] - d["Data_Emissao"]).dt.days
    ir = np.select(
        [prazo_dias <= 180, prazo_dias <= 360, prazo_dias <= 720],
        [0.225, 0.20, 0.175], default=0.15
    )
    # Hipótese simplificada: isenção LCI/LCA. Verificar outros instrumentos
    # e particularidades fiscais antes de uso decisório.
    isento = d["Produto"].astype(str).str.upper().isin(["LCI", "LCA"])
    ir = np.where(isento, 0.0, ir)
    rendimento_liquido = rendimento - np.maximum(rendimento, 0) * ir
    d["TAE_Liquida_Indicativa"] = ((1 + rendimento_liquido) ** (1 / anos) - 1) * 100
    d = d.replace([np.inf, -np.inf], np.nan)
    d = d.sort_values(["TAE_Liquida_Indicativa", "DU"], ascending=[False, True], na_position="last")
    d["Ranking"] = d["TAE_Liquida_Indicativa"].rank(method="min", ascending=False)
    return d, selic_cenario, ipca_cenario

st.title("Ranking de Renda Fixa | BTG")
st.caption("Análise histórica de títulos e cenários indicativos de indexadores")
st.warning("Simulação exploratória: não é cotação atual nem recomendação de investimento. Selic é usada como proxy simplificada do CDI; retornos ignoram fluxos intermediários, feriados, custos e particularidades tributárias.")

try:
    base = carregar_titulos()
except Exception as exc:
    st.error(f"Não foi possível carregar a base: {exc}")
    st.stop()

try:
    taxas = carregar_taxas()
except Exception as exc:
    st.error(f"Erro na base de taxas: {exc}")
    st.stop()

with st.sidebar:
    st.header("Filtros e premissas")
    datas = sorted(base["Data_Emissao"].dropna().unique(), reverse=True)
    data_escolhida = st.selectbox("Data histórica do Ranking", datas, format_func=lambda x: pd.Timestamp(x).strftime("%d/%m/%Y"))
    produtos = sorted(base["Produto"].dropna().astype(str).unique())
    escolhidos = st.multiselect("Produtos", produtos, default=produtos)
    selic_padrao, ipca_padrao = 14.0, 4.5
    if taxas is not None:
        anteriores = taxas.loc[taxas["Data"] <= pd.Timestamp(data_escolhida)]
        if not anteriores.empty:
            ultima = anteriores.iloc[-1]
            if pd.notna(ultima["Selic"]): selic_padrao = float(ultima["Selic"])
            if pd.notna(ultima["IPCA_12m"]): ipca_padrao = float(ultima["IPCA_12m"])
    else:
        st.info("taxas_macro.csv ainda não foi enviado. Valores abaixo são exemplos editáveis, não dados históricos.")
    selic = st.number_input("Selic de referência (% a.a.)", min_value=0.01, max_value=100.0, value=selic_padrao, step=0.25)
    ipca = st.number_input("IPCA 12m de referência (%)", min_value=-20.0, max_value=100.0, value=ipca_padrao, step=0.25)
    passos = st.slider("Choque Selic (passos de 0,25 p.p.)", -24, 24, 0)
    choque = passos * 0.25
    fator = st.number_input("Fator hipotético Selic → IPCA", value=2.5, step=0.1)

try:
    ranking, selic_proj, ipca_proj = preparar(base, pd.Timestamp(data_escolhida), selic, ipca, choque, fator)
except Exception as exc:
    st.error(f"Não foi possível calcular o cenário: {exc}")
    st.stop()

ranking = ranking.loc[ranking["Produto"].astype(str).isin(escolhidos)]
a, b, c, d = st.columns(4)
a.metric("Títulos na seleção", f"{len(ranking):,}".replace(",", "."))
b.metric("Selic cenário", f"{selic_proj:.2f}%")
c.metric("IPCA cenário", f"{ipca_proj:.2f}%")
d.metric("Choque Selic", f"{choque:+.2f} p.p.")

st.subheader("Ranking indicativo")
colunas = ["Ranking", "Produto", "Emissor", "Data Vencimento", "Taxa", "Indexador", "DU", "Taxa_Bruta_Indicativa", "TAE_Liquida_Indicativa", "Roa"]
vis = ranking[colunas].copy()
vis = vis.rename(columns={"Data Vencimento": "Vencimento", "DU": "Dias úteis", "Roa": "ROA"})
st.dataframe(vis, use_container_width=True, hide_index=True)
st.download_button("Baixar seleção CSV", vis.to_csv(index=False).encode("utf-8-sig"), file_name="ranking_btg_cenario.csv", mime="text/csv")

validos = ranking.dropna(subset=["TAE_Liquida_Indicativa"]).head(20).copy()
if not validos.empty:
    validos["Título"] = validos["Produto"].astype(str) + " | " + validos["Emissor"].astype(str)
    fig = px.bar(validos.iloc[::-1], x="TAE_Liquida_Indicativa", y="Título", orientation="h", title="20 maiores TAE líquidas indicativas")
    fig.update_layout(xaxis_title="TAE líquida indicativa (% a.a.)", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

with st.expander("Metodologia e limitações"):
    st.markdown("""
    - **Histórico:** cada consulta utiliza a data de referência da planilha BTG; não implica disponibilidade atual.
    - **Cenários:** Selic projetada = Selic inicial + choque em p.p.; variação relativa = Selic projetada / Selic inicial − 1; IPCA projetado = IPCA inicial × (1 + 2,5 × variação relativa).
    - **Taxas:** prefixados usam taxa informada; %CDI aplica percentual à Selic-proxy; CDI+ e IPCA+ usam composição anual. Registros CDI/IPCA sem spread explícito ficam sem TAE estimada.
    - **TAE:** capitalização simplificada por dias úteis/252; IR regressivo aproximado por prazo em dias corridos; LCI e LCA tratados como isentos na hipótese. Pagamentos periódicos, amortizações, carência e outras regras tributárias ainda não estão modelados.
    - **Risco:** fator 2,5 é premissa de cenário escolhida pelo projeto, não causalidade demonstrada nem previsão econométrica.
    """)
