# Controlled starter: durable job runner

This is an explicitly authored, deliberately incomplete hackathon fixture, not a discovered production defect.
Implement these requirements together across Store, API, worker.tick and Client. Preserve the public signatures.
Use SQLite transactions and durable state. No claim of exactly-once external effects.

## Frozen observable contract v1

POST /jobs: X-Tenant and Idempotency-Key required and nonempty; JSON {payload: object, max_attempts: 1..10 default 3}.
Success returns HTTP 200 and persisted job including id,tenant,key,payload,max_attempts,state,attempts,token,lease_until,result.
Same tenant/key + semantically equal JSON payload and same max_attempts returns the original job, including after restart.
JSON object key order is irrelevant. Different tenants' keys are independent. A conflicting payload OR max_attempts returns
HTTP 409 {"detail":"idempotency_conflict"}; Client raises httpx.HTTPStatusError preserving this response.
Concurrent identical submissions create one row. Use database-enforced tenant/key uniqueness.
GET /jobs/{id}: own job 200; absent or other tenant 404 {"detail":"job_not_found"}. Health remains {"status":"ok"}.
Invalid inputs return 422. Client must propagate errors, including 404/409.

States: queued -> running on claim; running -> succeeded on current, unexpired token completion;
running -> queued on current unexpired failure if attempts < max_attempts, otherwise failed.
Attempts count claims, not retries; max_attempts=3 allows at most three executions total.
claim increments attempts and assigns a fresh opaque token and lease_until=now+lease_seconds atomically.
A job can only be claimed if queued and attempts < max_attempts. No concurrent double claim.
recover(now): running rows with lease_until <= now become queued if attempts < max_attempts, otherwise failed;
clear token and lease. Return number transitioned. Durable across Store/process restart. Recovery is called by tick.
finish(id,token,now,result,error): return True only when a running row's token matches AND lease_until > now.
Expired/stale completion or failure returns False and changes nothing. Success JSON-encodes result, including false/0/null;
failure records error text in result. Both clear token and lease. Error presence is `error is not None`, even empty text.
Cancellation: queued/running -> cancelled, clear token and lease; terminal succeeded/failed/cancelled are unchanged.
POST /jobs/{id}/cancel uses tenant isolation and 404 contract; repeat cancellation is idempotent.
Cancelled rows cannot be recovered, claimed or completed. Late completion cannot undo cancellation.

## Dependency ordered milestones

1. smoke: existing health, create/read, isolation and client errors remain valid.
2. idempotency: durable tenant/key uniqueness, conflict contract, concurrent submissions, API/client behavior.
3. execution: bounded retries, atomic claims, fresh tokens and current lease checks.
4. recovery: expired recovery after restart, exhausted recovery and stale fencing.
5. cancellation: terminal protection, tenant isolation, late completion protection, integrated worker flow.

Development checks belong to the agent; the controller independently verifies these milestones.
