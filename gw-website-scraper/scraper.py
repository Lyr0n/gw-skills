#!/usr/bin/env python3
"""Website scraper pour la prospection.

Lit un CSV qui contient une colonne de sites web, visite la page d'accueil et quelques pages
utiles (contact, mentions légales, à propos), et ajoute au CSV ce qu'on y trouve :
domaine, emails, téléphone, LinkedIn de l'entreprise, Facebook, Instagram, SIREN (mentions
légales), et si le site appartient à une chaîne ou à une plateforme.

Sans dépendance (bibliothèque standard Python 3.9+).

Usage :
  python3 scraper.py entree.csv sortie.csv --col site [--sep ";"] [--limit 25] [--workers 8]
"""
import argparse
import csv
import html
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
TIMEOUT = 12
MAX_PAGES = 4
MOTS_PAGES = ("contact", "mentions", "legal", "legales", "a-propos", "apropos", "qui-sommes",
              "about", "equipe", "team", "impressum", "cgv")

# Domaines qui ne sont pas le site propre de l'établissement : chaîne, plateforme, réseau social.
TIERS = ("accor.com", "all.accor.com", "bestwestern", "booking.com", "facebook.com", "instagram.com",
         "logishotels.com", "choicehotels", "ihg.com", "marriott.com", "hilton.com", "hotel-bb.com",
         "campanile.com", "kyriad.com", "louvrehotels.com", "brithotel.fr", "premiereclasse.com",
         "ibis.com", "novotel.com", "mercure.com", "hotelf1.com", "greet.com", "expedia", "tripadvisor",
         "airbnb", "google.com", "hotels.com", "the-originals", "inter-hotel",
         "contact-hotel", "citotel", "logis-hotels", "relaischateaux", "ace-hotel", "fasthotel")

RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_TEL = re.compile(r"(?:\+33\s?|0)[1-9](?:[\s.-]?\d{2}){4}")
RE_SIREN = re.compile(r"(?:SIREN|SIRET|RCS|R\.C\.S\.?)[^0-9]{0,40}((?:\d[\s.]?){9})")
RE_HREF = re.compile(r'href=["\']([^"\'#]+)["\']', re.I)
FAUX_EMAILS = ("sentry", "wixpress", "example", "domain.com", "@2x", ".png", ".jpg", ".webp", ".gif",
               "yourdomain", "email.com", "nom@", "votre", "exemple")
# Messageries perso acceptées même si le domaine diffère du site (petites boîtes).
MESSAGERIES = ("gmail.", "orange.fr", "wanadoo.fr", "hotmail.", "outlook.", "free.fr", "sfr.fr", "laposte.net",
               "yahoo.", "icloud.com", "live.fr", "neuf.fr", "bbox.fr", "aol.com")


def normaliser_url(u):
    u = (u or "").strip()
    if not u or u == "-":
        return ""
    if not u.startswith("http"):
        u = "https://" + u
    return u


def domaine(u):
    net = urllib.parse.urlparse(u).netloc.lower()
    return net[4:] if net.startswith("www.") else net


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if "text/html" not in (r.headers.get("Content-Type") or "text/html"):
            return "", r.geturl()
        return r.read(1_500_000).decode("utf-8", "ignore"), r.geturl()


def pages_utiles(base, page):
    vues, out = set(), []
    for href in RE_HREF.findall(page):
        absu = urllib.parse.urljoin(base, html.unescape(href))
        if domaine(absu) != domaine(base):
            continue
        chemin = urllib.parse.urlparse(absu).path.lower()
        if any(m in chemin for m in MOTS_PAGES) and absu not in vues:
            vues.add(absu)
            out.append(absu)
    return out[: MAX_PAGES - 1]


def extraire(texte, dom):
    texte = html.unescape(texte)
    emails = []
    for e in RE_EMAIL.findall(texte.replace("[at]", "@").replace("(at)", "@")):
        e = e.lower().strip(".")
        if any(f in e for f in FAUX_EMAILS) or e in emails:
            continue
        dom_e = e.split("@")[1]
        racine = dom.split(".")[-2] if dom.count(".") else dom
        # un email d'un autre domaine pro est celui de l'agence web ou d'un partenaire : on l'écarte
        if racine not in dom_e and not any(m in dom_e for m in MESSAGERIES):
            continue
        emails.append(e)
    # le domaine du site d'abord
    emails.sort(key=lambda e: any(m in e.split("@")[1] for m in MESSAGERIES))
    tels = []
    for t in RE_TEL.findall(texte):
        t = re.sub(r"[\s.-]", "", t)
        if t not in tels:
            tels.append(t)
    sirens = [re.sub(r"\D", "", s)[:9] for s in RE_SIREN.findall(texte)]
    def lien(motif):
        m = re.search(r'https?://(?:[a-z]{2,3}\.)?' + motif + r'[^"\'\s<>]*', texte, re.I)
        return m.group(0).rstrip("/\\") if m else ""
    return {
        "emails": emails,
        "tels": tels,
        "siren": next((s for s in sirens if len(s) == 9), ""),
        "linkedin": lien(r"linkedin\.com/company/"),
        "facebook": lien(r"facebook\.com/(?!sharer|share|plugins|tr\b)"),
        "instagram": lien(r"instagram\.com/(?!p/)"),
    }


def scraper(url):
    res = {"domaine": "", "site_tiers": "", "emails": "", "email_principal": "", "telephone": "",
           "linkedin_entreprise": "", "facebook": "", "instagram": "", "siren_site": "",
           "pages_visitees": 0, "statut_scrap": ""}
    url = normaliser_url(url)
    if not url:
        res["statut_scrap"] = "pas de site"
        return res
    dom = domaine(url)
    res["domaine"] = dom
    if any(t in dom for t in TIERS):
        res["site_tiers"] = "oui"
        res["statut_scrap"] = "site de chaîne ou plateforme, non visité"
        return res
    try:
        page, finale = telecharger(url)
    except Exception as e:  # noqa: BLE001
        res["statut_scrap"] = f"erreur : {type(e).__name__}"
        return res
    if domaine(finale) != dom:
        res["domaine"] = dom = domaine(finale)
        if any(t in dom for t in TIERS):
            res["site_tiers"] = "oui"
    textes = [page]
    for u in pages_utiles(finale, page):
        try:
            textes.append(telecharger(u)[0])
        except Exception:  # noqa: BLE001
            pass
    x = extraire("\n".join(textes), dom)
    res.update({
        "emails": " | ".join(x["emails"][:3]),
        "email_principal": x["emails"][0] if x["emails"] else "",
        "telephone": x["tels"][0] if x["tels"] else "",
        "linkedin_entreprise": x["linkedin"],
        "facebook": x["facebook"],
        "instagram": x["instagram"],
        "siren_site": x["siren"],
        "pages_visitees": len(textes),
        "statut_scrap": "ok",
    })
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entree")
    ap.add_argument("sortie")
    ap.add_argument("--col", default="site", help="colonne qui contient le site web")
    ap.add_argument("--sep", default=None, help="séparateur du CSV d'entrée (deviné sinon)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    brut = open(a.entree, encoding="utf-8-sig").read()
    sep = a.sep or (";" if brut.split("\n", 1)[0].count(";") > brut.split("\n", 1)[0].count(",") else ",")
    lignes = list(csv.DictReader(brut.splitlines(), delimiter=sep))
    if a.limit:
        lignes = lignes[: a.limit]
    if not lignes or a.col not in lignes[0]:
        sys.exit(f"Colonne « {a.col} » absente. Colonnes : {list(lignes[0]) if lignes else []}")

    with ThreadPoolExecutor(a.workers) as ex:
        resultats = list(ex.map(lambda l: scraper(l[a.col]), lignes))

    champs = list(lignes[0]) + list(resultats[0])
    with open(a.sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        for l, r in zip(lignes, resultats):
            w.writerow({**l, **r})

    ok = sum(1 for r in resultats if r["statut_scrap"] == "ok")
    print(f"{len(lignes)} sites, {ok} visités")
    for k in ("email_principal", "telephone", "linkedin_entreprise", "siren_site"):
        print(f"  {k} : {sum(1 for r in resultats if r[k])}")
    print(f"  chaîne ou plateforme : {sum(1 for r in resultats if r['site_tiers'])}")
    print(f"→ {a.sortie}")


if __name__ == "__main__":
    main()
