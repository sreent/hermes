/**
 * What people see is called tuos (FORK.md, "Rebranded as tuos"): the TypeScript twin of
 * `hermes_cli/distribution.py`'s `brand()`. Each app applies it where it resolves its translations,
 * so copy written for Hermes names the product tuos in every language, upstream's new strings
 * included. Free of the DOM and of imports: the TUI, Electron's main process, the desktop renderer
 * and the web dashboard all load it.
 */

export const PRODUCT_NAME = 'tuos'

// "Hermes Agent" or "Hermes" as a word, in any language's text (CJK puts letters right next to it).
// Not "Hermes Cloud", Nous Research's hosted service; a Nous model such as "Hermes 3" or
// "Hermes-4-405B"; the wake word "Hey Hermes", the phrase the voice listener actually hears; credit
// to upstream ("built on Hermes Agent", "based on Hermes Agent"); a path or app name
// ("Application Support/Hermes", "Hermes.app", "Hermes.exe"); the middle of a hyphenated name such as
// the X-Hermes-Session-Id header; or the macOS signing certificate's name in the keychain ("Hermes Local
// Signing").
const PRODUCT =
  /(?<![A-Za-z0-9_/\\])(?<!Hey )(?<![Bb]uilt on )(?<![Bb]ased on )(?!(?<=[A-Za-z0-9_]-)Hermes-[A-Za-z0-9_])Hermes(?:[ -]Agent(?![A-Za-z0-9_]))?(?![A-Za-z0-9_/\\])(?!\.[A-Za-z])(?![ -]?(?:Cloud|\d)| Local Signing)/g

// The command, wherever copy tells someone to run it: `hermes setup`, `hermes -p work ...`, a template's
// `hermes {profile_arg}doctor`, `hermes` in backticks, "the hermes command". Not a path, package or module
// (~/.hermes, /opt/hermes/, hermes-agent, hermes_cli, hermes.exe), nor the `hermes` user and group the
// Docker image and the Nix module run as ("the `hermes` user", "drops to hermes", `sudo -u hermes`, `--user hermes`,
// `s6-setuidgid hermes`, `chown hermes:hermes`), which keep their name.
const COMMAND =
  /(?<![A-Za-z0-9_./\\`:=-])(?<!-u )(?<!--user )(?<!setuidgid )(?<!chown )(?<!id -u )(?<!id -g )(?<!su - )(?<!to )(?<!as )hermes(?=\s(?:-{1,2}[A-Za-z]|[a-z{])|`)(?!`?\s(?:user|group|account)\b)|(?<=`)hermes(?=`|\s)(?!`?\s(?:user|group|account)\b)/g

export function brand(text: string): string {
  return text.replace(PRODUCT, PRODUCT_NAME).replace(COMMAND, PRODUCT_NAME)
}

/** A translation catalog (nested strings, string arrays, and functions returning those) with every
 *  string naming tuos. Function leaves keep their parameters; their results are rebranded, except the
 *  values they interpolate (a profile's name, a backend's message), which read as given. */
export function brandCatalog<T>(node: T): T {
  if (typeof node === 'string') {
    return brand(node) as T
  }

  if (typeof node === 'function') {
    const leaf = node as unknown as (...args: unknown[]) => unknown

    return ((...args: unknown[]) => brandResult(leaf(...args), args)) as T
  }

  if (Array.isArray(node)) {
    return node.map(item => brandCatalog(item)) as T
  }

  if (node && typeof node === 'object' && Object.getPrototypeOf(node) === Object.prototype) {
    return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, brandCatalog(value)])) as T
  }

  return node
}

function brandResult(result: unknown, args: unknown[]): unknown {
  if (typeof result !== 'string') {
    return brandCatalog(result)
  }

  // Values brand() would change stand aside (longest first) while the catalog's own wording is branded.
  const values = [...new Set(args.filter((arg): arg is string => typeof arg === 'string' && brand(arg) !== arg))]
    .sort((a, b) => b.length - a.length)
  const masked = values.reduce((text, value, index) => text.split(value).join(String.fromCharCode(0xe000 + index)), result)

  return brand(masked).replace(/[\ue000-\uf8ff]/g, mark => values[mark.charCodeAt(0) - 0xe000] ?? mark)
}
