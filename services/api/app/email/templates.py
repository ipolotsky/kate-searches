"""Рендер HTML писем: единый layout + Jinja2, автоэкранирование данных (title/lines/labels).

Контент (subject/title/строки/CTA) собирает notifications.py, здесь только вёрстка. Строки тела
экранируются (autoescape), поэтому в них безопасно подставлять имена бренда/пользователя.
"""

from jinja2 import Environment, select_autoescape

_env = Environment(autoescape=select_autoescape(["html"]))

_UNSUBSCRIBE = {
    "en": ("You get this because you use KateSearches.", "Unsubscribe"),
    "ru": ("Вы получили это письмо как пользователь KateSearches.", "Отписаться"),
}

_LAYOUT = _env.from_string(
    """<!doctype html>
<html lang="{{ locale }}"><body style="margin:0;background:#f3f4f6;padding:24px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:32px;">
<tr><td>
<h1 style="margin:0 0 16px;font-size:20px;color:#111827;">{{ title }}</h1>
{% for line in lines %}<p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#374151;">{{ line }}</p>{% endfor %}
{% if cta_url %}<p style="margin:24px 0 0;"><a href="{{ cta_url }}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px;">{{ cta_label }}</a></p>{% endif %}
{% if unsubscribe_url %}<p style="margin:28px 0 0;font-size:12px;color:#9ca3af;">{{ unsubscribe_note }} <a href="{{ unsubscribe_url }}" style="color:#9ca3af;">{{ unsubscribe_label }}</a></p>{% endif %}
</td></tr></table></td></tr></table>
</body></html>"""
)


def render_html(
    *,
    locale: str,
    title: str,
    lines: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    unsubscribe_url: str | None = None,
) -> str:
    note, label = _UNSUBSCRIBE.get(locale, _UNSUBSCRIBE["en"])
    return _LAYOUT.render(
        locale=locale,
        title=title,
        lines=lines,
        cta_label=cta_label,
        cta_url=cta_url,
        unsubscribe_url=unsubscribe_url,
        unsubscribe_note=note,
        unsubscribe_label=label,
    )
