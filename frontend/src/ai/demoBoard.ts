import type { CaptureRequest, RunContext, TargetId, ThinkingLevel } from '../types.ts';

export const DEMO_BOARD_SIZE = [1200, 1000] as const;

// Canonical venue/reviewed_venue.json polygons translated by (-50, -50).
// These coordinates describe an illustrative tabletop, not measured venue space.
export const DEMO_ZONES = [
  { id: 'EVENT', x: 0, y: 0, width: 300, height: 200 },
  { id: 'WEST', x: 0, y: 220, width: 120, height: 150 },
  { id: 'EAST', x: 180, y: 220, width: 120, height: 150 },
  { id: 'RESERVE', x: 130, y: 210, width: 40, height: 120 },
] as const;

export const DEMO_TARGETS: Record<TargetId, { x: number; y: number; typedId: string; padId: string }> = {
  P1: { x: 60, y: 210, typedId: 'portal:P1', padId: 'T_P1' },
  P2: { x: 240, y: 210, typedId: 'portal:P2', padId: 'T_P2' },
  B2: { x: 240, y: 374, typedId: 'boundary:B2', padId: 'T_B2' },
};

/** The preview and uploaded JPEG are rendered from this same, self-contained SVG. */
export function demoBoardSvg(target: TargetId): string {
  if (!Object.prototype.hasOwnProperty.call(DEMO_TARGETS, target)) throw new Error('Choose P1, P2 or B2 for the synthetic token.');
  const rooms = DEMO_ZONES.map(zone => `<rect x="${zone.x}" y="${zone.y}" width="${zone.width}" height="${zone.height}" rx="2" fill="${zone.id === 'EVENT' ? '#e8edd6' : zone.id === 'RESERVE' ? '#d5e2c1' : '#eef1e5'}" stroke="#26372f" stroke-width="3"/>`).join('');
  const pads = Object.entries(DEMO_TARGETS).map(([id, pad]) => `<g transform="translate(${pad.x} ${pad.y})"><circle r="23" fill="#fcfff5" stroke="#315d44" stroke-width="2"/><text text-anchor="middle" y="5" font-size="16" font-weight="700" fill="#162d20">${id}</text><text text-anchor="middle" y="39" font-size="9" font-weight="700" fill="#223c2e">${pad.padId}</text></g>`).join('');
  const token = DEMO_TARGETS[target];
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1000" viewBox="0 0 1200 1000">
    <rect width="1200" height="1000" fill="#f4f5ec"/>
    <g font-family="Arial, Helvetica, sans-serif">
      <text x="600" y="52" text-anchor="middle" font-size="26" font-weight="700" fill="#173429">SPATIALTWIN / SYNTHETIC TABLETOP</text>
      <text x="600" y="86" text-anchor="middle" font-size="19" fill="#526157">One red BLOCKED token on a labeled pad</text>
      <g transform="translate(330 142) scale(1.8)">
        <rect x="-22" y="-20" width="344" height="450" rx="9" fill="#d5dbc9" stroke="#9aa88f" stroke-width="2"/>
        ${rooms}
        <path d="M60 170 V350 M240 170 V350" fill="none" stroke="#84a273" stroke-width="3" stroke-dasharray="6 6"/>
        <text x="150" y="88" text-anchor="middle" font-size="18" font-weight="700" fill="#243e2e">MAIN EVENT HALL</text>
        <text x="150" y="113" text-anchor="middle" font-size="11" fill="#50634c">EVENT</text>
        <text x="60" y="285" text-anchor="middle" font-size="13" font-weight="700" fill="#243e2e">WEST</text>
        <text x="60" y="302" text-anchor="middle" font-size="9" fill="#50634c">CORRIDOR</text>
        <text x="240" y="285" text-anchor="middle" font-size="13" font-weight="700" fill="#243e2e">EAST</text>
        <text x="240" y="302" text-anchor="middle" font-size="9" fill="#50634c">CORRIDOR</text>
        <text transform="translate(150 285) rotate(-90)" text-anchor="middle" font-size="10" font-weight="700" fill="#3a5338">RESERVE</text>
        <path d="M137 205 H163" stroke="#617451" stroke-width="7"/>
        <text x="150" y="190" text-anchor="middle" font-size="8" fill="#3a5338">P3 CLOSED</text>
        <path d="M170 280 H180" stroke="#617451" stroke-width="5"/>
        <text x="176" y="267" text-anchor="middle" font-size="7" fill="#3a5338">P4</text>
        <rect x="37" y="365" width="46" height="18" rx="3" fill="#e7eddc" stroke="#617451" stroke-width="2"/>
        <text x="60" y="378" text-anchor="middle" font-size="12" font-weight="700" fill="#243e2e">B1</text>
        <text x="60" y="414" text-anchor="middle" font-size="8" fill="#50634c">FINITE BOUNDARY</text>
        ${pads}
        <g transform="translate(${token.x} ${token.y})" data-blocked-target="${target}">
          <circle r="22" fill="#d92d2a" stroke="#802522" stroke-width="2"/>
          <text text-anchor="middle" y="1" font-size="17" font-weight="700" fill="#ffffff">${target}</text>
          <text text-anchor="middle" y="12" font-size="6.5" font-weight="700" fill="#ffffff">BLOCKED</text>
        </g>
      </g>
      <text x="600" y="963" text-anchor="middle" font-size="18" fill="#526157">Illustrative four-zone board · not a surveyed building · no physical hardware</text>
    </g>
  </svg>`;
}

/** Target identity travels only in the picture; no fixture or forced-match controls. */
export function demoBoardCapture(imageBase64: string, metadata: { captureId: string; timestampIso: string; context: RunContext; thinkingLevel: ThinkingLevel }): CaptureRequest {
  if (!imageBase64) throw new Error('The synthetic board image could not be captured.');
  return {
    capture_id: metadata.captureId, timestamp_iso: metadata.timestampIso, source_context: { ...metadata.context },
    dimensions: [...DEMO_BOARD_SIZE], source_kind: 'annotated_plan', mode: 'live', image_base64: imageBase64,
    thinking_level: metadata.thinkingLevel,
    deadline_seconds: 45,
  };
}
