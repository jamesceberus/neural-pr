# GitHub repository

The source is prepared for a **private** repository, named `neural-pr` by default, under the account authenticated by GitHub CLI. No public publishing fallback is enabled.

From an ordinary Terminal:

```sh
cd /Users/jameshennessy/src/cv_whsipr_hack
.venv/bin/python scripts/publish_github.py
```

The publisher checks GitHub authentication, audits the source files, initializes this folder's Git metadata, commits the audited source, creates the private repository and pushes `main`. It returns the real repository URL after a successful push. If GitHub CLI needs authentication, run `gh auth login --hostname github.com` and retry. Use `--repo another-name` if `neural-pr` already belongs to another checkout. Existing remote URLs are never replaced, public repositories are refused, and no force push is used.

The restricted tool shell cannot reach GitHub and cannot create `.git` in this folder. A source-only checkout can still be prepared and committed under a writable temporary directory:

```sh
.venv/bin/python scripts/publish_github.py --prepare-only
```

That command prints the prepared checkout path, commit hash and audited file manifest. `prepared_not_pushed` does not claim that a GitHub repository exists.

Included source: coding controller, Whisper tools, research coordinator, UI, scripts, tests, documentation, synthetic CI checks and `docs/evidence/policy_upgrade_pilot.json`, a sanitized recorded-results summary.

Excluded local material: `.env` and credentials, virtual environments, checkpoints, audio packs, raw model traces, generated benchmark banks, experiment states, recorded dashboards and multi-gigabyte run directories. Raw evidence remains local; the sanitized summary is not a replacement for those artifacts. Audio experiments require separately supplied packs and a local checkpoint.

The repository contains trusted evaluator implementation and synthetic benchmark authoring code. Keep those outside runtime workers' mounts and contexts. The private repository is intended for trusted project collaborators; this publication does not expose graders to the coding worker.

For a clean source checkout, the CI command requires no API key, Whisper weights or audio recordings:

```sh
python -m pip install -e .
python -m unittest tests.test_action_protocol tests.test_controller \
  tests.test_evaluator_improver tests.test_transport tests.test_sandbox_worker \
  tests.test_policy_followup tests.test_wonder_learning tests.test_publish_github -v
```

Model-dependent UI/investigation tests and raw-result verification need the excluded local fixtures. No open-source license has been assigned by the publisher.
