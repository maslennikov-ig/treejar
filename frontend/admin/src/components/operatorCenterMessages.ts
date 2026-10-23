import type { ManagerReviewDetail } from '@/types/operators';

export interface OperatorActionMessage {
    tone: 'success' | 'info' | 'error';
    text: string;
}

export interface ManagerReviewMessageTexts {
    managerFallback: string;
    scored: (managerName: string, score: number, maxScore: number) => string;
    refreshFailed: string;
}

const DEFAULT_TEXTS: ManagerReviewMessageTexts = {
    managerFallback: 'Manager',
    scored: (managerName, score, maxScore) => `${managerName} scored ${score}/${maxScore}.`,
    refreshFailed: 'Review saved, but operator data failed to refresh.',
};

export function buildManagerReviewMessage(
    managerName: string | null | undefined,
    detail: Pick<ManagerReviewDetail, 'total_score' | 'max_score'>,
    refreshError: string | null,
    texts: ManagerReviewMessageTexts = DEFAULT_TEXTS,
): OperatorActionMessage {
    const baseText = texts.scored(managerName ?? texts.managerFallback, detail.total_score, detail.max_score);

    if (!refreshError) {
        return {
            tone: 'success',
            text: baseText,
        };
    }

    return {
        tone: 'info',
        text: `${baseText} ${texts.refreshFailed}`,
    };
}
