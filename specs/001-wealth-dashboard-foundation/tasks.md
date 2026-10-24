---

description: "Liste de tâches du lot 001 : socle de suivi de patrimoine et tableau de bord"
---

# Tasks: Socle de suivi de patrimoine et tableau de bord

**Input**: Design documents from `/specs/001-wealth-dashboard-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, contracts/export-format.md, quickstart.md

**Tests**: obligatoires. Le principe V de la constitution impose les tests chiffrés d'abord pour tout calcul financier, et un test par importeur. Dans chaque phase, les tests s'écrivent en premier et DOIVENT échouer avant l'implémentation.

**Organization**: les tâches sont groupées par histoire utilisateur (US1 à US5, numérotées comme dans spec.md) pour que chacune soit implémentable et testable seule.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, aucune dépendance sur une tâche non terminée)
- **[Story]** : histoire utilisateur concernée (US1 à US5)
- Chaque description contient le chemin exact des fichiers

## Path Conventions

Application web (voir plan.md) : `backend/src/finance/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`.
Règles transverses à respecter dans chaque tâche : montants, quantités, prix et taux en `Decimal` jamais en `float` (principe III) ; aucun `UPDATE` ni `DELETE` sur les tables du journal (principe II) ; aucune donnée personnelle réelle dans les fixtures (principe I).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: structure du projet, outillage et CI du code

- [x] T001 Créer l'arborescence `backend/src/finance/{auth,db,domain,services,importers,prices,api}/` et `backend/tests/{unit,integration,contract,fixtures}/` avec des `__init__.py`, conformément à plan.md
- [x] T002 Créer `backend/pyproject.toml` (Python 3.12) avec FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, `sqlcipher3-wheels==0.5.7`, `httpx`, `yfinance==1.7.0`, `charset-normalizer`, `python-multipart`, `uvicorn` ; groupe de développement `pytest`, `hypothesis`, `pytest-cov`, `ruff`, `mypy`
- [x] T003 [P] Configurer `ruff` et `mypy` (mode strict sur `finance.domain`) dans `backend/pyproject.toml`
- [x] T004 Créer le projet `frontend/` (Vite, React 18, TypeScript 5) : `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, avec React Router, TanStack Query, Recharts, `decimal.js-light`
- [x] T005 [P] Configurer Tailwind CSS 4 (plugin Vite, configuration dans `frontend/src/styles/theme.css`, pas de `tailwind.config.ts`), ESLint dans `frontend/eslint.config.js` et Prettier dans `frontend/.prettierrc`
- [x] T006 [P] Configurer Vitest et Testing Library dans `frontend/vitest.config.ts` et `frontend/tests/setup.ts`
- [x] T007 Étendre `.github/workflows/ci.yml` : job `backend` (ruff, mypy, pytest avec couverture) et job `frontend` (lint, `tsc --noEmit`, vitest, build), actions épinglées par empreinte de commit, et les ajouter à `needs` du job `ci-gate`
- [x] T008 [P] Ajouter les entrées `pip` (`/backend`) et `npm` (`/frontend`) à `.github/dependabot.yml` ; l'entrée `docker` (`/`) s'ajoute avec le `Dockerfile` en T122 (Dependabot échoue si le fichier n'existe pas)
- [x] T009 [P] Ajouter `.github/workflows/codeql.yml` (langages Python et JavaScript/TypeScript, actions épinglées par empreinte, permissions `security-events: write` limitées à ce workflow)
- [x] T010 [P] Créer `backend/src/finance/config.py` (dossier de données `FINANCE_DATA_DIR` par défaut `/data`, port, récupération de prix activable) et `.env.example` à la racine, sans aucune valeur secrète
- [x] T011 [P] Écrire en premier `backend/tests/unit/test_no_float_in_domain.py` : analyse AST de `backend/src/finance/domain/` qui échoue sur tout littéral flottant, appel à `float(` ou annotation `float`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: base de données chiffrée, modèle de données, authentification et squelette applicatif. Toute histoire en dépend, car la base ne s'ouvre qu'après déverrouillage.

**⚠️ CRITICAL**: aucune histoire utilisateur ne peut commencer avant la fin de cette phase

### Tests (à écrire d'abord, ils doivent échouer)

- [x] T012 [P] Écrire `backend/tests/unit/test_decimal_type.py` : le type décimal texte conserve `Decimal("90.199")` à l'identique, refuse un `float`, refuse la notation scientifique
- [x] T013 [P] Écrire `backend/tests/unit/test_money.py` : devise conservée avec le montant, addition de deux devises différentes refusée, arrondi au centime seulement à l'affichage
- [x] T014 [P] Écrire `backend/tests/unit/test_isin.py` : ISIN valides et invalides (clé de contrôle), 12 caractères alphanumériques
- [x] T015 [P] Écrire `backend/tests/integration/test_encrypted_db.py` : le fichier de base n'est pas lisible sans clé, un mauvais mot de passe est refusé, aucune récupération n'existe après oubli (clarification 1)
- [x] T016 [P] Écrire `backend/tests/unit/test_append_only.py` : toute tentative d'`UPDATE` ou de `DELETE` sur `transaction_version`, `price`, `declared_balance`, `rate` et `import_batch` lève une erreur
- [x] T017 [P] Écrire `backend/tests/integration/test_auth_api.py` : création du mot de passe à la première utilisation, refus d'un mot de passe de moins de 12 caractères, de plus de 128 ou présent dans la liste des mots de passe courants, accès refusé sans session, cookie `HttpOnly` et `SameSite=Strict` (et `Secure` en HTTPS), 5 échecs puis délai doublé à chaque échec jusqu'à 15 minutes, expiration après 30 minutes d'inactivité et 12 heures au plus, verrouillage après redémarrage
- [x] T018 [P] Écrire `backend/tests/contract/test_openapi_conformance.py` : pour chaque routeur monté (liste `IMPLEMENTED_TAGS` dans le test), ses chemins et méthodes sont identiques à ceux de `specs/001-wealth-dashboard-foundation/contracts/openapi.yaml` ; Foundational déclare le tag `auth`, chaque histoire ajoute ses tags (US1 : accounts, instruments, transactions, transfers, declared-balances ; US2 : dashboard ; US3 : imports ; US4 : prices, rates, settings ; US5 : data) en complétant la liste dans sa phase *(l'opération `POST /auth/change-password` du contrat est reportée à T139 via `DEFERRED_OPERATIONS`)*

### Implementation

- [x] T019 Implémenter `backend/src/finance/domain/money.py` (type montant avec devise, opérations sur `Decimal`, arrondi d'affichage documenté)
- [x] T020 [P] Implémenter `backend/src/finance/domain/enums.py` : types de compte `PEE, PEA, CTO, ASSURANCE_VIE, LIVRET_A` ; types d'actif `EQUITY, ETF, FUND, FCPE, SCPI, EURO_FUND, CASH` ; types d'opération `DEPOSIT, WITHDRAWAL, BUY, SELL, DIVIDEND, DISTRIBUTION, INTEREST, FEE, EMPLOYER_MATCH, TRANSFER_OUT, TRANSFER_IN` ; types de prix `MARKET, NAV, SUBSCRIPTION, REDEMPTION`
- [x] T021 [P] Implémenter `backend/src/finance/domain/isin.py` (contrôle de la clé)
- [x] T022 Implémenter le type `DecimalText` dans `backend/src/finance/db/types.py` (stockage en texte décimal canonique, point comme séparateur, pas de notation scientifique)
- [x] T023 Implémenter `backend/src/finance/db/engine.py` : moteur SQLAlchemy avec `creator` ouvrant `sqlcipher3` puis `PRAGMA key`, vérification du mot de passe par lecture de test ; paramètres SQLCipher 4 par défaut (dérivation PBKDF2-HMAC-SHA512, 256000 itérations) fixés explicitement, avec un test qui échoue si une valeur plus faible est appliquée
- [x] T024 Implémenter `backend/src/finance/db/models.py` avec toutes les tables de data-model.md : `account` (nom « Obligatoire, unique parmi les comptes ouverts », `closed_on` « supérieur ou égal à `opened_on` »), `instrument` (ISIN « 12 caractères alphanumériques avec clé de contrôle valide ; unique s'il est présent »), `transaction`, `transaction_version`, `transfer_group`, `price` (valeur « Strictement positif »), `declared_balance` (montant « Positif ou nul »), `rate`, `import_batch`, `import_mapping` (nom « unique »), `setting` ; identifiants UUID texte
- [x] T025 Implémenter `backend/src/finance/db/append_only.py` : écouteurs SQLAlchemy qui interdisent `UPDATE` et `DELETE` sur les tables du journal (en plus des déclencheurs SQLite de la migration, T026), branchés dans `backend/src/finance/db/session.py` ; tables protégées : `transaction`, `transaction_version`, `transfer_group`, `price`, `declared_balance`, `rate`, `import_batch`
- [x] T026 Créer la configuration Alembic (`backend/alembic.ini`, `backend/migrations/env.py` compatible SQLCipher), l'assistant `backend/src/finance/db/migrate.py` et la migration `backend/migrations/versions/0001_initial_schema.py` (tables et déclencheurs d'ajout seul)
- [x] T027 Implémenter `backend/src/finance/auth/metadata.py` : petit fichier de métadonnées hors de la base chiffrée indiquant si l'instance est initialisée
- [x] T028 Implémenter `backend/src/finance/auth/service.py` : création du mot de passe (12 à 128 caractères, hors liste des mots de passe courants), déverrouillage (l'ouverture correcte de la base prouve le mot de passe), verrouillage ; aucun mécanisme de récupération
- [x] T029 [P] Implémenter `backend/src/finance/auth/sessions.py` (cookie de session aléatoire en mémoire, `HttpOnly`, `SameSite=Strict`, `Secure` en HTTPS, expiration après 30 minutes d'inactivité et 12 heures au plus) et `backend/src/finance/auth/ratelimit.py` (5 échecs consécutifs puis délai doublé à chaque échec jusqu'à 15 minutes)
- [x] T030 [P] Implémenter `backend/src/finance/api/deps.py` (session de base, exigence de déverrouillage), `backend/src/finance/api/errors.py` (format d'erreur commun) et `backend/src/finance/api/schemas.py` (montants échangés en chaînes décimales)
- [x] T031 Implémenter `backend/src/finance/api/routers/auth.py` : `GET /auth/status`, `POST /auth/setup`, `POST /auth/unlock`, `POST /auth/lock` conformes à `contracts/openapi.yaml`
- [x] T032 Implémenter `backend/src/finance/main.py` : fabrique d'application, montage des routeurs, service du frontend compilé, un seul processus
- [x] T033 [P] Ajouter à `backend/src/finance/main.py` des en-têtes de sécurité (CSP, `X-Content-Type-Options`, `Referrer-Policy`), un contrôle de l'en-tête `Origin` sur les requêtes qui modifient des données et une taille maximale de requête ; ajouter les tests dans `backend/tests/integration/test_security_headers.py`
- [x] T034 Ajouter un script `gen:api` dans `frontend/package.json` (via `npx openapi-typescript@7.13.0`, épinglé car son pair TypeScript est ^5) qui génère `frontend/src/api/schema.ts` depuis `specs/001-wealth-dashboard-foundation/contracts/openapi.yaml`, et écrire `frontend/src/api/client.ts` (appels avec cookies, erreurs typées)
- [x] T035 [P] Créer l'identité visuelle propre dans `frontend/src/brand.ts` (nom provisoire « Finance », textes) et `frontend/src/styles/theme.css` (palette, typographie, icônes originales, aucun élément d'un tiers)
- [x] T036 [P] Créer `frontend/src/lib/format.ts` : formatage `fr-FR` des montants et pourcentages à partir de chaînes décimales (`decimal.js-light`), sans passer par des nombres flottants pour le calcul
- [x] T037 Créer le squelette applicatif `frontend/src/main.tsx`, `frontend/src/App.tsx` (routes) et `frontend/src/components/Layout.tsx` (navigation latérale sur ordinateur, barre basse sur téléphone, sans défilement horizontal)
- [x] T038 Écrire `frontend/tests/pages/Login.test.tsx` puis implémenter `frontend/src/pages/Login.tsx` : création du mot de passe avec les règles (12 caractères minimum), l'avertissement qu'un oubli rend les données irrécupérables et l'invitation à exporter (FR-028), puis déverrouillage

**Checkpoint**: la base chiffrée s'ouvre avec le mot de passe, l'API répond, le frontend affiche la connexion

---

## Phase 3: User Story 1 - Enregistrer ses comptes et ses positions (Priority: P1) 🎯 MVP

**Goal**: créer des comptes des cinq types, des actifs, saisir, modifier et annuler des opérations, déclarer des soldes, virer entre comptes, et voir la valeur de chaque compte.

**Independent Test**: dérouler les étapes a à g de `quickstart.md` section 3 et vérifier chaque valeur au centime (SC-002).

### Tests for User Story 1 (écrire d'abord, ils doivent échouer) ⚠️

- [x] T039 [P] [US1] Écrire `backend/tests/unit/test_ledger_cash_effects.py` : `DEPOSIT, DIVIDEND, DISTRIBUTION, INTEREST, EMPLOYER_MATCH, TRANSFER_IN` ajoutent ; `WITHDRAWAL, FEE, TRANSFER_OUT` retirent ; `BUY` retire `quantity × unit_price + fees` ; `SELL` ajoute `quantity × unit_price − fees`
- [x] T040 [P] [US1] Écrire `backend/tests/unit/test_positions_and_cost_basis.py` : 10 parts à 90 € avec 1,99 € de frais donnent un prix de revient de 90,199 € et 98,01 € de liquidités sur 1 000 € versés ; moyenne pondérée de deux achats ; une vente partielle ne change pas le prix de revient unitaire restant
- [x] T041 [P] [US1] Écrire `backend/tests/unit/test_transfer_neutrality.py` : un virement de 500 € du PEA vers le Livret A laisse le patrimoine inchangé ; les deux jambes ont « le même montant, la même date et deux comptes différents » ; elles « se modifient et s'annulent ensemble »
- [x] T042 [P] [US1] Écrire `backend/tests/unit/test_transaction_versions.py` : modifier ajoute une version, annuler ajoute une version `voided`, rétablir est possible, la dernière version fait foi ; propriétés `hypothesis` (la somme des positions ne dépend pas de l'ordre de saisie)
- [x] T043 [P] [US1] Écrire `backend/tests/unit/test_transaction_rules.py` : `EMPLOYER_MATCH` « n'est autorisé que sur un compte `PEE` » ; achat ou vente sur un compte `LIVRET_A` « refusé » ; `trade_date` « supérieure ou égale à `opened_on` » ; une vente supérieure à la quantité détenue est acceptée avec un avertissement, jamais bloquée ; `quantity` « strictement positive pour `BUY`, `SELL` » *(les règles vivent dans `backend/src/finance/domain/rules.py`, fonction pure appelée par T054)*
- [x] T044 [P] [US1] Écrire `backend/tests/unit/test_pea_cap_and_pee_lock.py` : cumul des versements du PEA comparé au plafond paramétrable (défaut 150000), virements entrants inclus, retraits non déduits ; somme du PEE bloquée jusqu'à `unlock_date`, abondement exclu des apports
- [x] T045 [P] [US1] Écrire `backend/tests/unit/test_euro_fund_valuation.py` : valeur = dernier solde déclaré à la date plus flux suivants ; sans solde déclaré valeur nulle et message ; le solde déclaré le plus récent (`recorded_at`) fait foi à une même date
- [x] T046 [P] [US1] Écrire `backend/tests/contract/test_accounts_transactions_contract.py` pour `/accounts`, `/instruments`, `/transactions`, `/transfers`, `/declared-balances` selon `contracts/openapi.yaml`
- [x] T047 [P] [US1] Écrire `backend/tests/integration/test_quickstart_scenario_3.py` : étapes a à g de `quickstart.md` section 3 de bout en bout sur la base chiffrée

### Implementation for User Story 1

- [x] T048 [P] [US1] Implémenter `backend/src/finance/domain/ledger.py` : effets de trésorerie par type d'opération, positions à une date à partir des dernières versions non annulées *(avec `backend/src/finance/domain/entries.py`, `rules.py` et `transfers.py`, ajoutés pour les tests T041 à T043)*
- [x] T049 [P] [US1] Implémenter `backend/src/finance/domain/cost_basis.py` : prix de revient unitaire en moyenne pondérée frais inclus
- [x] T050 [P] [US1] Implémenter `backend/src/finance/domain/caps.py` : cumul des versements du PEA et plafond, disponibilité des sommes du PEE selon `unlock_date`
- [x] T051 [US1] Implémenter `backend/src/finance/domain/valuation.py` : valeur d'une position (dernier prix connu, à défaut prix de revient marqué « estimé »), valeur d'un compte (positions plus trésorerie), fonds en euros par solde déclaré (dépend de T048, T049)
- [x] T052 [P] [US1] Implémenter `backend/src/finance/services/accounts.py` (création, modification, clôture ; `settings` avec `deposit_cap` et `lock_years`) *(avec `services/errors.py` et `services/loaders.py`, communs aux services)*
- [x] T053 [P] [US1] Implémenter `backend/src/finance/services/instruments.py` (création, ISIN validé et unique, `price_mode` par défaut `MANUAL` pour `SCPI, FCPE, EURO_FUND, CASH`)
- [x] T054 [US1] Implémenter `backend/src/finance/services/transactions.py` : création, modification et annulation par ajout de version, application de toutes les règles de data-model.md, avertissements non bloquants, historique des versions (dépend de T048)
- [x] T055 [US1] Implémenter `backend/src/finance/services/transfers.py` : création, modification et annulation atomiques des deux jambes reliées par `transfer_group_id` (dépend de T054)
- [x] T056 [P] [US1] Implémenter `backend/src/finance/services/balances.py` (soldes déclarés)
- [x] T057 [P] [US1] Implémenter `backend/src/finance/api/routers/accounts.py` : `GET/POST /accounts`, `GET/PATCH /accounts/{accountId}` avec positions, valeur et indicateurs « estimé »
- [x] T058 [P] [US1] Implémenter `backend/src/finance/api/routers/instruments.py` : `GET/POST /instruments`, `PATCH /instruments/{instrumentId}`
- [x] T059 [US1] Implémenter `backend/src/finance/api/routers/transactions.py` : `GET/POST /transactions`, `GET/PUT/DELETE /transactions/{transactionId}` (la suppression annule, l'historique des versions est renvoyé), et `POST /transfers` *(le sérialiseur JSON est `api/serializers.py` ; les réponses sont validées contre le contrat par T046)*
- [x] T060 [P] [US1] Implémenter `backend/src/finance/api/routers/balances.py` : `POST /declared-balances` *(la route vit dans `api/routers/accounts.py` : le contrat range `/declared-balances` sous le tag `accounts`)*
- [x] T061 [P] [US1] Écrire `frontend/tests/components/TransactionForm.test.tsx` puis implémenter `frontend/src/components/TransactionForm.tsx` (champs selon le type, avertissement de vente excédentaire, abondement réservé au PEE)
- [x] T062 [P] [US1] Implémenter `frontend/src/components/TransferForm.tsx` et `frontend/src/components/ModificationHistory.tsx` (versions d'une opération) *(avec `components/BalanceForm.tsx`, `components/fields.tsx`, `lib/form-errors.ts`, `lib/decimal-input.ts`, `lib/labels.ts` et les modules `api/accounts.ts`, `api/instruments.ts`, `api/transactions.ts`, `api/keys.ts`)*
- [x] T063 [P] [US1] Implémenter `frontend/src/pages/Instruments.tsx` (création, message d'ISIN invalide)
- [x] T064 [US1] Écrire `frontend/tests/pages/Accounts.test.tsx` puis implémenter `frontend/src/pages/Accounts.tsx` (liste, création des cinq types de compte) *(routes `/comptes`, `/comptes/:accountId` et `/actifs` ajoutées à `App.tsx` et à la navigation)*
- [x] T065 [US1] Implémenter `frontend/src/pages/AccountDetail.tsx` : positions, prix de revient, liquidités, historique des opérations, barre de plafond du PEA, plafond du Livret A, sommes bloquées du PEE, déclaration de solde pour les fonds en euros et le Livret A *(inclut renommer, clôturer et rouvrir un compte, et la déclaration de solde du fonds en euros)*

**Checkpoint**: US1 fonctionne seule : le scénario a à g du quickstart passe, avec le suivi manuel complet

---

## Phase 4: User Story 2 - Consulter son patrimoine sur un tableau de bord (Priority: P1)

**Goal**: afficher le patrimoine net « hors dettes », sa courbe, sa répartition par classe d'actifs et la liste des comptes.

**Independent Test**: avec les données de l'US1, le patrimoine égale la somme des comptes, la courbe passe par les bonnes valeurs aux dates saisies et la répartition fait 100 % (`quickstart.md` section 4).

### Tests for User Story 2 (écrire d'abord) ⚠️

- [ ] T066 [P] [US2] Écrire `backend/tests/unit/test_networth.py` : somme exacte des comptes ouverts ; un compte clôturé sort du total courant mais reste dans la série passée
- [ ] T067 [P] [US2] Écrire `backend/tests/unit/test_series.py` : la valeur à chaque date est recalculée depuis le journal et les prix ; points quotidiens jusqu'à 1 an, hebdomadaires au-delà ; dernier prix connu utilisé et valeur marquée estimée
- [ ] T068 [P] [US2] Écrire `backend/tests/unit/test_allocation.py` : classes dérivées (`EQUITY, ETF` → Actions & ETF ; `FUND, FCPE` → Fonds ; `SCPI` ; `EURO_FUND` → Fonds en euros ; `CASH` → Liquidités), poids dont la somme vaut exactement 100 %
- [ ] T069 [P] [US2] Écrire `backend/tests/contract/test_dashboard_contract.py` pour `GET /dashboard/summary`, `/dashboard/series`, `/dashboard/allocation`
- [ ] T070 [P] [US2] Écrire `backend/tests/integration/test_dashboard_performance.py` : 10 ans d'historique et 5 000 opérations, réponse de la série en moins de 3 s (SC-004)

### Implementation for User Story 2

- [ ] T071 [P] [US2] Implémenter `backend/src/finance/domain/networth.py` (patrimoine net hors dettes, comptes ouverts)
- [ ] T072 [P] [US2] Implémenter `backend/src/finance/domain/allocation.py` (classes d'actifs, répartition des arrondis pour que la somme des poids fasse 100 %)
- [ ] T073 [US2] Implémenter `backend/src/finance/domain/series.py` : balayage unique des opérations et des prix triés, échantillonnage quotidien puis hebdomadaire (dépend de T051)
- [ ] T074 [US2] Implémenter `backend/src/finance/services/dashboard.py` avec un cache mémoire invalidé à chaque écriture, reconstructible à l'identique (dépend de T071, T072, T073)
- [ ] T075 [US2] Implémenter `backend/src/finance/api/routers/dashboard.py` : `GET /dashboard/summary`, `GET /dashboard/series` (période 1 mois, 1 an, depuis le début), `GET /dashboard/allocation`
- [x] T076 [P] [US2] Implémenter `frontend/src/components/NetWorthChart.tsx` (Recharts) et `frontend/src/components/AllocationChart.tsx`
- [x] T077 [P] [US2] Implémenter `frontend/src/components/AccountList.tsx` (type, établissement, valeur, pastille « estimé ») et `frontend/src/components/EmptyState.tsx` guidant vers la création d'un premier compte
- [x] T078 [US2] Écrire `frontend/tests/pages/Dashboard.test.tsx` puis implémenter `frontend/src/pages/Dashboard.tsx` : synthèse en haut avec la mention « hors dettes », courbe avec sélecteur de période, répartition, liste des comptes ; ouverture d'un compte vers `AccountDetail`
- [x] T079 [P] [US2] Écrire `frontend/tests/layout/no-horizontal-scroll.test.tsx` : le tableau de bord et la liste des comptes tiennent à 375 px de large sans défilement horizontal (FR-026)

**Checkpoint**: US1 et US2 fonctionnent ensemble : la valeur du tableau de bord correspond aux calculs de référence

---

## Phase 5: User Story 3 - Importer ses opérations depuis un fichier CSV (Priority: P2)

**Goal**: importer un CSV avec réglages, correspondance des colonnes, aperçu, actifs inconnus à confirmer, dédoublonnage et réutilisation du paramétrage.

**Independent Test**: importer un fichier d'exemple de 50 lignes, puis le réimporter sans aucun ajout (`quickstart.md` section 5).

### Tests for User Story 3 (écrire d'abord) ⚠️

- [ ] T080 [P] [US3] Créer des fichiers anonymisés dans `backend/tests/fixtures/csv/` : `courtier_a_50_lignes.csv` (séparateur point-virgule, virgule décimale, dates jour/mois/année, encodage `windows-1252`), `lignes_invalides.csv`, `doublons_meme_jour.csv`, `actifs_inconnus.csv`, `vide.csv` ; aucune donnée réelle
- [ ] T081 [P] [US3] Écrire `backend/tests/unit/test_csv_parsing.py` : détection d'encodage, séparateur, format de date et de nombre, fichier vide
- [ ] T082 [P] [US3] Écrire `backend/tests/unit/test_line_fingerprint.py` : l'empreinte combine compte, date, type, actif, quantité, montant, libellé et rang d'occurrence ; deux achats identiques du même fichier restent distincts ; un `external_id` fourni l'emporte sur l'empreinte
- [ ] T083 [P] [US3] Écrire `backend/tests/integration/test_import_idempotent.py` : 50 lignes importées puis réimportées ajoutent 0 opération ; 500 lignes en moins d'une minute et 0 doublon à la réimportation (SC-003)
- [ ] T084 [P] [US3] Écrire `backend/tests/integration/test_import_unknown_instruments.py` : créer, rattacher ou ignorer un actif inconnu, et rien n'est créé avant la validation (clarification 4)
- [ ] T085 [P] [US3] Écrire `backend/tests/integration/test_import_invalid_rows.py` : lignes invalides listées avec leur cause, rien d'écrit sans confirmation, import partiel confirmé ; fichier trop volumineux refusé avec un message
- [ ] T086 [P] [US3] Écrire `backend/tests/contract/test_imports_contract.py` pour `/import-mappings`, `/imports/preview`, `/imports/commit`

### Implementation for User Story 3

- [ ] T087 [P] [US3] Implémenter `backend/src/finance/importers/base.py` : interface d'importeur qui reçoit un fichier et renvoie des lignes normalisées, sans jamais écrire en base
- [ ] T088 [US3] Implémenter `backend/src/finance/importers/csv_generic.py` : détection d'encodage (`charset-normalizer`), séparateur, formats de date et de nombre, application d'un `ImportMapping` (dépend de T087)
- [ ] T089 [P] [US3] Implémenter `backend/src/finance/services/import_mappings.py` : paramétrage par établissement (`delimiter` « un caractère », `decimal_separator` `,` ou `.`)
- [ ] T090 [US3] Implémenter `backend/src/finance/services/imports.py` : aperçu, empreinte de ligne avec rang d'occurrence, actifs inconnus, validation, écriture via `services/transactions.py`, trace `ImportBatch` (`rows_added`, `rows_skipped`, `rows_rejected`) (dépend de T088, T054)
- [ ] T091 [US3] Implémenter `backend/src/finance/api/routers/imports.py` : `GET/POST /import-mappings`, `POST /imports/preview`, `POST /imports/commit`, avec limite de taille de fichier (dépend de T090)
- [ ] T092 [P] [US3] Implémenter `frontend/src/components/ColumnMapper.tsx` et `frontend/src/components/UnknownInstrumentsPanel.tsx` (créer, rattacher ou ignorer)
- [ ] T093 [US3] Écrire `frontend/tests/pages/Import.test.tsx` puis implémenter `frontend/src/pages/Import.tsx` : dépôt du fichier, réglages, correspondance des colonnes, aperçu, actifs inconnus, résumé (ajoutées, ignorées, rejetées), paramétrage proposé automatiquement au prochain fichier du même établissement

**Checkpoint**: US1, US2 et US3 fonctionnent : un historique importé apparaît sur le tableau de bord

---

## Phase 6: User Story 4 - Valoriser avec des cours et des valeurs liquidatives (Priority: P2)

**Goal**: cours et taux automatiques, prix manuels, valorisation des SCPI, intérêts estimés du Livret A et conversion de devises.

**Independent Test**: associer un ETF à son ISIN, récupérer ses cours, vérifier quantité × dernier cours ; couper la source et vérifier le repli (`quickstart.md` section 6).

### Tests for User Story 4 (écrire d'abord) ⚠️

- [ ] T094 [P] [US4] Écrire `backend/tests/unit/test_price_selection.py` : dernier prix antérieur ou égal à la date, valeur marquée estimée si ancien, saisie la plus récente (`recorded_at`) prioritaire à une même date
- [ ] T095 [P] [US4] Écrire `backend/tests/unit/test_scpi_valuation.py` : prix de revient au prix de souscription, valorisation au prix de retrait, écart initial visible, sans prix valeur estimée au prix de revient ; distributions comptées comme opérations
- [ ] T096 [P] [US4] Écrire `backend/tests/unit/test_livret_a_interest.py` : cas calculés à la main du solde minimum de la quinzaine × taux annuel / 24, crédit au 31 décembre, table de taux datée, intérêt réel saisi prioritaire, plafond de 22950 paramétrable
- [ ] T097 [P] [US4] Écrire `backend/tests/unit/test_fx_conversion.py` : conversion au taux de la date de valorisation, report du dernier taux les jours sans publication, valeur « non convertible » si aucun taux
- [ ] T098 [P] [US4] Écrire `backend/tests/unit/test_price_providers.py` avec `httpx` simulé : lecture du fichier de taux de la BCE, échec de Yahoo Finance avec repli sur les derniers prix, correspondance OpenFIGI ; vérifier que les requêtes sortantes ne contiennent que des tickers, des ISIN et des devises, et aucune quantité, aucun montant, aucun nom de compte ni aucune date d'opération (SC-008, principe I), et qu'aucune requête ne part tant que la récupération automatique n'est pas activée
- [ ] T099 [P] [US4] Écrire `backend/tests/contract/test_prices_rates_contract.py` pour `/prices`, `/prices/refresh`, `/rates/livret-a`, `/settings`, `/instruments/{instrumentId}/ticker-suggestions`

### Implementation for User Story 4

- [ ] T100 [P] [US4] Implémenter `backend/src/finance/prices/base.py` : interface `PriceProvider` (prix d'un actif à une date)
- [ ] T101 [P] [US4] Implémenter `backend/src/finance/prices/ecb.py` : taux de change de la BCE (publiés en général vers 16 h CET les jours ouvrés)
- [ ] T102 [P] [US4] Implémenter `backend/src/finance/prices/yahoo.py` : cours et valeurs liquidatives via `yfinance`, désactivable, erreurs absorbées
- [ ] T103 [P] [US4] Implémenter `backend/src/finance/prices/openfigi.py` : `POST https://api.openfigi.com/v3/mapping`, déclenchée par l'utilisateur, limite de débit respectée
- [ ] T104 [P] [US4] Implémenter `backend/src/finance/domain/prices.py` : sélection du prix applicable, état « estimé »
- [ ] T105 [P] [US4] Implémenter `backend/src/finance/domain/fx.py` : conversion à la date de valorisation et report du dernier taux
- [ ] T106 [P] [US4] Implémenter `backend/src/finance/domain/livret_a.py` : intérêts estimés par quinzaine, arrondi au centime documenté dans le code, plafond
- [ ] T107 [US4] Étendre `backend/src/finance/domain/valuation.py` : SCPI (souscription pour le revient, retrait pour la valorisation), conversion de devises, intérêts estimés du Livret A (dépend de T104, T105, T106)
- [ ] T108 [US4] Implémenter `backend/src/finance/services/prices.py` : saisie manuelle, mise à jour automatique avec repli sur les derniers prix et signalement d'ancienneté, conservation locale
- [ ] T109 [P] [US4] Implémenter `backend/src/finance/services/rates.py` (taux du Livret A datés et modifiables, taux de change) et `backend/src/finance/services/settings.py` (récupération automatique des prix **désactivée par défaut** jusqu'à un choix explicite, devise de référence, plafonds par défaut)
- [ ] T110 [US4] Implémenter `backend/src/finance/api/routers/prices.py` (`GET/POST /prices`, `POST /prices/refresh`, suggestions de ticker), `backend/src/finance/api/routers/rates.py` (`GET/POST /rates/livret-a`) et `backend/src/finance/api/routers/settings.py` (`GET/PATCH /settings`)
- [ ] T111 [P] [US4] Écrire `frontend/tests/components/PriceEntryForm.test.tsx` puis implémenter `frontend/src/components/PriceEntryForm.tsx` (prix de souscription et de retrait pour les SCPI, valeur liquidative, date)
- [ ] T112 [P] [US4] Implémenter `frontend/src/components/StaleBadge.tsx` (prix ancien, solde non déclaré, taux manquant) et l'afficher dans `AccountDetail.tsx` et `AccountList.tsx`
- [ ] T113 [P] [US4] Ajouter à `frontend/src/pages/Instruments.tsx` le bouton « Mettre à jour les cours », la saisie du ticker et les suggestions OpenFIGI
- [ ] T114 [P] [US4] Implémenter `frontend/src/components/LivretARatesEditor.tsx` (table des taux datés, plafond)
- [ ] T137 [P] [US4] Écrire `frontend/tests/components/PriceFetchConsent.test.tsx` puis implémenter `frontend/src/components/PriceFetchConsent.tsx` : choix explicite à la première utilisation, récupération désactivée tant que rien n'est choisi, liste des services contactés et des données envoyées (FR-029)

**Checkpoint**: US1 à US4 fonctionnent : les positions sont valorisées, les SCPI et le Livret A suivent leurs règles

---

## Phase 7: User Story 5 - Installer l'application et protéger l'accès (Priority: P3)

**Goal**: installation en une commande, accès protégé, export et restauration des données, réglages.

**Independent Test**: sur une machine vierge, installer, créer l'accès, saisir une donnée, redémarrer et la retrouver ; exporter puis restaurer à l'identique (`quickstart.md` sections 1, 2 et 8).

### Tests for User Story 5 (écrire d'abord) ⚠️

- [ ] T115 [P] [US5] Écrire `backend/tests/integration/test_export_restore_roundtrip.py` : export puis restauration redonnent des valeurs identiques pour tous les comptes et le patrimoine net (SC-009), selon `contracts/export-format.md`
- [ ] T116 [P] [US5] Écrire `backend/tests/integration/test_restore_rules.py` : la restauration n'est acceptée que sur une instance vide, un fichier de version inconnue est refusé
- [ ] T117 [P] [US5] Écrire `backend/tests/integration/test_protected_endpoints.py` : tous les endpoints sauf `/auth/*` répondent 401 sans session et 423 sur une instance verrouillée
- [ ] T118 [P] [US5] Écrire `backend/tests/contract/test_data_contract.py` pour `GET /data/export` et `POST /data/restore`
- [ ] T138 [P] [US5] Écrire `backend/tests/integration/test_change_password.py` : l'ancien mot de passe est exigé, le nouveau respecte les règles de FR-028, les données restent lisibles avec le nouveau, l'ancien est refusé ensuite (FR-033)
- [ ] T119 [P] [US5] Écrire `scripts/smoke.sh` : construit l'image, démarre le conteneur avec un volume temporaire, crée l'accès, enregistre une donnée, redémarre et la relit

### Implementation for User Story 5

- [ ] T120 [US5] Implémenter `backend/src/finance/services/export.py` : export JSON versionné non chiffré et restauration sur instance vide, selon `contracts/export-format.md`
- [ ] T121 [US5] Implémenter `backend/src/finance/api/routers/data.py` : `GET /data/export`, `POST /data/restore`
- [ ] T139 [US5] Implémenter le changement de mot de passe : `backend/src/finance/auth/service.py` (rechiffrement de la base par `PRAGMA rekey`) et `POST /auth/change-password` dans `backend/src/finance/api/routers/auth.py`, avec le tag `auth` déjà couvert par `IMPLEMENTED_TAGS`
- [ ] T140 [US5] Implémenter `frontend/src/components/ChangePasswordForm.tsx` et l'intégrer à `frontend/src/pages/Settings.tsx`, avec un test dans `frontend/tests/components/ChangePasswordForm.test.tsx`
- [ ] T122 [P] [US5] Créer `Dockerfile` à la racine, ajouter l'entrée `docker` à `.github/dependabot.yml` et créer `.dockerignore` : étape de build du frontend puis image d'exécution Python, utilisateur non root, un seul processus `uvicorn`, volume `/data`
- [ ] T123 [P] [US5] Créer `compose.yaml` à la racine : un service, un volume de données, port exposé uniquement sur la boucle locale par défaut, redémarrage automatique
- [ ] T124 [US5] Implémenter `frontend/src/pages/Settings.tsx` : export et restauration avec avertissement (le fichier n'est pas chiffré), bascule de récupération automatique des prix, liste des services contactés (BCE, Yahoo Finance, OpenFIGI) avec les données envoyées à chacun, rappel d'export, taux du Livret A, changement de mot de passe
- [ ] T125 [US5] Ajouter un rappel d'export périodique (réglage de fréquence, bannière dans `frontend/src/components/Layout.tsx`)
- [ ] T126 [P] [US5] Écrire `README.md` à la racine : prérequis, installation avec `docker compose up`, création de l'accès, sauvegarde et restauration, avertissement sur le mot de passe oublié

**Checkpoint**: les cinq histoires fonctionnent, l'application s'installe et se restaure

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: améliorations transverses et validation finale

- [ ] T127 [P] Ajouter `frontend/src/components/Disclaimer.tsx` (valeurs indicatives, aucun conseil en investissement, FR-032) dans `frontend/src/components/Layout.tsx`
- [ ] T128 [P] Écrire `frontend/tests/e2e/quickstart.spec.ts` (Playwright) qui déroule les sections 3 à 8 de `quickstart.md`
- [ ] T129 Parcourir l'interface à 375 px et 1280 px pour vérifier l'absence de défilement horizontal et corriger `frontend/src/components/*.tsx` en conséquence (FR-026)
- [ ] T130 [P] Mesurer SC-001, SC-004 et SC-005 et consigner les résultats dans `specs/001-wealth-dashboard-foundation/quickstart.md` section 9
- [ ] T131 [P] Vérifier qu'aucune requête sortante ne contient un montant ou un nom de compte (`quickstart.md` section 7, SC-008) et consigner le résultat
- [ ] T132 Revue de sécurité : en-têtes, contrôle `Origin`, limites de taille, absence de secrets, dépendances à jour ; compléter `SECURITY.md` si besoin
- [ ] T133 [P] Mettre à jour `.github/CODEOWNERS` si de nouveaux dossiers sensibles apparaissent, et ajouter le check de chaque job de code à la liste des checks requis de la règle `protect-main`
- [x] T134 Choisir la licence du dépôt puis ajouter `LICENSE` et la mention dans `README.md` (fait : AGPL-3.0, PR `chore/license`)
- [ ] T135 Valider l'arrondi des intérêts du Livret A sur de vrais relevés et ajuster `backend/src/finance/domain/livret_a.py` (point ouvert de research.md §13)
- [ ] T141 Passer `IMPLEMENTED_TAGS` de `backend/tests/contract/test_openapi_conformance.py` à la liste complète des tags du contrat : le test échoue si le contrat contient un chemin sans routeur
- [ ] T136 Exécuter `quickstart.md` de bout en bout, mettre à jour `docs/design-brief.md` si le périmètre a bougé, puis lancer `graphify update .` pour rafraîchir le graphe

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance, démarre tout de suite
- **Foundational (Phase 2)** : dépend du Setup, **bloque toutes les histoires**
- **US1 (Phase 3)** : dépend de la Phase 2, sans dépendance sur les autres histoires
- **US2 (Phase 4)** : dépend de la Phase 2 et réutilise `domain/valuation.py` de l'US1 (T051) ; les tests de l'US2 peuvent s'écrire dès la fin de la Phase 2
- **US3 (Phase 5)** : dépend de la Phase 2 et réutilise `services/transactions.py` de l'US1 (T054)
- **US4 (Phase 6)** : dépend de la Phase 2 et étend `domain/valuation.py` (T051)
- **US5 (Phase 7)** : dépend de la Phase 2 ; l'export lit les tables de toutes les histoires
- **Polish (Phase 8)** : après les histoires visées

### User Story Dependencies

- **US1 (P1)** : base de tout, à livrer en premier
- **US2 (P1)** : après T051 (valorisation), indépendante des routeurs de l'US1 pour ses tests unitaires
- **US3 (P2)** : après T054 (service des opérations)
- **US4 (P2)** : après T051, étend la valorisation
- **US5 (P3)** : peut démarrer après la Phase 2 pour le Dockerfile et le compose, l'export après les modèles

### Within Each User Story

- Tests écrits en premier et en échec avant l'implémentation (principe V)
- Domaine (fonctions pures) avant services, services avant routeurs, routeurs avant pages
- Une histoire est terminée quand son test indépendant passe

### Parallel Opportunities

- Les tâches marquées [P] d'une même phase touchent des fichiers différents et peuvent tourner en parallèle
- Les tests d'une histoire (T039 à T047, T066 à T070, T080 à T086, T094 à T099, T115 à T119) se lancent tous ensemble
- Les histoires US2, US3 et US4 peuvent avancer en parallèle après T051 et T054, avec une personne par histoire

---

## Parallel Example: User Story 1

```text
# Tests de l'US1 en parallèle :
Task: "Écrire backend/tests/unit/test_ledger_cash_effects.py"
Task: "Écrire backend/tests/unit/test_positions_and_cost_basis.py"
Task: "Écrire backend/tests/unit/test_transfer_neutrality.py"
Task: "Écrire backend/tests/unit/test_transaction_versions.py"

# Domaine de l'US1 en parallèle (fichiers différents) :
Task: "Implémenter backend/src/finance/domain/ledger.py"
Task: "Implémenter backend/src/finance/domain/cost_basis.py"
Task: "Implémenter backend/src/finance/domain/caps.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 puis 2)

1. Phase 1 : Setup
2. Phase 2 : Foundational (bloquant)
3. Phase 3 : US1, puis valider avec le scénario a à g du quickstart
4. Phase 4 : US2 pour voir le patrimoine sur le tableau de bord
5. **S'arrêter et valider** : un suivi manuel complet avec tableau de bord est déjà utilisable

### Incremental Delivery

1. Setup + Foundational : base chiffrée et authentification
2. US1 : suivi manuel complet (premier incrément utilisable)
3. US2 : tableau de bord
4. US3 : import CSV (gain de temps majeur)
5. US4 : cours, taux, SCPI, Livret A
6. US5 : installation, export, réglages
7. Polish et validation du quickstart

### Notes

- Chaque tâche vise une PR de taille raisonnable ; fusion sur `main` uniquement par pull request avec `ci-gate` vert
- Vérifier que les tests échouent avant d'implémenter, puis committer après chaque tâche ou groupe logique
- Les identifiants T137 à T141 ont été ajoutés après `/speckit-analyze` pour ne pas renuméroter ; ils sont placés dans la phase concernée et non dans l'ordre numérique

### Règle de livraison (tests d'abord)

- Les tests précèdent le code dans l'ordre des **commits**, pas dans l'ordre des **PR**.
- Une PR regroupe les tests d'un ensemble cohérent et leur implémentation. Le premier commit contient les tests (rouges), le dernier est vert ; `ci-gate` s'évalue sur le dernier commit.
- Aucune PR ne fusionne de test rouge ni de test désactivé pour passer la CI.
- Découpage conseillé : Setup ; Foundational-base (T012 à T026) ; Foundational-auth (T027 à T038) ; puis, par histoire, domaine et services, API, interface.
- Aucune donnée personnelle réelle dans les fixtures, aucun `float` dans `domain/`, aucun `UPDATE` ni `DELETE` sur les tables du journal
- Tâche qui attend l'utilisateur : T135 demande de vrais relevés du Livret A
