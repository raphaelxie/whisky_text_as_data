# Version 2 Lexicon Reconstruction Protocol

## Purpose

Version 2 rebuilds the tasting-language instrument before any further
interpretation of the `Natural_Artificial` embedding dimension. Version 1 is
retained as historical and sensitivity evidence, but is superseded for primary
interpretation because its nine-category design mixed constructs and did not
record a complete term-level approval trail. The simplified Version 2 design
contains eleven primary constructs. It omits herbal/tea because it is not a
central connoisseurial vocabulary for this study's theoretical argument and
replaces the former combined sherry/rancio category with `sherry_influence`,
which distinguishes direct cask references from berry and dried-fruit
association candidates during adjudication.

## Blind Approval Workflow

Run:

```bash
python -m analysis.dictionary candidate
```

This creates `dictionary_v2_adjudication.csv`,
`dictionary_v2_ambiguous_terms.csv`, and `dictionary_v2_exclusions.csv`. The
worksheet displays candidate terms, prior and proposed category assignments,
review frequency, three concordance snippets, and construct definitions. It
does not display review scores, regressions, projections, WEAT tests, or
validation-group differences.

The command will not overwrite a worksheet that already exists, protecting
manual decisions between sessions. The `--overwrite` option should be used
only when intentionally discarding and restarting all adjudication work.

For each candidate, the reviewer must set `decision` to one of:

- `approve_primary`
- `exclude_ambiguous`
- `exclude_irrelevant`
- `exclude_infrequent`

Every candidate row must also contain `reviewer_rationale` and a
`reviewer_status` of `approved`. Ambiguous terms are flagged but not
pre-decided: the reviewer must explicitly choose `exclude_ambiguous` or
document why an ambiguous term should nevertheless be approved for one
primary construct after concordance review.

After review is complete, run:

```bash
python -m analysis.dictionary freeze
```

The freeze command fails if any candidate row lacks a decision or rationale, if
an approved primary term is duplicated, if it occurs in fewer than 10 reviews,
or if any of the 11 categories has no approved term. An ambiguity-flagged term
may enter a primary category only through an explicit documented approval.

## Constructs

| Category | Short name | Construct |
| --- | --- | --- |
| `fruit` | `fruit` | Fresh, citrus, tropical, and orchard fruit descriptors |
| `floral` | `floral` | Flower and blossom descriptors |
| `spice` | `spice` | Culinary spice descriptors |
| `peat_smoke_coastal` | `peat` | Peat, smoke, ash, maritime, and coastal descriptors |
| `sherry_influence` | `sherry` | Direct sherry-cask references and reviewed berry or dried-fruit sensory markers of sherry influence |
| `oak_cask_wood` | `oak` | Wood and cask influence |
| `texture_body` | `texture` | Mouthfeel and bodily texture |
| `mineral_earth_farmy` | `mineral` | Mineral, earth, grain, and agricultural descriptors |
| `flaws_off_notes` | `flaw` | Defect and contamination descriptors |
| `complexity_balance` | `structure` | Structural judgment language |
| `explicit_evaluation` | `eval` | Direct praise and blame language |

## Ambiguity Rule

Context-dependent terms must be explicitly reviewed and, when marked
`exclude_ambiguous`, are excluded from primary category rates and introduced
only in labeled sensitivity scenarios after freeze. The initial register
includes `tcp`, `sulphur`, `polish`, `farmyard`, `barnyard`,
`manure`, `medicinal`, `antiseptic`, `bandage`, `phenolic`, `creosote`,
`diesel`, `engine_oil`, berry-family candidates, `date`, `dried_fruit`,
`dried_fig`, `dried_apricot`, `dried_citrus`, `prune`, `raisin`, `sultana`, `fig`,
`jam`, and `marmalade`. `honey` is also presented for explicit reviewer
adjudication rather than automatically retained as fruit.

`rancio`, `balsamic`, `old_book`, and `antique` are flagged as possible
aged/oxidative character language rather than direct sherry-cask cues. Other
inherited dark, nutty, confectionary, or tobacco/leather descriptors remain
visible in the worksheet but are ambiguity-flagged because association with
sherried whisky is not the same as measuring sherry-cask reference.

Direct sherry candidate expansion includes `manzanilla`, `palo_cortado`,
`cream_sherry`, `pedro_ximenez`, `bodega`, `ex_bodega`, and `jerez`. Berry
and dried-fruit candidates are proposed under `sherry_influence` with
ambiguity flags so their inclusion or exclusion is explicitly documented.
`solera` is included as an ambiguity-flagged candidate because it may not
identify a direct sherry-cask cue in every whisky-review context.

The omitted herbal/tea candidate family (`mint`, `herbal`, `black_tea`,
`green_tea`, and `earl_grey`) is recorded in `dictionary_v2_exclusions.csv` as
a construct-design exclusion rather than assigned to a primary category.
After phrase matching was corrected to recognize spaced and underscored forms,
`sea_breeze` was observed in the corpus and is therefore retained as a peat
candidate for manual review rather than excluded as zero-frequency.

Only singular `flower` is included as a floral candidate. The current
preprocessing step lemmatizes ordinary words consistently when they are
followed or surrounded by punctuation, so forms such as `flowers,` and
`berries.` are counted under their singular canonical candidates. Underscored
phrase tokens remain intact.

## Editing Workflow

Do not add terms by editing `notebooks/v2_dictionary_review.ipynb`. The
notebook only reads and presents the generated worksheet. To add or reassign a
candidate before review begins, edit the candidate definitions in
`analysis/dictionary.py`, run `python -m analysis.dictionary candidate
--overwrite`, and then rerun the notebook. Once manual decisions have been
entered in the CSV, do not use `--overwrite` unless intentionally discarding
that review work.

## Post-Freeze Outputs

After the instrument freezes successfully, run:

```bash
python -m analysis.models
python -m analysis.embeddings
python -m analysis.assemble
```

Primary Version 2 analytical artifacts are written under `data/v2/` and
`figures/v2/`. Ambiguous-term allocation scenarios report changes to
coefficients, independent validation differences, and embedding projections;
frequency-weighted embedding means remain a separately labeled sensitivity
output. The `Natural_Artificial` name and poles remain unchanged during
reconstruction; its substantive interpretation must be reconsidered only
after Version 2 evidence exists.
