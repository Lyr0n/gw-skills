#!/usr/bin/env python3
"""CSV outbound builder.

Construit un fichier de prospection prêt à importer (lemlist, Clay, tableur) en trois temps :
  1. la liste des boîtes : le fichier Atout France des hébergements classés, filtré
     (ou n'importe quel CSV qui a un nom, un code postal et un site) ;
  2. le site de chaque boîte : skill website-scraper (domaine, email, téléphone, LinkedIn, SIREN) ;
  3. le décideur : API Recherche d'entreprises (data.gouv), gratuite. Si la boîte est tenue par
     une holding, on remonte au dirigeant de la holding.

Ce que ça ne trouve pas : le LinkedIn et l'email perso du décideur. La colonne linkedinUrl reste
vide ; à compléter avec un outil d'enrichissement ou à la main.

Sans dépendance (bibliothèque standard Python 3.9+).

Usage, source Atout France :
  python3 builder.py sortie.csv --atout-france --type "HÔTEL DE TOURISME" \
      --etoiles 1,2,3,4 --dep 39,25 [--chambres-min 10] [--chambres-max 80] [--limit 25]
Usage, CSV déjà prêt :
  python3 builder.py sortie.csv --entree liste.csv --col-nom nom --col-cp code_postal --col-site site
"""
import argparse
import csv
import json
import os
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ATOUT_URL = "https://data.classement.atout-france.fr/static/exportHebergementsClasses/hebergements_classes.csv"
API = "https://recherche-entreprises.api.gouv.fr/search"
UA = "csv-outbound-builder/1.0"
MOTS_VIDES = ("hotel", "hôtel", "le", "la", "les", "de", "du", "des", "restaurant", "et", "&", "spa", "bar")
ROLES = ("gérant", "président", "directeur général", "président de sas", "co-gérant")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "website-scraper"))
try:
    from scraper import scraper  # noqa: E402
except ImportError:
    scraper = None


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    for essai in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.load(r).get("results", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 + essai * 2)
                continue
            return []
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return []


# 1. La liste des boîtes ------------------------------------------------------------------------

def charger_atout(a):
    req = urllib.request.Request(ATOUT_URL, headers={"User-Agent": UA})
    brut = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig")
    lignes = list(csv.DictReader(brut.splitlines(), delimiter=";"))
    etoiles = {e.strip() for e in (a.etoiles or "").split(",") if e.strip()}
    deps = tuple(d.strip() for d in (a.dep or "").split(",") if d.strip())

    def n(x):
        try:
            return int(x)
        except ValueError:
            return 0
    out = []
    for r in lignes:
        if a.type and r["TYPOLOGIE ÉTABLISSEMENT"] != a.type:
            continue
        if etoiles and r["CLASSEMENT"].split(" ")[0] not in etoiles:
            continue
        if deps and not r["CODE POSTAL"].startswith(deps):
            continue
        taille = n(r["NOMBRE DE CHAMBRES"]) or n(r["NOMBRE D'EMPLACEMENTS"])
        if a.chambres_min and taille < a.chambres_min:
            continue
        if a.chambres_max and taille > a.chambres_max:
            continue
        out.append({
            "nom": r["NOM COMMERCIAL"].strip(), "adresse": r["ADRESSE"].strip(),
            "code_postal": r["CODE POSTAL"].strip(), "ville": r["COMMUNE"].strip(),
            "site": r["SITE INTERNET"].strip(), "etoiles": r["CLASSEMENT"], "chambres": taille,
            "type": r["TYPOLOGIE ÉTABLISSEMENT"],
        })
    print(f"Atout France : {len(lignes)} établissements, {len(out)} après filtres")
    return out


def charger_csv(a):
    brut = open(a.entree, encoding="utf-8-sig").read()
    sep = ";" if brut.split("\n", 1)[0].count(";") > brut.split("\n", 1)[0].count(",") else ","
    out = []
    for r in csv.DictReader(brut.splitlines(), delimiter=sep):
        out.append({"nom": r.get(a.col_nom, ""), "code_postal": r.get(a.col_cp, ""),
                    "site": r.get(a.col_site, ""), "adresse": r.get("adresse", ""),
                    "ville": r.get("ville", ""), "etoiles": r.get("etoiles", ""),
                    "chambres": r.get("chambres", ""), "type": r.get("type", "")})
    return out


# 3. Le décideur --------------------------------------------------------------------------------

def dirigeants_utiles(res):
    """Les dirigeants, sans les commissaires aux comptes (ce sont des auditeurs, pas des décideurs)."""
    return [d for d in res.get("dirigeants", []) if "commissaire" not in sans_accents(d.get("qualite", ""))]


def dirigeant_physique(res):
    for d in dirigeants_utiles(res):
        if d.get("type_dirigeant") == "personne physique" and any(k in sans_accents(d.get("qualite", "")) for k in map(sans_accents, ROLES)):
            return d
    for d in dirigeants_utiles(res):
        if d.get("type_dirigeant") == "personne physique":
            return d
    return None


def trouver_entreprise(b, siren_site):
    if siren_site:
        r = api({"q": siren_site, "per_page": 1})
        if r and r[0].get("siren") == siren_site:
            return r[0], "haute", "SIREN des mentions légales"
    if b["nom"] and b["code_postal"]:
        nom = b["nom"]
        court = " ".join(m for m in nom.split() if sans_accents(m) not in MOTS_VIDES)
        for q in dict.fromkeys([nom, court]):
            if not q:
                continue
            r = api({"q": q, "code_postal": b["code_postal"], "etat_administratif": "A", "per_page": 5})
            hotel = [x for x in r if (x.get("activite_principale") or "").startswith(("55.", "56."))]
            if len(hotel) == 1:
                return hotel[0], "moyenne", "nom + code postal, activité hébergement ou restauration"
            if len(hotel) > 1:
                return hotel[0], "faible", f"{len(hotel)} homonymes, premier retenu"
    return None, "", "introuvable"


def enrichir(b):
    s = scraper(b["site"]) if scraper else {}
    ent, confiance, methode = trouver_entreprise(b, s.get("siren_site", ""))
    ligne = {
        "companyName": b["nom"], "companyDomain": s.get("domaine", ""), "website": b["site"],
        "firstName": "", "lastName": "", "jobTitle": "",
        "email": s.get("email_principal", ""), "emailType": "générique" if s.get("email_principal") else "",
        "phone": s.get("telephone", ""), "companyLinkedinUrl": s.get("linkedin_entreprise", ""),
        "linkedinUrl": "", "address": b["adresse"], "postalCode": b["code_postal"], "city": b["ville"],
        "etoiles": b["etoiles"], "chambres": b["chambres"], "siren": "", "legalName": "",
        "effectif": "", "groupe": "", "chaine_ou_plateforme": s.get("site_tiers", ""),
        "confiance": confiance, "methode": methode, "a_verifier": "", "statut_site": s.get("statut_scrap", ""),
    }
    if ent:
        ligne.update({"siren": ent.get("siren", ""), "legalName": ent.get("nom_raison_sociale") or ent.get("nom_complet", ""),
                      "effectif": ent.get("tranche_effectif_salarie") or ""})
        d = dirigeant_physique(ent)
        if not d:
            morale = next((x for x in dirigeants_utiles(ent) if x.get("type_dirigeant") == "personne morale"), None)
            if morale:
                ligne["groupe"] = morale.get("denomination", "")
                h = api({"q": morale.get("siren", ""), "per_page": 1}) if morale.get("siren") else []
                d = dirigeant_physique(h[0]) if h else None
                if d:
                    ligne["methode"] += " ; dirigeant de la holding"
        if d:
            prenom = (d.get("prenoms") or "").split(" ")[0]
            nom = (d.get("nom") or "").split("(")[0].strip()
            ligne.update({"firstName": prenom.title(), "lastName": nom.title(),
                          "jobTitle": d.get("qualite", "")})
    probs = []
    if ligne["confiance"] in ("faible", ""):
        probs.append("entreprise")
    if not ligne["firstName"]:
        probs.append("décideur")
    if ligne["chaine_ou_plateforme"] or ligne["groupe"]:
        probs.append("chaîne ou groupe : décision au siège ?")
    ligne["a_verifier"] = " ; ".join(probs)
    return ligne


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sortie")
    ap.add_argument("--atout-france", action="store_true")
    ap.add_argument("--type", default="")
    ap.add_argument("--etoiles", default="")
    ap.add_argument("--dep", default="")
    ap.add_argument("--chambres-min", type=int, default=0)
    ap.add_argument("--chambres-max", type=int, default=0)
    ap.add_argument("--entree")
    ap.add_argument("--col-nom", default="nom")
    ap.add_argument("--col-cp", default="code_postal")
    ap.add_argument("--col-site", default="site")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    if not scraper:
        print("Attention : skill website-scraper introuvable, pas de visite des sites.")
    boites = charger_atout(a) if a.atout_france else charger_csv(a)
    if a.limit:
        boites = boites[: a.limit]
    with ThreadPoolExecutor(a.workers) as ex:
        lignes = list(ex.map(enrichir, boites))

    with open(a.sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)

    t = len(lignes)
    def c(k):
        return sum(1 for l in lignes if l[k])
    print(f"{t} boîtes")
    print(f"  domaine {c('companyDomain')} · email {c('email')} · téléphone {c('phone')} · LinkedIn entreprise {c('companyLinkedinUrl')}")
    print(f"  SIREN {c('siren')} · décideur {c('firstName')} · chaîne ou groupe {sum(1 for l in lignes if l['groupe'] or l['chaine_ou_plateforme'])}")
    print(f"  LinkedIn du décideur : 0 (pas trouvable gratuitement, à compléter)")
    print(f"→ {a.sortie}")


if __name__ == "__main__":
    main()
