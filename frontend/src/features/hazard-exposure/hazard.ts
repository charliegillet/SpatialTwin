export interface HazardEventView { element_id: string; close_at_s: number; }
export interface HazardAlternativeView { alternative_id: string; completed_crossings: number; exposure_people_seconds: number; }
export interface HazardCheckView { status: 'passed' | 'failed'; reasons: string[]; }
export interface HazardResultView {
  scenario_label: string;
  events: HazardEventView[];
  alternatives: HazardAlternativeView[];
  check: HazardCheckView;
}

export const EXPOSURE_CAVEAT = 'modeled people-seconds in hazard; not a casualty or survival prediction';

export function formatExposureLabel(): string {
  return EXPOSURE_CAVEAT;
}

export function isDisplayable(result: HazardResultView | null | undefined, isCurrent: boolean): result is HazardResultView {
  return isCurrent && result != null;
}

export interface AlternativeSummary {
  rows: HazardAlternativeView[];
  total_completed_crossings: number;
  total_exposure_people_seconds: number;
}

export function summarizeAlternatives(alternatives: readonly HazardAlternativeView[]): AlternativeSummary {
  const rows = alternatives.map(item => ({ ...item }));
  return {
    rows,
    total_completed_crossings: rows.reduce((sum, row) => sum + row.completed_crossings, 0),
    total_exposure_people_seconds: rows.reduce((sum, row) => sum + row.exposure_people_seconds, 0),
  };
}

export interface HazardDisplayModel {
  kind: 'empty' | 'stale' | 'result';
  message: string;
  label: string | null;
  scenario_label: string | null;
  events: HazardEventView[];
  summary: AlternativeSummary | null;
  check: HazardCheckView | null;
}

export function buildDisplayModel(result: HazardResultView | null | undefined, isCurrent: boolean): HazardDisplayModel {
  const blank = { label: null, scenario_label: null, events: [], summary: null, check: null };
  if (result == null) return { kind: 'empty', message: 'No hazard simulation has been run.', ...blank };
  if (!isCurrent) return { kind: 'stale', message: 'This hazard result belongs to an earlier scenario state. Re-run the simulation to see current values.', ...blank };
  return {
    kind: 'result', message: '', label: formatExposureLabel(), scenario_label: result.scenario_label,
    events: result.events.map(event => ({ ...event })), summary: summarizeAlternatives(result.alternatives),
    check: { status: result.check.status, reasons: [...result.check.reasons] },
  };
}
