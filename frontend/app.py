from pathlib import Path
import os
from decimal import Decimal
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="DataPulse · Analyse des ventes", page_icon="📊", layout="wide")
st.markdown(
    """<style>.stApp{background:#f5f7fb}h1,h2,h3{color:#17243c}
[data-testid="stMetric"]{background:white;padding:20px;border:1px solid #e0e6f0;border-radius:12px}
[data-testid="stSidebar"]{background:#eaf0fa}</style>""",
    unsafe_allow_html=True,
)
API = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
KEY = os.getenv("IMPORT_API_KEY", "")


def call(method, route, **kwargs):
    try:
        response = requests.request(method, API + route, timeout=60, **kwargs)
        if not response.ok:
            st.error(f"API : {response.status_code}")
            st.json(response.json())
            return None
        return response.json()
    except (requests.RequestException, ValueError):
        st.error("API inaccessible. Vérifier que le backend est démarré puis réessayer.")
        return None


with st.sidebar:
    st.title("DataPulse")
    st.caption("Des données fiables. Des décisions claires.")
    page = st.radio("Navigation", ["Tableau de bord", "Importer des ventes", "Historique"])
    st.divider()
    st.caption("Démo portfolio · Données de ventes uniquement · EUR")

st.title(page)
if page == "Importer des ventes":
    st.write("Contrôlez le fichier avant import. Si une ligne est invalide, aucune vente n’est enregistrée.")
    st.caption(
        "CSV UTF-8, séparateur virgule, dates YYYY-MM-DD, prix décimaux avec un point. Maximum 2 Mo / 10 000 lignes."
    )
    sample = Path(__file__).resolve().parents[1] / "data" / "sales_demo.csv"
    st.download_button("Télécharger le CSV de démonstration", sample.read_bytes(), "sales_demo.csv", "text/csv")
    upload = st.file_uploader("Fichier de ventes", type=["csv"])
    if upload:
        data = upload.getvalue()
        report = call(
            "POST", "/imports/preview", files={"file": (upload.name, data, "text/csv")}, headers={"X-API-Key": KEY}
        )
        if report is not None:
            a, b = st.columns(2)
            a.metric("Lignes valides", report["valid_rows"])
            b.metric("Lignes à corriger", report["invalid_rows"])
            if report["errors"]:
                st.dataframe(pd.DataFrame(report["errors"]), hide_index=True)
            else:
                st.dataframe(pd.DataFrame(report["preview"]), hide_index=True)
                if st.button("Confirmer l’import", type="primary"):
                    result = call(
                        "POST", "/imports", files={"file": (upload.name, data, "text/csv")}, headers={"X-API-Key": KEY}
                    )
                    if result:
                        st.success(f"{result['imported_rows']} ventes enregistrées. Consultez le tableau de bord.")
elif page == "Historique":
    records = call("GET", "/imports")
    if records:
        st.dataframe(pd.DataFrame(records), hide_index=True, width="stretch")
    elif records is not None:
        st.info("Aucun import pour le moment.")
else:
    records = call("GET", "/sales")
    if records is not None:
        if not records:
            st.info("Votre tableau de bord est prêt. Importez le CSV de démonstration pour commencer.")
        else:
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            a, b = st.columns(2)
            categories = a.multiselect("Catégories", sorted(df.category.unique()), default=sorted(df.category.unique()))
            dates = b.date_input(
                "Période",
                value=(df.date.min().date(), df.date.max().date()),
                min_value=df.date.min().date(),
                max_value=df.date.max().date(),
            )
            if len(dates) != 2:
                st.info("Sélectionnez une date de début et une date de fin.")
                st.stop()
            filtered = df[
                df.category.isin(categories) & (df.date.dt.date >= dates[0]) & (df.date.dt.date <= dates[1])
            ].copy()
            if filtered.empty:
                st.info("Aucune vente sur cette sélection.")
                st.stop()
            total = sum((Decimal(v) for v in filtered.revenue), Decimal(0))
            filtered["revenue"] = filtered.revenue.astype(float)
            metrics = st.columns(3)
            metrics[0].metric("Chiffre d’affaires", f"{total:,.2f} €".replace(",", " "))
            metrics[1].metric("Lignes de vente", len(filtered))
            metrics[2].metric("Articles vendus", int(filtered.quantity.sum()))
            daily = filtered.groupby("date", as_index=False).revenue.sum()
            st.plotly_chart(
                px.line(
                    daily,
                    x="date",
                    y="revenue",
                    title="Évolution quotidienne du chiffre d’affaires",
                    markers=True,
                    labels={"date": "Date", "revenue": "CA (€)"},
                ),
                width="stretch",
            )
            left, right = st.columns(2)
            products = filtered.groupby("product", as_index=False).revenue.sum().nlargest(10, "revenue")
            left.plotly_chart(
                px.bar(
                    products,
                    x="revenue",
                    y="product",
                    orientation="h",
                    title="Top 10 produits par chiffre d’affaires",
                    labels={"revenue": "CA (€)", "product": "Produit"},
                ),
                width="stretch",
            )
            cats = filtered.groupby("category", as_index=False).revenue.sum()
            right.plotly_chart(
                px.bar(
                    cats,
                    x="category",
                    y="revenue",
                    title="Chiffre d’affaires par catégorie",
                    labels={"category": "Catégorie", "revenue": "CA (€)"},
                ),
                width="stretch",
            )
            st.subheader("Ventes détaillées")
            st.caption(
                "Les indicateurs portent sur les lignes de vente, pas sur des commandes ou des clients. Maximum 50 000 lignes affichées."
            )
            st.dataframe(filtered, hide_index=True, width="stretch")
