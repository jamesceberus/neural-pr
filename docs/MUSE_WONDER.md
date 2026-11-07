# Meta Muse Wonder research agent

For the requested failure-driven coding-policy experiment, use the [current execution launcher and infrastructure diagnosis](WONDER_LEARNING_EXECUTION.md). Its new versioned adapter replaces the tiny readiness probe for that experiment; the historical diagnostics below describe the earlier adapter.

The research UI now selects `muse-wonder-1.0` at `https://api.meta.ai/v1`. Meta documents [Muse Wonder](https://dev.meta.ai/docs/muse-wonder) on its [Chat Completions endpoint](https://dev.meta.ai/docs/protocols/chat-completions), which the existing agent adapter uses. This is the project's runtime research agent.

The non-secret preference is in `ui/agent_profile.json`. Credentials still come from the existing local `.env` or server environment. The legacy `.env`, accepted checkpoint and historical attempts are preserved. The original worker has since received a [direct implementation repair](ORIGINAL_WORKER_FIX.md); explicit shell model/endpoint/root settings still override the research profile.

A source-bound comparison is frozen in `research_runs/wonder-v2`, with Wonder assigned to both procedures. It currently has **zero research episodes**, and no fresh private audio registered. Earlier source versions remain in their original directories; coding-task results are reported separately.

Executed checks:

```sh
.venv/bin/python scripts/whisper_ui.py --prepare-only
.venv/bin/python scripts/whisper_ui.py --check-agent
.venv/bin/python scripts/wonder_research.py report
.venv/bin/python -m unittest tests.test_agent_profile tests.test_research_ui -v
```

The six profile/UI checks pass. The Wonder DNS preflight fails here; a separate request through the actual existing model adapter returns `Model API unavailable (URLError)`. Those diagnostics are saved in `research_runs/wonder-v1/api-preflight.json` and `transport-probe.json`. No successful authentication, Wonder response, or autonomous investigation is claimed.

From an ordinary Mac Terminal, start the configured UI:

```sh
cd /Users/jameshennessy/src/cv_whsipr_hack
.venv/bin/python scripts/whisper_ui.py
```

Open http://127.0.0.1:8787/research and click **Test agent API**. If it succeeds, use **Run episode** for the frozen Wonder attempts. Restart an older server to load this profile. A model mismatch against a frozen comparison is rejected.

For CLI use, `scripts/wonder_research.py` is a thin wrapper around the existing research CLI; it selects the same model/root before calling it. For example, `run-episode baseline --attempt 1` starts a real bounded episode when networking works. That live Wonder episode remains unrun here. Starting development work does not establish a fresh held-out comparison: register independent private material in a new task before freezing a future protected comparison.
