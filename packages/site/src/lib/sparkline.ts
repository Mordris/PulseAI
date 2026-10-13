export interface Sparkline {
  /** SVG polyline points, "x,y x,y …". */
  points: string;
  last: { x: number; y: number };
}

/**
 * Points for a small trend line in a width×height box with padding. A flat series sits in the
 * middle. Fewer than two values draw nothing.
 */
export function sparkline(
  series: readonly number[],
  width: number,
  height: number,
  padding: number,
): Sparkline | undefined {
  if (series.length < 2) return undefined;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max - min;
  const step = (width - 2 * padding) / (series.length - 1);
  const coords = series.map((value, index) => {
    const ratio = span === 0 ? 0.5 : (value - min) / span;
    const x = padding + index * step;
    const y = height - padding - ratio * (height - 2 * padding);
    return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
  });
  const last = coords.at(-1);
  if (last === undefined) return undefined;
  return { points: coords.map(({ x, y }) => `${x},${y}`).join(" "), last };
}
