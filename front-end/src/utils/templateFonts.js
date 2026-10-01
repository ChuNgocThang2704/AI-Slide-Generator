// Fonts an uploaded template can ask for versus the fonts this app actually loads.
// A PowerPoint/Canva font that is not installed in the browser silently falls back
// to a serif default, which is what made imported decks look wrong. Unknown fonts
// are mapped to the closest loaded family by name and style, all with Vietnamese support.

const SANS = "'Plus Jakarta Sans', sans-serif";
const SERIF = "'Merriweather', serif";
const DISPLAY_SERIF = "'Playfair Display', serif";
const ROUND = "'Nunito', sans-serif";
const TECH = "'Space Grotesk', sans-serif";

// Families loaded by index.html; returned unchanged (with a proper fallback stack).
const LOADED = {
  inter: "'Inter', sans-serif",
  nunito: ROUND,
  'plus jakarta sans': SANS,
  'space grotesk': TECH,
  'playfair display': DISPLAY_SERIF,
  merriweather: SERIF,
  'exo 2': "'Exo 2', sans-serif",
  saira: "'Saira', sans-serif",
  'baloo 2': "'Baloo 2', cursive",
  'be vietnam pro': "'Be Vietnam Pro', sans-serif",
};

// Well-known template fonts and their nearest loaded relative.
const KNOWN = [
  [/garet|montserrat|poppins|gotham|proxima|avenir|futura|lexend|dm sans|manrope|outfit|urbanist|sora|work sans|raleway|josefin/, SANS],
  [/playfair|didot|bodoni|cormorant|dm serif|abril|prata|libre baskerville/, DISPLAY_SERIF],
  [/merriweather|georgia|times|garamond|cambria|palatino|lora|noto serif|source serif|crimson|book antiqua|baskerville|serif/, SERIF],
  [/nunito|quicksand|comfortaa|varela|rounded|baloo|fredoka|pacifico/, ROUND],
  [/grotesk|orbitron|rajdhani|audiowide|bebas|oswald|anton|impact|condensed|mono|courier|consolas/, TECH],
];

const WEIGHT_WORDS = /\b(bold|black|light|medium|regular|thin|extra|semi|heavy|italic|oblique|demi|book)\b/g;

const clean = (name) => String(name || '')
  .toLowerCase()
  .replace(/['"]/g, '')
  .replace(/[-_]/g, ' ')
  .replace(WEIGHT_WORDS, ' ')
  .replace(/\s+/g, ' ')
  .trim();

/** A CSS font stack made only of fonts the app loads. Never returns an unloaded family. */
export function mapTemplateFont(name, fallback = SANS) {
  const base = clean(name);
  if (!base) return fallback;
  if (LOADED[base]) return LOADED[base];
  const known = KNOWN.find(([pattern]) => pattern.test(base));
  if (known) return known[1];
  if (/arial|helvetica|calibri|verdana|tahoma|segoe|roboto|open sans|lato|sans/.test(base)) return SANS;
  return fallback;
}
