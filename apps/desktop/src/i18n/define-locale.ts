import { brandCatalog } from '@hermes/shared/brand'
import { mergeTranslations, type TranslationOverride } from '@hermes/shared/i18n'

import { en } from './en'
import type { Translations } from './types'

export type TranslationOverrides = TranslationOverride<Translations>

// tuos (FORK.md): translated copy written for Hermes names the product, as `en` does.
export const defineLocale = (overrides: TranslationOverrides): Translations =>
  brandCatalog(mergeTranslations<Translations>(en, overrides))
