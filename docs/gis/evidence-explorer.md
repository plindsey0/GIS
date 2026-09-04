# Entity-centered Evidence Explorer

The Workbench Evidence area answers “what does GIS know about this subject?” rather
than exposing a flat list of provider records. Filters cover subject text, canonical
entity type, registered source, evidence type, evidence status, and page size. Source
choices come from the source registry, so newly registered providers do not require a
hard-coded filter option.

## Inspect BuiltWith technology intelligence

1. Open **Evidence**.
2. Select **BuiltWith** under Source / provider, select **Domain**, and search for the
   hostname.
3. Open the canonical domain result. The technology facet groups normalized detections
   using BuiltWith's reported category and keeps search/domain observations attached to
   the same domain identity.
4. Open a technology to inspect provider identity, reported first/last-seen dates,
   evidence identifiers, hashes, policy version, acquisition method, ingestion run,
   orchestration run, and source.

First seen and last seen are provider-reported history. They do not prove that a
technology is installed now; the interface therefore says current presence is unknown.
Raw provider evidence appears only when the policy recorded on that observation sets
raw display to `ALLOWED`. Otherwise, safe provenance remains visible and raw content is
withheld. `UNKNOWN` never grants display permission.

## Received and inserted counts

The first live `vahomemath.com` collection received 25 technology entries and produced
24 canonical detections, with zero rejects and zero errors. Inspection of the stored
evidence found two distinct BuiltWith source signatures for Google Analytics. Both
source evidence records were retained, while identity resolution correctly consolidated
them into one canonical Google Analytics detection. Thus “received” counts source
entries and “inserted” counts unique normalized technologies; the difference is not
collection loss.

This accounting explanation is derived prospectively in the evidence and run views.
Historical counters and evidence are not rewritten.

## Credits and cost

Provider requests and provider-reported credit headers are operational facts captured
with the collection response. They are labeled with that scope and timestamp rather than
presented as permanent account state. The configured `$0.0495` per-domain value is an
estimated economic cost derived from the operator pricing assumption. It is never an
actual charge. Actual provider USD cost remains **Not reported** unless BuiltWith reports
one explicitly.

## Reusable provider pattern

Future collectors should resolve their subject to an existing canonical `Domain`,
`Site`, URL, or query identity and attach typed observations to it. The explorer may
then expose a provider-specific facet while preserving common navigation:

`canonical subject → typed observation → normalized item → provenance → ingestion/run → source`

Do not create provider-specific copies of a canonical subject, flatten typed evidence
into one universal record, duplicate live System status in evidence tables, or loosen
rights to improve discoverability. System source and run pages remain the authority for
live connection, schedule, reliability, and provider-operational state.
