"""
Professional forensic report generator — ForensicChat Edition
All fixes:
  1. ForensicChat heading always visible (solid colour fallback, no clip dependency)
  2. Logo loaded correctly from static/myicon.png (7 candidate paths, base64 embedded)
  3. ALL database records shown — no date cutoff
  4. Timestamps correctly formatted DD/MM/YYYY HH:MM:SS everywhere
  5. JS table renderer uses pre-formatted display values (not _raw)
  6. Data sorted ascending (oldest first)
  7. Timeline shows ALL events, no cap
  8. Client-side date filter defaults to "All data"
"""

import os
import re
import platform
import base64
from datetime import datetime
from collections import Counter
from database import get_all_data
from paths import get_reports_dir, get_base_dir
import json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(v):
    """HTML-escape a value."""
    return (str(v)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _short(v, n=80):
    s = str(v) if v is not None else ""
    return s[:n] + ("…" if len(s) > n else "")


def _fmt_ts(v):
    """
    Convert ANY ISO-style timestamp to  DD/MM/YYYY HH:MM:SS  (or DD/MM/YYYY).
    Handles:
        2026-04-29T13:32:44
        2026-04-29 13:32:44
        2026-04-29T13:32:44+0000
        2026-04-29T13:32:44Z
        2026-04-29
    Returns the formatted string, never the raw value.
    """
    if not v:
        return "—"

    s = str(v).strip()

    # 1. Replace T separator
    s = s.replace("T", " ")

    # 2. Strip timezone: Z  |  +HH:MM  |  +HHMM  |  -HH:MM  |  -HHMM
    s = re.sub(r"[Zz]$", "", s)
    s = re.sub(r"[+-]\d{2}:?\d{2}$", "", s)
    s = s.strip()

    # 3. Try parse — longest format first
    for fmt, has_time in [
        ("%Y-%m-%d %H:%M:%S", True),
        ("%Y-%m-%d %H:%M",    True),
        ("%Y-%m-%d",          False),
    ]:
        # Only try if string is long enough
        needed = 19 if has_time else 10
        chunk  = s[:needed]
        try:
            dt = datetime.strptime(chunk, fmt)
            return (dt.strftime("%d/%m/%Y %H:%M:%S")
                    if has_time
                    else dt.strftime("%d/%m/%Y"))
        except ValueError:
            continue

    # 4. Last resort — return first 19 chars unchanged so at least something shows
    return s[:19] if len(s) >= 10 else s


def _load_logo(base_dir):
    """
    Search for myicon.png in several locations.
    Returns a base64-embedded <img> tag, or a 🔍 emoji span as fallback.
    """
    fallback  = '<span class="forensic-logo-fallback">🔍</span>'
    script_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(script_dir,  "static",  "myicon.png"),
        os.path.join(script_dir,  "..",       "static", "myicon.png"),
        os.path.join(base_dir,    "static",  "myicon.png"),
        os.path.join(base_dir,    "..",       "static", "myicon.png"),
        os.path.join("static",               "myicon.png"),
        os.path.join("..",         "static", "myicon.png"),
        "myicon.png",
    ]

    for raw in candidates:
        path = os.path.normpath(raw)
        if os.path.isfile(path):
            try:
                with open(path, "rb") as fh:
                    b64 = base64.b64encode(fh.read()).decode()
                print(f"[report] ✅ Logo loaded: {path}")
                return (
                    f'<img class="forensic-logo" '
                    f'src="data:image/png;base64,{b64}" '
                    f'alt="ForensicChat">'
                )
            except Exception as exc:
                print(f"[report] Logo read error ({path}): {exc}")

    print("[report] ⚠️  Logo not found — using emoji fallback")
    return fallback


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:

    def __init__(self):
        self.report_dir = get_reports_dir()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, query_data=None, filtered_data=None):
        """
        Query report.  If filtered_data is supplied and non-empty, use it;
        otherwise pull EVERYTHING from the database.
        """
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{ts}.html"
        filepath = os.path.join(self.report_dir, filename)

        organized = (self._organize(filtered_data)
                     if filtered_data
                     else get_all_data())

        html = self._build(organized, query_data=query_data, full=False)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return filename, filepath

    def generate_full(self):
        """Full report — every record in the DB."""
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"full_report_{ts}.html"
        filepath = os.path.join(self.report_dir, filename)
        data     = get_all_data()
        html     = self._build(data, query_data=None, full=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return filename, filepath

    # ------------------------------------------------------------------
    # Data organisation
    # ------------------------------------------------------------------

    def _organize(self, flat):
        buckets = {t: [] for t in [
            "browser_history", "event_logs", "prefetch_files",
            "recent_files",    "usb_devices", "usb_connections",
            "usb_history",     "system_logs",
        ]}
        for item in flat:
            if "browser" in item and "url" in item:
                buckets["browser_history"].append(item)
            elif "event_id" in item:
                buckets["event_logs"].append(item)
            elif "exe_name" in item:
                buckets["prefetch_files"].append(item)
            elif "device_name" in item and "connection_type" in item:
                buckets["usb_devices"].append(item)
            elif "file_type" in item or "target_path" in item:
                buckets["recent_files"].append(item)
            elif "log_type" in item:
                if "event_date" in item:
                    buckets["event_logs"].append(item)
                else:
                    buckets["system_logs"].append(item)
            elif "instance_id" in item or "serial_number" in item:
                buckets["usb_history"].append(item)
        return buckets

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def _summary_cards(self, data):
        total = sum(len(v) for v in data.values())
        cards = [("🔎", "Total Artifacts", total, "#3b82f6")]

        bh = data.get("browser_history", [])
        if bh:
            top_b = Counter(i.get("browser", "?") for i in bh).most_common(1)[0]
            cards.append(("🌐", "Web Visits",     len(bh),  "#10b981"))
            cards.append(("💻", "Top Browser",    top_b[0], "#6366f1"))

        usb = data.get("usb_devices", [])
        if usb:
            ext = sum(1 for d in usb if "External" in d.get("connection_type", ""))
            cards.append(("💾", "USB Devices",    ext,      "#f59e0b"))

        pf = data.get("prefetch_files", [])
        if pf:
            cards.append(("⚙️", "Programs Run",   len(pf),  "#ef4444"))

        rf = data.get("recent_files", [])
        if rf:
            cards.append(("📁", "Files Accessed", len(rf),  "#8b5cf6"))

        sl = data.get("system_logs", [])
        el = data.get("event_logs",  [])
        if sl or el:
            cards.append(("📋", "Log Entries", len(sl) + len(el), "#64748b"))

        return cards

    def _findings(self, data):
        lines = []

        bh = data.get("browser_history", [])
        if bh:
            domains = []
            for i in bh:
                url = i.get("url", "")
                try:
                    domain = url.split("/")[2] if "//" in url else url.split("/")[0]
                    domains.append(domain)
                except Exception:
                    pass
            top_d = Counter(domains).most_common(3)
            lines.append(
                f"<b>{len(bh)}</b> web pages visited. "
                + ("Most-visited: " + ", ".join(d[0] for d in top_d) + "." if top_d else "")
            )

        usb = data.get("usb_devices", [])
        ext = [d for d in usb if "External" in d.get("connection_type", "")]
        if ext:
            names = list({d.get("device_name", "Unknown") for d in ext})[:3]
            lines.append(
                f"<b>{len(ext)}</b> external USB device(s) detected: "
                + ", ".join(_esc(n) for n in names) + "."
            )

        pf = data.get("prefetch_files", [])
        if pf:
            exes = [i.get("exe_name", "") for i in pf[:5]]
            lines.append(
                f"<b>{len(pf)}</b> program(s) executed. Examples: "
                + ", ".join(_esc(e) for e in exes if e) + "."
            )

        rf = data.get("recent_files", [])
        if rf:
            types = Counter(i.get("file_type", "File") for i in rf).most_common(3)
            lines.append(
                f"<b>{len(rf)}</b> file(s) recently opened/modified. Types: "
                + ", ".join(f"{t[0]} ({t[1]})" for t in types) + "."
            )

        sl = data.get("system_logs", [])
        if sl:
            lines.append(f"<b>{len(sl)}</b> system log entries recorded.")

        el = data.get("event_logs", [])
        if el:
            levels = Counter(i.get("level", "Info") for i in el).most_common(3)
            lines.append(
                f"<b>{len(el)}</b> Windows Event Log entries. Severity: "
                + ", ".join(f"{lv[0]} ({lv[1]})" for lv in levels) + "."
            )

        if not lines:
            lines.append("No forensic artifacts were found in the database.")
        return lines

    def _timeline(self, data):
        """ALL events, sorted ascending (oldest first). No cap."""
        events = []

        for item in data.get("browser_history", []):
            t = item.get("visit_time", "")
            if t:
                events.append((t, "🌐", "Web Visit",
                    _short(item.get("title") or item.get("url", ""), 70),
                    item.get("browser", "")))

        for item in data.get("prefetch_files", []):
            t = item.get("last_run", "")
            if t:
                events.append((t, "⚙️", "Program Executed",
                    _short(item.get("exe_name", ""), 70), ""))

        for item in data.get("recent_files", []):
            t = item.get("accessed_time", "")
            if t:
                events.append((t, "📁", "File Accessed",
                    _short(item.get("name", ""), 70),
                    item.get("file_type", "")))

        for item in data.get("usb_devices", []):
            t = item.get("last_connected", "")
            if t:
                events.append((t, "💾", "USB Device",
                    _short(item.get("device_name", ""), 70),
                    item.get("connection_type", "")))

        for item in data.get("event_logs", []):
            t = item.get("time_generated", "")
            if t:
                events.append((t, "📋", "System Event",
                    _short(item.get("message", ""), 70),
                    item.get("level", "")))

        for item in data.get("system_logs", []):
            t = item.get("timestamp", "")
            if t:
                events.append((t, "🐧", "System Log",
                    _short(item.get("message", ""), 70),
                    item.get("source", "")))

        events.sort(key=lambda x: x[0])
        return events

    # ------------------------------------------------------------------
    # HTML builder
    # ------------------------------------------------------------------

    def _build(self, data, query_data, full):
        now_str  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        title    = "Full System Forensic Report" if full else "Forensic Query Report"
        os_name  = platform.system()
        hostname = platform.node()
        total    = sum(len(v) for v in data.values())

        base_dir = get_base_dir()
        logo_tag = _load_logo(base_dir)

        # ── Section definitions ──
        SECTIONS = [
            ("browser_history", "🌐 Browser History",
             ["browser", "profile", "title", "url", "visit_time", "visit_count"],
             "visit_time"),
            ("usb_devices",     "💾 USB Devices",
             ["device_name", "connection_type", "vendor",
              "last_connected", "serial_number", "mount_point"],
             "last_connected"),
            ("prefetch_files",  "⚙️ Prefetch Files",
             ["exe_name", "run_count", "last_run", "file_path"],
             "last_run"),
            ("recent_files",    "📁 Recent Files",
             ["name", "file_type", "accessed_time", "target_path"],
             "accessed_time"),
            ("event_logs",      "📋 Event Logs",
             ["log_type", "event_id", "source", "level",
              "time_generated", "message"],
             "time_generated"),
            ("system_logs",     "🐧 System Logs",
             ["source", "timestamp", "log_type", "message"],
             "timestamp"),
            ("usb_connections", "🔌 USB Connections",
             ["device_name", "event_type", "event_time", "device_id"],
             "event_time"),
            ("usb_history",     "📀 USB History",
             ["device_name", "last_connected", "vendor", "product_id"],
             "last_connected"),
        ]

        # Columns whose values should be formatted as timestamps
        TS_COLS = {
            "visit_time", "last_connected", "time_generated",
            "accessed_time", "last_run", "event_time", "timestamp",
        }

        # ── Build JSON for JS ──
        # KEY FIX: store BOTH the formatted display string AND the raw ISO
        # for JS date-range filtering.  The table renderer uses the display
        # string — never the raw value.
        sections_json = []
        for sid, sname, cols, ts_field in SECTIONS:
            items = data.get(sid, [])
            if not items:
                continue

            sorted_items = sorted(items, key=lambda x: (x.get(ts_field) or "0000"))

            items_json = []
            for item in sorted_items:
                clean = {}
                for k, v in item.items():
                    raw = str(v) if v is not None else ""
                    if k in TS_COLS:
                        # display  → pre-formatted  DD/MM/YYYY HH:MM:SS
                        clean[k]           = _fmt_ts(raw)
                        # _raw    → original ISO string kept only for JS cutoff maths
                        clean[k + "_raw"]  = raw
                    else:
                        clean[k] = _esc(raw)
                items_json.append(clean)

            sections_json.append({
                "id":              sid,
                "name":            sname,
                "columns":         cols,
                "timestamp_field": ts_field,
                "items":           items_json,
                "count":           len(items_json),
            })

        # ── Timeline ──
        timeline       = self._timeline(data)
        total_timeline = len(timeline)

        timeline_rows = ""
        for ts_raw, icon, etype, desc, detail in timeline:
            # _fmt_ts applied here too — timeline always shows DD/MM/YYYY HH:MM:SS
            timeline_rows += (
                f"<tr>"
                f"<td class='tl-time'>{_esc(_fmt_ts(ts_raw))}</td>"
                f"<td>{icon}</td>"
                f"<td><b>{_esc(etype)}</b></td>"
                f"<td title='{_esc(desc)}'>{_esc(desc)}</td>"
                f"<td class='tl-detail'>{_esc(detail)}</td>"
                f"</tr>"
            )
        if not timeline_rows:
            timeline_rows = (
                "<tr><td colspan='5' class='empty'>No events available.</td></tr>"
            )

        # ── Cards & findings ──
        cards        = self._summary_cards(data)
        findings     = self._findings(data)

        cards_html = "".join(
            f'<div class="card" style="border-top:4px solid {c[3]};">'
            f'<div class="card-icon">{c[0]}</div>'
            f'<div class="card-val">{_esc(str(c[2]))}</div>'
            f'<div class="card-label">{_esc(c[1])}</div>'
            f'</div>'
            for c in cards
        )
        findings_html = "".join(f"<li>{f}</li>" for f in findings)

        # ── Query banner ──
        query_banner = ""
        if query_data:
            q  = _esc(query_data.get("query", ""))
            df = _esc(query_data.get("date_filter")    or "All collected data")
            bf = _esc(query_data.get("browser_filter") or "All")
            query_banner = (
                f'<div class="query-banner">'
                f'<span class="qb-label">Query</span>'
                f'<span class="qb-value">{q}</span>'
                f'<span class="qb-meta">📅 {df} &nbsp;|&nbsp; 🌐 {bf}</span>'
                f'</div>'
            )

        sj = json.dumps(sections_json, ensure_ascii=False)

        # ════════════════════════════════════════════════════════════════
        #  Complete HTML
        # ════════════════════════════════════════════════════════════════
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)}</title>
<style>
/* ── Reset ── */
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Segoe UI',Roboto,Arial,sans-serif;
      background:#eef2f5;color:#1e2a3a;line-height:1.5;font-size:14px;}}
.report-container{{display:flex;min-height:100vh;}}

/* ════════════ SIDEBAR ════════════ */
.sidebar{{
  width:280px;background:#1e293b;color:#e2e8f0;
  flex-shrink:0;display:flex;flex-direction:column;
  box-shadow:2px 0 8px rgba(0,0,0,.20);
  position:sticky;top:0;height:100vh;overflow-y:auto;
}}
.sidebar-header{{padding:20px 18px 14px;border-bottom:1px solid #334155;}}
.sidebar-header h2{{font-size:1.1rem;font-weight:700;color:#f1f5f9;margin-bottom:3px;}}
.sidebar-header p{{font-size:.72rem;color:#94a3b8;}}
.artifact-buttons{{flex:1;padding:12px 10px;display:flex;flex-direction:column;gap:4px;}}
.artifact-btn{{
  background:transparent;border:none;color:#cbd5e1;
  padding:9px 14px;text-align:left;font-size:.83rem;
  border-radius:7px;cursor:pointer;transition:all .15s;
  display:flex;align-items:center;gap:9px;font-weight:500;width:100%;
}}
.artifact-btn:hover{{background:#334155;color:#f1f5f9;}}
.artifact-btn.active{{background:#0ea5e9;color:#fff;
  box-shadow:0 2px 8px rgba(14,165,233,.3);}}
.badge{{margin-left:auto;background:rgba(0,0,0,.28);
  padding:2px 8px;border-radius:20px;font-size:.67rem;font-weight:600;}}
.sidebar-footer{{padding:12px 18px;font-size:.67rem;
  border-top:1px solid #334155;color:#64748b;line-height:1.7;}}

/* ════════════ MAIN ════════════ */
.main-content{{flex:1;background:#f1f5f9;overflow-x:auto;}}
.content-pane{{padding:24px 32px;max-width:1500px;margin:0 auto;}}

/* ════════════════════════════════════════════════════════
   FORENSICCHAT HEADER
   Two rows:
     Row 1 — "ForensicChat"  large solid + gradient text
     Row 2 — subtitle (left) | logo (right)

   FIX: use both color: and background-clip so the heading
   is ALWAYS visible even when clip is unsupported.
════════════════════════════════════════════════════════ */
.forensic-header{{
  background:#0f172a;
  background-image:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#0c2a4a 100%);
  border-radius:16px;
  padding:26px 32px 22px;
  margin-bottom:26px;
  box-shadow:0 6px 28px rgba(0,0,0,.32);
  border:1px solid rgba(56,189,248,.20);
  display:flex;
  flex-direction:column;
  gap:18px;
}}

/* Row 1 */
.forensic-brand-row{{
  display:block;        /* simple block — no flex needed */
}}
.forensic-heading{{
  /* Solid colour visible on every browser */
  color:#38bdf8;
  font-size:3rem;
  font-weight:900;
  letter-spacing:1px;
  line-height:1.05;
  /* Gradient overlay where supported */
  background:linear-gradient(90deg,#38bdf8 0%,#a5f3fc 50%,#e0f2fe 100%);
  -webkit-background-clip:text;
  background-clip:text;
  /* Only go transparent if clip actually worked */
  -webkit-text-fill-color:transparent;
}}
/* Older / non-webkit engines: override to solid cyan */
@supports not (-webkit-background-clip:text){{
  .forensic-heading{{
    color:#38bdf8 !important;
    -webkit-text-fill-color:unset !important;
    background:none !important;
  }}
}}

/* Row 2 */
.forensic-meta-row{{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:20px;
}}
.forensic-sub{{font-size:.82rem;color:#94a3b8;line-height:1.65;}}
.forensic-sub strong{{color:#cbd5e1;font-weight:600;}}
.forensic-sub .accent{{color:#38bdf8;font-weight:700;}}

/* Logo */
.forensic-logo{{
  max-height:76px;width:auto;
  border-radius:14px;background:#fff;padding:7px;
  box-shadow:0 4px 16px rgba(0,0,0,.32);
  flex-shrink:0;display:block;
}}
.forensic-logo-fallback{{font-size:3.2rem;flex-shrink:0;}}

/* ════════════ SUMMARY CARDS ════════════ */
.cards-grid{{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(148px,1fr));
  gap:14px;margin-bottom:22px;
}}
.card{{background:#fff;border-radius:12px;padding:16px 12px;
  text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.07);}}
.card-icon{{font-size:1.7rem;margin-bottom:7px;}}
.card-val{{font-size:1.6rem;font-weight:800;color:#0f172a;}}
.card-label{{font-size:.67rem;text-transform:uppercase;
  color:#64748b;letter-spacing:.5px;margin-top:3px;}}

/* ════════════ EXEC SUMMARY / TIMELINE WRAPPER ════════════ */
.exec-summary,.timeline-section{{
  background:#fff;border-radius:12px;
  padding:20px 24px;margin-bottom:22px;
  box-shadow:0 1px 3px rgba(0,0,0,.05);
}}
.exec-summary h3,.timeline-section h3{{
  font-size:.85rem;text-transform:uppercase;letter-spacing:.5px;
  color:#475569;margin-bottom:14px;
  border-left:4px solid #0ea5e9;padding-left:10px;
}}
.exec-summary ul{{list-style:none;display:flex;flex-direction:column;gap:8px;}}
.exec-summary li{{background:#f8fafc;padding:11px 14px;border-radius:8px;
  border-left:3px solid #3b82f6;font-size:.86rem;}}

/* ════════════ TIMELINE ════════════ */
.timeline-controls{{display:flex;gap:10px;align-items:center;
  margin-bottom:12px;flex-wrap:wrap;}}
.tl-search,.tl-filter{{padding:6px 10px;border:1px solid #cbd5e1;
  border-radius:6px;font-size:.78rem;background:#fff;}}
.tl-search{{min-width:200px;}}
.timeline-table-wrap{{overflow-x:auto;max-height:540px;overflow-y:auto;}}
.timeline-table{{width:100%;border-collapse:collapse;font-size:.77rem;}}
.timeline-table thead th{{
  background:#f1f5f9;padding:8px 10px;text-align:left;font-weight:700;
  border-bottom:2px solid #e2e8f0;white-space:nowrap;
  position:sticky;top:0;z-index:2;
  font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;color:#475569;
}}
.timeline-table tbody td{{padding:7px 10px;border-bottom:1px solid #f1f5f9;}}
.timeline-table tbody tr:hover td{{background:#f0f9ff;}}
.tl-time{{
  width:190px;font-family:monospace;
  font-size:.74rem;color:#334155;white-space:nowrap;
}}
.tl-detail{{color:#64748b;font-size:.73rem;}}
.empty{{text-align:center;color:#94a3b8;padding:30px;font-style:italic;}}

/* ════════════ ARTIFACT VIEW ════════════ */
.artifact-view{{
  background:#fff;border-radius:12px;
  padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,.05);margin-top:18px;
}}
.artifact-view-header{{
  display:flex;justify-content:space-between;align-items:flex-start;
  flex-wrap:wrap;gap:12px;margin-bottom:14px;
  padding-bottom:12px;border-bottom:2px solid #e2e8f0;
}}
.artifact-title{{font-size:1.18rem;font-weight:700;}}
.artifact-meta{{font-size:.75rem;color:#64748b;margin-top:3px;}}
.filter-bar{{
  display:flex;gap:10px;align-items:center;
  background:#f8fafc;padding:8px 14px;border-radius:8px;flex-wrap:wrap;
}}
.filter-bar label{{font-size:.7rem;font-weight:700;color:#475569;
  text-transform:uppercase;letter-spacing:.04em;}}
.filter-select,.filter-input{{padding:5px 10px;border-radius:6px;
  border:1px solid #cbd5e1;background:#fff;font-size:.78rem;color:#1e293b;}}
.filter-input{{min-width:180px;}}
.record-count{{font-size:.73rem;color:#64748b;margin-bottom:7px;padding:0 2px;}}
.table-wrapper{{overflow-x:auto;max-height:600px;overflow-y:auto;}}
.data-table{{width:100%;border-collapse:collapse;font-size:.77rem;}}
.data-table thead th{{
  background:#f1f5f9;padding:8px 11px;text-align:left;font-weight:700;
  border-bottom:2px solid #e2e8f0;white-space:nowrap;
  position:sticky;top:0;z-index:2;
  font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;color:#475569;
}}
.data-table tbody td{{
  padding:7px 11px;border-bottom:1px solid #f1f5f9;
  max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}}
.data-table tbody tr:hover td{{background:#f0f9ff;}}
.data-table tbody tr:nth-child(even) td{{background:#fafcff;}}
.data-table tbody tr:nth-child(even):hover td{{background:#f0f9ff;}}
.empty-message{{text-align:center;padding:40px;color:#94a3b8;font-style:italic;}}

/* ════════════ QUERY BANNER ════════════ */
.query-banner{{
  background:#1e293b;color:#e2e8f0;
  padding:8px 16px;border-radius:8px;
  display:inline-flex;align-items:center;gap:12px;
  font-size:.78rem;margin-bottom:18px;flex-wrap:wrap;
}}
.qb-label{{background:#3b82f6;padding:2px 8px;
  border-radius:20px;font-size:.68rem;font-weight:700;}}
.qb-value{{font-family:monospace;font-size:.8rem;}}
.qb-meta{{color:#94a3b8;font-size:.73rem;}}

/* ════════════ FOOTER ════════════ */
.footer{{text-align:center;padding:18px;font-size:.68rem;color:#94a3b8;
  border-top:1px solid #e2e8f0;margin-top:20px;}}

/* ════════════ SCROLLBARS ════════════ */
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-track{{background:#f1f5f9;}}
::-webkit-scrollbar-thumb{{background:#cbd5e1;border-radius:3px;}}

/* ════════════ RESPONSIVE ════════════ */
@media(max-width:768px){{
  .sidebar{{width:220px;}}
  .content-pane{{padding:12px;}}
  .forensic-heading{{font-size:2rem;}}
  .forensic-logo{{max-height:54px;}}
}}
</style>
</head>
<body>
<div class="report-container">

<!-- ════════════ SIDEBAR ════════════ -->
<div class="sidebar">
  <div class="sidebar-header">
    <h2>🔍 Forensic Report</h2>
    <p>Digital Evidence Analysis</p>
  </div>
  <div class="artifact-buttons" id="sidebar-buttons">
    <button class="artifact-btn active" onclick="showSummary(this)">
      📊 <span>Case Summary</span>
    </button>
    <button class="artifact-btn" onclick="showTimeline(this)">
      🕐 <span>Activity Timeline</span>
      <span class="badge">{total_timeline}</span>
    </button>
  </div>
  <div class="sidebar-footer">
    Generated: {now_str}<br>
    Host: {_esc(hostname)}<br>
    OS: {_esc(os_name)}<br>
    Total Artifacts: {total}
  </div>
</div>

<!-- ════════════ MAIN CONTENT ════════════ -->
<div class="main-content">
<div class="content-pane">

  <!--
  ╔══════════════════════════════════════════════╗
  ║  FORENSICCHAT HEADER — always rendered first ║
  ╚══════════════════════════════════════════════╝
  Row 1: "ForensicChat" in large bold gradient text
  Row 2: subtitle (left)  +  logo image (right)
  -->
  <div class="forensic-header">

    <div class="forensic-brand-row">
      <div class="forensic-heading">ForensicChat</div>
    </div>

    <div class="forensic-meta-row">
      <div class="forensic-sub">
        <strong>{_esc(title)}</strong><br>
        Generated: {now_str}&nbsp;·&nbsp;
        Host: {_esc(hostname)}&nbsp;·&nbsp;
        OS: {_esc(os_name)}<br>
        <span class="accent">
          {total} total artifacts&nbsp;·&nbsp;{total_timeline} timeline events
        </span>
      </div>
      {logo_tag}
    </div>

  </div><!-- /forensic-header -->

  {query_banner}

  <!-- ════════ SUMMARY VIEW ════════ -->
  <div id="view-summary">
    <div class="cards-grid">{cards_html}</div>
    <div class="exec-summary">
      <h3>📌 Executive Summary</h3>
      <ul>{findings_html}</ul>
    </div>
  </div>

  <!-- ════════ TIMELINE VIEW ════════ -->
  <div id="view-timeline" style="display:none;">
    <div class="timeline-section">
      <h3>🕐 Complete Activity Timeline — All Data (Oldest → Latest)</h3>
      <div class="timeline-controls">
        <input class="tl-search" type="text" id="tl-search"
               placeholder="Search description, type, detail…"
               oninput="filterTimeline()">
        <select class="tl-filter" id="tl-type-filter" onchange="filterTimeline()">
          <option value="">All Event Types</option>
          <option>Web Visit</option>
          <option>Program Executed</option>
          <option>File Accessed</option>
          <option>USB Device</option>
          <option>System Event</option>
          <option>System Log</option>
        </select>
        <span id="tl-count-footer" style="font-size:.74rem;color:#64748b;"></span>
      </div>
      <div class="timeline-table-wrap">
        <table class="timeline-table">
          <thead><tr>
            <th>Date &amp; Time (DD/MM/YYYY HH:MM:SS)</th>
            <th></th>
            <th>Event Type</th>
            <th>Description</th>
            <th>Detail</th>
          </tr></thead>
          <tbody id="tl-tbody">{timeline_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ════════ ARTIFACT DETAIL VIEW ════════ -->
  <div id="artifact-container"></div>

</div><!-- /content-pane -->

<div class="footer">
  ForensicAssist — Professional Edition &nbsp;|&nbsp;
  Report generated {now_str} &nbsp;|&nbsp;
  All data is stored locally and remains confidential.
</div>
</div><!-- /main-content -->
</div><!-- /report-container -->

<!-- ════════════════════════════════════════════════════════
     CLIENT-SIDE JAVASCRIPT
     Data is already embedded and pre-formatted in Python.
     The JS table renderer uses the display string (e.g.
     "29/04/2026 13:32:44") stored in item[col], and uses
     item[col+"_raw"] ONLY for date-range cutoff maths.
════════════════════════════════════════════════════════ -->
<script>
const artifactData = {sj};

/* ── Build sidebar artifact buttons ── */
(function () {{
  const container = document.getElementById('sidebar-buttons');
  for (const sec of artifactData) {{
    const btn = document.createElement('button');
    btn.className = 'artifact-btn';
    btn.innerHTML =
      '<span>' + sec.name + '</span>' +
      '<span class="badge">' + sec.count + '</span>';
    btn.addEventListener('click', function () {{
      setActive(this);
      renderArtifact(sec.id);
    }});
    container.appendChild(btn);
  }}
}})();

function setActive(btn) {{
  document.querySelectorAll('.artifact-btn')
          .forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}}

/* ── View switchers ── */
function showSummary(btn) {{
  if (btn) setActive(btn);
  document.getElementById('view-summary').style.display   = '';
  document.getElementById('view-timeline').style.display  = 'none';
  document.getElementById('artifact-container').innerHTML = '';
}}

function showTimeline(btn) {{
  if (btn) setActive(btn);
  document.getElementById('view-summary').style.display   = 'none';
  document.getElementById('view-timeline').style.display  = '';
  document.getElementById('artifact-container').innerHTML = '';
  const n = document.querySelectorAll('#tl-tbody tr').length;
  document.getElementById('tl-count-footer').textContent =
    'Showing all ' + n + ' events — oldest to latest (DD/MM/YYYY HH:MM:SS).';
}}

/* ── Timeline filter ── */
function filterTimeline() {{
  const q    = (document.getElementById('tl-search').value || '').toLowerCase();
  const type = (document.getElementById('tl-type-filter').value || '').toLowerCase();
  const rows = document.querySelectorAll('#tl-tbody tr');
  let shown  = 0;
  rows.forEach(tr => {{
    const text     = tr.textContent.toLowerCase();
    const typeCell = tr.cells[2] ? tr.cells[2].textContent.toLowerCase() : '';
    const ok = (!q || text.includes(q)) && (!type || typeCell.includes(type));
    tr.style.display = ok ? '' : 'none';
    if (ok) shown++;
  }});
  document.getElementById('tl-count-footer').textContent =
    'Showing ' + shown + ' of ' + rows.length + ' events.';
}}

/* ── Artifact renderer ── */
let _sec = null;

function renderArtifact(id) {{
  document.getElementById('view-summary').style.display   = 'none';
  document.getElementById('view-timeline').style.display  = 'none';
  _sec = artifactData.find(s => s.id === id);
  if (!_sec) return;

  document.getElementById('artifact-container').innerHTML =
    '<div class="artifact-view">' +
      '<div class="artifact-view-header">' +
        '<div>' +
          '<div class="artifact-title">' + _sec.name + '</div>' +
          '<div class="artifact-meta">All ' + _sec.count +
            ' records — sorted oldest → latest (DD/MM/YYYY HH:MM:SS)</div>' +
        '</div>' +
        '<div class="filter-bar">' +
          '<label>📅 Date:</label>' +
          '<select class="filter-select" id="art-date" onchange="applyFilter()">' +
            '<option value="0">All data</option>' +
            '<option value="7">Last 7 days</option>' +
            '<option value="14">Last 14 days</option>' +
            '<option value="30">Last 30 days</option>' +
            '<option value="90">Last 90 days</option>' +
          '</select>' +
          '<label>🔍</label>' +
          '<input class="filter-input" type="text" id="art-search"' +
            ' placeholder="Search…" oninput="applyFilter()">' +
        '</div>' +
      '</div>' +
      '<div class="record-count" id="art-cnt"></div>' +
      '<div class="table-wrapper"><div id="art-tbl"></div></div>' +
    '</div>';

  applyFilter();
}}

/* ── Filter + render table ──
   CRITICAL: display values (item[col]) are already formatted
   as "DD/MM/YYYY HH:MM:SS" by Python.  We show those directly.
   item[col+"_raw"] is the original ISO string used ONLY for
   the date-range cutoff calculation.
── */
function applyFilter() {{
  if (!_sec) return;

  const days  = parseInt(
    (document.getElementById('art-date')   || {{value:'0'}}).value
  );
  const query = (
    (document.getElementById('art-search') || {{value:''}}).value || ''
  ).toLowerCase();

  let rows = _sec.items.slice();   // already sorted ascending by Python

  /* ── Date-range filter (uses _raw ISO value for maths) ── */
  if (days > 0) {{
    const cutoff = Date.now() - days * 86400000;
    const tsf    = _sec.timestamp_field;
    rows = rows.filter(item => {{
      const raw = item[tsf + '_raw'] || '';
      if (!raw || raw === '—') return true;           // keep undated rows
      const ms  = new Date(raw.replace('T', ' ')).getTime();
      return isNaN(ms) || ms >= cutoff;
    }});
  }}

  /* ── Text search (searches display values) ── */
  if (query) {{
    rows = rows.filter(item =>
      Object.values(item).some(v => String(v).toLowerCase().includes(query))
    );
  }}

  /* ── Count badge ── */
  const cnt = document.getElementById('art-cnt');
  if (cnt) cnt.textContent =
    'Showing ' + rows.length + ' of ' + _sec.count + ' records';

  const tbl = document.getElementById('art-tbl');
  if (!tbl) return;

  if (!rows.length) {{
    tbl.innerHTML = '<div class="empty-message">No records match the filter.</div>';
    return;
  }}

  /* ── Column selection ── */
  const allKeys = Object.keys(rows[0]).filter(k => !k.endsWith('_raw') && k !== 'id');
  let cols      = _sec.columns.filter(c => allKeys.includes(c));
  if (!cols.length) cols = allKeys.slice(0, 8);

  /* ── Header ── */
  const hdr = cols.map(c =>
    '<th>' + c.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase()) + '</th>'
  ).join('');

  /* ── Data rows ──
     item[col] is already "DD/MM/YYYY HH:MM:SS" for timestamp columns.
     We show it directly — no further transformation needed.
  ── */
  const bdy = rows.map(item => {{
    const cells = cols.map(c => {{
      const v    = String(item[c] !== undefined ? item[c] : '');
      const disp = v.length > 90 ? v.slice(0, 90) + '…' : v;
      return '<td title="' + v.replace(/"/g, '&quot;') + '">' + disp + '</td>';
    }}).join('');
    return '<tr>' + cells + '</tr>';
  }}).join('');

  tbl.innerHTML =
    '<table class="data-table">' +
    '<thead><tr>' + hdr + '</tr></thead>' +
    '<tbody>' + bdy + '</tbody>' +
    '</table>';
}}
</script>
</body>
</html>"""