"""HTML helpers for the v2 design page."""
import html
import re


def md(t):
    """Escape text; `code` -> mono span; **bold** -> strong; [[chip:kind|label]] -> chip."""
    t = html.escape(str(t), quote=False)
    t = re.sub(r"\[\[(\w+)\|([^\]]+)\]\]", lambda m: chip(m.group(1), m.group(2)), t)
    t = re.sub(r"`([^`]+)`", r'<span class="mono">\1</span>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t


def chip(kind, label=None):
    label = label or kind
    return f'<span class="chip {kind}">{html.escape(label)}</span>'


def pend(t="pending"):
    return f'<span class="pend">{html.escape(t)}</span>'


def table(headers, rows, caption=None, num=(), wide=(), mid=(), raw=False):
    """rows: list of lists of strings (md-lite unless raw=True). num: col indexes right-aligned."""
    th = "".join(
        f'<th class="num">{md(h)}</th>' if i in num else f"<th>{md(h)}</th>"
        for i, h in enumerate(headers)
    )
    out = [f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>']
    for r in rows:
        tds = []
        for i, c in enumerate(r):
            cell = c if raw else md(c)
            cls = []
            if i in num:
                cls.append("num")
            if i in wide:
                cls.append("wide")
            if i in mid:
                cls.append("mid")
            tds.append(f'<td{" class=%s" % chr(34).join(["", " ".join(cls), ""]) if cls else ""}>{cell}</td>')
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</tbody>")
    if caption:
        out.append(f"<caption>{md(caption)}</caption>")
    out.append("</table></div>")
    return "".join(out)


def card(title, badges, fields, note=None, open_=True):
    """Configuration card: <details> with a definition list."""
    b = " ".join(badges)
    rows = "".join(f"<dt>{md(k)}</dt><dd>{md(v)}</dd>" for k, v in fields)
    n = f'<p class="cardnote">{md(note)}</p>' if note else ""
    return (
        f'<details class="card"{" open" if open_ else ""}><summary><span class="ct">{md(title)}</span> {b}</summary>'
        f'<dl class="kv2">{rows}</dl>{n}</details>'
    )


def kv(rows):
    return '<dl class="kv">' + "".join(f"<dt>{md(k)}</dt><dd>{md(v)}</dd>" for k, v in rows) + "</dl>"


def callout(title, body_html, kind="callout"):
    return f'<div class="{kind}"><strong class="t">{md(title)}</strong>{body_html}</div>'


def p(t):
    return f"<p>{md(t)}</p>"


def ul(items):
    return "<ul>" + "".join(f"<li>{md(i)}</li>" for i in items) + "</ul>"


def h2(id_, t, lede=None):
    l = f'<p class="lede">{md(lede)}</p>' if lede else ""
    return f'<section id="{id_}"><h2>{md(t)}</h2>{l}'


def h3(t):
    return f"<h3>{md(t)}</h3>"
