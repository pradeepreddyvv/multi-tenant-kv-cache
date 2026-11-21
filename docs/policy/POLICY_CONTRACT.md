# CPU retained-KV allocation policy — candidate v1

Owner: Akshit
Reviewer: Jauwaad
Status: Proposed specification; implementation and live integration pending.

## Scope and objective

Allocate a fixed CPU retained-KV byte budget among registered tenants.
Do not change GPU active KV, model settings, or inference scheduling.

Research objective: compare aggregate and per-tenant TTFT, throughput,
failures, and eviction/refill overhead under identical workloads and
resource budgets. Report the maximum per-tenant median-TTFT ratio to
equal allocation as a harm measure.

An acceptable harm threshold must be agreed before live tuning.
No latency improvement or formal fairness guarantee is established.

Offline observation replay validates quota decisions and invariants.
It does not simulate cache contents or measure inference performance.

## Interface

policy(observations, budget_bytes, state) -> (quotas_by_tenant, next_state)

Each observation contains:
- tenant_id: nonempty string
- window_end_s: finite timestamp in seconds
- eligible_input_tokens: nonnegative integer count in this window
- retained_bytes: nonnegative integer current retained payload
- retrieved_tokens: nonnegative integer count in this window
- errors: nonnegative integer error count in this window

Counts are window values, not cumulative counters.
Eligible input tokens use the same definition across all policies.
Retrieved tokens must not exceed eligible input tokens.

State contains registered tenant IDs, previous quotas, smoothed demand,
last accepted observation timestamp, configuration, and decision reason.
Configuration includes the fixed unequal baseline weights.

All tenants in one invocation describe the same observation window.
The caller invokes the controller at window completion, every 5 seconds.
This pure function has no clock, sleeps, I/O, model imports, or mutation
of its input arguments.

## Baselines

1. Equal:
   Divide the complete byte budget equally among registered tenants.
   Resolve integer remainders in lexicographic tenant-ID order.

2. Fixed unequal:
   Allocate by nonnegative declared initial-demand weights.
   Freeze weights before replay; do not use future observations.
   If every initial weight is zero, use equal allocation.
   Use largest-remainder rounding, breaking ties by tenant ID.
   Do not apply the adaptive floor to this baseline; disclose this choice.

3. Adaptive:
   Initialize quotas equally and smoothed demand to zero.
   On each valid window, update demand:
       d_i = 0.5 * eligible_input_tokens_i + 0.5 * previous_d_i

   Reserve floor(0.20 * budget_bytes) as the equal floor pool.
   Divide that pool equally with deterministic integer remainders.
   Allocate remaining bytes proportionally to smoothed demand using
   largest-remainder rounding with tenant-ID tie breaking.
   If all smoothed demand is zero, use the equal target.

   Let transfer_needed = sum(max(target_i - previous_quota_i, 0)).
   Hold quotas when transfer_needed is zero or below 5% of the budget.
   Otherwise move at most floor(0.10 * budget_bytes) bytes in total
   from donors to receivers, approaching the target.

   Order donors and receivers by descending surplus/deficit, then ID.
   A transferred byte counts once, not once at each endpoint.
   Do not independently round increases and decreases.
   If the integer transfer cap is zero, hold and report that reason.

## Invalid data and membership

Reject invalid configuration, negative budgets, duplicate tenant IDs,
and impossible configured minimum allocations with explicit exceptions.

With established state, missing fields, missing registered tenants,
nonfinite timestamps, repeated/out-of-order windows, unequal window
timestamps, gaps over 10 seconds, or nonzero errors hold the last valid
allocation and demand state. Return an explicit diagnostic reason.
Do not advance the last accepted timestamp on a rejected window.

Absolute telemetry age is the caller's responsibility: the caller must
not submit an old window as a fresh controller invocation.

Registered membership and budget are fixed within a replay episode.
A new tenant causes an explicit membership-change failure; it is not
silently ignored. The caller must register the new membership and begin
a new episode with an equal initialization. Record the reset.
A budget change similarly requires a new episode.
These resets are not ordinary capped transfers.

## Invariants

- Tenant quotas are nonnegative integer byte counts.
- Every registered tenant has exactly one quota.
- Quotas sum to budget_bytes.
- Adaptive quotas respect the integer minimum allocations.
- Each ordinary adaptive update transfers at most the configured cap.
- Identical inputs and state produce identical outputs.
- Invalid telemetry preserves the last valid allocation.
- Inputs and previous state are not mutated.

## Offline validation

Test 4, 8, and 16 tenants, equal/skewed/shifted demand, idle tenants,
zero demand, small budgets, remainder ties, invalid observations,
membership changes, impossible floors, and long repeated sequences.

Run all three policies against identical synthetic observations.
Save quotas, decisions, configuration, fixture identity, and invariant
checks under ignored runs/. Never overwrite previous evidence.

These trajectories demonstrate controller behavior only. They do not
establish cache hit rates, TTFT gains, throughput gains, or service fairness.

## Integration boundary and deferred work

The adapter, owned by Pradeep, applies byte targets and returns an update
ID, applied timestamp, and accepted/deferred/error status.
Requested quotas are not proof of actual retained-byte enforcement.
Live integration must distinguish requested, accepted, and occupied bytes.

The 30-second cooldown and eviction/restoration cost check in the original
proposal are deferred variants, not features of this candidate.
Demand may reward low-reuse traffic; evaluate that limitation.

All numeric policy parameters are starting hypotheses, not tuned optima.
