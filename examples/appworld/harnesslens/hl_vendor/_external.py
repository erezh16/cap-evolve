"""Stand-ins for HarnessLens names on code paths the AppWorld port never takes (see VENDORED.md).

``OpencodeHarnessAdapter`` is used by analyzer._validate_candidate only when harness == "opencode" and the
candidate carries a ``manifest_delta``. The port passes harness="appworld" and Analyzer candidates are editor
briefs without a manifest_delta (the prompts forbid it), so reaching it is a bug.
"""


class OpencodeHarnessAdapter:  # pragma: no cover
    def __init__(self, *a, **k):
        raise RuntimeError("OpencodeHarnessAdapter is not available in the AppWorld port")
