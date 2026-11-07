# Fixing the research-agent connection

An OpenAI key is optional. Whisper-small runs locally; the research coding agent uses the configured remote provider through the existing Chat Completions adapter.

The four recorded attempts failed before authentication. The separate preflight confirms credentials are present, but DNS lookup fails in the restricted tool shell. This does not establish that the keys, endpoint, model ID, or request format will work once networking is available.

First run this in an ordinary Mac Terminal:

```sh
cd /Users/jameshennessy/src/cv_whsipr_hack
.venv/bin/python scripts/check_research_api.py
```

Or start the UI with `.venv/bin/python scripts/whisper_ui.py`, open http://127.0.0.1:8787/research, and click **Test agent API**. Restart a server that predates the new button/backend. This preflight does not consume an episode or modify a comparison. Credentials remain on the server.

| Result | Next action |
| --- | --- |
| `ready: true` | Use that provider. Create a new comparison; retain the failed attempts. |
| `failure_stage: dns` | Check the configured hostname and whether it resolves outside the restricted shell. If it also fails there, check the URL, VPN/proxy and local DNS. Changing keys does not fix name resolution. |
| `credentials_missing` | Set a provider-specific key in the local `.env` or server environment. |
| HTTP 401 / 403 | Check the provider-specific key and account/model permissions. |
| HTTP 400 / 404 / 422 | Check the endpoint, model ID and compatibility with the adapter's JSON Chat Completions parameters. |
| HTTP 429 | Check the provider's quota, billing and rate limits. |
| Other transport error | Check TLS, proxy/firewall or provider availability. |

The existing adapter reads `NEURAL_PR_BASE_URL`, `NEURAL_PR_MODEL` and `NEURAL_PR_API_KEY`. With its original provider it can also read `MODEL_API_KEY`; the Gemini configuration can read `GEMINI_API_KEY`. An environment variable takes precedence over `.env`, so restart the UI after changing its environment. Do not paste keys into chat or store them in experiment artifacts.

The research UI and preflight now default to [Muse Wonder](MUSE_WONDER.md) through `ui/agent_profile.json`. That research-only model/endpoint preference overrides the legacy `.env` model setting; explicit shell environment settings still win. The original coding CLI continues to use its frozen configuration. Switching the research provider requires a new comparison root.

To use OpenAI instead, configure `NEURAL_PR_BASE_URL=https://api.openai.com/v1`, a model available to your API project that supports the existing Chat Completions request parameters, and your OpenAI key as `NEURAL_PR_API_KEY`. Authentication and the endpoint are documented in the [official API reference](https://developers.openai.com/api/reference/overview) and [Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create). Compatibility and account access still require a successful preflight; this project does not silently migrate model-specific parameters.

A provider/model change is a new comparison condition: freeze it once and use it for both procedures. Do not mix the previous failed provider attempts with new-model completed attempts as balanced pairs. See [fresh comparison commands and remaining evaluation gaps](RESEARCH_EVAL_RESULTS.md).
