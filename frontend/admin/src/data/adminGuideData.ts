import type { AdminViewId } from '@/components/Sidebar';
import type { AdminRouteState } from '@/hooks/useAdminRouter';
import type { Lang } from '@/i18n';

export interface LocalizedText {
    ru: string;
    en: string;
}

export function pickText(text: LocalizedText, lang: Lang): string {
    return lang === 'en' ? text.en : text.ru;
}

export type TourTrackId = 'full' | 'daily_ops' | 'teach_bot' | 'quality_settings';

export interface NoorTourStepSpec {
    id: string;
    /** Optional route to activate before spotlighting the element. */
    route?: Partial<AdminRouteState> & { view: AdminViewId };
    /** CSS selector to spotlight. Omit for a centered welcome/summary card. */
    selector?: string;
    side?: 'top' | 'right' | 'bottom' | 'left';
    align?: 'start' | 'center' | 'end';
    title: LocalizedText;
    description: LocalizedText;
}

export interface MiniTourCardMeta {
    id: Exclude<TourTrackId, 'full'>;
    duration: LocalizedText;
    role: LocalizedText;
    title: LocalizedText;
    summary: LocalizedText;
}

export const MINI_TOUR_CARDS: MiniTourCardMeta[] = [
    {
        id: 'daily_ops',
        duration: { ru: '4 шага · 45 сек', en: '4 steps · 45 sec' },
        role: { ru: 'Руководитель и РОП', en: 'Owner & Sales Lead' },
        title: {
            ru: 'Ежедневный обход: воронка, диалоги и эскалации',
            en: 'Daily check: funnel, chats & escalations',
        },
        summary: {
            ru: 'Показывает полосу срочных задач, переписки клиентов со статусом ведения, закрытие эскалаций и недельный отчёт.',
            en: 'Walks through the urgent attention bar, customer chats, closing resolved escalations and the 7-day report.',
        },
    },
    {
        id: 'teach_bot',
        duration: { ru: '4 шага · 45 сек', en: '4 steps · 45 sec' },
        role: { ru: 'Контент и обучение', en: 'Knowledge & Playbooks' },
        title: {
            ru: 'Как обучить Noor фактам и приёмам продаж',
            en: 'Teaching Noor facts & sales rules',
        },
        summary: {
            ru: 'Редактор базы знаний, очередь кандидатов из Telegram, конструктор правил поведения и проверка в песочнице.',
            en: 'Knowledge base editor, Telegram Auto-FAQ queue, behavior rules builder and live rule sandbox.',
        },
    },
    {
        id: 'quality_settings',
        duration: { ru: '4 шага · 45 сек', en: '4 steps · 45 sec' },
        role: { ru: 'Контроль качества и ИТ', en: 'QA & System Admin' },
        title: {
            ru: 'ИИ-контроль качества, Telegram и аудит системы',
            en: 'AI quality controls, Telegram & audit',
        },
        summary: {
            ru: 'Настройка трёх контуров оценки качества и бюджетов, проверка Telegram-уведомлений и журнал безопасности.',
            en: 'Configuring the 3 AI quality contours and USD budgets, testing Telegram alerts and inspecting the audit log.',
        },
    },
];

export const TOUR_TRACKS: Record<TourTrackId, NoorTourStepSpec[]> = {
    full: [
        {
            id: 'welcome',
            title: {
                ru: 'Добро пожаловать в кабинет управления Noor CRM',
                en: 'Welcome to the Noor CRM Control Panel',
            },
            description: {
                ru: 'За 2 минуты мы пройдём по всем ключевым экранам и покажем, как контролировать продажи в WhatsApp, обучать бота без программистов и оценивать работу менеджеров. Кабинет работает в безопасном режиме мониторинга: живые ответы клиентам идут через WhatsApp и Telegram, поэтому здесь нельзя случайно отправить лишнее сообщение.',
                en: 'In 2 minutes we will walk through every key workspace to show how you monitor WhatsApp sales, train the bot without developers and review manager performance. The panel runs in safe monitoring mode: live customer replies happen in WhatsApp and Telegram, so nothing here can accidentally message a buyer.',
            },
        },
        {
            id: 'sidebar',
            selector: '[data-admin-sidebar]',
            side: 'right',
            align: 'start',
            title: {
                ru: 'Левое меню: 9 разделов + Справка и Приёмка',
                en: 'Left sidebar: 9 sections + Guide & Self-Test',
            },
            description: {
                ru: '1) Операционная работа (Обзор, Клиенты и диалоги, Очереди и качество) — для ежедневного контроля. 2) Знания и каталог (База знаний, Правила бота, Каталог и остатки) — чем руководствуется Noor в ответах. 3) Система (Отчеты, Настройки, Аудит и статус), а в самом низу — Справка и стенд Приёмки. Жёлтые счётчики сразу показывают, где ждут задачи.',
                en: '1) Operations (Overview, Customers & Conversations, Queues & Quality) for daily oversight. 2) Knowledge & Catalog (Knowledge Base, Bot Rules, Catalog & Inventory) for what Noor knows and sells. 3) System (Reports, Settings, Audit & Health), plus Help & Guide and Self-Test at the bottom. Amber badges highlight items awaiting attention.',
            },
        },
        {
            id: 'header',
            selector: '[data-admin-header]',
            side: 'bottom',
            align: 'end',
            title: {
                ru: 'Верхняя панель: умный поиск, период, RU/EN и тема',
                en: 'Top bar: smart search, period, RU/EN & theme',
            },
            description: {
                ru: 'Слева — умный поиск: в списках он фильтрует текущий раздел, а на экранах без списка нажатие Enter сразу переносит в «Клиенты и диалоги» с этим запросом (Esc очищает). Справа — переключатель периода в «Обзоре» (по умолчанию «Месяц», далее запоминает ваш выбор), язык RU | EN, светлая/тёмная тема, обновление и повторный запуск тура.',
                en: 'On the left, smart search filters the active list — or press Enter on summary screens to jump straight to Customers & Conversations with that query (Esc clears). On the right: the Overview period switch (defaults to Month and remembers your last choice), RU | EN toggle, Light/Dark theme, refresh and tour launcher.',
            },
        },
        {
            id: 'overview',
            route: { view: 'overview' },
            selector: '[data-overview-attention-bar]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Обзор: с чего начинать рабочий день',
                en: 'Overview: your 3-minute morning check',
            },
            description: {
                ru: 'По умолчанию включён период «Месяц» (чтобы графики сразу показывали картину даже после тихих недель), а любое переключение на День / Неделю / Все автоматически запоминается в браузере. Полоса «Требует внимания» ведёт в 1 клик к открытым эскалациям, сделкам без оценки и статусу остатков Zoho.',
                en: 'Defaults to Month on first visit so charts carry full context right away, and remembers whichever period (Day / Week / Month / All) you pick next. The Needs Attention strip jumps in 1 click to open escalations, unreviewed deals and Zoho stock freshness.',
            },
        },
        {
            id: 'conversations',
            route: { view: 'conversations' },
            selector: '[data-conversations-layout="variant-4a"]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Клиенты и диалоги: чаты, расшифровка голоса и CRM',
                en: 'Customers & Conversations: chats, voice transcripts & CRM',
            },
            description: {
                ru: 'Слева — вкладки («Все», «Ожидают оператора», «На разбор» — закрытые эскалации на проверку) и кнопка расширенных фильтров по 4 параметрам. В ленте WhatsApp видна текстовая расшифровка голосовых сообщений клиентов и кнопка «Оценить диалог» (Bot QA). Справа в «CRM и детали» можно править и сохранять поля сделки, смотреть Zoho Contact/Deal ID, а в меню «⋯» — безопасно сбрасывать тестовый номер (RESET).',
                en: 'Left column offers quick tabs (All, Waiting for operator, Needs review for resolved handoffs) plus a 4-field filter panel. The WhatsApp timeline renders text transcripts of customer voice notes and a direct Evaluate chat (Bot QA) button. Open CRM & details to edit and save deal fields or inspect Zoho Contact/Deal IDs, and use "⋯" for safe test-chat reset (RESET).',
            },
        },
        {
            id: 'queues',
            route: { view: 'queuesQuality', tab: 'escalations' },
            selector: '[data-queues-tabs]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Очереди и качество: эскалации, РОП и разбор оценок',
                en: 'Queues & Quality: escalations, sales & score details',
            },
            description: {
                ru: 'Три вкладки: 1) «Эскалации» с фильтром Открытые / Закрытые / Все и переходом в чат; 2) «Сделки РОПа» — оценка работы менеджеров (0–20 баллов); 3) «Оценки ИИ и рубрика» — эталон из 15 критериев (30 баллов) и таблица проверок, где клик по любой строке открывает детальную карточку со скоростью ответа и суммой сделки в AED.',
                en: 'Three unified tabs: 1) Escalations with Open / Resolved / All filter and 1-click chat jump; 2) Sales Lead Deals for Manager QA (0–20 pts); 3) AI Scores & Rubric with the 15-criterion checklist (30 pts) and clickable review rows showing manager response time and AED deal value.',
            },
        },
        {
            id: 'knowledge',
            route: { view: 'knowledge' },
            selector: '[data-kb-master-detail]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'База знаний: предпросмотр безопасности и Auto-FAQ',
                en: 'Knowledge Base: safety preview & Telegram Auto-FAQ',
            },
            description: {
                ru: 'Хранит проверенные факты о доставке, сборке, оплате, 5% VAT, шоуруме и опте с метками источника («Шаблон Treejar», «Изменён вручную», «Auto-FAQ»). Перед публикацией кнопка «Предпросмотр» проверяет текст на смысловые дубликаты и рискованные обещания, а «Сохранить и проиндексировать» мгновенно включает статью в работу.',
                en: 'Stores verified facts on delivery, assembly, payment, 5% VAT, showroom and B2B terms with clear origin badges (Treejar template, Customized, Auto-FAQ). Click Preview before saving to check semantic duplicates and safety warnings, then Save and index to publish immediately.',
            },
        },
        {
            id: 'botRules',
            route: { view: 'botRules' },
            selector: '[data-bot-rules-master-detail]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Правила бота и песочница проверки',
                en: 'Bot Rules & live testing sandbox',
            },
            description: {
                ru: 'В отличие от Базы знаний (где лежат справочные факты), здесь задаётся поведение продавца: жёсткие ограничения, правила передачи менеджеру, сценарии консультации, допродажи и стиль. Перед включением откройте «Песочницу правил» вверху — введите фразу покупателя и проверьте, какие правила сработают.',
                en: 'While Knowledge Base holds factual answers, Bot Rules govern sales behavior: hard guardrails, escalation triggers, consultative playbooks, upsell prompts and tone. Open the Rules Sandbox at the top to test any customer phrase before activating a rule.',
            },
        },
        {
            id: 'catalog',
            route: { view: 'catalog' },
            selector: '[data-catalog-status-kpis]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Каталог и остатки: витрина сайта и склад Zoho',
                en: 'Catalog & Inventory: website items & Zoho stock',
            },
            description: {
                ru: 'Показывает число активных товаров, готовность поисковых индексов и возраст снимка остатков Zoho Inventory (обновляется автоматически каждые 5 минут). При обновлении цен или ассортимента на сайте можно вручную запустить синхронизацию с Treejar Catalog API или Zoho.',
                en: 'Displays active product counts, search index readiness and Zoho Inventory stock snapshot freshness (auto-refreshed every 5 minutes). Trigger a manual sync from Treejar Catalog API or Zoho whenever new furniture items or price updates go live.',
            },
        },
        {
            id: 'reports',
            route: { view: 'reports' },
            selector: '[data-reports-view]',
            side: 'top',
            align: 'start',
            title: {
                ru: 'Отчеты: еженедельный управленческий дайджест',
                en: 'Reports: 7-day executive operations digest',
            },
            description: {
                ru: 'Формирует стандартизированную операционную сводку за последние 7 дней (независимо от фильтра периода в «Обзоре»): конверсия воронки, самые запрашиваемые модели мебели, причины эскалаций, рейтинг менеджеров и точный предпросмотр отчёта для Telegram.',
                en: 'Generates a standardized 7-day operational summary on demand (independent of the Overview period switch): funnel conversion, top requested furniture SKUs, escalation reasons, manager leaderboard and a full Telegram digest preview.',
            },
        },
        {
            id: 'settings',
            route: { view: 'settings' },
            selector: '[data-settings-view]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Настройки: ИИ-контроль качества, бюджеты и Telegram',
                en: 'Settings: AI quality modes, USD caps & Telegram',
            },
            description: {
                ru: 'По умолчанию контуры Bot QA, Manager QA и «Красные флаги» выключены, чтобы не тратить бюджет без вашего решения. Здесь они включаются в 1 клик (Вручную, По расписанию или Ежедневная выборка), задаются лимиты в USD, расширенные параметры модели/транскрипта и проверяется тестовая доставка в Telegram.',
                en: 'Bot QA, Manager QA and Red Flags start disabled by default to protect spend. Enable Manual, Scheduled or Daily Sample mode in 1 click, set daily USD caps, tune advanced evaluator/transcript options and send a live test alert to Telegram.',
            },
        },
        {
            id: 'auditSystem',
            route: { view: 'auditSystem', tab: 'audit' },
            selector: '[data-audit-system-view]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Аудит и статус системы: прозрачность и здоровье',
                en: 'Audit & System Health: accountability & live status',
            },
            description: {
                ru: 'Вкладка «Журнал действий» хранит неизменяемую историю всех правок в кабинете с точным сравнением «было → стало» и переходом к объекту. Вкладка «Статус системы» в реальном времени проверяет PostgreSQL, кэш Redis, индексы каталога и свежесть снимка Zoho.',
                en: 'Action Log keeps an immutable history of every admin change with field-level before/after diffs and 1-click entity jump. System Health monitors live PostgreSQL, Redis, catalog embeddings and Zoho snapshot status.',
            },
        },
        {
            id: 'acceptance',
            route: { view: 'acceptance' },
            selector: '[data-acceptance-view]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Приёмка (Acceptance): пошаговая самопроверка сценариев',
                en: 'Self-Test (Acceptance): guided end-to-end verification',
            },
            description: {
                ru: 'Встроенный чек-лист для проверки живых сценариев WhatsApp + Telegram на тестовом номере: подбор каталога, точный SKU и остаток, черновик КП с кнопками менеджера в Telegram («Подтвердить заказ» / «Отклонить» / «Ответить клиенту») и команда /reset.',
                en: 'Interactive checklist for verifying end-to-end WhatsApp + Telegram scenarios on a test phone: catalog lookup, exact SKU stock, draft quotation approval buttons in Telegram (Approve / Reject / Reply to buyer) and /reset.',
            },
        },
        {
            id: 'guideFinish',
            route: { view: 'guide', tab: 'playbooks' },
            selector: '[data-guide-view]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Справка и инструкции — всегда под рукой!',
                en: 'Help & Guide — always one click away!',
            },
            description: {
                ru: 'Экскурсия завершена! В этом разделе внизу левого меню всегда доступны 9 пошаговых регламентов (включая работу менеджера в Telegram и самопроверку), карта всех экранов, словарь статусов и быстрые мини-туры по ролям.',
                en: 'Tour complete! This Help & Guide section in the bottom-left menu keeps 9 step-by-step playbooks (including Telegram manager actions and self-testing), a full section map, status glossary and role mini-tours ready anytime.',
            },
        },
    ],

    daily_ops: [
        {
            id: 'ops-attention',
            route: { view: 'overview' },
            selector: '[data-overview-attention-bar]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Шаг 1. Проверьте полосу «Требует внимания»',
                en: 'Step 1. Check the Needs Attention bar',
            },
            description: {
                ru: 'Каждое утро начинайте с «Обзора»: здесь видно число открытых эскалаций, сделок без оценки РОПа и актуальность остатков Zoho. Нажатие на любой индикатор сразу открывает нужный рабочий список.',
                en: 'Start each morning on Overview: check open escalations, deals awaiting manager review and Zoho stock freshness. Clicking any indicator jumps straight to that action queue.',
            },
        },
        {
            id: 'ops-waiting-chats',
            route: { view: 'conversations' },
            selector: '[data-conv-quick-tabs]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Шаг 2. Отфильтруйте чаты «Ожидают оператора»',
                en: 'Step 2. Filter chats Waiting for operator',
            },
            description: {
                ru: 'В разделе «Клиенты и диалоги» вкладка «Ожидают оператора» оставляет только тех покупателей, которых Noor передал живому менеджеру (на опт 20+ шт., мебель на заказ или спецзапрос). Откройте чат, проверьте карточку CRM справа и после ответа продавца нажмите «Закрыть эскалацию».',
                en: 'In Customers & Conversations, the Waiting for operator tab isolates buyers handed over to a human manager (bulk 20+ units, bespoke items or custom requests). Inspect the chat and CRM drawer, then click Close escalation once handled.',
            },
        },
        {
            id: 'ops-manager-qa',
            route: { view: 'queuesQuality', tab: 'manager_deals' },
            selector: '[data-queues-tabs]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Шаг 3. Оцените отработку сделок менеджерами',
                en: 'Step 3. Score manager follow-up quality',
            },
            description: {
                ru: 'Во вкладке «Сделки РОПа» собираются завершённые эскалации. Нажмите «Оценить», чтобы ИИ-аудитор проверил скорость реакции, использование контекста бота и точность коммерческих условий по 20-балльной шкале.',
                en: 'The Sales Lead Deals tab lists resolved handoffs. Click Evaluate so the AI auditor scores response speed, handover context usage and commercial accuracy on a 20-point scale.',
            },
        },
        {
            id: 'ops-reports',
            route: { view: 'reports' },
            selector: '[data-reports-view]',
            side: 'top',
            align: 'start',
            title: {
                ru: 'Шаг 4. Сформируйте управленческую сводку за 7 дней',
                en: 'Step 4. Generate the 7-day operations digest',
            },
            description: {
                ru: 'Раздел «Отчеты» в один клик собирает конверсию, топ запрашиваемых моделей мебели, причины передач и рейтинг менеджеров — в том же формате, который приходит руководителю в Telegram.',
                en: 'Reports builds a 1-click weekly summary of conversion, top requested furniture SKUs, escalation reasons and manager scores — identical to the Telegram executive digest.',
            },
        },
    ],

    teach_bot: [
        {
            id: 'teach-kb-editor',
            route: { view: 'knowledge' },
            selector: '[data-kb-master-detail]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Шаг 1. Добавьте или обновите статью в Базе знаний',
                en: 'Step 1. Add or edit a Knowledge Base article',
            },
            description: {
                ru: 'Выберите категорию (Доставка и сборка, Оплата и VAT 5%, Шоурум, B2B и опт), напишите проверенный факт и нажмите «Сохранить и проиндексировать». Поисковый вектор создаётся автоматически — Noor сразу начнёт опираться на этот текст.',
                en: 'Pick a category (Delivery & assembly, Payment & 5% VAT, Showroom, B2B & bulk), write the verified policy and click Save and index. Embeddings update automatically so Noor uses the new fact right away.',
            },
        },
        {
            id: 'teach-autofaq',
            route: { view: 'knowledge' },
            selector: '[data-open-autofaq-drawer]',
            side: 'bottom',
            align: 'end',
            title: {
                ru: 'Шаг 2. Одобрите кандидатов Auto-FAQ из Telegram',
                en: 'Step 2. Approve Telegram Auto-FAQ candidates',
            },
            description: {
                ru: 'Когда менеджер отвечает клиенту через кнопку «📚 FAQ + клиент» в Telegram, система очищает ответ от разовых обещаний и кладёт его сюда. Нажмите «Кандидаты Auto-FAQ», проверьте формулировку и опубликуйте её одной кнопкой «Одобрить».',
                en: 'When a manager answers via "FAQ + customer" in Telegram, the safety filter strips one-off promises and queues reusable answers here. Click Auto-FAQ Candidates to review and approve in one click.',
            },
        },
        {
            id: 'teach-rules',
            route: { view: 'botRules' },
            selector: '[data-bot-rules-master-detail]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Шаг 3. Настройте приём продаж в «Правилах бота»',
                en: 'Step 3. Configure sales behavior in Bot Rules',
            },
            description: {
                ru: 'Нужно изменить поведение продавца (например, предлагать тумбы к рабочим станциям или сразу передавать опт от 20 единиц)? Создайте правило: «Жесткое» и «Эскалация» действуют в каждом ходе, а «Сценарий», «Допродажа» и «Стиль» подключаются по смыслу вопроса.',
                en: 'Need to adjust sales behavior (such as suggesting pedestals with workstations or escalating 20+ unit inquiries)? Create a rule: Hard and Escalation rules apply on every turn, while Playbook, Upsell and Style rules match by context.',
            },
        },
        {
            id: 'teach-sandbox',
            route: { view: 'botRules' },
            selector: '[data-open-rules-sandbox]',
            side: 'bottom',
            align: 'end',
            title: {
                ru: 'Шаг 4. Проверьте правило в Песочнице до запуска',
                en: 'Step 4. Verify in the Rules Sandbox first',
            },
            description: {
                ru: 'Нажмите «Песочница правил», введите реальный вопрос покупателя на английском или арабском языке и посмотрите точный список правил, которые попадут в инструкцию бота.',
                en: 'Click Rules Sandbox, type a sample customer message in English or Arabic and inspect the exact list of active rules that will be injected into Noor for that turn.',
            },
        },
    ],

    quality_settings: [
        {
            id: 'qa-cards',
            route: { view: 'settings' },
            selector: '[data-aiqc-simple-cards]',
            side: 'top',
            align: 'center',
            title: {
                ru: 'Шаг 1. Включите контуры ИИ-контроля качества и бюджет',
                en: 'Step 1. Enable AI Quality contours & USD budget',
            },
            description: {
                ru: 'Три карточки управляют проверкой диалогов бота (Bot QA), оценкой менеджеров (Manager QA) и поиском критичных ошибок (Красные флаги). Выберите режим «Вручную» или «Авто по расписанию» и задайте дневной лимит расходов в долларах.',
                en: 'Three cards control Bot QA, Manager QA and Red Flags scanning. Choose Manual or Scheduled mode for each contour and set a clear daily spend cap in USD.',
            },
        },
        {
            id: 'qa-telegram',
            route: { view: 'settings' },
            selector: '[data-send-telegram-test]',
            side: 'top',
            align: 'start',
            title: {
                ru: 'Шаг 2. Проверьте доставку уведомлений в Telegram',
                en: 'Step 2. Test Telegram alert delivery',
            },
            description: {
                ru: 'Кнопка «Отправить тестовое сообщение» проверяет связь сервера с рабочим чатом Telegram, куда приходят уведомления об эскалациях, новых КП и еженедельные отчёты.',
                en: 'Click Send test message to verify live connectivity to the Telegram operator chat used for escalation alerts, quotation notifications and weekly digests.',
            },
        },
        {
            id: 'qa-rubric',
            route: { view: 'queuesQuality', tab: 'ai_rubric' },
            selector: '[data-queues-tabs]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Шаг 3. Изучите оценки и эталонную рубрику 30 баллов',
                en: 'Step 3. Review scores & the 30-point rubric',
            },
            description: {
                ru: 'Во вкладке «Оценки ИИ и рубрика» хранятся последние разборы диалогов и кнопка «Эталонная рубрика (15 критериев)» — прозрачный стандарт того, как Noor обязан приветствовать, проверять склад Zoho, считать 5% VAT и оформлять КП.',
                en: 'The AI Scores & Rubric tab shows recent evaluations alongside the Reference Rubric (15 criteria) — the exact standard for greeting, Zoho stock checks, 5% VAT math and PDF quotations.',
            },
        },
        {
            id: 'qa-audit-health',
            route: { view: 'auditSystem', tab: 'system' },
            selector: '[data-audit-system-tabs]',
            side: 'bottom',
            align: 'start',
            title: {
                ru: 'Шаг 4. Статус системы и неизменяемый журнал аудита',
                en: 'Step 4. System health & immutable audit trail',
            },
            description: {
                ru: 'Вкладка «Статус системы» показывает живое состояние базы данных, кэша Redis, каталога и снимка Zoho, а вкладка «Журнал действий» фиксирует каждое изменение настроек, правил и статусов с точным сравнением «было → стало».',
                en: 'System Health reports live PostgreSQL, Redis, catalog and Zoho snapshot status, while Action Log records every admin change with a transparent before/after diff.',
            },
        },
    ],
};

export interface GuidePlaybookItem {
    id: string;
    role: LocalizedText;
    duration: LocalizedText;
    title: LocalizedText;
    goal: LocalizedText;
    steps: LocalizedText[];
    tip: LocalizedText;
    route: Partial<AdminRouteState> & { view: AdminViewId };
    tourTrack?: TourTrackId;
}

export const GUIDE_PLAYBOOKS: GuidePlaybookItem[] = [
    {
        id: 'login-and-modes',
        role: { ru: 'Все сотрудники', en: 'All team members' },
        duration: { ru: '1 мин', en: '1 min' },
        title: {
            ru: '1. Вход в кабинет через Telegram и настройка языка / темы',
            en: '1. Signing in via Telegram and setting language & theme',
        },
        goal: {
            ru: 'Быстро войти в систему без пересылки паролей и настроить удобный вид экрана.',
            en: 'Sign in securely without sharing static passwords and personalize your workspace.',
        },
        steps: [
            {
                ru: 'Откройте страницу входа /admin/login и нажмите «Войти через Telegram» (или отправьте команду /admin боту @Treejar_Trading_bot в личном чате). Бот выдаст одноразовую ссылку и сразу откроет /dashboard/.',
                en: 'Open /admin/login and click Sign in via Telegram (or send /admin to @Treejar_Trading_bot in a direct message). The bot issues a one-time link that lands straight in /dashboard/.',
            },
            {
                ru: 'Если Telegram под рукой недоступен, используйте блок «Технический fallback» на странице входа с логином и паролем администратора.',
                en: 'If Telegram is unavailable on your workstation, use the password fallback form on the login screen with admin credentials.',
            },
            {
                ru: 'В правом верхнем углу выберите язык интерфейса (RU | EN) и тему оформления (луна/солнце — светлая или тёмная). Выбор сохраняется в вашем браузере автоматически.',
                en: 'In the top-right header, pick your interface language (RU | EN) and theme (Light or Dark). Your preference is saved in the browser automatically.',
            },
            {
                ru: 'Используйте поиск в верхней шапке: в разделах со списком он фильтрует записи на месте, а на сводных экранах («Обзор», «Каталог», «Отчеты», «Настройки») нажатие Enter сразу переносит в «Клиенты и диалоги» с этим запросом (Esc очищает строку).',
                en: 'Use the top header search: on list screens it filters records in place, while pressing Enter on summary screens (Overview, Catalog, Reports, Settings) jumps straight to Customers & Conversations with that query (Esc clears).',
            },
        ],
        tip: {
            ru: 'Одна сессия входа действует сразу для обоих интерфейсов (/dashboard/ и /admin/), а отметка о прохождении тура хранится индивидуально в браузере каждого сотрудника.',
            en: 'One login session authenticates both /dashboard/ and /admin/, while onboarding tour progress is saved per browser so every team member gets the tour on their own device.',
        },
        route: { view: 'overview' },
        tourTrack: 'full',
    },
    {
        id: 'morning-executive-check',
        role: { ru: 'Руководитель / РОП', en: 'Owner / Head of Sales' },
        duration: { ru: '3 мин', en: '3 min' },
        title: {
            ru: '2. Утренний контроль продаж и узких мест за 3 минуты',
            en: '2. 3-minute morning sales & bottleneck review',
        },
        goal: {
            ru: 'Увидеть динамику обращений, конверсию в сделки, причины передач людям и зависшие эскалации.',
            en: 'Spot conversation volume trends, deal conversion, escalation drivers and pending human handoffs.',
        },
        steps: [
            {
                ru: 'Откройте «Обзор»: при первом входе по умолчанию выбран период «Месяц» (чтобы графики всегда были информативны), а любое переключение на «День», «Неделю» или «Все» автоматически запоминается в вашем браузере.',
                en: 'Open Overview: first visit defaults to Month so charts immediately carry context, and switching to Day, Week or All is remembered automatically in your browser.',
            },
            {
                ru: 'Проверьте верхнюю полосу «Требует внимания»: если счётчик «Открытые эскалации» или «Сделки на оценку РОПа» больше нуля — кликните по плашке для прямого перехода к списку.',
                en: 'Inspect the Needs Attention strip: if Open escalations or Deals awaiting review is above zero, click the pill to jump directly to that queue.',
            },
            {
                ru: 'Посмотрите блоки «Воронка и эффективность» и «Причины эскалаций»: они показывают средний чек в AED, долю целевых лидов и то, почему бот передавал диалоги (опт, кастом, запрос звонка).',
                en: 'Review Funnel & Efficiency and Escalation Reasons to see average deal value in AED, target lead share and why chats were routed to humans.',
            },
        ],
        tip: {
            ru: 'Клик по сегменту графика или карточке языка в «Обзоре» открывает отфильтрованные диалоги, а раздел «Отчеты» всегда строит отдельную фиксированную сводку за 7 дней (аналог еженедельного Telegram-дайджеста).',
            en: 'Clicking chart segments in Overview drills into matching chats, while Reports always builds a dedicated 7-day digest matching the weekly Telegram executive summary.',
        },
        route: { view: 'overview' },
        tourTrack: 'daily_ops',
    },
    {
        id: 'inspect-chat-and-escalation',
        role: { ru: 'РОП / Оператор', en: 'Sales Lead / Operator' },
        duration: { ru: '2 мин', en: '2 min' },
        title: {
            ru: '3. Разбор переписки, расшифровка голоса, правка CRM и закрытие эскалации',
            en: '3. Reviewing chats, voice transcripts, CRM fields & closing escalations',
        },
        goal: {
            ru: 'Проверить ответы Noor (включая расшифровку голосовых), обновить поля сделки CRM и вернуть диалог в штатный статус после работы менеджера.',
            en: 'Verify Noor replies (including voice note transcripts), update CRM deal fields and close open escalations once resolved.',
        },
        steps: [
            {
                ru: 'Перейдите в «Клиенты и диалоги». Используйте поиск (телефон, имя, номер КП или заказа SO), быстрые вкладки («Все», «Ожидают оператора», «На разбор» — закрытые эскалации для проверки) или кнопку расширенных фильтров по 4 полям (статус, этап, язык EN/AR, эскалация).',
                en: 'Open Customers & Conversations. Search by phone/name/quote/SO, use quick tabs (All, Waiting for operator, Needs review for resolved handoffs) or open the 4-field advanced filter panel (status, stage, language, escalation).',
            },
            {
                ru: 'Изучите ленту WhatsApp и статус в шапке («Ведёт Noor», «Ожидает оператора», «Диалог закрыт»). Если покупатель присылал голосовые сообщения, их текстовая расшифровка отображается прямо внутри пузыря сообщения; кнопкой «Оценить диалог» можно сразу запустить Bot QA.',
                en: 'Inspect the WhatsApp timeline and header badge. Customer voice notes include inline text transcripts right inside the message bubble, and Evaluate chat triggers an immediate Bot QA check.',
            },
            {
                ru: 'Нажмите «CRM и детали» справа вверху чата — здесь видны Zoho Contact ID / Zoho Deal ID, применённые правила и оценка Bot QA, а также можно вручную отредактировать и нажать «Сохранить карточку» (имя клиента, статус чата, этап воронки, статус эскалации и статус сделки pending / won / delivered).',
                en: 'Click CRM & details in the top-right to view Zoho Contact/Deal IDs, applied rules and Bot QA score, or edit and save customer name, chat status, sales stage, escalation state and deal status (pending / won / delivered).',
            },
            {
                ru: 'Когда живой менеджер завершил консультацию в WhatsApp/Zoho, нажмите «Закрыть эскалацию» в шапке диалога (или в разделе «Очереди и качество»).',
                en: 'Once the human manager finishes assisting the customer in WhatsApp/Zoho, click Close escalation in the chat header (or inside Queues & Quality).',
            },
        ],
        tip: {
            ru: 'Для очистки собственного тестового номера после проверки откройте меню «⋯» в шапке чата → «Сбросить данные клиента»: система сначала покажет точный предпросмотр удаляемых записей и попросит ввести слово RESET.',
            en: 'To wipe your own test phone number after QA checks, open the "⋯" menu → Reset customer data: the panel previews affected records first and requires typing RESET.',
        },
        route: { view: 'conversations' },
    },
    {
        id: 'update-knowledge-base',
        role: { ru: 'Контент / Руководитель', en: 'Content / Owner' },
        duration: { ru: '2 мин', en: '2 min' },
        title: {
            ru: '4. Добавление фактов в Базу знаний и проверка через «Предпросмотр»',
            en: '4. Updating Knowledge Base facts & running Safety Preview',
        },
        goal: {
            ru: 'Оперативно обновить условия доставки, сборки, гарантии или оплаты без дубликатов и опасных формулировок.',
            en: 'Update delivery, assembly, warranty or payment policies cleanly without semantic duplicates or unsafe promises.',
        },
        steps: [
            {
                ru: 'Откройте «База знаний». Слева выберите существующую статью (обратите внимание на метки «Шаблон Treejar», «Изменён вручную», «Auto-FAQ») или нажмите «+ Новая».',
                en: 'Open Knowledge Base. Select an existing article on the left (note origin badges: Treejar template, Customized, Auto-FAQ) or click + New.',
            },
            {
                ru: 'Укажите заголовок, категорию («Доставка и сборка», «Оплата и VAT 5%», «Шоурум», «B2B и опт»), язык (EN или AR) и нажмите «Предпросмотр» — система до сохранения проверит готовность индекса, близость к существующим статьям (дубликаты) и стоп-факторы безопасности.',
                en: 'Fill in title, category, language (EN or AR) and click Preview first — the system checks embedding readiness, semantic duplicate similarity and safety warnings before anything goes live.',
            },
            {
                ru: 'Нажмите «Сохранить и проиндексировать» (или «Скрыть / удалить» для неактуальной записи). Со следующего сообщения покупателя Noor использует обновлённый факт.',
                en: 'Click Save and index (or Hide / delete to retire an outdated entry). Noor applies the updated fact starting from the very next customer message.',
            },
        ],
        tip: {
            ru: 'Кнопка «Восстановить шаблоны БЗ» вверху открывает окно сравнения: «Безопасный режим» добавляет только недостающие базовые статьи Treejar, не затирая ваши ручные правки.',
            en: 'Restore KB templates opens a diff preview first: Safe Mode adds missing canonical Treejar articles while preserving all your custom edits.',
        },
        route: { view: 'knowledge' },
        tourTrack: 'teach_bot',
    },
    {
        id: 'approve-telegram-autofaq',
        role: { ru: 'РОП / Контент', en: 'Sales Lead / Content' },
        duration: { ru: '1 мин', en: '1 min' },
        title: {
            ru: '5. Одобрение новых ответов из Telegram (Кандидаты Auto-FAQ)',
            en: '5. Approving manager answers from Telegram (Auto-FAQ)',
        },
        goal: {
            ru: 'Превращать удачные ответы живых менеджеров в постоянные знания бота с проверкой в один клик.',
            en: 'Turn helpful manager replies from Telegram into permanent bot knowledge with 1-click review.',
        },
        steps: [
            {
                ru: 'Когда бот встречает незнакомый вопрос и зовёт менеджера в Telegram, менеджер нажимает «📚 FAQ + клиент» и отвечает покупателю.',
                en: 'When Noor escalates an unfamiliar question to Telegram, the manager replies using the "FAQ + customer" button.',
            },
            {
                ru: 'Защитный фильтр автоматически отсекает разовые обещания (индивидуальные скидки, личные договорённости на конкретную дату), а общие полезные ответы ставит в очередь кандидатов.',
                en: 'The safety guard automatically blocks one-time promises (custom discounts or specific delivery dates) and places reusable answers into the candidate queue.',
            },
            {
                ru: 'Откройте «База знаний» → нажмите кнопку «Кандидаты Auto-FAQ» справа вверху. Проверьте текст и нажмите «Одобрить» (статья сразу попадёт в активный поиск) или «Отклонить».',
                en: 'Go to Knowledge Base → click Auto-FAQ Candidates in the top-right. Review the wording and click Approve (publishes and indexes immediately) or Reject.',
            },
        ],
        tip: {
            ru: 'Счётчик ожидающих кандидатов всегда виден на жёлтом бейдже напротив пункта «База знаний» в левом меню.',
            en: 'Pending Auto-FAQ candidates are always visible as an amber count badge next to Knowledge Base in the sidebar.',
        },
        route: { view: 'knowledge' },
    },
    {
        id: 'create-and-test-bot-rule',
        role: { ru: 'Руководитель / РОП', en: 'Owner / Sales Lead' },
        duration: { ru: '3 мин', en: '3 min' },
        title: {
            ru: '6. Создание правила поведения бота и проверка в Песочнице',
            en: '6. Creating a Bot Behavior Rule & testing in the Sandbox',
        },
        goal: {
            ru: 'Научить Noor новому приёму консультации, кросс-продаже или правилу эскалации и убедиться, что оно срабатывает корректно.',
            en: 'Add a consultative sales rule, cross-sell suggestion or escalation trigger and verify how it matches.',
        },
        steps: [
            {
                ru: 'Откройте «Правила бота» и нажмите «+ Новое правило». Выберите тип: «Жесткое» или «Эскалация» (действуют всегда), либо «Сценарий», «Допродажа», «Стиль» (подбираются по смыслу сообщения).',
                en: 'Open Bot Rules and click + New rule. Choose Hard or Escalation (always active), or Playbook, Upsell or Style (matched semantically per turn).',
            },
            {
                ru: 'Задайте статус («Черновик» пока редактируете, «Активен» для включения в работу), область действия (глобально или только для конкретного этапа/языка), инструкцию и 2–3 примера фраз клиента.',
                en: 'Set status (Draft while editing, Active to go live), scope (Global or restricted to a stage/language), clear instruction text and 2–3 trigger examples.',
            },
            {
                ru: 'Нажмите «Сохранить и проиндексировать», затем откройте «Песочницу правил» в правом верхнем углу экрана, введите тестовую реплику покупателя и нажмите «Проверить».',
                en: 'Click Save and index, then open Rules Sandbox in the top-right, enter a realistic buyer message and click Test to inspect matched rules.',
            },
        ],
        tip: {
            ru: 'В каждый ответ Noor помещается до 12 активных жёстких/эскалационных правил (по приоритету) и до 6 наиболее близких по смыслу мягких правил.',
            en: 'Each customer turn receives up to 12 active hard/escalation rules (ordered by priority) plus up to 6 semantically matched soft rules.',
        },
        route: { view: 'botRules' },
        tourTrack: 'teach_bot',
    },
    {
        id: 'configure-ai-quality-and-audit',
        role: { ru: 'Руководитель / Админ', en: 'Owner / Admin' },
        duration: { ru: '2 мин', en: '2 min' },
        title: {
            ru: '7. Настройка ИИ-контроля качества (Bot QA / Manager QA) и проверка системы',
            en: '7. Configuring AI Quality Controls & checking system health',
        },
        goal: {
            ru: 'Включить ручную или автоматическую оценку диалогов с понятным дневным бюджетом и разобрать детальные карточки оценок.',
            en: 'Enable manual, scheduled or daily-sample quality reviews within a USD budget and inspect detailed evaluation drawers.',
        },
        steps: [
            {
                ru: 'Перейдите в «Настройки». Если контуры выключены, нажмите «Включить ручной режим для всех» — это сразу разблокирует кнопки «Оценить» в чатах и «Сделках РОПа».',
                en: 'Open Settings. If quality contours are disabled, click Enable manual mode for all to unlock Evaluate buttons across chats and manager deals.',
            },
            {
                ru: 'Выберите подходящий режим («Вручную», «Авто по расписанию» или «Ежедневная выборка»), задайте дневной бюджет в USD, а в блоке «Расширенные настройки инженера» при необходимости уточните модель оценки, объём транскрипта (выкл / сводка / полный), лимиты вызовов и чекбоксы критериев.',
                en: 'Select Manual, Scheduled or Daily sample mode, set a daily USD cap, and optionally tune evaluator model, transcript mode (disabled / summary / full), call limits and rubric criteria inside Advanced engineer settings.',
            },
            {
                ru: 'Во вкладке «Очереди и качество → Оценки ИИ и рубрика» кликните по любой строке таблицы, чтобы открыть подробный разбор со временем реакции менеджера и суммой сделки в AED; в разделе «Аудит и статус системы» проверьте БД, Redis, Zoho и журнал изменений «было → стало».',
                en: 'In Queues & Quality → AI Scores & Rubric, click any review row to inspect first-response speed and AED deal value; in Audit & System Health, verify DB, Redis, Zoho and before/after config diffs.',
            },
        ],
        tip: {
            ru: 'Если лимит дневного бюджета достигнут, проверки качества аккуратно пропускаются до следующего дня без влияния на ответы Noor покупателям в WhatsApp.',
            en: 'If a daily quality budget cap is reached, QA evaluations pause cleanly until the next day without affecting live WhatsApp customer replies.',
        },
        route: { view: 'settings' },
        tourTrack: 'quality_settings',
    },
    {
        id: 'telegram-manager-workflow',
        role: { ru: 'Менеджеры / РОП', en: 'Sales Managers / Lead' },
        duration: { ru: '2 мин', en: '2 min' },
        title: {
            ru: '8. Работа менеджера в Telegram: подтверждение КП, ответы клиенту и команды',
            en: '8. Manager workflow in Telegram: approving quotes, replying & commands',
        },
        goal: {
            ru: 'Понимать, какие кнопки приходят в рабочий Telegram при оформлении КП и эскалациях и как они отражаются в кабинете.',
            en: 'Use Telegram operator buttons for draft quotations and escalations and see how actions sync back to the dashboard.',
        },
        steps: [
            {
                ru: 'Когда клиент запрашивает точное КП (Quotation / Proforma), Noor не отправляет PDF вслепую, а создаёт черновик в Zoho и присылает карточку проверки в Telegram с кнопками «Подтвердить заказ» (отправляет PDF покупателю в WhatsApp), «Отклонить» (блокирует отправку) и «Ответить клиенту».',
                en: 'When a buyer requests a formal Quotation / Proforma, Noor creates a Zoho draft and posts a review card in Telegram with Approve order (sends the PDF on WhatsApp), Reject (blocks sending) and Reply to customer buttons.',
            },
            {
                ru: 'При передаче сложного вопроса менеджеру в Telegram доступны две кнопки ответа: «Ответить клиенту» (разовый ответ конкретному покупателю) и «📚 FAQ + клиент» (отправляет ответ покупателю и одновременно ставит очищенный вариант в очередь «Кандидаты Auto-FAQ» в Базе знаний).',
                en: 'On escalated questions Telegram offers two reply actions: Reply to customer (one-off answer to that buyer) and "FAQ + customer" (replies to the buyer and queues a sanitized draft under Auto-FAQ Candidates in Knowledge Base).',
            },
            {
                ru: 'В личном чате с ботом @Treejar_Trading_bot команда /admin выдаёт одноразовую ссылку входа в /dashboard/, а команда /reset сбрасывает контекст выделенного тестового диалога при проверках.',
                en: 'In a direct chat with @Treejar_Trading_bot, /admin issues a one-time login link to /dashboard/, while /reset clears the dedicated test conversation state during QA runs.',
            },
        ],
        tip: {
            ru: 'Каждое подтверждение/отклонение КП и каждый ответ менеджера фиксируются в истории чата «Клиенты и диалоги» и в «Журнале действий» аудита.',
            en: 'Every quote approval/rejection and manager reply is recorded in the Customers & Conversations timeline and the Audit Action Log.',
        },
        route: { view: 'queuesQuality', tab: 'escalations' },
    },
    {
        id: 'run-acceptance-self-test',
        role: { ru: 'Руководитель / Тестировщик', en: 'Owner / QA Reviewer' },
        duration: { ru: '5 мин', en: '5 min' },
        title: {
            ru: '9. Пошаговая приёмка и самопроверка сценариев (раздел «Приёмка» и /test)',
            en: '9. Guided end-to-end scenario verification (Self-Test & /test)',
        },
        goal: {
            ru: 'Проверить работу цепочки WhatsApp → Noor → Zoho → Telegram по готовым контрольным сценариям и сохранить отчёт тестера.',
            en: 'Walk through structured WhatsApp → Noor → Zoho → Telegram test cases and submit structured acceptance notes.',
        },
        steps: [
            {
                ru: 'Откройте пункт «Приёмка» в самом низу левого меню (или прямую страницу /test). В каждой карточке уже заготовлена точная фраза покупателя, ожидаемый ответ бота и ожидаемое поведение в Telegram.',
                en: 'Open Self-Test (Acceptance) at the bottom of the left sidebar (or visit /test directly). Each scenario card provides the exact buyer prompt, expected Noor reply and expected Telegram behavior.',
            },
            {
                ru: 'Пройдите сценарии по порядку: подбор мебели из каталога, проверка точного артикула и остатка Zoho, неполный запрос счёта без ложной эскалации, выпуск чернового КП с подтверждением/отклонением в Telegram, ответ менеджера и сброс /reset.',
                en: 'Run the scenarios in order: catalog discovery, exact SKU price & Zoho stock, incomplete proforma without premature escalation, draft quotation approve/reject in Telegram, manager reply and /reset.',
            },
            {
                ru: 'Отметьте статус каждого шага (пройдено / ошибка / пропущено), добавьте комментарий и нажмите кнопку отправки результатов — прогресс черновика также сохраняется локально в браузере.',
                en: 'Mark each scenario status (pass / fail / skip), add notes and submit the report — draft progress is also auto-saved locally in your browser.',
            },
        ],
        tip: {
            ru: 'Перед повторным прогоном сценария с того же тестового телефона используйте команду /reset в Telegram или безопасный сброс (RESET) через меню «⋯» в шапке диалога.',
            en: 'Before re-running a scenario from the same test phone, run /reset in Telegram or use Reset customer data (RESET) from the "⋯" menu in the chat header.',
        },
        route: { view: 'acceptance' },
    },
];

export interface GuideSectionCard {
    id: string;
    group: LocalizedText;
    title: LocalizedText;
    purpose: LocalizedText;
    keyActions: LocalizedText;
    botImpact: LocalizedText;
    route?: Partial<AdminRouteState> & { view: AdminViewId };
    externalHref?: string;
}

export const GUIDE_SECTIONS: GuideSectionCard[] = [
    {
        id: 'sec-overview',
        group: { ru: 'Блок 1 · Операционная работа', en: 'Group 1 · Operations' },
        title: { ru: 'Обзор', en: 'Overview' },
        purpose: {
            ru: 'Управленческий экран руководителя: полоса срочных задач, 4 карточки KPI с динамикой, графики диалогов, классификация по языкам (EN/AR) и целевым лидам, воронка продаж и причины эскалаций.',
            en: 'Executive dashboard: urgent attention strip, 4 KPI cards with period deltas, conversation volume trends, language & target split, sales funnel and escalation reasons.',
        },
        keyActions: {
            ru: 'Период по умолчанию — «Месяц» с автоматическим запоминанием последнего выбора (День / Неделя / Месяц / Все), переход к эскалациям и сделкам, фильтрация чатов кликом по графику.',
            en: 'Defaults to Month and remembers your last selected period (Day / Week / Month / All), 1-click jump to escalations/reviews, and chart-click chat filtering.',
        },
        botImpact: {
            ru: 'Только чтение и аналитика — никакие клики здесь не меняют поведение бота.',
            en: 'Read-only analytics — viewing or filtering metrics never alters live bot behavior.',
        },
        route: { view: 'overview' },
    },
    {
        id: 'sec-conversations',
        group: { ru: 'Блок 1 · Операционная работа', en: 'Group 1 · Operations' },
        title: { ru: 'Клиенты и диалоги', en: 'Customers & Conversations' },
        purpose: {
            ru: 'Двухколоночное рабочее место для чтения переписок WhatsApp (включая расшифровку голосовых сообщений), расширенной фильтрации и работы с выезжающей карточкой CRM.',
            en: 'Two-column workspace for inspecting full WhatsApp histories (including voice message transcripts), multi-field filtering and editing the slide-over CRM drawer.',
        },
        keyActions: {
            ru: 'Поиск по телефону/имени/SO, вкладки «Ожидают оператора» и «На разбор», 4 расширенных фильтра, редактирование и сохранение полей сделки + Zoho Contact/Deal ID, запуск Bot QA, закрытие эскалации и сброс теста (RESET).',
            en: 'Search by phone/name/SO, Waiting for operator & Needs review tabs, 4-field filter panel, edit & save CRM deal fields + Zoho IDs, run Bot QA, close escalations and reset test chats (RESET).',
        },
        botImpact: {
            ru: 'Закрытие эскалации или смена статуса возвращают диалог в штатный режим; сброс удаляет тестовую историю выбранного номера.',
            en: 'Closing an escalation updates handoff state; resetting a test customer clears that phone number’s conversation history.',
        },
        route: { view: 'conversations' },
    },
    {
        id: 'sec-queues-quality',
        group: { ru: 'Блок 1 · Операционная работа', en: 'Group 1 · Operations' },
        title: { ru: 'Очереди и качество', en: 'Queues & Quality' },
        purpose: {
            ru: 'Единый центр оперативного контроля из 3 вкладок: «Эскалации» (фильтр Открытые / Закрытые / Все), «Сделки РОПа» (оценка менеджеров) и «Оценки ИИ и рубрика».',
            en: 'Unified 3-tab control center: Escalations (Open / Resolved / All filter), Sales Lead Deals (pending Manager QA) and AI Scores & 15-point Rubric.',
        },
        keyActions: {
            ru: 'Переход из эскалации в чат, закрытие заявок, оценка менеджера (0–20), эталонная рубрика бота (0–30) и клик по строке оценки для просмотра скорости ответа и суммы сделки в AED.',
            en: 'Jump from an escalation to the chat, resolve items, run 20-pt Manager QA, view the 30-pt Bot QA rubric and click any review row for response time & AED deal details.',
        },
        botImpact: {
            ru: 'Помогает находить слабые места в консультациях и переводить типовые вопросы в Базу знаний или Правила бота.',
            en: 'Surfaces coaching insights and recurring customer questions to promote into Knowledge Base entries or Bot Rules.',
        },
        route: { view: 'queuesQuality', tab: 'escalations' },
    },
    {
        id: 'sec-knowledge',
        group: { ru: 'Блок 2 · Знания и каталог', en: 'Group 2 · Knowledge & Catalog' },
        title: { ru: 'База знаний', en: 'Knowledge Base' },
        purpose: {
            ru: 'Хранилище выверенных фактов компании Treejar: условия доставки и сборки по ОАЭ, правила 5% VAT и оформления КП, шоурум, гарантия и работа с оптом.',
            en: 'Repository of verified Treejar company facts: UAE delivery & installation, 5% VAT & quotation policy, showroom details, warranty and B2B terms.',
        },
        keyActions: {
            ru: 'Создание/правка статей, «Предпросмотр» дубликатов и безопасности до сохранения, метки источника, скрытие устаревших статей, одобрение Auto-FAQ из Telegram и восстановление шаблонов.',
            en: 'Create/edit articles, run duplicate & safety Preview before saving, inspect origin badges, hide outdated items, approve Telegram Auto-FAQ and restore canonical templates.',
        },
        botImpact: {
            ru: 'Прямое и мгновенное: на каждом сообщении клиента Noor ищет по смыслу активные статьи с индексом и отвечает строго по ним.',
            en: 'Direct and immediate: on every customer message Noor retrieves semantically matching indexed articles as factual grounding.',
        },
        route: { view: 'knowledge' },
    },
    {
        id: 'sec-bot-rules',
        group: { ru: 'Блок 2 · Знания и каталог', en: 'Group 2 · Knowledge & Catalog' },
        title: { ru: 'Правила бота', en: 'Bot Rules' },
        purpose: {
            ru: 'Конструктор продающего поведения и ограничений Noor без изменения программного кода.',
            en: 'No-code builder for Noor’s sales playbooks, guardrails, cross-sells and escalation rules.',
        },
        keyActions: {
            ru: 'Настройка типа, приоритета и условий применения правила, архивация устаревших правил, восстановление шаблонов и проверка на живых фразах в «Песочнице правил».',
            en: 'Set rule type, priority and stage/language conditions, archive old rules, restore defaults and test phrases in the Rules Sandbox.',
        },
        botImpact: {
            ru: 'Прямое и мгновенное: активные правила добавляются в системную инструкцию бота [BOT OPERATING RULES] со следующего хода.',
            en: 'Direct and immediate: active rules are injected into [BOT OPERATING RULES] starting from the very next customer message.',
        },
        route: { view: 'botRules' },
    },
    {
        id: 'sec-catalog',
        group: { ru: 'Блок 2 · Знания и каталог', en: 'Group 2 · Knowledge & Catalog' },
        title: { ru: 'Каталог и остатки', en: 'Catalog & Inventory' },
        purpose: {
            ru: 'Панель контроля товарной витрины Treejar (цены, описания, фото, ссылки, поисковые векторы) и живого снимка складских остатков Zoho Inventory.',
            en: 'Control panel for the Treejar product catalog (prices, photos, canonical URLs, RAG vectors) and the Zoho Inventory stock snapshot.',
        },
        keyActions: {
            ru: 'Проверка свежести остатков Zoho (в минутах/секундах), числа проиндексированных товаров и ручной запуск синхронизации с Treejar API или Zoho.',
            en: 'Inspect Zoho stock snapshot age, indexed product counts and manually trigger Treejar Catalog API or Zoho sync.',
        },
        botImpact: {
            ru: 'Определяет, какие модели мебели, цены, фото и точные складские остатки Noor показывает покупателям в WhatsApp.',
            en: 'Governs which furniture models, AED prices, photos and exact stock counts Noor presents in WhatsApp.',
        },
        route: { view: 'catalog' },
    },
    {
        id: 'sec-reports',
        group: { ru: 'Блок 3 · Система и отчёты', en: 'Group 3 · System & Reports' },
        title: { ru: 'Отчеты', en: 'Reports' },
        purpose: {
            ru: 'Генератор стандартизированного операционного отчёта за последние 7 дней (отдельно от переключателя периода в «Обзоре») с предпросмотром текста для Telegram, топ-товарами и рейтингом менеджеров.',
            en: 'Standardized 7-day operations report generator (independent of the Overview period switch) with Telegram digest preview, top products and manager leaderboard.',
        },
        keyActions: {
            ru: 'Кнопка «Сформировать отчет» пересчитывает свежую сводку за 7 суток без ожидания еженедельного расписания.',
            en: 'Click Generate report to build an up-to-the-minute 7-day summary on demand.',
        },
        botImpact: {
            ru: 'Только чтение — формирование отчёта не отправляет сообщений клиентам и не меняет настройки.',
            en: 'Read-only — generating a report neither messages customers nor modifies settings.',
        },
        route: { view: 'reports' },
    },
    {
        id: 'sec-settings',
        group: { ru: 'Блок 3 · Система и отчёты', en: 'Group 3 · System & Reports' },
        title: { ru: 'Настройки', en: 'Settings' },
        purpose: {
            ru: 'Управление тремя контурами ИИ-контроля качества (Bot QA, Manager QA, Красные флаги), бюджетами в USD, инженерными параметрами оценки и связью с Telegram.',
            en: 'Configuration for the 3 AI quality contours (Bot QA, Manager QA, Red Flags), daily USD caps, advanced evaluator parameters and Telegram connectivity.',
        },
        keyActions: {
            ru: 'Режимы Выкл / Вручную / По расписанию / Ежедневная выборка, выбор модели и полноты транскрипта, лимиты вызовов, чекбоксы критериев и тестовое сообщение в Telegram.',
            en: 'Disabled / Manual / Scheduled / Daily sample modes, evaluator model & transcript depth, call limits, rubric criteria toggles and test Telegram notification.',
        },
        botImpact: {
            ru: 'Управляет работой ИИ-аудитора качества и тестовой проверкой уведомлений операторов.',
            en: 'Controls background and manual AI quality auditing plus operator alert verification.',
        },
        route: { view: 'settings' },
    },
    {
        id: 'sec-audit-system',
        group: { ru: 'Блок 3 · Система и отчёты', en: 'Group 3 · System & Reports' },
        title: { ru: 'Аудит и статус системы', en: 'Audit & System Health' },
        purpose: {
            ru: 'Две вкладки прозрачности и надёжности: неизменяемый «Журнал действий» администраторов и живая диагностика «Статус системы».',
            en: 'Two reliability tabs: an immutable admin Action Log with before/after diffs and real-time System Health diagnostics.',
        },
        keyActions: {
            ru: 'Фильтрация журнала по типу объекта и автору, просмотр изменений «было → стало», переход к изменённой сущности и проверка статуса PostgreSQL, Redis и Zoho.',
            en: 'Filter audit entries by entity or actor, inspect field-level diffs, jump to the modified record and verify PostgreSQL, Redis and Zoho health.',
        },
        botImpact: {
            ru: 'Обеспечивает полную подотчётность любых правок в кабинете и быструю диагностику инфраструктуры.',
            en: 'Provides full accountability for every admin action and instant infrastructure visibility.',
        },
        route: { view: 'auditSystem', tab: 'audit' },
    },
    {
        id: 'sec-acceptance',
        group: { ru: 'Дополнительно · Проверка и БД', en: 'Additional · Self-Test & DB' },
        title: { ru: 'Самопроверка (Acceptance)', en: 'Self-Test (Acceptance)' },
        purpose: {
            ru: 'Встроенный интерактивный стенд (также доступен по прямой ссылке /test) для приёмочного прогона сценариев WhatsApp + Telegram по шагам.',
            en: 'Built-in interactive workbench (also accessible directly at /test) for running structured WhatsApp + Telegram acceptance scenarios.',
        },
        keyActions: {
            ru: 'Прогон готовых сценариев (каталог, SKU, КП с кнопками Подтвердить/Отклонить в Telegram, ответ менеджера, /reset), отметки Pass/Fail и отправка отчёта тестера.',
            en: 'Run guided scenarios (catalog, SKU stock, Telegram quote Approve/Reject, manager reply, /reset), mark Pass/Fail and submit tester notes.',
        },
        botImpact: {
            ru: 'Используется во время приёмки новых функций на выделенном тестовом номере.',
            en: 'Used during feature acceptance testing on the dedicated test channel.',
        },
        route: { view: 'acceptance' },
    },
    {
        id: 'sec-sqladmin',
        group: { ru: 'Дополнительно · Проверка и БД', en: 'Additional · Self-Test & DB' },
        title: { ru: 'Инженерная панель /admin/ (16 таблиц)', en: 'Engineering Panel /admin/ (16 tables)' },
        purpose: {
            ru: 'Низкоуровневый интерфейс базы данных: 16 таблиц (диалоги, сообщения, товары, оценки, снимки метрик, аудит исходящих отправок, системные промпты с версиями).',
            en: 'Low-level database interface exposing 16 tables (conversations, messages, products, reviews, metric snapshots, outbound message audit, versioned system prompts).',
        },
        keyActions: {
            ru: 'Просмотр сырых полей БД, версий системных промптов и технических ключей конфигурации.',
            en: 'Inspect raw database columns, system prompt versions and low-level configuration keys.',
        },
        botImpact: {
            ru: 'Большинство таблиц открыто только для чтения ради безопасности; для ежедневной работы всегда используйте /dashboard/.',
            en: 'Most tables are read-only by design for safety; use /dashboard/ for 99% of daily operations.',
        },
        externalHref: '/admin/',
    },
];

export interface GlossaryItem {
    badge: LocalizedText;
    tone: 'green' | 'amber' | 'blue' | 'gray';
    meaning: LocalizedText;
}

export interface GlossaryGroup {
    id: string;
    title: LocalizedText;
    subtitle: LocalizedText;
    items: GlossaryItem[];
}

export const GUIDE_GLOSSARY: GlossaryGroup[] = [
    {
        id: 'lead-indicators',
        title: {
            ru: '1. Индикаторы «Кто ведёт диалог» (в шапке переписки)',
            en: '1. "Who leads the chat" badges (in conversation header)',
        },
        subtitle: {
            ru: 'Показывают, отвечает ли покупателю сейчас автоматика Noor или чат передан живому сотруднику.',
            en: 'Shows at a glance whether Noor is actively replying or waiting for a human operator.',
        },
        items: [
            {
                badge: { ru: 'Ведёт Noor', en: 'Handled by Noor' },
                tone: 'green',
                meaning: {
                    ru: 'Штатный автоматический режим: бот сам консультирует клиента, проверяет склад Zoho, присылает фото и готовит PDF-КП.',
                    en: 'Standard automated mode: Noor consults the buyer, checks Zoho stock, sends product photos and prepares PDF quotations.',
                },
            },
            {
                badge: { ru: 'Ожидает оператора', en: 'Waiting for operator' },
                tone: 'amber',
                meaning: {
                    ru: 'Открыта эскалация (опт 20+ шт., мебель под заказ, запрос менеджера или сложный случай). Уведомление отправлено в Telegram; после работы продавца нажмите «Закрыть эскалацию».',
                    en: 'An escalation is open (bulk 20+ units, custom furniture, human request or complex case). Telegram was alerted; click Close escalation once resolved.',
                },
            },
            {
                badge: { ru: 'Диалог закрыт', en: 'Conversation closed' },
                tone: 'gray',
                meaning: {
                    ru: 'Консультация или сделка завершена. Если клиент напишет снова, история сохранится.',
                    en: 'Consultation or order completed. Full history stays preserved if the customer writes back later.',
                },
            },
        ],
    },
    {
        id: 'funnel-stages',
        title: {
            ru: '2. Восемь этапов воронки продаж (Sales Stage)',
            en: '2. Eight Sales Funnel Stages',
        },
        subtitle: {
            ru: 'Этап определяется автоматически по ходу беседы и отображается в списке диалогов, карточке CRM и аналитике воронки.',
            en: 'Tracked automatically as the dialogue progresses and shown in chat lists, the CRM drawer and funnel charts.',
        },
        items: [
            {
                badge: { ru: 'Приветствие → Квалификация', en: 'Greeting → Qualifying' },
                tone: 'gray',
                meaning: {
                    ru: 'Первое касание, знакомство с клиентом, определение языка общения (EN / AR) и того, целевой ли это запрос по мебели.',
                    en: 'Initial contact, customer name & language detection (EN / AR) and verifying a genuine furniture inquiry.',
                },
            },
            {
                badge: { ru: 'Потребности → Решение', en: 'Needs analysis → Solution' },
                tone: 'blue',
                meaning: {
                    ru: 'Выяснение числа рабочих мест, размеров и бюджета; подбор конкретных моделей из каталога Treejar с фото, ссылками и остатками Zoho.',
                    en: 'Clarifying headcount, dimensions and budget; presenting catalog SKUs with photos, canonical links and live Zoho stock.',
                },
            },
            {
                badge: { ru: 'Компания → КП (Quoting)', en: 'Company details → Quoting' },
                tone: 'amber',
                meaning: {
                    ru: 'Клиент выбрал позиции и подтвердил расчёт КП: сбор реквизитов (имя, компания, адрес доставки) и выпуск официального PDF Quotation через Zoho.',
                    en: 'Items selected and quote confirmed: collecting customer/company details and issuing an official Zoho PDF Quotation.',
                },
            },
            {
                badge: { ru: 'Закрытие → Фидбек', en: 'Closing → Feedback' },
                tone: 'green',
                meaning: {
                    ru: 'Финальное согласование заказа, оплата/доставка и сбор оценки удовлетворённости покупателя (NPS).',
                    en: 'Order confirmation, delivery coordination and post-purchase customer satisfaction (NPS) collection.',
                },
            },
        ],
    },
    {
        id: 'bot-rule-types',
        title: {
            ru: '3. Пять типов правил в конструкторе «Правила бота»',
            en: '3. Five Rule Types in Bot Rules Builder',
        },
        subtitle: {
            ru: 'От выбранного типа зависит то, подключается ли правило в каждый ответ бота или только в подходящих по смыслу ситуациях.',
            en: 'Rule type determines whether an instruction runs unconditionally on every turn or matches contextually.',
        },
        items: [
            {
                badge: { ru: 'Жесткое (Hard rule)', en: 'Hard rule' },
                tone: 'amber',
                meaning: {
                    ru: 'Действует всегда (до 12 слотов в высшем приоритете). Используйте для строгих бизнес-ограничений: раскрытие 5% VAT, запрет выдумывать скидки или остатки.',
                    en: 'Always active (up to 12 top-priority slots). Use for non-negotiable guardrails: 5% VAT disclosure, no invented discounts or unverified stock.',
                },
            },
            {
                badge: { ru: 'Эскалация (Escalation rule)', en: 'Escalation rule' },
                tone: 'amber',
                meaning: {
                    ru: 'Действует всегда. Определяет ситуации обязательной передачи живому менеджеру (опт 20+ шт., нестандартное производство, запрос человека).',
                    en: 'Always active. Defines when Noor must route the chat to a human manager (bulk 20+ units, custom joinery, explicit manager request).',
                },
            },
            {
                badge: { ru: 'Сценарий (Playbook)', en: 'Playbook' },
                tone: 'blue',
                meaning: {
                    ru: 'Подбирается по смыслу сообщения (до 6 мягких правил на ход). Описывает как вести консультацию в конкретном кейсе — например, при комплектации офиса «под ключ».',
                    en: 'Matched semantically per message (up to 6 soft rules per turn). Guides consultative flow for specific scenarios such as turnkey office packages.',
                },
            },
            {
                badge: { ru: 'Допродажа (Upsell) и Стиль (Style)', en: 'Upsell & Style rules' },
                tone: 'green',
                meaning: {
                    ru: 'Подбираются по смыслу: «Допродажа» подсказывает уместные сопутствующие товары (кресла и тумбы к столам), а «Стиль» задаёт лаконичность и тон переписки.',
                    en: 'Matched semantically: Upsell suggests complementary items (chairs and pedestals with desks), while Style refines tone and WhatsApp formatting.',
                },
            },
        ],
    },
    {
        id: 'qa-contours',
        title: {
            ru: '4. Три контура ИИ-контроля качества',
            en: '4. Three AI Quality Control Contours',
        },
        subtitle: {
            ru: 'Настраиваются в «Настройки → Контроль качества AI», а результаты видны в карточках диалогов и разделе «Очереди и качество».',
            en: 'Configured in Settings → AI Quality Controls, with scores displayed in conversation drawers and Queues & Quality.',
        },
        items: [
            {
                badge: { ru: 'Проверка бота (Bot QA · 0–30)', en: 'Bot QA (0–30 pts)' },
                tone: 'blue',
                meaning: {
                    ru: 'Оценивает завершённые или выбранные диалоги Noor по 15 критериям: приветствие, выявление потребностей, точность артикулов, проверка Zoho, расчёт 5% VAT и оформление КП.',
                    en: 'Evaluates Noor conversations across 15 criteria: greeting, need discovery, SKU accuracy, Zoho stock check, 5% VAT clarity and quotation flow.',
                },
            },
            {
                badge: { ru: 'Оценка менеджеров (Manager QA · 0–20)', en: 'Manager QA (0–20 pts)' },
                tone: 'green',
                meaning: {
                    ru: 'Оценивает работу живого продавца после эскалации: скорость первого ответа, использование собранного ботом контекста, точность условий и закрытие сделки.',
                    en: 'Scores human manager follow-up after escalation: response speed SLA, use of bot handover context, commercial accuracy and closing hygiene.',
                },
            },
            {
                badge: { ru: 'Красные флаги (Red Flags)', en: 'Red Flags scan' },
                tone: 'amber',
                meaning: {
                    ru: 'Оперативный поиск критичных сбоев в переписке: пропущенный вопрос клиента, неподтверждённое обещание, пропуск сигнала на эскалацию или невежливый тон.',
                    en: 'Scans active conversations for critical issues: ignored buyer questions, unverified commitments, missed escalation signals or poor tone.',
                },
            },
        ],
    },
    {
        id: 'kb-and-crm-badges',
        title: {
            ru: '5. Метки статей Базы знаний и статусы сделок CRM',
            en: '5. Knowledge Base Origin Badges & CRM Deal Statuses',
        },
        subtitle: {
            ru: 'Помогают отличать базовые шаблоны от ручных правок и отслеживать состояние сделки в карточке клиента.',
            en: 'Distinguish factory templates from custom edits and track deal lifecycle inside the CRM drawer.',
        },
        items: [
            {
                badge: {
                    ru: 'Шаблон Treejar / Изменён вручную',
                    en: 'Treejar template / Customized',
                },
                tone: 'blue',
                meaning: {
                    ru: '«Шаблон Treejar» — эталонная заводская статья или правило. Если вы отредактировали её текст, метка меняется на «Изменён вручную» — «Безопасный режим» синхронизации бережно сохранит вашу правку.',
                    en: 'Treejar template marks canonical factory items. Editing one switches its badge to Customized so Safe Mode template sync never overwrites your wording.',
                },
            },
            {
                badge: { ru: 'Auto-FAQ / Вручную', en: 'Auto-FAQ / Manual entry' },
                tone: 'green',
                meaning: {
                    ru: '«Auto-FAQ» — статья, выросшая из реального ответа менеджера в Telegram (кнопка «📚 FAQ + клиент») после одобрения в кабинете; «Вручную» — созданная напрямую через кнопку «+ Новая».',
                    en: 'Auto-FAQ marks entries promoted from a Telegram manager answer ("FAQ + customer"); Manual entry marks articles created directly via + New in the dashboard.',
                },
            },
            {
                badge: {
                    ru: 'Сделка: pending → won → delivered',
                    en: 'Deal: pending → won → delivered',
                },
                tone: 'amber',
                meaning: {
                    ru: 'Статус коммерческой сделки в правой панели «CRM и детали» (рядом с Zoho Contact ID и Zoho Deal ID): в работе (pending), выиграна/оплачена (won) или доставлена покупателю (delivered).',
                    en: 'Deal lifecycle state editable in the right-hand CRM & details drawer (alongside Zoho Contact ID and Zoho Deal ID): in progress (pending), closed-won (won) or fulfilled (delivered).',
                },
            },
        ],
    },
];

export interface GuideFaqItem {
    id: string;
    question: LocalizedText;
    answer: LocalizedText;
}

export const GUIDE_FAQ: GuideFaqItem[] = [
    {
        id: 'faq-no-manual-messages',
        question: {
            ru: 'Можно ли из кабинета /dashboard/ случайно отправить сообщение реальному покупателю в WhatsApp?',
            en: 'Can clicking buttons in /dashboard/ accidentally send a WhatsApp message to a real customer?',
        },
        answer: {
            ru: 'Нет. Веб-кабинет специально спроектирован в режиме безопасного мониторинга и управления знаниями: здесь нет поля отправки сообщений клиентам. Живое общение менеджеров идёт в привычных рабочих каналах (WhatsApp / Wazzup / Telegram), поэтому вы можете спокойно изучать переписки, тестировать правила в песочнице и строить отчёты.',
            en: 'No. The dashboard operates strictly as a safe monitoring and knowledge-management control plane with no manual customer chat input. Live human replies stay in WhatsApp / Wazzup / Telegram, so exploring tabs, running the sandbox or generating reports never messages a customer.',
        },
    },
    {
        id: 'faq-how-fast-changes-apply',
        question: {
            ru: 'Нужно ли перезапускать сервер или звать разработчиков после правки Базы знаний или Правил бота?',
            en: 'Do we need a server restart or developer deploy after editing Knowledge Base or Bot Rules?',
        },
        answer: {
            ru: 'Не нужно. Как только вы нажимаете «Сохранить и проиндексировать» (или одобряете кандидата Auto-FAQ), сервер автоматически пересчитывает поисковый индекс, и уже со следующего входящего сообщения в WhatsApp Noor отвечает с учётом новых данных.',
            en: 'No restart or deploy is needed. Clicking Save and index (or approving an Auto-FAQ candidate) immediately updates the vector embeddings on the server, and Noor applies the change on the very next incoming WhatsApp turn.',
        },
    },
    {
        id: 'faq-kb-vs-rules',
        question: {
            ru: 'В чём разница между «Базой знаний» и «Правилами бота» — куда что добавлять?',
            en: 'What is the difference between Knowledge Base and Bot Rules — where should I add new info?',
        },
        answer: {
            ru: 'Простое правило: если это справочный ФАКТ о компании или условиях («доставка по Дубаю 3–5 рабочих дней», «адрес шоурума и часы работы», «способы оплаты») — добавляйте в «Базу знаний». Если это ПОВЕДЕНИЕ и приём продаж («всегда показывать сумму до и после 5% VAT», «к рабочим станциям предлагать кресла и тумбы», «опт от 20 шт. передавать менеджеру») — добавляйте в «Правила бота».',
            en: 'Rule of thumb: if it is a factual company policy ("delivery in Dubai takes 3–5 business days", "showroom address and hours", "accepted payment methods"), put it in Knowledge Base. If it is sales behavior ("always quote totals before and with 5% VAT", "suggest chairs with workstations", "escalate 20+ unit orders"), put it in Bot Rules.',
        },
    },
    {
        id: 'faq-safe-vs-full-sync',
        question: {
            ru: 'Что делает кнопка «Восстановить шаблоны» и не затрёт ли она наши собственные правки?',
            en: 'What does Restore templates do, and will it overwrite our custom edits?',
        },
        answer: {
            ru: 'При нажатии сначала открывается окно предпросмотра с двумя режимами. «Безопасный режим» (рекомендуется по умолчанию) восстанавливает только удалённые или отсутствующие базовые шаблоны Treejar и НЕ трогает статьи и правила, которые вы отредактировали вручную. «Полный сброс» возвращает все шаблонные записи к заводскому тексту.',
            en: 'Clicking Restore templates always opens a diff preview modal first. Safe Mode (default) restores missing canonical Treejar entries while leaving every admin-customized article or rule untouched. Full Reset reverts canonical items back to factory wording.',
        },
    },
    {
        id: 'faq-qa-button-locked',
        question: {
            ru: 'Почему кнопка «Оценить» (Bot QA / Manager QA) пишет, что проверка отключена?',
            en: 'Why does the Evaluate (Bot QA / Manager QA) button say quality review is disabled?',
        },
        answer: {
            ru: 'По умолчанию контуры ИИ-оценки выключены, чтобы не расходовать бюджет без вашего решения. Нажмите кнопку «Включить ручной режим» прямо в плашке предупреждения (или в разделе «Настройки») — и ручной запуск оценок сразу заработает в пределах заданного дневного лимита.',
            en: 'AI quality contours start disabled by default so no LLM evaluation spend occurs without your consent. Click Enable manual mode right inside the notice banner (or in Settings) to unlock on-demand evaluations within your daily limit.',
        },
    },
    {
        id: 'faq-treejar-vs-zoho-sync',
        question: {
            ru: 'Чем отличается синхронизация Treejar Catalog API от Zoho Inventory в разделе «Каталог и остатки»?',
            en: 'How does Treejar Catalog API sync differ from Zoho Inventory sync in Catalog & Inventory?',
        },
        answer: {
            ru: 'Treejar Catalog API — это витрина вашего сайта: оттуда берутся названия моделей, описания, фотографии, ссылки на карточки товаров и базовые цены, а также строятся поисковые векторы. Zoho Inventory — источник точных складских остатков в реальном времени (снимок остатков также обновляется автоматически каждые 5 минут в фоне) и система выставления официальных PDF-КП.',
            en: 'Treejar Catalog API is your website storefront source for product names, descriptions, photos, canonical URLs, catalog prices and search embeddings. Zoho Inventory is the source of truth for real-time warehouse stock (also refreshed automatically every 5 minutes) and formal PDF Quotations.',
        },
    },
    {
        id: 'faq-period-and-reports',
        question: {
            ru: 'Почему в «Обзоре» по умолчанию открыт период «Месяц», а в разделе «Отчеты» строится сводка за 7 дней?',
            en: 'Why does Overview default to Month while the Reports section builds a 7-day summary?',
        },
        answer: {
            ru: 'В «Обзоре» при первом входе включён «Месяц», чтобы графики и карточки KPI сразу показывали наглядную динамику даже после спокойных недель, а любое переключение (День / Неделя / Месяц / Все) автоматически запоминается в вашем браузере для следующих визитов. Раздел «Отчеты» решает другую задачу: он формирует стандартизированный 7-дневный операционный дайджест — точно такой же, какой уходит руководителю в еженедельном Telegram-отчёте.',
            en: 'Overview defaults to Month on first visit so KPI cards and trend charts always carry meaningful context, and remembers whichever period (Day / Week / Month / All) you pick next in your browser. Reports serves a distinct purpose: generating the standardized 7-day operational digest that mirrors the weekly Telegram executive report.',
        },
    },
    {
        id: 'faq-shared-login-tour',
        question: {
            ru: 'Если один сотрудник уже вошёл через свой Telegram и прошёл обучение, запустится ли тур у другого коллеги?',
            en: 'If one admin already signed in via Telegram and finished the tour, will another teammate still get the walkthrough?',
        },
        answer: {
            ru: 'Да, обязательно запустится. Отметка о прохождении тура сохраняется локально в браузере конкретного устройства, а не на сервере. Когда другой сотрудник войдёт со своего компьютера или телефона, система автоматически проведёт для него полную экскурсию. Кроме того, прямая ссылка /dashboard/?tour=1 и кнопка «Интерактивный тур» в шапке запускают обучение повторно в любой момент.',
            en: 'Yes. Tour completion is stored locally in each user’s own browser rather than in the server database. When a teammate signs in on their own workstation or phone, the full interactive tour starts automatically — and /dashboard/?tour=1 or the header Tour button replays it anytime.',
        },
    },
];

export interface PipelineStepItem {
    step: string;
    title: LocalizedText;
    detail: LocalizedText;
}

export const GUIDE_PIPELINE_STEPS: PipelineStepItem[] = [
    {
        step: '01',
        title: { ru: 'Клиент пишет в WhatsApp', en: 'Buyer writes on WhatsApp' },
        detail: {
            ru: 'Сообщение поступает через Wazzup (текст, голосовые с авторасшифровкой, фото, EN или AR) и попадает в конвейер Noor.',
            en: 'Inbound message arrives via Wazzup (text, auto-transcribed voice notes, EN or AR) into Noor’s pipeline.',
        },
    },
    {
        step: '02',
        title: { ru: 'Память, каталог и правила', en: 'Memory, catalog & rules' },
        detail: {
            ru: 'Noor сверяется с «Каталогом» и остатками Zoho, ищет факты в «Базе знаний» и применяет активные «Правила бота».',
            en: 'Noor checks Catalog & live Zoho stock, retrieves Knowledge Base facts and applies active Bot Rules.',
        },
    },
    {
        step: '03',
        title: { ru: 'Ответ, PDF-КП или Telegram', en: 'Reply, PDF Quote or Telegram' },
        detail: {
            ru: 'Клиент получает подборку с фото, ценами ±5% VAT и PDF-КП из Zoho, а опт/кастом передаётся менеджеру в Telegram.',
            en: 'Buyer gets photos, ±5% VAT pricing and Zoho PDF quotes, while bulk/custom inquiries alert a manager in Telegram.',
        },
    },
    {
        step: '04',
        title: { ru: 'Контроль в /dashboard/', en: 'Oversight in /dashboard/' },
        detail: {
            ru: 'Вся переписка, сделки, очереди, оценки качества (Bot QA / Manager QA) и аудит сразу видны в этом кабинете.',
            en: 'Every chat, deal stage, queue item, AI quality score and audit record surfaces here in real time.',
        },
    },
];
