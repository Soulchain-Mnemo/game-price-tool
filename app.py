"""
Game Price Tool - Version propre (Loose + CIB)
"""

import streamlit as st
import requests
from urllib.parse import quote_plus

PRICECHARTING_TOKEN = "5efe3fca0235950767def78da9d234cea9dbf13d"

st.set_page_config(
    page_title="Game Price Tool",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Style propre
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 640px;
    }
    h3 {
        margin-bottom: 0.2rem !important;
        font-size: 1.25rem !important;
    }
    .price-box {
        background: #1c1c1c;
        border-radius: 10px;
        padding: 14px 10px;
        text-align: center;
        border: 1px solid #333;
    }
    .price-label {
        font-size: 0.8rem;
        color: #aaa;
        margin-bottom: 4px;
    }
    .price-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #fff;
    }
    .game-card {
        background: #161616;
        border: 1px solid #2a2a2a;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 14px;
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


def cents_to_eur(value, rate):
    if value is None:
        return None
    try:
        return round(float(value) / 100 * rate, 2)
    except:
        return None


def get_price(product, *keys):
    """Essaie plusieurs noms de champs possibles"""
    for key in keys:
        if key in product and product[key] is not None:
            return product[key]
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


def make_links(title: str, console: str = ""):
    q = quote_plus(f"{title} {console}".strip())
    q_simple = quote_plus(title)
    return {
        "vinted": f"https://www.vinted.fr/catalog?search_text={q_simple}",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q_simple}&category=43",
        "ebay_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
        "ebay_us": f"https://www.ebay.com/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
        "pc": f"https://www.pricecharting.com/search-products?q={q_simple}&type=prices"
    }


# ======================
# Interface
# ======================
st.title("🎮 Game Price Tool")
st.caption("Loose & CIB en euros • API PriceCharting")

query = st.text_input(
    "Recherche",
    placeholder="Ex: Kirby Dream Land Game Boy",
    label_visibility="collapsed"
)

col1, col2 = st.columns([3, 1])
with col1:
    search = st.button("Chercher", type="primary", use_container_width=True)
with col2:
    max_results = st.selectbox("Résultats", [5, 8, 10], index=0, label_visibility="collapsed")

if search and query.strip():
    with st.spinner("Recherche en cours..."):
        results = search_games(query.strip(), max_results=max_results)

    if not results:
        st.warning("Aucun résultat trouvé. Ajoute la console (ex: Game Boy, SNES, PS1).")
    else:
        rate = get_eur_rate()
        st.success(f"{len(results)} résultat(s)")

        for product in results:
            title = get_price(product, "product-name", "product_name") or "Sans titre"
            console = get_price(product, "console-name", "console_name") or ""
            product_id = str(product.get("id", ""))

            loose_raw = get_price(product, "loose-price", "loose_price", "used-price")
            cib_raw = get_price(product, "cib-price", "cib_price", "complete-price")

            loose = cents_to_eur(loose_raw, rate)
            cib = cents_to_eur(cib_raw, rate)

            # Carte
            st.markdown(f"""
            <div class="game-card">
                <h3 style="margin:0 0 2px 0;">{title}</h3>
                <div style="color:#888; font-size:0.9rem; margin-bottom:12px;">{console}</div>
            """, unsafe_allow_html=True)

            # Prix Loose + CIB
            p1, p2 = st.columns(2)
            with p1:
                st.markdown(f"""
                <div class="price-box">
                    <div class="price-label">LOOSE</div>
                    <div class="price-value">{f"{loose} €" if loose is not None else "—"}</div>
                </div>
                """, unsafe_allow_html=True)
            with p2:
                st.markdown(f"""
                <div class="price-box">
                    <div class="price-label">CIB</div>
                    <div class="price-value">{f"{cib} €" if cib is not None else "—"}</div>
                </div>
                """, unsafe_allow_html=True)

            # Liens
            links = make_links(title, console)
            st.markdown(
                f"<div style='margin-top:12px; font-size:0.9rem;'>"
                f"<a href='{links['pc']}' target='_blank'>PriceCharting</a> · "
                f"<a href='{links['vinted']}' target='_blank'>Vinted</a> · "
                f"<a href='{links['leboncoin']}' target='_blank'>Leboncoin</a> · "
                f"<a href='{links['ebay_fr']}' target='_blank'>eBay FR</a>"
                f"</div>",
                unsafe_allow_html=True
            )

            st.markdown("</div>", unsafe_allow_html=True)
            st.write("")  # petit espace

st.caption("API PriceCharting • Prix convertis en €")
