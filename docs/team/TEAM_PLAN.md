# Three-person collaboration plan

Team: Pradeep, Akshit and Jauwaad. Ownership below is **proposed work streams, not assignments already agreed or work already completed**. Choose one owner for each stream in the first team meeting, and record who implemented/reviewed each contribution.

## Suggested division

| Stream | Deliverables | Dependency / cross-review |
|---|---|---|
| A: serving and enforcement | Fresh clean-launcher smoke run; general tenant accounting; safe sustained primary-quota interface; shutdown/restart behavior | B reviews policy interface; C checks attribution and memory evidence |
| B: adaptive policy and baselines | Defined objective; fixed equal/manual policies; one interpretable feedback policy; budget/floor/oscillation checks | A supplies enforcement; C supplies controlled traces and metrics |
| C: workloads and evaluation | Repeatable contention/traffic-shift traces; per-tenant latency/reuse/bytes; repetitions, plots and result interpretation | A validates instrumentation; B checks comparison fairness |

Each person owns one substantive technical component, runs or analyzes at least one controlled experiment, and prepares the associated slide/evidence explanation. All three should understand the whole system; assigning one person only slide formatting will not prepare the group for Q&A.

## Agree on these interfaces first

- Tenant ID representation: use the verified GPU connector tag mechanism.
- Accounting unit: actual retained bytes; policy changes must conserve the total budget.
- Observation schema: tenant, timestamp/window, request volume, retrieved tokens, occupancy, evictions and errors.
- Update contract: tenant → quota bytes, application timestamp, accepted/deferred/error status.
- Workload contract: seed/trace, prompt/output lengths, reuse ratio, concurrency/arrival schedule, phase change.
- Result contract: commit/config/job provenance plus raw records, derived summaries and cleanup status.

These are design agreements to implement, not a claim that a general API already exists. Keep manual and adaptive policies on the same enforcement path.

## First meeting checklist

1. Everyone reads START_HERE and the GPU test sections; inspect at least one measured JSON file.
2. Confirm whether professor guidance has arrived and whether Option 1 is selected. No approval is recorded here.
3. Choose a primary optimization/fairness objective and the initial experiment scope.
4. Assign A/B/C owners and cross-reviewers; record actual availability.
5. Agree on accessible Sol storage/images and who may schedule which jobs; avoid accidental duplicate large runs.
6. Agree on repository access and feature-branch names. Do not share credentials.

## Git workflow

`main` remains the basic starter. `docs/team-handoff` is the shared reference branch. Documentation updates stay on that branch; implementation work should use separate feature branches and reviewed pull requests.

For a new implementation branch, after preserving any local edits:

```bash
git fetch origin
git switch -c feature/tenant-accounting origin/main
# Make a focused change, run relevant checks, and inspect the diff.
git add scripts/ tests/ docs/
git diff --cached
git commit -m "Describe the concrete change"
git push -u origin feature/tenant-accounting
```

Use similarly focused names such as `feature/adaptive-policy` or `feature/workload-metrics`. Before `git add`, inspect which files changed; do not stage another teammate's work accidentally. Open a pull request against main, have another person review, and agree who merges. Do not force-push shared branches or merge the handoff into main merely to obtain its documentation. Read it through its branch link.

A useful PR description includes the problem, behavior changed, test evidence, limits and whether a fresh GPU run was performed. A useful experiment update includes the question, exact config/commit, artifacts, observation, interpretation and next action. Do not report only “it ran.”

## Proposed schedule toward Phase 2

The user-supplied deadline is Nov 21, 2026 at 11:59 pm for one group slide PDF. Duration is still to be announced. This schedule is conditional on direction, compute authorization and team availability:

| Dates | Milestone |
|---|---|
| Nov 13–14 | Confirm scope; assign streams; fresh launcher smoke test; integrate manual accounting/enforcement and timing |
| Nov 15–16 | One adaptive policy and baseline runners; correct four-tenant pressure/shift run |
| Nov 17–18 | Main policy comparisons with repetitions; expand to 8/16 tenants and attempt integrated 128 GiB run |
| Nov 19 | Analyze findings, plot results and investigate failures/tradeoffs |
| Nov 20 | Assemble research-story slides; team walkthrough and rehearsal |
| Nov 21 | Validate figures/citations/PDF/readability; rehearse and submit before the deadline |

This is aggressive and is not a completion promise. If integration is unstable, prioritize a correct smaller-budget comparison over 256/512 GiB or CPU-only expansion. If adaptation cannot be completed, discuss narrower scope with the professor; do not silently present a mechanism diagnostic as completed adaptive research.

## Presentation readiness

The largest grading areas are technical ideas/design (9), experimental results (7) and analysis/insights (5): **21/40 points**. The feasibility work provides a foundation, but does not replace a concrete policy and a meaningful comparison.

Suggested story: problem → cache contention challenge → architecture → allocation mechanism/policy → controlled setup → results → explanation/tradeoffs → remaining Phase 3 work. Use an architecture figure and a few readable quantitative plots. Clearly separate existing frameworks from team code and measured observations from proposed ideas.

Before presenting, each person should be able to answer:

- What exactly is new, and what is supplied by vLLM/LMCache?
- Which evidence proves external reuse rather than native prefix caching?
- Why does the workload expose contention, and what is the cache-budget denominator?
- How do identity propagation and eviction safety work?
- How are baselines fair, and what does adaptation optimize?
- When does the policy fail or hurt a tenant, and what is its overhead?
- Which results are pilot observations, which are repeated comparisons, and what remains untested?
- What did you personally implement, test and review?
