export const MAX_TIP_BASIS_POINTS: number;
export const PERCENT_HINT: string;
export function parsePercent(text: string): number | null | undefined;
export function percentText(bp: number | null | undefined): string;
export function percentOf(cents: number, bp: number): number;
export function tipBase(cost: {
  final_cents: number | null; quoted_cents: number | null; estimated_cents: number | null;
}): number | null;
export function tipPaymentsGap(cost: {
  tip_state: string | null; scheduled_cents: number; committed_cents: number;
}): { paymentsCents: number; tipCents: number } | null;
export function tipsMove(
  tips: { archived: boolean; tip_state: string | null; tip_basis_points: number | null; committed_cents: number }[],
  newBase: number | null,
): { before: number; after: number; count: number };
export function tipTargets<T extends { archived: boolean; tip_state: string | null }>(costs: T[]): T[];
