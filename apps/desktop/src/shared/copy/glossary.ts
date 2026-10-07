import glossaryJson from './glossary.json'

export interface GlossaryEntry {
  term: string
  preferred: string
  reason: string
  allowedIn: string[]
}

export const glossary: readonly GlossaryEntry[] = glossaryJson
