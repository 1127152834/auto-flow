import { useSignatureStore } from '../hooks/stores/signatureStore'

export const SIGNATURE_INVALID_MESSAGE = '输入与输出里还有没填好的地方，请先修正'

/** What a save must do about the flow inputs: refuse an invalid draft (it would be lost silently), or carry the edited signature. */
export function signatureForSave(): { ok: false; message: string } | { ok: true; signature: Record<string, unknown> | undefined } {
  const state = useSignatureStore.getState()
  if (!state.canSave && !state.readOnly) return { ok: false, message: SIGNATURE_INVALID_MESSAGE }
  return { ok: true, signature: state.serialize() }
}
