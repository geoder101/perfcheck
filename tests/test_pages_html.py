from __future__ import annotations

import errno
import os
from typing import TYPE_CHECKING, Never

import pytest
from tools import pages_authorization

if TYPE_CHECKING:
    from pathlib import Path


def test_pages_html_accepts_relative_project_site_assets(tmp_path: Path) -> None:
    # Given: prebuilt documentation with a nested page and local CSS.
    (tmp_path / "nested").mkdir()
    _ = (tmp_path / "style.css").write_text("body {}")
    _ = (tmp_path / "index.html").write_text('<a href="nested/page.html">Page</a>')
    _ = (tmp_path / "nested/page.html").write_text(
        '<link href="../style.css"><a href="../index.html#top">Home</a>'
    )
    # When: the exact uploader root is validated.
    pages_authorization.validate_html(tmp_path)
    # Then: validation accepts the project-site-relative links without rewrites.
    assert (tmp_path / "nested/page.html").read_text().startswith('<link href="../')


@pytest.mark.parametrize(
    "link", ["/style.css", "../outside", "%2e%2e/outside", "missing.css"]
)
def test_pages_html_rejects_invalid_local_assets(link: str, tmp_path: Path) -> None:
    # Given: an HTML page with a missing or escaping resource.
    _ = (tmp_path / "index.html").write_text(f'<script src="{link}"></script>')
    # When: validation checks local resource destinations.
    # Then: a broken artifact fails before upload.
    with pytest.raises(pages_authorization.PagesValidationError):
        pages_authorization.validate_html(tmp_path)


def test_pages_html_requires_landing_page(tmp_path: Path) -> None:
    # Given: an empty output directory after an unsuccessful build.
    # When: validation checks the artifact root.
    # Then: an empty directory cannot be presented as a successful build.
    with pytest.raises(pages_authorization.PagesValidationError):
        pages_authorization.validate_html(tmp_path)


def test_pages_html_rejects_symlinks(tmp_path: Path) -> None:
    # Given: an artifact entry redirected outside the trusted HTML tree.
    _ = (tmp_path / "index.html").write_text("Landing")
    try:
        (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)
    except OSError as error:
        if os.name == "nt" and error.winerror == 1314:
            pytest.skip("Windows symlink privilege is unavailable")
        raise
    # When: all staged paths are checked before the official uploader runs.
    # Then: symlinks cannot silently omit or expose artifact content.
    with pytest.raises(pages_authorization.PagesValidationError):
        pages_authorization.validate_html(tmp_path)


def test_pages_html_rejects_enumeration_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a landing page but an inaccessible artifact directory scan.
    _ = (tmp_path / "index.html").write_text("Landing")

    def inaccessible(_path: Path) -> Never:
        raise PermissionError(errno.EACCES, "controlled artifact scan failure")

    # When: the OS refuses directory enumeration during validation.
    # Then: the validator must not mistake an unreadable tree for an empty one.
    with monkeypatch.context() as context:
        context.setattr(os, "scandir", inaccessible)
        with pytest.raises(pages_authorization.PagesValidationError):
            pages_authorization.validate_html(tmp_path)


@pytest.mark.parametrize("target", ["http://[", "%00invalid"])
def test_pages_html_reports_malformed_destinations(target: str, tmp_path: Path) -> None:
    # Given: malformed URL/path input in a trusted build's output.
    _ = (tmp_path / "index.html").write_text(f'<a href="{target}">Broken</a>')
    # When: artifact validation parses the destination.
    # Then: it fails with an artifact-context error, not a misleading success.
    with pytest.raises(pages_authorization.PagesValidationError):
        pages_authorization.validate_html(tmp_path)


def test_pages_html_reports_invalid_encoding(tmp_path: Path) -> None:
    # Given: unreadable HTML bytes instead of Sphinx's UTF-8 output.
    _ = (tmp_path / "index.html").write_bytes(b"\xff")
    # When: artifact validation reads the page.
    # Then: the invalid artifact fails with contextual validation evidence.
    with pytest.raises(pages_authorization.PagesValidationError):
        pages_authorization.validate_html(tmp_path)


@pytest.mark.parametrize(
    "target",
    [
        "missing.svg",
        "../escape.svg",
        "/root.svg",
        "https://example.com/a.svg",
        "//example.com/a.svg",
        "",
    ],
)
def test_pages_html_rejects_invalid_object_resources(
    target: str, tmp_path: Path
) -> None:
    # Given: an SVG object that is missing, escaping, or externally hosted.
    _ = (tmp_path / "index.html").write_text(
        f'<object data="{target}" type="image/svg+xml"></object>'
    )
    # When/Then: resource validation fails before publication.
    with pytest.raises(pages_authorization.PagesValidationError):
        pages_authorization.validate_html(tmp_path)


def test_pages_html_accepts_local_svg_object(tmp_path: Path) -> None:
    # Given: build-time Mermaid output and an ordinary external navigation link.
    _ = (tmp_path / "diagram.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"/>'
    )
    _ = (tmp_path / "index.html").write_text(
        '<object data="diagram.svg"></object><a href="https://example.com">Link</a>'
    )
    # When: the artifact is validated.
    pages_authorization.validate_html(tmp_path)
    # Then: local diagrams and external navigation remain supported.


@pytest.mark.parametrize("base", ["https://example.com/", "//example.com/", "../"])
def test_pages_html_rejects_base_url_overrides(base: str, tmp_path: Path) -> None:
    # Given: a real local SVG whose browser URL would be changed by HTML base.
    _ = (tmp_path / "diagram.svg").write_text("<svg/>")
    _ = (tmp_path / "index.html").write_text(
        f'<base href="{base}"><object data="diagram.svg"></object>'
    )
    # When/Then: a generated site cannot redirect validated resources elsewhere.
    with pytest.raises(pages_authorization.PagesValidationError):
        pages_authorization.validate_html(tmp_path)
