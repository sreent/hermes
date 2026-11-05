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
// "Hermes-4-405B"; the wake word "Hey Hermes", the phrase the voice listener actually hears; or credit
// to upstream ("built on Hermes Agent", "based on Hermes Agent").
const PRODUCT =
  /(?<![A-Za-z0-9_])(?<!Hey )(?<![Bb]uilt on )(?<![Bb]ased on )Hermes(?:[ -]Agent(?![A-Za-z0-9_]))?(?![A-Za-z0-9_])(?![ -]?(?:Cloud|\d))/g

export function brand(text: string): string {
  return text.replace(PRODUCT, PRODUCT_NAME)
}

/** A translation catalog (nested strings, string arrays, and functions returning those) with every
 *  string naming tuos. Function leaves keep their parameters; their results are rebranded. */
export function brandCatalog<T>(node: T): T {
  if (typeof node === 'string') {
    return brand(node) as T
  }

  if (typeof node === 'function') {
    const leaf = node as unknown as (...args: unknown[]) => unknown

    return ((...args: unknown[]) => brandCatalog(leaf(...args))) as T
  }

  if (Array.isArray(node)) {
    return node.map(item => brandCatalog(item)) as T
  }

  if (node && typeof node === 'object' && Object.getPrototypeOf(node) === Object.prototype) {
    return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, brandCatalog(value)])) as T
  }

  return node
}
