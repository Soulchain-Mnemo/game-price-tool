"""
Game Price Tool - Version API officielle PriceCharting
"""

import streamlit as st
import requests
from urllib.parse import quote_plus

# ======================
# TON TOKEN PRICECHARTING
# ======================
PRICECHARTING_TOKEN = "5efe3fca0235950767def78da9d234cea9dbf13d"

st.set_page_config(
    page_title="Game Price Tool 🎮",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data(ttl=3600)
def get_eur_rate():
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=8)
        return r.json()["rates"]["EUR"]
    except:
        return 0.92


def cents_to_eur(cents, rate):
    """PriceCharting renvoie les prix en centimes de dollar"""
    if cents is None:
        return None
    try:
        usd = float(cents) / 100
        return round(usd * rate, 2)
    except:
        return None


@st.cache_data(ttl=1800)
def search_games(query: str, max_results: int = 8):
    """Recherche via l'API officielle PriceCharting"""
    url = "https://www.pricecharting.com/api/products"
    params = {
        "t": PRICECHARTING_TOKEN,
        "q": query
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if data.get("status") != "success":
            return []

        products = data.get("products", [])
        return products[:max_results]
    except Exception as e:
        st.error(f"Erreur API : {e}")
        return []


def make_links(title: str, console: str = ""):
    q = quote_plus(f"{title} {console}".strip())
    q_simple = quote_plus(title)
    return {
        "pricecharting": f"https://www.pricecharting.com/search-products?q={q_simple}&type=prices",
        "vinted": f"https://www.vinted.fr/catalog?search_text={q_simple}&order=relevance",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q_simple}&category=43",
        "ebay_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
        "ebay_us": f"https://www.ebay.com/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
    }


# ======================
# Interface
# ======================
st.title("🎮 Game Price Tool")
st.caption("Version API officielle PriceCharting • Prix Loose / CIB / New en €")

with st.sidebar:
    st.header("Options")
    max_results = st.slider("Nombre de résultats", 3, 12, 6)
    st.markdown("---")
    rate = get_eur_rate()
    st.metric("Taux USD → EUR", f"{rate:.4f}")
    st.caption("Token PriceCharting actif")

query = st.text_input(
    "Titre du jeu + console (recommandé)",
    placeholder="Ex: Chrono Trigger SNES   ou   Kirby Dream Land Game Boy"
)

if st.button("Chercher", type="primary") and query.strip():
    with st.spinner("Recherche en cours via PriceCharting API..."):
        results = search_games(query.strip(), max_results=max_results)

    if not results:
        st.warning("Aucun résultat trouvé. Essaie avec un titre plus précis + console.")
    else:
        rate = get_eur_rate()
        st.success(f"{len(results)} résultat(s) trouvé(s)")

        for product in results:
            title = product.get("product-name") or product.get("product_name") or "Sans titre"
            console = product.get("console-name") or product.get("console_name") or ""
            loose_cents = product.get("loose-price") or product.get("loose_price")
            cib_cents = product.get("cib-price") or product.get("cib_price")
            new_cents = product.get("new-price") or product.get("new_price")
            product_id = product.get("id")

            loose_eur = cents_to_eur(loose_cents, rate)
            cib_eur = cents_to_eur(cib_cents, rate)
            new_eur = cents_to_eur(new_cents, rate)

            # Lien vers la page du jeu
            game_url = f"https://www.pricecharting.com/game/{product_id}" if product_id else None

            with st.container(border=True):
                col1, col2 = st.columns([3, 2])

                with col1:
                    st.subheader(title)
                    if console:
                        st.caption(f"Console : {console}")
                    if game_url:
                        st.markdown(f"[Voir sur PriceCharting ↗]({game_url})")

                with col2:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Loose", f"{loose_eur} €" if loose_eur is not None else "—")
                    c2.metric("CIB", f"{cib_eur} €" if cib_eur is not None else "—")
                    c3.metric("New", f"{new_eur} €" if new_eur is not None else "—")

                # Liens marketplace
                links = make_links(title, console)
                st.markdown(
                    f"**Liens rapides :** "
                    f"[Vinted]({links['vinted']}) · "
                    f"[Leboncoin]({links['leboncoin']}) · "
                    f"[eBay FR vendus]({links['ebay_fr']}) · "
                    f"[eBay US vendus]({links['ebay_us']})"
                )

        st.caption(
            "Prix fournis par l'API officielle PriceCharting (en USD puis convertis en €). "
            "Les cotes PAL / marché français peuvent légèrement différer → vérifie eBay.fr."
        )

st.markdown("---")
st.caption("Game Price Tool • API PriceCharting • Usage personnel")
