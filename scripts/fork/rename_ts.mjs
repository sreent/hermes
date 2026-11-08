#!/usr/bin/env node
/**
 * The TypeScript half of scripts/fork/rename.py (FORK.md, "Rebranded as tuos"): applies
 * apps/shared/src/brand.ts to copy the desktop app, its setup installer, the web dashboard, the TUI
 * and the docs site show that is written into their code rather than their translation catalogs (each
 * app brands those as it loads them).
 *
 * Renamed: JSX text; JSX attributes, object properties, variables and function results whose names
 * say they hold copy (title, label, message, description, hint, ...); error messages; calls that
 * refuse, fail or report progress. Never: logs, keys, comparisons, regular expressions, commands the
 * code runs or scripts it sends to a shell, and text other code matches on (`KEEP`).
 *
 * Tests follow (`followTest`): an expectation quoting copy that now reads renamed is renamed with it.
 *
 * Needs the repository's node_modules (`pnpm install --frozen-lockfile`) for the TypeScript parser.
 *
 *     node scripts/fork/rename_ts.mjs             # rewrite; prints the files it changed
 *     node scripts/fork/rename_ts.mjs --check     # change nothing; prints the files it would change
 *     node scripts/fork/rename_ts.mjs --report    # also list, on stderr, strings left as they are
 *     node scripts/fork/rename_ts.mjs --stdin PATH   # print stdin renamed as PATH would be (rename.py --resolve)
 *
 * rename.py passes the backend's renamed strings (`--backend-renames FILE`, JSON `[{at, old, new}]`) so
 * that a regular expression or a matcher here that recognised a backend message, and would no longer,
 * is named as a conflict too.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ts = createRequire(path.join(ROOT, 'package.json'))('typescript')

const ROOTS = [
  'apps/desktop/src',
  'apps/desktop/electron',
  'apps/bootstrap-installer/src',
  'web/src',
  'ui-tui/src',
  'website/src',
  'website/sidebars.ts'
]
let PRODUCT_NAME = 'tuos' // read from brand.ts in main()
const TEST = /\.(test|spec)\.(ts|tsx)$/
// Tests, fixtures and translation catalogs (branded where they load).
const SKIP = /\.(test|spec|stories)\.|__tests__|\/tests?\/|\/e2e\/|fixture|\.d\.ts$|\/i18n\/|\/i18n\.ts$/
// Text that keeps its wording: code elsewhere matches on it, or it names something that is not the
// product (Nous's models and services, the `hermes` executable).
const KEEP = [
  'hermes gateway ensure produced no result', // matched in apps/desktop/src/lib/local-gateway-ensure-failure.ts
  'Hosted Hermes & Nous-trained models', // Nous Portal's models
  'Hermes Flow', // the service that starts `hermes_flow` sessions
  'full path to the `hermes` binary', // the executable a remote path must name
  'Hermes Agent community', // upstream's community showcase on the docs site
  'Built something with Hermes?' // ...and its call for more stories
]

// Files whose regular expressions read process command lines or file names, not messages: no renamed
// copy can break them.
const NOT_MESSAGE_PATTERNS = new Set([
  'apps/desktop/electron/backend-ownership.ts',
  'apps/desktop/electron/package-process-reap.ts',
  'apps/desktop/electron/venv-holder-select.ts',
  'apps/desktop/electron/windows-hermes-path.ts'
])

// Words that, in a name, say it holds copy: `title`, `closedErrorMessage`, `FIELD_DESCRIPTIONS`,
// `missingInstallPartMessage()`, `defineFieldCopy({...})`.
const COPY_WORDS = new Set(`aria alt banner caption copy description descriptions detail details error
  errors explanation failure headline help hint hints html humanize instruction instructions intro
  label labels lead message messages note notice page placeholder reason refusal remedy status
  subtitle summary text title toast tooltip warning`.split(/\s+/))
// Words that say it holds data, even inside copy: `{ label: ..., command: 'hermes ...' }`.
const DATA_WORDS = new Set(`args argv cmd command commands env header headers href id key kind path
  pattern prompt script shell src type url`.split(/\s+/))
// Calls whose arguments are shown to a person (besides anything named ...Error).
const COPY_CALLS = new Set(`advanceBootProgress fail invalidate refuse reject showErrorBox speak
  withTimeout writeLine`.split(/\s+/))
// Transformations a copy expression may pass through: `[...].filter(Boolean).join('\n').trim()`.
const CHAIN = new Set(['concat', 'filter', 'join', 'trim', 'trimEnd', 'trimStart'])

const words = name => name.replace(/([a-z0-9])([A-Z])/g, '$1 $2').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean)
const nameSays = (name, set) => words(name).some(word => set.has(word))
const holdsCopy = name => nameSays(name, COPY_WORDS) && !nameSays(name, DATA_WORDS)

async function loadBrand() {
  const source = readFileSync(path.join(ROOT, 'apps/shared/src/brand.ts'), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
  })

  return import(`data:text/javascript,${encodeURIComponent(outputText)}`)
}

function nodeName(node) {
  const name = node?.name

  return name && (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isPrivateIdentifier(name)) ? name.text : ''
}

function calleeName(call) {
  const callee = call.expression

  if (ts.isIdentifier(callee)) {
    return callee.text
  }

  if (ts.isPropertyAccessExpression(callee)) {
    const owner = callee.expression

    // console.error(...), log.warn(...), logger.info(...): logs, not copy.
    return ts.isIdentifier(owner) && /^(console|log|logger|logging)$/i.test(owner.text) ? '' : callee.name.text
  }

  return callee.kind === ts.SyntaxKind.SuperKeyword ? superClassName(call) : ''
}

function superClassName(call) {
  let node = call

  while (node && !ts.isClassLike(node)) {
    node = node.parent
  }

  const heritage = node?.heritageClauses?.find(clause => clause.token === ts.SyntaxKind.ExtendsKeyword)

  return heritage?.types[0]?.expression.getText() ?? ''
}

function functionName(fn) {
  if (nodeName(fn)) {
    return nodeName(fn)
  }

  let node = fn.parent

  // `const updateConfirmDescription = useMemo(() => ...)`, `labels = items.map(item => ...)`.
  while (node && (ts.isParenthesizedExpression(node) || ts.isCallExpression(node) || ts.isAsExpression(node))) {
    node = node.parent
  }

  return ts.isVariableDeclaration(node) || ts.isPropertyAssignment(node) || ts.isPropertyDeclaration(node)
    ? nodeName(node)
    : ''
}

function enclosingFunction(node) {
  while (node && !ts.isFunctionLike(node)) {
    node = node.parent
  }

  return node
}

const passesThrough = (parent, child) =>
  ts.isParenthesizedExpression(parent) ||
  ts.isAsExpression(parent) ||
  ts.isSatisfiesExpression(parent) ||
  ts.isNonNullExpression(parent) ||
  ts.isTemplateSpan(parent) ||
  ts.isTemplateExpression(parent) ||
  ts.isArrayLiteralExpression(parent) ||
  ts.isObjectLiteralExpression(parent) ||
  ts.isSpreadElement(parent) ||
  (ts.isConditionalExpression(parent) && child !== parent.condition) ||
  (ts.isBinaryExpression(parent) &&
    [ts.SyntaxKind.PlusToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(
      parent.operatorToken.kind
    ))

const MATCH_CALLS = new Set(`endsWith every filter find has includes indexOf lastIndexOf match matchAll
  replace replaceAll search some split startsWith test`.split(/\s+/))
const EQUALITY = new Set([ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken])

/** Whether code matches text against the string at `node`: a comparison, a `case`, a search, a list. */
function isMatcher(node) {
  let child = node

  for (let parent = node.parent; parent; child = parent, parent = parent.parent) {
    if (ts.isArrayLiteralExpression(parent) || ts.isCaseClause(parent)) {
      return true
    }

    if (ts.isBinaryExpression(parent) && EQUALITY.has(parent.operatorToken.kind)) {
      return true
    }

    if (ts.isCallExpression(parent)) {
      const callee = parent.expression

      return ts.isPropertyAccessExpression(callee) && MATCH_CALLS.has(callee.name.text)
    }

    if (!passesThrough(parent, child)) {
      return false
    }
  }

  return false
}

/** Whether the string at `node` is shown to a person, judged by where it flows. */
function isCopy(node) {
  let child = node

  for (let parent = node.parent; parent; child = parent, parent = parent.parent) {
    if (passesThrough(parent, child) || ts.isJsxExpression(parent)) {
      continue
    }

    if (ts.isJsxElement(parent) || ts.isJsxFragment(parent)) {
      return true
    }

    if (ts.isJsxAttribute(parent)) {
      return holdsCopy(parent.name.getText())
    }

    if (ts.isPropertyAccessExpression(parent) && CHAIN.has(parent.name.text) && parent.parent.expression === parent) {
      child = parent
      parent = parent.parent // the chained call; keep climbing from it

      continue
    }

    // `LABELS = new Map([[key, 'copy'], ...])`: the variable says what the values are.
    if (ts.isNewExpression(parent) && parent.expression.getText() === 'Map') {
      continue
    }

    if (ts.isCallExpression(parent) || ts.isNewExpression(parent)) {
      const callee = parent.expression === child ? '' : calleeName(parent)

      return /Error$/.test(callee) || COPY_CALLS.has(callee) || holdsCopy(callee)
    }

    if (ts.isPropertyAssignment(parent) || ts.isPropertyDeclaration(parent) || ts.isVariableDeclaration(parent)) {
      if (child === parent.name || nameSays(nodeName(parent), DATA_WORDS)) {
        return false
      }

      if (holdsCopy(nodeName(parent))) {
        return true
      }

      if (ts.isVariableDeclaration(parent) || ts.isPropertyDeclaration(parent)) {
        return false
      }

      continue // a property of an object that may itself hold copy: `FIELD_DESCRIPTIONS = { browser: { ... } }`
    }

    if (ts.isReturnStatement(parent) || (ts.isArrowFunction(parent) && child === parent.body)) {
      return holdsCopy(functionName(enclosingFunction(parent)))
    }

    // `document.title = ...`, `message = ...`
    if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.EqualsToken && child === parent.right) {
      const target = parent.left

      return holdsCopy(ts.isPropertyAccessExpression(target) ? target.name.text : ts.isIdentifier(target) ? target.text : '')
    }

    return false
  }

  return false
}

/** The literal's text as written (escapes included), without its quotes or template delimiters. */
function rawSpan(node, sourceFile) {
  const start = node.getStart(sourceFile)
  const end = node.getEnd()

  if (ts.isJsxText(node)) {
    return [start, end]
  }

  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    return [start + 1, end - 1]
  }

  // TemplateHead `...${, TemplateMiddle }...${, TemplateTail }...`
  return [start + 1, end - (ts.isTemplateTail(node) ? 1 : 2)]
}

const isText = node =>
  ts.isStringLiteral(node) ||
  ts.isNoSubstitutionTemplateLiteral(node) ||
  ts.isTemplateHead(node) ||
  ts.isTemplateMiddle(node) ||
  ts.isTemplateTail(node) ||
  ts.isJsxText(node)

const ENTITIES = { '&lt;': '<', '&gt;': '>', '&amp;': '&', '&apos;': "'", '&quot;': '"', '&nbsp;': ' ' }
const decodeEntities = text => text.replace(/&(lt|gt|amp|apos|quot|nbsp);/g, entity => ENTITIES[entity])

// brand() over a regular expression's source: escapes (`\.`, `\s`) stand aside so "Hermes\." reads as a word.
function brandPattern(source, brand) {
  const escapes = []
  const masked = source.replace(/\\./g, escape => String.fromCharCode(0xe000 + escapes.push(escape) - 1))

  return brand(masked).replace(/[\ue000-\uf8ff]/g, mark => escapes[mark.charCodeAt(0) - 0xe000])
}

function scan(file, text, brand) {
  const sourceFile = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
    file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const renamed = []
  const left = []
  const patterns = []
  const shown = [] // copy as it reads once renamed, for tests to follow

  const visit = node => {
    if (ts.isRegularExpressionLiteral(node) && /hermes/i.test(node.text)) {
      patterns.push(node)
    }

    if (isText(node)) {
      const [start, end] = rawSpan(node, sourceFile)
      const raw = text.slice(start, end)
      const branded = brand(raw)
      // A kept phrase keeps its whole template: its pieces are one message.
      const whole = ts.isTemplateLiteralToken(node) && !ts.isNoSubstitutionTemplateLiteral(node)
        ? (ts.isTemplateHead(node) ? node.parent : node.parent.parent).getText(sourceFile) : raw
      const keep = KEEP.some(phrase => whole.includes(phrase))
      const copy = !keep && isCopy(node)

      if (branded !== raw) {
        ;(copy ? renamed : left).push({ start, end, raw, branded, node })
      }

      if (copy) {
        shown.push(brand(ts.isJsxText(node) ? decodeEntities(node.text) : node.text))
      }
    }

    ts.forEachChild(node, visit)
  }

  visit(sourceFile)

  return { sourceFile, renamed, left, patterns, shown }
}

// Where a test states what it expects to see. `search`: the text is looked for inside the output;
// `equal`: it must be the output, so only prose naming the product follows (an exact command or name
// is as often data the code returns).
const SEARCH_MATCHERS = new Set(['toContain', 'toMatch', 'toThrow', 'toThrowError', 'toHaveTextContent'])
const EQUAL_MATCHERS = new Set(['toBe', 'toEqual', 'toStrictEqual', 'toMatchObject', 'toContainEqual', 'toHaveProperty',
  'toHaveBeenCalledWith', 'toHaveBeenLastCalledWith', 'toHaveBeenNthCalledWith'])
const QUERIES = /^(get|getAll|query|queryAll|find|findAll)By(Text|LabelText|Title|PlaceholderText|DisplayValue|AltText)$/
const ASSERT_EQUAL = new Set(['equal', 'strictEqual', 'deepEqual', 'deepStrictEqual', 'notEqual', 'notStrictEqual'])
const ASSERT_SEARCH = new Set(['match', 'doesNotMatch', 'throws', 'rejects'])

function expectation(call) {
  const callee = call.expression
  const name = ts.isPropertyAccessExpression(callee) ? callee.name.text : ts.isIdentifier(callee) ? callee.text : ''

  if (QUERIES.test(name)) {
    return { mode: 'search', args: call.arguments.slice(0, 1) }
  }

  if (!ts.isPropertyAccessExpression(callee)) {
    return null
  }

  if (ts.isIdentifier(callee.expression) && callee.expression.text === 'assert') {
    return ASSERT_EQUAL.has(name) ? { mode: 'equal', args: call.arguments.slice(1) }
      : ASSERT_SEARCH.has(name) ? { mode: 'search', args: call.arguments.slice(1) } : null
  }

  let base = callee.expression

  while (ts.isPropertyAccessExpression(base) && ['not', 'resolves', 'rejects'].includes(base.name.text)) {
    base = base.expression
  }

  const fromExpect = ts.isCallExpression(base) && ts.isIdentifier(base.expression) && base.expression.text === 'expect'

  return !fromExpect ? null
    : SEARCH_MATCHERS.has(name) ? { mode: 'search', args: call.arguments }
    : EQUAL_MATCHERS.has(name) ? { mode: 'equal', args: call.arguments } : null
}

// `expect(out.includes('...'))`, `assert.ok(out.includes('...'))`: a search inside an assertion.
const insideAssertion = node => {
  for (let parent = node.parent; parent && !ts.isBlock(parent); parent = parent.parent) {
    if (ts.isCallExpression(parent) && /^(expect|assert)\b/.test(parent.expression.getText())) {
      return true
    }
  }

  return false
}

function expectedTexts(sourceFile) {
  const found = []
  const collect = (node, mode) => {
    if (isText(node) || ts.isRegularExpressionLiteral(node)) {
      found.push({ node, mode })
    } else if (ts.isConditionalExpression(node)) {
      collect(node.whenTrue, mode)
      collect(node.whenFalse, mode)
    } else if (ts.isTemplateExpression(node) || ts.isArrayLiteralExpression(node) || ts.isObjectLiteralExpression(node) ||
        ts.isPropertyAssignment(node) || ts.isTemplateSpan(node) || ts.isParenthesizedExpression(node)) {
      ts.forEachChild(node, child => (ts.isPropertyAssignment(node) && child === node.name ? null : collect(child, mode)))
    }
  }
  const visit = node => {
    if (ts.isCallExpression(node)) {
      const expected = expectation(node)

      if (expected) {
        expected.args.forEach(arg => collect(arg, expected.mode))
      } else if (ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'includes' &&
          node.arguments.length && insideAssertion(node)) {
        collect(node.arguments[0], 'search')
      }
    }

    ts.forEachChild(node, visit)
  }

  visit(sourceFile)

  return found
}

/** A test's expectations quoting copy that now reads renamed (`produced.shown`) renamed with it. Not when
 *  the apps still keep that wording somewhere (`produced.kept`), or when the test passes the same text
 *  in itself: then it checks its own input comes through. */
function followTest(file, text, produced, brand) {
  const sourceFile = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
    file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const expected = expectedTexts(sourceFile)
  const expectedNodes = new Set(expected.map(({ node }) => node))
  const inputs = []
  // A test's title describes it: `it('names ... hermes doctor', ...)` feeds nothing in.
  const title = node => ts.isCallExpression(node.parent) && node.parent.arguments[0] === node &&
    /^(it|test|describe)(\.(each|only|skip|concurrent))?$/.test(node.parent.expression.getText(sourceFile))
  const collectInputs = node => {
    if (isText(node) && !expectedNodes.has(node) && !title(node)) {
      inputs.push(node.text)
    }

    ts.forEachChild(node, collectInputs)
  }

  collectInputs(sourceFile)

  const edits = []

  for (const { node, mode } of expected) {
    const regex = ts.isRegularExpressionLiteral(node)
    const flags = regex ? node.text.slice(node.text.lastIndexOf('/') + 1).replace(/[gy]/g, '') : ''
    const [start, end] = regex ? [node.getStart(sourceFile) + 1, node.getStart(sourceFile) + node.text.lastIndexOf('/')]
      : rawSpan(node, sourceFile)
    const raw = text.slice(start, end)
    const branded = regex ? brandPattern(raw, brand) : brand(raw)
    const cooked = regex ? raw : node.text

    if (branded === raw || cooked.trim().length < 8 || !/[A-Za-z]{3}/.test(branded.split(PRODUCT_NAME).join('')) ||
        (mode === 'equal' && !/\bHermes\b/.test(cooked))) {
      continue
    }

    let follows = false

    try {
      const matches = regex ? source => new RegExp(source, flags) : null

      follows = regex
        ? matches(branded).test(produced.shown) && !matches(raw).test(produced.kept) && !inputs.some(input => matches(raw).test(input))
        : produced.shown.includes(brand(cooked)) && !produced.kept.includes(cooked) &&
          !inputs.some(input => input.includes(cooked) && brand(input).includes(brand(cooked)))
    } catch {
      follows = false
    }

    if (follows) {
      edits.push({ start, end, branded })
    }
  }

  return applyRenames(text, edits)
}

const where = (file, sourceFile, node) => `${file}:${sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1}`

const inScope = file =>
  /\.(ts|tsx)$/.test(file) && !SKIP.test(file) && ROOTS.some(root => file === root || file.startsWith(`${root}/`))

function applyRenames(text, renamed) {
  for (const { start, end, branded } of [...renamed].sort((a, b) => b.start - a.start)) {
    text = text.slice(0, start) + branded + text.slice(end)
  }

  return text
}

const git = (...args) => execFileSync('git', args, { cwd: ROOT, encoding: 'utf8' }).split('\n')

// Once each: mid-merge, ls-files lists a conflicted file once per side. A file a merge left conflicted
// holds both sides between markers: it is renamed once resolved.
const listed = () => {
  const unmerged = new Set(git('diff', '--name-only', '--diff-filter=U'))

  return [...new Set(git('ls-files', '--', ...ROOTS))].filter(file => !unmerged.has(file))
}
const isTest = file => TEST.test(file) && !/fixture/.test(file)
const read = file => readFileSync(path.join(ROOT, file), 'utf8')

/** Copy the apps show once renamed, joined: what a test's expectation may quote. */
// What the apps show once renamed, and the Hermes wording they keep, each joined. Catalogs are left out:
// they are branded where they load, which a test rendering them directly may not do.
const producedFrom = scans => ({
  shown: scans.flatMap(({ shown }) => shown).join('\0'),
  kept: scans.flatMap(({ left }) => left.map(entry => entry.node.text ?? entry.raw)).join('\0')
})

async function main() {
  const argv = process.argv.slice(2)
  const args = new Set(argv)
  const module = await loadBrand()
  const { brand } = module

  PRODUCT_NAME = module.PRODUCT_NAME

  if (args.has('--stdin')) {
    const file = argv[argv.indexOf('--stdin') + 1]
    const text = readFileSync(0, 'utf8')
    const scanAll = () => listed().filter(inScope).map(name => scan(name, read(name), brand))

    process.stdout.write(
      isTest(file) && ROOTS.some(root => file.startsWith(`${root}/`)) ? followTest(file, text, producedFrom(scanAll()), brand)
        : inScope(file) ? applyRenames(text, scan(file, text, brand).renamed) : text
    )

    return 0
  }

  const files = listed().filter(inScope)
  const scans = files.map(file => ({ file, ...scan(file, read(file), brand) }))

  // Text renamed in one place but matched as it was in another breaks the match: name it. A phrase
  // counts when it is a sentence's worth (`KEEP` holds the ones resolved by keeping the wording).
  const kept = scans.flatMap(({ file, sourceFile, left }) => left.map(entry => ({ ...entry, at: where(file, sourceFile, entry.node) })))
  const phrase = text => text.trim().length >= 16 && /\S\s+\S/.test(text)
  const overlaps = (a, b) => (a.includes(b) && phrase(b)) || (b.includes(a) && phrase(a))
  const conflicts = scans.flatMap(({ file, sourceFile, renamed }) =>
    renamed.flatMap(entry =>
      kept
        .filter(other => isMatcher(other.node) && overlaps(entry.raw, other.raw))
        .map(other => `${where(file, sourceFile, entry.node)} renames text ${other.at} keeps: ${JSON.stringify(other.raw)}`)
    )
  )

  for (const { file, renamed } of scans) {
    if (renamed.length === 0) {
      continue
    }

    process.stdout.write(`${file}\n`)

    if (!args.has('--check')) {
      writeFileSync(path.join(ROOT, file), applyRenames(readFileSync(path.join(ROOT, file), 'utf8'), renamed))
    }
  }

  // Tests follow: an expectation quoting copy that now reads renamed is renamed with it.
  const produced = producedFrom(scans)

  for (const file of listed().filter(isTest)) {
    const text = read(file)
    const followed = followTest(file, text, produced, brand)

    if (followed !== text) {
      process.stdout.write(`${file}\n`)

      if (!args.has('--check')) {
        writeFileSync(path.join(ROOT, file), followed)
      }
    }
  }

  // Regular expressions that mention Hermes, and matchers, against every renamed string (the backend's
  // too): one that recognised the old wording and misses the new is a broken match.
  const backendFile = argv[argv.indexOf('--backend-renames') + 1]
  const pairs = [
    ...(args.has('--backend-renames') ? JSON.parse(readFileSync(backendFile, 'utf8')) : []),
    ...scans.flatMap(({ file, sourceFile, renamed }) =>
      renamed.map(entry => ({ at: where(file, sourceFile, entry.node), old: entry.raw, new: entry.branded })))
  ]
  const tests = [
    ...scans.filter(({ file }) => !NOT_MESSAGE_PATTERNS.has(file)).flatMap(({ file, sourceFile, patterns }) => patterns.map(node => {
      const source = node.text.slice(1, node.text.lastIndexOf('/'))
      // Case-sensitively: /^hermes(\.exe)?$/i looks for the executable, not the product named in prose.
      const pattern = new RegExp(source, node.text.slice(node.text.lastIndexOf('/') + 1).replace(/[gyi]/g, ''))

      return { at: where(file, sourceFile, node), shown: node.text, matches: text => pattern.test(text) }
    })),
    ...kept.filter(other => isMatcher(other.node) && phrase(other.raw))
      .map(other => ({ at: other.at, shown: JSON.stringify(other.raw), matches: text => text.includes(other.raw) }))
  ]

  // A sentence's worth, as above: a bare "Hermes" heading is no message a pattern reads.
  for (const pair of pairs.filter(pair => phrase(pair.old))) {
    for (const test of tests.filter(test => test.matches(pair.old) && !test.matches(pair.new))) {
      conflicts.push(`${pair.at} renames text ${test.at} matches: ${test.shown}`)
    }
  }

  for (const conflict of [...new Set(conflicts)]) {
    process.stderr.write(`conflict: ${conflict}\n`)
  }

  if (args.has('--report')) {
    for (const { at, raw } of kept) {
      process.stderr.write(`left: ${at}: ${JSON.stringify(raw.trim().slice(0, 100))}\n`)
    }

    for (const { file, sourceFile, patterns } of scans) {
      for (const node of patterns) {
        process.stderr.write(`pattern: ${where(file, sourceFile, node)}: ${node.text}\n`)
      }
    }
  }

  return conflicts.length ? 3 : 0
}

process.exitCode = await main()
