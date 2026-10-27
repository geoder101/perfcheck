"""Validate the trusted Pages artifact; event authorization stays inline in Actions."""

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Never, override
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True, slots=True)
class PagesValidationError(Exception):
    """Identify the artifact entry that prevents safe Pages publication."""

    path: Path
    reason: str

    @override
    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


class _Links(HTMLParser):
    """Accumulate local links and resource paths from parser callbacks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.targets: list[tuple[str, bool]] = []
        self.base_override: bool = False

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "base" and any(key == "href" for key, _ in attrs):
            self.base_override = True
        self.targets.extend(
            (value or "", tag == "object" and key == "data")
            for key, value in attrs
            if key in {"href", "src"} or (tag == "object" and key == "data")
        )


def _raise_scan_error(error: OSError) -> Never:
    raise error


def _validate_targets(path: Path, root: Path, links: _Links) -> None:
    if links.base_override:
        raise PagesValidationError(path, "HTML base URL overrides are unsupported")
    for target, local_resource in links.targets:
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            if local_resource:
                raise PagesValidationError(path, f"invalid object resource: {target}")
            continue
        relative = unquote(parsed.path)
        destination = (path.parent / relative).resolve()
        if (
            relative.startswith("/")
            or not destination.is_relative_to(root)
            or not destination.is_file()
        ):
            raise PagesValidationError(path, f"invalid local link: {target}")


def validate_html(root: Path) -> None:
    """Check staged paths and HTML resource destinations, not general HTML validity."""
    if root.is_symlink():
        raise PagesValidationError(root, "HTML root must not be a symlink")
    resolved_root = root.resolve()
    if not (root / "index.html").is_file():
        raise PagesValidationError(root, "missing index.html")
    paths = (
        directory / name
        for directory, directories, files in root.walk(on_error=_raise_scan_error)
        for name in sorted((*directories, *files))
    )
    try:
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(resolved_root):
                raise PagesValidationError(path, "artifact path escapes HTML root")
            if path.suffix != ".html" or not path.is_file():
                continue
            links = _Links()
            links.feed(path.read_text(encoding="utf-8"))
            _validate_targets(path, resolved_root, links)
    except (OSError, ValueError) as error:
        raise PagesValidationError(root, str(error)) from error


if __name__ == "__main__":
    validate_html(Path("docs/_build/html"))
