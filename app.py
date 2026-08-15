"""
Game Price Tool - MVP (version Streamlit Cloud compatible)
Outil gratuit pour chineurs de jeux rétro
"""

import streamlit as st
import requests
from playwright.sync_api import sync_playwright
import re
from urllib.parse import quote_plus
from PIL import Image
import subprocess
import sys
import os

# -----------------------------
# Config
# -----------------------------
st.set_page_config(
    page_title="Game Price Tool 🎮",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------
# Utilitaires
# -----------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_eur_rate():
    """Taux USD → EUR gratuit"""
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=8)
        return r.json()["rates"]["EUR"]
    except Exception:
        try:
            r = requests.get("https://api.exchangerate.fun/latest?base=USD", timeout=8)
            return r.json()["rates"]["EUR"]
        except Exception:
            return 0.92


def usd_to_eur(usd_str, rate):
    if not usd_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(usd_str).split()[0])
    try:
        return round(float(cleaned) * rate, 2)
    except Exception:
        return None


def clean_price_text(text):
    if not text:
        return None
    match = re.search(r"\$[\d,]+\.?\d*", str(text))
    return match.group(0) if match else None


def ensure_chromium():
    """Installe Chromium si nécessaire (important pour Streamlit Cloud)"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            return True
    except Exception:
        st.info("Installation de Chromium en cours (première fois uniquement)...")
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
                capture_output=True
            )
            return True
        except Exception as e:
            st.error(f"Impossible d'installer Chromium : {e}")
            return False


# -----------------------------
# Scraping PriceCharting
# -----------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def search_pricecharting(query: str, max_results: int = 6):
    results = []

    if not ensure_chromium():
        return results

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            url = f"https://www.pricecharting.com/search-products?q={quote_plus(query)}&type=prices"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1800)

            links = page.query_selector_all('a[href*="/game/"]')
            seen = set()
            candidates = []

            for a in links:
                href = a.get_attribute("href")
                title = a.inner_text().strip()
                if not href or not title or href in seen or "/game/" not in href:
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
                    page.wait_for_timeout(900)

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
                        "title": full_title,
                        "console": console,
                        "url": cand["url"],
                        "loose_usd": clean_price_text(loose.inner_text() if loose else None),
                        "cib_usd": clean_price_text(cib.inner_text() if cib else None),
                        "new_usd": clean_price_text(newp.inner_text() if newp else None),
                    })
                except Exception:
                    continue

            browser.close()

    except Exception as e:
        st.error(f"Erreur lors du scraping : {str(e)[:200]}")

    return results


def make_search_links(title: str, console: str = ""):
    q = quote_plus(f"{title} {console}".strip())
    q_simple = quote_plus(title)
    return {
        "vinted": f"https://www.vinted.fr/catalog?search_text={q_simple}&order=relevance",
        "leboncoin": f"https://www.leboncoin.fr/recherche?text={q_simple}&category=43",
        "ebay_sold_fr": f"https://www.ebay.fr/sch/i.html?_nkw={q}&_sacat=0&LH_Sold=1&LH_Complete=1&rt=nc&LH_PrefLoc=1",
        "ebay_sold_all": f"https://www.ebay.com/sch/i.html?_nkw={q}&_sacat=0&LH_Sold=1&LH_Complete=1&rt=nc",
    }


# -----------------------------
# Interface
# -----------------------------
st.title("🎮 Game Price Tool")
st.caption("Outil gratuit pour chineurs • Cotes Loose / CIB en € • Source : PriceCharting")

with st.sidebar:
    st.header("⚙️ Options")
    max_results = st.slider("Nombre de résultats", 3, 10, 5)
    st.markdown("---")
    st.markdown("""
    **Comment l'utiliser :**
    - Tape un titre + console (ex: `Chrono Trigger SNES`)
    - Plus tu précises, meilleurs sont les résultats
    """)
    rate = get_eur_rate()
    st.metric("Taux USD → EUR", f"{rate:.4f}")

# Recherche
text_query = st.text_input(
    "Titre du jeu + console",
    placeholder="Ex: Super Mario World SNES   ou   Resident Evil 2 PS1"
)

if st.button("Chercher", type="primary") and text_query.strip():
    query = text_query.strip()

    with st.spinner(f"Recherche de « {query} »..."):
        results = search_pricecharting(query, max_results=max_results)

    if not results:
        st.warning("Aucun résultat trouvé. Essaie avec un titre plus précis + console.")
    else:
        rate = get_eur_rate()
        st.success(f"{len(results)} résultat(s) trouvé(s)")

        for r in results:
            with st.container(border=True):
                col1, col2 = st.columns([3, 2])

                with col1:
                    st.subheader(r["title"])
                    if r.get("console"):
                        st.caption(f"Plateforme : {r['console']}")
                    st.markdown(f"[Voir sur PriceCharting ↗]({r['url']})")

                with col2:
                    loose = usd_to_eur(r.get("loose_usd"), rate)
                    cib = usd_to_eur(r.get("cib_usd"), rate)
                    newp = usd_to_eur(r.get("new_usd"), rate)

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Loose", f"{loose} €" if loose else "—")
                    c2.metric("CIB", f"{cib} €" if cib else "—")
                    c3.metric("New", f"{newp} €" if newp else "—")

                links = make_search_links(r["title"], r.get("console", ""))
                st.markdown(
                    f"**Liens :** [Vinted]({links['vinted']}) · "
                    f"[Leboncoin]({links['leboncoin']}) · "
                    f"[eBay FR vendus]({links['ebay_sold_fr']}) · "
                    f"[eBay US vendus]({links['ebay_sold_all']})"
                )

        st.caption(
            "⚠️ Prix basés sur PriceCharting (marché US principalement). "
            "Vérifie toujours les ventes récentes sur eBay.fr pour le marché français."
        )

st.markdown("---")
st.caption("Game Price Tool • MVP gratuit • Usage personnel")
