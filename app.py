"""
Game Price Tool v2
-------------------
Recherche + cotation de jeux retro via l'API PriceCharting.

Corrections apportées à la v1 :
1. CIB manquant par intermittence -> l'API PriceCharting limite à 1 appel/seconde.
   La v1 appelait /api/product pour CHAQUE résultat en boucle rapide -> blocages
   silencieux. Ici on ne va chercher le détail complet que quand l'utilisateur
   clique sur un jeu (1 seul appel de détail à la fois).
2. Photos absentes -> l'API /api/product ne renvoie AUCUN champ image (vérifié
   dans la doc officielle). Les visuels existent uniquement sur les pages du
   site (pricecharting.com/game/<console>/<jeu>). On les récupère en scrapant
   la balise og:image de cette page, avec un cache pour ne pas le refaire à
   chaque rechargement.

Sécurité : le token est lu depuis st.secrets si présent (recommandé pour un
déploiement), sinon depuis la constante ci-dessous pour un usage local rapide.
Si tu push ce fichier sur un repo public, pense à retirer le token en dur.
"""

import re
import time
import unicodedata
from urllib.parse import quote_plus

import requests
import streamlit as st

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
DEFAULT_TOKEN = "5efe3fca0235950767def78da9d234cea9dbf13d"
PRICECHARTING_TOKEN = st.secrets.get("PRICECHARTING_TOKEN", DEFAULT_TOKEN) if hasattr(st, "secrets") else DEFAULT_TOKEN

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GamePriceTool/2.0)"}

st.set_page_config(
    page_title="Game Price Tool",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .block-container { max-width: 720px; padding-top: 1.2rem; }

        .result-row {
            background: #161616;
            border: 1px solid #2a2a2a;
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 8px;
        }
        .result-title { font-size: 1rem; font-weight: 600; color: #fff; }
        .result-console { font-size: 0.82rem; color: #999; }

        .detail-header {
            display: flex;
            gap: 18px;
            background: #161616;
            border: 1px solid #2c2c2c;
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 16px;
        }
        .detail-title { font-size: 1.35rem; font-weight: 700; color: #fff; margin-bottom: 2px; }
        .detail-sub { font-size: 0.9rem; color: #999; margin-bottom: 10px; }
        .badge {
            display: inline-block;
            background: #2a2a2a;
            color: #ccc;
            border-radius: 6px;
            padding: 2px 9px;
            font-size: 0.75rem;
            margin-right: 6px;
        }

        .price-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 6px;
        }
        .price-box {
            background: #1f1f1f;
            border-radius: 10px;
            padding: 12px 6px;
            text-align: center;
            border: 1px solid #333;
        }
        .price-box.highlight { border-color: #4c8bf5; }
        .price-label { font-size: 0.72rem; color: #999; margin-bottom: 4px; letter-spacing: 0.4px; text-transform: uppercase; }
        .price-value { font-size: 1.25rem; font-weight: 700; color: #fff; }
        .price-value.empty { color: #555; font-weight: 400; font-size: 1rem; }

        .links-row a {
            color: #4c8bf5;
            text-decoration: none;
            margin-right: 14px;
            font-size: 0.88rem;
        }
        .links-row a:hover { text-decoration: underline; }

        .cover-img img { border-radius: 10px; border: 1px solid #2c2c2c; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_eur_rate():
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=8)
        return r.json()["rates"]["EUR"]
    except Exception:
        return 0.92


def cents_to_eur(value, rate):
    if value is None:
        return None
    try:
        return round(float(value) / 100 * rate, 2)
    except Exception:
        return None


def format_eur(value):
    if value is None:
        return None
    # format français : 1 234,56 €
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " €"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


@st.cache_data(ttl=1800)
def search_games(query: str, max_results: int = 10):
    """Un seul appel rapide : /api/products. Pas de détail ici -> pas de risque de rate-limit."""
    url = "https://www.pricecharting.com/api/products"
    params = {"t": PRICECHARTING_TOKEN, "q": query}
    try:
        r = requests.get(url, params=params, timeout=12)
        data = r.json()
        if data.get("status") != "success":
            return [], data.get("error-message", "Erreur inconnue")
        return data.get("products", [])[:max_results], None
    except Exception as e:
        return [], str(e)


@st.cache_data(ttl=1800)
def get_full_product(product_id: str):
    """Détail complet d'UN jeu (loose, cib, new, graded, box only, manual only, genre, date...)."""
    url = "https://www.pricecharting.com/api/product"
    params = {"t": PRICECHARTING_TOKEN, "id": product_id}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get("status") == "success":
            return data
    except Exception:
        pass
    return {}


@st.cache_data(ttl=86400)
def get_game_image(console: str, title: str):
    """Scrape la balise og:image de la fiche produit (l'API n'a aucun champ image).
    Best-effort : si le slug ne matche pas exactement l'URL PriceCharting, on renvoie None
    sans planter le reste de la fiche."""
    url = f"https://www.pricecharting.com/game/{slugify(console)}/{slugify(title)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return None
        match = re.search(r'property="og:image"\s+content="([^"]+)"', r.text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def make_links(title: str, console: str = ""):
    q = quote_plus(f"{title} {console}".strip())
    q_simple = quote_plus(title)
    return {
        "pc": f"https://www.pricecharting.com/search-products?q={q_simple}&type=prices",
        "vinted": f"https://www.vinted.fr/catalog?search_text={q_simple}",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q_simple}&category=43",
        "ebay_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1",
    }


def price_box_html(label, cents, rate, highlight=False):
    val = cents_to_eur(cents, rate)
    css = "price-box highlight" if highlight else "price-box"
    val_css = "price-value" if val is not None else "price-value empty"
    display = format_eur(val) if val is not None else "—"
    return f"""<div class="{css}"><div class="price-label">{label}</div><div class="{val_css}">{display}</div></div>"""


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None
if "selected_meta" not in st.session_state:
    st.session_state.selected_meta = {}

# ------------------------------------------------------------------
# Interface
# ------------------------------------------------------------------
st.title("🎮 Game Price Tool")
st.caption("Loose · CIB · New · Graded · Box only · Manual only — API PriceCharting")

query = st.text_input(
    "Recherche", placeholder="Kirby Dream Land Game Boy", label_visibility="collapsed"
)
c1, c2 = st.columns([3, 1])
with c1:
    search = st.button("Chercher", type="primary", use_container_width=True)
with c2:
    max_results = st.selectbox("Nb", [6, 10, 14], index=1, label_visibility="collapsed")

if search and query.strip():
    st.session_state.selected_id = None  # nouvelle recherche -> on ferme le détail précédent

if search and query.strip():
    with st.spinner("Recherche..."):
        results, error = search_games(query.strip(), max_results=max_results)
    st.session_state.last_results = results
    st.session_state.last_error = error

results = st.session_state.get("last_results", [])
error = st.session_state.get("last_error")

if error:
    st.error(f"Erreur API : {error}")

# ------------------------------------------------------------------
# Fiche détaillée (si un jeu est sélectionné)
# ------------------------------------------------------------------
if st.session_state.selected_id:
    product_id = st.session_state.selected_id

    if st.button("← Retour aux résultats"):
        st.session_state.selected_id = None
        st.rerun()

    with st.spinner("Récupération de la fiche complète..."):
        details = get_full_product(product_id)
        time.sleep(0.3)  # marge de politesse, l'API tolère 1 appel/s

    if not details:
        st.warning("Impossible de récupérer ce jeu (l'API a peut-être limité la requête, réessaie).")
    else:
        rate = get_eur_rate()
        title = details.get("product-name", "Sans titre")
        console = details.get("console-name", "")
        genre = details.get("genre")
        release = details.get("release-date")

        with st.spinner("Récupération de la photo..."):
            image_url = get_game_image(console, title)

        col_img, col_info = st.columns([1, 2])
        with col_img:
            if image_url:
                st.image(image_url, use_container_width=True)
            else:
                st.markdown(
                    "<div style='background:#1f1f1f;border:1px solid #333;border-radius:10px;"
                    "aspect-ratio:3/4;display:flex;align-items:center;justify-content:center;"
                    "color:#555;font-size:2.2rem;'>🎮</div>",
                    unsafe_allow_html=True,
                )
        with col_info:
            st.markdown(f"<div class='detail-title'>{title}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='detail-sub'>{console}</div>", unsafe_allow_html=True)
            badges = ""
            if genre:
                badges += f"<span class='badge'>{genre}</span>"
            if release:
                badges += f"<span class='badge'>Sortie : {release}</span>"
            if badges:
                st.markdown(badges, unsafe_allow_html=True)

        st.markdown("#### Cotes")
        grid = "<div class='price-grid'>"
        grid += price_box_html("Loose", details.get("loose-price"), rate, highlight=True)
        grid += price_box_html("CIB (complet)", details.get("cib-price"), rate, highlight=True)
        grid += price_box_html("New (scellé)", details.get("new-price"), rate)
        grid += price_box_html("Graded", details.get("graded-price"), rate)
        grid += price_box_html("Boîte seule", details.get("box-only-price"), rate)
        grid += price_box_html("Manuel seul", details.get("manual-only-price"), rate)
        grid += "</div>"
        st.markdown(grid, unsafe_allow_html=True)

        links = make_links(title, console)
        st.markdown(
            f"<div class='links-row' style='margin-top:16px;'>"
            f"<a href='{links['pc']}' target='_blank'>PriceCharting ↗</a>"
            f"<a href='{links['vinted']}' target='_blank'>Vinted ↗</a>"
            f"<a href='{links['leboncoin']}' target='_blank'>Leboncoin ↗</a>"
            f"<a href='{links['ebay_fr']}' target='_blank'>eBay FR (vendus) ↗</a>"
            f"</div>",
            unsafe_allow_html=True,
        )

# ------------------------------------------------------------------
# Liste des résultats (masquée quand une fiche est ouverte)
# ------------------------------------------------------------------
elif results:
    st.success(f"{len(results)} résultat(s) — clique sur un jeu pour voir toutes les cotes + photo")
    for product in results:
        pid = str(product.get("id", ""))
        title = product.get("product-name") or "Sans titre"
        console = product.get("console-name") or ""

        row_col, btn_col = st.columns([5, 1])
        with row_col:
            st.markdown(
                f"<div class='result-row'>"
                f"<div class='result-title'>{title}</div>"
                f"<div class='result-console'>{console}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with btn_col:
            if st.button("Voir", key=f"btn_{pid}", use_container_width=True):
                st.session_state.selected_id = pid
                st.rerun()

elif search and not results and not error:
    st.warning("Aucun résultat. Essaie d'ajouter le nom de la console.")

st.caption("API PriceCharting · Prix convertis en € · Photos scrapées depuis la fiche produit (best-effort)")
