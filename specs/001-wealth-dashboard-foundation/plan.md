# Implementation Plan: Socle de suivi de patrimoine et tableau de bord

**Branch**: `001-wealth-dashboard-foundation` | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-wealth-dashboard-foundation/spec.md`

## Summary

Premier lot de Finance : une application web auto-hébergée, mono-utilisateur, qui permet de déclarer
des comptes (PEE, PEA, CTO, assurance-vie, Livret A), d'y saisir ou importer par CSV des opérations
sur des actifs (actions/ETF, fonds, FCPE, SCPI, fonds en euros), de les valoriser avec des cours
récupérés ou saisis, et de les consulter sur un tableau de bord (patrimoine hors dettes, courbe,
répartition, liste des comptes).

Approche technique (détails dans [research.md](research.md)) :

- **Journal versionné en ajout seul** : les opérations ne sont jamais modifiées ni supprimées ; une
  modification ou une annulation ajoute une nouvelle version. Tout chiffre affiché est recalculé
  depuis ce journal et les prix.
- **Base SQLite chiffrée (SQLCipher)** dont la clé vient du mot de passe : un oubli rend les données
  illisibles (clarification 1). Les montants sont stockés en texte décimal et calculés en `Decimal`.
- **Moteur de valorisation en fonctions pures**, testé sur des scénarios chiffrés (test d'abord).
- **Importeur CSV générique** avec mapping de colonnes, aperçu, création d'actifs inconnus après
  confirmation et dédoublonnage par empreinte de ligne.
- **Fournisseurs de prix interchangeables** : taux de change BCE, cours via Yahoo Finance (non
  officiel), recherche de ticker via OpenFIGI, et saisie manuelle toujours disponible.
- **Une image Docker** qui sert l'API FastAPI et le frontend React compilé, avec un seul processus.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x avec Node 22 LTS (frontend, build uniquement)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, `sqlcipher3-wheels`, `httpx`, `yfinance`, `charset-normalizer` (détection d'encodage CSV) ; React 18, Vite, TanStack Query, React Router, Recharts, Tailwind CSS

**Storage**: SQLite chiffré par SQLCipher, un fichier dans un volume (`/data`). PostgreSQL n'est pas pris en charge dans ce lot (voir Complexity Tracking).

**Testing**: pytest (+ `hypothesis` pour les invariants du journal), Vitest et Testing Library côté interface, Playwright pour le parcours de bout en bout du quickstart

**Target Platform**: Linux (conteneur Docker, amd64 et arm64) ; navigateurs récents sur ordinateur ; téléphone en consultation seulement (FR-026)

**Project Type**: Application web (backend + frontend)

**Performance Goals**: tableau de bord en moins de 3 s avec 10 ans d'historique et 5 000 opérations (SC-004) ; import de 500 lignes en moins de 1 min (SC-003)

**Constraints**: calculs en `Decimal` exact (jamais de flottant) ; un seul processus serveur (la clé de la base déverrouillée vit en mémoire) ; aucune donnée personnelle ni montant ne sort de la machine ; utilisable sans accès réseau

**Scale/Scope**: un utilisateur, quelques dizaines de comptes et d'actifs, jusqu'à quelques dizaines de milliers d'opérations ; 7 écrans (connexion, tableau de bord, comptes, détail de compte, actifs et prix, import, réglages/export)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Verdict | Comment le plan le respecte |
|---|---|---|
| I. Données locales d'abord | **Réussi** (constitution v1.1.0) | Pas de télémétrie ni de compte en ligne ; données chiffrées au repos ; authentification locale. Les récupérations de prix envoient des identifiants d'actifs (ticker, ISIN), jamais de quantités, montants ni noms de comptes. Ces identifiants révèlent néanmoins ce que l'utilisateur détient : la récupération automatique est désactivée par défaut jusqu'à un choix explicite, coupable à tout moment, les services contactés sont listés dans les réglages et la recherche de ticker est lancée par l'utilisateur. Le principe I amendé en v1.1.0 autorise ces identifiants et ces devises, et eux seuls. |
| II. Journal immuable | **Réussi** | Les lignes d'opérations ne reçoivent jamais d'`UPDATE` ni de `DELETE` : modifier ou annuler insère une nouvelle version. L'état courant est la dernière version non annulée. Compatible avec la correction directe décidée à la clarification 3. Aucun total n'est stocké. |
| III. Exactitude monétaire | **Réussi** | Types décimaux de bout en bout (colonnes texte canoniques, `Decimal` en Python, chaînes dans l'API). Montants avec leur devise ; conversion à la date de valorisation ; arrondi uniquement à l'affichage. Un test interdit tout `float` dans le domaine. |
| IV. Ingestion sans scraping | **Réussi** | Saisie, CSV et API publiques de prix uniquement ; aucun identifiant d'établissement stocké. L'importeur reçoit un fichier et renvoie des lignes normalisées sans écrire en base. Imports idempotents par empreinte. |
| V. Tests chiffrés d'abord | **Réussi** | Chaque calcul du domaine (prix de revient, valorisation, SCPI, Livret A, plafond PEA, séries, répartition) a des cas chiffrés écrits avant le code (voir tests dans la structure). |
| VI. Simplicité et déploiement trivial | **Réussi, avec un écart justifié** | Une image, un volume, `docker compose up`. SQLite par défaut ; PostgreSQL reporté (le chiffrement dérivé du mot de passe ne s'applique qu'à SQLite). Pas de file de tâches, pas de cache externe. |
| VII. Expérience utilisateur et accessibilité | **Réussi, une fois les tâches UX livrées** (constitution v1.2.0) | Parcours issus de la [découverte UX](../../docs/ux-discovery/2026-10-24-finance-discovery.md). Quatre états par écran de données (FR-036), WCAG 2.2 AA avec audit automatisé et parcours clavier (FR-034, SC-010), confirmations des actions lourdes (FR-035), formats `fr-FR`, jeu unique de composants et de jetons. Détail par écran dans [ux.md](ux.md). Les tâches T142 à T152 portent ces exigences ; l'UI déjà écrite (T061 à T065, US2) est à reprendre. |

**Contraintes techniques et légales** : stack conforme à la constitution ; interface JSON documentée par OpenAPI ; moteur de performance en fonctions pures ; identité visuelle propre ; avertissement « indicatif » présent dans l'interface ; licence à choisir avant publication (point ouvert, hors de ce lot de code).

**Résultat de la porte** : aucun blocage, sous réserve de livrer les tâches UX (principe VII). Un écart (PostgreSQL) est justifié dans Complexity Tracking.

**Re-vérification après conception (Phase 1)** : conforme. Le modèle de données ([data-model.md](data-model.md)) n'introduit aucun champ dérivé persistant, les contrats ([contracts/openapi.yaml](contracts/openapi.yaml)) échangent les montants en chaînes décimales, et le quickstart ([quickstart.md](quickstart.md)) vérifie l'absence de sortie de données personnelles.

## Design UX

Source : [découverte UX](../../docs/ux-discovery/2026-10-24-finance-discovery.md) (persona « épargnant salarié multi-enveloppes », débutant technique ; job principal J1 : consolider son patrimoine ; North Star : temps jusqu'à un total jugé juste). Le détail écran par écran est dans [ux.md](ux.md).

- **Design system et jetons** : `frontend/src/styles/theme.css` et `components/fields.tsx` existants ; aucun second jeu de composants. Nouveaux composants transverses : `LoadingState`, `ErrorState`, `ConfirmDialog`, `ChartSummary`, `LiveAnnouncer`.
- **Navigation et mise en page** : latérale sur ordinateur ; sur téléphone, barre basse en consultation seulement, sans défilement horizontal dès 375 px (FR-026).
- **Écrans** : connexion, tableau de bord, comptes, détail de compte, actifs et prix, import, réglages et export.
- **Accessibilité** : WCAG 2.2 AA ; vérifiée par `jest-axe` en tests de composants et par un parcours clavier Playwright (SC-010).
- **Installation** : `docker compose up` comme base, plus une procédure illustrée sans ligne de commande dans le README ; SC-006 mesuré avec un testeur débutant.

## Project Structure

### Documentation (this feature)

```text
specs/001-wealth-dashboard-foundation/
├── plan.md              # Ce fichier (sortie de /speckit-plan)
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── ux.md                # Phase 1 : écrans, états, parcours clavier, libellés
├── contracts/           # Phase 1
│   ├── openapi.yaml     # Contrat de l'API
│   └── export-format.md # Format du fichier d'export et de restauration
├── checklists/
│   ├── requirements.md
│   └── ux.md
└── tasks.md             # Phase 2 (/speckit-tasks, non créé ici)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── alembic.ini
├── migrations/
├── src/finance/
│   ├── main.py                 # création de l'application, montage du frontend compilé
│   ├── config.py               # chemin des données, options de prix
│   ├── auth/                   # déverrouillage, sessions, limitation des essais
│   ├── db/                     # moteur SQLCipher, types décimaux, modèles, versions d'opérations
│   ├── domain/                 # fonctions pures : argent, positions, valorisation, séries,
│   │                           #   répartition, Livret A, SCPI, plafond PEA
│   ├── services/               # comptes, actifs, opérations, prix, imports, export
│   ├── importers/              # interface d'importeur + importeur CSV générique
│   ├── prices/                 # interface de fournisseur + BCE, Yahoo, OpenFIGI
│   └── api/                    # routeurs et schémas
└── tests/
    ├── unit/                   # domaine : cas chiffrés, invariants
    ├── integration/            # base chiffrée, import de bout en bout, export/restauration
    ├── contract/               # conformité de l'API à openapi.yaml
    └── fixtures/               # CSV anonymisés, scénarios de référence

frontend/
├── package.json
├── src/
│   ├── api/                    # client généré depuis openapi.yaml
│   ├── components/             # tableau de bord, graphiques, tableaux, formulaires
│   ├── pages/                  # Login, Dashboard, Accounts, AccountDetail, Instruments,
│   │                           #   Import, Settings
│   └── styles/                 # thème et identité visuelle propres au projet
└── tests/                      # composants (Vitest) et parcours (Playwright)

Dockerfile                      # build du frontend puis image d'exécution Python
compose.yaml                    # service unique + volume de données
docs/
└── design-brief.md
```

**Structure Decision**: application web à deux projets (`backend/` et `frontend/`), conformément à la
stack figée dans la constitution. Le frontend est compilé dans l'image et servi par le backend, ce
qui garde un seul service à déployer. Le dossier `domain/` ne dépend ni de la base ni du réseau, ce
qui le rend testable par des cas chiffrés.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| PostgreSQL non pris en charge dans ce lot (la constitution le prévoit « en option ») | L'exigence « données illisibles sans le mot de passe » (FR-028) repose sur le chiffrement de fichier SQLCipher, qui n'existe que pour SQLite | Chiffrer les champs au niveau applicatif pour supporter PostgreSQL empêcherait les requêtes et agrégations sur les montants et doublerait la surface de code ; l'option reste ouverte pour un lot ultérieur |
| Dépendance à Yahoo Finance via une bibliothèque non officielle | Seule source gratuite couvrant actions, ETF et beaucoup de fonds européens | Une source officielle gratuite n'existe pas pour ces données ; l'interface de fournisseur et la saisie manuelle limitent le risque de rupture |
