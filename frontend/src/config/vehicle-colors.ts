/**
 * Palette centralisee des couleurs vehicules.
 *
 * Chaque vehicule recoit une cle ('V', 'B', 'M', 'R', 'O')
 * stockee dans vehicle.color. Toute l'application resout
 * les couleurs via ce module — aucune duplication.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface VehicleColor {
  /** Cle stockee dans Vehicle.color ('V', 'B', 'M', 'R', 'O') */
  key: string;
  label: string;
  /** Couleur principale */
  hex: string;
  /** Variante foncee (texte, accents forts) */
  dark: string;
  /** Variante tres claire (fonds, badges) */
  light: string;
}

// ── Palette ──────────────────────────────────────────────────────────────────

const PALETTE: readonly VehicleColor[] = [
  { key: 'V', label: 'Vert',   hex: '#66B0B7', dark: '#4A8A90', light: '#EDF6F7' },
  { key: 'B', label: 'Bleu',   hex: '#6688B7', dark: '#4A6690', light: '#EDF1F7' },
  { key: 'M', label: 'Mauve',  hex: '#6D66B7', dark: '#504A90', light: '#EEEDF7' },
  { key: 'R', label: 'Rouge',  hex: '#B76D66', dark: '#904A45', light: '#F7EDEC' },
  { key: 'O', label: 'Or',     hex: '#B0B766', dark: '#8A9045', light: '#F6F7ED' },
] as const;

// ── Exports ──────────────────────────────────────────────────────────────────

/** Liste ordonnee des couleurs disponibles */
export const VEHICLE_COLORS = PALETTE;

/** Couleur par defaut (fallback) */
export const DEFAULT_VEHICLE_COLOR = PALETTE[0];

/** Recupere un VehicleColor par sa cle. Fallback sur la premiere couleur. */
export function getVehicleColor(key: string): VehicleColor {
  return PALETTE.find((c) => c.key === key) ?? DEFAULT_VEHICLE_COLOR;
}

/** Raccourci : hex principal d'une cle */
export function getVehicleHex(key: string): string {
  return getVehicleColor(key).hex;
}

/** Attribue une couleur par index (cycle automatique) */
export function colorByIndex(index: number): VehicleColor {
  return PALETTE[index % PALETTE.length];
}

/** Cle de la couleur attribuee par index */
export function colorKeyByIndex(index: number): string {
  return PALETTE[index % PALETTE.length].key;
}

// ── Utilitaires couleur ──────────────────────────────────────────────────────

/** Convertit un hex (#RRGGBB ou #RGB) en rgba(r,g,b,a) */
export function hexToRgba(hex: string, alpha: number): string {
  const n = hex.replace('#', '');
  const full = n.length === 3
    ? n.split('').map((c) => c + c).join('')
    : n;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
