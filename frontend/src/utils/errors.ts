import { ApiError } from '../api/client'

export function errorMessage(error: Error, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.code === 'NETWORK_ERROR') {
      return 'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.'
    }
    return error.detail || fallback
  }
  if (error.message.trim() !== '') {
    return error.message
  }
  return fallback
}
