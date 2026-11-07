# Whisper lab UI

Run from your Mac's Terminal:

```sh
cd /Users/jameshennessy/src/cv_whsipr_hack
.venv/bin/python scripts/whisper_ui.py
```

Open **http://127.0.0.1:8787**. Keep the Terminal window open. If the server was already running while the UI was being built, stop it with Ctrl-C and run the command again. You can also double-click `scripts/start_whisper_ui.command` in Finder.

## What you can do

- **Prepare model & runtime:** prepares the project-local audio environment and downloads the official multilingual small checkpoint if missing. Existing verified weights are retained. The current workspace is already prepared.
- **Verify model & runtime:** checks the official checkpoint hash, installed Whisper/PyTorch versions, and development recordings.
- **Run diagnostic:** enter a testable hypothesis, select a decoder layer/head and protocol-v2 scale, choose a frozen development probe, and run a real local forward intervention. Results include target log-probability change, relative probability ratio, hook/edit agreement, and pristine restoration.
- **Run full development check:** evaluates all 29 full recordings, including all 12 genuine-speech controls. It reports non-speech lexical-output counts, speech WER, newly empty transcripts, inference errors, paired changes and the unchanged repair-gate result.
- **Inspect evidence:** switch between all reused probes, former discovery and former confirmation. Matched control heads use the same displayed subset. Listen to development audio, compare pristine/rejected transcripts, inspect provenance and open the separate reports.
- **Run history:** progress and results are persisted under `audio_runs/ui/jobs/`. One model job runs at a time. Stop cancels the process; cancellation cannot turn into a successful result.

Runs are exploratory and user-initiated. No UI action promotes a Whisper checkpoint, modifies the coding-agent policy, changes acceptance thresholds, or selects original holdout inputs. The original 40-recording audio holdout is consumed. Previously used confirmation inputs are development data for follow-up hypotheses.

## Results already loaded

The interface displays the actual original mechanistic study and the bounded head-strength follow-up. The follow-up tested scales 0, 0.9, 1, 1.1 and 1.25 on layer 4/head 4. Amplification did not reduce the 9/17 non-speech lexical-output count. The pristine checkpoint remains accepted. The separate coding-agent upgrade result remains unvalidated.

Three successful UI demonstration jobs are saved: setup verification, a real controlled diagnostic, and a full 29-recording development evaluation. They are explicitly implementation/UI demonstrations, not fresh confirmation.

## Verification and limitations

Five HTTP/UI tests passed, including actual Whisper inference, full development evaluation, input/permission boundaries and cancellation. Additional HTTP checks verified setup preparation in the already-prepared environment. The first-time download/install branch requires network access and was not re-downloaded during UI testing. Live and recorded JavaScript pass Node syntax checks.

This execution sandbox denies binding a localhost listener. The server was exercised through FastAPI's in-process HTTP client, including real background model jobs. Browser visual QA was unavailable; no browser screenshot is claimed. Launching the command in your unrestricted Terminal makes the live UI available to your browser.

A read-only, self-contained recording is available at `audio_runs/ui/whisper-lab-recorded.html`. It contains real results and playable development audio. Its experiment buttons are disabled and it is labeled **Recorded snapshot**. It cannot run Python jobs; use the live local server for that.

```sh
.venv/bin/python scripts/export_whisper_ui.py
.venv/bin/python -m unittest tests.test_whisper_ui -v
```
