# Did the build regress? A flat mean with a five-point trade inside it

Asked because the published acceptance number used to be higher — 18.5 at its
peak — and is now quoted at about 12. Answered 2026-08-08 by reading two stored
builds on one instrument. No live traffic, no paid judge call, no deploy.

**The build did not regress. The number was never real.** But the comparison
turned up a genuine regression the mean could not show.

## The instrument

Two blind Claude readers, each scoring the ten stored transcripts of both
builds: same prompt, same fifteen criteria, the applicability map the runtime
derived rather than one the reader chose, and the arithmetic handed to the
product's own `calculate_weighted_score`. Neither reader was told which build
produced a transcript, saw the other's scores, or saw any earlier scoring.

Two readers rather than five, at the owner's call. It costs almost nothing: the
pooled sd came back at **0.9**, the same figure the five-reader panel measured,
and the interval on the mean widened only from ±0.3 to ±0.4.

## What the numbers were, and are

| build | old judge | published | this panel |
|---|---|---|---|
| `6a14f2f` 2026-08-07 13:34 | 16.1 | **18.5** | **12.6 ± 0.4** |
| `5656c82` 2026-08-07 15:12 | 16.1 | 18.2 | **12.6 ± 0.4** |

The 18.5 was 16.1 with the /30 normalisation applied a second time by hand, and
the 16.1 came from a judge that reads about four points more generously than a
careful reader and carries sd 3.8. Two separate corrections to the measurement,
neither of them a change in the product.

## The finding the mean hid

```
6a14f2f -> 5656c82    mean 12.6 -> 12.6, delta -0.0 +/- 0.6
```

Identical. Inside it, two scenarios moved past their bound of 1.8:

```
S05   14.1 -> 17.3   +3.2   real gain
S07   17.8 -> 14.5   -3.3   real regression
```

Everything else sat inside the noise. A real regression and a real gain of the
same size cancelled exactly, and no single number could have shown it. This is
the argument for reading per scenario with a stated bound rather than watching
one mean: the mean was honest and told us nothing.

## What broke in S07

Visible in the transcripts without any judge. The customer asks for laboratory
fume hoods, which Treejar does not sell, then asks to be told plainly and shown
what Treejar does carry.

`6a14f2f` says there is no exact match, then lists three real products with
verified prices and stock and names the most relevant:

> The closest office-furniture alternatives currently listed are: Work station,
> XTEN-S, XWST 2470 — AED 606.64; 10 in stock … The XTEN-S workstation is the
> most relevant alternative

`5656c82` answers the same request with nothing but a restatement of the
instruction:

> Understood, Rami. I will clearly state when Treejar has no exact catalog match
> and suggest only relevant office-furniture categories that Treejar actually
> carries

No product, no price, no category. The customer asked what Treejar carries and
was told what Noor intends to do. Filed as `tj-2m5m.6`; the candidate cause is
the slot rewrite series between the two builds, and the fix has to keep the
grounding guarantee that makes the `6a14f2f` answer acceptable — every figure in
it came from a verified row.

S08's bulleted-echo behaviour is identical in both builds (+0.0), so that one is
a standing defect rather than part of this.

## A methodological correction, recorded because it nearly misled

The first pass compared this panel against the five-reader panel of 2026-08-07
and reported S03 moving +3.3. Reading the two S03 transcripts side by side
showed near-identical content, which is what prompted the recheck. Scored by the
same two readers, S03 moves −0.5 — inside the noise.

Two differently-prompted panels do not share a noise estimate any more than two
judge models do. Between-panel drift here is about 0.3 on the mean, small but
real. **Compare within one instrument.**
