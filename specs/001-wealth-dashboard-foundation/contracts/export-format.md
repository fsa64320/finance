# Format d'export et de restauration

**Route**: `GET /api/v1/data/export` et `POST /api/v1/data/restore` (voir [openapi.yaml](openapi.yaml)).

## Principes

- Un seul fichier JSON, en UTF-8, ouvert et lisible.
- **Non chiffré** : toute personne qui le détient lit l'intégralité des données. L'interface avertit
  l'utilisateur à chaque export de le conserver en lieu sûr.
- **Versionné** : le champ `format_version` permet de lire d'anciens exports. Une version inconnue plus
  récente est refusée avec un message clair.
- **Complet** : comptes, actifs, toutes les versions de toutes les opérations, prix, soldes déclarés,
  taux, historique d'imports, paramétrages d'import et réglages. Aucun mot de passe ni clé n'y figure.
- **Exact** : montants, quantités, prix et taux sont des chaînes décimales, comme dans l'API.

## Structure

```json
{
  "format_version": 1,
  "exported_at": "2026-10-24T12:00:00Z",
  "reference_currency": "EUR",
  "settings": { "auto_fetch_prices": true, "export_reminder_days": 30 },
  "accounts": [
    { "id": "…", "type": "PEA", "name": "PEA Courtier A", "institution": "…",
      "currency": "EUR", "opened_on": "2020-03-02", "closed_on": null,
      "settings": { "deposit_cap": "150000" } }
  ],
  "instruments": [
    { "id": "…", "kind": "ETF", "name": "…", "isin": "…", "currency": "EUR",
      "price_ticker": "…", "price_mode": "AUTO" }
  ],
  "transactions": [
    { "id": "…", "account_id": "…", "created_at": "2026-01-05T10:00:00Z",
      "versions": [
        { "version": 1, "voided": false, "type": "BUY", "trade_date": "2026-01-05",
          "instrument_id": "…", "quantity": "10", "unit_price": "90", "fees": "1.99",
          "cash_amount": "-901.99", "currency": "EUR", "unlock_date": null,
          "transfer_group_id": null, "label": "", "external_id": null,
          "line_fingerprint": "…", "import_id": null, "created_at": "2026-01-05T10:00:00Z" }
      ] }
  ],
  "prices": [
    { "instrument_id": "…", "price_date": "2026-10-23", "kind": "MARKET",
      "value": "91.2", "currency": "EUR", "source": "PROVIDER", "recorded_at": "…" }
  ],
  "declared_balances": [
    { "account_id": "…", "instrument_id": "…", "balance_date": "2026-01-01",
      "amount": "5000", "currency": "EUR", "recorded_at": "…" }
  ],
  "rates": [
    { "kind": "LIVRET_A", "effective_from": "2025-08-01", "value": "1.7", "source": "MANUAL" },
    { "kind": "FX", "base": "EUR", "quote": "USD", "effective_from": "2026-10-23",
      "value": "1.08", "source": "ECB" }
  ],
  "imports": [
    { "id": "…", "account_id": "…", "file_name": "export.csv", "file_hash": "…",
      "mapping_id": null, "rows_added": 50, "rows_skipped": 0, "rows_rejected": 0,
      "imported_at": "…" }
  ],
  "import_mappings": [
    { "id": "…", "name": "Courtier A", "delimiter": ";", "encoding": "windows-1252",
      "date_format": "%d/%m/%Y", "decimal_separator": ",", "columns": { "trade_date": "Date" } }
  ]
}
```

## Règles de restauration

1. La restauration n'est acceptée que sur une instance **vide** (aucun compte) ; sinon `409`.
2. Le fichier est validé en entier (version, références entre entités, décimaux valides, devises) avant
   toute écriture ; en cas d'erreur, rien n'est écrit (`422` avec la liste des problèmes).
3. Les identifiants sont conservés, ce qui garde intactes les relations (virements, imports,
   versions).
4. Après restauration, les valeurs de tous les comptes et le patrimoine net sont **identiques** à celles
   de l'instance exportée (SC-009). Un test automatisé compare les deux.
