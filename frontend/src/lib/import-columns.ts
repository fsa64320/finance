/** Données d'une opération qu'une colonne du fichier peut renseigner. */
export type ImportField =
  | 'trade_date'
  | 'type'
  | 'instrument_name'
  | 'isin'
  | 'quantity'
  | 'unit_price'
  | 'amount'
  | 'fees'
  | 'label'
  | 'external_id'

export interface ImportFieldInfo {
  key: ImportField
  label: string
  required: boolean
  /** Mots qui, dans un en-tête sans accents ni majuscules, désignent cette donnée. */
  pattern: RegExp
}

export const IMPORT_FIELDS: ImportFieldInfo[] = [
  { key: 'trade_date', label: 'Date', required: true, pattern: /date/ },
  {
    key: 'type',
    label: "Type d'opération",
    required: true,
    pattern: /^(type|operation|nature|sens)/,
  },
  { key: 'isin', label: 'Code ISIN', required: false, pattern: /isin/ },
  {
    key: 'quantity',
    label: 'Quantité',
    required: false,
    pattern: /quantite|nombre|\bparts?\b|\bqte\b/,
  },
  { key: 'unit_price', label: 'Prix unitaire', required: false, pattern: /cours|prix|\bpu\b/ },
  { key: 'amount', label: 'Montant', required: false, pattern: /montant|total/ },
  { key: 'fees', label: 'Frais', required: false, pattern: /frais|commission|courtage/ },
  {
    key: 'instrument_name',
    label: "Nom de l'actif",
    required: false,
    pattern: /\bnom\b|produit|actif|valeur|designation|support|libelle/,
  },
  { key: 'label', label: 'Libellé', required: false, pattern: /libelle|description|intitule/ },
  {
    key: 'external_id',
    label: 'Référence unique',
    required: false,
    pattern: /reference|identifiant|\bid\b|numero/,
  },
]

/** Ordre d'affichage : la date et le type d'abord, puis l'actif, puis les montants. */
export const IMPORT_FIELD_ORDER: ImportField[] = [
  'trade_date',
  'type',
  'instrument_name',
  'isin',
  'quantity',
  'unit_price',
  'amount',
  'fees',
  'label',
  'external_id',
]

function fold(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/**
 * Devine la correspondance d'après les en-têtes. Une colonne ne sert qu'à une donnée, sauf le
 * libellé, qui peut aussi nommer l'actif. La personne vérifie et corrige avant d'analyser.
 */
export function guessColumns(headers: string[]): Partial<Record<ImportField, string>> {
  const guessed: Partial<Record<ImportField, string>> = {}
  const usedBy = new Map<string, ImportField>()
  for (const info of IMPORT_FIELDS) {
    const found = headers.find((header) => {
      if (!info.pattern.test(fold(header))) return false
      const owner = usedBy.get(header)
      return owner === undefined || (info.key === 'label' && owner === 'instrument_name')
    })
    if (found !== undefined) {
      guessed[info.key] = found
      if (!usedBy.has(found)) usedBy.set(found, info.key)
    }
  }
  return guessed
}
