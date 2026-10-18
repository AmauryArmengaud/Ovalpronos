"""
Design quality guard tests — fail if conventions are violated.

Run: python manage.py test apps.matches.tests_quality
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / 'templates'

# Directories/files excluded from style checks.
# Emails use inline hex/style by convention (mail clients don't support CSS vars).
# 500.html is standalone with no Django context processor — inline styles intentional.
# admin/ templates are Django admin overrides, handled separately.
_EXCLUDED_DIRS = {
    'templates/emails',
    'templates/accounts/emails',
    'templates/admin',
}
_EXCLUDED_FILES = {
    'templates/500.html',
}

# Approved inline style="" values: substring match against the style attribute value.
# Each exception must be documented with a reason.
_INLINE_STYLE_EXCEPTIONS = [
    # Progress bar fill: width is dynamic ({% widthratio %}), no static CSS alternative.
    'widthratio',
]


def _app_templates():
    """Yield (path, rel_str) for all non-excluded HTML templates."""
    for path in TEMPLATES_DIR.rglob('*.html'):
        rel = str(path.relative_to(BASE_DIR)).replace('\\', '/')
        if any(rel.startswith(d) for d in _EXCLUDED_DIRS):
            continue
        if rel in _EXCLUDED_FILES:
            continue
        yield path, rel


class InlineStyleTest(SimpleTestCase):
    """No style="" attributes in non-email, non-admin templates.

    Exception: the progress bar fill width (dynamic widthratio value).
    """

    def test_no_inline_styles(self):
        pattern = re.compile(r'\bstyle="([^"]*)"')
        violations = []
        for path, rel in _app_templates():
            content = path.read_text(encoding='utf-8')
            for lineno, line in enumerate(content.splitlines(), 1):
                for m in pattern.finditer(line):
                    value = m.group(1)
                    if any(exc in value for exc in _INLINE_STYLE_EXCEPTIONS):
                        continue
                    violations.append(f'  {rel}:{lineno}: style="{value[:80]}"')
        self.assertFalse(
            violations,
            'Inline style="" attributes found — use CSS classes instead.\n'
            'Exceptions: progress bar width (widthratio).\n'
            + '\n'.join(violations),
        )


class HardcodedColorTest(SimpleTestCase):
    """No hardcoded hex colors in non-email, non-admin templates."""

    def test_no_hex_colors(self):
        # Match #RGB or #RRGGBB not preceded by common non-color contexts (comments, URLs)
        pattern = re.compile(r'(?<![/\w])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b')
        violations = []
        for path, rel in _app_templates():
            content = path.read_text(encoding='utf-8')
            for lineno, line in enumerate(content.splitlines(), 1):
                # Skip HTML comments
                stripped = re.sub(r'<!--.*?-->', '', line)
                if pattern.search(stripped):
                    violations.append(f'  {rel}:{lineno}: {stripped.strip()[:80]}')
        self.assertFalse(
            violations,
            'Hardcoded hex colors found — use CSS variables (var(--color-*)) instead.\n'
            + '\n'.join(violations),
        )


class PoFileQualityTest(SimpleTestCase):
    """No fuzzy entries or empty msgstr for app-level strings in django.po."""

    PO_PATH = BASE_DIR / 'locale' / 'fr' / 'LC_MESSAGES' / 'django.po'

    def _parse_entries(self):
        import polib
        po = polib.pofile(str(self.PO_PATH))
        entries = []
        for entry in po:
            # For plural entries, the translation lives in msgstr_plural, not msgstr
            if entry.msgid_plural:
                translated = bool(entry.msgstr_plural and any(entry.msgstr_plural.values()))
            else:
                translated = bool(entry.msgstr)
            entries.append({
                'flags': list(entry.flags),
                'refs': [f'{f}:{l}' for f, l in entry.occurrences],
                'msgid': entry.msgid,
                'msgstr': entry.msgstr,
                'translated': translated,
            })
        return entries

    def _is_app_ref(self, entry):
        for ref in entry['refs']:
            file_part = ref.split(':')[0]
            if file_part.startswith(('apps/', 'templates/', 'ovalpronos/')):
                return True
        return False

    def test_no_fuzzy_app_entries(self):
        entries = self._parse_entries()
        fuzzy = [
            e for e in entries
            if 'fuzzy' in e['flags'] and self._is_app_ref(e)
        ]
        self.assertFalse(
            fuzzy,
            'Fuzzy entries in django.po — review and remove #, fuzzy flag:\n'
            + '\n'.join(f'  msgid "{e["msgid"]}"' for e in fuzzy),
        )

    def test_no_empty_msgstr_for_app_strings(self):
        entries = self._parse_entries()
        empty = [
            e for e in entries
            if not e['translated'] and self._is_app_ref(e) and e['msgid'] != ''
        ]
        self.assertFalse(
            empty,
            'Empty msgstr for app-level strings — add French translations:\n'
            + '\n'.join(f'  msgid "{e["msgid"]}"' for e in empty),
        )
