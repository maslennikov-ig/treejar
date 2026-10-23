import { useCallback, useEffect, useState } from 'react';
import { Bell, RefreshCw, Send, Settings } from 'lucide-react';
import { fetchNotificationConfig, sendTestNotification } from '@/api/operators';
import AIQualityControlsPanel from '@/components/AIQualityControlsPanel';
import { HelpTooltip } from '@/components/HelpTooltip';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import {
    ActionMessageBox,
    Badge,
    Field,
    Panel,
    RefreshButton,
    ViewBanner,
    errorMessage,
} from '@/components/ui/Primitives';
import type { ActionMessage } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/Toast';
import { useI18n } from '@/i18n';
import type { NotificationConfig } from '@/types/operators';

export default function SettingsView() {
    const { t } = useI18n();
    const { pushToast } = useToast();
    const [config, setConfig] = useState<NotificationConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [sendingTest, setSendingTest] = useState(false);
    const [confirmTestOpen, setConfirmTestOpen] = useState(false);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    const loadConfig = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            setConfig(await fetchNotificationConfig());
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void loadConfig();
    }, [loadConfig]);

    async function handleConfirmSendTest() {
        setConfirmTestOpen(false);
        setSendingTest(true);
        setMessage(null);
        try {
            const result = await sendTestNotification();
            const text =
                result.status === 'sent'
                    ? t('settings.testSent')
                    : result.reason || t('settings.telegramNotConfigured');
            const tone = result.status === 'sent' ? 'success' : 'info';
            setMessage({ tone, text });
            pushToast({ tone, message: text });
        } catch (err) {
            const errText = errorMessage(err, t);
            setMessage({ tone: 'error', text: errText });
            pushToast({ tone: 'error', message: errText });
        } finally {
            setSendingTest(false);
        }
    }

    const loadingText = loading ? t('common.loading') : '—';

    return (
        <>
            <ViewBanner view="settings" />
            <section className="space-y-4 p-5" data-settings-view="">
                {message && <ActionMessageBox message={message} />}

                {/* Variant 6A: AI Quality Controls (Simple Mode 3 Cards + Collapsible Engineer Settings) */}
                <AIQualityControlsPanel />

                {/* Telegram & Runtime Session Settings */}
                <Panel
                    title={t('settings.title')}
                    subtitle={t('settings.subtitle')}
                    icon={Settings}
                    action={<RefreshButton loading={loading} onClick={() => void loadConfig()} />}
                >
                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-2">
                                    <Bell size={16} className="text-[var(--accent-primary)]" />
                                    <p className="text-sm font-semibold text-[var(--text-primary)]">
                                        {t('settings.telegramTitle')}
                                    </p>
                                    <HelpTooltip text={t('settings.telegramHelp')} />
                                </div>
                                <Badge
                                    label={
                                        config?.telegram_configured
                                            ? t('settings.configured')
                                            : t('settings.notConfigured')
                                    }
                                    tone={config?.telegram_configured ? 'green' : 'amber'}
                                />
                            </div>
                            <div className="mt-3 space-y-2">
                                <Field
                                    label={t('settings.botToken')}
                                    value={config?.telegram_bot_token || loadingText}
                                />
                                <Field
                                    label={t('settings.chatId')}
                                    value={config?.telegram_chat_id || loadingText}
                                />
                            </div>
                            <button
                                type="button"
                                disabled={sendingTest}
                                onClick={() => setConfirmTestOpen(true)}
                                className="mt-4 inline-flex items-center gap-2 rounded-md bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white hover:opacity-95 disabled:opacity-50"
                                data-send-telegram-test=""
                            >
                                {sendingTest ? (
                                    <RefreshCw size={14} className="animate-spin" />
                                ) : (
                                    <Send size={14} />
                                )}
                                {t('settings.sendTest')}
                            </button>
                        </div>

                        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
                            <p className="text-sm font-semibold text-[var(--text-primary)]">
                                {t('settings.sessionTitle')}
                            </p>
                            <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">
                                {t('settings.sessionBody')}
                            </p>
                        </div>
                    </div>
                </Panel>
            </section>

            <ConfirmDialog
                open={confirmTestOpen}
                title={t('settings.telegramTitle')}
                description={t('settings.confirmSendTest')}
                confirmLabel={t('settings.sendTest')}
                cancelLabel={t('common.cancel')}
                busy={sendingTest}
                onConfirm={() => void handleConfirmSendTest()}
                onCancel={() => setConfirmTestOpen(false)}
            />
        </>
    );
}
