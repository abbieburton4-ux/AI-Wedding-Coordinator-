export const MAX_TIP_BASIS_POINTS: number;
export const PERCENT_HINT: string;
export function parsePercent(text: string): number | null | undefined;
export function percentText(bp: number | null | undefined): string;
export function percentOf(cents: number, bp: number): number;
export function tipBase(cost: {
  final_cents: number | null; quoted_cents: number | null; estimated_cents: number | null;
}): number | null;
export function tipTargets<T extends { archived: boolean; tip_state: string | null }>(costs: T[]): T[];
