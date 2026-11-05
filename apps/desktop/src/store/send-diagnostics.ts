// "Save Diagnostics" — the error card's consent-gated debug-bundle archive.
//
// Flow: an error card (or any surface) calls requestSendDiagnostics() with
// optional error context → the modal host renders the privacy notice → the
// user explicitly clicks Save → diagnostics.save runs backend-side (collect +
// force-redact + write a zip under the profile's logs) → the modal shows the
// archive's path plus where to report the problem. Nothing is uploaded
// (FORK.md).
//
// Consent is per-save and explicit, mirroring `hermes debug share`. On a
// remote connection the backend bundles ITS OWN logs (the runtime that owns
// the failure) and saves the archive on that machine; the local desktop.log
// is attached as a client-side extra so the archive holds both halves.

import { atom } from 'nanostores'

import { $gateway } from '@/store/gateway'

export interface SendDiagnosticsResult {
  /** Where the backend saved the archive (on the machine running Hermes). */
  path?: string
}

export interface SendDiagnosticsState {
  /** Short text describing the failure that prompted the report (attached
   *  to the bundle as error-context.txt, redacted server-side). */
  errorContext?: string
  error?: string
  /** Client-side files (label → text) the requesting surface attaches, e.g.
   *  the update output it showed. Redacted and size-capped server-side. */
  extraFiles?: Record<string, string>
  /** The requesting surface renders the flow itself (the update error box
   *  shows the result where the failure is), so the global modal stays closed. */
  inline?: boolean
  phase: 'consent' | 'done' | 'error' | 'saving'
  result?: SendDiagnosticsResult
}

export interface SendDiagnosticsOptions {
  extraFiles?: Record<string, string>
  inline?: boolean
}

export const $sendDiagnostics = atom<SendDiagnosticsState | null>(null)

// Generation token: bumped on every open AND every dismiss. An in-flight
// save captures the generation it started under and only writes its
// completion back when the token still matches — so dismissing mid-save is
// immediate and a stale completion can't resurrect or overwrite the dialog.
// Request cancellation stays best-effort (the WS call runs to completion
// server-side; we just ignore the result).
let generation = 0

/** Open the consent modal. Nothing is collected until the user confirms. */
export function requestSendDiagnostics(errorContext?: string, options: SendDiagnosticsOptions = {}): void {
  generation += 1
  $sendDiagnostics.set({ errorContext, phase: 'consent', ...options })
}

export function dismissSendDiagnostics(): void {
  generation += 1
  $sendDiagnostics.set(null)
}

interface SaveDiagnosticsResponse {
  error?: string
  ok: boolean
  path?: string
}

/** Read the LOCAL desktop log via Electron so a remote backend's bundle still
 *  carries the Desktop-side transport evidence. Best-effort: absence of the
 *  IPC (browser dashboard, older shells) just omits the file. */
async function collectLocalExtras(): Promise<Record<string, string>> {
  try {
    const logs = await window.hermesDesktop?.getRecentLogs?.()
    const lines = Array.isArray(logs?.lines) ? logs.lines : []

    return lines.length ? { 'desktop.log': lines.join('\n') } : {}
  } catch {
    return {}
  }
}

// Bundle collection + archive write legitimately takes a while (log reads +
// zip); the default WS timeout is too tight for slow disks.
const SAVE_TIMEOUT_MS = 120_000

/** User confirmed — save the archive. Transitions consent → saving → done/error. */
export async function confirmSendDiagnostics(): Promise<void> {
  const current = $sendDiagnostics.get()

  if (!current || current.phase !== 'consent') {
    return
  }

  const startedGeneration = generation
  // Only write back while the dialog the save belongs to is still open.
  const stillCurrent = () => generation === startedGeneration

  $sendDiagnostics.set({ ...current, phase: 'saving' })

  try {
    const gateway = $gateway.get()

    if (!gateway) {
      throw new Error('Hermes gateway unavailable')
    }

    const extraFiles = { ...(await collectLocalExtras()), ...current.extraFiles }

    if (!stillCurrent()) {
      return
    }

    const response = await gateway.request<SaveDiagnosticsResponse>(
      'diagnostics.save',
      {
        ...(current.errorContext ? { error_context: current.errorContext } : {}),
        ...(Object.keys(extraFiles).length ? { extra_files: extraFiles } : {})
      },
      SAVE_TIMEOUT_MS
    )

    if (!stillCurrent()) {
      return
    }

    if (!response.ok || !response.path) {
      throw new Error(response.error || 'save failed')
    }

    $sendDiagnostics.set({ ...current, phase: 'done', result: { path: response.path } })
  } catch (error) {
    if (!stillCurrent()) {
      return
    }

    $sendDiagnostics.set({
      ...current,
      error: error instanceof Error ? error.message : String(error),
      phase: 'error'
    })
  }
}
