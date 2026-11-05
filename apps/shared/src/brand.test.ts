import { describe, expect, it } from 'vitest'

import { brand, brandCatalog, PRODUCT_NAME } from './brand'

describe('brand', () => {
  it('names the product tuos in copy written for Hermes, in any language', () => {
    expect(brand('Hermes is restarting')).toBe('tuos is restarting')
    expect(brand('Welcome to Hermes Agent!')).toBe('Welcome to tuos!')
    expect(brand('Hermes-Sitzung')).toBe('tuos-Sitzung')
    expect(brand('Hermesを再起動')).toBe('tuosを再起動')
  })

  it('keeps Nous services and models, the wake word, credit to upstream and internal names', () => {
    for (const text of [
      'Managed by Hermes Cloud',
      'Nous Research Hermes 3 & 4 models',
      'Hermes-4-405B',
      "Toggle the 'Hey Hermes' wake word",
      'Built on Hermes Agent by Nous Research',
      'Run `hermes setup` and edit ~/.hermes/config.yaml or HERMES_HOME',
      'HermesDesktop'
    ]) {
      expect(brand(text)).toBe(text)
    }
  })

  it('rebrands every string of a catalog, including what its functions return', () => {
    const catalog = brandCatalog({
      title: 'Hermes',
      nested: { placeholders: ['Ask Hermes…'], sessions: (count: number) => `${count} Hermes sessions` }
    })

    expect(catalog.title).toBe(PRODUCT_NAME)
    expect(catalog.nested.placeholders).toEqual(['Ask tuos…'])
    expect(catalog.nested.sessions(2)).toBe('2 tuos sessions')
  })
})
