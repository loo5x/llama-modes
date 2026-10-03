import { describe, expect, it } from 'vitest';
import { agreement, chartData, errorMessage, makeRequests, parseChat, parseDirect, sortPoints } from './api';
import { scaleFixture } from './fixtures';
import { localTarget } from '../proxy';

describe('response contracts', () => {
    it('handles the single-token path and derives multi-token relative weights', () => {
        const single = {
            choices: [
                { text: 'Yes', token_id: 1, probability: 0.8 },
                { text: 'No', token_id: 2, probability: 0.2 },
            ],
        };
        expect(parseDirect(single, 'BOOLEAN', ['Yes', 'No']).winners).toEqual(['Yes']);
        const multi = {
            choices: [
                {
                    text: 'New York',
                    token_ids: [1, 2],
                    token_count: 2,
                    sum_log_probability: -1000,
                    mean_log_probability: -500,
                },
                {
                    text: 'Paris',
                    token_ids: [3],
                    token_count: 1,
                    sum_log_probability: -1001,
                    mean_log_probability: -1001,
                },
            ],
        };
        const parsed = parseDirect(multi, 'CHOICE', ['New York', 'Paris']);
        expect(parsed.rows[0].weight).toBeCloseTo(0.7310585786);
        expect(parsed.rows[0].tokenCount).toBe(2);
        expect(parsed.weightKind).toContain('computed by this UI');
    });
    it('rejects malformed responses', () => {
        for (const data of [null, {}, { choices: [] }, { choices: [{ text: 'Yes', probability: NaN }] }])
            expect(() => parseDirect(data, 'BOOLEAN', ['Yes', 'No'])).toThrow();
    });
    it('sorts scales without mutating input and converts chart percentages', () => {
        const points = [
            { value: 2, label: 'B' },
            { value: 1, label: 'A' },
        ];
        expect(sortPoints(points).map((p) => p.value)).toEqual([1, 2]);
        expect(points[0].value).toBe(2);
        expect(chartData([{ label: 'A', value: 1, weight: 0.25 }])).toEqual([
            { name: '1', label: 'A', percent: 25 },
        ]);
    });
    it('only shows interval arithmetic on interval scales', () => {
        const points = [
            { value: 1, label: 'A' },
            { value: 2, label: 'B' },
        ];
        const ordinal = parseDirect(scaleFixture(points, 'ordinal'), 'SCALE', ['A', 'B']);
        expect(ordinal.expected).toBeUndefined();
        expect(ordinal.deviation).toBeUndefined();
        expect(ordinal.q25).toBeDefined();
        expect(parseDirect(scaleFixture(points, 'interval'), 'SCALE', ['A', 'B']).expected).toBeGreaterThan(
            1,
        );
    });
});

describe('chat and agreement', () => {
    const chat = (content: string | null, finish_reason = 'stop') => ({
        choices: [{ message: { content, reasoning_content: 'Internal reasoning' }, finish_reason }],
        usage: { completion_tokens: 42 },
    });
    it('accepts only exact final content and a stop finish reason', () => {
        expect(parseChat(chat(' Yes\n'), ['Yes', 'No']).answer).toBe('Yes');
        for (const data of [
            chat('Yes because...'),
            chat(null),
            chat('Yes', 'length'),
            chat('<think>Yes</think>'),
            chat('yes'),
        ])
            expect(parseChat(data, ['Yes', 'No']).answer).toBeNull();
        expect(parseChat(chat('Yes'), ['Yes', 'No']).completionTokens).toBe(42);
    });
    it('does not count ties and missing answers as agreement', () => {
        expect(agreement(['Yes'], 'Yes')).toBe(true);
        expect(agreement(['No'], 'Yes')).toBe(false);
        expect(agreement(['No', 'Yes'], 'Yes')).toBeNull();
        expect(agreement(['Yes'], null)).toBeNull();
    });
});

describe('requests and errors', () => {
    it('explains token-prefix overlap and missing endpoints', () => {
        expect(errorMessage(400, { error: { message: 'strict token-prefix overlap' } })).toContain(
            'symbolic labels',
        );
        expect(errorMessage(404, {})).toContain('llama-modes build');
        expect(errorMessage(502, {})).toContain('502');
    });
    it('shares messages and includes visible scale mapping', () => {
        const result = makeRequests(
            'SCALE',
            'Rate',
            [],
            [
                { label: 'A', value: 0 },
                { label: 'B', value: 1 },
            ],
            'ordinal',
            'model',
        );
        expect(result.direct.messages).toEqual(result.chat.messages);
        expect(result.direct.messages[0].content).toContain('"label":"A"');
        expect(() => makeRequests('CHOICE', 'Pick', [], [], 'ordinal', '')).toThrow();
    });
    it('restricts the proxy target to HTTP loopback with no URL extras', () => {
        expect(localTarget('http://localhost:8080')).toBe('http://127.0.0.1:8080');
        expect(localTarget('http://[::1]:8080')).toBe('http://[::1]:8080');
        for (const url of [
            'https://example.com',
            'http://127.0.0.1.evil.test',
            'http://user@localhost:8080',
            'http://localhost:8080/path',
            'http://localhost:8080/?target=example.com',
            'file:///etc/passwd',
        ])
            expect(() => localTarget(url)).toThrow();
    });
});

import { makeEvaluation, parseEvaluation } from './api';
import { sharedPreset } from './presets';
import { sharedFixture } from './fixtures';
import { editQuestions } from './SharedContext';

describe('shared context', () => {
    const request = () => makeEvaluation(sharedPreset.context, sharedPreset.questions, 'local-model');
    const response = () => ({
        results: request().questions.map((q) => ({
            id: q.id,
            type: q.type,
            result: q.scale
                ? scaleFixture(q.scale, q.measurement!)
                : {
                      choices: q.choices!.map((text, i) => ({
                          text,
                          token_id: i,
                          probability: 1 / q.choices!.length,
                      })),
                  },
        })),
        execution: {
            strategy: 'shared_aligned',
            shared_prefix_tokens: 128,
            n_batch: 128,
            n_ubatch: 128,
            fallback_reason: null,
        },
    });
    it('constructs mixed requests with explicit labels and mappings, without a sharing toggle', () => {
        const body = request();
        expect(Object.keys(body).sort()).toEqual(['context', 'model', 'questions']);
        expect(body.questions.map((q) => q.type)).toEqual(['boolean', 'choice', 'scale']);
        expect(body.questions[0].choices).toEqual(['Yes', 'No']);
        expect(body.questions[2].question).toContain('Ordered label/value mapping');
        expect(body.questions[2].question).toContain('"label":"C"');
        expect(body.questions[0]).not.toHaveProperty('messages');
        expect(() => makeEvaluation('', sharedPreset.questions)).toThrow('context');
        expect(() => makeEvaluation('text', [])).toThrow('1 to 32');
        expect(() => makeEvaluation('text', Array(33).fill(sharedPreset.questions[0]))).toThrow();
        expect(() => makeEvaluation('text', [sharedPreset.questions[0], sharedPreset.questions[0]])).toThrow(
            'IDs',
        );
        expect(() => makeEvaluation('text', [{ ...sharedPreset.questions[0], labels: ['Yes'] }])).toThrow(
            'two',
        );
    });
    it('parses mixed results and retains actual server diagnostics', () => {
        const parsed = parseEvaluation(response(), request());
        expect(parsed.results).toHaveLength(3);
        expect(parsed.results[2].parsed.measurement).toBe('ordinal');
        expect(parsed.execution.shared_prefix_tokens).toBe(128);
        const fresh = response();
        Object.assign(fresh.execution, {
            strategy: 'fresh',
            shared_prefix_tokens: 0,
            fallback_reason: 'fresh_only',
        });
        expect(parseEvaluation(fresh, request()).execution.fallback_reason).toBe('fresh_only');
    });
    it('rejects mismatched IDs, types, scale mapping, missing results and diagnostics', () => {
        for (const mutate of [
            (r: ReturnType<typeof response>) => {
                r.results.reverse();
            },
            (r: ReturnType<typeof response>) => {
                r.results[0].type = 'choice';
            },
            (r: ReturnType<typeof response>) => {
                r.results.pop();
            },
            (r: ReturnType<typeof response>) => {
                r.execution.shared_prefix_tokens = -1;
            },
            (r: ReturnType<typeof response>) => {
                r.results[2].result = scaleFixture(
                    [
                        { label: 'A', value: 10 },
                        { label: 'B', value: 11 },
                        { label: 'C', value: 12 },
                        { label: 'D', value: 13 },
                    ],
                    'ordinal',
                );
            },
        ]) {
            const r = response();
            mutate(r);
            expect(() => parseEvaluation(r, request())).toThrow('Malformed');
        }
        expect(() => parseEvaluation({ results: response().results }, request())).toThrow();
        expect(errorMessage(503, { error: { message: 'Evaluation busy' } })).toContain('Evaluation busy');
        expect(errorMessage(404, {})).toContain('--evaluate');
    });
    it('adds, removes and reorders independent rows with stable unique IDs', () => {
        const original = sharedPreset.questions;
        const added = editQuestions(original, 'add');
        expect(added).toHaveLength(4);
        expect(original).toHaveLength(3);
        expect(new Set(editQuestions(added, 'add').map((q) => q.id)).size).toBe(5);
        expect(editQuestions(added, 'remove', 3)).toEqual(original);
        expect(editQuestions(original, 'down', 0)[1]).toEqual(original[0]);
        expect(editQuestions(original, 'up', 0)).toEqual(original);
        expect(editQuestions(Array(32).fill(original[0]), 'add')).toHaveLength(32);
    });
    it('provides illustrative mixed fixtures without fabricated execution or timing', () => {
        const result = sharedFixture(request());
        expect(result.map((r) => r.type)).toEqual(['boolean', 'choice', 'scale']);
        expect(result[1].parsed.weightKind).toContain('softmax of SUM');
        expect(result[2].parsed.mode).toBeDefined();
        expect(JSON.stringify(result)).not.toMatch(/latency|shared_prefix_tokens|strategy/);
    });
});
