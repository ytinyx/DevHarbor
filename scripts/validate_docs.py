"""Validate repository documentation and visual assets without network access.

Run from any directory with Python 3.11+: python scripts/validate_docs.py
The checker supports the Markdown/HTML link forms used in this repository. It is
not a Markdown renderer; external URLs are deliberately left to manual review.
"""

from __future__ import annotations

import argparse
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import struct
import sys
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


def without_code_blocks(text: str) -> str:
    """Keep line numbers while removing fenced/indented code and HTML comments."""
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m[0].count("\n"), text, flags=re.S)
    lines, fence = [], None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*$", line):
                fence = None
            lines.append("\n" if line.endswith("\n") else "")
        elif match:
            fence = (match[1][0], len(match[1]))
            lines.append("\n" if line.endswith("\n") else "")
        elif line.startswith(("    ", "\t")):
            lines.append("\n" if line.endswith("\n") else "")
        else:
            lines.append(line)
    return "".join(lines)


def without_inline_code(text: str) -> str:
    return re.sub(r"(`+)(?!`)(.*?)\1(?!`)", lambda m: " " * len(m[0]), text, flags=re.S)


def heading_slug(value: str) -> str:
    """GitHub-style Unicode heading IDs for ordinary Markdown headings."""
    code_spans = []

    def protect_code(match: re.Match[str]) -> str:
        code_spans.append(match[2])
        return f"\x00{len(code_spans) - 1}\x00"

    value = re.sub(r"(`+)(?!`)(.*?)\1(?!`)", protect_code, value)
    value = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<[^>]*>", "", value)
    value = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])", r"\1", value)
    value = re.sub(r"(?<!\w)(_{1,3})(\S(?:.*?\S)?)\1(?!\w)", r"\2", value)
    value = re.sub(r"\x00(\d+)\x00", lambda match: code_spans[int(match[1])], value)
    value = unescape(value).lower().strip()
    # GitHub retains Unicode letters/numbers/combining marks, '-' and '_'.
    # Backticks/emphasis punctuation and emoji do not contribute to the ID.
    value = "".join(
        char for char in value
        if char in "-_ " or unicodedata.category(char)[0] in "LNM"
    )
    return value.replace(" ", "-")


class HTMLReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[int, str]] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        for name in ("id", "name" if tag == "a" else "id"):
            if attributes.get(name):
                self.anchors.add(attributes[name])
        for name in ("href", "src", "poster"):
            if attributes.get(name):
                self.links.append((self.getpos()[0], attributes[name]))
        if attributes.get("srcset"):
            for candidate in attributes["srcset"].split(","):
                if candidate.strip():
                    self.links.append((self.getpos()[0], candidate.strip().split()[0]))


def markdown_anchors(text: str) -> set[str]:
    clean = without_code_blocks(text)
    parser = HTMLReferences()
    parser.feed(without_inline_code(clean))
    anchors, seen = set(parser.anchors), set()
    lines = clean.splitlines()
    for number, line in enumerate(lines):
        match = re.match(r"^ {0,3}#{1,6}(?:\s+|$)(.*?)(?:\s+#+\s*)?$", line)
        heading = match[1] if match else None
        if heading is None and number + 1 < len(lines) and line.strip():
            if re.match(r"^ {0,3}(?:=+|-+)\s*$", lines[number + 1]):
                heading = line.strip()
        if heading is None:
            continue
        base = heading_slug(heading)
        slug, duplicate = base, 0
        while slug in seen:
            duplicate += 1
            slug = f"{base}-{duplicate}"
        seen.add(slug)
        anchors.add(slug)
    return anchors


def destination(text: str, start: int) -> tuple[str, int] | None:
    """Read a CommonMark-style link destination, including balanced parentheses."""
    while start < len(text) and text[start].isspace():
        start += 1
    if start == len(text):
        return None
    if text[start] == "<":
        end = text.find(">", start + 1)
        return (text[start + 1:end], end + 1) if end >= 0 else None
    end, depth = start, 0
    while end < len(text):
        char = text[end]
        if char == "\\" and end + 1 < len(text):
            end += 2
            continue
        if char.isspace() and depth == 0:
            break
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        end += 1
    return text[start:end], end


def reference_key(label: str) -> str:
    return " ".join(label.split()).casefold()


def markdown_links(text: str) -> list[tuple[int, str]]:
    clean = without_inline_code(without_code_blocks(text))
    parser = HTMLReferences()
    parser.feed(clean)
    links = list(parser.links)
    definitions = {}
    definition_spans = []
    for match in re.finditer(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*", clean, re.M):
        found = destination(clean, match.end())
        if found:
            definitions[reference_key(match[1])] = found[0]
            links.append((clean.count("\n", 0, match.start()) + 1, found[0]))
            definition_spans.append((match.start(), found[1]))
    # Inline links and images can contain nested brackets in their label.
    index = 0
    while index < len(clean):
        if clean[index] != "[" or (index > 0 and clean[index - 1] == "\\"):
            index += 1
            continue
        if any(start <= index < end for start, end in definition_spans):
            index += 1
            continue
        end, depth = index + 1, 1
        while end < len(clean) and depth:
            if clean[end] == "\\":
                end += 2
                continue
            depth += (clean[end] == "[") - (clean[end] == "]")
            end += 1
        if depth:
            index += 1
            continue
        label = clean[index + 1:end - 1]
        if "[" in label:
            offset = clean.count("\n", 0, index)
            links.extend((offset + line, value) for line, value in markdown_links(label))
        value = None
        if end < len(clean) and clean[end] == "(":
            found = destination(clean, end + 1)
            if found:
                value, end = found
        elif end < len(clean) and clean[end] == "[":
            close = clean.find("]", end + 1)
            if close >= 0:
                key = clean[end + 1:close] or label
                value = definitions.get(reference_key(key))
                end = close + 1
        else:
            value = definitions.get(reference_key(label))
        if value is not None:
            links.append((clean.count("\n", 0, index) + 1, value))
        index = end
    return links


def check_svg(path: Path) -> list[str]:
    errors = []
    try:
        raw = path.read_text(encoding="utf-8")
        if re.search(r"<!DOCTYPE|<!ENTITY", raw, re.I):
            return ["SVG must not contain DOCTYPE/entity declarations"]
        root = ET.fromstring(raw)
    except (OSError, UnicodeError, ET.ParseError) as error:
        return [f"invalid SVG XML: {error}"]
    if root.tag.split("}")[-1] != "svg":
        errors.append("SVG root element is missing")
    ids = {node.attrib["id"] for node in root.iter() if "id" in node.attrib}
    markers = {node.attrib.get("id") for node in root.iter() if node.tag.split("}")[-1] == "marker"}
    for node in root.iter():
        tag = node.tag.split("}")[-1].lower()
        if tag in {"script", "foreignobject"}:
            errors.append(f"forbidden SVG element: {tag}")
        for name, value in node.attrib.items():
            name = name.split("}")[-1].lower()
            if name.startswith("on"):
                errors.append(f"forbidden SVG event attribute: {name}")
            if name in {"href", "src"} and value and not value.startswith("#"):
                errors.append(f"external SVG resource: {value}")
            if name == "href" and value.startswith("#") and value[1:] not in ids:
                errors.append(f"missing SVG target: {value}")
            if name.startswith("marker-"):
                for marker in re.findall(r"url\(\s*['\"]?#([^)'\"\s]+)", value):
                    if marker not in markers:
                        errors.append(f"missing SVG marker: {marker}")
    for reference in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", raw, re.I):
        if not reference.startswith("#"):
            errors.append(f"external SVG CSS resource: {reference}")
        elif reference[1:] not in ids:
            errors.append(f"missing SVG resource ID: {reference}")
    if re.search(r"@import\b", raw, re.I):
        errors.append("external SVG CSS @import is forbidden")
    return sorted(set(errors))


def check_bitmap(path: Path) -> list[str]:
    data = path.read_bytes()
    if path.suffix.lower() == ".png":
        if len(data) < 45 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            return ["invalid or empty PNG signature/IHDR"]
        if not all(struct.unpack(">II", data[16:24])) or data[-12:-8] != b"\x00\x00\x00\x00" or data[-8:-4] != b"IEND":
            return ["PNG has invalid dimensions or is missing its IEND trailer"]
    elif len(data) < 20 or not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
        return ["invalid, empty, or incomplete JPEG signature"]
    return []


def validate(root: Path) -> tuple[list[str], dict[str, int]]:
    root = root.resolve()
    errors = []
    counts = {"markdown": 0, "local_links": 0, "external_links_skipped": 0, "svg": 0, "bitmaps": 0}
    markdown = [root / name for name in ("README.md", "SECURITY.md", "VERSIONS.md")]
    markdown += sorted((root / "docs").rglob("*.md"))
    texts, anchors = {}, {}
    for path in markdown:
        try:
            texts[path] = path.read_text(encoding="utf-8-sig")
            anchors[path] = markdown_anchors(texts[path])
            counts["markdown"] += 1
        except (OSError, UnicodeError) as error:
            errors.append(f"{path.relative_to(root).as_posix()}: cannot read UTF-8 Markdown: {error}")
    for path, text in texts.items():
        for line, raw in markdown_links(text):
            location = f"{path.relative_to(root).as_posix()}:{line}"
            value = unescape(re.sub(r"\\([\\()<> ])", r"\1", raw))
            try:
                parsed = urlsplit(value)
            except ValueError as error:
                errors.append(f"{location}: malformed link {raw!r}: {error}")
                continue
            if parsed.scheme or parsed.netloc:
                counts["external_links_skipped"] += 1
                continue
            counts["local_links"] += 1
            target_path = unquote(parsed.path)
            target = ((root / target_path.lstrip("/")) if target_path.startswith("/") else (path.parent / target_path)).resolve() if target_path else path
            if not target.is_relative_to(root):
                errors.append(f"{location}: link escapes repository: {raw}")
                continue
            if not target.exists():
                errors.append(f"{location}: missing local target: {raw}")
                continue
            fragment = unquote(parsed.fragment)
            if not fragment or target.is_dir():
                continue
            if target.suffix.lower() == ".md":
                if target not in anchors:
                    anchors[target] = markdown_anchors(target.read_text(encoding="utf-8-sig"))
                if fragment not in anchors[target]:
                    errors.append(f"{location}: missing Markdown anchor: {raw}")
            elif target.suffix.lower() == ".svg":
                try:
                    ids = {node.attrib.get("id") for node in ET.parse(target).iter()}
                    if fragment not in ids:
                        errors.append(f"{location}: missing SVG anchor: {raw}")
                except ET.ParseError:
                    pass  # The asset pass reports the XML error.
            else:
                line_anchor = re.fullmatch(r"L(\d+)(?:-L(\d+))?", fragment)
                if not line_anchor:
                    errors.append(f"{location}: unsupported local file anchor: {raw}")
                else:
                    start, end = int(line_anchor[1]), int(line_anchor[2] or line_anchor[1])
                    try:
                        line_count = len(target.read_text(encoding="utf-8-sig").splitlines())
                        if not 1 <= start <= end <= line_count:
                            errors.append(f"{location}: invalid source line anchor: {raw}")
                    except UnicodeError:
                        errors.append(f"{location}: line anchor targets a binary file: {raw}")
    for path in sorted((root / "docs" / "assets").rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".svg":
            counts["svg"] += 1
            problems = check_svg(path)
        elif suffix in {".png", ".jpg", ".jpeg"}:
            counts["bitmaps"] += 1
            problems = check_bitmap(path)
        else:
            continue
        errors.extend(f"{path.relative_to(root).as_posix()}: {problem}" for problem in problems)
    return sorted(set(errors)), counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="repository root (defaults to the script's parent repository)")
    args = parser.parse_args()
    errors, counts = validate(args.root)
    summary = ", ".join(f"{key}={value}" for key, value in counts.items())
    if errors:
        print(f"Documentation validation FAILED: {len(errors)} problem(s); {summary}")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"Documentation validation PASSED: {summary}")
    print("External URLs were not fetched; image checks verify file structure, not visual layout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
