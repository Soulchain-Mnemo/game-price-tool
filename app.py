"""
Game Price Tool - Version debug + interface propre
"""

import streamlit as st
import requests
from urllib.parse import quote_plus
import json

PRICECHARTING_TOKEN = "5efe3fca0235950767def78da9d234cea9dbf13d"

st.set_page_config(
    page_title="Game Price Tool",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container { max-width: 640px; padding-top: 1.2rem; }
    .game-card {
        background: #161616;
        border: 1px solid #2c2c2c;
        border-radius: 14px;
        padding: 18px 16px;
        margin-bottom: 16px;
    }
    .price-box {
        background: #1f1f1f;
        border-radius: 10px;
        padding: 14px 8px;
        text-align: center;
        border: 1px solid #333;
    }
    .price-label { font-size: 0.78rem; color: #999; margin-bottom: 6px; letter-spacing: 0.5px; }
    .price-value { font-size: 1.45rem; font-weight: 700; color: #fff; }
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


def find_price(product, possible_keys):
    for key in possible_keys:
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
        "pc": f"https://www.pricecharting.com/search-products?q={q_simple}&type=prices",
        "vinted": f"https://www.vinted.fr/catalog?search_text={q_simple}",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q_simple}&category=43",
        "ebay_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
    }


# ======================
# UI
# ======================
st.title("🎮 Game Price Tool")
st.caption("Loose + CIB • API PriceCharting")

query = st.text_input("Recherche", placeholder="Kirby Dream Land Game Boy", label_visibility="collapsed")

c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    search = st.button("Chercher", type="primary", use_container_width=True)
with c2:
    max_results = st.selectbox("Nb", [5, 8, 10], index=0, label_visibility="collapsed")
with c3:
    debug = st.checkbox("Debug", value=False)

if search and query.strip():
    with st.spinner("Recherche..."):
        results = search_games(query.strip(), max_results=max_results)

    if not results:
        st.warning("Aucun résultat. Ajoute la console.")
    else:
        rate = get_eur_rate()
        st.success(f"{len(results)} résultat(s)")

        # Debug : affiche les vrais champs du premier résultat
        if debug and results:
            st.write("**Champs reçus de l'API (premier résultat) :**")
            st.json(results[0])

        for product in results:
            title = find_price(product, ["product-name", "product_name"]) or "Sans titre"
            console = find_price(product, ["console-name", "console_name"]) or ""
            product_id = str(product.get("id", ""))

            # On teste beaucoup de noms possibles pour Loose et CIB
            loose_raw = find_price(product, [
                "loose-price", "loose_price", "used-price", "used_price", "loose"
            ])
            cib_raw = find_price(product, [
                "cib-price", "cib_price", "complete-price", "complete_price",
                "cib", "complete", "box-price", "complete-in-box"
            ])

            loose = cents_to_eur(loose_raw, rate)
            cib = cents_to_eur(cib_raw, rate)

            # Carte
            st.markdown(f"""
            <div class="game-card">
                <div style="font-size:1.15rem; font-weight:600; margin-bottom:2px;">{title}</div>
                <div style="color:#888; font-size:0.88rem; margin-bottom:14px;">{console}</div>
            """, unsafe_allow_html=True)

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

            links = make_links(title, console)
            st.markdown(
                f"<div style='margin-top:13px; font-size:0.88rem;'>"
                f"<a href='{links['pc']}' target='_blank'>PriceCharting</a> · "
                f"<a href='{links['vinted']}' target='_blank'>Vinted</a> · "
                f"<a href='{links['leboncoin']}' target='_blank'>Leboncoin</a> · "
                f"<a href='{links['ebay_fr']}' target='_blank'>eBay FR</a>"
                f"</div></div>",
                unsafe_allow_html=True
            )

st.caption("API PriceCharting • Prix convertis en €")
