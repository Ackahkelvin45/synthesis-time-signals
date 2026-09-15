# Draft: Section 7 Discussion, second draft (2026-09-14). No em-dashes.

**What the heterogeneity says.** The pre-registration listed four outcomes
and this is the fourth: the same three signals, in the same loop, with the
same model, produced a detectable gain on one held-out parser (parson,
under measured coverage), a gain against the proxy but not against no
steering on a second (cJSON), nothing on the third (tomlc99), and nothing
attributable to any signal on the development target, where the crash
rule made every steered arm the same loop. Three readings are consistent
with that and the study separates them only partly. (1) Headroom: the seed
already reaches 60 to 70% of reachable branches, and the branches left may
need inputs a grammar-derived generator does not naturally produce. parson
is the target with the most reachable functions (40 of 144) and the one
where the oracle found something to do; tomlc99's remaining branches are
error paths a TOML grammar does not describe. (2) Author: the cheap model
failed a guard in 44 of 180 seeds, and on tomlc99 its seeds lose to a
mechanical generator, so on that target there may be nothing for a signal
to improve. (3) The signal's form: the scalar helped on parson and the
named-function variant did not, which suggests the model can act on "do
better" with a number attached but not on "cover function X" when X is a
name it has never seen the body of. The second model, whose runs were
under way when this submission was frozen, tests (2); a larger-budget arm tests (1); a C3n variant that shows
the function's source would test (3), and is the natural next condition.

**The proxy is not vindicated and not condemned.** It cannot be
distinguished from no steering on any target, so it does not earn its
place. But it is also not the reason refinement fails: on tomlc99 the
oracle does no better, and on parson the oracle's gain is one to two
points, so the ceiling the proxy was meant to approximate is itself low.
Section 5.5 measures how well it tracks coverage: moderately across
generators (rho 0.4 on the held-out targets), barely within a run's own
iterations (median rho 0.0 to 0.35), which is where the loop uses it. What the proxy arm
did have, uniquely, was the ExceptionGroup repair message (13 events, all
its own) and the collapses that went with it; Section 6 shows both to be
properties of the repair path.

**The development target.** Designing the proxy on a parser whose default
build crashes on every object was a mistake with a benefit. The mistake:
on that target no steering signal ever acted, so its rows in the family
test nothing about signals, and a reader who skipped Section 5.1 would
misread its C3n row as "naming functions is harmful". The benefit: it is a
clean demonstration that a loop's event priority (crash before signal)
can silently turn every condition into one condition, which is the kind of
confound a single-run evaluation never reveals and a replicated one does.
The pre-registration's decision to report the development target
separately is what kept it from contaminating the held-out claims.

**What Gentoo's thesis looks like from below.** Gentoo found that a strong
white-box agent's generators do not need coverage guidance at fuzz time.
Our cheap blind author's generators do not benefit from a blind signal at
synthesis time, and benefit from measured coverage on one held-out target
in three, and against the proxy only on a second.
The common reading is that the grammar, plus whatever the model knows about
the format, fixes most of the generator's reach at the first attempt. That
reading has a sharp limit on tomlc99, where a mechanical generator from the
same grammar beat every LLM condition.

**Repair policy as the actionable finding.** Every agentic loop that lets a
model fix its own code has a repair path, and ours shows a clean,
replicated failure of the "here is your code, change one thing" pattern:
the model anchors on its own output and resubmits it, recovering 2 times in
25. Re-seeding with the failure text recovers 12 in 14, and a loop that
always re-seeds produced no unusable generator in 20 runs on two targets.
This is exploratory in the registered sense and the collapse-count
difference is not established at ten replicates per cell, but the two-path
table is over 80 replicates, it replicates under the oracle arms, and its
direction is not subtle.

**Cost.** A run costs about three cents and five minutes. On the three
held-out targets it buys at most two points of coverage, and only under
measured coverage on one of them. Twenty independent seeds cost less than
one Gentoo synthesis and, on tomlc99, would be better spent on the grammar
and the adaptation note than on any refinement.

**What would change the conclusion.** A practical effect that this design
missed would need to be below about A12 0.8 (Section 5.9). A second model
family, a larger budget, a C3n that shows function bodies, and parsers with
more unreached branches are the four cheapest ways to look for it; the
second model's runs were under way when this submission was frozen
(Section 4.6), and it and the remaining Stage 2 parser are pre-specified
for the revision.
