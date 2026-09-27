import type { Point } from './api';

// Illustrative UI data only. No model evaluation or timing is represented.
export function scaleFixture(points: Point[], measurement: 'ordinal' | 'interval') {
    const sorted = [...points].sort((a, b) => a.value - b.value);
    const unscaled = sorted.map((_, i) => Math.exp(-((i - (sorted.length - 1) * 0.86) ** 2) / 1.4));
    const total = unscaled.reduce((a, b) => a + b, 0);
    let cumulative = 0;
    const rows = sorted.map((p, i) => {
        const weight = unscaled[i] / total;
        cumulative += weight;
        return {
            ...p,
            token_ids: [100 + i],
            token_count: 1,
            sum_log_probability: Math.log(weight) - 1,
            mean_log_probability: Math.log(weight) - 1,
            relative_weight: weight,
            cumulative_weight: cumulative,
        };
    });
    const quantile = (q: number) => rows.find((p) => p.cumulative_weight >= q)?.value ?? rows.at(-1)!.value;
    const mean = rows.reduce((sum, p) => sum + p.value * p.relative_weight, 0);
    return {
        measurement,
        points: rows,
        mode: [rows.reduce((a, b) => (a.relative_weight > b.relative_weight ? a : b)).value],
        median: quantile(0.5),
        quantiles: { '0.25': quantile(0.25), '0.75': quantile(0.75) },
        ...(measurement === 'interval'
            ? {
                  expected_value: mean,
                  standard_deviation: Math.sqrt(
                      rows.reduce((s, p) => s + p.relative_weight * (p.value - mean) ** 2, 0),
                  ),
              }
            : {}),
    };
}
