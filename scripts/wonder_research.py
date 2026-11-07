"""Run the existing research CLI with the selected Meta Muse Wonder profile."""
from pathlib import Path
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ui.agent_config import configure
configure()
if '--root' not in sys.argv:
    sys.argv[1:1]=['--root',os.environ['WHISPER_RESEARCH_ROOT']]
from research_eval.__main__ import main
main()
