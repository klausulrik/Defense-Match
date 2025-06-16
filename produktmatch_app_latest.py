
import streamlit as st
import pandas as pd
import sqlite3
import tempfile
from itertools import combinations
import plotly.express as px

st.set_page_config(page_title="Produktmatch – Synkroniseret", layout="wide")

st.sidebar.title("📂 Upload database")
uploaded_file = st.sidebar.file_uploader("Vælg en SQLite-database (.sqlite)", type=["sqlite"])
if not uploaded_file:
    st.stop()

with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp.write(uploaded_file.read())
    conn = sqlite3.connect(tmp.name)

produkter_df = pd.read_sql_query("SELECT * FROM Produktbeskrivelser", conn)
pk_df       = pd.read_sql_query("SELECT * FROM ProduktKapabilitet",   conn)
kap_df      = pd.read_sql_query("SELECT * FROM Produktionskapabiliteter", conn)
virk_df     = pd.read_sql_query("SELECT * FROM Virksomheder",         conn)
vk_df       = pd.read_sql_query("SELECT * FROM VirksomhedKapabilitet",conn)

for col in ["virksomhed_id", "kapabilitet_id"]:
    if vk_df[col].apply(lambda x: isinstance(x, bytes)).any():
        vk_df[col] = vk_df[col].apply(lambda x: int.from_bytes(x, 'little') if isinstance(x, bytes) else int(x))

def vis_virk(navn: str):
    row = virk_df[virk_df['navn'] == navn]
    if row.empty:
        return
    v = row.iloc[0]
    st.markdown(f'''
    ### {v['navn']}
    - 📍 **Lokation:** {v['lokation']}
    - 🔗 **Website:** [{v['website']}]({v['website']})
    - 🛡️ **Egnethed:** {v['egnethed_forsvar']}
    ''')
    k_ids  = vk_df[vk_df['virksomhed_id'] == v['virksomhed_id']]['kapabilitet_id']
    k_navn = kap_df[kap_df['kapabilitet_id'].isin(k_ids)]['navn'].tolist()
    st.markdown("**Kapabiliteter:**")
    for n in k_navn:
        st.write(f"- {n}")

st.title("🛠️ Produkt-match")
produkt = st.selectbox("Vælg produkt", produkter_df['navn'])
prod_id = produkter_df.loc[produkter_df['navn'] == produkt, 'produkt_id'].iloc[0]

krav_ids = pk_df[pk_df['produkt_id'] == prod_id]['kapabilitet_id'].tolist()
krav_df  = kap_df[kap_df['kapabilitet_id'].isin(krav_ids)]

st.subheader("🔧 Marker kapabilitetskrav")
valgte = [row['kapabilitet_id'] for _, row in krav_df.iterrows() if st.checkbox(row['navn'], value=True)]
if not valgte:
    st.warning("Vælg mindst én kapabilitet for at se match.")
    st.stop()

krav_set = set(valgte)

vk_grp = vk_df.groupby('virksomhed_id')['kapabilitet_id'].apply(set).reset_index()
vk_grp['navn'] = vk_grp['virksomhed_id'].map(virk_df.set_index('virksomhed_id')['navn'])

vk_grp['fuldt'] = vk_grp['kapabilitet_id'].apply(lambda s: krav_set.issubset(s))
match_fuldt = vk_grp[vk_grp['fuldt']]

kombi_2, kombi_3 = [], []
for r in (2, 3):
    for combo in combinations(vk_grp.itertuples(index=False), r):
        names = [v.navn for v in combo if isinstance(v.navn, str)]
        if len(names) != r:
            continue
        samlet = set().union(*(v.kapabilitet_id for v in combo))
        if krav_set.issubset(samlet):
            (kombi_2 if r == 2 else kombi_3).append(" + ".join(names))

chart_df = pd.DataFrame({"Matchtype": ["Individuelt","Kombi 2","Kombi 3"],
                         "Antal": [len(match_fuldt), len(kombi_2), len(kombi_3)]})
st.plotly_chart(px.bar(chart_df, x="Matchtype", y="Antal",
                       title="Match-oversigt"), use_container_width=True)

if not match_fuldt.empty:
    sel_indiv = st.selectbox("🏭 Individuelle match", match_fuldt['navn'].tolist())
    vis_virk(sel_indiv)
if kombi_2:
    sel_k2 = st.selectbox("🤝 Kombi – 2 virksomheder", kombi_2)
    st.markdown("### Detaljer for virksomheder i kombinationen")
    for n in sel_k2.split(" + "):
        vis_virk(n.strip())
if kombi_3:
    sel_k3 = st.selectbox("🤝 Kombi – 3 virksomheder", kombi_3)
    st.markdown("### Detaljer for virksomheder i kombinationen")
    for n in sel_k3.split(" + "):
        vis_virk(n.strip())
