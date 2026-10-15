# Skills GrowthWill pour Claude

Les skills de prospection qu'on utilise chez GrowthWill et qu'on a choisi de rendre publics.
Tous préfixés `gw-`.

## Catalogue

| Skill | Ce qu'il fait | Gratuit jusqu'à |
|---|---|---|
| `gw-website-scraper` | Visite le site de chaque boîte (accueil, contact, mentions légales) et ramène domaine, email, téléphone, LinkedIn de l'entreprise, SIREN | l'email générique (`contact@`) |
| `gw-csv-outbound-builder` | Filtre le fichier Atout France des hébergements classés (ou votre liste), appelle `gw-website-scraper`, trouve le dirigeant via l'API Recherche d'entreprises (data.gouv), sort un CSV prêt pour lemlist | le nom du dirigeant |

Exemple réel (15/10/2026) : 25 hôtels de 1 à 4 étoiles du Jura et du Doubs, 15 secondes,
dirigeant trouvé pour 16, email générique pour 11. Le LinkedIn et l'email perso du dirigeant ne
se trouvent pas gratuitement.

## Installer

Avec Claude Code :

```bash
git clone https://github.com/Lyr0n/growth-will-outbound.git
mkdir -p ~/.claude/skills
cp -R growth-will-outbound/gw-* ~/.claude/skills/
```

Puis demandez à Claude : « fais-moi un CSV de prospection des hôtels de 1 à 4 étoiles du Jura ».

Sans Claude, les scripts tournent seuls (Python 3.9+, aucune dépendance) :

```bash
python3 gw-csv-outbound-builder/builder.py hotels.csv --atout-france \
  --type "HÔTEL DE TOURISME" --etoiles 1,2,3,4 --dep 39,25 --limit 25
```

## Bon usage

- Testez sur 25 lignes, relisez, puis lancez le reste.
- Les noms de dirigeants viennent d'un registre public, mais restent des données personnelles :
  base légale (intérêt légitime B2B), lien de désinscription dans chaque message, pas de
  publication du fichier.
- Pas plus de 4 pages par site, et on ne contourne pas un site qui refuse les robots.

## Ajouter un skill à ce dépôt

Un skill entre ici seulement s'il coche tout :

1. Nom en `gw-<ce-qu-il-fait>`, un dossier par skill, un `SKILL.md` avec `name` et `description`.
2. Aucune donnée client, aucun nom de client, aucun process interne (registre, agents, crédits).
3. Aucune clé ni secret. Un service payant se branche par variable d'environnement, documentée.
4. Testé sur de vraies données, avec le résultat chiffré dans son `SKILL.md`, limites comprises.
5. Python de la bibliothèque standard de préférence. Toute dépendance est listée.
6. Une ligne de plus dans le catalogue ci-dessus.

## Sources

- Atout France, hébergements touristiques classés (data.gouv, export quotidien)
- API Recherche d'entreprises : https://recherche-entreprises.api.gouv.fr

Fait par GrowthWill.
