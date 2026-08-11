"""Where local packages may be read from, and the URL each tree is served at (ADR-0035).

The path-and-locator half of the dev intake, kept apart from the endpoints that use it:
which roots are declared, whether an operator's path stays inside one, and the locator base
a package under it registers with. No database, no HTTP, no FastAPI — `main.py` reads
`mounts()` to serve the roots and the dev router reads the rest.

The built-in `courses` root is not declared in the environment and never moves: locators
registered before this module point at `local_packages_base_url`, and a registered locator
is never rewritten. Every other root is served under `local_sources_base_url/<key>` and
mounted under a prefix disjoint from the built-in one, so no key can shadow a folder inside
`courses/` and no mount depends on the order the composition root registers them in.

The mount paths are fixed here rather than derived from the base URLs. Both can point
somewhere the process is not actually reachable at (a proxy prefix, a different port), and
deriving one from the other would only move that mismatch — the mount probe the dev router
runs before writing is what detects it (ADR-0035 §6).
"""

from dataclasses import dataclass
from pathlib import Path

from app.config import BUILTIN_SOURCE_ROOT, get_settings
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    FilesystemPackageRoot,
    PackageRoot,
)

# The gitignored tree of ADR-0027 §5. `main.py` and `app.cli` know it under their own names;
# a test pins that all three agree, which is cheaper than making the CLI depend on this.
COURSES_DIR = Path(__file__).resolve().parents[5] / "courses"

BUILTIN_MOUNT_PATH = "/packages"
SOURCES_MOUNT_PREFIX = "/sources"


class LocalSourceError(Exception):
    """The path is not one this process may read under the named root."""


@dataclass(frozen=True)
class SourceRoot:
    key: str
    path: Path
    #: Locator prefix for packages under this root, without a trailing slash.
    url_base: str
    #: Where the app serves `path`. Disjoint between roots by construction.
    mount_path: str
    builtin: bool

    @property
    def exists(self) -> bool:
        """Read live, never cached: a root can appear or disappear while the app runs. It
        does not say the tree is *served* — a root created after boot is not mounted until
        the next restart, and only the mount probe can tell."""
        return self.path.is_dir()

    @property
    def mount_name(self) -> str:
        # The built-in name predates ADR-0035 and stays as it was.
        return "local-packages" if self.builtin else f"local-source-{self.key}"


def builtin_root() -> SourceRoot:
    return SourceRoot(
        key=BUILTIN_SOURCE_ROOT,
        path=COURSES_DIR,
        url_base=get_settings().local_packages_base_url.rstrip("/"),
        mount_path=BUILTIN_MOUNT_PATH,
        builtin=True,
    )


def configured_roots() -> list[SourceRoot]:
    """Every root this process may read from, the built-in one first."""
    sources_base = get_settings().local_sources_base_url.rstrip("/")
    return [builtin_root()] + [
        SourceRoot(
            key=key,
            path=Path(path),
            url_base=f"{sources_base}/{key}",
            mount_path=f"{SOURCES_MOUNT_PREFIX}/{key}",
            builtin=False,
        )
        for key, path in get_settings().declared_source_roots
    ]


def root_for(key: str) -> SourceRoot | None:
    return next((root for root in configured_roots() if root.key == key), None)


def mounts() -> list[SourceRoot]:
    """The roots that exist right now — what the composition root serves. A declared root
    whose directory is missing is skipped, not fatal: the same reasoning that keeps a
    checkout without `courses/` booting (ADR-0035 §2)."""
    return [root for root in configured_roots() if root.exists]


def resolve(root: SourceRoot, relative: str) -> Path:
    """A directory inside `root`, or a refusal. `relative` is operator input: it is checked
    against the resolved root, so `..`, an absolute path and a symlink out all fail here."""
    base = root.path.resolve()
    candidate = (base / relative.strip().lstrip("/\\")).resolve()
    if candidate != base and base not in candidate.parents:
        raise LocalSourceError(f"'{relative}' is not inside the '{root.key}' source root")
    if not candidate.is_dir():
        raise LocalSourceError(f"'{relative}' is not a directory under the '{root.key}' root")
    return candidate


def relative_to(root: SourceRoot, directory: Path) -> str:
    """`directory` as a posix path relative to the root — "" for the root itself."""
    relative = directory.resolve().relative_to(root.path.resolve()).as_posix()
    return "" if relative == "." else relative


def locator_base(root: SourceRoot, relative: str) -> str:
    return f"{root.url_base}/{relative}" if relative else root.url_base


def package_root(root: SourceRoot, relative: str) -> FilesystemPackageRoot:
    """One package directory, ready to discover: its bytes come off the filesystem while
    the locators it registers point into the mount, which is what makes them fetchable for
    the brief intake and profiling later (ADR-0027 §5)."""
    directory = resolve(root, relative)
    return FilesystemPackageRoot(
        directory, locator_base=locator_base(root, relative_to(root, directory))
    )


def fixed_root(root: PackageRoot):
    """A `PackageDiscovery` root factory that ignores the source locator — the package root
    is already built. (The CLI's own copy of this closure stays where it is.)"""

    def factory(_: str) -> PackageRoot:
        return root

    return factory
