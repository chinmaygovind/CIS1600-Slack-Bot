"""Work out which homework problem an Ed post is about.

Tuned against 118 real CIS 1600 questions pulled from Ed. On that sample it
resolves both a homework and a problem number for ~49% of questions. Almost
all of the remainder genuinely are not about a specific problem (due dates,
regrade requests, Canvas issues, general concept questions), so returning
nothing for them is the correct behaviour rather than a miss.

Deliberate design choices, each of which fixed a real mis-match in the sample:

  * Ed's own `subcategory` is trusted first -- it is the assignment the student
    filed under and is far more reliable than the title. Students do miscategorise
    ("4T question 4" filed under General), so title/body regex is the fallback.
  * A part letter is only accepted when parenthesised or glued to the digit
    ("3(d)", "4b"). Allowing a loose trailing letter made "Q4 First turn" parse
    as 4f and "Q5 Clarification" as 5c, which would attach the wrong sub-problem.
  * A bare "3b"-style reference is honoured only in the title, and only with a
    part letter attached. A bare digit on its own is too weak a signal.
"""

import re

HW_CODES = {f"{n}{s}" for n in range(1, 16) for s in ("T", "H")}

_HW = re.compile(r"\b(\d{1,2})\s*([THth])\b")
_EXPLICIT = re.compile(
    r"\b(?:q|ques(?:tion)?s?|prob(?:lem)?s?)\s*\.?\s*(?:number|no\.?|#)?\s*#?\s*"
    r"(\d{1,2})(?:\s*\(([a-h])\)|\s*([a-h])\b)?",
    re.I,
)
_BARE = re.compile(
    r"(?:^|[\s(])(\d{1,2})\s*(?:\(([a-h])\)|([a-h]))(?=[\s:,.\-?)]|$)", re.I
)
_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"</paragraph>|<br[^>]*>")

# How much of the body to search. Problem references appear up front; scanning
# further mostly picks up incidental numbers from the student's own working.
BODY_WINDOW = 300


def strip_html(raw):
    """Ed post bodies are an XML-ish document; reduce to searchable plain text."""
    text = _BREAK.sub("\n", raw or "")
    return re.sub(r"\s+", " ", _TAG.sub(" ", text)).strip()


def _part(match):
    return (match.group(2) or match.group(3) or "").lower()


def find_homework(title, body, subcategory=None):
    sub = (subcategory or "").strip().upper()
    if sub in HW_CODES:
        return sub
    for match in _HW.finditer(f"{title} || {body[:BODY_WINDOW]}"):
        code = match.group(1) + match.group(2).upper()
        if code in HW_CODES:
            return code
    return None


def find_problem(title, body):
    for match in (_EXPLICIT.search(title), _EXPLICIT.search(body[:BODY_WINDOW])):
        if match:
            return match.group(1) + _part(match)
    for match in _BARE.finditer(title):
        # Skip things like "1T" that are the homework code, not a problem.
        if (match.group(1) + _part(match).upper()) in HW_CODES:
            continue
        return match.group(1) + _part(match)
    return None


def match(title, body_html, subcategory=None):
    """Return (homework, problem, part) -- any of which may be None.

    `problem` is the bare number as a string ("4"); `part` is the sub-part
    letter if one was given ("b"), which is used for display only since page
    lookup happens at problem granularity.
    """
    body = strip_html(body_html)
    homework = find_homework(title or "", body, subcategory)
    raw = find_problem(title or "", body)
    if raw is None:
        return homework, None, None
    number = re.match(r"(\d{1,2})([a-h]?)", raw)
    return homework, number.group(1), (number.group(2) or None)
