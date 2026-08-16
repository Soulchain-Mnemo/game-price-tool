"""
Game Price Tool v3
-------------------
Recherche + cotation de jeux retro via l'API PriceCharting.

Design : chaque résultat affiche directement le maximum d'infos utiles pour
décider d'un achat (Loose, CIB, ventes/mois, genre, année, photo) sans clic
supplémentaire. Les prix moins courants (New, Graded, Boîte seule, Manuel
seul) + les liens de comparaison sont dans un détail dépliable.

Corrections vs versions précédentes :
1. Rate limit API (1 appel/seconde) -> on fetch le détail de chaque résultat
   de façon SÉQUENTIELLE avec une pause, et on montre une barre de progression
   pendant le chargement. Tout est mis en cache (30 min) donc relancer la même
   recherche est instantané au second passage.
2. Photos -> l'API ne renvoie aucun champ image. Les visuels sont hébergés
   sur storage.googleapis.com/images.pricecharting.com/. On scrape la page
   produit et on prend la 1ère URL de ce domaine trouvée dans le HTML (c'est
   toujours l'image principale). Fallback silencieux si la page ne matche
   pas exactement (titres avec accents / éditions spéciales).
3. Ventes/mois -> l'API expose "sales-volume" (ventes annuelles estimées),
   on l'affiche divisé par 12.
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
IMAGE_URL_RE = re.compile(r'https://storage\.googleapis\.com/images\.pricecharting\.com/[^\s"\'\)]+?/240\.jpg')

st.set_page_config(
    page_title="Game Price Tool",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .block-container { max-width: 760px; padding-top: 1.2rem; }
        .price-row { display: flex; gap: 8px; margin-top: 6px; }
        .price-chip {
            background: #1f1f1f; border: 1px solid #333; border-radius: 8px;
            padding: 6px 12px; text-align: center; flex: 1;
        }
        .price-chip.main { border-color: #4c8bf5; }
        .price-chip-label { font-size: 0.68rem; color: #999; text-transform: uppercase; letter-spacing: 0.4px; }
        .price-chip-value { font-size: 1.05rem; font-weight: 700; color: #fff; }
        .price-chip-value.empty { color: #555; font-weight: 400; font-size: 0.9rem; }
        .badge {
            display: inline-block; background: #262626; color: #bbb;
            border-radius: 6px; padding: 2px 8px; font-size: 0.72rem; margin-right: 5px;
        }
        .sub-price-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 4px; }
        .links-row a { color: #4c8bf5; text-decoration: none; margin-right: 14px; font-size: 0.85rem; }
        .links-row a:hover { text-decoration: underline; }
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
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " €"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


@st.cache_data(ttl=1800)
def search_games(query: str, max_results: int = 8):
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
    """Best-effort : scrape la 1ère image du CDN PriceCharting sur la fiche produit."""
    url = f"https://www.pricecharting.com/game/{slugify(console)}/{slugify(title)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return None
        match = IMAGE_URL_RE.search(r.text)
        if match:
            return match.group(0)
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


def chip(label, cents, rate, main=False):
    val = cents_to_eur(cents, rate)
    css = "price-chip main" if main else "price-chip"
    val_css = "price-chip-value" if val is not None else "price-chip-value empty"
    display = format_eur(val) if val is not None else "—"
    return f"<div class='{css}'><div class='price-chip-label'>{label}</div><div class='{val_css}'>{display}</div></div>"


def monthly_sales(details):
    vol = details.get("sales-volume")
    try:
        vol = float(vol)
        monthly = vol / 12
        if monthly < 1:
            return "< 1 vente/mois"
        return f"≈ {monthly:.0f} ventes/mois"
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------
# Interface
# ------------------------------------------------------------------
st.title("🎮 Game Price Tool")
st.caption("Toutes les infos pour décider d'un achat, en un seul écran — API PriceCharting")

query = st.text_input(
    "Recherche", placeholder="Kirby Dream Land Game Boy", label_visibility="collapsed"
)
c1, c2 = st.columns([3, 1])
with c1:
    search = st.button("Chercher", type="primary", use_container_width=True)
with c2:
    max_results = st.selectbox("Nb", [4, 6, 8], index=1, label_visibility="collapsed")

if search and query.strip():
    with st.spinner("Recherche..."):
        results, error = search_games(query.strip(), max_results=max_results)
    st.session_state.last_results = results
    st.session_state.last_error = error
    st.session_state.last_query = query.strip()

results = st.session_state.get("last_results", [])
error = st.session_state.get("last_error")
last_query = st.session_state.get("last_query", "")

if error:
    st.error(f"Erreur API : {error}")

elif results:
    placeholder = st.empty()
    progress = None
    total = len(results)

    enriched = []
    for i, product in enumerate(results):
        pid = str(product.get("id", ""))
        if progress is None:
            progress = placeholder.progress(0, text=f"Chargement des cotes... (0/{total})")
        details = get_full_product(pid)
        title = details.get("product-name") or product.get("product-name") or "Sans titre"
        console = details.get("console-name") or product.get("console-name") or ""
        image_url = get_game_image(console, title)
        enriched.append({"id": pid, "details": details, "image": image_url, "title": title, "console": console})
        progress.progress((i + 1) / total, text=f"Chargement des cotes... ({i + 1}/{total})")
        if i < total - 1:
            time.sleep(1.05)  # respecte la limite API PriceCharting : 1 appel/seconde

    placeholder.empty()
    rate = get_eur_rate()
    st.success(f"{total} résultat(s) pour « {last_query} »")

    for item in enriched:
        details = item["details"]
        if not details:
            st.warning(f"⚠️ {item['title']} — impossible de récupérer les prix (réessaie la recherche).")
            continue

        title = item["title"]
        console = item["console"]
        genre = details.get("genre")
        release = details.get("release-date")
        release_year = release.split("-")[0] if release else None
        sales_txt = monthly_sales(details)

        with st.container(border=True):
            col_img, col_info = st.columns([1, 3])
            with col_img:
                if item["image"]:
                    st.image(item["image"], use_container_width=True)
                else:
                    st.markdown(
                        "<div style='background:#1f1f1f;border:1px solid #333;border-radius:8px;"
                        "aspect-ratio:3/4;display:flex;align-items:center;justify-content:center;"
                        "color:#555;font-size:1.8rem;'>🎮</div>",
                        unsafe_allow_html=True,
                    )
            with col_info:
                st.markdown(f"**{title}**")
                badges = f"<span class='badge'>{console}</span>"
                if genre:
                    badges += f"<span class='badge'>{genre}</span>"
                if release_year:
                    badges += f"<span class='badge'>{release_year}</span>"
                st.markdown(badges, unsafe_allow_html=True)
                if sales_txt:
                    st.caption(sales_txt)

                price_html = "<div class='price-row'>"
                price_html += chip("Loose", details.get("loose-price"), rate, main=True)
                price_html += chip("CIB", details.get("cib-price"), rate, main=True)
                price_html += "</div>"
                st.markdown(price_html, unsafe_allow_html=True)

            with st.expander("Plus de détails (New, Graded, boîte seule...)"):
                grid = "<div class='sub-price-grid'>"
                grid += chip("New", details.get("new-price"), rate)
                grid += chip("Graded", details.get("graded-price"), rate)
                grid += chip("Boîte seule", details.get("box-only-price"), rate)
                grid += chip("Manuel seul", details.get("manual-only-price"), rate)
                grid += "</div>"
                st.markdown(grid, unsafe_allow_html=True)

                links = make_links(title, console)
                st.markdown(
                    f"<div class='links-row' style='margin-top:12px;'>"
                    f"<a href='{links['pc']}' target='_blank'>PriceCharting ↗</a>"
                    f"<a href='{links['vinted']}' target='_blank'>Vinted ↗</a>"
                    f"<a href='{links['leboncoin']}' target='_blank'>Leboncoin ↗</a>"
                    f"<a href='{links['ebay_fr']}' target='_blank'>eBay FR (vendus) ↗</a>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

elif search and not results and not error:
    st.warning("Aucun résultat. Essaie d'ajouter le nom de la console.")

st.caption("API PriceCharting · Prix convertis en € · Photos scrapées depuis la fiche produit (best-effort)")
