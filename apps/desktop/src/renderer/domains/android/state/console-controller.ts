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
  let sequence = 0
  let queue = Promise.resolve()
  const listeners = new Set<(value: Session | null) => void>()
  const clientSessionId = `${identity.workspaceIdentity}:${identity.backendInstanceId}`
  const publish = () => listeners.forEach(listener => listener(session))
  return {
    async open(deviceId: string) {
      const current = ++token
      sequence = 0
      session = await api.session(deviceId, 'manual', crypto.randomUUID(), clientSessionId)
      if (current === token) publish()
    },
    send(command: Input) {
      const current = token, target = session
      if (!target || target.state === 'closed') return
      const payload = { ...command, generation: target.generation, sequence: ++sequence }
      queue = queue.then(async () => {
        if (current !== token || !session || session.id !== target.id) return
        session = await api.input(target.id, payload)
        publish()
      })
    },
    async leave() {
      const target = session
      await queue
      token += 1
      session = null
      publish()
      if (target && target.state !== 'closed') await api.action(target, 'end')
    },
    async flush() { await queue },
    async heartbeat() {
      if (session) { session = await api.heartbeat(session.id, clientSessionId, session.generation); publish() }
    },
    subscribe(listener: (value: Session | null) => void) { listeners.add(listener); return () => listeners.delete(listener) },
    async dispose() { await this.leave(); listeners.clear() },
    get session() { return session },
  }
}
