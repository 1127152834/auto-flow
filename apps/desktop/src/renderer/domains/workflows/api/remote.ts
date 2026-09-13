import type { Node, Edge } from '@xyflow/react'
export interface RemoteSession {
  assistCode: string
  role: 'host' | 'guest'
  status: 'connecting' | 'waiting' | 'connected' | 'disconnected'
  guestConnected?: boolean
  connectionType?: 'p2p' | 'relay'
}

export type RemoteMessageType = 
  | 'mouse_move'
  | 'mouse_click'
  | 'node_add'
  | 'node_delete'
  | 'node_move'
  | 'node_update'
  | 'nodes_change'
  | 'edge_add'
  | 'edge_delete'
  | 'edges_change'
  | 'variable_add'
  | 'variable_update'
  | 'variable_delete'
  | 'sync_request'
  | 'sync_data'
  | 'full_sync'

export interface RemoteMessage {
  type: RemoteMessageType | string
  [key: string]: unknown
}

export interface SyncData {
  nodes: Node[]
  edges: Edge[]
  variables: unknown[]
  workflowName?: string
}

type MessageHandler = (message: RemoteMessage) => void
type StatusHandler = (status: RemoteSession['status'], info?: string) => void
type GuestStatusHandler = (connected: boolean) => void
type SyncDataHandler = (data: SyncData) => void

/** Enterprise collaboration is excluded from AutoFlow Studio. */
class RemoteService {
  async createSession() { return { success:false, error:'AutoFlow 不包含远程协作' } }
  async joinSession(_code: string) { return { success:false, error:'AutoFlow 不包含远程协作' } }
  async closeSession() {}
  send(_message: RemoteMessage) {}
  sendOperation(_message: RemoteMessage) {}
  setApplyingRemote(_value: boolean) {}
  isApplyingRemoteOperation() { return false }
  onMessage(_handler: MessageHandler) { return () => {} }
  onStatus(_handler: StatusHandler) { return () => {} }
  onGuestStatus(_handler: GuestStatusHandler) { return () => {} }
  onSyncData(_handler: SyncDataHandler) { return () => {} }
  getSession(): RemoteSession | null { return null }
  isConnected() { return false }
  isHost() { return false }
  isGuest() { return false }
  getConnectionType(): 'p2p' | 'relay' | null { return null }
}
export const remoteService = new RemoteService()
