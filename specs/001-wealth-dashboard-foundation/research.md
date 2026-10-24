# Research: Socle de suivi de patrimoine et tableau de bord

**Date**: 2026-10-24 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Toutes les inconnues du contexte technique sont résolues ci-dessous. Aucun marqueur
`NEEDS CLARIFICATION` ne subsiste.

## 1. Chiffrement de la base

- **Decision**: SQLite chiffré par SQLCipher, via le paquet `sqlcipher3-wheels` (0.5.7). SQLAlchemy se
  connecte avec un `creator` qui ouvre la connexion `sqlcipher3` puis exécute `PRAGMA key`.
- **Rationale**: FR-028 exige des données illisibles sans le mot de passe. SQLCipher chiffre tout le
  fichier tout en laissant SQL et agrégations fonctionner. Les vérifications sur PyPI montrent que
  `sqlcipher3-wheels` publie des roues manylinux pour amd64 et arm64 (et musllinux), alors que
  `sqlcipher3-binary` n'affichait qu'une roue amd64 : l'image doit tourner aussi sur arm64.
- **Alternatives considered**: `pysqlcipher3` (plus maintenu depuis 2023, pas de roues) ; chiffrement
  champ par champ en Python (empêche les requêtes et agrégations sur les montants) ; chiffrement du
  disque seul (ne protège pas le fichier copié ailleurs).

## 2. Mot de passe, sessions et mode d'exécution

- **Decision**: le mot de passe sert de clé SQLCipher. L'ouvrir correctement prouve que le mot de passe est
  bon. Aucun mécanisme de récupération (clarification 1). Un seul processus serveur garde la base
  déverrouillée en mémoire ; après un redémarrage, l'instance est verrouillée jusqu'à la saisie du
  mot de passe. Un cookie de session aléatoire (HttpOnly, SameSite=Strict) désigne la session. Les
  essais de connexion sont limités (délai croissant après des échecs).
- **Rationale**: respecte la clarification 1 et le principe I. Le mode mono-processus évite de partager
  une clé entre processus.
- **Alternatives considered**: code de récupération ou clé gérée par le serveur (rejetés à la
  clarification 1) ; plusieurs workers (la clé ne serait déverrouillée que dans un seul).

## 3. Représentation des montants

- **Decision**: les montants, quantités, prix et taux sont stockés en texte décimal canonique dans SQLite
  (type SQLAlchemy dédié) et manipulés en `Decimal`. Les sommes et agrégats sont faits en Python. L'API
  les échange sous forme de chaînes.
- **Rationale**: principe III. Le type `NUMERIC` de SQLite a une affinité qui peut convertir en flottant,
  et `SUM()` en SQL travaille en flottant. À l'échelle visée (quelques dizaines de milliers
  d'opérations), agréger en Python reste largement dans le budget de performance.
- **Alternatives considered**: entiers en plus petite unité (insuffisant pour des quantités de parts à
  plusieurs décimales et des prix à 4 décimales) ; `NUMERIC` SQLite (risque de flottants).

## 4. Journal en ajout seul avec versions

- **Decision**: deux tables, `transaction` (identité stable) et `transaction_version` (une ligne par version,
  numérotée). Modifier insère une nouvelle version ; annuler insère une version marquée annulée. Aucun
  `UPDATE` ni `DELETE` sur ces tables (vérifié par test). L'état courant d'une opération est sa
  dernière version.
- **Rationale**: concilie le principe II (le journal n'est jamais modifié ni supprimé) avec la
  clarification 3 (correction directe dans l'interface, ancienne version conservée dans un historique).
- **Alternatives considered**: lignes mutables avec journal d'audit à part (viole le principe II) ;
  contre-écritures obligatoires (rejetées à la clarification 3 pour la lourdeur d'usage).

## 5. Virements entre comptes

- **Decision**: un virement est un groupe de deux jambes (sortie et entrée) reliées par un identifiant de
  groupe, saisies et modifiées ensemble. Il est neutre pour le patrimoine net total et n'est compté
  ni comme apport ni comme sortie extérieure.
- **Rationale**: clarification 2 ; chaque compte garde un solde calculable à partir de ses seules
  jambes, ce qui simplifie les calculs par compte.
- **Alternatives considered**: une seule ligne avec deux comptes (les calculs par compte devraient
  traiter deux cas) ; deux opérations libres sans lien (fausse le futur calcul de rendement).

## 6. Import CSV

- **Decision**: l'importeur générique détecte l'encodage (`charset-normalizer`), propose le séparateur, le
  format de date et le format de nombre, que l'utilisateur peut corriger dans l'aperçu. L'importeur
  reçoit un fichier et renvoie des lignes normalisées (il n'écrit jamais en base). Le service
  d'import fait ensuite : aperçu, validation, écriture.
  - **Empreinte d'une ligne** : compte, date, type, actif, quantité, montant, libellé et rang
    d'occurrence de cette même combinaison dans le fichier. Le rang distingue deux opérations vraiment
    identiques du même fichier ; réimporter le fichier retrouve les mêmes empreintes et n'ajoute rien.
    Si le fichier fournit un identifiant de transaction, il remplace l'empreinte.
  - **Actifs inconnus** : listés dans l'aperçu avec nom et ISIN lus dans le fichier ; créer, rattacher
    ou ignorer, sans rien créer avant validation (clarification 4).
  - **Mapping enregistrable** par établissement et proposé à l'import suivant.
- **Rationale**: principe IV (importeur isolé, idempotence) et FR-015 à FR-020.
- **Alternatives considered**: empreinte sans rang (fusionne à tort deux achats identiques du même
  jour) ; création automatique des actifs (rejetée à la clarification 4).

## 7. Sources de prix et de taux

- **Decision**: une interface `PriceProvider` et trois implémentations, plus la saisie manuelle.
  - **Taux de change : BCE** (taux de référence quotidiens, publiés en général vers 16 h CET les jours
    ouvrés). Les jours sans publication reprennent le dernier taux connu. La BCE précise que ces
    taux sont publiés à titre d'information : suffisant pour valoriser un patrimoine, pas pour une
    transaction.
  - **Cours actions, ETF et fonds : Yahoo Finance** via `yfinance` 1.7.0, par ticker stocké sur
    l'actif. Source non officielle, susceptible de changer ou de bloquer ; elle est désactivable.
  - **Aide à la saisie du ticker : OpenFIGI v3** (`POST https://api.openfigi.com/v3/mapping`), sans clé :
    25 requêtes par minute et 10 demandes par requête. Déclenchée par l'utilisateur pour proposer un
    ticker à partir d'un ISIN.
  - **Saisie manuelle** toujours possible, et seule voie prévue pour les SCPI et la plupart des FCPE.
- **Vie privée (principe I)**: seuls des identifiants d'actifs (ticker, ISIN) et des devises sortent ; jamais
  de quantités, de montants ni de noms de comptes. Ces identifiants révèlent néanmoins ce qui est
  détenu : la récupération est désactivable dans les réglages et la liste des services contactés y
  est affichée.
- **Rationale**: aucune source officielle gratuite ne couvre les cours des actifs européens. L'interface
  de fournisseur isole le risque de rupture, et l'application reste utilisable avec des prix saisis.
- **Alternatives considered**: Stooq (symboles, pas d'ISIN) ; API commerciales payantes (contraires à
  l'objectif gratuit et auto-hébergé) ; scraping de sites de fonds (exclu par le principe IV).

## 8. Règles de valorisation par type

- **Actions, ETF, fonds, FCPE**: valeur = quantité × dernier prix connu à la date (marqué « estimé » si le prix
  est ancien). Prix de revient unitaire = moyenne pondérée, frais inclus ; une vente partielle ne
  change pas le prix de revient unitaire des parts restantes.
- **Fonds en euros**: valeur = dernier solde déclaré à la date + flux depuis cette date. Sans solde déclaré,
  valeur nulle et message invitant à en déclarer un.
- **SCPI**: prix de revient avec le prix de souscription (frais d'entrée inclus) ; valorisation avec le
  prix de retrait ; sans prix, estimée au prix de revient et signalée ; distributions = opérations.
- **Livret A**: solde issu des opérations. Intérêts estimés par quinzaines : solde minimum de la quinzaine
  × taux annuel / 24, crédités au 31 décembre. Le taux vient de la table datée modifiable. L'arrondi au
  centime est documenté dans le code et **à valider contre de vrais relevés** avant de s'y fier ; les
  intérêts réels saisis ou importés prévalent. Plafond paramétrable (22 950 € par défaut).
- **PEA**: cumul des versements (extérieurs et virements entrants, sans déduire les retraits) comparé à un
  plafond paramétrable (150 000 € par défaut).
- **PEE**: l'abondement entre dans le patrimoine, pas dans les apports ; la date de déblocage est portée par
  la ligne.
- **Rationale**: FR-005 à FR-010 ; règles testables par des cas chiffrés (principe V).
- **Alternatives considered**: FIFO pour les ventes (le prix moyen pondéré est la convention fiscale
  courante et celle retenue au spec) ; intérêts du Livret A pris au solde de fin de quinzaine
  (surestime en cas de retrait).

## 9. Série du patrimoine et performance de calcul

- **Decision**: la série se calcule par un balayage unique des opérations triées et des prix triés, avec des
  points quotidiens jusqu'à 1 an et hebdomadaires au-delà. Le résultat n'est pas persisté ; un cache
  mémoire, invalidé à chaque écriture, est autorisé car reconstructible à l'identique.
- **Rationale**: SC-004 (moins de 3 s pour 10 ans et 5 000 opérations) et principe II (aucune valeur
  dérivée stockée en dur). Environ 5 000 opérations et 520 points hebdomadaires restent très en
  dessous du budget.
- **Alternatives considered**: table de valorisations précalculées (viole le principe II) ; points
  quotidiens sur 10 ans (inutilement lourds pour l'affichage).

## 10. Frontend

- **Decision**: React 18 + Vite + TypeScript, TanStack Query pour les appels, React Router, Recharts pour la
  courbe et la répartition, Tailwind CSS pour le style. Client TypeScript généré depuis
  `contracts/openapi.yaml`. Interface en français (`Intl` avec `fr-FR`), mise en page responsive,
  identité visuelle propre (nom, palette, icônes, textes originaux).
- **Rationale**: stack figée par la constitution ; ces bibliothèques sont courantes et suffisantes pour
  un tableau de bord et des formulaires.
- **Alternatives considered**: ECharts ou uPlot (plus lourds ou plus bas niveau que nécessaire) ;
  bibliothèque de composants complète (dépendance en plus, YAGNI).

## 11. Tests

- **Decision**: `pytest` avec `hypothesis` pour les invariants (somme des positions, neutralité des
  virements, idempotence de l'import, non-régression des versions) ; fixtures de CSV anonymisés ;
  Vitest + Testing Library pour les composants ; Playwright pour le parcours du quickstart ; un test
  qui interdit `float` dans le domaine ; un test de conformité de l'API à `openapi.yaml`.
- **Rationale**: principe V (tests chiffrés d'abord, importeur livré avec échantillon et test).

## 12. Export, restauration et déploiement

- **Decision**: l'export est un fichier JSON versionné décrit dans
  [contracts/export-format.md](contracts/export-format.md). Il est **non chiffré** : l'interface avertit
  l'utilisateur de le conserver en lieu sûr. La restauration s'applique sur une instance vide. Une image
  Docker multi-étapes (build du frontend, puis exécution Python) et un `compose.yaml` avec un volume
  `/data` ; un seul processus.
- **Rationale**: FR-030, SC-006 et SC-009 ; format ouvert et lisible.
- **Alternatives considered**: export chiffré (complique la récupération, cohérent avec la
  clarification 1 mais à décider dans un lot ultérieur) ; sauvegarde du fichier de base brut (illisible
  hors SQLCipher).

## 13. Points laissés ouverts (hors de ce lot de code)

- Choix de la licence du dépôt (obligatoire avant publication, voir constitution).
- Validation de l'arrondi des intérêts du Livret A sur de vrais relevés.
- Fiabilité de la couverture Yahoo Finance pour les fonds et FCPE, à évaluer à l'usage.
