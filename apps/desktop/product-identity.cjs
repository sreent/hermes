// The desktop product identity — THE single source for every name-shaped
// value a variant owns. HERMES_DESKTOP_VARIANT=light builds "tuos Light",
// the remote-only client; everything else is full "tuos".
//
// Consumed at build time by electron-builder.config.cjs (packaging
// identity). electron/product-identity.ts is the typed runtime accessor.
// @ts-check
/// <reference types="node" />
'use strict'

// Who ships this fork (FORK.md, "Rebranded as tuos"): the reverse-DNS prefix of every appId and the
// organisation prefix of the MSIX package names. The out-of-store MSIX publisher, which must equal the
// signing certificate's subject, is OUT_OF_STORE_PUBLISHER in scripts/msix-shared.mjs.
const APP_ID_PREFIX = 'io.github.sreent'
const MSIX_ORG = 'Sreent'

// This fork's Microsoft Store package identity, from Partner Center's "Product identity" page:
// { identityName, publisher, publisherDisplayName }. Null until the fork has a Store listing; packaging a
// store build refuses without it (mustStoreMsix in electron-builder.config.cjs).
/** @type {NonNullable<ProductIdentity['storeMsix']> | null} */
const STORE_MSIX = null

const variants = {
  '': { display: 'tuos', kebab: 'tuos', pascal: 'Tuos' },
  light: {
    display: 'tuos Light',
    kebab: 'tuos-light',
    pascal: 'TuosLight'
  },
  bundled: {
    display: 'tuos Agent',
    kebab: 'tuos-bundled',
    pascal: 'TuosBundled'
  }
}

const variant = process.env.HERMES_DESKTOP_VARIANT || ''
if (!['', 'light', 'bundled', 'store'].includes(variant)) {
  throw new Error(`Unknown HERMES_DESKTOP_VARIANT ${variant}. expected one of (empty), light, bundled, store`)
}

// 'store' is a Store-submission packaging identity layered on the bundled
// variant: same Electron app (displayName/appId/appNamePascal -> shared
// userData + single-instance lock with the out-of-store install), different
// MSIX package identity. The Store re-signs on submission.
const store = variant === 'store'
const light = variant === 'light'
const name = variants[store ? 'bundled' : (variant || '')]

// The electron-updater feed channel this build PUBLISHES to. A canary
// tag (vX.Y.Z+canary.YYYYMMDDTHHMMSSZ) writes canary.yml / light-canary.yml;
// stable tags write latest.yml / light.yml. Keyed on the payload tag so
// the one release workflow serves both channels — a canary build can
// never overwrite the stable feed file, and vice versa.
const canary = /\+canary\.20\d{6}T\d{6}Z$/.test(process.env.HERMES_PAYLOAD_TAG || '')

// Nonstable installs own their package family and local desktop state. The
// seven-character commit suffix also names the CLI and fits MSIX's name cap.
// The payload CLI keeps the `hermes` command's name (tuos runs it).
const buildCommitEnv = process.env.HERMES_BUILD_COMMIT || ''
const buildCommit = /^[a-f0-9]{40}$/.test(buildCommitEnv) ? buildCommitEnv.slice(0, 7) : null
const displayName = buildCommit
  ? `${name.display} ${buildCommit}`
  : canary
    ? `${name.display} Canary`
    : name.display

const kebabSuffix = buildCommit ? `-${buildCommit}` : canary ? '-canary' : ''
const pascalSuffix = buildCommit ? `Commit${buildCommit}` : canary ? 'Canary' : ''
const cliName = `${light ? 'hermes-light' : 'hermes'}${kebabSuffix}`
if (store && (canary || buildCommit)) {
  throw new Error('Store packaging is only eligible for stable releases')
}

/** @typedef {import("./product-identity.d.cts")} ProductIdentity */

/** @type {ProductIdentity} */
const identity = {
  store,
  light,
  displayName,
  appId: `${APP_ID_PREFIX}.${name.kebab}${kebabSuffix}`,
  // Store and commit builds do not publish a release feed.
  channel: store || buildCommit ? null : light ? (canary ? 'light-canary' : 'light') : (canary ? 'canary' : 'latest'),
  appNamePascal: `${name.pascal}${pascalSuffix}`,
  artifactNamePascal: name.pascal,
  windowsExecutableName: kebabSuffix ? cliName : displayName,
  cliName,
  msixAppIdWithOrg: `${MSIX_ORG}.${name.pascal}${pascalSuffix}`,
  // Partner Center publisher identity (the account's publisher ID) — validated
  // + re-signed by the Store on submission.
  ...(store && STORE_MSIX ? { storeMsix: STORE_MSIX } : {})
}

const { channelBuildRequest } = require('../../scripts/msix-shared.mjs')
const request = channelBuildRequest()

// A channel created with --branding stable copies stable's identity, so it IS
// the regular app. It must also run like one: a token would make the runtime
// pin a userData dir and single-instance lock that installed stable doesn't use.
// The updater reads the token from the stamped request, not from this export.
const officialChannel =
  request !== null &&
  ['appId', 'displayName', 'appNamePascal', 'artifactNamePascal', 'windowsExecutableName', 'cliName', 'msixAppIdWithOrg'].every(
    key => request.identity[key] === identity[key]
  )

module.exports = !request
  ? identity
  : Object.freeze(
      officialChannel
        ? { ...identity, channel: request.channel }
        : { ...request.identity, store: false, light: false, channel: request.channel }
    )
