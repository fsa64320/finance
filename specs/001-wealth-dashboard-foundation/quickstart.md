# Quickstart: valider le lot 001 de bout en bout

**Date**: 2026-10-24 | **Plan**: [plan.md](plan.md) | **Contrat**: [contracts/openapi.yaml](contracts/openapi.yaml) | **Modèle**: [data-model.md](data-model.md)

Ce guide décrit comment lancer l'application et vérifier les comportements du spec. Il ne contient
pas de code d'implémentation. Les parcours automatisés correspondants sont écrits avec Playwright
dans `frontend/tests/`.

## Prérequis

- Docker avec Compose v2.
- Un navigateur récent.
- Un terminal pour les vérifications réseau (section 7).

## 1. Installer et démarrer (FR-028, SC-006)

```bash
docker compose up --build -d
```

Ouvrir `http://localhost:8000`. **Attendu** : l'écran de création du mot de passe s'affiche, avec le
rappel qu'un oubli rend les données irrécupérables. Aucune autre configuration n'est requise.

Vérifier l'état :

```bash
curl -s http://localhost:8000/api/v1/auth/status
```

**Attendu** : `{"state":"uninitialized"}` avant la création du mot de passe, puis `"unlocked"` après.

## 2. Créer l'accès et vérifier la protection (User Story 5)

1. Créer un mot de passe d'au moins 12 caractères.
2. Se déconnecter, puis tenter d'ouvrir `http://localhost:8000/api/v1/accounts`.
   **Attendu** : `401`.
3. Redémarrer le conteneur (`docker compose restart`) : l'instance est **verrouillée** jusqu'à la saisie
   du mot de passe.
4. Saisir un mauvais mot de passe plusieurs fois. **Attendu** : délai croissant (`429` avec
   `Retry-After`).

## 3. Saisie manuelle et calculs de référence (User Story 1, SC-002)

Créer les comptes et opérations suivants (interface ou API) :

| Étape | Action | Résultat attendu |
|---|---|---|
| a | Créer un PEA « PEA Courtier A » ouvert le 2026-01-02 | Compte à 0 € |
| b | Versement de 1 000 € le 2026-01-05 | Liquidités 1 000 € |
| c | Créer l'ETF « ETF Monde » (ISIN valide) ; achat de 10 parts à 90 € avec 1,99 € de frais le 2026-01-06 | 10 parts, prix de revient **90,199 €**, liquidités **98,01 €** |
| d | Saisir un taux du Livret A de 0 % au 2026-01-01 (les intérêts estimés sont sinon ajoutés à la valeur), puis créer un Livret A de 3 000 € (versement) et un retrait de 500 € | Solde **2 500 €** |
| e | Créer une assurance-vie avec un fonds en euros, déclarer un solde de 5 000 € au 2026-01-01 | Valeur du fonds en euros **5 000 €** (+ flux suivants) |
| f | Virement de 500 € du PEA vers le Livret A | PEA −500 €, Livret A +500 €, **patrimoine net inchangé** |
| g | Modifier l'achat de l'étape c (quantité 12) | La liste montre la version à jour ; l'historique des modifications conserve la version d'origine |

**Vérifier** : chaque valeur correspond à un calcul manuel au centime près (SC-002). Les tests
automatisés du domaine contiennent ces mêmes scénarios.

## 4. Tableau de bord (User Story 2, SC-004, SC-005)

1. Ouvrir la page d'accueil. **Attendu** : patrimoine net **« hors dettes »**, courbe d'évolution,
   répartition par classe d'actifs, liste des comptes avec leur valeur.
2. Contrôler que le patrimoine net égale la somme des valeurs des comptes et que les poids de la
   répartition totalisent 100 %.
3. Changer la période (1 mois, 1 an, tout) : la courbe passe par les valeurs attendues aux dates saisies.
4. Réduire la fenêtre à la largeur d'un téléphone : aucun défilement horizontal de la page.
5. Mesurer le chargement avec 5 000 opérations (jeu de données de test fourni par le script
   `backend/tests/fixtures/` de génération) : **moins de 3 secondes**.

## 5. Import CSV (User Story 3, SC-003)

1. Importer `backend/tests/fixtures/courtier_a_50_lignes.csv` dans le PEA (séparateur `;`, virgule
   décimale, dates jour/mois/année).
2. Dans l'aperçu, associer les colonnes ; vérifier que l'actif inconnu est listé avec son nom et son ISIN
   et choisir « créer ». **Attendu** : rien n'existe avant la validation.
3. Valider. **Attendu** : 50 opérations ajoutées.
4. **Réimporter le même fichier**. **Attendu** : 0 ajoutée, 50 ignorées (0 doublon).
5. Importer un fichier contenant des lignes invalides : elles sont listées avec la cause et rien n'est
   écrit tant que la confirmation n'est pas donnée.
6. Réimporter un fichier du même établissement : le paramétrage enregistré est proposé.

## 6. Prix et valeurs liquidatives (User Story 4, SC-007)

0. Vérifier que la récupération automatique est **désactivée** à la première utilisation et qu'aucune
   connexion sortante n'a lieu, puis l'activer dans l'écran de choix (la liste des services contactés y
   est affichée).
1. Renseigner le ticker de l'ETF (aide à la suggestion à partir de l'ISIN) puis lancer la mise à jour des
   prix. **Attendu** : valeur de la position = quantité × dernier cours, avec sa date affichée.
2. Couper le réseau ou désactiver la récupération automatique, relancer la mise à jour.
   **Attendu** : toutes les pages restent consultables avec les derniers prix connus, et un
   avertissement signale l'ancienneté.
3. Saisir pour une SCPI un prix de souscription et un prix de retrait. **Attendu** : prix de revient
   calculé sur la souscription, valorisation sur le retrait, écart initial visible.

## 7. Aucune donnée personnelle ne sort (SC-008, principe I)

Observer les connexions sortantes du conteneur avec l'outil réseau de ton choix (proxy local,
pare-feu applicatif ou journal du routeur).

Pendant une mise à jour de prix, vérifier que seules les destinations attendues apparaissent (BCE,
Yahoo Finance, et OpenFIGI uniquement quand une suggestion de ticker est demandée) et qu'aucune
requête ne contient un montant, une quantité ou un nom de compte. La page Réglages liste les
services contactés et les données envoyées.

**Vérifié automatiquement (T131, SC-008)** :

- `backend/tests/unit/test_price_providers.py` capture les requêtes réellement construites : la BCE
  reçoit un `GET` sans paramètre ni corps ; OpenFIGI reçoit uniquement `[{"idType": "ID_ISIN",
  "idValue": …}]` ; Yahoo Finance reçoit un ticker et une période grossière (`5d`, `1mo`, `1y`,
  `max`), jamais de date d'opération. Aucune requête ne part avec un ISIN invalide.
- `backend/tests/integration/test_us4_api.py` (classe `TestRefresh`, `TestTickerSuggestions`) vérifie
  que **rien ne sort** tant que la récupération automatique est désactivée (réglage par défaut), que
  seuls les actifs en mode automatique avec un ticker sont envoyés, et que la BCE n'est pas
  interrogée sans devise étrangère.
- `frontend/tests/e2e/quickstart.spec.ts` (étape §7) enregistre toutes les requêtes du navigateur
  pendant le parcours complet : aucune ne quitte `127.0.0.1`.

**Limite** : la bibliothèque `yfinance` effectue elle-même des échanges d'amorçage avec Yahoo
(consentement, jeton) dont le contenu n'est pas maîtrisé par l'application ; seule la partie que
l'application construit est vérifiée. À observer avec un proxy local avant de s'y fier.

## 8. Export et restauration (SC-009)

1. Exporter les données depuis la page Réglages. **Attendu** : un fichier JSON conforme à
   [contracts/export-format.md](contracts/export-format.md), avec l'avertissement qu'il n'est pas
   chiffré.
2. Noter les valeurs de tous les comptes et le patrimoine net.
3. Sur une instance neuve (`docker compose down -v && docker compose up -d`), créer un mot de passe puis
   restaurer le fichier. **Attendu** : valeurs identiques, historique des modifications intact.
4. Tenter une restauration sur une instance qui contient déjà des comptes. **Attendu** : refus (`409`).

## 9. Tests automatisés

```bash
# Backend : unitaires (cas chiffrés), invariants, intégration, conformité au contrat
cd backend && uv run pytest

# Frontend : composants, puis parcours de bout en bout (interface compilée + vrai backend)
cd frontend && npm test && npm run build && npm run e2e

# Image Docker : construction, démarrage, redémarrage, relecture
scripts/smoke.sh
```

**Attendu** : tous les tests passent ; aucun `float` dans `backend/src/finance/domain/` (test dédié) ;
aucune requête `UPDATE` ni `DELETE` sur les tables du journal (test dédié).

### Résultats consignés

| Mesure | État |
|---|---|
| Parcours des sections 3 à 8 (T128) | Automatisé (`quickstart.spec.ts`), exécuté en CI à chaque PR |
| Parcours au clavier (T143, SC-010) | Automatisé (`keyboard.spec.ts`), exécuté en CI |
| Installation Docker et persistance (SC-006, partie technique) | `scripts/smoke.sh`, exécuté en CI |
| Débordement horizontal à 375 px (FR-026) | Contrôlé sur les cinq écrans par le test de bout en bout |
| **SC-001, SC-004, SC-005 avec un testeur débutant (T130)** | **À faire** : demande une personne extérieure |
| **SC-006 de bout en bout, moins de 10 minutes sans ligne de commande (T152)** | **À faire** : demande une personne extérieure ; l'installation exige aujourd'hui la commande `docker compose up -d --build` (aucune image publiée) |
| **Arrondi des intérêts du Livret A sur de vrais relevés (T135)** | **À faire** : demande des relevés réels |

## Nettoyage

```bash
docker compose down        # conserve les données
docker compose down -v     # supprime aussi le volume de données
```
