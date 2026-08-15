"""
Game Price Tool - MVP
Outil gratuit pour chineurs de jeux rétro (jusqu'à PS3)
Recherche par titre ou photo (OCR) → cotes Loose / CIB / New en €
+ liens Vinted, Leboncoin, eBay sold
"""

import streamlit as st
import requests
from playwright.sync_api import sync_playwright
import re
from urllib.parse import quote_plus
from PIL import Image
import pytesseract

# -----------------------------
# Config
# -----------------------------
st.set_page_config(
    page_title="Game Price Tool 🎮",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cache pour éviter de rescraper trop souvent
@st.cache_data(ttl=3600, show_spinner=False)
def get_eur_rate():
    """Taux USD → EUR gratuit (Frankfurter / ECB)"""
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=8)
        data = r.json()
        return data["rates"]["EUR"]
    except Exception:
        try:
            r = requests.get("https://api.exchangerate.fun/latest?base=USD", timeout=8)
            return r.json()["rates"]["EUR"]
        except Exception:
            return 0.92  # fallback approximatif


def usd_to_eur(usd_str, rate):
    """Convertit un prix PriceCharting ($xx.xx) en euros"""
    if not usd_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", usd_str.split()[0] if usd_str else "")
    try:
        usd = float(cleaned)
        return round(usd * rate, 2)
    except Exception:
        return None


def clean_price_text(text):
    if not text:
        return None
    match = re.search(r"\$[\d,]+\.?\d*", text)
    if match:
        return match.group(0)
    return text.strip()


# -----------------------------
# Scraping PriceCharting (Playwright)
# -----------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def search_pricecharting(query: str, max_results: int = 8):
    """Recherche sur PriceCharting et retourne les meilleurs matchs avec prix"""
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        try:
            url = f"https://www.pricecharting.com/search-products?q={quote_plus(query)}&type=prices"
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(1500)

            links = page.query_selector_all('a[href*="/game/"]')
            seen = set()
            candidates = []
            for a in links:
                href = a.get_attribute("href")
                title = a.inner_text().strip()
                if not href or not title or href in seen:
                    continue
                if "/game/" not in href:
                    continue
                if len(title) < 3:
                    continue
                seen.add(href)
                full_url = href if href.startswith("http") else "https://www.pricecharting.com" + href
                candidates.append({"title": title, "url": full_url})
                if len(candidates) >= max_results * 2:
                    break

            for cand in candidates[:max_results]:
                try:
                    page.goto(cand["url"], wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(800)

                    loose = page.query_selector("#used_price")
                    cib = page.query_selector("#complete_price")
                    newp = page.query_selector("#new_price")

                    h1 = page.query_selector("h1")
                    full_title = h1.inner_text().strip() if h1 else cand["title"]

                    console = ""
                    try:
                        crumbs = page.query_selector_all("nav a, .breadcrumb a, ol li a")
                        for c in crumbs:
                            t = c.inner_text().strip()
                            if t and t.lower() not in ["home", "video games", "prices"]:
                                console = t
                                break
                    except Exception:
                        pass

                    results.append({
                        "title": full_title or cand["title"],
                        "console": console,
                        "url": cand["url"],
                        "loose_usd": clean_price_text(loose.inner_text() if loose else None),
                        "cib_usd": clean_price_text(cib.inner_text() if cib else None),
                        "new_usd": clean_price_text(newp.inner_text() if newp else None),
                    })
                except Exception as e:
                    results.append({
                        "title": cand["title"],
                        "console": "",
                        "url": cand["url"],
                        "loose_usd": None,
                        "cib_usd": None,
                        "new_usd": None,
                    })
        except Exception as e:
            st.error(f"Erreur scraping PriceCharting : {e}")
        finally:
            browser.close()
    return results


def ocr_image(image: Image.Image) -> str:
    """OCR simple pour extraire du texte d'une photo de jeu"""
    try:
        text = pytesseract.image_to_string(image, lang="eng+fra")
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 2]
        return " ".join(lines)[:200]
    except Exception as e:
        return ""


def make_search_links(title: str, console: str = ""):
    """Génère des liens utiles pour le chineur français"""
    q = quote_plus(f"{title} {console}".strip())
    q_simple = quote_plus(title)
    return {
        "vinted": f"https://www.vinted.fr/catalog?search_text={q_simple}&order=relevance",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q_simple}&category=43",
        "ebay_sold_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&_sacat=0&LH_Sold=1&LH_Complete=1&rt=nc&LH_PrefLoc=1",
        "ebay_sold_all": f"https://www.ebay.com/sch/i.html?_nkw={q}&_sacat=0&LH_Sold=1&LH_Complete=1&rt=nc",
        "pricecharting": f"https://www.pricecharting.com/search-products?q={q_simple}&type=prices",
    }


# -----------------------------
# UI
# -----------------------------
st.title("🎮 Game Price Tool")
st.caption("Outil gratuit pour chineurs • Cotes Loose / CIB en € • Jusqu'à PS3 • Source : PriceCharting + eBay")

with st.sidebar:
    st.header("⚙️ Options")
    max_results = st.slider("Nombre de résultats", 3, 12, 6)
    st.markdown("---")
    st.markdown("""
    **Comment ça marche ?**
    1. Tape un titre (ex: `Chrono Trigger SNES`)
    2. Ou upload une photo de boîte / cartouche
    3. L'outil scrape PriceCharting (Loose / CIB / New)
    4. Convertit en euros et te donne les liens utiles

    **Astuce** : plus tu précises la console, meilleurs sont les résultats.
    """)
    st.markdown("---")
    rate = get_eur_rate()
    st.metric("Taux USD → EUR", f"{rate:.4f}")

# Tabs
tab1, tab2 = st.tabs(["🔍 Recherche texte", "📷 Photo (OCR)"])

query = None

with tab1:
    col1, col2 = st.columns([4, 1])
    with col1:
        text_query = st.text_input(
            "Titre du jeu + console (recommandé)",
            placeholder="Ex: Super Mario World SNES  ou  Resident Evil 2 PS1",
            key="text_q"
        )
    with col2:
        st.write("")
        st.write("")
        search_btn = st.button("Chercher", type="primary", use_container_width=True)

    if search_btn and text_query.strip():
        query = text_query.strip()

with tab2:
    st.info("Upload une photo claire de la boîte, cartouche ou jaquette. L'OCR extrait le texte puis recherche.")
    uploaded = st.file_uploader("Photo du jeu", type=["jpg", "jpeg", "png", "webp"])
    if uploaded:
        img = Image.open(uploaded)
        st.image(img, caption="Image uploadée", width=300)
        with st.spinner("OCR en cours..."):
            ocr_text = ocr_image(img)
        if ocr_text:
            st.success(f"Texte détecté : **{ocr_text[:120]}...**")
            query = ocr_text
        else:
            st.warning("Aucun texte lisible détecté. Essaie une photo plus nette ou utilise la recherche texte.")

# Lancement de la recherche
if query:
    with st.spinner(f"Recherche de « {query[:60]} » sur PriceCharting..."):
        results = search_pricecharting(query, max_results=max_results)

    if not results:
        st.warning("Aucun résultat trouvé. Essaie avec un titre plus précis + console.")
    else:
        rate = get_eur_rate()
        st.success(f"{len(results)} résultat(s) trouvé(s)")

        for i, r in enumerate(results):
            with st.container(border=True):
                col_a, col_b = st.columns([3, 2])

                with col_a:
                    st.subheader(r["title"])
                    if r.get("console"):
                        st.caption(f"Console / plateforme : {r['console']}")
                    st.markdown(f"[Voir sur PriceCharting ↗]({r['url']})")

                with col_b:
                    loose_eur = usd_to_eur(r.get("loose_usd"), rate)
                    cib_eur = usd_to_eur(r.get("cib_usd"), rate)
                    new_eur = usd_to_eur(r.get("new_usd"), rate)

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Loose", f"{loose_eur} €" if loose_eur else "—", help=r.get("loose_usd"))
                    m2.metric("CIB", f"{cib_eur} €" if cib_eur else "—", help=r.get("cib_usd"))
                    m3.metric("New", f"{new_eur} €" if new_eur else "—", help=r.get("new_usd"))

                links = make_search_links(r["title"], r.get("console", ""))
                st.markdown(
                    f"""
                    **Liens rapides :**  
                    [Vinted]({links['vinted']}) · 
                    [Leboncoin]({links['leboncoin']}) · 
                    [eBay FR vendus]({links['ebay_sold_fr']}) · 
                    [eBay US vendus]({links['ebay_sold_all']})
                    """
                )

        st.markdown("---")
        st.caption(
            "⚠️ Prix issus de PriceCharting (basés sur ventes eBay US principalement). "
            "Les cotes européennes (PAL) peuvent différer. Toujours vérifier les ventes récentes sur eBay.fr. "
            "Outil personnel gratuit – respecte les sites sources."
        )

st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:gray; font-size:0.85em;'>"
    "Game Price Tool • MVP gratuit • Scraping respectueux + OCR • "
    "Idéal pour chineurs Vinted / Leboncoin / vide-greniers"
    "</div>",
    unsafe_allow_html=True
)
