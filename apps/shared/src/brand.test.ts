import { describe, expect, it } from 'vitest'

import { brand, brandCatalog, PRODUCT_NAME } from './brand'

describe('brand', () => {
  it('names the product tuos in copy written for Hermes, in any language', () => {
    expect(brand('Hermes is restarting')).toBe('tuos is restarting')
    expect(brand('Welcome to Hermes Agent!')).toBe('Welcome to tuos!')
    expect(brand('Hermes-Sitzung')).toBe('tuos-Sitzung')
    expect(brand('Hermesを再起動')).toBe('tuosを再起動')
    expect(brand('Run `hermes setup`, then hermes -p work chat')).toBe('Run `tuos setup`, then tuos -p work chat')
    expect(brand('then run hermes {profile_arg}sessions recover')).toBe('then run tuos {profile_arg}sessions recover')
    expect(brand('docker exec -u hermes hermes-agent hermes pairing approve telegram ABC')).toBe(
      'docker exec -u hermes hermes-agent tuos pairing approve telegram ABC'
    )
  })

  it('keeps Nous services and models, the wake word, credit to upstream and internal names', () => {
    for (const text of [
      'Managed by Hermes Cloud',
      'Nous Research Hermes 3 & 4 models',
      'Hermes-4-405B',
      "Toggle the 'Hey Hermes' wake word",
      'Built on Hermes Agent by Nous Research',
      'Edit ~/.hermes/config.yaml or HERMES_HOME; pip install hermes-agent; python -m hermes_cli',
      'Logs are in ~/Library/Application Support/Hermes/logs; quit Hermes.app first',
      'Certificate name (default: Hermes Local Signing)',
      'Send the X-Hermes-Session-Id header',
      "Load the `hermes-agent` skill with skill_view(name='hermes-agent')",
      'HermesDesktop',
      // The `hermes` user and group the Docker image and the Nix module run as
      'creates the `hermes` user and adds you to the `hermes` group',
      'docker exec -u hermes hermes-agent sh; sudo -u hermes cat .env; su - hermes',
      'pass `--user hermes`, or `s6-setuidgid hermes`; state is `0750 hermes:hermes`',
      'the entrypoint drops to hermes via s6, and the reconciler runs as hermes',
      "Added to the hermes user's profile"
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

  it('leaves the values a catalog function interpolates as they are', () => {
    const catalog = brandCatalog({
      renamed: (name: string) => `Hermes renamed the profile to ${name}`,
      failed: (reason: string) => `The gateway couldn't restart: ${reason}`
    })

    expect(catalog.renamed('Hermes Lab')).toBe('tuos renamed the profile to Hermes Lab')
    expect(catalog.failed('run `hermes pm repair`')).toBe("The gateway couldn't restart: run `hermes pm repair`")
  })
})
