# Finance: brief de conception (point de départ pour Spec Kit)

Application web **auto-hébergée et open source** de suivi de patrimoine, inspirée des fonctionnalités publiques de Finary. Les données restent chez l'utilisateur. Aucun code ni asset de Finary n'est repris.

## Périmètre du MVP

**Enveloppes (comptes):** PEE, PEA, compte-titres ordinaire (CTO), assurance-vie, Livret A.
**Classes d'actifs:** SCPI, actions / ETF, fonds d'investissement (dont FCPE et fonds en euros).

**Hors périmètre pour l'instant:** multi-utilisateurs, application mobile, connecteurs bancaires automatiques, scraping, communauté sociale, conseil, exécution d'ordres.

## Fonctionnalités par phase

0. **Socle:** modèle de données, multi-devises (taux quotidiens), authentification locale, chiffrement au repos.
1. **MVP:** saisie manuelle des actifs, import CSV/OFX, cours automatiques (actions, ETF, fonds), dashboard (patrimoine net, évolution, répartition par classe d'actifs).
2. **Analyse:** performance (XIRR, plus-values latentes), diversification (secteur, zone, devise), dividendes, frais (courtage, TER).
3. **Au-delà du portefeuille:** budget et cashflow, objectifs et projections, rapport fiscal indicatif.
4. **Optionnel:** connecteurs open banking, partage en lecture seule, alertes, mobile.

## Architecture

- **Backend:** Python, FastAPI.
- **Frontend:** React, Vite.
- **Base de données:** SQLite par défaut, PostgreSQL en option.
- **Déploiement:** une image Docker qui sert l'API et le frontend compilé (`docker compose up`).

Quatre briques:

1. **Domaine et stockage:** modèle de données et règles de cohérence. Montants en `Decimal`, jamais en flottants.
2. **Importeurs (plugins):** reçoivent un fichier, renvoient des transactions et valorisations au format commun, ne touchent jamais la base. Un établissement = un fichier. Pas de scraping.
3. **Fournisseurs de cours:** interface unique « prix de cet instrument à cette date », une implémentation par source (marché, valeur liquidative des fonds, saisie manuelle pour les SCPI). Cache local, l'application reste utilisable si une source tombe.
4. **Moteur de performance:** fonctions pures (patrimoine net, XIRR, allocation, dividendes), testées sur des cas chiffrés.

**Principe directeur:** le journal de transactions est la source de vérité. Le patrimoine à une date se recalcule depuis le journal et les cours, sans valeur stockée en dur.

## Modèle de données

Compte (enveloppe) → positions → instruments.

| Entité | Rôle |
|---|---|
| Account | Enveloppe: type, établissement, devise, date d'ouverture. Configuration propre au type (plafond PEA, blocage PEE). |
| Instrument | Action, ETF, fonds, FCPE, SCPI, fonds en euros, cash. ISIN quand il existe, source des prix. |
| Transaction | Journal immuable: achat, vente, versement, retrait, dividende, distribution, intérêt, frais, abondement. Date, quantité, prix, frais, trace de l'import. |
| Price | Cours ou valeur liquidative à une date, avec source et indicateur « saisi à la main ». |
| Balance | Solde déclaré à une date pour les instruments sans cours (fonds en euros, Livret A). Sert aussi de point de contrôle. |
| Rate | Taux réglementaires datés (Livret A), modifiables. |
| Import | Une trace par fichier importé (importeur, empreinte). Imports rejouables sans doublons. |

### Cas particuliers

- **PEE:** l'abondement entre dans le patrimoine mais pas dans la performance (c'est un apport). La date de déblocage est portée par la ligne, pour afficher « disponible / bloqué ».
- **Fonds en euros (assurance-vie):** pas de cours. Valeur = dernier solde déclaré + flux depuis. Le taux servi en fin d'année est une transaction d'intérêt.
- **SCPI:** deux prix. Prix de souscription (frais d'entrée inclus, environ 10 %) pour le prix de revient, prix de retrait pour la valorisation. La moins-value apparente du départ est visible sans fausser le rendement. Distributions trimestrielles = transactions.
- **Livret A:** solde issu des versements et retraits. Intérêts estimés par quinzaines avec la table des taux, remplacés par la ligne réelle quand elle est importée ou saisie.
- **PEA / CTO:** prix de revient unitaire = moyenne pondérée, frais inclus. Le plafond de versements du PEA se calcule à partir des dépôts.

### Règles transverses

- Montants en décimaux, avec leur devise d'origine, convertis à la date de valorisation.
- Un import ne crée que ce qu'il ne connaît pas déjà (dédoublonnage par identifiant externe ou empreinte).
- Le patrimoine historique se recalcule toujours depuis le journal et les cours.

## Interface utilisateur

L'interface s'inspire de l'organisation et des parcours de Finary: vue d'ensemble du patrimoine en page d'accueil (patrimoine net, courbe d'évolution, répartition par classe d'actifs), liste des comptes avec leur valeur et leur performance, page de détail par compte et par position, navigation latérale par grandes familles (patrimoine, performance, dividendes, budget).

Limites: on reprend les principes de mise en page et d'ergonomie, pas les éléments protégés. Identité visuelle propre (nom, logo, palette, icônes, typographie, textes), aucun asset ni code de Finary. Le détail des écrans sera fixé à partir des pages publiques du produit (site, captures de présentation, parcours que l'on peut observer avec son propre compte), puis décrit dans la spécification.

## Pour la suite avec Spec Kit

Ordre suggéré: `/speckit-constitution` (principes: décimaux, journal immuable, pas de scraping, données locales, tests chiffrés), puis `/speckit-specify` découpé en un premier lot (socle + modèle + import CSV générique + dashboard patrimoine net), `/speckit-plan`, `/speckit-tasks`.
