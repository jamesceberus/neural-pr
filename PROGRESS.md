# Neural PR progress

Started 2026-11-07 (America/Los_Angeles). Seven-hour maximum; finish early when complete.

- Inspected workspace: empty; no existing work to preserve.
- Python/Git available. Docker/Podman absent. macOS sandbox-exec installed but sandbox_apply denied by host.
- No model credential environment variables. Requested local setup; no secrets printed.
- Network package installation failed (DNS restricted). Bootstrapped Python 3.12 environment using already-installed FastAPI/httpx/uvicorn packages from a local environment, without modifying that environment.
- Verified Meta's official quickstart: https://api.meta.ai/v1, muse-spark-1.3, MODEL_API_KEY. Endpoint and model remain configurable.
- Building a controlled starter and controller; live coding evidence must come from runtime API calls. No claim of self-improvement from implementation edits or controls.

## Final execution — 2026-11-07T19:21:59.354472+00:00

- Elapsed 28.3 minutes. Completed controller, model adapter, policy store, proposer, paired evaluator, recovery/rollback, read-only dashboard, documentation and exact commands.
- Final tests: 41 total, 40 passed, 1 Docker integration test skipped. Full log: .neural-pr/verification/unittest.txt.
- Main verifier additionally checks API/client cancellation, JSON ordering, false/null results, bounded retry semantics and lease recovery across two separate OS processes. Test-only reference passes; actual controlled starter remains unfinished.
- Ran real init, one attempted episode, separate-process resume, actual application rollback with diagnostic preservation/fixture cleanup, labeled rejection controls and audit preflight.
- Actual result: two API transport failures; one deduplicated incident with two occurrences; no model proposal or live comparison; no promotions/rejections/policy rollbacks. One actual application rollback.
- Audit inconclusive (API DNS unavailable); all A/B/audit blocks untouched. Incumbent retained: no_validated_improvement.
- Root Git initialization denied; controlled application Git works. Unrelated Whisper audio artifacts left untouched.
- Host denies API DNS, local port binding, and sandbox_apply; Docker absent. Local evaluation integrity remains unenforced and cannot authorize promotion.
- Supplied keys exist only in ignored .env (0600); scan found no copies outside it. No keys in public documentation, logs, dashboard or records.
- Recorded dashboard: .neural-pr/dashboard-recorded.html. Live route verification used in-process HTTP; no browser QA claim.
- Earlier implementation rehearsals archived before final frozen-controller execution; unsuccessful evidence preserved.
- Complete honest outcomes: docs/RESULTS.md. Three-minute presentation: docs/DEMO_SCRIPT.md. Next experiment: one real Meta candidate on fresh block A under Docker, then once-only audit.

## Whisper experiment — 2026-11-07T19:48:31.372133+00:00

- Followed the new audio instructions separately from Neural PR's coding-policy gate. Original brief reread; no old controller outcome overwritten.
- User selected multilingual small and prepared original openai-whisper in .audio-venv plus audio_models/small.pt from their unrestricted terminal. Tool-side package/weight requests failed before that preparation.
- Verified official pristine checkpoint SHA-256. Actual runtime: openai-whisper 20250625, PyTorch 2.15.0, CPU float32, English, temperature 0, beam 1, fixed thresholds and four threads.
- Verified ZIP/manifest/audio hashes for all 29 development clips. Reproduced two lexical failure behaviors among the five reported cases; one is verified all-zero PCM producing 'you you you'. One additional case produces repeated punctuation. Full raw outputs retained.
- Development baseline: 9/17 supplied-label NS lexical outputs (original weak labels), speech WER 13/264 = 4.9242%, zero empty speech/errors. All 12 genuine-speech controls included in every repair evaluation.
- known_failures.jsonl: 16 local records with original manifest links and label provenance (9 lexical NS, 6 speech mismatches, 1 punctuation diagnostic). One silence case has additional exact-zero signal verification.
- Ranked head-scale gradients from development evidence only. Evaluated eight saved/exported/independently reloaded static head edits on all 29 clips. None reduced NS lexical count. No search budget extension.
- For the requested final comparison, froze the best nonregressing exploratory candidate: decoder layer 2/head 5 cross-attention output columns scaled 0.75. Its failed development gate is explicit; baseline remained approved. The selection-only controller change was archived and audited: no gate, score, decoder, or other method changed.
- Moved already-extracted holdout outside the workspace before this audio experiment; no manifest/audio inspection until freeze. OS-enforced secrecy is unavailable and this limitation is explicit. Original holdout ZIP/audio hashes verified only after freeze.
- Complete held-out evaluation: 40/40 recordings for each artifact. Both produce lexical output on 9/20 annotated NS clips; speech WER 5/337 = 1.4837%; zero new empty transcripts; zero errors. Candidate fails the original strict gate. No tuning after audit.
- Final audio decision: no_validated_whisper_weight_improvement; retain untouched small.pt. All eight unsuccessful weight artifacts and evidence preserved.
- Actual transcriptions: 341; measured inference time 278.14s plus 9.46s gradient ranking, hashes/export and setup overhead separately. Five reproduction outputs reused in baseline rather than rerun.
- Audio-only tests: 12 passed. Final integrity checks verify hashes, complete sets, freeze-before-access ordering and post-holdout edit/reselection refusal.
- Separate reports: docs/AUDIO_RESULTS.md and docs/AGENT_POLICY_RESULTS.md. Coding-policy outcome unchanged: no_validated_improvement, zero paired live coding rollouts; audio results are not policy evidence.

## Mechanistic addendum, bounded direction follow-up, and UI

- Saved the complete supplied specification at docs/mechanistic_interpretability.md and linked it from README. Existing model loader, lexical/WER scorer, export primitive, checkpoint Git helper, durable State journal, model adapter and dashboard were reused. Original coding-policy gate source and active version remain unchanged.
- New self-attention investigation uses original Whisper-small, uncached decoder forwards, exact production-derived prefixes/target/SOT indices, captured real windows, detached head outputs, source-grouped prospective development confirmation and five matched same-layer controls. All cases were previously used in the cross-attention study; the original final audio holdout was not reopened.
- Real-model identity, rollback, alignment, scale-one and hook/permanent-column-equivalence checks passed. Fresh process attested the edited file hash and projection hash and reproduced smoke transcripts with no hooks. Targeted 49,152 weights; actually changed 49,151 (one original value was zero). Bias and unrelated tensors preserved.
- Bounded first investigation: 24 coarse heads, three refined heads, 480 recorded diagnostic trials, 203 full application recordings. Chosen L4/H4 scale 0 increased former-confirmation unsupported-token log probability by 0.028354 nats and worsened non-speech lexical outputs from 9/17 to 10/17. Five matched controls stayed at 9/17. Speech WER improved 13/264 to 10/264; no new empty speech or errors. Implementation passed; narrow causal token-score contribution observed; proposed role unsupported; repair rejected.
- Runtime investigator attempted the existing Meta adapter twice; both transports were unavailable. Structured capability/validation tests passed, but real runtime next-proposal execution remains unverified. Actual run labeled engineering sweep. Independent coding-policy outcome remains no_validated_improvement. Activation interchange left unrun because no documented suitable matched donor pair was established.
- Preserved initial tracing-closure failure and source snapshot. Fixed before measurements; instrumented baseline matches all 29 original transcripts exactly.
- User-requested protocol v2 explicitly adds .9/1.1/1.25 strengths without changing legacy defaults or repair gate. Same exact 20 inputs and five control heads; no fresh confirmation claim. 600 diagnostics plus all 29 development recordings for each of three new selected-head settings and five controls at 1.1. Original attenuation diagnostic effect reproduced exactly. All old selected/control paired transitions inspected.
- Follow-up completed in 412.09 seconds including one infrastructure recovery, within the original 900-second deadline. The coding worker's 2 MB regular-file cap stopped the trusted research journal. Partial tail, old source/logs and full records were preserved. Only the supervisor/source-recovery guard changed, numerical code was verified AST-identical, completed records reused, and deadline/inputs/gate unchanged.
- Follow-up outcome: .9, 1.1 and 1.25 each retain 9/17 non-speech lexical outputs, no new empty genuine speech/errors. Bidirectional diagnostic prediction holds on only 4/7 reused NS cases. No amplification repair qualifies; stop this head under this hypothesis and retain pristine small. Reports: docs/MECHANISTIC_RESULTS.md and docs/HEAD_STRENGTH_FOLLOWUP.md.
- Verification: pre-UI core/project suite 58 tests run: 55 passed and three skipped for unavailable optional environments; 22 real-audio/boundary tests passed in .audio-venv. Frozen policy/controller/model identities remain valid.
- Built an interactive local Whisper UI: model/runtime preparation, official-hash verification, hypothesis and layer/head/scale controls, real local diagnostic jobs, full 29-clip checks, progress/cancellation, persistent history, audio/transcript comparisons, matched controls, provenance and four independent statuses.
- Five UI HTTP tests passed, including actual Whisper diagnostic and full-development inference and cancellation safety; three additional final boundary checks passed. Three real UI demonstration jobs are saved (setup, diagnostic and full development). Native localhost binding is denied in this executor; launch scripts/whisper_ui.py from the user's Terminal. In-process HTTP testing passed; no browser visual QA claim.
- Read-only offline UI recording: audio_runs/ui/whisper-lab-recorded.html. Live UI instructions: docs/WHISPER_UI.md. Checkpoints and histories remain separate from agent policy; no UI action promotes either one or reopens the consumed holdout.
