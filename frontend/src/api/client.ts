/** Client HTTP typé pour l'API /api/v1. Les cookies de session sont gérés par le navigateur. */

const BASE = '/api/v1'

export type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface ApiErrorDetail {
  field: string
  message: string
}

/** Erreur renvoyée par l'API (format {code, message, details}) ou par le réseau (status 0). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: ApiErrorDetail[]
  readonly retryAfter?: number

  constructor(
    status: number,
    code: string,
    message: string,
    details?: ApiErrorDetail[],
    retryAfter?: number,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.retryAfter = retryAfter
  }
}

interface ErrorBody {
  code?: string
  message?: string
  details?: ApiErrorDetail[]
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {}
  try {
    body = (await response.json()) as ErrorBody
  } catch {
    // Corps absent ou qui n'est pas du JSON : on garde un code générique.
  }
  const header = response.headers.get('retry-after')
  const retryAfter = header !== null && /^\d+$/.test(header) ? Number(header) : undefined
  return new ApiError(
    response.status,
    body.code ?? 'http_error',
    body.message ?? `Erreur HTTP ${response.status}`,
    body.details,
    retryAfter,
  )
}

export async function request<T = undefined>(
  method: Method,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { accept: 'application/json' }
  const init: RequestInit = { method, credentials: 'same-origin', headers }
  if (body instanceof FormData) {
    // Le navigateur ajoute lui-même le type multipart et sa frontière.
    init.body = body
  } else if (body !== undefined) {
    headers['content-type'] = 'application/json'
    init.body = JSON.stringify(body)
  }

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'network_error', 'Impossible de joindre le serveur.')
  }

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
