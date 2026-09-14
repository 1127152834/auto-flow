import type { Monaco } from '@monaco-editor/react'
import type { editor, languages } from 'monaco-editor'

/** Monaco providers are global; bind workflow hints to this editor and its lifetime. */
export function registerEditorCompletions(
  instance: editor.IStandaloneCodeEditor,
  monaco: Monaco,
  language: string,
  provider: languages.CompletionItemProvider,
) {
  const scoped: languages.CompletionItemProvider = {
    ...provider,
    provideCompletionItems(model, position, context, token) {
      if (model !== instance.getModel()) return { suggestions: [] }
      return provider.provideCompletionItems(model, position, context, token)
    },
  }
  const registration = monaco.languages.registerCompletionItemProvider(language, scoped)
  instance.onDidDispose(() => registration.dispose())
}
