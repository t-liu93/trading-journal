import type { components } from './schema'
import { http } from './http'

export type McpToken = components['schemas']['McpTokenRead']
export type McpTokenIssued = components['schemas']['McpTokenIssued']
export type McpTokenCreate = components['schemas']['McpTokenCreate']

export const mcpTokensApi = {
  list: () => http.get('/api/mcp-tokens') as Promise<McpToken[]>,
  create: (payload: McpTokenCreate) => http.post('/api/mcp-tokens', payload) as Promise<McpTokenIssued>,
  revoke: (id: string) => http.delete(`/api/mcp-tokens/${id}`),
}
