import { useEffect, useRef, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
    ArrowRight,
    Check,
    ChevronDown,
    Copy,
    Layers3,
    Maximize2,
    Play,
    Plus,
    RefreshCw,
    Settings2,
    X,
} from 'lucide-react';
import {
    agreement,
    api,
    chartData,
    makeRequests,
    object,
    parseChat,
    parseDirect,
    type DirectResult,
    type Mode,
    type Point,
} from './api';
import { presets, type Preset } from './presets';
import { scaleFixture } from './fixtures';

type Run = {
    raw: unknown;
    request: unknown;
    endpoint: string;
    latency: number | null;
    parsed?: DirectResult;
    chat?: ReturnType<typeof parseChat>;
    error?: string;
};
const format = (n?: number) =>
    n === undefined ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
const json = (x: unknown) => JSON.stringify(x, null, 2);
const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));
const fixtureMode = new URLSearchParams(window.location.search).get('fixture') === '1';
const labelValue = (label: string, points: { label: string; value?: number }[]) => {
    const point = points.find((p) => p.label === label);
    return point?.value !== undefined ? `${label} / value ${format(point.value)}` : label;
};

function Distribution({ result }: { result: DirectResult }) {
    return (
        <>
            {result.measurement && (
                <div className="summary-grid">
                    <div className="score">
                        <span>{result.measurement === 'interval' ? 'EXPECTED VALUE' : 'MODE'}</span>
                        <strong>
                            {result.measurement === 'interval'
                                ? format(result.expected)
                                : result.mode?.join(', ')}
                        </strong>
                        <small>
                            {result.measurement === 'interval'
                                ? 'Derived from the full distribution'
                                : 'Ordinal scale: order has meaning'}
                        </small>
                    </div>
                    <div className="summary-details">
                        <div>
                            <span>Mode</span>
                            <b>
                                {result.rows
                                    .filter((row) => result.mode?.includes(row.value!))
                                    .map((row) => labelValue(row.label, result.rows))
                                    .join(', ')}
                            </b>
                        </div>
                        <div>
                            <span>Median</span>
                            <b>{format(result.median)}</b>
                        </div>
                        <div>
                            <span>q25 - q75</span>
                            <b>
                                {format(result.q25)} - {format(result.q75)}
                            </b>
                        </div>
                        {result.measurement === 'interval' && (
                            <div>
                                <span>Standard deviation</span>
                                <b>{format(result.deviation)}</b>
                            </div>
                        )}
                    </div>
                </div>
            )}
            {!result.measurement && (
                <div className="answer-heading">
                    <span>HIGHEST WEIGHT</span>
                    <strong>{result.winners.join(' / ')}</strong>
                </div>
            )}
            {result.measurement ? (
                <div
                    className="chart"
                    role="img"
                    aria-label="Relative weight distribution; exact values are listed below"
                >
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                            data={chartData(result.rows)}
                            margin={{ top: 14, right: 8, bottom: 0, left: -22 }}
                        >
                            <CartesianGrid vertical={false} stroke="#2a3337" />
                            <XAxis dataKey="name" stroke="#9aa8ae" tickLine={false} axisLine={false} />
                            <YAxis stroke="#9aa8ae" tickLine={false} axisLine={false} unit="%" />
                            <Tooltip
                                cursor={{ fill: '#ffffff08' }}
                                contentStyle={{
                                    background: '#181e21',
                                    border: '1px solid #3a454b',
                                    borderRadius: 8,
                                }}
                                formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Relative weight']}
                            />
                            <Bar
                                dataKey="percent"
                                fill="#a6d8ba"
                                radius={[5, 5, 0, 0]}
                                maxBarSize={52}
                                isAnimationActive={false}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            ) : null}
            <div className={result.measurement ? 'point-weights' : 'ranked'}>
                {[...result.rows]
                    .sort((a, b) => (result.measurement ? a.value! - b.value! : b.weight - a.weight))
                    .map((row) =>
                        result.measurement ? (
                            <div key={row.label}>
                                <span>
                                    {row.value} <small>{row.label}</small>
                                </span>
                                <b>{(row.weight * 100).toFixed(1)}%</b>
                            </div>
                        ) : (
                            <div className="candidate-bar" key={row.label}>
                                <div>
                                    <span>{row.label}</span>
                                    <b>{(row.weight * 100).toFixed(2)}%</b>
                                </div>
                                <div className="bar-track">
                                    <div style={{ width: `${row.weight * 100}%` }} />
                                </div>
                            </div>
                        ),
                    )}
            </div>
            <p className="caption">{result.weightKind}. These weights are not calibrated confidence.</p>
        </>
    );
}

function ResultCard({
    run,
    side,
    busy,
    points,
}: {
    run: Run | null;
    side: 'DIRECT' | 'CHAT';
    busy: boolean;
    points: Point[];
}) {
    return (
        <section className="panel result-panel" aria-live="polite">
            <div className="panel-heading">
                <h2>{side === 'DIRECT' ? 'Direct evaluation' : 'Chat completion'}</h2>
                <span className="badge">{side}</span>
            </div>
            {!run ? (
                <div className="empty">
                    <Layers3 size={34} strokeWidth={1} />
                    <h3>{busy ? 'Evaluating locally...' : 'Ready when you are'}</h3>
                    <p>
                        {side === 'DIRECT'
                            ? 'Score the supplied alternatives and inspect the result.'
                            : 'Generate an answer to the same task.'}
                    </p>
                </div>
            ) : (
                <>
                    {run.error && (
                        <div className="error" role="alert">
                            {run.error}
                        </div>
                    )}
                    {run.parsed && <Distribution result={run.parsed} />}
                    {run.chat && (
                        <>
                            <div className="answer-heading">
                                <span>EXACT FINAL ANSWER</span>
                                <strong>
                                    {run.chat.answer
                                        ? labelValue(run.chat.answer, points)
                                        : 'No exact answer'}
                                </strong>
                            </div>
                            <p className={`chat-content ${run.chat.answer ? 'exact-content' : ''}`}>
                                {run.chat.content || 'No final content was returned.'}
                            </p>
                            {!run.chat.answer && (
                                <p className="caption">
                                    A truncated answer, reasoning-only response, or extra prose is not
                                    silently converted into a label.
                                </p>
                            )}
                            {run.chat.reasoning && (
                                <details>
                                    <summary>Reasoning returned by the model</summary>
                                    <pre>{run.chat.reasoning}</pre>
                                </details>
                            )}
                        </>
                    )}
                    <div className="metrics">
                        <div>
                            <span>Interactive latency</span>
                            <b>
                                {run.latency === null ? 'Fixture: unmeasured' : `${format(run.latency)} ms`}
                            </b>
                        </div>
                        <div>
                            <span>{side === 'DIRECT' ? 'Generated tokens' : 'Completion tokens'}</span>
                            <b>
                                {side === 'DIRECT'
                                    ? '0 by design'
                                    : (run.chat?.completionTokens ?? 'Not reported')}
                            </b>
                        </div>
                    </div>
                </>
            )}
        </section>
    );
}

export default function App() {
    const [view, setView] = useState<Mode | 'COMPARE'>('SCALE');
    const [mode, setMode] = useState<Mode>('SCALE');
    const [question, setQuestion] = useState(presets[2].question);
    const [labels, setLabels] = useState(['Paris', 'London', 'New York']);
    const [points, setPoints] = useState<Point[]>(presets[2].points!);
    const [measurement, setMeasurement] = useState<'ordinal' | 'interval'>('interval');
    const [model, setModel] = useState('');
    const [target, setTarget] = useState('http://127.0.0.1:8080');
    const [connected, setConnected] = useState(false);
    const [connectionError, setConnectionError] = useState('');
    const [settings, setSettings] = useState(false);
    const [presentation, setPresentation] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [copied, setCopied] = useState('');
    const [direct, setDirect] = useState<Run | null>(null);
    const [chat, setChat] = useState<Run | null>(null);
    const running = useRef(false);
    const connectionVersion = useRef(0);
    const detectedModel = useRef('');

    async function connect() {
        const version = ++connectionVersion.current;
        if (fixtureMode) return;
        try {
            const config = await api('/config');
            if (version !== connectionVersion.current) return;
            setTarget(String(object(config).target));
            const models = await api('/v1/models');
            const list = object(models).data;
            if (!Array.isArray(list) || !list.length || typeof object(list[0]).id !== 'string')
                throw new Error('No model was reported by /v1/models');
            if (version !== connectionVersion.current) return;
            const nextModel = String(object(list[0]).id);
            if (nextModel !== detectedModel.current) {
                setDirect(null);
                setChat(null);
                detectedModel.current = nextModel;
            }
            setModel(nextModel);
            setConnected(true);
            setConnectionError('');
        } catch (e) {
            if (version === connectionVersion.current) {
                setConnected(false);
                setModel('');
                setDirect(null);
                setChat(null);
                setConnectionError(errorText(e));
            }
        }
    }
    useEffect(() => {
        void connect();
        const timer = setInterval(() => {
            if (!running.current) void connect();
        }, 15_000);
        return () => {
            clearInterval(timer);
            connectionVersion.current++;
        };
    }, []);

    function clearResults() {
        setDirect(null);
        setChat(null);
        setError('');
    }
    function applyPreset(preset: Preset) {
        setMode(preset.mode);
        if (view !== 'COMPARE') setView(preset.mode);
        setQuestion(preset.question);
        if (preset.labels) setLabels(preset.labels);
        if (preset.points) setPoints(preset.points);
        if (preset.measurement) setMeasurement(preset.measurement);
        clearResults();
    }
    function changeMode(next: Mode) {
        applyPreset(presets.find((p) => p.mode === next)!);
    }
    let requests: ReturnType<typeof makeRequests> | null = null;
    let validation = '';
    try {
        requests = makeRequests(
            mode,
            question,
            mode === 'BOOLEAN' ? ['Yes', 'No'] : labels,
            points,
            measurement,
            model,
        );
    } catch (e) {
        validation = errorText(e);
    }

    async function copy(value: string, label: string) {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(label);
        } catch {
            setError('Clipboard unavailable. Select and copy the JSON below.');
        }
    }
    function curl(endpoint: string, body: unknown) {
        const quote = (s: string) => "'" + s.replaceAll("'", "'\\''") + "'";
        return `curl ${quote(target + endpoint)} -H 'Content-Type: application/json' --data-raw ${quote(JSON.stringify(body))}`;
    }
    async function run(which: 'direct' | 'chat' | 'both') {
        if (running.current || !requests) return;
        running.current = true;
        setBusy(true);
        setError('');
        const snapshot = requests;
        if (which === 'both') {
            setDirect(null);
            setChat(null);
        }
        const execute = async (side: 'direct' | 'chat') => {
            const endpoint = side === 'direct' ? snapshot.endpoint : '/v1/chat/completions';
            const body = side === 'direct' ? snapshot.direct : snapshot.chat;
            const start = performance.now();
            let raw: unknown = null;
            let latency: number | null = null;
            let result: Run;
            try {
                if (fixtureMode) {
                    if (side !== 'direct' || mode !== 'SCALE')
                        throw new Error(
                            'Fixture preview supports only SCALE. Remove ?fixture=1 to run live inference.',
                        );
                    raw = scaleFixture(points, measurement);
                } else {
                    raw = await api(endpoint, body);
                    latency = performance.now() - start;
                }
                const parsed = side === 'direct' ? parseDirect(raw, mode, snapshot.labels) : undefined;
                if (
                    parsed &&
                    mode === 'SCALE' &&
                    (parsed.measurement !== measurement ||
                        parsed.rows.some(
                            (row) => !points.some((p) => p.label === row.label && p.value === row.value),
                        ))
                )
                    throw new Error('Malformed response: scale mapping or measurement differs from request');
                result = {
                    raw,
                    request: body,
                    endpoint,
                    latency,
                    ...(parsed ? { parsed } : { chat: parseChat(raw, snapshot.labels) }),
                };
            } catch (e) {
                result = {
                    raw,
                    request: body,
                    endpoint,
                    latency: fixtureMode ? null : performance.now() - start,
                    error: errorText(e),
                };
            }
            if (side === 'direct') setDirect(result);
            else setChat(result);
        };
        try {
            if (which !== 'chat') await execute('direct');
            if (which !== 'direct') await execute('chat');
        } finally {
            running.current = false;
            setBusy(false);
        }
    }
    const match = direct?.parsed && chat?.chat ? agreement(direct.parsed.winners, chat.chat.answer) : null;

    return (
        <div className={presentation ? 'app presentation' : 'app'}>
            <header>
                <div className="brand">
                    <div className="brand-mark">
                        <Layers3 size={24} />
                    </div>
                    <div>
                        <b>
                            llama-modes<span className="version">v0.4</span>
                        </b>
                        <p>Direct structured inference for local LLMs</p>
                    </div>
                </div>
                <div className="header-controls">
                    <span className={`connection ${connected ? 'online' : ''}`}>
                        <i />
                        {fixtureMode ? 'Fixture preview' : connected ? 'Connected' : 'Disconnected'}
                    </span>
                    <button
                        className="icon-button connection-settings"
                        aria-label="Connection settings"
                        onClick={() => setSettings(!settings)}
                    >
                        <Settings2 size={18} />
                    </button>
                    <button className="presentation-button" onClick={() => setPresentation(!presentation)}>
                        <Maximize2 size={16} />
                        {presentation ? 'Exit presentation' : 'Presentation mode'}
                    </button>
                </div>
            </header>
            {fixtureMode && (
                <div className="fixture-banner">
                    FIXTURE / DEMO DATA - Illustrative distribution. No live model, inference, or measured
                    latency.
                </div>
            )}
            {settings && !presentation && (
                <section className="settings panel">
                    <h2>Local connection</h2>
                    <p>Target: {target}</p>
                    <p>
                        Set <code>LLAMA_SERVER_URL=http://127.0.0.1:8080</code> in{' '}
                        <code>demo/.env.local</code> and restart the demo to change the target. Only HTTP
                        loopback addresses are accepted.
                    </p>
                    <button disabled={busy} onClick={() => void connect()}>
                        <RefreshCw size={16} />
                        Reconnect
                    </button>
                    {connectionError && <p className="error">{connectionError}</p>}
                </section>
            )}
            <main>
                <div className="intro">
                    <div>
                        <div className="eyebrow">THE LOCAL INFERENCE WORKBENCH</div>
                        <h1>A judgment. A choice. A distribution.</h1>
                        <p>Evaluate supplied alternatives directly at the model's prepared response state.</p>
                    </div>
                    <div className="model-context">
                        <span>MODEL</span>
                        <b>{fixtureMode ? 'Illustrative fixture' : model || 'No model detected'}</b>
                        <small>{target.replace('http://', '')}</small>
                    </div>
                </div>
                <nav aria-label="Inference views">
                    {(['BOOLEAN', 'CHOICE', 'SCALE', 'COMPARE'] as const).map((tab) => (
                        <button
                            key={tab}
                            disabled={busy}
                            className={view === tab ? 'active' : ''}
                            onClick={() => {
                                if (tab !== 'COMPARE') changeMode(tab);
                                setView(tab);
                                clearResults();
                            }}
                        >
                            {tab}
                            <span>
                                {tab === 'BOOLEAN'
                                    ? '01'
                                    : tab === 'CHOICE'
                                      ? '02'
                                      : tab === 'SCALE'
                                        ? '03'
                                        : '04'}
                            </span>
                        </button>
                    ))}
                </nav>
                {presentation && (
                    <div className="presentation-context">
                        <span className="field-label">{view === 'COMPARE' ? `COMPARE / ${mode}` : mode}</span>
                        <p>{question}</p>
                        {mode === 'SCALE' && (
                            <small>Symbolic labels are sent to the model with the label/value mapping.</small>
                        )}
                    </div>
                )}
                <div className={`workspace ${view === 'COMPARE' ? 'compare' : ''}`}>
                    <section className="panel input-panel">
                        <div className="panel-heading">
                            <h2>
                                {view === 'COMPARE'
                                    ? 'Interactive comparison'
                                    : `${mode[0]}${mode.slice(1).toLowerCase()} evaluation`}
                            </h2>
                            <span className="badge">INPUT</span>
                        </div>
                        <fieldset disabled={busy}>
                            <label className="field-label" htmlFor="preset">
                                START WITH AN EXAMPLE
                            </label>
                            <div className="select-wrap">
                                <select
                                    id="preset"
                                    value=""
                                    onChange={(e) => applyPreset(presets[Number(e.target.value)])}
                                >
                                    <option value="" disabled>
                                        Choose a preset
                                    </option>
                                    {presets.map((p, i) => (
                                        <option key={p.name} value={i}>
                                            {p.name}
                                        </option>
                                    ))}
                                </select>
                                <ChevronDown size={16} />
                            </div>
                            {view === 'COMPARE' && (
                                <div className="segmented">
                                    {(['BOOLEAN', 'CHOICE', 'SCALE'] as Mode[]).map((m) => (
                                        <button
                                            className={mode === m ? 'selected' : ''}
                                            key={m}
                                            onClick={() => changeMode(m)}
                                        >
                                            {m}
                                        </button>
                                    ))}
                                </div>
                            )}
                            <label className="field-label" htmlFor="question">
                                {mode === 'SCALE' ? 'TASK / COMMENT' : 'QUESTION'}
                            </label>
                            <textarea
                                id="question"
                                rows={6}
                                value={question}
                                onChange={(e) => {
                                    setQuestion(e.target.value);
                                    clearResults();
                                }}
                            />
                            {mode === 'BOOLEAN' && (
                                <div className="boolean-options">
                                    <span>YES</span>
                                    <span>NO</span>
                                    <p>Two supplied alternatives. Zero generated answer tokens.</p>
                                </div>
                            )}
                            {mode === 'CHOICE' && (
                                <>
                                    <div className="field-label">CANDIDATE LABELS</div>
                                    <div className="label-list">
                                        {labels.map((label, i) => (
                                            <div key={i}>
                                                <input
                                                    aria-label={`Candidate ${i + 1}`}
                                                    value={label}
                                                    onChange={(e) => {
                                                        setLabels(
                                                            labels.map((x, j) =>
                                                                i === j ? e.target.value : x,
                                                            ),
                                                        );
                                                        clearResults();
                                                    }}
                                                />
                                                <button
                                                    className="icon-button"
                                                    aria-label={`Remove candidate ${i + 1}`}
                                                    onClick={() => {
                                                        setLabels(labels.filter((_, j) => i !== j));
                                                        clearResults();
                                                    }}
                                                >
                                                    <X size={16} />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                    <button
                                        className="subtle"
                                        onClick={() => {
                                            setLabels([...labels, '']);
                                            clearResults();
                                        }}
                                    >
                                        <Plus size={15} />
                                        Add candidate
                                    </button>
                                    <p className="caption">
                                        Multi-token labels are supported. Inspect token counts and log scores
                                        in Advanced.
                                    </p>
                                </>
                            )}
                            {mode === 'SCALE' && (
                                <>
                                    <div className="field-label">MEASUREMENT</div>
                                    <div className="segmented">
                                        {(['ordinal', 'interval'] as const).map((m) => (
                                            <button
                                                key={m}
                                                className={measurement === m ? 'selected' : ''}
                                                onClick={() => {
                                                    setMeasurement(m);
                                                    clearResults();
                                                }}
                                            >
                                                {m === 'ordinal' ? 'Ordinal' : 'Interval'}
                                            </button>
                                        ))}
                                    </div>
                                    <p className="caption">
                                        {measurement === 'interval'
                                            ? 'You assert that numeric distances have meaning. Expected value is derived from all point weights.'
                                            : 'Order has meaning. Expected value and standard deviation are not reported.'}
                                    </p>
                                    {question === presets[2].question && (
                                        <div className="semantic-scale">
                                            <span>
                                                <b>0</b> Very unfavorable
                                            </span>
                                            <span>
                                                <b>5</b> Neutral
                                            </span>
                                            <span>
                                                <b>10</b> Very favorable
                                            </span>
                                        </div>
                                    )}
                                    <p className="caption">
                                        Symbolic labels are sent to the model with this label/value mapping.
                                    </p>
                                    <details className="encoding">
                                        <summary>
                                            Encoding / Edit mapping <span>{points.length} labels</span>
                                        </summary>
                                        <div className="scale-editor">
                                            {points.map((p, i) => (
                                                <div key={i}>
                                                    <input
                                                        aria-label={`Scale label ${i + 1}`}
                                                        value={p.label}
                                                        onChange={(e) => {
                                                            setPoints(
                                                                points.map((x, j) =>
                                                                    i === j
                                                                        ? { ...x, label: e.target.value }
                                                                        : x,
                                                                ),
                                                            );
                                                            clearResults();
                                                        }}
                                                    />
                                                    <span>=</span>
                                                    <input
                                                        type="number"
                                                        step="any"
                                                        aria-label={`Scale value ${i + 1}`}
                                                        value={Number.isFinite(p.value) ? p.value : ''}
                                                        onChange={(e) => {
                                                            setPoints(
                                                                points.map((x, j) =>
                                                                    i === j
                                                                        ? {
                                                                              ...x,
                                                                              value:
                                                                                  e.target.value === ''
                                                                                      ? NaN
                                                                                      : Number(
                                                                                            e.target.value,
                                                                                        ),
                                                                          }
                                                                        : x,
                                                                ),
                                                            );
                                                            clearResults();
                                                        }}
                                                    />
                                                    <button
                                                        className="icon-button"
                                                        aria-label={`Remove scale point ${i + 1}`}
                                                        onClick={() => {
                                                            setPoints(points.filter((_, j) => i !== j));
                                                            clearResults();
                                                        }}
                                                    >
                                                        <X size={13} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                        <button
                                            className="subtle"
                                            onClick={() => {
                                                setPoints([
                                                    ...points,
                                                    {
                                                        label: '',
                                                        value:
                                                            Math.max(...points.map((p) => p.value), -1) + 1,
                                                    },
                                                ]);
                                                clearResults();
                                            }}
                                        >
                                            <Plus size={15} />
                                            Add point
                                        </button>
                                        <p className="caption">
                                            This mapping is included in the prompt. Symbols can avoid numeric
                                            token-prefix overlap; they are not universally unbiased.
                                        </p>
                                    </details>
                                </>
                            )}
                        </fieldset>
                        {(validation || error) && (
                            <div className="error" role="alert">
                                {error || validation}
                            </div>
                        )}
                        <div className="actions">
                            <button
                                className="primary"
                                disabled={busy || !!validation}
                                onClick={() => void run('direct')}
                            >
                                <Play size={15} />
                                {fixtureMode ? 'Show fixture' : 'Run Direct'}
                            </button>
                            {view === 'COMPARE' && (
                                <>
                                    <button
                                        disabled={busy || !!validation || fixtureMode}
                                        onClick={() => void run('chat')}
                                    >
                                        Run Chat
                                    </button>
                                    <button
                                        disabled={busy || !!validation || fixtureMode}
                                        onClick={() => void run('both')}
                                    >
                                        Run Both
                                        <ArrowRight size={15} />
                                    </button>
                                </>
                            )}
                        </div>
                    </section>
                    <div className="results">
                        <ResultCard
                            run={direct}
                            side="DIRECT"
                            busy={busy}
                            points={mode === 'SCALE' ? points : []}
                        />
                        {view === 'COMPARE' && (
                            <>
                                <ResultCard
                                    run={chat}
                                    side="CHAT"
                                    busy={busy}
                                    points={mode === 'SCALE' ? points : []}
                                />
                                <div className="agreement">
                                    <span>
                                        {mode === 'SCALE'
                                            ? 'Direct mode / Chat agreement'
                                            : 'Direct / Chat agreement'}
                                    </span>
                                    <b>
                                        {match === null
                                            ? 'Not available (missing answer or tie)'
                                            : match
                                              ? 'Same result'
                                              : 'Different'}
                                    </b>
                                </div>
                                <p className="caption comparison-notice">
                                    Sequential timing: Direct finishes before Chat starts when running both.
                                    This interactive comparison is not a benchmark. Different results do not
                                    establish which procedure is correct.
                                </p>
                            </>
                        )}
                        <div className="interpretation">
                            <span>READ THE DISTRIBUTION</span>
                            <p>
                                {mode === 'SCALE'
                                    ? 'A middle score can mean a narrow middle preference or a split between extremes. The point weights show the difference.'
                                    : 'The highest-scoring label reflects the model at this evaluation state. Autoregressive reasoning can lead to a different answer.'}
                            </p>
                        </div>
                    </div>
                </div>
                {!presentation && (
                    <details className="advanced">
                        <summary>
                            Advanced <span>Requests, raw responses, tokens and log scores</span>
                        </summary>
                        <div className="advanced-content">
                            <p>
                                Model: {model || 'not detected'} | Endpoint: {requests?.endpoint} | Target:{' '}
                                {target}
                            </p>
                            <div className="actions">
                                <button
                                    disabled={!requests}
                                    onClick={() => void copy(json(requests?.direct), 'request')}
                                >
                                    <Copy size={14} />
                                    Copy request JSON
                                </button>
                                <button
                                    disabled={!requests}
                                    onClick={() =>
                                        requests &&
                                        void copy(curl(requests.endpoint, requests.direct), 'curl')
                                    }
                                >
                                    <Copy size={14} />
                                    Copy curl (POSIX shell)
                                </button>
                                <button
                                    disabled={!direct}
                                    onClick={() => void copy(json(direct?.raw), 'response')}
                                >
                                    Copy response JSON
                                </button>
                                {copied && (
                                    <small role="status">
                                        <Check size={14} />
                                        Copied {copied}
                                    </small>
                                )}
                            </div>
                            <h3>Request JSON</h3>
                            <pre>{json(requests?.direct)}</pre>
                            {direct?.parsed && (
                                <div className="table-scroll">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Label</th>
                                                <th>Token IDs</th>
                                                <th>Count</th>
                                                <th>SUM log p</th>
                                                <th>MEAN log p</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {direct.parsed.rows.map((r) => (
                                                <tr key={r.label}>
                                                    <td>{r.label}</td>
                                                    <td>{r.tokenIds?.join(', ')}</td>
                                                    <td>{r.tokenCount}</td>
                                                    <td>{r.sum ?? 'Not returned'}</td>
                                                    <td>{r.mean ?? 'Not returned'}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                            {direct && (
                                <>
                                    <h3>Direct response JSON</h3>
                                    <pre>{json(direct.raw)}</pre>
                                </>
                            )}
                            {chat && (
                                <>
                                    <h3>
                                        Chat request / response (includes usage and fingerprint when returned)
                                    </h3>
                                    <button
                                        onClick={() =>
                                            void copy(curl(chat.endpoint, chat.request), 'chat curl')
                                        }
                                    >
                                        Copy chat curl
                                    </button>
                                    <pre>{json({ request: chat.request, response: chat.raw })}</pre>
                                </>
                            )}
                        </div>
                    </details>
                )}
                <footer>
                    <span>llama-modes / Built on llama.cpp</span>
                    <span>Local inference. No telemetry. No cloud services.</span>
                </footer>
            </main>
        </div>
    );
}
