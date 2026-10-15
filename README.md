# Skills de prospection pour Claude

Deux skills pour construire une liste de prospects gratuite avec Claude : d'abord la liste des
boîtes, ensuite les bonnes personnes.

| Skill | Ce qu'il fait |
|---|---|
| `website-scraper` | Visite le site de chaque boîte (accueil, contact, mentions légales) et ramène domaine, email, téléphone, LinkedIn de l'entreprise, SIREN |
| `csv-outbound-builder` | Filtre le fichier Atout France des hébergements classés (ou votre propre liste), appelle le scraper, trouve le dirigeant via l'API Recherche d'entreprises (data.gouv) et sort un CSV prêt pour lemlist |

Exemple réel (15/10/2026) : 25 hôtels de 1 à 4 étoiles du Jura et du Doubs, 15 secondes,
dirigeant trouvé pour 16, email générique pour 11.

Ce que ça ne trouve pas : le LinkedIn et l'email perso du dirigeant. Gratuit jusqu'à son nom,
pas plus loin.

## Installer

Avec Claude Code :

```bash
git clone https://github.com/Lyr0n/growth-will-outbound.git
mkdir -p ~/.claude/skills
cp -R growth-will-outbound/website-scraper growth-will-outbound/csv-outbound-builder ~/.claude/skills/
```

Puis demandez à Claude : « fais-moi un CSV de prospection des hôtels de 1 à 4 étoiles du Jura ».

Sans Claude, les scripts tournent seuls (Python 3.9+, aucune dépendance) :

```bash
python3 csv-outbound-builder/builder.py hotels.csv --atout-france \
  --type "HÔTEL DE TOURISME" --etoiles 1,2,3,4 --dep 39,25 --limit 25
```

## Bon usage

- Testez sur 25 lignes, relisez, puis lancez le reste.
- Les noms de dirigeants viennent d'un registre public, mais restent des données personnelles :
  base légale (intérêt légitime B2B), lien de désinscription dans chaque message, pas de
  publication du fichier.
- Pas plus de 4 pages par site, et on ne contourne pas un site qui refuse les robots.

## Sources

- Atout France, hébergements touristiques classés (data.gouv, export quotidien)
- API Recherche d'entreprises : https://recherche-entreprises.api.gouv.fr

Fait par GrowthWill.
