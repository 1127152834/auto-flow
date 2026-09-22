type Session = { id: string; deviceId: string; generation: number; access: 'manual' | 'readonly'; state: string; width: number; height: number }
type Input = { kind: string; text?: string; [key: string]: unknown }
type Api = {
  session(deviceId: string, access: 'manual' | 'readonly', requestId: string, clientSessionId?: string): Promise<Session>
  input(id: string, body: Input & { generation: number; sequence: number }): Promise<Session>
  action(session: Session, action: 'end'): Promise<Session>
  heartbeat(id: string, clientSessionId: string, generation: number): Promise<Session>
}
type Identity = { workspaceIdentity: string; backendInstanceId: string }

export function createConsoleController(api: Api, identity: Identity) {
  let session: Session | null = null
  let token = 0
  let epoch = 0
  let leaving = 0
  let sequence = 0
  let queue = Promise.resolve()
  const listeners = new Set<(value: Session | null) => void>()
  const clientSessionId = `${identity.workspaceIdentity}:${identity.backendInstanceId}`
  const publish = () => listeners.forEach(listener => listener(session))
  const end = async (target: Session) => {
    if (target.state === 'closed') return
    try { await api.action(target, 'end') } catch { /* the remote session is already discarded locally */ }
  }
  return {
    async open(deviceId: string) {
      const current = ++token
      const currentEpoch = epoch
      const previous = session
      session = null
      sequence = 0
      if (previous) publish()
      if (previous) await end(previous)
      if (current !== token || currentEpoch !== epoch) return
      const opened = await api.session(deviceId, 'manual', crypto.randomUUID(), clientSessionId)
      if (current !== token || currentEpoch !== epoch || opened.deviceId !== deviceId) {
        await end(opened)
        return
      }
      session = opened
      publish()
    },
    send(command: Input) {
      if (leaving > 0) return
      const current = token, target = session
      if (!target || target.state === 'closed') return
      const payload = { ...command, generation: target.generation, sequence: ++sequence }
      queue = queue.then(async () => {
        if (current !== token || !session || session.id !== target.id) return
        const next = await api.input(target.id, payload)
        if (current !== token || !session || session.id !== target.id || session.generation !== target.generation) return
        session = next
        publish()
      })
    },
    async leave() {
      const target = session
      const current = token
      leaving += 1
      epoch += 1
      sequence = 0
      try {
        await queue
      } finally {
        leaving -= 1
        if (token === current) {
          token += 1
          session = null
          if (target) publish()
          if (target) await end(target)
        }
      }
    },
    async flush() { await queue },
    async heartbeat() {
      const current = token, currentEpoch = epoch, target = session
      if (!target) return
      const next = await api.heartbeat(target.id, clientSessionId, target.generation)
      if (current !== token || currentEpoch !== epoch || !session || session.id !== target.id || session.deviceId !== target.deviceId || session.generation !== target.generation) return
      session = next
      publish()
    },
    subscribe(listener: (value: Session | null) => void) { listeners.add(listener); return () => listeners.delete(listener) },
    async dispose() { await this.leave(); listeners.clear() },
    get session() { return session },
  }
}
