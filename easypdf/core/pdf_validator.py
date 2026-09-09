"""
PDF/UA-1 accessibility checker using pikepdf.

Inspects a generated PDF for the structural markers required by PDF/UA-1
and reports pass/fail per check so the user can see what is and isn't
compliant before distributing the file.

Checks performed
----------------
1. Tagged PDF  — /MarkInfo /Marked = true
2. Language    — /Lang is present and non-empty
3. Display title — /ViewerPreferences /DisplayDocTitle = true
4. Structure tree — /StructTreeRoot present (content-level H1, P, etc.)
5. PDF/UA identifier — XMP pdfuaid:part = "1"
6. Document title — dc:title in XMP (or /Title in Info dict)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    path: str
    results: list[CheckResult] = field(default_factory=list)
    engine: str = ""        # "WeasyPrint" or "ReportLab" if detectable

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def score(self) -> tuple[int, int]:
        ok = sum(1 for r in self.results if r.passed)
        return ok, len(self.results)

    def format_report(self) -> str:
        ok, total = self.score
        lines = [
            f"Accessibility check: {self.path}",
            f"Result: {ok}/{total} checks passed"
            + (" ✓" if ok == total else ""),
            "",
        ]
        for r in self.results:
            icon = "PASS" if r.passed else "FAIL"
            line = f"  [{icon}] {r.name}"
            if r.detail:
                line += f"\n         {r.detail}"
            lines.append(line)

        if ok < total:
            lines += [
                "",
                "Tip: Install WeasyPrint (pip install weasyprint) for full",
                "     PDF/UA-1 structure-tag support (/StructTreeRoot).",
            ]
        return "\n".join(lines)


def validate_pdf(path: str) -> ValidationReport:
    """Run PDF/UA-1 accessibility checks on the PDF at *path*."""
    report = ValidationReport(path=path)

    try:
        import pikepdf
    except ImportError:
        report.results.append(CheckResult(
            "pikepdf available", False,
            "Install pikepdf (pip install pikepdf) to enable validation.",
        ))
        return report

    try:
        with pikepdf.open(path) as pdf:
            root = pdf.Root

            # 1. Tagged PDF
            mark_info = root.get("/MarkInfo")
            if mark_info:
                marked = mark_info.get("/Marked")
                passed = bool(marked)
            else:
                passed = False
            report.results.append(CheckResult(
                "Tagged PDF  (/MarkInfo /Marked = true)",
                passed,
                "" if passed else "PDF/UA-1 §7.1 requires /MarkInfo /Marked = true.",
            ))

            # 2. Language
            lang = root.get("/Lang")
            lang_str = str(lang).strip() if lang else ""
            passed = bool(lang_str)
            report.results.append(CheckResult(
                "Document language  (/Lang)",
                passed,
                lang_str if passed else "Set language in File → Document Properties.",
            ))

            # 3. DisplayDocTitle
            vp = root.get("/ViewerPreferences")
            passed = bool(vp and vp.get("/DisplayDocTitle"))
            report.results.append(CheckResult(
                "Title in viewer title bar  (/DisplayDocTitle = true)",
                passed,
                "" if passed else "Required by PDF/UA-1 §7.1.",
            ))

            # 4. Structure tree (content-level tags)
            stt = root.get("/StructTreeRoot")
            passed = stt is not None
            report.results.append(CheckResult(
                "Content structure tree  (/StructTreeRoot)",
                passed,
                "" if passed
                else "Missing: heading/paragraph tags absent. "
                     "Install WeasyPrint for full tagging.",
            ))

            # 5. XMP PDF/UA identifier
            try:
                with pdf.open_metadata() as meta:
                    part = str(meta.get("pdfuaid:part", "")).strip()
                passed = part == "1"
                detail = "" if passed else "XMP pdfuaid:part not set to '1'."
            except Exception as exc:
                passed = False
                detail = f"Could not read XMP metadata: {exc}"
            report.results.append(CheckResult(
                "PDF/UA-1 identifier  (XMP pdfuaid:part = 1)",
                passed,
                detail,
            ))

            # 6. Document title
            try:
                with pdf.open_metadata() as meta:
                    title = str(meta.get("dc:title", "")).strip()
                if not title:
                    title = str(pdf.docinfo.get("/Title", "")).strip()
                passed = bool(title)
                detail = title if passed else "Set title in File → Document Properties."
            except Exception:
                passed = False
                detail = "Could not read title metadata."
            report.results.append(CheckResult(
                "Document title in metadata",
                passed,
                detail,
            ))

            # Detect which engine produced the PDF
            try:
                producer = str(pdf.docinfo.get("/Producer", "")).lower()
                if "weasyprint" in producer:
                    report.engine = "WeasyPrint"
                elif "reportlab" in producer:
                    report.engine = "ReportLab"
            except Exception:
                pass

    except Exception as exc:
        report.results.append(CheckResult("File readable", False, str(exc)))

    return report
