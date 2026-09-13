import { useLayoutEffect, useRef, useState } from 'react'
import type { components } from '../../shared/api/generated'
import type { SchemaFieldDraft } from './components/SchemaFieldDrawer'
import type { SchemaCandidate } from './schema-api'
import { applySchemaField, createSchemaDraft, sameSchema, schemaChanges } from './schema-draft'

type Options = {
  sessionKey: string
  generation: string
  directory: components['schemas']['DataFieldDirectory']
  restoredCandidate?: SchemaCandidate
}
export function useSchemaDraft({ sessionKey, generation, directory, restoredCandidate }: Options) {
  const [baseline, setBaseline] = useState(() => createSchemaDraft(generation, directory))
  const [candidate, setCandidate] = useState(() => structuredClone(restoredCandidate ?? baseline))
  const session = useRef(sessionKey)
  const dirty = !sameSchema(baseline, candidate)
  useLayoutEffect(() => {
    const changedSession = session.current !== sessionKey
    session.current = sessionKey
    if (changedSession || !dirty) {
      const next = createSchemaDraft(generation, directory)
      if (changedSession || !sameSchema(baseline, next)) {
        setBaseline(next)
        setCandidate(structuredClone(changedSession && restoredCandidate ? restoredCandidate : next))
      }
    }
  }, [sessionKey, generation, directory, restoredCandidate, dirty, baseline])
  return {
    candidate, baseline, dirty, changes: schemaChanges(baseline, candidate),
    apply: (id: string | null, draft: SchemaFieldDraft) => setCandidate(applySchemaField(candidate, id, draft)),
    reset: () => { const next = createSchemaDraft(generation, directory); setBaseline(next); setCandidate(structuredClone(next)) },
  }
}
