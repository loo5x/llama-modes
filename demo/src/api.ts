export type Mode = 'BOOLEAN' | 'CHOICE' | 'SCALE';
export type Point = { value: number; label: string };
export type Row = {
    label: string;
    weight: number;
    value?: number;
    tokenCount?: number;
    tokenIds?: number[];
    sum?: number;
    mean?: number;
};
export type DirectResult = {
    rows: Row[];
    winners: string[];
    weightKind: string;
    measurement?: 'ordinal' | 'interval';
    mode?: number[];
    median?: number;
    q25?: number;
    q75?: number;
    expected?: number;
    deviation?: number;
};
export type ObjectData = Record<string, unknown>;

export function object(value: unknown): ObjectData {
    if (typeof value !== 'object' || value === null || Array.isArray(value))
        throw new Error('Malformed response: expected an object');
    return value as ObjectData;
}
function number(value: unknown): number {
    if (typeof value !== 'number' || !Number.isFinite(value))
        throw new Error('Malformed response: missing or non-finite number');
    return value;
}
function text(value: unknown): string {
    if (typeof value !== 'string' || !value) throw new Error('Malformed response: missing label');
    return value;
}
function tokens(row: ObjectData) {
    const ids = row.token_ids ?? (row.token_id === undefined ? undefined : [row.token_id]);
    if (!Array.isArray(ids) || !ids.length || !ids.every((x) => Number.isInteger(x) && x >= 0))
        throw new Error('Malformed response: invalid token IDs');
    const count = row.token_count === undefined ? ids.length : number(row.token_count);
    if (count !== ids.length) throw new Error('Malformed response: inconsistent token count');
    return { tokenIds: ids as number[], tokenCount: count };
}
export function sortPoints<T extends Point>(points: T[]): T[] {
    return [...points].sort((a, b) => a.value - b.value);
}
export function chartData(rows: Row[]) {
    return rows.map((row) => ({
        name: String(row.value ?? row.label),
        label: row.label,
        percent: row.weight * 100,
    }));
}
export function parseDirect(input: unknown, mode: Mode, labels: string[]): DirectResult {
    const data = object(input);
    const source = mode === 'SCALE' ? data.points : data.choices;
    if (!Array.isArray(source) || source.length !== labels.length || !source.length)
        throw new Error('Malformed response: candidate count mismatch');
    const raw = source.map(object);
    const sequence = mode !== 'SCALE' && raw[0].sum_log_probability !== undefined;
    const scores = raw.map((r) =>
        number(mode === 'SCALE' ? r.relative_weight : sequence ? r.sum_log_probability : r.probability),
    );
    const maxScore = Math.max(...scores);
    const exp = sequence ? scores.map((s) => Math.exp(s - maxScore)) : scores;
    const total = exp.reduce((a, b) => a + b, 0);
    if (!sequence && (scores.some((s) => s < 0 || s > 1) || Math.abs(total - 1) > 1e-5))
        throw new Error('Malformed response: weights are not normalized');
    let rows: Row[] = raw.map((r, i) => ({
        label: text(mode === 'SCALE' ? r.label : r.text),
        weight: sequence ? exp[i] / total : scores[i],
        ...tokens(r),
        ...(r.sum_log_probability === undefined
            ? {}
            : { sum: number(r.sum_log_probability), mean: number(r.mean_log_probability) }),
        ...(mode === 'SCALE' ? { value: number(r.value) } : {}),
    }));
    if (
        new Set(rows.map((r) => r.label)).size !== labels.length ||
        rows.some((r) => !labels.includes(r.label))
    )
        throw new Error('Malformed response: labels differ from request');
    const max = Math.max(...rows.map((r) => r.weight));
    const result: DirectResult = {
        rows,
        winners: rows.filter((r) => r.weight === max).map((r) => r.label),
        weightKind: sequence
            ? 'Relative weights: softmax of SUM log scores (computed by this UI)'
            : mode === 'SCALE'
              ? 'Relative scale weights'
              : 'Candidate-relative probabilities',
    };
    if (mode === 'SCALE') {
        if (data.measurement !== 'interval' && data.measurement !== 'ordinal')
            throw new Error('Malformed response: measurement missing');
        rows = [...rows].sort((a, b) => a.value! - b.value!);
        if (new Set(rows.map((r) => r.value)).size !== rows.length)
            throw new Error('Malformed response: duplicate scale values');
        if (!Array.isArray(data.mode) || !data.mode.length)
            throw new Error('Malformed response: mode missing');
        const quantiles = object(data.quantiles);
        Object.assign(result, {
            rows,
            measurement: data.measurement,
            mode: data.mode.map(number),
            median: number(data.median),
            q25: number(quantiles['0.25']),
            q75: number(quantiles['0.75']),
        });
        const values = rows.map((r) => r.value!);
        if (
            [...result.mode!, result.median!, result.q25!, result.q75!].some((v) => !values.includes(v)) ||
            result.q25! > result.median! ||
            result.median! > result.q75!
        )
            throw new Error('Malformed response: summaries do not match scale support');
        if (data.measurement === 'interval')
            Object.assign(result, {
                expected: number(data.expected_value),
                deviation: number(data.standard_deviation),
            });
        if (
            result.expected !== undefined &&
            (result.expected < values[0] || result.expected > values.at(-1)! || result.deviation! < 0)
        )
            throw new Error('Malformed response: invalid interval summary');
    }
    return result;
}
export function parseChat(input: unknown, labels: string[]) {
    const data = object(input);
    if (!Array.isArray(data.choices) || !data.choices.length) throw new Error('Malformed chat response');
    const choice = object(data.choices[0]);
    const message = object(choice.message);
    const content = typeof message.content === 'string' ? message.content : '';
    const matches = labels.filter((label) => label.trim() === content.trim());
    const answer = choice.finish_reason === 'stop' && matches.length === 1 ? matches[0] : null;
    const usage = data.usage == null ? {} : object(data.usage);
    const completionTokens =
        typeof usage.completion_tokens === 'number' &&
        Number.isInteger(usage.completion_tokens) &&
        usage.completion_tokens >= 0
            ? usage.completion_tokens
            : null;
    return {
        answer,
        content,
        completionTokens,
        finishReason: choice.finish_reason,
        reasoning: typeof message.reasoning_content === 'string' ? message.reasoning_content : '',
    };
}
export function agreement(direct: string[], chat: string | null): boolean | null {
    return direct.length === 1 && chat !== null ? direct[0] === chat : null;
}
export function errorMessage(status: number, body: unknown): string {
    let detail = '';
    try {
        detail = String(object(object(body).error).message ?? '');
    } catch {
        /* Non-JSON errors retain HTTP status. */
    }
    if (/token-prefix/i.test(detail))
        return (
            'Scale labels overlap as token prefixes. Try symbolic labels (A, B, C...) with an explicit mapping, then verify them with this model. ' +
            detail
        );
    if (status === 404)
        return 'Endpoint unavailable. Use a llama-modes build with /decision and /scale support.';
    return `HTTP ${status}${detail ? ': ' + detail : ': request failed'}`;
}
export async function api(path: string, body?: unknown): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 125_000);
    try {
        const response = await fetch('/api' + path, {
            method: body === undefined ? 'GET' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
            signal: controller.signal,
        });
        const value = await response.json().catch(() => {
            throw new Error(`HTTP ${response.status}: server returned malformed JSON`);
        });
        if (!response.ok) throw new Error(errorMessage(response.status, value));
        return value;
    } catch (error) {
        if (controller.signal.aborted)
            throw new Error('Request timed out. Check llama-server and try again.');
        throw error;
    } finally {
        clearTimeout(timer);
    }
}
export function makeRequests(
    mode: Mode,
    question: string,
    labels: string[],
    points: Point[],
    measurement: 'ordinal' | 'interval',
    model: string,
) {
    if (!question.trim()) throw new Error('Enter a question or task.');
    const candidates = mode === 'SCALE' ? points.map((p) => p.label) : labels;
    if (
        candidates.length < 2 ||
        candidates.length > 256 ||
        candidates.some((x) => !x.trim()) ||
        new Set(candidates.map((x) => x.trim())).size !== candidates.length
    )
        throw new Error('Provide 2 to 256 distinct, non-empty labels.');
    if (
        mode === 'SCALE' &&
        (points.some((p) => !Number.isFinite(p.value)) ||
            new Set(points.map((p) => p.value)).size !== points.length)
    )
        throw new Error('Scale values must be finite and distinct.');
    const mapping =
        mode === 'SCALE' ? '\nOrdered label/value mapping: ' + JSON.stringify(sortPoints(points)) : '';
    const content =
        question +
        '\nSelect exactly one supplied label. Return only that label. Labels: ' +
        JSON.stringify(candidates) +
        mapping;
    const messages = [{ role: 'user', content }];
    const direct = {
        messages,
        ...(model ? { model } : {}),
        ...(mode === 'SCALE' ? { measurement, scale: points } : { choices: candidates }),
    };
    const chat = { messages, ...(model ? { model } : {}), temperature: 0, max_tokens: 1024, stream: false };
    return { endpoint: mode === 'SCALE' ? '/scale' : '/decision', direct, chat, labels: candidates };
}
