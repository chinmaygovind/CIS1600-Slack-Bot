"""Keep a local, rendered copy of the homework PDFs from the Overleaf project.

The Overleaf project is a git remote. For each homework folder it holds a
single `.tex` carrying both the questions and the solutions, switched by an
etoolbox toggle:

    \\newtoggle{solutions}
    \\toggletrue{solutions}

so each homework is built twice -- once with the toggle off (questions only)
and once with it on (questions + solutions).

Finding which page a problem landed on is done by letting LaTeX report it.
Before building, `\\ques` is wrapped so that every problem writes a label, and
the resulting `.aux` then contains

    \\newlabel{cisq:4}{{4}{3}...}   ->  problem 4 is printed on page 3

The first field is the number the reader actually sees, so this stays correct
even if the enumerate numbering is ever changed. Parsing the rendered text for
"Problem N" headings would not survive a reformat; this does.
"""

import json
import os
import re
import shutil
import subprocess

from dotenv import load_dotenv

from utils import get_logger

load_dotenv()

PROJECT_ID = os.getenv("OVERLEAF_PROJECT_ID", "")
GIT_TOKEN = os.getenv("OVERLEAF_GIT_TOKEN", "")
CACHE_DIR = os.getenv("HW_CACHE_DIR", "cache/hw")
RENDER_DPI = int(os.getenv("HW_RENDER_DPI", "110"))
# Guard against a mis-parse dumping a whole homework into the thread.
MAX_PAGES_PER_ATTACHMENT = int(os.getenv("HW_MAX_PAGES", "4"))

REPO_DIR = os.path.join(CACHE_DIR, "overleaf")
BUILD_DIR = os.path.join(CACHE_DIR, "build")
OUT_DIR = os.path.join(CACHE_DIR, "out")

logger = get_logger("hw_pdfs")

# Wraps \ques so each problem records "printed number -> page" into the .aux.
# \makeatletter is needed because the helper names contain @.
# The wrapper deliberately takes NO argument and lets the original macro consume
# it. Taking #1 and re-inserting it makes TeX double any literal '#' in the
# question text (HW3H has "poster #1"), which is a fatal error.
_LABEL_INJECTION = r"""
\makeatletter
\newcounter{cisq}
\let\cis@origques\ques
\renewcommand{\ques}{\stepcounter{cisq}\label{cisq:\thecisq}\cis@origques}
\makeatother
"""

_TOGGLE_LINE = re.compile(
    r"^[ \t]*%*[ \t]*\\toggle(?:true|false)\{solutions\}[ \t]*$", re.M
)
_NEWLABEL = re.compile(r"\\newlabel\{cisq:(\d+)\}\{\{([^}]*)\}\{(\d+)\}")
_HW_DIR = re.compile(r"^HW(\d{1,2}[TH])$")


class BuildError(RuntimeError):
    pass


def _run(cmd, cwd=None, timeout=300):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )


def _redact(text):
    return re.sub(r"olp_[A-Za-z0-9]+", "olp_***", text or "")


def remote_url():
    if not PROJECT_ID or not GIT_TOKEN:
        raise BuildError(
            "OVERLEAF_PROJECT_ID and OVERLEAF_GIT_TOKEN must be set in .env"
        )
    return f"https://git:{GIT_TOKEN}@git.overleaf.com/{PROJECT_ID}"


def sync_repo():
    """Clone or fast-forward the Overleaf project. Returns True if it changed."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
        logger.info("Cloning Overleaf project")
        result = subprocess.run(
            ["git", "clone", remote_url(), REPO_DIR],
            capture_output=True, text=True, timeout=300, env=env,
        )
        if result.returncode != 0:
            raise BuildError(f"git clone failed: {_redact(result.stderr)[:400]}")
        return True

    before = _run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR).stdout.strip()
    result = subprocess.run(
        ["git", "pull", "--ff-only"], cwd=REPO_DIR,
        capture_output=True, text=True, timeout=300, env=env,
    )
    if result.returncode != 0:
        raise BuildError(f"git pull failed: {_redact(result.stderr)[:400]}")
    after = _run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR).stdout.strip()

    if before != after:
        logger.info(f"Overleaf project updated {before[:8]} -> {after[:8]}")
        return True
    return False


def available_homeworks():
    """{"4T": "/path/to/HW4T/HW4T.tex"} for every homework that has a main file."""
    found = {}
    if not os.path.isdir(REPO_DIR):
        return found
    for entry in sorted(os.listdir(REPO_DIR)):
        match = _HW_DIR.match(entry)
        if not match:
            continue
        tex = os.path.join(REPO_DIR, entry, f"{entry}.tex")
        if os.path.isfile(tex):
            found[match.group(1).upper()] = tex
    return found


def _prepare_source(source, with_solutions):
    """Force the solutions toggle and add the page-recording labels.

    The source sets the toggle itself a few lines after declaring it, so simply
    appending our own setting would be overridden. Every existing setting is
    neutralised first, and ours is placed immediately after \\newtoggle -- it has
    to land before the \\iftoggle block that defines \\sol.
    """
    text = _TOGGLE_LINE.sub("% [cis1600-bot] toggle overridden", source)
    setting = r"\toggletrue{solutions}" if with_solutions else r"\togglefalse{solutions}"
    text = text.replace(
        r"\newtoggle{solutions}", r"\newtoggle{solutions}" + "\n" + setting, 1
    )
    return text.replace(r"\begin{document}", _LABEL_INJECTION + r"\begin{document}", 1)


def _parse_aux(aux_path):
    """{problem number: page} from the labels LaTeX wrote.

    Each label records both the number the reader sees and the page. The
    printed number is preferred, but it can only be trusted when the homework
    numbers its problems through the enumerate counter. Several homeworks
    number them by hand (`\\item[\\bf 2.]`), which never steps that counter, so
    LaTeX writes either an empty number (HW10H) or -- worse, because it looks
    valid -- the previous problem's number repeated (HW9H writes 1,1,1,1,1,1).

    So the printed sequence is only used when it is strictly increasing across
    the document, which is what a real enumerate always produces. Otherwise the
    label's own index is used, the Nth \\ques being the Nth problem regardless.
    """
    if not os.path.isfile(aux_path):
        return {}
    with open(aux_path, encoding="utf-8", errors="replace") as handle:
        entries = [
            (int(m.group(1)), m.group(2).strip(), int(m.group(3)))
            for m in _NEWLABEL.finditer(handle.read())
        ]
    if not entries:
        return {}
    entries.sort(key=lambda e: e[0])

    printed = [e[1] for e in entries]
    trustworthy = all(re.fullmatch(r"\d{1,2}", p) for p in printed) and all(
        int(b) > int(a) for a, b in zip(printed, printed[1:])
    )
    return {
        (entry[1] if trustworthy else str(entry[0])): entry[2] for entry in entries
    }


def _page_count(pdf_path):
    result = _run(["pdfinfo", pdf_path])
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.M)
    return int(match.group(1)) if match else 0


def _page_ranges(pages, total):
    """Turn problem start pages into the page span each problem occupies.

    A problem runs from its own start page up to and including the page the
    next problem starts on, because its tail often shares that page.
    """
    ordered = sorted(pages.items(), key=lambda kv: (kv[1], _numeric(kv[0])))
    spans = {}
    for index, (label, start) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else total
        spans[label] = list(range(start, max(start, end) + 1))
    return spans


def _numeric(label):
    match = re.match(r"(\d+)", label)
    return int(match.group(1)) if match else 0


def build_homework(homework, tex_path):
    """Build both PDFs for one homework and record the problem page spans."""
    work = os.path.join(BUILD_DIR, homework)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)

    # Copy the folder so \includegraphics and any local .sty still resolve.
    source_dir = os.path.dirname(tex_path)
    for name in os.listdir(source_dir):
        src = os.path.join(source_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, work)

    with open(tex_path, encoding="utf-8", errors="replace") as handle:
        source = handle.read()

    manifest = {"homework": homework, "problems": {}, "modes": {}}
    for mode, with_solutions in (("q", False), ("s", True)):
        stem = f"cisbot_{homework}_{mode}"
        with open(os.path.join(work, f"{stem}.tex"), "w", encoding="utf-8") as handle:
            handle.write(_prepare_source(source, with_solutions))

        # No -halt-on-error: some sources contain recoverable errors (HW3H has a
        # literal '#' inside a macro argument) that LaTeX warns about and works
        # around, exactly as Overleaf does. Success is judged on whether a PDF
        # came out, not on latexmk's exit code.
        result = _run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-f", f"{stem}.tex"],
            cwd=work, timeout=420,
        )
        pdf = os.path.join(work, f"{stem}.pdf")
        if not os.path.isfile(pdf):
            raise BuildError(
                f"{homework} ({'solutions' if with_solutions else 'questions'}) "
                f"failed to build: {(result.stdout or '')[-400:]}"
            )

        total = _page_count(pdf)
        spans = _page_ranges(_parse_aux(os.path.join(work, f"{stem}.aux")), total)
        manifest["modes"][mode] = {"pages": total}
        for label, span in spans.items():
            manifest["problems"].setdefault(label, {})[mode] = span

        os.makedirs(os.path.join(OUT_DIR, homework), exist_ok=True)
        shutil.copy2(pdf, os.path.join(OUT_DIR, homework, f"{mode}.pdf"))

    manifest_path = os.path.join(OUT_DIR, homework, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
    logger.info(
        f"Built {homework}: {len(manifest['problems'])} problems, "
        f"{manifest['modes']['q']['pages']}q/{manifest['modes']['s']['pages']}s pages"
    )
    return manifest


def load_manifest(homework):
    path = os.path.join(OUT_DIR, homework, "manifest.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def render_pages(homework, mode, pages):
    """Render the given 1-based PDF pages to PNGs; returns the file paths."""
    pdf = os.path.join(OUT_DIR, homework, f"{mode}.pdf")
    if not os.path.isfile(pdf) or not pages:
        return []
    images = []
    for page in pages[:MAX_PAGES_PER_ATTACHMENT]:
        prefix = os.path.join(OUT_DIR, homework, f"{mode}_p{page}")
        target = f"{prefix}.png"
        if not os.path.isfile(target):
            result = _run([
                "pdftoppm", "-png", "-r", str(RENDER_DPI),
                "-f", str(page), "-l", str(page), "-singlefile", pdf, prefix,
            ])
            if result.returncode != 0 or not os.path.isfile(target):
                logger.error(f"Could not render {homework} {mode} page {page}")
                continue
        images.append(target)
    return images


def problem_attachments(homework, problem):
    """(question_images, solution_images, note) for one problem.

    `note` is set when something is worth saying in the thread -- most often
    that the source carries no written solution for this problem, which is the
    case for a handful of them.
    """
    manifest = load_manifest(homework)
    if not manifest:
        return [], [], f"No built copy of homework {homework} yet."

    spans = manifest["problems"].get(str(problem))
    if not spans:
        return [], [], (
            f"Homework {homework} has no problem {problem} "
            f"(found {len(manifest['problems'])} problems)."
        )

    questions = render_pages(homework, "q", spans.get("q", []))
    solutions = render_pages(homework, "s", spans.get("s", []))
    note = None
    if questions and not solutions:
        note = "No solution for this problem in the Overleaf source."
    return questions, solutions, note


def sync_and_build(force=False):
    """Pull, then rebuild homeworks whose source changed. Returns (built, errors)."""
    changed = sync_repo()
    built, errors = [], []
    for homework, tex in available_homeworks().items():
        manifest = load_manifest(homework)
        if manifest and not changed and not force:
            continue
        try:
            build_homework(homework, tex)
            built.append(homework)
        except Exception as e:
            errors.append(f"{homework}: {e}")
            logger.error(f"Build failed for {homework}: {e}")
    return built, errors
