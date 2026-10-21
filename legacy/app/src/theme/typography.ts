import {
  Figtree_300Light,
  Figtree_300Light_Italic,
  Figtree_400Regular,
  Figtree_600SemiBold,
} from '@expo-google-fonts/figtree';
import type { TextStyle } from 'react-native';

/**
 * The single font setting.
 *
 * The design uses Proxima Nova Light / Regular / Semibold. Shipping Proxima inside an
 * app needs an app licence, so CURO ships Figtree for now. To switch, load the Proxima
 * files here and change the family names below; nothing else references a font.
 */
export const fontAssets = {
  Figtree_300Light,
  Figtree_300Light_Italic,
  Figtree_400Regular,
  Figtree_600SemiBold,
};

const FAMILY = {
  light: 'Figtree_300Light',
  lightItalic: 'Figtree_300Light_Italic',
  regular: 'Figtree_400Regular',
  semibold: 'Figtree_600SemiBold',
} as const;

export type Weight = 300 | 400 | 600;

/** Font style for a weight. Each weight is its own family, so never set fontWeight too. */
export function font(weight: Weight = 400, italic = false): Pick<TextStyle, 'fontFamily'> {
  if (italic) return { fontFamily: FAMILY.lightItalic };
  if (weight === 300) return { fontFamily: FAMILY.light };
  if (weight === 600) return { fontFamily: FAMILY.semibold };
  return { fontFamily: FAMILY.regular };
}
