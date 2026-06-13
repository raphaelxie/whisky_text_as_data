# Theoretical Framework

## Making Expert Taste Computable

**Purpose:** Authoritative theoretical and measurement guide for revising the
paper toward submission to *Poetics: Journal of Empirical Research on
Culture, the Media and the Arts* (primary target), with *Big Data & Society*,
*Socius*, and ICWSM 2027 as ranked backups. It positions the project as
cultural sociology of expert valuation, with whisky criticism as a bounded
empirical case. It is not itself the manuscript. See
`paper/REFRAMING_MEMO_POETICS.md` for the submission strategy and timeline.

**Preferred paper title:** *Making Expert Taste Computable: Theory-Guided
Measurement of Valuation and Symbolic Boundaries in Whisky Reviews*

**Cultural-sociology alternative:** *Expert Whisky Criticism Produces Cultural
Value: Discernment and Symbolic Boundaries in Whiskyfun Reviews*

**Methods-forward alternative:** *Measuring Expert Valuation in Text:
Interpretable Domain Categories and Semantic Boundaries in Whisky Reviews*

## Working Statement

> This paper develops a transparent computational measurement strategy for
> studying how expert discourse organizes value. Prediction is a validation
> benchmark; the sociological object is the interpretable classification of
> sensory character and defect.

## 1. Central Problem And Argument

### The Problem

A sensory encounter is private, fleeting, and difficult to compare. A bottle
does not announce itself as complex, elegant, artificial, flawed, mature, or
worthy of a high score. An expert review must make those classifications
publicly recognizable and authoritative.

The paper therefore joins a substantive question to a computational
measurement question:

> How can theory-guided text measurement make observable the classifications
> through which expert whisky criticism transforms sensory experience into a
> publicly recognizable hierarchy of value?

### The Argument

> Expert whisky criticism organizes sensation as discernment, and a
> human-adjudicated domain instrument combined with semantic-space analysis
> makes part of that classificatory process computationally observable.

Here, **produces** has a specific and limited meaning. Criticism does not
magically create material qualities in a bottle, and this study does not
estimate effects on sales, prices, collectors, or readers. Criticism produces
value discursively: it makes certain sensory differences nameable, comparable,
consequential, and ratable.

### The Empirical Contribution

Whiskyfun is treated as a case of an expert judgment institution. Its
structured reviews make visible a sequence in which a critic attends to
sensations, names them through a specialized vocabulary, distinguishes valued
character from defect, and records a numerical judgment. The empirical
contribution is paired with a measurement contribution: the study documents
how theory, term adjudication, independent validation, prediction benchmarks,
and embedding-sensitivity tests can be joined in computational analysis of a
specialized evaluative discourse.

## 2. What The Study Can And Cannot Claim

### Defensible Claims

- This corpus reveals a specialized language of discernment whose evaluative
  content is not reducible to generic sentiment.
- Evaluative relevance is embedded in sensory description, not confined to
  explicit verdict language.
- In this evaluative discourse, artificial defect is a robust boundary against
  which legitimate whisky character is organized.
- Whiskyfun offers an institution-specific case of the discursive production
  of value in a singular sensory good.
- Theory-guided categories provide interpretable social measurement even where
  a high-dimensional lexical benchmark is more predictive.

### Claims Not Supported By The Design

The dataset does not observe reader class position, acquisition of competence,
audience uptake, market prices, purchases, or comparison among multiple
critical institutions. The paper therefore must not claim that it:

- demonstrates the class distribution of whisky taste;
- tests Bourdieu's homology thesis or proves social reproduction;
- shows that consumers use tasting vocabulary as cultural capital;
- identifies a causal impact of reviews on economic value;
- represents all whisky criticism or all expert tasting discourse.

The single-reviewer design is useful because it isolates an internally
consistent critical repertoire. Its limitation is equally important: findings
characterize this corpus and its reviewing practice.

## 3. Theoretical Architecture

For Poetics, theory is the leading contribution, not ornamental context after
a methods section. It defines the constructs that the dictionary and semantic
axes attempt to measure. The section should proceed as a cumulative argument
(Bourdieu → Hennion → Douglas), not a list of theorists or a horse race
among competing explanations.

### 3.1 Bourdieu: Taste As Classification And Competent Judgment

Bourdieu should be central rather than an opening foil. *Distinction* matters
here because expert reviews enact classification: they separate subtle from
simple, balanced from excessive, legitimate character from defect, and worthy
objects from ordinary or failed ones. Expert vocabulary displays a competent
relation to sensory objects by making fine differences intelligible as
differences of quality.

Use Bourdieu to develop four propositions:

1. Judgments of taste classify objects and simultaneously present a competent
   manner of attending to them.
2. Cultivated appreciation relies on learned distinctions that do not appear
   self-evident without practical familiarity.
3. Technical and controlled description can authorize a judgment by presenting
   it as informed discernment rather than simple liking.
4. A public repertoire of fine distinctions can provide the discursive
   infrastructure of legitimate appreciation even when the analyst does not
   observe the social positions of readers.

Do not treat the corpus as a direct test of class distinction. The appropriate
Bourdieusian contribution is narrower: the study observes how a mode of
legitimate appreciation is linguistically organized, not who acquires it or
what social advantages it yields.

**Bridge sentence:**

> Whiskyfun makes visible the classificatory work of expert taste: sensory
> impressions become judgments of quality through a learned vocabulary of
> differences that can be publicly recognized as competent appreciation.

### 3.2 Jarness: From What People Consume To How They Appreciate It

Jarness's shift from object choice to modes of consumption clarifies why a
review corpus is theoretically valuable. The project cannot identify which
social groups drink single malt whisky. It can identify, in unusual detail,
how whisky is appropriated as a worthy object within an expert mode of
appreciation.

This move avoids a weak argument based on whisky being expensive or elite.
Whisky matters because it is a setting in which distinctions of attention,
description, and judgment are recorded repeatedly and systematically.

**Bridge sentence:**

> Rather than infer distinction from the consumption of whisky as an object,
> this study examines the mode of appreciation through which an expert
> discourse renders whisky differences culturally meaningful.

### 3.3 Hennion: Tasting As Practical, Mediated Attention

Hennion supplies the account of how tasting is accomplished. Appreciation is
not merely status display; it involves bodies, glasses, sequences of tasting,
comparison, memory, language, and repeated attention. Specialized terms do
practical work by stabilizing subtle sensations as objects of reflection and
communication.

Hennion should complement Bourdieu, not replace him:

> Bourdieu identifies the classificatory stakes of legitimate taste; Hennion
> identifies the practical and mediated labor through which tasting becomes
> possible. Expert whisky criticism joins these dimensions: it is an attentive
> practice whose categories also rank objects publicly.

This synthesis makes it possible to discuss genuine sensory engagement without
abandoning the social consequences of expert classification.

### 3.4 Karpik And Smith Maguire: Judgment Devices And Discernment Media

Whiskies are singular goods: bottle identity, age, distillery, cask history,
release, and maturation make quality difficult to evaluate through ordinary
comparison. Karpik provides the concept of a judgment device for the
institutions that make such objects comparable. Whiskyfun's recurring review
sequence - `Nose`, `Mouth`, `Finish`, `Comments`, classification code, and
score - organizes attention and culminates in a public ranking.

Smith Maguire's work on connoisseurial wine media provides the closest
substantive comparator. Specialist media do not only announce preferences;
they codify a logic of discernment by teaching why particulars matter. This
paper extends that insight by measuring recurrent distinctions in a
longitudinal whisky-review corpus.

**Bridge sentence:**

> The review form is not a neutral container for opinions. It is a judgment
> device that organizes the particularities through which a singular good can
> be described, compared, and valued.

### 3.5 Lamont, Molnar, And Douglas: Character Versus Contamination

Lamont and Molnar justify treating evaluative distinctions as symbolic
boundaries. Douglas provides a particularly useful interpretation of defect:
contamination is not merely a detectable quality but a judgment that something
is out of place. In whisky criticism, terms associated with rubber, solvent,
soap, or metallic character mark sensory features as violations of legitimate
character rather than simply as intensities.

This framework does not deny material sensations. It asks how such sensations
are interpreted as character, excessive intervention, or defect.

**Boundary proposition:**

> Expert whisky criticism organizes legitimate character partly through a
> durable opposition to artificial or contaminating defect, rather than
> through positive praise alone.

## 4. From Sensation To Value

The revised article may use the following process model:

```text
sensory encounter -> trained attention -> descriptive classification
                  -> boundary judgment -> public comparison and score
```

1. **Sensory encounter:** The critic engages with a bottle through smell,
   taste, texture, and finish.
2. **Trained attention:** Review conventions and acquired vocabulary indicate
   which differences deserve notice.
3. **Descriptive classification:** Sensations become publicly shareable
   descriptors such as peat, wax, sherry, mineral, rubber, or balance.
4. **Boundary judgment:** Descriptors and their contexts place qualities as
   valued character, excess, artificial intervention, or defect.
5. **Public comparison:** Structured prose and a score make a singular bottle
   comparable with other bottles.

Avoid speculative chemical explanations and fixed connotations for individual
terms. The claim concerns patterned classificatory use across a corpus, with
close readings used to show how context changes meaning.

## 5. Research Questions And Measurement Expectations

### Primary Question

> How can interpretable computational measurement identify the cultural
> classifications through which expert whisky criticism organizes sensory
> value?

### Supporting Questions

1. Does a human-adjudicated domain instrument recover held-out evaluative
   information beyond generic sentiment, while remaining distinguishable from
   a broad predictive lexical benchmark?
2. Do instrument categories correspond to independently specified whisky-style
   cues and to the structured locations where expert assessment occurs?
3. Is a theoretically proposed character/defect boundary recoverable robustly
   in corpus-trained semantic space?

### Measurement Expectations

**E1. Specialized vocabulary is measurable as interpretable discernment.**
If expertise is organized through learned classifications, a domain-specific
instrument should recover held-out evaluative information beyond generic
sentiment, without being expected to beat unrestricted text features.

**E2. Description is already evaluation.**
If the review format is a judgment device, sensory sections should contain
evaluative information even before explicit concluding commentary.

**E3. Legitimate character is defined against artificial defect.**
If expert judgment works through symbolic boundaries, flaw vocabulary should
align negatively with score and occupy a stable artificial/contaminating
semantic pole.

## 6. Corrected Evidence Map

Only regenerated scripted results should be carried into a manuscript rewrite.

| Corrected output | Theoretical use | Permitted interpretation |
| --- | --- | --- |
| Corpus contains 11,149 reviews; 8,492 are name-matched and 2,657 are index-matched | Defines the institution-specific evidentiary base and its identity limitation | A substantial longitudinal case corpus with transparent matching uncertainty |
| QA reports zero detected numerical score markers in primary modeling text after cleaning | Supports validity of text-score comparisons | Associations are not mechanically generated by retained numerical scoring expressions |
| Dictionary out-of-fold `R2 = 0.287`; VADER out-of-fold `R2 = 0.160` | Supports E1 | Specialized distinctions carry evaluative information beyond generic sentiment |
| TF-IDF/Ridge out-of-fold `R2 = 0.590` | Bounds the dictionary contribution | The interpretable taxonomy is substantively useful but does not exhaust the discourse |
| Nose-Mouth-Finish adjusted `R2 = 0.335`; Comments adjusted `R2 = 0.022` on a common complete-case sample | Supports E2 | Evaluation is embedded in structured sensory description |
| Flaw frequency `b = -0.332`, HC1 `SE = 0.024` per 1,000 tokens | Supports E3 | Defect classification is especially consequential within observed evaluation |
| Islay-assigned/peat `d = 1.406`; sherry-title/sherry `d = 1.247` | Independent instrument validation | Some categories track independently identified style cues |
| Bourbon-title/oak `d = 0.030` | Necessary weak/null validation finding | Not every material or title cue is translated into the expected vocabulary |
| Natural/Artificial is widest in 30/30 embedding specifications and flaw remains artificial-facing in 30/30 | Supports E3 | Character versus artificial defect is a robust recovered boundary in this corpus |

Do not describe cross-validated performance as proof of legitimacy or use
score-defined group contrasts as independent validation. High- and low-score
comparisons are criterion associations only.

## 7. Computational Sociology Contribution

> If expert criticism organizes value through discernment, its classifications
> should be recoverable through a transparent measurement workflow: theory
> defines categories and boundaries; manual adjudication disciplines the
> vocabulary; independent metadata tests construct validity; held-out
> comparisons distinguish interpretable measurement from generic sentiment and
> unrestricted prediction; and robust semantic-space tests assess boundary
> structure. These analyses do not establish audience uptake or causal market
> value. They demonstrate how computational sociology can measure the
> classificatory language through which one critical institution renders
> sensory value publicly legible.

The manuscript should explicitly state three contributions for Poetics:

1. **Substantive contribution:** evidence that expert whisky valuation is
   organized in part by a stable semantic opposition between legitimate
   character and artificial defect, consistent with cultural-field theories
   of legitimate versus illegitimate production and Douglas's purity
   framework.
2. **Measurement contribution:** a documented procedure for constructing an
   interpretable domain instrument with ambiguity review and sensitivity
   analyses, demonstrating that sociologically meaningful categories occupy
   a distinct analytical space between generic sentiment and opaque
   prediction.
3. **Methodological contribution:** a reproducible workflow combining leakage
   auditing, out-of-fold comparison, independent metadata groups, and
   embedding stability — a transparent design for computational analysis of
   specialized evaluative discourse.

## 8. Manuscript Architecture For Poetics

1. **Introduction: How expert discourse organizes sensory value.** Open with
   the sociological problem — not the dataset, not the method. Motivate with
   Bourdieu on classification, Hennion on mediated attention, Douglas on
   purity/contamination. State the three contributions. Do not mention R²,
   VADER, TF-IDF, or any model name until the Research Design section.
2. **Theory: Discernment, valuation, and symbolic boundaries.** Present
   Bourdieu, Jarness, Hennion, Karpik/Smith Maguire, and Douglas as a
   cumulative chain of construct definitions, each ending with a measurement
   expectation (E1–E3) to be tested in the Results.
3. **Data and research design.** Describe Whiskyfun as a judgment device.
   Present the dictionary as theory-grounded measurement. Frame prediction
   benchmarks as validation tools in a dedicated subsection.
4. **Results (organized by research question).**
   - §4.1 Does expert taste operate through specialized classifications?
     (RQ1/E1)
   - §4.2 Is evaluation embedded in structured sensory description? (RQ2/E2)
   - §4.3 Is a character/defect boundary recoverable in semantic space?
     (RQ3/E3)
5. **Discussion.** Return to each theory: what it gained or lost from
   empirical testing. Contrast interpretable measurement with unrestricted
   prediction. State corpus-specific limits and extensions.
6. **Conclusion.** Expert taste is computationally observable through
   transparent measurement of its classificatory language.

## 9. Language Guardrails

### Use

- "discursive production of cultural value"
- "theory-guided computational measurement"
- "interpretable domain instrument"
- "construct validation"
- "prediction as a benchmark, not the explanation"
- "language of discernment"
- "mode of appreciation"
- "expert judgment institution"
- "evaluation embedded in sensory description"
- "legitimate character versus artificial defect"
- "this corpus" and "this reviewing practice"

### Avoid

| Do not write | Write instead |
| --- | --- |
| "The reviews cause value." | "The reviews make sensory value publicly legible through classification and comparison." |
| "This proves Bourdieu." | "This identifies the classificatory organization of one expert mode of appreciation." |
| "Whisky consumers display cultural capital." | "The corpus records an expert vocabulary associated with legitimate appreciation." |
| "The NLP model predicts cultural value." | "The measured vocabulary carries evaluative information in held-out reviews." |
| "The dictionary should outperform all text models." | "The dictionary trades exhaustive prediction for interpretable measurement of theoretically specified classifications." |
| "Defects are only social constructions." | "Material sensations become evaluatively consequential through culturally organized defect classifications." |
| "Bourbon maturation validates the oak measure." | "The expected bourbon-title/oak association is not supported in this corpus." |

## 10. Reading And Citation Agenda

This framework provides a direction, not a substitute for close reading or
computational-social-science positioning. Before submitting the manuscript:

1. Read *Distinction* closely for classification, aesthetic disposition,
   cultural competence, and passages relevant to food, drink, and everyday
   consumption. Record page-specific notes before making precise interpretive
   claims.
2. Read Jarness (2015) for the shift from objects consumed to modes of
   appropriation.
3. Read Smith Maguire (2018) for discernment and connoisseurial media in the
   closely related wine case.
4. Re-read Hennion (2007) for mediated tasting and attentive practice.
5. Use Karpik for judgment devices and Lamont and Molnar with Douglas for the
   narrowly evidenced boundary argument.
6. Treat Howland (2013) as a useful wine/distinction comparator only after
   identifying precisely which audience-level or democratization claims cannot
   be transferred to this corpus.
7. Read recent Poetics articles (2024–2026) that use computational methods,
   text analytics, or embeddings to assess editorial receptivity and identify
   how they frame sociological contributions alongside methods.

For every source added to the manuscript, update `paper/references.bib` and
`paper/source_log.md`. Do not import substantive claims from abstracts alone.

## 11. Core Sources For The Reframed Theory

| Citation key | Source | Planned role |
| --- | --- | --- |
| `bourdieu1984distinction` | Bourdieu. 1984. *Distinction*. | Classification, competence, legitimate appreciation |
| `jarness2015modes` | Jarness. 2015. "Modes of Consumption." *Poetics* 53: 65-79. | Shift from what is consumed to how it is appropriated |
| `hennion2007things` | Hennion. 2007. "Those Things That Hold Us Together." *Cultural Sociology* 1(1): 97-114. | Tasting as mediated attentive practice |
| `karpik2010valuing` | Karpik. 2010. *Valuing the Unique*. | Judgment devices for singular goods |
| `smithmaguire2018taste` | Smith Maguire. 2018. "The Taste for the Particular." *Journal of Consumer Culture* 18(1): 3-20. | Connoisseurial media and discernment |
| `lamont2002boundaries` | Lamont and Molnar. 2002. "The Study of Boundaries." *Annual Review of Sociology* 28: 167-195. | Symbolic boundaries |
| `douglas1966purity` | Douglas. 1966. *Purity and Danger*. | Character/contamination interpretation |
| `howland2013distinction` | Howland. 2013. "Distinction by Proxy." *Journal of Sociology* 49(2-3): 325-340. | Cautious comparative reading on wine and distinction |

## Closing Formulation

> This project makes expert taste computationally observable without reducing
> it to score prediction. A validated domain instrument and robust semantic
> analyses show how one critical discourse names the differences that deserve
> attention, distinguishes character from defect, and makes sensory value
> publicly comparable.
