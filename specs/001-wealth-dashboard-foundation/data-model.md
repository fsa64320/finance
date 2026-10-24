# Data Model: Socle de suivi de patrimoine et tableau de bord

**Date**: 2026-10-24 | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

## Conventions

- Identifiants : UUID texte. Dates : `date` ISO 8601 (jour) ; horodatages en UTC.
- **Décimaux** : montants, quantités, prix et taux sont des textes décimaux canoniques (pas de notation
  scientifique, point comme séparateur), lus en `Decimal`. Aucun flottant.
- **Devises** : code ISO 4217 en trois lettres. Chaque montant garde sa devise d'origine.
- **Journal en ajout seul** : les tables `transaction_version`, `price`, `declared_balance`, `rate` et
  `import_batch` ne reçoivent ni `UPDATE` ni `DELETE`. Une correction ajoute une ligne.
- **Aucune valeur dérivée n'est stockée** : valeurs de comptes, patrimoine, répartition, prix de revient
  se recalculent depuis ces tables.

## Entités

### Account (compte)

| Champ | Type | Règle |
|---|---|---|
| id | UUID | Clé |
| type | énumération | `PEE`, `PEA`, `CTO`, `ASSURANCE_VIE`, `LIVRET_A` |
| name | texte | Obligatoire, unique parmi les comptes ouverts |
| institution | texte | Facultatif |
| currency | devise | Par défaut la devise de référence |
| opened_on | date | Obligatoire |
| closed_on | date | Facultatif ; supérieur ou égal à `opened_on` |
| settings | JSON | Paramètres propres au type : `deposit_cap` (PEA, défaut 150000), `deposit_cap` (Livret A, défaut 22950), `lock_years` (PEE) |

**Transitions** : ouvert → clôturé (par `closed_on`). Un compte clôturé sort des totaux courants mais
reste dans l'historique. La réouverture efface `closed_on` et est tracée par la date de modification
du compte (table de comptes modifiable, car ce n'est pas du journal).

### Instrument (actif)

| Champ | Type | Règle |
|---|---|---|
| id | UUID | Clé |
| kind | énumération | `EQUITY`, `ETF`, `FUND`, `FCPE`, `SCPI`, `EURO_FUND`, `CASH` |
| name | texte | Obligatoire |
| isin | texte | Facultatif ; 12 caractères alphanumériques avec clé de contrôle valide ; unique s'il est présent |
| currency | devise | Obligatoire |
| price_ticker | texte | Facultatif ; ticker utilisé par le fournisseur de cours |
| price_mode | énumération | `AUTO` (fournisseur) ou `MANUAL` (saisie) ; défaut `MANUAL` pour `SCPI`, `FCPE`, `EURO_FUND`, `CASH` |

**Classe d'actifs dérivée du type** (pour la répartition) :

| Type d'actif | Classe affichée |
|---|---|
| `EQUITY`, `ETF` | Actions & ETF |
| `FUND`, `FCPE` | Fonds |
| `SCPI` | SCPI |
| `EURO_FUND` | Fonds en euros |
| `CASH` | Liquidités |

Les liquidités d'un compte sont l'actif `CASH` de la devise du compte, valorisé à 1 ; chaque compte les
suit par somme des effets de trésorerie de ses opérations.

### Transaction et TransactionVersion

`transaction` porte l'identité stable (id, compte, date de création). `transaction_version` porte le
contenu, une ligne par version.

| Champ (`transaction_version`) | Type | Règle |
|---|---|---|
| transaction_id | UUID | Référence `transaction` |
| version | entier | 1, 2, 3, … ; la dernière version fait foi |
| voided | booléen | Vrai pour une annulation ; l'opération sort alors de tous les calculs |
| type | énumération | `DEPOSIT`, `WITHDRAWAL`, `BUY`, `SELL`, `DIVIDEND`, `DISTRIBUTION`, `INTEREST`, `FEE`, `EMPLOYER_MATCH`, `TRANSFER_OUT`, `TRANSFER_IN` |
| trade_date | date | Obligatoire ; supérieure ou égale à `opened_on` du compte |
| instrument_id | UUID | Obligatoire pour `BUY`, `SELL`, `DIVIDEND`, `DISTRIBUTION` ; vide pour les flux de trésorerie purs |
| quantity | décimal | Strictement positive pour `BUY`, `SELL` ; vide sinon |
| unit_price | décimal | Positif pour `BUY`, `SELL` |
| fees | décimal | Positif ou nul, dans la devise de l'opération |
| cash_amount | décimal | Effet signé sur la trésorerie du compte ; calculé à la saisie selon le type et conservé |
| currency | devise | Devise de l'opération |
| unlock_date | date | Facultatif ; déblocage d'une somme du PEE |
| transfer_group_id | UUID | Obligatoire pour `TRANSFER_OUT` et `TRANSFER_IN`, commun aux deux jambes |
| label | texte | Libellé libre |
| external_id | texte | Identifiant fourni par un fichier importé |
| line_fingerprint | texte | Empreinte de ligne pour le dédoublonnage |
| import_id | UUID | Fichier d'origine, vide si saisie manuelle |
| created_at | horodatage | Création de cette version |

**Effets de trésorerie** : `DEPOSIT`, `DIVIDEND`, `DISTRIBUTION`, `INTEREST`, `EMPLOYER_MATCH`,
`TRANSFER_IN` ajoutent ; `WITHDRAWAL`, `FEE`, `TRANSFER_OUT` retirent ; `BUY` retire
`quantity × unit_price + fees` ; `SELL` ajoute `quantity × unit_price − fees`.

**Règles de validation**

- Une vente qui dépasse la quantité détenue est acceptée avec un avertissement (historique possiblement
  incomplet), jamais bloquée.
- Les deux jambes d'un virement ont le même montant, la même date et deux comptes différents ; elles se
  modifient et s'annulent ensemble.
- `EMPLOYER_MATCH` n'est autorisé que sur un compte `PEE`.
- Un achat ou une vente sur un compte `LIVRET_A` est refusé (trésorerie seule).
- Un fichier importé qui fournit `external_id` l'emporte sur l'empreinte pour la détection de doublon.

**Transitions** : version 1 → version n (modification) → version n+1 avec `voided` vrai (annulation).
Une annulation peut être suivie d'une nouvelle version non annulée (rétablissement).

### TransferGroup

Table minimale (id, créée le) qui garantit qu'un groupe de virement a exactement deux jambes de types
opposés. Contrôlée à l'écriture par le service des opérations.

### Price (prix)

| Champ | Type | Règle |
|---|---|---|
| instrument_id | UUID | Référence |
| price_date | date | Obligatoire |
| kind | énumération | `MARKET`, `NAV` (valeur liquidative), `SUBSCRIPTION`, `REDEMPTION` |
| value | décimal | Strictement positif |
| currency | devise | Devise du prix |
| source | énumération | `PROVIDER` ou `MANUAL` |
| recorded_at | horodatage | Pour départager deux saisies à la même date : la plus récente fait foi |

Seuls les prix `SUBSCRIPTION` et `REDEMPTION` s'appliquent aux SCPI ; `MARKET` aux actions et ETF ;
`NAV` aux fonds et FCPE.

### DeclaredBalance (solde déclaré)

| Champ | Type | Règle |
|---|---|---|
| account_id | UUID | Référence |
| instrument_id | UUID | Actif sans cours (`EURO_FUND`, `CASH`) |
| balance_date | date | Obligatoire |
| amount | décimal | Positif ou nul |
| currency | devise | Devise du solde |
| recorded_at | horodatage | La plus récente saisie à une date fait foi |

Sert de valeur de référence pour les actifs sans cours et de point de contrôle avec le relevé réel.

### Rate (taux)

| Champ | Type | Règle |
|---|---|---|
| kind | énumération | `LIVRET_A`, `FX` |
| base | texte | Pour `FX` : devise de base (`EUR`) ; vide pour `LIVRET_A` |
| quote | texte | Pour `FX` : devise cotée ; vide pour `LIVRET_A` |
| effective_from | date | Début de validité ; le taux en vigueur est le plus récent antérieur ou égal à la date |
| value | décimal | Pour `LIVRET_A` : taux annuel en pourcentage ; pour `FX` : taux de change |
| source | énumération | `ECB` ou `MANUAL` |

### ImportBatch (import)

| Champ | Type | Règle |
|---|---|---|
| id | UUID | Clé |
| account_id | UUID | Compte visé |
| file_name | texte | Nom d'origine |
| file_hash | texte | Empreinte du contenu |
| mapping_id | UUID | Paramétrage utilisé, facultatif |
| rows_added | entier | Lignes ajoutées |
| rows_skipped | entier | Lignes déjà connues |
| rows_rejected | entier | Lignes invalides |
| imported_at | horodatage | Création |

### ImportMapping (paramétrage d'import)

| Champ | Type | Règle |
|---|---|---|
| id | UUID | Clé |
| name | texte | Nom de l'établissement, unique |
| delimiter | texte | Un caractère |
| encoding | texte | Par exemple `utf-8`, `windows-1252` |
| date_format | texte | Par exemple `%d/%m/%Y` |
| decimal_separator | texte | `,` ou `.` |
| columns | JSON | Correspondance colonne du fichier → donnée d'opération |

### Setting (réglage)

Clé / valeur modifiable : devise de référence, récupération automatique des prix (oui/non, **non** par défaut tant que l'utilisateur n'a pas choisi), plafonds par
défaut, rappel d'export. Un enregistrement de configuration d'authentification (sel, paramètres de
dérivation) vit hors de la base chiffrée dans un petit fichier de métadonnées, car il est nécessaire
avant le déverrouillage.

## Relations

```text
Account 1 ── * Transaction 1 ── * TransactionVersion * ── 0..1 Instrument
Transaction (TRANSFER_OUT) ── groupe ── Transaction (TRANSFER_IN)   [via transfer_group_id]
Instrument 1 ── * Price
Account 1 ── * DeclaredBalance * ── 1 Instrument
ImportBatch 1 ── * TransactionVersion          ImportMapping 1 ── * ImportBatch
```

## Calculs dérivés (rappel, non stockés)

- **Position** (compte, actif, date) : somme signée des quantités des dernières versions non annulées
  jusqu'à la date.
- **Prix de revient unitaire** : moyenne pondérée des achats, frais inclus ; les ventes retirent des parts
  sans changer le prix de revient unitaire restant.
- **Valeur d'une position** : voir [research.md](research.md), section 8, par type d'actif.
- **Valeur d'un compte** : valeur des positions plus trésorerie.
- **Patrimoine net (hors dettes)** : somme des valeurs des comptes ouverts convertie dans la devise de
  référence au taux de la date de valorisation.
- **Répartition** : valeurs groupées par classe d'actifs, poids en pourcentage, somme égale à 100 %.
