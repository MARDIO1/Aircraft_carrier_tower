"""
Feishu MCP sync preparation.

There is no Feishu MCP connector available in this session, so this module
implements the stable payload/draft layer first. Once the connector is added,
the actual upload function can call the MCP tool without changing analysis code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable


def build_report_markdown(report: Dict[str, object]) -> str:
    summary = report.get("summary", {})
    source_csv = report.get("source_csv", "")
    lines = [
        "# 飞控黑匣子分析报告",
        "",
        f"- Source CSV: `{source_csv}`",
        f"- Created at: `{report.get('created_at', '')}`",
        f"- Rows: `{summary.get('row_count', 0)}`",
        f"- Sample rate: `{float(summary.get('sample_rate_hz', 0.0)):.2f} Hz`",
        f"- Duration: `{float(summary.get('duration_s', 0.0)):.2f} s`",
        "",
        "## Correlation Highlights",
        "",
        "| Pair | Zero lag | Best lag samples | Best lag correlation |",
        "| --- | ---: | ---: | ---: |",
    ]
    correlations = report.get("correlations", {})
    if isinstance(correlations, dict):
        for name, item in correlations.items():
            if not isinstance(item, dict):
                continue
            best_lag = item.get("best_lag", {})
            lines.append(
                f"| {name} | {float(item.get('zero_lag', 0.0)):.3f} | "
                f"{int(best_lag.get('lag_samples', 0))} | {float(best_lag.get('correlation', 0.0)):.3f} |"
            )
    return "\n".join(lines) + "\n"


def write_local_feishu_draft(report: Dict[str, object], output_dir: Path | str = "analysis_reports/feishu_drafts") -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    source_name = Path(str(report.get("source_csv", "report"))).stem
    draft_path = output_path / f"{source_name}_feishu_draft.md"
    draft_path.write_text(build_report_markdown(report), encoding="utf-8")
    return draft_path


def feishu_research_checklist() -> Dict[str, Iterable[str]]:
    return {
        "mcp_capabilities_to_confirm": [
            "cloud document create/update APIs",
            "table or spreadsheet block update APIs",
            "image/file upload for MATLAB figures",
            "document permission and workspace scope",
            "conflict detection when a human edits the same doc",
        ],
        "recommended_first_sync": [
            "create a report page per blackbox CSV",
            "append summary metrics and correlation table",
            "upload generated figures as attachments after MATLAB output is stable",
            "store Feishu document token in local config after user confirmation",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(feishu_research_checklist(), ensure_ascii=False, indent=2))
