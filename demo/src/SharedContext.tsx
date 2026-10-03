import { useRef, useState, type ReactNode } from 'react';
import {
    api,
    makeEvaluation,
    parseEvaluation,
    type DirectResult,
    type EvaluationQuestion,
    type Mode,
} from './api';
import { sharedPreset } from './presets';
import { sharedFixture } from './fixtures';

export function editQuestions(
    questions: EvaluationQuestion[],
    action: 'add' | 'remove' | 'up' | 'down',
    index = 0,
): EvaluationQuestion[] {
    if (action === 'add') {
        if (questions.length >= 32) return questions;
        let n = 1;
        while (questions.some((q) => q.id === `q${n}`)) n++;
        return [
            ...questions,
            {
                id: `q${n}`,
                mode: 'BOOLEAN',
                question: '',
                labels: ['Yes', 'No'],
                points: [
                    { label: 'L', value: 0 },
                    { label: 'H', value: 1 },
                ],
                measurement: 'ordinal',
            },
        ];
    }
    if (action === 'remove') return questions.filter((_, i) => i !== index);
    const next = index + (action === 'up' ? -1 : 1);
    if (index < 0 || index >= questions.length || next < 0 || next >= questions.length) return questions;
    const result = [...questions];
    [result[index], result[next]] = [result[next], result[index]];
    return result;
}

export default function SharedContext({
    model,
    target,
    presentation,
    fixture,
    onBusy,
    distribution,
}: {
    model: string;
    target: string;
    presentation: boolean;
    fixture: boolean;
    onBusy: (busy: boolean) => void;
    distribution: (result: DirectResult) => ReactNode;
}) {
    const [context, setContext] = useState(sharedPreset.context);
    const [questions, setQuestions] = useState<EvaluationQuestion[]>(sharedPreset.questions);
    const [busy, setBusy] = useState(false);
    const running = useRef(false);
    const [error, setError] = useState('');
    const [raw, setRaw] = useState<unknown>(null);
    const [results, setResults] = useState<ReturnType<typeof sharedFixture>>([]);
    const [execution, setExecution] = useState<Record<string, unknown> | null>(null);
    const [latency, setLatency] = useState<number | null>(null);
    let request: ReturnType<typeof makeEvaluation> | null = null;
    let validation = '';
    try {
        request = makeEvaluation(context, questions, model);
    } catch (e) {
        validation = e instanceof Error ? e.message : String(e);
    }
    function clear() {
        setResults([]);
        setRaw(null);
        setExecution(null);
        setLatency(null);
        setError('');
    }
    function update(index: number, patch: Partial<EvaluationQuestion>) {
        setQuestions(questions.map((q, i) => (i === index ? { ...q, ...patch } : q)));
        clear();
    }
    async function run() {
        if (running.current || !request) return;
        running.current = true;
        setBusy(true);
        onBusy(true);
        clear();
        const start = performance.now();
        try {
            if (fixture) setResults(sharedFixture(request));
            else {
                const response = await api('/evaluate', request);
                setRaw(response);
                const parsed = parseEvaluation(response, request);
                setResults(parsed.results);
                setExecution(parsed.execution);
                setLatency(performance.now() - start);
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            running.current = false;
            setBusy(false);
            onBusy(false);
        }
    }
    return (
        <section className="shared-workflow">
            <div className="shared-concept">
                <div>
                    <h2>One context. Independent questions.</h2>
                    <p>Orchestrate the three scoring primitives in one request.</p>
                </div>
                <div
                    className="shared-flow"
                    aria-label="One shared context branches to independent Boolean, Choice and Scale questions"
                >
                    <b>Shared context</b>
                    <span>branches to</span>
                    <div>
                        <span>BOOLEAN</span>
                        <span>CHOICE</span>
                        <span>SCALE</span>
                    </div>
                </div>
            </div>
            <div className="panel shared-context">
                {presentation ? (
                    <>
                        <span className="field-label">SHARED CONTEXT</span>
                        <p className="context-text">{context}</p>
                    </>
                ) : (
                    <fieldset disabled={busy}>
                        <label className="field-label" htmlFor="shared-text">
                            SHARED CONTEXT
                        </label>
                        <textarea
                            id="shared-text"
                            rows={4}
                            value={context}
                            onChange={(e) => {
                                setContext(e.target.value);
                                clear();
                            }}
                        />
                        <button
                            className="subtle"
                            onClick={() => {
                                setContext(sharedPreset.context);
                                setQuestions(sharedPreset.questions);
                                clear();
                            }}
                        >
                            Load fictional customer example
                        </button>
                    </fieldset>
                )}
            </div>
            {!presentation && (
                <fieldset disabled={busy} className="shared-editors">
                    {questions.map((q, i) => (
                        <section className="panel question-editor" key={q.id}>
                            <div className="panel-heading">
                                <h3>Question {i + 1}</h3>
                                <span className="badge">{q.id}</span>
                            </div>
                            <label className="field-label" htmlFor={`type-${q.id}`}>
                                SCORING PRIMITIVE
                            </label>
                            <select
                                id={`type-${q.id}`}
                                value={q.mode}
                                onChange={(e) =>
                                    update(i, {
                                        mode: e.target.value as Mode,
                                        ...(e.target.value === 'BOOLEAN'
                                            ? { labels: ['Yes', 'No'] }
                                            : e.target.value === 'SCALE' && !q.points.length
                                              ? {
                                                    points: [
                                                        { label: 'L', value: 0 },
                                                        { label: 'H', value: 1 },
                                                    ],
                                                }
                                              : e.target.value === 'CHOICE' && !q.labels.length
                                                ? { labels: ['A', 'B'] }
                                                : {}),
                                    })
                                }
                            >
                                {(['BOOLEAN', 'CHOICE', 'SCALE'] as const).map((m) => (
                                    <option key={m}>{m}</option>
                                ))}
                            </select>
                            <label className="field-label" htmlFor={`question-${q.id}`}>
                                QUESTION / LABEL MEANINGS
                            </label>
                            <textarea
                                id={`question-${q.id}`}
                                rows={3}
                                value={q.question}
                                onChange={(e) => update(i, { question: e.target.value })}
                            />
                            {q.mode === 'SCALE' ? (
                                <>
                                    <label className="field-label" htmlFor={`measurement-${q.id}`}>
                                        MEASUREMENT
                                    </label>
                                    <select
                                        id={`measurement-${q.id}`}
                                        value={q.measurement}
                                        onChange={(e) =>
                                            update(i, {
                                                measurement: e.target.value as 'ordinal' | 'interval',
                                            })
                                        }
                                    >
                                        <option value="ordinal">Ordinal: order only</option>
                                        <option value="interval">Interval: meaningful distances</option>
                                    </select>
                                    <p className="caption">
                                        Label/value mapping is included in the question. Define the scale
                                        meanings above.
                                    </p>
                                    {q.points.map((p, j) => (
                                        <div className="shared-point" key={j}>
                                            <input
                                                aria-label={`Question ${i + 1} scale label ${j + 1}`}
                                                value={p.label}
                                                onChange={(e) =>
                                                    update(i, {
                                                        points: q.points.map((x, k) =>
                                                            j === k ? { ...x, label: e.target.value } : x,
                                                        ),
                                                    })
                                                }
                                            />
                                            <input
                                                type="number"
                                                step="any"
                                                aria-label={`Question ${i + 1} scale value ${j + 1}`}
                                                value={Number.isFinite(p.value) ? p.value : ''}
                                                onChange={(e) =>
                                                    update(i, {
                                                        points: q.points.map((x, k) =>
                                                            j === k
                                                                ? {
                                                                      ...x,
                                                                      value:
                                                                          e.target.value === ''
                                                                              ? NaN
                                                                              : Number(e.target.value),
                                                                  }
                                                                : x,
                                                        ),
                                                    })
                                                }
                                            />
                                            <button
                                                aria-label={`Remove point ${j + 1} from question ${i + 1}`}
                                                onClick={() =>
                                                    update(i, { points: q.points.filter((_, k) => j !== k) })
                                                }
                                            >
                                                X
                                            </button>
                                        </div>
                                    ))}
                                    <button
                                        className="subtle"
                                        disabled={q.points.length >= 256}
                                        onClick={() =>
                                            update(i, {
                                                points: [
                                                    ...q.points,
                                                    {
                                                        label: '',
                                                        value:
                                                            Math.max(-1, ...q.points.map((p) => p.value)) + 1,
                                                    },
                                                ],
                                            })
                                        }
                                    >
                                        Add point
                                    </button>
                                </>
                            ) : (
                                <>
                                    <span className="field-label">
                                        {q.mode === 'BOOLEAN' ? 'TWO EXPLICIT LABELS' : 'CANDIDATE LABELS'}
                                    </span>
                                    {q.labels.map((label, j) => (
                                        <div className="shared-label" key={j}>
                                            <input
                                                aria-label={`Question ${i + 1} label ${j + 1}`}
                                                value={label}
                                                onChange={(e) =>
                                                    update(i, {
                                                        labels: q.labels.map((x, k) =>
                                                            j === k ? e.target.value : x,
                                                        ),
                                                    })
                                                }
                                            />
                                            {q.mode === 'CHOICE' && (
                                                <button
                                                    aria-label={`Remove label ${j + 1} from question ${i + 1}`}
                                                    onClick={() =>
                                                        update(i, {
                                                            labels: q.labels.filter((_, k) => j !== k),
                                                        })
                                                    }
                                                >
                                                    X
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                    {q.mode === 'CHOICE' && (
                                        <button
                                            className="subtle"
                                            disabled={q.labels.length >= 256}
                                            onClick={() => update(i, { labels: [...q.labels, ''] })}
                                        >
                                            Add label
                                        </button>
                                    )}
                                </>
                            )}
                            <div className="actions question-actions">
                                {(['up', 'down', 'remove'] as const).map((action) => (
                                    <button
                                        key={action}
                                        aria-label={`${action} question ${i + 1}`}
                                        disabled={
                                            (action === 'up' && i === 0) ||
                                            (action === 'down' && i === questions.length - 1)
                                        }
                                        onClick={() => {
                                            setQuestions(editQuestions(questions, action, i));
                                            clear();
                                        }}
                                    >
                                        {action === 'up'
                                            ? 'Move up'
                                            : action === 'down'
                                              ? 'Move down'
                                              : 'Remove'}
                                    </button>
                                ))}
                            </div>
                        </section>
                    ))}
                    <button
                        disabled={questions.length >= 32}
                        onClick={() => {
                            setQuestions(editQuestions(questions, 'add'));
                            clear();
                        }}
                    >
                        Add question ({questions.length}/32)
                    </button>
                </fieldset>
            )}
            {(error || validation) && (
                <div className="error" role="alert">
                    {error || validation}
                </div>
            )}
            <div className="actions">
                <button className="primary" disabled={busy || !!validation} onClick={() => void run()}>
                    {busy ? 'Evaluating...' : fixture ? 'Show shared fixture' : 'Run all'}
                </button>
                <span className="caption">
                    {fixture
                        ? 'Illustrative, unmeasured. No server diagnostics.'
                        : 'POST /evaluate | Sharing configured at server startup.'}
                </span>
            </div>
            {execution && (
                <div className="execution" role="status">
                    Server strategy: <b>{String(execution.strategy)}</b> | Shared prefix:{' '}
                    {String(execution.shared_prefix_tokens)} tokens | Batch: {String(execution.n_batch)} /
                    microbatch: {String(execution.n_ubatch)} | Fallback:{' '}
                    {execution.fallback_reason === null ? 'none' : String(execution.fallback_reason)} |
                    Interactive latency: {latency?.toFixed(0)} ms
                </div>
            )}
            <div className="shared-results" aria-live="polite">
                {results.map((r, i) => (
                    <section className="panel result-panel" key={r.id}>
                        <div className="panel-heading">
                            <h2>Question {i + 1}</h2>
                            <span className="badge">{r.type.toUpperCase()}</span>
                        </div>
                        <p className="result-question">{questions[i].question}</p>
                        {distribution(r.parsed)}
                    </section>
                ))}
            </div>
            <p className="caption">
                Direct is a structured readout from a prepared model state, not shortened Chat. Weights are
                not calibrated correctness probabilities. Labels, tokenization, templates and readout
                boundaries affect results. Direct does not universally replace reasoning. Questions do not see
                each other's answers; sharing must preserve independent evaluation semantics.
            </p>
            {!presentation && (
                <>
                    <p className="caption">
                        Enable --evaluate on llama-server. Optional --evaluate-shared-prefix reuses eligible
                        prefixes within this request only; fresh evaluation is the default and fallback. The
                        first request after model load may be slower due to warm-up. UI latency is not a
                        reproducible benchmark.
                    </p>
                    <details className="advanced">
                        <summary>
                            Advanced <span>Request, response and server diagnostics</span>
                        </summary>
                        <div className="advanced-content">
                            <p>
                                Endpoint: /evaluate | Model: {model || 'not detected'} | Target: {target}
                            </p>
                            <h3>Full request JSON</h3>
                            <pre>{JSON.stringify(request, null, 2)}</pre>
                            <h3>Full response JSON</h3>
                            <pre>
                                {raw === null
                                    ? fixture
                                        ? 'Fixture: no server response or execution diagnostics.'
                                        : 'No response yet.'
                                    : JSON.stringify(raw, null, 2)}
                            </pre>
                            {results.map((r) => (
                                <details key={r.id}>
                                    <summary>{r.id}: token IDs, counts, SUM / MEAN log scores</summary>
                                    <pre>{JSON.stringify(r.parsed.rows, null, 2)}</pre>
                                </details>
                            ))}
                        </div>
                    </details>
                </>
            )}
        </section>
    );
}
