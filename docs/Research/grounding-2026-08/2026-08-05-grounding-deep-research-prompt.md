Target: Deep Research analyst, web-enabled
Audience: manual handoff; the requester will run this brief in two different models and compare the outputs

Goal: Produce an evidence-graded briefing on how teams running LLM sales assistants in production stop the model asserting product facts it has no source for, without degrading it into a hedging, refusing, robotic assistant. Both halves weigh equally; a briefing that only covers hallucination suppression is a failed answer.

Success criteria:
- Every claim carries a URL and a publication date.
- Every source is labelled practitioner-experience, academic, vendor-marketing, or unverified/likely-AI-generated.
- Reddit and Hacker News threads are covered with quoted substantive comments, including dissenting ones.
- Questions with no real evidence are marked "no substantive evidence found" rather than filled in.
- Disagreements between sources are shown as disagreements, not averaged.

Context (you have no access to the requester's codebase; this is all you get):
A deployed B2B sales assistant for office furniture in the UAE, on WhatsApp and Telegram, answering in English, Arabic and Russian. It is a tool-calling agent over a product catalog (SKU, name, description text, category, price, stock, free-form attributes JSON), a CRM, and a quotation generator. A controlled comparison of four frontier models over 60 responses surfaced three failure modes:
(a) asserting product attributes absent from the retrieved catalog rows - "breathable mesh back", "synchronised tilt mechanism", "each desk seats ten people";
(b) invoking the quotation tool after the customer explicitly declined a quote, in the same turn as saying it would not prepare one;
(c) the automated LLM judge penalised a clearly LABELLED assumption ("assuming roughly ten workstations per desk - or would you prefer a different split?") as a hallucination, while missing a vaguer unsourced claim ("its verified catalog features include adjustable elements and supportive seating").
Already in place: numbers, SKUs, prices and stock are verified against tool output; a state-based allowlist hides some tools in some conversation states; a model-owned rewrite pass exists for numeric corrections.

Questions - one numbered heading each, so two runs can be diffed:

Q1 Approaches used in production 2024-2026: per-claim citation/provenance, structured "fields I relied on" plus code verification, state-machine tool gating, second-pass groundedness checking, ensemble or disagreement checking, knowledge-graph verification, constrained decoding, fine-tuning for abstention. For each: mechanism, position in the request path, whether it ELIMINATES a class of error or only DETECTS it, and known limits.

Q2 Quantitative evidence: hallucination rate before and after, false-positive or over-refusal rate, added latency, added cost per message, engineering effort. Label each number measured, vendor-claimed, or anecdotal.

Q3 The over-constraint problem: evidence that groundedness guards degrade an assistant - higher refusal, more hedging, blander answers, lower conversion or satisfaction. How is it detected and measured? Which benchmarks or in-house false-refusal eval sets are used? Any reported commercial impact.

Q4 The labelled-assumption pattern: is there established practice of letting the model state a visible assumption and ask a confirming question, instead of asserting or refusing? Where documented - sales methodology, agent UX, prompt frameworks, eval rubrics? How is it distinguished in evaluation from hedging that hides an unsourced fact? Evidence on customer response in a selling context.

Q5 Verifier reliability: evidence for and against a second LLM checking the first for groundedness - agreement with human labels, failure modes, whether a narrow "is this sentence supported by this passage" task measurably beats holistic scoring, and how ensemble disagreement, NLI/entailment models, retrieval-based verification and uncertainty estimation compare. Include checker model-size and cost tradeoffs.

Q6 Data prerequisite: evidence on catalog or PIM attribute completeness as root cause - typical completeness rates, whether guarding is reported ineffective below some threshold, and what is done about attributes that genuinely do not exist in the catalog.

Q7 Evaluation practice: how an observed failure becomes a durable regression suite - test-case format, judge rubrics, human-labelled sets, sample sizes, handling of judge-criteria drift, and whether anyone reports judge errors of the kind in point (c).

Q8 Anti-recommendations: what is reported as not working or counterproductive - system-prompt-only bans, temperature reduction, hard output blocking, long rule lists, "zero hallucination" vendor claims.

Q9 Ranked recommendation for the exact situation in Context: what to do first, second, third, with rationale and rough effort, and what to deliberately NOT do.

Constraints:
- Prioritise practitioner postmortems with concrete numbers, engineering blogs of companies actually running such an assistant, GitHub issues/discussions/PRs in agent and guardrail frameworks, Reddit (r/LLMDevs, r/AI_Agents, r/MachineLearning, r/LocalLLaMA, r/ExperiencedDevs), Hacker News, and arXiv or peer-reviewed work reporting an evaluation.
- Reddit and Hacker News were unreachable in a prior attempt and matter most; do not skip them.
- Flag content-farm signals: no named author, no date, unfinished editorial placeholders, confident claims with no numbers, a conclusion that resolves to buying the author's product.
- Do not invent or estimate statistics.

Output: numbered sections Q1 to Q9, each ending with one line "Confidence: high/medium/low - because ...". Then a source table: URL, date, type label, one line on reliability. Target 2000-3500 words. No executive summary, no closing pep talk.

Stop: if the search returns mostly vendor marketing, say so plainly and report what evidence is missing rather than padding the sections.
