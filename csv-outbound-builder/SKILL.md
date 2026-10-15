---
name: csv-outbound-builder
description: "Construit un fichier de prospection prêt à importer (lemlist, Clay, tableur) depuis le fichier Atout France des hébergements classés ou n'importe quelle liste de boîtes : companyName, companyDomain, email, téléphone, LinkedIn de l'entreprise, SIREN, décideur (prénom, nom, fonction) via data.gouv, chaîne ou groupe. Gratuit. Déclencheurs : « fais-moi un CSV de prospection », « liste d'hôtels / campings à prospecter », « Atout France », « CSV outbound », « prépare le fichier lemlist »."
---

# CSV outbound builder

D'abord la liste des boîtes, ensuite les bonnes personnes. Trois temps, tous gratuits :

1. **La liste** : le fichier Atout France (hôtels, campings, résidences, villages de vacances,
   mis à jour chaque jour), filtré. Ou un CSV qui a un nom, un code postal et un site.
2. **Le site** : skill `website-scraper` (domaine, email, téléphone, LinkedIn, SIREN).
3. **Le décideur** : API Recherche d'entreprises (data.gouv). Par le SIREN du site (confiance
   haute), sinon par le nom et le code postal (moyenne). Boîte tenue par une holding : on
   remonte au dirigeant de la holding.

## Avant de lancer

Afficher les filtres et les faire valider : type, étoiles, départements, taille. Exemple :
« hôtels de 1 à 4 étoiles (les 5 étoiles sont déjà équipés), Jura et Doubs, 25 lignes de test ».

## Lancer

```bash
# Atout France
python3 ~/.claude/skills/csv-outbound-builder/builder.py sortie.csv --atout-france \
  --type "HÔTEL DE TOURISME" --etoiles 1,2,3,4 --dep 39,25 --limit 25

# Une liste déjà prête
python3 ~/.claude/skills/csv-outbound-builder/builder.py sortie.csv --entree liste.csv \
  --col-nom nom --col-cp code_postal --col-site site
```

Types Atout France : `HÔTEL DE TOURISME`, `CAMPING`, `RÉSIDENCE DE TOURISME`,
`VILLAGE DE VACANCES`, `PARC RÉSIDENTIEL DE LOISIRS`, `AUBERGE COLLECTIVE`. Pour les campings,
`--chambres-min/max` filtre sur le nombre d'emplacements.

`--limit 25` par défaut : on teste, on relit, puis on lance le reste (`--limit 0`).

## Colonnes (noms lemlist)

`companyName`, `companyDomain`, `website`, `firstName`, `lastName`, `jobTitle`, `email`,
`emailType`, `phone`, `companyLinkedinUrl`, `linkedinUrl`, `address`, `postalCode`, `city`,
`etoiles`, `chambres`, `siren`, `legalName`, `effectif`, `groupe`, `chaine_ou_plateforme`,
`confiance`, `methode`, `a_verifier`, `statut_site`.

## Ce que ça trouve, ce que ça ne trouve pas

Test du 15/10/2026, 25 hôtels de 1 à 4 étoiles du Jura et du Doubs, 15 secondes :
domaine 25, décideur 16, téléphone 16, email 11 (génériques), LinkedIn de l'entreprise 3.

- **`linkedinUrl` reste vide.** Le LinkedIn et l'email perso du décideur ne se trouvent pas
  gratuitement. À compléter avec un outil d'enrichissement, ou à la main sur les meilleurs.
- `email` est générique (`contact@`, `accueil@`, une messagerie perso du patron parfois).
- Chaînes et franchises (`chaine_ou_plateforme`, `groupe`) : la décision se prend souvent au
  siège. Les sortir ou leur écrire un autre message.
- Le dirigeant légal n'est pas toujours celui qui décide (directeur salarié). `a_verifier` le dit.

## Règles

- Rien ne part dans lemlist sans relecture : on importe un CSV relu, jamais le brut.
- Données personnelles : le nom du dirigeant vient d'un registre public. Le fichier reste
  interne ; sur un visuel ou un post, noms et emails floutés.
- Dédoublonner avec ce qui est déjà dans votre CRM ou vos campagnes avant d'importer.
