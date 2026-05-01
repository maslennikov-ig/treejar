import { useEffect, useMemo, useState } from 'react';
import {
    AlertTriangle,
    CheckCircle2,
    CircleDashed,
    ClipboardCheck,
    MinusCircle,
    Send,
    XCircle,
} from 'lucide-react';
import { submitClientSelfTest } from '@/api/operators';
import type {
    ClientSelfTestStatus,
    ClientSelfTestSubmitRequest,
} from '@/types/operators';

export const CLIENT_SELF_TEST_STORAGE_KEY = 'treejar-client-self-test-v1';

export interface ClientSelfTestScenario {
    id: string;
    title: string;
    intent: string;
    customerPrompt: string;
    expectedBot: string;
    expectedManager: string;
    backend: string;
}

export interface ClientSelfTestItemState {
    id: string;
    status: ClientSelfTestStatus;
    note: string;
}

interface ClientSelfTestDraft {
    testerName: string;
    overallComment: string;
    items: ClientSelfTestItemState[];
}

export const CLIENT_SELF_TEST_SCENARIOS: ClientSelfTestScenario[] = [
    {
        id: 'catalog-discovery',
        title: 'Каталог и подбор товара',
        intent: 'Проверить, что бот умеет подобрать офисные товары из каталога, а не отвечает общими словами.',
        customerPrompt: "I'd like to buy an executive chair for a manager and an L-shaped desk.",
        expectedBot: 'Даёт релевантные варианты, цены, наличие и не просит менеджера без причины.',
        expectedManager: 'В Telegram не должно быть эскалации, если клиент пока только выбирает товары.',
        backend: 'Сообщение проходит через историю диалога, RAG/catalog lookup и safety-проверки. Бот отвечает только по найденным товарам.',
    },
    {
        id: 'exact-sku',
        title: 'Точный SKU, цена и наличие',
        intent: 'Проверить “source of truth”: конкретный артикул должен отвечаться по Zoho/каталогу.',
        customerPrompt: 'Can you confirm price and availability for CH 410?',
        expectedBot: 'Возвращает конкретную цену, остаток и аккуратную формулировку без неподтверждённых обещаний.',
        expectedManager: 'Telegram молчит, если нет риска или просьбы о нестандартных условиях.',
        backend: 'SKU нормализуется, затем проверяется stock/price. Если запись не найдена, бот не выдумывает данные.',
    },
    {
        id: 'incomplete-proforma',
        title: 'Неполный invoice/proforma без лишней эскалации',
        intent: 'Проверить свежий фикс: invoice/proforma request не должен сразу уходить менеджеру.',
        customerPrompt: 'Please issue a proforma invoice for these items.',
        expectedBot: 'Просит подтвердить точные позиции/SKU и количество.',
        expectedManager: 'Telegram не получает generic escalation “требуется подтверждение менеджера”.',
        backend: 'Invoice/proforma intent теперь ведётся как quotation intent, пока нет payment terms, скидки или другого риска.',
    },
    {
        id: 'exact-quotation',
        title: 'Quotation/proforma с подтверждением менеджера',
        intent: 'Проверить, что точный заказ запускает draft quotation flow.',
        customerPrompt: 'Please make a quotation for 1 CH 410.',
        expectedBot: 'Не отправляет PDF клиенту напрямую. Клиент видит аккуратное подтверждение, что запрос обрабатывается.',
        expectedManager: 'В Telegram появляются кнопки “Подтвердить заказ”, “Отклонить”, “Ответить клиенту”.',
        backend: 'Создаётся draft Sale Order/PDF, состояние review кладётся в Redis, а отправка клиенту ждёт manager approval.',
    },
    {
        id: 'approval-rejection',
        title: 'Подтверждение и отклонение заказа',
        intent: 'Проверить обе ветки approval flow в админской группе.',
        customerPrompt: 'Use точный quotation-сценарий выше, затем нажмите approve или reject в Telegram.',
        expectedBot: 'После approve отправляет клиенту PDF/сообщение. После reject не отправляет PDF и даёт корректный отказ.',
        expectedManager: 'Telegram callback обновляет сообщение и показывает, что решение обработано.',
        backend: 'Callback достаёт review payload из Redis, отправляет документ через Wazzup только при approve и пишет audit-событие.',
    },
    {
        id: 'manager-private-reply',
        title: 'Ответ менеджера клиенту',
        intent: 'Проверить, что менеджер может вмешаться без ручного поиска клиента.',
        customerPrompt: 'Ask something that requires manager answer, then use “Ответить клиенту”.',
        expectedBot: 'Бот не спорит с менеджером и сохраняет контекст диалога.',
        expectedManager: 'Менеджер пишет текст, система доставляет его клиенту и отмечает действие.',
        backend: 'Telegram reply связывается с conversation UUID, сообщение уходит через Wazzup, затем попадает в outbound audit.',
    },
    {
        id: 'risk-boundaries',
        title: 'Консервативные границы',
        intent: 'Проверить, что опасные обязательства остаются под контролем человека.',
        customerPrompt: 'Please include net 30 payment terms and a 20% discount.',
        expectedBot: 'Не обещает кредитные условия или нестандартную скидку самостоятельно.',
        expectedManager: 'Telegram получает manager handoff, потому что это коммерческое решение.',
        backend: 'Правила verified answers отсекают payment terms, discount и рискованные обязательства от автоматизации.',
    },
    {
        id: 'telegram-tail-context',
        title: 'Длинный Telegram-контекст сохраняет последнюю реплику',
        intent: 'Проверить фикс Telegram truncation: менеджер должен видеть актуальный конец диалога.',
        customerPrompt: 'Send a long conversation, then finish with: “Can you issue invoice for 2 CH 410?”',
        expectedBot: 'Поведение зависит от полноты заказа, но последняя просьба клиента не теряется.',
        expectedManager: 'Если есть Telegram alert, он показывает последнюю user-реплику, а ранний контекст помечен как скрытый.',
        backend: 'Обрезка контекста теперь tail-preserving: сохраняются последние строки, затем весь текст HTML-экранируется.',
    },
    {
        id: 'language-sanity',
        title: 'English/Arabic sanity check',
        intent: 'Проверить, что бот сохраняет язык клиента в безопасных сценариях.',
        customerPrompt: 'Arabic: أحتاج كرسي مكتب مريح للمدير. English: I need a manager office chair.',
        expectedBot: 'Отвечает на языке клиента, не ломает SKU/quantity flow и не смешивает языки без нужды.',
        expectedManager: 'Эскалация появляется только по реальному риску, а не из-за языка сообщения.',
        backend: 'Language detection и prompt policy работают до финальной генерации ответа.',
    },
    {
        id: 'admin-visibility',
        title: 'Admin visibility и operator controls',
        intent: 'Проверить, что операционная часть видна не только в WhatsApp.',
        customerPrompt: 'Open /dashboard/ after test conversations.',
        expectedBot: 'WhatsApp-часть уже отработала в предыдущих сценариях.',
        expectedManager: 'В dashboard видны conversations, manager review surfaces, reports, AI controls и безопасные defaults.',
        backend: 'Админка читает защищённые API, не требует публичной страницы и оставляет acceptance checklist внутри admin session.',
    },
];

const STATUS_OPTIONS: Array<{
    status: ClientSelfTestStatus;
    label: string;
    Icon: typeof CheckCircle2;
    activeClassName: string;
}> = [
    {
        status: 'passed',
        label: 'Прошёл',
        Icon: CheckCircle2,
        activeClassName: 'border-emerald-400/70 bg-emerald-500/15 text-emerald-200',
    },
    {
        status: 'failed',
        label: 'Неверно',
        Icon: XCircle,
        activeClassName: 'border-rose-400/70 bg-rose-500/15 text-rose-200',
    },
    {
        status: 'skipped',
        label: 'Пропустить',
        Icon: MinusCircle,
        activeClassName: 'border-amber-400/70 bg-amber-500/15 text-amber-200',
    },
    {
        status: 'not_tested',
        label: 'Не проверял',
        Icon: CircleDashed,
        activeClassName: 'border-slate-500/70 bg-slate-700/40 text-slate-200',
    },
];

export function createInitialClientSelfTestItems(): ClientSelfTestItemState[] {
    return CLIENT_SELF_TEST_SCENARIOS.map((scenario) => ({
        id: scenario.id,
        status: 'not_tested',
        note: '',
    }));
}

export function updateClientSelfTestItem(
    items: ClientSelfTestItemState[],
    id: string,
    patch: Partial<Omit<ClientSelfTestItemState, 'id'>>,
): ClientSelfTestItemState[] {
    return items.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

export function buildClientSelfTestSubmitPayload(draft: ClientSelfTestDraft): ClientSelfTestSubmitRequest {
    const titlesById = new Map(CLIENT_SELF_TEST_SCENARIOS.map((scenario) => [scenario.id, scenario.title]));

    return {
        tester_name: draft.testerName.trim() || null,
        overall_comment: draft.overallComment.trim() || null,
        items: draft.items.map((item) => ({
            id: item.id,
            title: titlesById.get(item.id) ?? item.id,
            status: item.status,
            note: item.note.trim(),
        })),
    };
}

function readDraft(): ClientSelfTestDraft {
    const fallback: ClientSelfTestDraft = {
        testerName: '',
        overallComment: '',
        items: createInitialClientSelfTestItems(),
    };

    if (typeof window === 'undefined') {
        return fallback;
    }

    try {
        const raw = window.localStorage.getItem(CLIENT_SELF_TEST_STORAGE_KEY);
        if (!raw) {
            return fallback;
        }
        const parsed = JSON.parse(raw) as Partial<ClientSelfTestDraft>;
        const itemsById = new Map((parsed.items ?? []).map((item) => [item.id, item]));

        return {
            testerName: parsed.testerName ?? '',
            overallComment: parsed.overallComment ?? '',
            items: CLIENT_SELF_TEST_SCENARIOS.map((scenario) => {
                const saved = itemsById.get(scenario.id);
                return {
                    id: scenario.id,
                    status: saved?.status ?? 'not_tested',
                    note: saved?.note ?? '',
                };
            }),
        };
    } catch {
        return fallback;
    }
}

export default function AcceptanceDemo() {
    const [testerName, setTesterName] = useState(() => readDraft().testerName);
    const [overallComment, setOverallComment] = useState(() => readDraft().overallComment);
    const [items, setItems] = useState<ClientSelfTestItemState[]>(() => readDraft().items);
    const [submitState, setSubmitState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
    const [submitMessage, setSubmitMessage] = useState('');

    const counts = useMemo(() => {
        return items.reduce<Record<ClientSelfTestStatus, number>>(
            (acc, item) => {
                acc[item.status] += 1;
                return acc;
            },
            { passed: 0, failed: 0, skipped: 0, not_tested: 0 },
        );
    }, [items]);

    useEffect(() => {
        const draft: ClientSelfTestDraft = { testerName, overallComment, items };
        window.localStorage.setItem(CLIENT_SELF_TEST_STORAGE_KEY, JSON.stringify(draft));
    }, [testerName, overallComment, items]);

    const completedCount = items.length - counts.not_tested;

    async function handleSubmit() {
        setSubmitState('sending');
        setSubmitMessage('');

        try {
            const response = await submitClientSelfTest(
                buildClientSelfTestSubmitPayload({ testerName, overallComment, items }),
            );
            setSubmitState('sent');
            setSubmitMessage(`Отчёт отправлен в Telegram. Сценариев: ${response.submitted_count}.`);
        } catch (error) {
            setSubmitState('error');
            setSubmitMessage(error instanceof Error ? error.message : 'Не удалось отправить отчёт.');
        }
    }

    return (
        <section className="space-y-5">
            <div className="rounded-lg border border-emerald-400/20 bg-emerald-500/10 px-5 py-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-start gap-3">
                        <div className="mt-1 rounded-lg bg-emerald-500/15 p-2 text-emerald-300">
                            <ClipboardCheck size={22} />
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold text-white">Acceptance Demo</h2>
                            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-300">
                                Controlled self-test для заказчика: каждый сценарий показывает, что написать клиентом,
                                что должно произойти в WhatsApp, Telegram и на backend.
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                        <div className="rounded-lg border border-emerald-400/20 bg-slate-950/30 px-3 py-2">
                            <p className="text-slate-500">Прошло</p>
                            <p className="text-lg font-semibold text-emerald-300">{counts.passed}</p>
                        </div>
                        <div className="rounded-lg border border-rose-400/20 bg-slate-950/30 px-3 py-2">
                            <p className="text-slate-500">Неверно</p>
                            <p className="text-lg font-semibold text-rose-300">{counts.failed}</p>
                        </div>
                        <div className="rounded-lg border border-amber-400/20 bg-slate-950/30 px-3 py-2">
                            <p className="text-slate-500">Пропущено</p>
                            <p className="text-lg font-semibold text-amber-300">{counts.skipped}</p>
                        </div>
                        <div className="rounded-lg border border-white/[0.08] bg-slate-950/30 px-3 py-2">
                            <p className="text-slate-500">Прогресс</p>
                            <p className="text-lg font-semibold text-slate-100">
                                {completedCount}/{items.length}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
                <label className="block">
                    <span className="text-sm font-medium text-slate-300">Имя тестировщика</span>
                    <input
                        value={testerName}
                        onChange={(event) => setTesterName(event.target.value)}
                        maxLength={80}
                        className="mt-2 w-full rounded-lg border border-white/[0.08] bg-slate-900/80 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-400/60"
                        placeholder="Например: TreeJar owner"
                    />
                </label>

                <div className="rounded-lg border border-white/[0.08] bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
                    <div className="flex items-start gap-2">
                        <AlertTriangle size={16} className="mt-0.5 text-amber-300" />
                        <p>Используйте тестовый чат и не запускайте реальные рискованные условия без согласования.</p>
                    </div>
                </div>
            </div>

            <div className="space-y-4">
                {CLIENT_SELF_TEST_SCENARIOS.map((scenario, index) => {
                    const item = items.find((candidate) => candidate.id === scenario.id);
                    const selectedStatus = item?.status ?? 'not_tested';

                    return (
                        <article
                            key={scenario.id}
                            className="rounded-lg border border-white/[0.08] bg-slate-900/70 p-5 backdrop-blur-xl"
                        >
                            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                                <div>
                                    <div className="text-xs font-semibold uppercase text-emerald-300">
                                        Сценарий {index + 1}
                                    </div>
                                    <h3 className="mt-1 text-lg font-semibold text-white">{scenario.title}</h3>
                                    <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{scenario.intent}</p>
                                </div>

                                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[430px]">
                                    {STATUS_OPTIONS.map(({ status, label, Icon, activeClassName }) => {
                                        const active = selectedStatus === status;
                                        return (
                                            <button
                                                key={status}
                                                type="button"
                                                onClick={() => {
                                                    setItems((current) => (
                                                        updateClientSelfTestItem(current, scenario.id, { status })
                                                    ));
                                                }}
                                                className={`flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition ${
                                                    active
                                                        ? activeClassName
                                                        : 'border-white/[0.08] bg-slate-950/30 text-slate-400 hover:border-white/[0.18] hover:text-slate-100'
                                                }`}
                                            >
                                                <Icon size={16} />
                                                <span>{label}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
                                <div className="space-y-3 text-sm">
                                    <div>
                                        <p className="font-medium text-slate-200">Что написать клиентом</p>
                                        <p className="mt-1 rounded-lg bg-slate-950/40 px-3 py-2 font-mono text-slate-300">
                                            {scenario.customerPrompt}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="font-medium text-slate-200">Ожидаемый WhatsApp/bot результат</p>
                                        <p className="mt-1 leading-6 text-slate-400">{scenario.expectedBot}</p>
                                    </div>
                                </div>

                                <div className="space-y-3 text-sm">
                                    <div>
                                        <p className="font-medium text-slate-200">Ожидаемый Telegram/admin результат</p>
                                        <p className="mt-1 leading-6 text-slate-400">{scenario.expectedManager}</p>
                                    </div>
                                    <div>
                                        <p className="font-medium text-slate-200">Что происходит на backend</p>
                                        <p className="mt-1 leading-6 text-slate-400">{scenario.backend}</p>
                                    </div>
                                </div>
                            </div>

                            <label className="mt-4 block">
                                <span className="text-sm font-medium text-slate-300">Заметка по сценарию</span>
                                <textarea
                                    value={item?.note ?? ''}
                                    onChange={(event) => {
                                        setItems((current) => (
                                            updateClientSelfTestItem(current, scenario.id, { note: event.target.value })
                                        ));
                                    }}
                                    maxLength={800}
                                    rows={2}
                                    className="mt-2 w-full resize-y rounded-lg border border-white/[0.08] bg-slate-950/30 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-400/60"
                                    placeholder="Что получилось неверно, номер диалога, что нажимали в Telegram..."
                                />
                            </label>
                        </article>
                    );
                })}
            </div>

            <div className="rounded-lg border border-white/[0.08] bg-slate-900/80 p-5">
                <label className="block">
                    <span className="text-sm font-medium text-slate-300">Итоговый комментарий</span>
                    <textarea
                        value={overallComment}
                        onChange={(event) => setOverallComment(event.target.value)}
                        maxLength={1000}
                        rows={3}
                        className="mt-2 w-full resize-y rounded-lg border border-white/[0.08] bg-slate-950/30 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-400/60"
                        placeholder="Общее впечатление, что проверить повторно, что можно принимать..."
                    />
                </label>

                <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-slate-500">
                        Черновик сохраняется в браузере. После отправки команда получит summary в Telegram.
                    </p>
                    <button
                        type="button"
                        onClick={handleSubmit}
                        disabled={submitState === 'sending'}
                        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        <Send size={16} />
                        <span>{submitState === 'sending' ? 'Отправляем...' : 'Я закончил тестирование'}</span>
                    </button>
                </div>

                {submitMessage && (
                    <div
                        className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
                            submitState === 'error'
                                ? 'border-rose-400/30 bg-rose-500/10 text-rose-200'
                                : 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200'
                        }`}
                    >
                        {submitMessage}
                    </div>
                )}
            </div>
        </section>
    );
}
