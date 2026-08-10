# DRAFT — NOT SENT: rubric validity and missing evidence

Across 1247 evaluated dialogues from 1400 unfiltered WhatsApp dialogues, scored
by `claude-haiku-4.5` across five manager groups with one group contributing
about 67%, four criteria were almost never earned:

- sincere compliment: 0.00/2 across 1247 evaluated dialogues;
- “drill and hole” / customer job: 0.01/2 across 1247 evaluated dialogues;
- ask what the customer's company does: 0.02/2 across 1247 evaluated dialogues;
- discount, bundle, or bonus: 0.05/2 across 1247 evaluated dialogues.

Together these criteria occupy 8 of 30 available points. Could you confirm
which interpretation is correct: the criteria no longer describe the sales
method, the evaluator does not reliably detect them, or the method is intended
but is not practised in WhatsApp? The comparison also goes the other way: Noor
already scores 0.75/2 on asking what the company does over the stored 53-packet,
19-scenario panel, versus 0.02/2 across the 1247 evaluated human dialogues. We
see that as a differentiator, not a defect.

To finish a defensible comparison, could you also provide:

1. The exact evaluator prompt offered in section 8 of the corpus note. Without
   it, any `claude-haiku-4.5` bridge must be labelled as reconstructed from the
   `rubric.json` anchors rather than run with the client's prompt.
2. The exported attachments. “Can you share some pictures?” is the most common
   unanswered customer request, while the current export retains filenames or
   attachment types but not the files themselves.
3. A Zoho deal export keyed by `crm_deal_id`. Outcomes are visible in-channel
   for only 192 of 1400 dialogues; without the deal export there is no outcome
   variable and therefore no defensible statement about conversion, revenue,
   deal size, or close rate.

These requests are for measurement inputs only. This draft makes no claim that
a rubric score predicts an outcome or that Noor closes deals.
