"""
Worksheet export: render one or more saved worksheet lessons into a single,
self-contained document a learner can read, print or save as PDF offline.

Two formats are produced from the same lesson data:

* ``html`` (default) — a standalone HTML page with embedded, print-friendly CSS.
  Open it in any browser and use *Print → Save as PDF* to keep a copy.
* ``md`` — lightweight Markdown for note-taking apps / plain-text reading.

Each lesson is rendered in full (grammar explanation, conjugation table,
vocabulary, exercises **with the answer key**, and roleplay prompts) so the
export doubles as revision material.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

LANGUAGE_LABELS = {"en": "English", "fr": "French", "es": "Spanish"}

EXPORT_FORMATS = ("html", "md")


def _lang_label(code: str | None) -> str:
    if not code:
        return ""
    return LANGUAGE_LABELS.get(code, code.upper())


def _lesson_title(lesson: dict[str, Any]) -> str:
    """A human title for a lesson, mirroring the History list labels."""
    worksheet = lesson.get("worksheet") or {}
    if (lesson.get("mode") or "scenario") == "verb" and (lesson.get("verb") or worksheet.get("verb")):
        return f"Verb practice: {lesson.get('verb') or worksheet.get('verb')}"
    return lesson.get("scenario") or worksheet.get("scenario_summary") or "Worksheet"


def _fmt_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    # Stored timestamps are ISO-8601; show just the date portion when present.
    return text[:10]


# --------------------------------------------------------------------------- #
# HTML                                                                         #
# --------------------------------------------------------------------------- #
_HTML_STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  font-family: Georgia, 'Times New Roman', serif;
  color: #1a1a2e;
  max-width: 820px;
  margin: 0 auto;
  padding: 2.5rem 1.5rem 4rem;
  line-height: 1.55;
}
h1, h2, h3 { font-family: 'Trebuchet MS', 'Segoe UI', sans-serif; color: #1e2761; }
h1 { font-size: 2rem; margin: 0 0 .25rem; }
h2 { font-size: 1.5rem; margin: 0 0 .35rem; }
h3 { font-size: 1.05rem; margin: 1.4rem 0 .5rem; text-transform: uppercase; letter-spacing: .04em; color: #3a4a8c; }
.doc-head { border-bottom: 3px solid #1e2761; padding-bottom: 1rem; margin-bottom: 1.5rem; }
.doc-head .meta { color: #55607a; font-size: .9rem; }
.toc { background: #f2f5ff; border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 2rem; }
.toc ol { margin: .5rem 0 0; padding-left: 1.25rem; }
.toc a { color: #1e2761; text-decoration: none; }
.worksheet { padding: 1.25rem 0 1.75rem; border-bottom: 1px solid #d7ddf0; margin-bottom: 1.5rem; }
.badges { margin: .35rem 0 1rem; }
.badge {
  display: inline-block; font-family: 'Trebuchet MS', sans-serif; font-size: .72rem;
  font-weight: 700; letter-spacing: .03em; text-transform: uppercase;
  background: #1e2761; color: #fff; border-radius: 999px; padding: .2rem .6rem; margin-right: .4rem;
}
.badge.alt { background: #3a4a8c; }
.badge.ghost { background: #cadcfc; color: #1e2761; }
p.prose { margin: .3rem 0 1rem; }
table { width: 100%; border-collapse: collapse; margin: .3rem 0 1rem; font-family: 'Segoe UI', sans-serif; font-size: .92rem; }
th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #e2e7f5; vertical-align: top; }
th { background: #f2f5ff; color: #1e2761; font-size: .8rem; text-transform: uppercase; letter-spacing: .03em; }
.exercise { margin: 0 0 .9rem; padding: .75rem .9rem; background: #f8faff; border-left: 3px solid #1e2761; border-radius: 4px; }
.exercise .q { font-family: 'Segoe UI', sans-serif; margin: 0 0 .35rem; }
.exercise .a { font-family: 'Segoe UI', sans-serif; margin: 0; color: #1b6b3a; }
.exercise .hint { font-size: .82rem; color: #55607a; margin: .25rem 0 0; }
.type-tag { display: inline-block; font-family: 'Trebuchet MS', sans-serif; font-size: .68rem; font-weight: 700;
  text-transform: uppercase; color: #3a4a8c; background: #e7ecfb; border-radius: 4px; padding: .12rem .4rem; margin-bottom: .35rem; }
ul.prompts { font-family: 'Segoe UI', sans-serif; padding-left: 1.2rem; }
ul.prompts li { margin: .2rem 0; }
footer { margin-top: 2.5rem; color: #8890a8; font-size: .8rem; text-align: center; }
@media print {
  body { padding: 0; max-width: none; }
  .worksheet { page-break-inside: avoid; break-inside: avoid; }
  h2 { page-break-after: avoid; }
  a { color: inherit; text-decoration: none; }
}
"""


def _html_worksheet(index: int, lesson: dict[str, Any]) -> str:
    worksheet = lesson.get("worksheet") or {}
    title = _lesson_title(lesson)
    lang_label = _lang_label(lesson.get("target_language"))

    parts: list[str] = [f'<section class="worksheet" id="ws-{index}">']
    parts.append(f"<h2>{index}. {escape(title)}</h2>")

    badges = []
    if lang_label:
        badges.append(f'<span class="badge">{escape(lang_label)}</span>')
    if lesson.get("difficulty"):
        badges.append(f'<span class="badge alt">{escape(str(lesson["difficulty"]))}</span>')
    grammar = lesson.get("grammar_focus") or worksheet.get("grammar_focus")
    if grammar:
        badges.append(f'<span class="badge ghost">grammar · {escape(str(grammar))}</span>')
    created = _fmt_date(lesson.get("created_at"))
    if created:
        badges.append(f'<span class="badge ghost">{escape(created)}</span>')
    if badges:
        parts.append(f'<div class="badges">{"".join(badges)}</div>')

    if worksheet.get("scenario_summary"):
        parts.append(f'<p class="prose">{escape(str(worksheet["scenario_summary"]))}</p>')

    if worksheet.get("explanations"):
        parts.append("<h3>Explanation</h3>")
        parts.append(f'<p class="prose">{escape(str(worksheet["explanations"]))}</p>')

    conj = worksheet.get("conjugation_table") or []
    if conj:
        parts.append("<h3>Conjugation</h3>")
        parts.append("<table><thead><tr><th>Pronoun</th><th>Form</th><th>Meaning</th></tr></thead><tbody>")
        for row in conj:
            parts.append(
                "<tr>"
                f"<td>{escape(str(row.get('pronoun', '')))}</td>"
                f"<td><strong>{escape(str(row.get('form', '')))}</strong></td>"
                f"<td>{escape(str(row.get('translation', '')))}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")

    vocab = worksheet.get("vocabulary") or []
    if vocab:
        parts.append("<h3>Vocabulary</h3>")
        parts.append("<table><thead><tr><th>Word</th><th>Translation</th><th>Example</th></tr></thead><tbody>")
        for v in vocab:
            parts.append(
                "<tr>"
                f"<td><strong>{escape(str(v.get('word', '')))}</strong></td>"
                f"<td>{escape(str(v.get('translation', '')))}</td>"
                f"<td><em>{escape(str(v.get('example_sentence', '')))}</em></td>"
                "</tr>"
            )
        parts.append("</tbody></table>")

    exercises = worksheet.get("exercises") or []
    if exercises:
        parts.append("<h3>Exercises &amp; answer key</h3>")
        for n, ex in enumerate(exercises, start=1):
            ex_type = str(ex.get("type", "")).replace("_", " ")
            parts.append('<div class="exercise">')
            if ex_type.strip():
                parts.append(f'<span class="type-tag">{escape(ex_type)}</span>')
            parts.append(f'<p class="q"><strong>Q{n}.</strong> {escape(str(ex.get("question", "")))}</p>')
            if ex.get("hint"):
                parts.append(f'<p class="hint">Hint: {escape(str(ex["hint"]))}</p>')
            parts.append(f'<p class="a"><strong>Answer:</strong> {escape(str(ex.get("answer", "")))}</p>')
            parts.append("</div>")

    prompts = worksheet.get("roleplay_prompts") or []
    if prompts:
        parts.append("<h3>Roleplay prompts</h3>")
        parts.append('<ul class="prompts">')
        for p in prompts:
            parts.append(f"<li>{escape(str(p))}</li>")
        parts.append("</ul>")

    parts.append("</section>")
    return "\n".join(parts)


def _render_html(lessons: list[dict[str, Any]], generated_at: datetime) -> str:
    count = len(lessons)
    heading = "Worksheet" if count == 1 else f"{count} Worksheets"
    date_str = generated_at.strftime("%d %b %Y %H:%M UTC")

    body: list[str] = []
    body.append('<header class="doc-head">')
    body.append(f"<h1>Language Learning · {escape(heading)}</h1>")
    body.append(f'<p class="meta">Exported {escape(date_str)} · read, print or save as PDF</p>')
    body.append("</header>")

    if count > 1:
        body.append('<nav class="toc"><strong>Contents</strong><ol>')
        for i, lesson in enumerate(lessons, start=1):
            body.append(f'<li><a href="#ws-{i}">{escape(_lesson_title(lesson))}</a></li>')
        body.append("</ol></nav>")

    for i, lesson in enumerate(lessons, start=1):
        body.append(_html_worksheet(i, lesson))

    body.append(
        f"<footer>Generated by the Language Learning App · {escape(date_str)}</footer>"
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"<title>Language Learning · {escape(heading)}</title>\n"
        f"<style>{_HTML_STYLE}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------- #
# Markdown                                                                     #
# --------------------------------------------------------------------------- #
def _md_escape(text: Any) -> str:
    """Escape Markdown table-breaking / heading characters in inline content."""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _md_worksheet(index: int, lesson: dict[str, Any]) -> list[str]:
    worksheet = lesson.get("worksheet") or {}
    out: list[str] = [f"## {index}. {_md_escape(_lesson_title(lesson))}"]

    meta = []
    lang_label = _lang_label(lesson.get("target_language"))
    if lang_label:
        meta.append(f"**{lang_label}**")
    if lesson.get("difficulty"):
        meta.append(f"level {lesson['difficulty']}")
    grammar = lesson.get("grammar_focus") or worksheet.get("grammar_focus")
    if grammar:
        meta.append(f"grammar: {grammar}")
    created = _fmt_date(lesson.get("created_at"))
    if created:
        meta.append(created)
    if meta:
        out.append(" · ".join(str(m) for m in meta))

    if worksheet.get("scenario_summary"):
        out.append("")
        out.append(str(worksheet["scenario_summary"]).strip())

    if worksheet.get("explanations"):
        out.append("")
        out.append("### Explanation")
        out.append(str(worksheet["explanations"]).strip())

    conj = worksheet.get("conjugation_table") or []
    if conj:
        out.append("")
        out.append("### Conjugation")
        out.append("| Pronoun | Form | Meaning |")
        out.append("| --- | --- | --- |")
        for row in conj:
            out.append(
                f"| {_md_escape(row.get('pronoun', ''))} | {_md_escape(row.get('form', ''))} "
                f"| {_md_escape(row.get('translation', ''))} |"
            )

    vocab = worksheet.get("vocabulary") or []
    if vocab:
        out.append("")
        out.append("### Vocabulary")
        out.append("| Word | Translation | Example |")
        out.append("| --- | --- | --- |")
        for v in vocab:
            out.append(
                f"| {_md_escape(v.get('word', ''))} | {_md_escape(v.get('translation', ''))} "
                f"| {_md_escape(v.get('example_sentence', ''))} |"
            )

    exercises = worksheet.get("exercises") or []
    if exercises:
        out.append("")
        out.append("### Exercises & answer key")
        for n, ex in enumerate(exercises, start=1):
            ex_type = str(ex.get("type", "")).replace("_", " ").strip()
            tag = f" _({ex_type})_" if ex_type else ""
            out.append("")
            out.append(f"**Q{n}.**{tag} {str(ex.get('question', '')).strip()}")
            if ex.get("hint"):
                out.append(f"- Hint: {str(ex['hint']).strip()}")
            out.append(f"- **Answer:** {str(ex.get('answer', '')).strip()}")

    prompts = worksheet.get("roleplay_prompts") or []
    if prompts:
        out.append("")
        out.append("### Roleplay prompts")
        for p in prompts:
            out.append(f"- {str(p).strip()}")

    out.append("")
    return out


def _render_markdown(lessons: list[dict[str, Any]], generated_at: datetime) -> str:
    count = len(lessons)
    heading = "Worksheet" if count == 1 else f"{count} Worksheets"
    date_str = generated_at.strftime("%d %b %Y %H:%M UTC")

    out: list[str] = [f"# Language Learning · {heading}", f"_Exported {date_str}_", ""]

    if count > 1:
        out.append("## Contents")
        for i, lesson in enumerate(lessons, start=1):
            out.append(f"{i}. {_md_escape(_lesson_title(lesson))}")
        out.append("")

    for i, lesson in enumerate(lessons, start=1):
        out.extend(_md_worksheet(i, lesson))
        out.append("---")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
def render_export(lessons: list[dict[str, Any]], fmt: str = "html") -> tuple[str, str, str]:
    """Render lessons into a document.

    Returns ``(content, media_type, filename)``. ``lessons`` are full lesson
    dicts as returned by ``store.get_lesson`` (i.e. with a parsed ``worksheet``).
    """
    fmt = (fmt or "html").lower()
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {fmt!r}")

    generated_at = datetime.now(timezone.utc)
    stamp = generated_at.strftime("%Y%m%d")
    suffix = "worksheet" if len(lessons) == 1 else "worksheets"

    if fmt == "md":
        return (
            _render_markdown(lessons, generated_at),
            "text/markdown; charset=utf-8",
            f"language-{suffix}-{stamp}.md",
        )
    return (
        _render_html(lessons, generated_at),
        "text/html; charset=utf-8",
        f"language-{suffix}-{stamp}.html",
    )
