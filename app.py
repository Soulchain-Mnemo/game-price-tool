"""
Game Price Tool - Version légère & stable pour Streamlit Cloud
Sans Playwright (beaucoup plus fiable)
"""

import streamlit as st
import requests
from urllib.parse import quote_plus

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


def make_links(title: str):
    q = quote_plus(title.strip())
    return {
        "pricecharting": f"https://www.pricecharting.com/search-products?q={q}&type=prices",
        "vinted": f"https://www.vinted.fr/catalog?search_text={q}&order=relevance",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q}&category=43",
        "ebay_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&_sacat=0&LH_Sold=1&LH_Complete=1&rt=nc&LH_PrefLoc=1",
        "ebay_us": f"https://www.ebay.com/sch/i.html?_nkw={q}&_sacat=0&LH_Sold=1&LH_Complete=1&rt=nc",
    }


# ---------- Interface ----------
st.title("🎮 Game Price Tool")
st.caption("Version légère • Stable sur Streamlit Cloud • Liens directs + cotes")

with st.sidebar:
    st.header("Comment utiliser")
    st.markdown("""
    1. Tape le **titre + console** (ex: `Kirby Dream Land Game Boy`)
    2. Clique sur **Chercher**
    3. Ouvre les liens pour voir les cotes et les ventes récentes
    """)
    rate = get_eur_rate()
    st.metric("Taux USD → EUR", f"{rate:.4f}")

query = st.text_input(
    "Titre du jeu + console",
    placeholder="Ex: Kirby Dream Land Game Boy   ou   Chrono Trigger SNES"
)

if st.button("Chercher", type="primary") and query.strip():
    title = query.strip()
    links = make_links(title)

    st.success(f"Recherche prête pour : **{title}**")

    st.subheader("Liens utiles")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        ### 📊 Cotes
        - [**PriceCharting** (Loose / CIB / New)]({links['pricecharting']})
        
        ### 🇫🇷 Ventes France
        - [**eBay.fr vendus**]({links['ebay_fr']})
        - [**Leboncoin**]({links['leboncoin']})
        - [**Vinted**]({links['vinted']})
        """)

    with col2:
        st.markdown(f"""
        ### 🇺🇸 Ventes internationales
        - [**eBay.com vendus**]({links['ebay_us']})
        """)

    st.info("""
    **Astuce chineur :**
    - Sur PriceCharting → regarde les colonnes **Loose** et **CIB**
    - Sur eBay.fr → filtre « Ventes terminées » pour voir les vrais prix en euros
    - Plus tu précises la console (SNES, PS1, Game Boy…), meilleurs sont les résultats
    """)

st.markdown("---")
st.caption("Game Price Tool • Version légère & stable • Usage personnel")
