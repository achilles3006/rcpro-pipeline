"""Write the leads table to one local HTML page with filters, and open it in the browser.

The page holds personal data: it is written to data/ (ignored by git) and never published.
"""

import json
import webbrowser
from pathlib import Path

COLUMNS = ["start_date", "segment", "sales_angle", "mandatory", "legal_form_type", "juridical_form_label", "name",
           "postcode", "municipality", "email", "phone", "website", "site", "site_level", "site_email", "site_phone", "founders", "activity_summary", "evidence", "needs_review",
           "dm_allowed_from_kbo", "enterprise_number"]

# Display only: the table keeps its keys, the page shows clear English labels
# (Belgian legal terms such as BV, NV and eenmanszaak stay as they are).
HEADERS = {
    "start_date": "Start date", "segment": "Segment", "sales_angle": "Sales story",
    "mandatory": "Insurance mandatory", "legal_form_type": "Type", "juridical_form_label": "Legal form",
    "name": "Name", "postcode": "Postcode", "municipality": "Municipality", "email": "Email",
    "phone": "Phone", "website": "Website", "site": "Website found", "site_level": "Match",
    "site_email": "Email on website", "site_phone": "Phone on website",
    "founders": "Founders (deed)", "activity_summary": "Activity (deed)", "evidence": "Evidence", "needs_review": "Needs review",
    "dm_allowed_from_kbo": "Contact allowed (KBO)", "enterprise_number": "Enterprise number",
}
LABELS = {
    "segment": {
        "architects": "Architects", "interior_architects": "Interior architects",
        "urban_landscape": "Urban, garden and landscape architects", "engineers": "Engineers and design offices",
        "land_surveyors": "Land surveyors", "accountants": "Accountants and tax advisers",
        "psychologists": "Psychologists and psychotherapists", "management_consultants": "Management consultants",
        "it_consultants": "IT consultants", "real_estate": "Real estate agents and syndics",
        "insurance_intermediaries": "Insurance intermediaries",
        "dentists": "Dentists and oral care", "doctors": "GPs and medical specialists",
        "paramedics": "Physiotherapists, nurses and other paramedics", "veterinarians": "Veterinarians",
        "technical_testing": "Technical testing (EPB, asbestos?)", "financial_planners": "Financial planners and advisers",
        "recruitment": "Recruitment agencies", "marketing_communication": "Marketing, PR and design",
        "legal_advisers": "Legal advisers (non-lawyers)", "real_estate_appraisers": "Real estate appraisers",
        "legal_collective": "Lawyers, notaries, bailiffs, auditors",
    },
    "sales_angle": {
        "legal_obligation": "Legal obligation", "legal_unconfirmed": "Obligation not confirmed",
        "commercial_need": "Commercial (no obligation)", "no_outreach": "Do not contact",
    },
    "mandatory": {"yes": "Yes", "likely": "Likely", "unlikely": "Unlikely", "unknown": "Unknown"},
    "legal_form_type": {"sole_trader": "Eenmanszaak", "company": "Company"},
}


def write_html(con, path):
    rows = con.execute(f"""
        SELECT {", ".join(COLUMNS)} FROM leads ORDER BY start_date DESC, enterprise_number
    """).fetchall()
    data = [[str(v) if k == "start_date" else "; ".join(v) if k == "evidence" else v
             for k, v in zip(COLUMNS, row)] for row in rows]
    payload = json.dumps({"columns": COLUMNS, "headers": HEADERS, "labels": LABELS, "rows": data}, ensure_ascii=False).replace("</", "<\\/")
    Path(path).write_text(PAGE.replace("__DATA__", payload), encoding="utf-8")
    return len(rows)


def open_html(path):
    webbrowser.open(Path(path).resolve().as_uri())


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RC pro leads</title>
<style>
  :root { --bg: #fff; --fg: #1d1d1f; --muted: #6e6e73; --line: #e5e5ea; --head: #f5f5f7; --accent: #0a66c2; }
  @media (prefers-color-scheme: dark) { :root { --bg: #1c1c1e; --fg: #f2f2f7; --muted: #a1a1a6; --line: #38383a; --head: #2c2c2e; --accent: #64a8ff; } }
  body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg); font: 13px -apple-system, system-ui, sans-serif; }
  h1 { font-size: 18px; margin: 0 0 12px; }
  .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
  select, input[type=search] { font: inherit; padding: 4px 6px; background: var(--bg); color: var(--fg); border: 1px solid var(--line); border-radius: 6px; }
  #count { color: var(--muted); margin-left: auto; }
  .wrap { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: top; }
  th { position: sticky; top: 0; background: var(--head); cursor: pointer; user-select: none; }
  td.wrapok { white-space: normal; min-width: 160px; }
  a { color: var(--accent); }
</style></head><body>
<h1>RC pro leads</h1>
<div class="bar">
  <select id="segment"><option value="">All segments</option></select>
  <select id="sales_angle"><option value="">All sales stories</option></select>
  <select id="mandatory"><option value="">Insurance mandatory: all</option></select>
  <select id="legal_form_type"><option value="">Eenmanszaak and company</option></select>
  <select id="juridical_form_label"><option value="">All legal forms</option></select>
  <label><input type="checkbox" id="dm"> Only contact allowed (KBO)</label>
  <label><input type="checkbox" id="contact"> Has email, phone or website</label>
  <input type="search" id="q" placeholder="Search name, postcode, municipality, number">
  <span id="count"></span>
</div>
<div class="wrap"><table><thead id="head"></thead><tbody id="body"></tbody></table></div>
<script>
const DATA = __DATA__;
const C = DATA.columns, ix = Object.fromEntries(C.map((c, i) => [c, i]));
const LIMIT = 500, FILTERS = ["segment", "sales_angle", "mandatory", "legal_form_type", "juridical_form_label"];
const label = (c, v) => (DATA.labels[c] || {})[v] ?? v;
let sortCol = ix.start_date, sortDesc = true;

for (const f of FILTERS) {
  const sel = document.getElementById(f);
  [...new Set(DATA.rows.map(r => r[ix[f]]))].filter(v => v != null)
    .sort((a, b) => label(f, a).localeCompare(label(f, b), "en"))
    .forEach(v => sel.add(new Option(label(f, v), v)));
  sel.onchange = render;
}
["dm", "contact"].forEach(id => document.getElementById(id).onchange = render);
document.getElementById("q").oninput = render;

document.getElementById("head").innerHTML = "<tr>" + C.map((c, i) => `<th data-i="${i}">${DATA.headers[c]}</th>`).join("") + "</tr>";
document.querySelectorAll("th").forEach(th => th.onclick = () => {
  const i = +th.dataset.i; sortDesc = sortCol === i ? !sortDesc : false; sortCol = i; render();
});

const esc = v => String(v).replace(/[&<>"]/g, ch => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[ch]));
function cell(c, v) {
  if (v == null) return "<td></td>";
  if (c === "enterprise_number")
    return `<td><a target="_blank" href="https://kbopub.economie.fgov.be/kbopub/zoeknummerform.html?nummer=${esc(v.replace(/\\./g, ""))}&actionLu=Zoek">${esc(v)}</a></td>`;
  if (c === "website" || c === "site")
    return "<td>" + v.split("; ").map(w => `<a target="_blank" href="${esc(/^https?:/.test(w) ? w : "https://" + w)}">${esc(w)}</a>`).join("<br>") + "</td>";
  if (c === "email" || c === "site_email") return "<td>" + v.split("; ").map(e => `<a href="mailto:${esc(e)}">${esc(e)}</a>`).join("<br>") + "</td>";
  if (typeof v === "boolean") return `<td>${v ? "yes" : "no"}</td>`;
  if (c === "evidence") v = v.replaceAll(" MAIN", " main").replaceAll(" SECO", " secondary");
  return `<td${["evidence", "name", "founders", "activity_summary"].includes(c) ? ' class="wrapok"' : ""}>${esc(label(c, v))}</td>`;
}

function render() {
  const val = id => document.getElementById(id).value;
  const q = val("q").trim().toLowerCase(), dm = document.getElementById("dm").checked,
        contact = document.getElementById("contact").checked;
  const rows = DATA.rows.filter(r =>
    FILTERS.every(f => !val(f) || r[ix[f]] === val(f)) &&
    (!dm || r[ix.dm_allowed_from_kbo]) &&
    (!contact || ["email", "phone", "website", "site", "site_email", "site_phone"].some(c => r[ix[c]])) &&
    (!q || ["name", "postcode", "municipality", "enterprise_number"].some(f => (r[ix[f]] || "").toLowerCase().includes(q))));
  rows.sort((a, b) => {
    const x = a[sortCol] ?? "", y = b[sortCol] ?? "";
    return (x < y ? -1 : x > y ? 1 : 0) * (sortDesc ? -1 : 1);
  });
  document.getElementById("count").textContent =
    `${rows.length.toLocaleString("en")} leads` + (rows.length > LIMIT ? ` (first ${LIMIT} shown)` : "");
  document.getElementById("body").innerHTML =
    rows.slice(0, LIMIT).map(r => "<tr>" + C.map((c, i) => cell(c, r[i])).join("") + "</tr>").join("");
}
render();
</script></body></html>
"""
