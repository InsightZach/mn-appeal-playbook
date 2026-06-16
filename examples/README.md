# Worked Examples

Three real 26p27 residential parcels run through the playbook, with the documented outcomes. Owner names
and client-specific notes are removed; the address, PID, and assessment figures are public record. Each
case study shows the same lifecycle — data → triage → packet → submission → outcome — and together they
make the central point of the whole playbook:

> **Process, not the packet, determines the outcome.** The same kind of property, in the same season, with
> a comparable filing, reduced or didn't reduce based on *how the appeal was run* — whether anyone engaged
> the appraiser and got onto the property.

| Example | County / jurisdiction | Triage | How it was run | Outcome |
|---------|----------------------|--------|----------------|---------|
| [884 Ashland Ave](ramsey-884-ashland.md) | Ramsey (county-assessed) | Appeal angle | In process | Pending — illustrates the clean single-authority path and the timeline |
| [2913 Drew Ave S](minneapolis-2913-drew.md) | Hennepin / **Minneapolis** (self-assessing) | Strong angle | Mailed written appeal, **no engagement** | **No change** — Local Board sustained |
| [15012 Cherry Ln](minnetonka-15012-cherry.md) | Hennepin / **Minnetonka** (self-assessing) | Borderline | Appraiser **inspected**, corrected the record | **Reduced** $952,200 → $922,700 |

## The lesson in one line

The Minneapolis parcel had the *stronger* triage angle (the owner's own purchase was 8.6% below the
assessed value). It got nothing — because it was mailed in as a written appeal with no appraiser contact.
The Minnetonka parcel had only a *borderline* angle. It won a reduction — because an appraiser inspected
the property and corrected the record. That contrast is the case for running appeals as an operation, not
a mail-merge.

Each case study is reproducible: the figures come from the collectors in [`../collectors`](../collectors)
and the triage in [`../scripts`](../scripts).
