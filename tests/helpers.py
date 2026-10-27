import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mindgap.config import Config  # noqa: E402


def tmp_cfg(**kw):
    d = tempfile.mkdtemp(prefix="mindgap-test-")
    return Config(archive_dir=d, notify=False, **kw), Path(d)
