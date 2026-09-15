# Draft: Section 7 Discussion, third draft (2026-09-15), revised to the blueprint. No em-dashes.

**What the heterogeneity says.** Gentoo's thesis is that a generator which
encodes the target's structure needs little help from the fuzzer that runs
it (Vikram and Padhye 2026). Seen from below, with a cheap model that never
reads the parser, the same thesis appears at synthesis time: the grammar,
plus whatever the model knows about the format, fixes most of the
generator's reach at the first attempt, and five rounds of any signal move
it by one or two points. The pre-registration listed four possible
outcomes and this is the fourth, a result that differs by target. The same
signals, in the same loop, with the same model, produced a detectable gain
on one held-out parser (parson, under measured coverage), a gain against
the proxy but not against no steering on a second (cJSON), nothing on the
third (tomlc99), and nothing attributable to any signal on the development
target. That reading has a
sharp limit on tomlc99, where a mechanical expansion of the same grammar
beat every LLM condition at the seed and after refinement, so the first
attempt is most of the result only where the model's first attempt is
good.

Three readings are consistent with the heterogeneity, and the study
separates them only partly. The first is headroom. The seed already
reaches 60 to 70% of reachable branches, and the branches left may need
inputs a grammar-derived generator does not naturally produce. parson has
the most reachable functions of the four targets (40 of 144) and is the
one where the oracle found something to do; tomlc99's remaining branches
are error paths a TOML grammar does not describe. The second is
the author: the model failed a guard in 44 of 180 first drafts, and on
tomlc99 its seeds lose to a mechanical generator, so on that target there
may be nothing for a signal to improve. The third is the signal's form:
the scalar helped on parson and the named-function variant did not, which
suggests the model can act on "do better" with a number attached but not
on "cover function X" when X is a name whose body it has never seen. A
second model tests the second reading, a larger budget the first, and a
C3n variant that shows the function's source the third; the last is the
natural next condition.

**The proxy is not vindicated and not condemned.** It cannot be
distinguished from no steering on any target, so it does not earn its
place. But it is also not the reason refinement fails: on tomlc99 the
oracle does no better, and on parson the oracle's gain is one to two
points, so the ceiling the proxy was meant to approximate is itself low.
Section 5.5 measured how well it tracks that ceiling: moderately across
generators, barely within a run's own iterations, which is where the loop
uses it. What the proxy arm did have, uniquely, was the empty
ExceptionGroup repair message and the collapses that went with it, and
Section 6 shows both to be properties of the repair path rather than of
the signal.

**Repair policy as the actionable finding.** Every agentic loop that lets a
model fix its own code has a repair path, and ours shows a clean,
replicated failure of the "here is your code, change one thing" pattern:
the model anchors on its own output and resubmits it, and an explicit
error message does not break the anchor. Re-seeding with the failure text
does, and a loop that always re-seeds produced no unusable generator on
two targets. This is exploratory in the registered sense and the
collapse-count difference is not established at ten replicates per cell,
but the three-path table is over 80 replicates, it replicates under the
oracle arms, and its direction is not subtle. For loop design the
implication is an ordering: fix the repair path, then the first draft,
then ask whether a signal is worth its instrumentation.

**The development target.** Designing the proxy on a parser whose default
build crashes on every object was a mistake with a benefit. The mistake:
on that target no steering signal ever acted, so its rows in the family
test nothing about signals, and a reader who skipped Section 5.1 would
misread its C3n row as "naming functions is harmful". The benefit: it is a
clean demonstration that a loop's event priority, crash before signal, can
silently turn every condition into one condition, which is the kind of
confound a single-run evaluation never reveals and a replicated one does.
The pre-registration's decision to report the development target
separately is what kept it from contaminating the held-out claims, and the
same rule, one event priority above the signal, exists in every loop that
treats a crash as its objective.

**What would change the conclusion.** A practical effect that this design
missed would need to be below about A12 0.8 (Section 5.9). A second model
family, a larger budget, a C3n that shows function bodies, and parsers with
more unreached branches are the four cheapest ways to look for it. The
second model's runs were under way when this submission was frozen
(Section 4.6), and it and the remaining Stage 2 parser are pre-specified
for the revision.
