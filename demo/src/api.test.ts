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
