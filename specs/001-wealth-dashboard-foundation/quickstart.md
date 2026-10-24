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
| d | Créer un Livret A de 3 000 € (versement), puis un retrait de 500 € | Solde **2 500 €** |
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
requête ne contient un montant, une quantité ou un nom de compte. Le test d'intégration
`backend/tests/integration/test_outbound_requests.py` fait cette vérification sur les requêtes
envoyées aux fournisseurs de prix. La page Réglages liste les services contactés et les données
envoyées.

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
docker compose run --rm finance pytest

# Frontend : composants puis parcours de bout en bout
cd frontend && npm test && npx playwright test
```

**Attendu** : tous les tests passent ; aucun `float` dans `backend/src/finance/domain/` (test dédié) ;
aucune requête `UPDATE` ni `DELETE` sur les tables du journal (test dédié).

## Nettoyage

```bash
docker compose down        # conserve les données
docker compose down -v     # supprime aussi le volume de données
```
