from __future__ import annotations

import difflib


def _edits(base: list[str], changed: list[str]) -> list[tuple[int, int, list[str]]]:
    matcher = difflib.SequenceMatcher(a=base, b=changed, autojunk=False)
    return [
        (start, end, changed[replacement_start:replacement_end])
        for operation, start, end, replacement_start, replacement_end in matcher.get_opcodes()
        if operation != "equal"
    ]


def _overlap(
    first: tuple[int, int, list[str]], second: tuple[int, int, list[str]]
) -> bool:
    first_start, first_end, first_replacement = first
    second_start, second_end, second_replacement = second
    if first_start == first_end and second_start == second_end:
        return first_start == second_start and first_replacement != second_replacement
    if first_start == first_end:
        return second_start < first_start < second_end
    if second_start == second_end:
        return first_start < second_start < first_end
    return max(first_start, second_start) < min(first_end, second_end)


def merge_dashboard_text(base_text: str, user_text: str, latest_text: str) -> str:
    """Apply non-conflicting user line edits from a dashboard onto a newer template."""
    base = base_text.splitlines(keepends=True)
    user_edits = _edits(base, user_text.splitlines(keepends=True))
    latest_edits = _edits(base, latest_text.splitlines(keepends=True))

    for user_edit in user_edits:
        for latest_edit in latest_edits:
            identical = user_edit == latest_edit
            if not identical and _overlap(user_edit, latest_edit):
                raise ValueError(
                    "La fusion du dashboard a détecté des modifications incompatibles. "
                    "Aucun changement n’a été appliqué."
                )

    combined = list(latest_edits)
    combined.extend(edit for edit in user_edits if edit not in latest_edits)
    merged = list(base)
    for start, end, replacement in sorted(
        combined, key=lambda edit: (edit[0], edit[1]), reverse=True
    ):
        merged[start:end] = replacement
    return "".join(merged)
