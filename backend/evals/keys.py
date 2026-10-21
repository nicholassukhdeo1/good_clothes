# keys.py - resolving the API keys an eval needs.
#
# Through config.py, never os.environ directly. config is the only module that
# calls load_dotenv(), so a key sitting in backend/.env does not exist in
# os.environ until something imports config - and an eval runner that checks the
# raw environment first will report the key as missing while the file is open in
# the next editor tab. Both runners shipped with exactly that bug.
#
# This also keeps CI working unchanged: load_dotenv() does not overwrite a real
# environment variable, so a key supplied by the runner reaches config too.

import config


def missing(*names: str) -> list:
    """Which of `names` config could not resolve, in the order given."""
    return [n for n in names if not getattr(config, n, "")]
