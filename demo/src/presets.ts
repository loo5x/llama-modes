import type { Mode, Point } from './api';

export type Preset = {
    name: string;
    mode: Mode;
    question: string;
    labels?: string[];
    points?: Point[];
    measurement?: 'ordinal' | 'interval';
};
const symbols = (start: number, count: number) =>
    Array.from({ length: count }, (_, i) => ({ label: String.fromCharCode(65 + i), value: start + i }));
export const presets: Preset[] = [
    { name: 'Fact check', mode: 'BOOLEAN', question: 'Is Paris the capital of France?' },
    {
        name: 'Product sentiment',
        mode: 'CHOICE',
        question: 'Classify the sentiment: "The screen is beautiful, but the battery barely lasts an hour."',
        labels: ['positive', 'neutral', 'negative'],
    },
    {
        name: 'Comment favorability',
        mode: 'SCALE',
        question:
            'How favorable is this comment on a scale from 0 to 10? 0 means very unfavorable, 5 neutral, 10 very favorable. Comment: "Thoughtfully designed, easy to use, and a real improvement. I would happily recommend it."',
        points: symbols(0, 11),
        measurement: 'interval',
    },
    {
        name: 'Topic classification',
        mode: 'CHOICE',
        question: 'Classify the topic: "The telescope captured a new image of a distant galaxy."',
        labels: ['space science', 'financial markets', 'team sports'],
    },
    {
        name: 'Likert agreement',
        mode: 'SCALE',
        question:
            'Rate agreement with "The instructions were clear" based on: "I understood most steps, but the final setup was confusing." 1 strongly disagree; 2 disagree; 3 neither agree nor disagree; 4 agree; 5 strongly agree.',
        points: symbols(1, 5),
        measurement: 'ordinal',
    },
    {
        name: 'Severity rating',
        mode: 'SCALE',
        question:
            'Rate this fictional support incident. 0 no impact; 1 cosmetic issue; 2 one feature unavailable; 3 service unavailable. Incident: "Users can sign in, but file export fails for everyone."',
        points: symbols(0, 4),
        measurement: 'ordinal',
    },
];

export const sharedPreset: { context: string; questions: import('./api').EvaluationQuestion[] } = {
    context:
        'Fictional customer message: I bought the Northstar desk lamp last week. The light is pleasant and the controls are simple, but the charging port stopped working after two days. Support replied quickly and offered a replacement. I am disappointed that a new lamp failed, although I appreciate the helpful reply.',
    questions: [
        {
            id: 'dissatisfied',
            mode: 'BOOLEAN',
            question:
                'Is the customer dissatisfied with the product? Yes means dissatisfied; No means not dissatisfied.',
            labels: ['Yes', 'No'],
            points: [],
            measurement: 'ordinal',
        },
        {
            id: 'topic',
            mode: 'CHOICE',
            question: 'What is the primary topic of the customer message?',
            labels: ['product reliability', 'delivery', 'price'],
            points: [],
            measurement: 'ordinal',
        },
        {
            id: 'severity',
            mode: 'SCALE',
            question:
                'Rate the product issue severity: 0 no issue, 1 cosmetic issue, 2 a feature fails, 3 unusable product.',
            labels: [],
            points: [
                { label: 'A', value: 0 },
                { label: 'B', value: 1 },
                { label: 'C', value: 2 },
                { label: 'D', value: 3 },
            ],
            measurement: 'ordinal',
        },
    ],
};
