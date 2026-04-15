import type { ManagerReviewDetail } from '@/types/operators';

export interface OperatorActionMessage {
    tone: 'success' | 'info' | 'error';
    text: string;
}

export function buildManagerReviewMessage(
    managerName: string | null | undefined,
    detail: Pick<ManagerReviewDetail, 'total_score' | 'max_score'>,
    refreshError: string | null,
): OperatorActionMessage {
    const baseText = `${managerName ?? 'Manager'} scored ${detail.total_score}/${detail.max_score}.`;

    if (!refreshError) {
        return {
            tone: 'success',
            text: baseText,
        };
    }

    return {
        tone: 'info',
        text: `${baseText} Review saved, but operator data failed to refresh.`,
    };
}
