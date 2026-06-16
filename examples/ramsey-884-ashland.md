# Worked Example — 884 Ashland Ave, St. Paul (Ramsey County)

The clean single-authority case: Ramsey assesses every jurisdiction in the county, so routing is trivial
and there is one process and one contact. This example shows the data → triage → packet path and the
Ramsey timeline.

## Subject (public record)

| Field | Value |
|-------|-------|
| Address | 884 Ashland Ave, St. Paul, MN 55104 |
| PID | 02-28-23-24-0039 |
| County / assessor | Ramsey County (county-assessed) |
| Year built | 1939 |
| Finished SF | 1,355 (Ramsey basis — includes finished basement) |
| Lot | 0.14 ac |

## Assessment history

| Assess year | EMV total | YoY |
|-------------|-----------|-----|
| 2024 | $453,400 | — |
| 2025 | $511,900 | +12.9% |
| 2026 (under appeal) | $498,600 | −2.6% |

## Triage

**Verdict: appeal angle.** Signals:

- **Subject's own sale below EMV** — the property sold arm's-length for **$470,000 on 2025-04-10**, which
  is **5.7% below** the 2026 EMV of $498,600. The strongest single piece of evidence.
- **Equalization** — building assessed at **$264/SF vs. a $185/SF neighborhood median (98th percentile)**;
  land $/SF mid-pack (55th percentile). The over-assessment is in the building line.
- **EMV history** — the county already trimmed 2.6% for 2026 after a +12.9% jump in 2025; the building
  loading still leaves room.

## Listing enrichment changed the packet

Pulling the listing (MLS / public) before drafting reshaped the argument:

- The **$470,000 sale is MLS-confirmed** as arm's-length — the own-sale evidence is verifiable, not just a
  county data point.
- **Photos show a renovated interior** — so a condition downgrade is off the table, and the 98th-percentile
  building $/SF is *secondary* (a renovation plausibly justifies an above-median building value), not the
  lead argument.
- **Record discrepancies surfaced** — the listing shows 2,060 SF / built 1970 vs. the county's 1,355 SF /
  1939; flagged for verification, not relied upon.

See the [listing enrichment guide](../collectors/listing_enrichment.md).

## Packet

The packet leads with the **subject's own MLS-confirmed arm's-length sale** as the governing evidence,
uses neighborhood sales to corroborate, and treats equalization as secondary support. It claims **no
condition adjustment** (the photos show good condition). The requested value is the $470,000 purchase
price — a value the evidence brackets, not below it.

A rendered demonstration of this packet (illustrative sample, format only) is at
**[`sample-appeal-packet.html`](sample-appeal-packet.html)**.

## How it's run (Ramsey path)

```
Ramsey County Assessor (open book / informal review)
  → Ramsey County Local Board / open book
  → Ramsey County Special Board of Appeal & Equalization (after the 2nd Friday in June)
  → MN Tax Court (petition by April 30 of the payable year)
```

One office, one calendar. Engage the assessor in the open-book window, deliver the packet, and request a
review.

## Outcome

**Pending** at the time of writing — Ramsey's response had not yet come back. That is itself instructive:
the county boards convene in mid-to-late June, and a parcel in process at that point is exactly on the
normal timeline. The lesson is the calendar discipline — engage early in the open-book window so the
appraiser has time to review before the board date, rather than arriving with a packet at the end.
