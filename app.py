"""
Game Price Tool - Version API PriceCharting
Interface mobile-friendly + photos
"""

import streamlit as st
import requests
from urllib.parse import quote_plus

# ======================
# TOKEN
# ======================
PRICECHARTING_TOKEN = "5efe3fca0235950767def78da9d234cea9dbf13d"

st.set_page_config(
    page_title="Game Price Tool 🎮",
    page_icon="🎮",
    layout="centered",          # mieux pour mobile
    initial_sidebar_state="collapsed"
)

# CSS pour rendre l'interface plus propre sur téléphone
st.markdown("""
<style>
    .stMetric {
        background-color: #1e1e1e;
        padding: 12px 8px;
        border-radius: 10px;
        text-align: center;
    }
    .stMetric label {
        font-size: 0.85rem !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
        font-weight: 700;
    }
    div[data-testid="stVerticalBlock"] > div {
        gap: 0.6rem;
    }
    .game-card {
        border: 1px solid #333;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        background: #161616;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def get_eur_rate():
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=8)
        return r.json()["rates"]["EUR"]
    except:
        return 0.92


def cents_to_eur(cents, rate):
    if cents is None:
        return None
    try:
        return round(float(cents) / 100 * rate, 2)
    except:
        return None


@st.cache_data(ttl=1800)
def search_games(query: str, max_results: int = 8):
    url = "https://www.pricecharting.com/api/products"
    params = {"t": PRICECHARTING_TOKEN, "q": query}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("status") != "success":
            return []
        return data.get("products", [])[:max_results]
    except Exception as e:
        st.error(f"Erreur API : {e}")
        return []


def get_product_details(product_id: str):
    """Récupère plus d'infos (notamment l'image si disponible)"""
    url = "https://www.pricecharting.com/api/product"
    params = {"t": PRICECHARTING_TOKEN, "id": product_id}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get("status") == "success":
            return data
    except:
        pass
    return {}


def make_links(title: str, console: str = ""):
    q = quote_plus(f"{title} {console}".strip())
    q_simple = quote_plus(title)
    return {
        "vinted": f"https://www.vinted.fr/catalog?search_text={q_simple}",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q_simple}&category=43",
        "ebay_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
        "ebay_us": f"https://www.ebay.com/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
    }


# ======================
# Interface
# ======================
st.title("🎮 Game Price Tool")
st.caption("Prix Loose / CIB / New en € • API PriceCharting")

query = st.text_input(
    "Titre + console",
    placeholder="Ex: Kirby Dream Land Game Boy",
    label_visibility="collapsed"
)

col_btn1, col_btn2 = st.columns([3, 1])
with col_btn1:
    search = st.button("Chercher", type="primary", use_container_width=True)
with col_btn2:
    max_results = st.selectbox("Nb", [4, 6, 8, 10], index=1, label_visibility="collapsed")

if search and query.strip():
    with st.spinner("Recherche..."):
        results = search_games(query.strip(), max_results=max_results)

    if not results:
        st.warning("Aucun résultat. Essaie avec le nom + console.")
    else:
        rate = get_eur_rate()
        st.success(f"{len(results)} résultat(s)")

        for product in results:
            title = product.get("product-name") or product.get("product_name") or "Sans titre"
            console = product.get("console-name") or product.get("console_name") or ""
            product_id = str(product.get("id", ""))

            loose = cents_to_eur(product.get("loose-price") or product.get("loose_price"), rate)
            cib = cents_to_eur(product.get("cib-price") or product.get("cib_price"), rate)
            new = cents_to_eur(product.get("new-price") or product.get("new_price"), rate)

            # Essayer de récupérer plus d'infos (image)
            details = get_product_details(product_id) if product_id else {}
            image_url = details.get("image") or details.get("image-url") or details.get("cover")

            # Carte du jeu
            with st.container():
                st.markdown(f"### {title}")
                if console:
                    st.caption(f"{console}")

                # Photo + Prix
                img_col, price_col = st.columns([1, 2])

                with img_col:
                    if image_url:
                        st.image(image_url, use_container_width=True)
                    else:
                        # Image de secours via le lien PriceCharting
                        st.markdown(
                            f"<div style='background:#222;height:140px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#666;font-size:13px;'>Pas d'image</div>",
                            unsafe_allow_html=True
                        )

                with price_col:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Loose", f"{loose} €" if loose is not None else "—")
                    c2.metric("CIB", f"{cib} €" if cib is not None else "—")
                    c3.metric("New", f"{new} €" if new is not None else "—")

                    if product_id:
                        st.markdown(f"[Voir sur PriceCharting ↗](https://www.pricecharting.com/game/{product_id})")

                # Liens marketplace
                links = make_links(title, console)
                st.markdown(
                    f"<div style='font-size:14px; margin-top:8px;'>"
                    f"<a href='{links['vinted']}' target='_blank'>Vinted</a> · "
                    f"<a href='{links['leboncoin']}' target='_blank'>Leboncoin</a> · "
                    f"<a href='{links['ebay_fr']}' target='_blank'>eBay FR</a> · "
                    f"<a href='{links['ebay_us']}' target='_blank'>eBay US</a>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                st.divider()

st.caption("API PriceCharting • Prix convertis en € • Usage personnel")
