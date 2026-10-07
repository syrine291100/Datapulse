# DataPulse

Application d’analyse de ventes avec pipeline d’import CSV, contrôle de qualité, stockage SQL et tableau de bord interactif.

**Python · pandas · FastAPI · SQLAlchemy · PostgreSQL · Streamlit · Plotly · Docker**

## Fonctionnalités

- Prévisualisation des données et rapport d’anomalies par ligne.
- Validation des dates, champs requis, quantités, prix et identifiants.
- Import atomique : toute anomalie bloque le fichier entier.
- Protection contre les doubles imports, y compris lors d’un conflit en base.
- Calcul monétaire en Decimal côté API, stockage en Numeric(12, 2).
- Filtres par période et catégorie, chiffre d’affaires, volumes et trois graphiques.
- Historique des imports et traçabilité des ventes vers leur lot.
- CSV fictif de 180 ventes pour démarrer et fichier invalide pour illustrer les contrôles.
- Tests automatisés et GitHub Actions.

## Démarrer sous Windows

Prérequis : Python 3.12. Extraire le ZIP et ouvrir un terminal **à la racine de DataPulse**.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copier la clé générée dans `IMPORT_API_KEY` dans `.env`. Conserver les deux autres valeurs pour SQLite en local. Le même fichier `.env` est lu par l’API et le dashboard.

**Terminal 1 — API, depuis la racine :**

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — dashboard, depuis la même racine :**

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Ouvrir http://localhost:8501. Choisir **Importer des ventes**, charger `data/sales_demo.csv`, puis cliquer sur **Confirmer l’import**. Revenir au tableau de bord. La base SQLite est créée automatiquement au démarrage de l’API.

Sur Linux/macOS, remplacer `py -3.12` par `python3.12`, `.\.venv\Scripts\python.exe` par `.venv/bin/python` et `Copy-Item` par `cp`.

Documentation API : http://localhost:8000/docs. Les imports nécessitent le header `X-API-Key` ; les consultations sont publiques.

## Format CSV

UTF-8, séparateur virgule, en-tête exact :

```csv
sale_id,date,product,category,quantity,unit_price
VENTE-001,2026-01-01,Café,Boissons,2,3.50
```

- Identifiants uniques parmi toutes les ventes déjà importées.
- Dates ISO `YYYY-MM-DD`.
- Quantités entières positives, maximum 100 000.
- Prix unitaires positifs en EUR, maximum 1 000 000, deux décimales maximum.
- Textes requis, maximum 120 caractères.
- Maximum 2 Mo et 10 000 lignes par fichier.

Une ligne représente une vente de produit. Aucun identifiant de commande ou de client n’est disponible : les indicateurs ne doivent pas être interprétés comme un nombre de commandes ou un panier moyen.

## Architecture

Le dashboard Streamlit appelle l’API depuis son serveur. L’API valide le CSV puis enregistre un lot et ses ventes dans une transaction SQL. Le dashboard transforme les ventes avec pandas pour les agrégations et Plotly pour les graphiques. Les montants affichés dans le KPI total sont additionnés en Decimal ; les graphiques utilisent des flottants.

```text
backend/pipeline.py    Lecture et validation du CSV
backend/database.py    Modèles SQLAlchemy et connexion
backend/main.py        Prévisualisation, import et consultations
frontend/app.py        Dashboard et formulaires Streamlit
data/                 Jeux de données fictifs
tests/                Tests API et validation
scripts/              Vérification du dashboard
```

## Tester

Depuis la racine :

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/verify_dashboard.py
```

Les tests utilisent une base temporaire isolée. Le dernier script démarre une API temporaire sur le port 8091 et utilise le framework de test Streamlit : état vide, import, indicateurs, filtres, historique et écran d’import.

## Docker et PostgreSQL

Copier `.env.example` vers `.env`, définir la clé d’import, puis :

```sh
docker compose up --build
```

Dashboard : http://localhost:8501. API : http://localhost:8000. PostgreSQL reste accessible uniquement aux services Docker et conserve ses données dans un volume. Le mot de passe fourni dans Compose est exclusivement destiné au développement local.

## Déploiement à préparer

Cette version est prête pour les essais locaux ; aucune démo publique n’est encore configurée.

Pour héberger l’application : base PostgreSQL chez Neon, API Python chez Render et dashboard sur un hébergeur Streamlit. Définir `DATABASE_URL` et `IMPORT_API_KEY` pour l’API, `API_URL` et la même clé pour le dashboard. Les secrets restent côté serveur et ne doivent jamais être commités.

Le dashboard est une démonstration **partagée**, sans comptes utilisateurs : tous les visiteurs accèdent aux mêmes ventes. N’utiliser que des données fictives. Avant une utilisation métier, ajouter authentification et isolation par organisation, limites d’usage, pagination, migrations Alembic et journal d’audit. Cette V1 crée le schéma au démarrage avec SQLAlchemy et ne gère pas les évolutions de schéma.

## Vérification de la V1

- 15 tests API et validation réussis sur Python 3.12 / SQLite.
- Contrôle Ruff réussi.
- Vérification Streamlit réussie avec le CSV de démonstration.
- PostgreSQL / Docker et le déploiement public restent à vérifier dans leurs environnements respectifs.

Les versions directes sont figées dans `requirements.txt` et `requirements-dev.txt`. `requirements-dev.lock.txt` documente l’ensemble de l’environnement Linux utilisé pour la vérification ; les instructions Windows utilisent les dépendances directes.
