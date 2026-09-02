"""Tests for packaging artifacts and configuration parsability.

Validates that every packaging/distribution file committed to the repo
is well-formed and parseable by the tools that consume them. These tests
run in CI as part of the static-checks + unit-test matrix.

Scope: packaging/, scripts/, Dockerfile, docker-compose.yml, pyproject.toml,
requirements.txt, packaging/requirements-lock.txt, packaging/antique.service.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# All paths relative to the project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGING_DIR = PROJECT_ROOT / "packaging"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------

class TestPyProject:
    def test_pyproject_is_valid_toml(self):
        """pyproject.toml must parse without error."""
        try:
            import tomllib
        except ImportError:
            pytest.skip("tomllib not available (Python <3.11)")

        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert "project" in data
        assert data["project"]["name"] == "antique"
        assert "version" in data["project"]
        assert "dependencies" in data["project"]

    def test_pyproject_version_matches_source(self):
        """Version in pyproject.toml must match src.__version__."""
        try:
            import tomllib
        except ImportError:
            pytest.skip("tomllib not available (Python <3.11)")

        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        from src import __version__
        assert data["project"]["version"] == __version__

    def test_pyproject_requires_python_ge_310(self):
        try:
            import tomllib
        except ImportError:
            pytest.skip("tomllib not available")
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert ">=3.10" in data["project"]["requires-python"]


# ---------------------------------------------------------------------------
# requirements.txt + requirements-lock.txt
# ---------------------------------------------------------------------------

class TestRequirements:
    def test_requirements_txt_is_parseable(self):
        """Every non-empty, non-comment line in requirements.txt must be
        a valid pip requirement specifier."""
        req_file = PROJECT_ROOT / "requirements.txt"
        assert req_file.exists(), "requirements.txt missing"

        errors = []
        for i, line in enumerate(req_file.read_text().splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # A valid requirement starts with a package name (letter/digit)
            if not re.match(r"^[a-zA-Z0-9]", stripped):
                errors.append(f"Line {i}: invalid: {stripped}")
        assert not errors, "\n".join(errors)

    def test_lock_file_is_parseable(self):
        """Every non-empty, non-comment line in the lock file must be
        an exact pin (name==version)."""
        lock_file = PACKAGING_DIR / "requirements-lock.txt"
        assert lock_file.exists(), "requirements-lock.txt missing"

        errors = []
        for i, line in enumerate(lock_file.read_text().splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            requirement = stripped.split(";", 1)[0].strip()
            if not re.match(r"^[a-zA-Z0-9_.-]+==[0-9a-zA-Z.+!-]+$", requirement):
                errors.append(f"Line {i}: invalid pin: {stripped}")
        assert not errors, "\n".join(errors)

    def test_lock_file_pins_core_deps(self):
        """The lock file must pin all core dependencies from pyproject.toml."""
        try:
            import tomllib
        except ImportError:
            pytest.skip("tomllib not available")

        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        lock = (PACKAGING_DIR / "requirements-lock.txt").read_text()

        for dep in data["project"]["dependencies"]:
            # Extract package name (before any version specifier or extras)
            name = re.split(r"[>=<~!]", dep, 1)[0].strip()
            # Strip extras like [standard] — the lock pins the base package
            name = name.split("[")[0]
            # camoufox is optional, may not be in lock on all platforms
            if name == "camoufox":
                continue
            # Package names are case-insensitive in pip
            lock_lower = lock.lower()
            assert f"{name.lower()}==" in lock_lower, \
                f"Core dep '{name}' not pinned in lock file"

    def test_lock_file_versions_are_consistent(self):
        """No package appears twice with different versions in the lock."""
        lock_file = PACKAGING_DIR / "requirements-lock.txt"
        seen = {}
        for line in lock_file.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = re.match(r"^([a-zA-Z0-9_.-]+)==(.+)$", stripped)
            if m:
                name, version = m.group(1).lower(), m.group(2)
                if name in seen and seen[name] != version:
                    pytest.fail(
                        f"{name} pinned twice: {seen[name]} and {version}"
                    )
                seen[name] = version

    def test_async_test_plugin_is_declared(self):
        """A clean environment must be able to execute async tests."""
        requirements = (PROJECT_ROOT / "requirements.txt").read_text().lower()
        assert "pytest-asyncio" in requirements


# ---------------------------------------------------------------------------
# Dockerfile
# ---------------------------------------------------------------------------

class TestDockerfile:
    def test_dockerfile_has_non_root_user(self):
        """Dockerfile must define and switch to a non-root USER."""
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "USER antique" in dockerfile, "Missing non-root USER directive"
        assert "useradd" in dockerfile, "Missing useradd for non-root user"

    def test_dockerfile_has_healthcheck(self):
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "HEALTHCHECK" in dockerfile, "Missing HEALTHCHECK"

    def test_dockerfile_uses_lock_constraints(self):
        """Dockerfile should use the lock file for reproducible installs."""
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "requirements-lock.txt" in dockerfile, \
            "Dockerfile should pip install with lock constraints"

    def test_dockerfile_sets_pythonunbuffered(self):
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "PYTHONUNBUFFERED=1" in dockerfile, \
            "PYTHONUNBUFFERED=1 not set"


# ---------------------------------------------------------------------------
# docker-compose.yml
# ---------------------------------------------------------------------------

class TestDockerCompose:
    def test_compose_has_security_hardening(self):
        """docker-compose.yml must have key security hardening directives."""
        import yaml
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose_file.read_text())

        service = data["services"]["antique"]

        # no-new-privileges
        assert "no-new-privileges:true" in service["security_opt"], \
            "Missing no-new-privileges"

        # all capabilities dropped
        assert service["cap_drop"] == ["ALL"], \
            "Missing cap_drop: ALL"

        # read-only filesystem
        assert service["read_only"] is True, \
            "Missing read_only: true"

    def test_compose_port_bound_to_localhost(self):
        """Port must be bound to 127.0.0.1, not 0.0.0.0."""
        import yaml
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose_file.read_text())

        ports = data["services"]["antique"]["ports"]
        assert any("127.0.0.1" in str(p) for p in ports), \
            "Port not bound to 127.0.0.1"

    def test_compose_has_healthcheck(self):
        import yaml
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose_file.read_text())
        assert "healthcheck" in data["services"]["antique"], \
            "Missing healthcheck in compose"

    def test_compose_has_resource_limits(self):
        import yaml
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose_file.read_text())
        svc = data["services"]["antique"]
        assert "mem_limit" in svc, "Missing mem_limit"
        assert "cpus" in svc, "Missing cpus limit"


# ---------------------------------------------------------------------------
# systemd unit
# ---------------------------------------------------------------------------

class TestSystemdUnit:
    def test_service_file_exists(self):
        assert (PACKAGING_DIR / "antique.service").exists()

    def test_service_has_hardening(self):
        """systemd unit must have key hardening directives."""
        unit = (PACKAGING_DIR / "antique.service").read_text()

        required = [
            "User=antique",
            "NoNewPrivileges=true",
            "ProtectSystem=strict",
            "ProtectKernelTunables=true",
            "ProtectKernelModules=true",
            "ProtectControlGroups=true",
            "PrivateTmp=true",
            "PrivateDevices=true",
            "CapabilityBoundingSet=",
            "RestrictAddressFamilies=",
        ]
        missing = [d for d in required if d not in unit]
        assert not missing, f"Missing hardening directives: {missing}"

    def test_service_binds_to_localhost(self):
        """The service must bind to 127.0.0.1, not 0.0.0.0."""
        unit = (PACKAGING_DIR / "antique.service").read_text()
        assert "127.0.0.1" in unit, \
            "Service should bind to 127.0.0.1"

    def test_service_has_restart_policy(self):
        unit = (PACKAGING_DIR / "antique.service").read_text()
        assert "Restart=on-failure" in unit
        assert "RestartSec=" in unit

    def test_install_script_exists(self):
        assert (PACKAGING_DIR / "install-systemd.sh").exists()

    def test_install_script_has_safety_checks(self):
        script = (PACKAGING_DIR / "install-systemd.sh").read_text()
        assert 'id -u' in script, "Missing root check"
        assert 'useradd' in script or 'adduser' in script, \
            "Missing service user creation"


# ---------------------------------------------------------------------------
# PyInstaller spec
# ---------------------------------------------------------------------------

class TestPyInstallerSpec:
    def test_spec_file_exists(self):
        assert (PACKAGING_DIR / "antique.spec").exists()

    def test_spec_has_hidden_imports(self):
        """Spec must declare hidden imports for dynamically-loaded modules."""
        spec = (PACKAGING_DIR / "antique.spec").read_text()
        assert "hidden_imports" in spec
        assert "uvicorn" in spec, "Missing uvicorn hidden imports"
        assert "sqlalchemy" in spec, "Missing sqlalchemy hidden imports"

    def test_spec_has_data_files(self):
        """Spec must include UI templates and static files."""
        spec = (PACKAGING_DIR / "antique.spec").read_text()
        assert "templates" in spec, "Missing UI templates in datas"
        assert "static" in spec, "Missing UI static in datas"

    def test_spec_no_code_signing_claimed(self):
        """Spec must not claim code signing (codesign_identity=None)."""
        spec = (PACKAGING_DIR / "antique.spec").read_text()
        assert "codesign_identity=None" in spec or \
               "codesign_identity" not in spec, \
               "Should not claim code signing"


# ---------------------------------------------------------------------------
# Build scripts
# ---------------------------------------------------------------------------

class TestBuildScripts:
    def test_build_portable_script_exists(self):
        assert (SCRIPTS_DIR / "build-portable.bat").exists()

    def test_launcher_script_exists(self):
        assert (SCRIPTS_DIR / "antique-launcher.bat").exists()

    def test_launcher_has_all_commands(self):
        launcher = (SCRIPTS_DIR / "antique-launcher.bat").read_text()
        for cmd in ["install", "update", "rollback", "serve"]:
            assert f'"{cmd}"' in launcher, \
                f"Launcher missing {cmd} command"

    def test_launcher_uses_lock_file(self):
        """Launcher should reference the lock file for reproducible installs."""
        launcher = (SCRIPTS_DIR / "antique-launcher.bat").read_text()
        assert "requirements-lock.txt" in launcher, \
            "Launcher should use requirements-lock.txt"

    def test_build_script_references_spec(self):
        build = (SCRIPTS_DIR / "build-portable.bat").read_text()
        assert "antique.spec" in build, \
            "Build script should reference the PyInstaller spec"

    def test_start_portable_exists(self):
        assert (SCRIPTS_DIR / "start-portable.bat").exists()


# ---------------------------------------------------------------------------
# CI workflow
# ---------------------------------------------------------------------------

class TestCIWorkflow:
    def test_ci_yaml_exists(self):
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_file.exists(), "ci.yml missing"

    def test_ci_has_matrix(self):
        import yaml
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        data = yaml.safe_load(ci_file.read_text())

        # Find the test job
        test_job = data["jobs"].get("test", {})
        strategy = test_job.get("strategy", {})
        matrix = strategy.get("matrix", {})

        assert "ubuntu-latest" in matrix["os"]
        assert "windows-latest" in matrix["os"]
        assert "3.11" in matrix["python-version"]
        assert "3.12" in matrix["python-version"]

    def test_ci_has_static_checks_job(self):
        import yaml
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        data = yaml.safe_load(ci_file.read_text())
        assert "static-checks" in data["jobs"], \
            "Missing static-checks job"

    def test_ci_has_package_build_job(self):
        import yaml
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        data = yaml.safe_load(ci_file.read_text())
        assert "package-build" in data["jobs"], \
            "Missing package-build job"

    def test_ci_has_compile_step(self):
        ci = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "compileall" in ci, "Missing compileall step"

    def test_ci_uses_lock_file(self):
        ci = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "requirements-lock.txt" in ci, \
            "CI should use requirements-lock.txt"


# ---------------------------------------------------------------------------
# .dockerignore
# ---------------------------------------------------------------------------

class TestDockerIgnore:
    def test_dockerignore_exists(self):
        assert (PROJECT_ROOT / ".dockerignore").exists()

    def test_dockerignore_excludes_sensitive(self):
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert ".git" in content
        assert ".venv" in content
        assert "__pycache__" in content
