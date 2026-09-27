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
