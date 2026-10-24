import { afterEach, describe, expect, it, vi } from 'vitest'

import * as client from '../../src/api/client'
import { commitImport, listMappings, previewImport } from '../../src/api/imports'
import { IMPORT_COLUMNS, MAPPING_ID, PEA_ID } from '../fixtures'

afterEach(() => {
  vi.restoreAllMocks()
})

const file = new File(['Date;Opération\n'], 'export.csv', { type: 'text/csv' })

describe('API d’import', () => {
  it('envoie le fichier et le compte en multipart', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({})
    await previewImport({ file, accountId: PEA_ID })
    const [method, path, body] = spy.mock.calls[0]!
    expect([method, path]).toEqual(['POST', '/imports/preview'])
    expect(body).toBeInstanceOf(FormData)
    const form = body as FormData
    expect(form.get('account_id')).toBe(PEA_ID)
    expect((form.get('file') as File).name).toBe('export.csv')
    expect([...form.keys()].sort()).toEqual(['account_id', 'file'])
  })

  it('joint la correspondance en JSON, le paramétrage et les réglages quand ils sont donnés', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({})
    await previewImport({
      file,
      accountId: PEA_ID,
      mappingId: MAPPING_ID,
      columns: IMPORT_COLUMNS,
      settings: {
        delimiter: ';',
        encoding: 'utf-8',
        date_format: '%d/%m/%Y',
        decimal_separator: '.',
      },
    })
    const form = spy.mock.calls[0]![2] as FormData
    expect(JSON.parse(form.get('columns') as string)).toEqual(IMPORT_COLUMNS)
    expect(form.get('mapping_id')).toBe(MAPPING_ID)
    expect(form.get('delimiter')).toBe(';')
    expect(form.get('encoding')).toBe('utf-8')
    expect(form.get('date_format')).toBe('%d/%m/%Y')
    expect(form.get('decimal_separator')).toBe('.')
  })

  it('n’envoie pas de correspondance vide', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({})
    await previewImport({ file, accountId: PEA_ID, columns: {} })
    expect((spy.mock.calls[0]![2] as FormData).has('columns')).toBe(false)
  })

  it('valide un aperçu', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue({})
    const body = { preview_id: 'jeton', confirm_rejected: false }
    await commitImport(body)
    expect(spy).toHaveBeenCalledWith('POST', '/imports/commit', body)
  })

  it('liste les paramétrages', async () => {
    const spy = vi.spyOn(client, 'request').mockResolvedValue([])
    await listMappings()
    expect(spy).toHaveBeenCalledWith('GET', '/import-mappings')
  })
})
