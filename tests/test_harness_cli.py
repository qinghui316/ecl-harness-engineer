from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness_cli.py"


class HarnessCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ecl-harness-test-")
        self.root = Path(self.temp.name)
        spec = importlib.util.spec_from_file_location(f"harness_cli_test_{id(self)}", CLI)
        assert spec and spec.loader
        self.cli_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli_module)
        self.runtime_analysis = importlib.import_module("harness_runtime.analysis")
        self.runtime_changes = importlib.import_module("harness_runtime.changes")
        self.runtime_contracts = importlib.import_module("harness_runtime.contracts")
        self.runtime_core = importlib.import_module("harness_runtime.core")
        self.runtime_evolution = importlib.import_module("harness_runtime.evolution")
        self.runtime_integration = importlib.import_module("harness_runtime.integration")
        self.runtime_knowledge = importlib.import_module("harness_runtime.knowledge")
        self.runtime_links = importlib.import_module("harness_runtime.links")
        self.runtime_project = importlib.import_module("harness_runtime.project")
        self.runtime_project_commands = importlib.import_module("harness_runtime.project_commands")
        self.runtime_rendering = importlib.import_module("harness_runtime.rendering")
        self.runtime_transactions = importlib.import_module("harness_runtime.transactions")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_process(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        expected: tuple[int, ...] = (0,),
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode not in expected:
            self.fail(
                f"Command returned {result.returncode}: {' '.join(command)}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def cli(
        self,
        project: Path,
        *arguments: str,
        expected: tuple[int, ...] = (0,),
    ) -> dict:
        command = [sys.executable, str(CLI), *arguments, "--project-root", str(project)]
        result = self.run_process(command, expected=expected)
        stream = result.stdout if result.stdout.strip() else result.stderr
        return json.loads(stream)

    def cli_args(self, project: Path, *arguments: str):
        return self.cli_module.build_parser().parse_args([
            *arguments, "--project-root", str(project),
        ])

    def dispatch(self, project: Path, *arguments: str) -> dict:
        return self.cli_module.dispatch(self.cli_args(project, *arguments))

    def git(self, project: Path, *arguments: str) -> str:
        return self.run_process(["git", "-C", str(project), *arguments]).stdout.strip()

    def create_git_project(self, name: str = "project") -> Path:
        project = self.root / name
        project.mkdir()
        self.run_process(["git", "init", "-b", "main", str(project)])
        self.git(project, "config", "user.email", "harness-tests@example.invalid")
        self.git(project, "config", "user.name", "Harness Tests")
        (project / "README.md").write_text(
            "# Test Project\n\nA fixture service that accepts jobs and records results.\n\n"
            "Job intake is implemented by `submit_job`.\n",
            encoding="utf-8",
        )
        (project / "pyproject.toml").write_text(
            "[project]\nname='fixture'\nversion='0.1.0'\n\n[tool.pytest.ini_options]\ntestpaths=['tests']\n",
            encoding="utf-8",
        )
        (project / ".env.example").write_text("APP_MODE=development\n", encoding="utf-8")
        (project / "src" / "jobs").mkdir(parents=True)
        (project / "src" / "runtime").mkdir(parents=True)
        (project / "src" / "jobs" / "service.py").write_text(
            "from .contracts import JobSubmitter\n\nclass JobService(JobSubmitter):\n"
            "    def submit_job(self, payload):\n        return {'status': 'queued', 'payload': payload}\n\n"
            "def submit_job(payload):\n    return JobService().submit_job(payload)\n",
            encoding="utf-8",
        )
        (project / "src" / "jobs" / "contracts.py").write_text(
            "from typing import Protocol\n\nclass JobSubmitter(Protocol):\n"
            "    def submit_job(self, payload): ...\n",
            encoding="utf-8",
        )
        (project / "src" / "runtime" / "worker.py").write_text(
            "from src.jobs.service import submit_job\n\ndef run(payload):\n    return submit_job(payload)\n",
            encoding="utf-8",
        )
        (project / "misc-one").mkdir()
        (project / "misc-one" / "note.txt").write_text("not a module\n", encoding="utf-8")
        (project / "misc-two").mkdir()
        (project / "misc-two" / "data.txt").write_text("not a module\n", encoding="utf-8")
        (project / "tests").mkdir()
        (project / "tests" / "test_jobs.py").write_text(
            "from src.jobs.service import submit_job\n\ndef test_submit():\n    assert submit_job(1)['status'] == 'queued'\n",
            encoding="utf-8",
        )
        self.git(project, "add", ".")
        self.git(project, "commit", "-m", "initial")
        return project

    def write_bundle(
        self,
        project: Path,
        name: str,
        *,
        purpose: str = "Accept jobs, coordinate execution, and persist observable results.",
        include_bridge: bool = True,
        command: str = "python -m pytest",
        command_evidence: str = "pyproject.toml",
        language: str = "Python",
        module_id: str = "job-processing",
        module_name: str = "Job Processing",
        module_root: str = "src/jobs",
        module_entrypoint: str = "src/jobs/service.py",
        module_test: str = "tests/test_jobs.py",
        artifact: bool = False,
    ) -> Path:
        bundle = self.root / "bundles" / name
        artifacts = bundle / "artifacts"
        artifacts.mkdir(parents=True)
        profile = {
            "schema_version": "1.0",
            "analysis_status": "complete",
            "project_name": project.name,
            "purpose": {"summary": purpose, "confidence": "high", "evidence": [module_entrypoint, module_test]},
            "primary_flows": [
                {
                    "name": "Submit and run a job",
                    "description": "Job service accepts input and the runtime worker invokes it.",
                    "evidence": [module_entrypoint, "src/runtime/worker.py"],
                }
            ],
            "languages": [{"name": language, "confidence": "high", "evidence": [command_evidence]}],
            "frameworks": [],
            "package_managers": [],
            "source_roots": [{"path": "src", "confidence": "high", "evidence": [module_entrypoint]}],
            "entrypoints": [{"path": module_entrypoint, "kind": "service", "evidence": [module_entrypoint]}],
            "modules": [
                {
                    "id": module_id,
                    "name": module_name,
                    "responsibility": "Own job submission, status transitions, and job-facing contracts.",
                    "kind": "business_domain",
                    "roots": [module_root],
                    "entrypoints": [module_entrypoint],
                    "interfaces": ["submit_job(payload)"],
                    "dependencies": ["runtime worker calls this module"],
                    "tests": [module_test],
                    "commands": [command],
                    "boundaries": ["Runtime orchestration must call the public job service."],
                    "evidence": [module_entrypoint, "src/runtime/worker.py", module_test],
                }
            ],
            "commands": [
                {
                    "purpose": "Run the test suite",
                    "category": "test",
                    "command": command,
                    "working_directory": ".",
                    "status": "configured",
                    "last_result": "not executed",
                    "evidence": [command_evidence],
                }
            ],
            "environment": {
                "services": [],
                "variables": [
                    {
                        "name": "APP_MODE",
                        "description": "Selects the local runtime mode; no secret value is stored.",
                        "evidence": [".env.example"],
                    }
                ],
                "modes": [
                    {"name": "development", "description": "Local development mode.", "evidence": [".env.example"]}
                ],
                "evidence": [".env.example"],
            },
            "ci": [],
            "bridges": [],
            "global_boundaries": [
                {
                    "name": "Job ownership",
                    "description": "Job state is owned by Job Processing.",
                    "evidence": [module_entrypoint],
                }
            ],
            "unknowns": [],
            "evidence": [command_evidence, module_entrypoint, module_test],
        }
        if include_bridge:
            profile["bridges"].append(
                {
                    "id": "terminology-to-code",
                    "title": "Terminology To Code",
                    "purpose": "Translate the product term job submission to its code owner.",
                    "mappings": [
                        {
                            "from": "submit a job",
                            "to": "src/jobs/service.py::submit_job",
                            "evidence": [module_entrypoint, module_test],
                        }
                    ],
                }
            )
        audit = {
            "schema_version": "1.0",
            "analysis_status": "complete",
            "overall_score": 8.5,
            "dimensions": {
                "project_knowledge": {"score": 9, "weight": 25, "checks_passed": 9, "checks_total": 10},
                "mechanical_checks": {"score": 8, "weight": 20, "checks_passed": 8, "checks_total": 10},
                "environment": {"score": 8, "weight": 15, "checks_passed": 8, "checks_total": 10},
                "coordination": {"score": 9, "weight": 15, "checks_passed": 9, "checks_total": 10},
                "ecl_changes": {"score": 8, "weight": 15, "checks_passed": 8, "checks_total": 10},
                "evolution": {"score": 9, "weight": 10, "checks_passed": 9, "checks_total": 10},
            },
            "gaps": [],
            "strengths": ["Project command and module ownership are source-backed."],
            "knowledge_findings": [{
                "type": "knowledge_drift", "decision": "promote",
                "owner": "project Harness knowledge owner", "projection": "refresh affected Wiki entries",
                "repair": "rescan changed canonical evidence", "validation": "knowledge check",
            }],
        }
        contract_path = "src/jobs/contracts.py" if (project / "src" / "jobs" / "contracts.py").is_file() else module_entrypoint
        architecture = {
            "schema_version": "1.0",
            "analysis_status": "complete",
            "layers": [{
                "level": 0,
                "packages": [module_root],
                "description": "Owns the job-facing domain boundary.",
                "evidence": [module_entrypoint],
            }],
            "dependencies": [{
                "from": "src/runtime/worker.py", "to": module_entrypoint,
                "relation": "imports submit_job", "module_id": module_id,
                "evidence": ["src/runtime/worker.py", module_entrypoint],
            }],
            "components": [],
            "circular_dependencies": [],
            "key_interfaces": [{
                "name": "JobSubmitter",
                "location": f"{contract_path}::JobSubmitter",
                "implementations": [f"{module_entrypoint}::JobService"],
                "module_id": module_id,
                "evidence": list(dict.fromkeys([contract_path, module_entrypoint])),
            }],
            "code_paths": [{
                "name": "Submit job",
                "flow": [module_entrypoint, "src/runtime/worker.py"],
                "semantic_bridge": True,
                "evidence": [module_entrypoint, "src/runtime/worker.py"],
            }],
            "error_patterns": {},
            "evidence": [module_entrypoint, "src/runtime/worker.py"],
        }
        delta = {"schema_version": "1.0", "mode": "init", "decisions": [], "artifacts": []}
        if artifact:
            check = artifacts / "check_project.py"
            check.write_text("#!/usr/bin/env python3\nprint('project check ok')\n", encoding="utf-8")
            delta["decisions"].append(
                {
                    "source": module_entrypoint,
                    "action": "create",
                    "owner": "project-skill/scripts/checks",
                    "projection": "scripts/checks/check_project.py",
                    "validation": "python scripts/checks/check_project.py",
                }
            )
            delta["artifacts"].append(
                {
                    "path": "scripts/checks/check_project.py",
                    "action": "create",
                    "source": "artifacts/check_project.py",
                    "owner": "creator-linters",
                    "validation": "python scripts/checks/check_project.py",
                    "evidence": [module_entrypoint],
                }
            )
        (bundle / "project-profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
        (bundle / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
        (bundle / "creation-delta.json").write_text(json.dumps(delta, indent=2), encoding="utf-8")
        (bundle / "architecture.json").write_text(json.dumps(architecture, indent=2), encoding="utf-8")
        return bundle

    def add_bundle_retirement(
        self,
        bundle: Path,
        target: str,
        *,
        evidence: str = "src/jobs/service.py",
    ) -> Path:
        delta_path = bundle / "creation-delta.json"
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        delta["artifacts"].append({
            "path": target,
            "action": "retire",
            "owner": "project Harness artifact owner",
            "validation": "retired",
            "evidence": [evidence],
        })
        delta_path.write_text(json.dumps(delta, indent=2), encoding="utf-8")
        return bundle

    def agent_review_extracted_bundle(
        self,
        project: Path,
        bundle: Path,
        *,
        artifact: bool = False,
        mode: str = "init",
    ) -> Path:
        profile_path = bundle / "project-profile.json"
        architecture_path = bundle / "architecture.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
        self.assertIn(profile["analysis_status"], {"partial", "bootstrap_only"})
        self.assertNotEqual(profile["analysis_status"], "complete")
        profile["analysis_status"] = "complete"
        profile.pop("document_candidates", None)
        profile["purpose"] = {
            "summary": "Accept jobs, coordinate execution, and persist observable results.",
            "confidence": "high",
            "evidence": [profile["entrypoints"][0]["path"], profile["modules"][0]["tests"][0]],
        }
        if not profile.get("bridges") and profile["entrypoints"][0]["path"] == "src/jobs/service.py":
            profile["bridges"] = [{
                "id": "terminology-to-code",
                "title": "Terminology To Code",
                "purpose": "Map the reviewed job-submission concept to its implementation owner.",
                "mappings": [{
                    "from": "submit a job",
                    "to": f"{profile['entrypoints'][0]['path']}::submit_job",
                    "evidence": [profile["entrypoints"][0]["path"], profile["modules"][0]["tests"][0]],
                }],
            }]
        profile["unknowns"] = [
            item for item in profile.get("unknowns", [])
            if "Agent semantic review is required" not in item
        ]
        architecture["analysis_status"] = "complete"
        audit = {
            "schema_version": "1.0",
            "analysis_status": "complete",
            "overall_score": 8.5,
            "dimensions": {
                "project_knowledge": {"score": 9, "weight": 25},
                "mechanical_checks": {"score": 8, "weight": 20},
                "environment": {"score": 8, "weight": 15},
                "coordination": {"score": 9, "weight": 15},
                "ecl_changes": {"score": 8, "weight": 15},
                "evolution": {"score": 9, "weight": 10},
            },
            "strengths": ["Agent review confirmed the extracted project evidence and semantic ownership."],
            "gaps": [],
            "knowledge_findings": [{
                "type": "knowledge_drift",
                "decision": "promote",
                "owner": "project Harness knowledge owner",
                "projection": "refresh affected L1/L2/L3 entries",
                "repair": "rescan changed canonical evidence",
                "validation": "knowledge check source fingerprints",
            }],
        }
        delta = {"schema_version": "1.0", "mode": mode, "decisions": [], "artifacts": []}
        if artifact:
            artifact_dir = bundle / "artifacts"
            artifact_dir.mkdir(exist_ok=True)
            check = artifact_dir / "check_source_roots.py"
            roots = [item["path"] for item in profile["source_roots"]]
            check.write_text(
                "import subprocess\nfrom pathlib import Path\n"
                "skill=Path(__file__).resolve().parents[2]\n"
                f"roots={roots!r}\n"
                "found=subprocess.run(['git','-C',str(skill),'rev-parse','--show-toplevel'],text=True,capture_output=True)\n"
                "root=Path(found.stdout.strip()) if found.returncode == 0 else skill.parents[2]\n"
                "missing=[item for item in roots if not (root/item).exists()]\n"
                "if missing: raise SystemExit('CHECK-SOURCE-ROOTS missing: '+', '.join(missing))\n"
                "print('CHECK-SOURCE-ROOTS ok')\n",
                encoding="utf-8",
            )
            action = "replace" if mode == "migrate" else "create"
            delta["artifacts"].append({
                "path": "scripts/checks/check_source_roots.py",
                "action": action,
                "source": "artifacts/check_source_roots.py",
                "owner": "creator-linters",
                "validation": "python scripts/checks/check_source_roots.py",
                "evidence": profile["evidence"][:1],
            })
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        architecture_path.write_text(json.dumps(architecture, indent=2), encoding="utf-8")
        (bundle / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
        (bundle / "creation-delta.json").write_text(json.dumps(delta, indent=2), encoding="utf-8")
        return bundle

    def init_project(
        self,
        project: Path,
        bundle: Path | None = None,
        *,
        allow_executable_artifacts: bool = False,
    ) -> dict:
        args = ["project", "init"]
        if bundle:
            args.extend(["--analysis-bundle", str(bundle)])
        if allow_executable_artifacts:
            args.append("--allow-executable-artifacts")
        return self.cli(project, *args)

    def commit_routes(self, project: Path) -> str:
        paths = ["AGENTS.md", "CLAUDE.md"]
        connectors = sorted((project / "scripts").glob("harness-skill-link.*"))
        paths.extend(str(path.relative_to(project)) for path in connectors)
        self.git(project, "add", *paths)
        self.git(project, "commit", "-m", "add harness routes")
        return self.git(project, "rev-parse", "HEAD")

    def initialize_skill_git_repository(self, skill_root: Path) -> str:
        (skill_root / ".gitignore").write_text(
            "/state/*\n!/state/manifest.json\n\n**/__pycache__/\n*.py[cod]\n*.log\n",
            encoding="utf-8",
        )
        manifest = json.loads((skill_root / "state" / "manifest.json").read_text(encoding="utf-8"))
        (skill_root / "README.md").write_text(
            f"# Shared Project Skill\n\nProject id: `{manifest['project_id']}`\n",
            encoding="utf-8",
        )
        pull_request = skill_root / ".github" / "pull_request_template.md"
        pull_request.parent.mkdir(parents=True)
        pull_request.write_text(
            "# Project Skill PR\n\n- Base Skill commit:\n- Business project commit/PR:\n- Modules:\n- Validation:\n",
            encoding="utf-8",
        )
        self.run_process(["git", "init", "-b", "main", str(skill_root)])
        self.git(skill_root, "config", "user.email", "harness-tests@example.invalid")
        self.git(skill_root, "config", "user.name", "Harness Tests")
        self.git(skill_root, "add", ".")
        self.assertEqual(self.git(skill_root, "ls-files", "state").splitlines(), ["state/manifest.json"])
        self.git(skill_root, "commit", "-m", "publish project skill")
        return self.git(skill_root, "rev-parse", "HEAD")

    def connector_command(self, worktree: Path, *, detach: bool = False) -> list[str]:
        powershell = worktree / "scripts" / "harness-skill-link.ps1"
        node = worktree / "scripts" / "harness-skill-link.mjs"
        python = worktree / "scripts" / "harness-skill-link.py"
        if powershell.is_file():
            command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(powershell),
            ]
            if detach:
                command.append("-Detach")
            return command
        if node.is_file():
            return ["node", str(node), *(["--detach"] if detach else [])]
        if python.is_file():
            return [sys.executable, str(python), *(["--detach"] if detach else [])]
        self.fail("No worktree connector was generated.")

    def run_connector(self, worktree: Path, *, detach: bool = False) -> dict:
        result = self.run_process(
            self.connector_command(worktree, detach=detach),
            cwd=worktree,
        )
        return json.loads(result.stdout)

    def complete_change_documents(self, worktree: Path, change_id: str) -> None:
        candidates = list((worktree / ".agents" / "skills").glob("*-harness"))
        self.assertEqual(len(candidates), 1)
        evidence = candidates[0] / "state" / "changes" / "active" / change_id
        (evidence / "spec.md").write_text(
            f"# Spec: {change_id}\n\n## Goal And Evidence\n\n- Goal: complete fixture behavior.\n"
            "- Evidence: user:test fixture.\n\n## Acceptance Criteria\n\n- AC-001: fixture validation passes.\n",
            encoding="utf-8",
        )
        (evidence / "plan.md").write_text(
            f"# Plan: {change_id}\n\n## Technical Approach\n\nImplement the fixture.\n\n"
            "## Verification Plan\n\n- AC-001 -> fixture validation.\n\n"
            "## Plan Review\n\n- Status: approved\n- Reviewer/evidence: test reviewer\n",
            encoding="utf-8",
        )
        (evidence / "tasks.md").write_text(
            f"# Tasks: {change_id}\n\n- [x] T001 [AC-001] Implement fixture; owner/path: test; validation: fixture validation.\n",
            encoding="utf-8",
        )
        (evidence / "reviews" / "review.md").write_text(
            f"# Review: {change_id}\n\n## Plan Review\n\n- Approved: yes\n\n"
            "## Scope And Contract\n\n- Scope matches spec: yes\n- Contract conflicts resolved: not applicable\n\n"
            "## Code And Validation\n\n- Findings: none\n- Commands and outcomes: fixture validation passed\n"
            "- Failure attribution: none\n\n## Optional Integration Notes\n\n"
            "- Integration requested: no\n- Commit boundary: not recorded\n- Dependencies: none recorded\n\n"
            "## Knowledge And Evolution Signals\n\n- Project-map impact: none\n",
            encoding="utf-8",
        )
        (evidence / "summary.md").write_text(
            f"---\nchange_id: \"{change_id}\"\nstatus: \"active\"\n---\n\n# Summary: {change_id}\n\n"
            "## Outcome\n\nFixture behavior completed.\n\n## Validation\n\n- Status: passed\n- Evidence: fixture validation\n",
            encoding="utf-8",
        )

    def complete_git_change(self, worktree: Path, change_id: str, filename: str) -> str:
        self.cli(worktree, "change", "new", change_id, "--scope", f"Implement {change_id}")
        self.complete_change_documents(worktree, change_id)
        (worktree / filename).write_text(f"{change_id}\n", encoding="utf-8")
        self.git(worktree, "add", filename)
        self.git(worktree, "commit", "-m", f"complete {change_id}")
        commit = self.git(worktree, "rev-parse", "HEAD")
        closed = self.cli(
            worktree,
            "change",
            "close",
            change_id,
            "--status",
            "completed",
            "--completion-commit",
            commit,
            "--validation",
            "fixture test passed",
            "--validation-passed",
        )
        self.assertEqual(closed["status"], "closed")
        return commit

    def complete_non_git_change(self, project: Path, change_id: str) -> dict:
        self.cli(project, "change", "new", change_id, "--scope", f"Implement {change_id}")
        self.complete_change_documents(project, change_id)
        return self.cli(
            project,
            "change",
            "close",
            change_id,
            "--status",
            "completed",
            "--validation",
            "manual fixture validation",
            "--validation-passed",
        )

    def prepare_evolution(
        self,
        name: str,
        *,
        stage: bool = True,
        optional_artifact: str | None = None,
    ) -> tuple[Path, Path, Path]:
        project = self.root / name
        (project / "src" / "jobs").mkdir(parents=True)
        (project / "src" / "runtime").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / "README.md").write_text("# Evolution\n\nAccept jobs and run them.\n", encoding="utf-8")
        (project / "pyproject.toml").write_text("[project]\nname='evolution'\nversion='0.1'\n", encoding="utf-8")
        (project / ".env.example").write_text("APP_MODE=development\n", encoding="utf-8")
        (project / "src" / "jobs" / "service.py").write_text("def submit_job(x): return x\n", encoding="utf-8")
        (project / "src" / "runtime" / "worker.py").write_text("def run(x): return x\n", encoding="utf-8")
        (project / "tests" / "test_jobs.py").write_text("def test_job(): assert True\n", encoding="utf-8")
        initialized = self.init_project(project, self.write_bundle(project, f"{name}-base"))
        skill_root = Path(initialized["skill_root"])
        if optional_artifact:
            target = skill_root / optional_artifact
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Obsolete project guidance\n", encoding="utf-8")
        for index in range(1, 6):
            self.complete_non_git_change(project, f"change-{index}")
        self.cli(
            project,
            "evolve",
            "check",
            "--claim-owner",
            "independent-judge",
            "--e1-confirmed",
        )
        proposal = skill_root / "state" / "evolution" / "proposals" / "accepted-knowledge.md"
        proposal.write_text(
            "# Evolution Proposal\n\nPromote canonical runtime ownership and retain evidence-backed module boundaries.\n",
            encoding="utf-8",
        )
        (project / "README.md").write_text(
            "# Evolution\n\nAccept jobs, coordinate runtime execution, and expose durable results.\n",
            encoding="utf-8",
        )
        bundle = self.write_bundle(
            project,
            f"{name}-updated",
            purpose="Accept jobs, coordinate runtime execution, and expose durable results.",
        )
        if stage:
            self.cli(
                project,
                "evolve",
                "stage",
                "--proposal-id",
                "accepted-knowledge",
                "--owner",
                "independent-judge",
                "--analysis-bundle",
                str(bundle),
            )
        return project, skill_root, bundle

    def write_focused_evolution_bundle(
        self,
        skill_root: Path,
        name: str,
    ) -> Path:
        bundle = self.root / f"{name}-focused-bundle"
        artifacts = bundle / "artifacts"
        artifacts.mkdir(parents=True)
        current = skill_root / "references" / "workflows" / "evolve.md"
        replacement = artifacts / "evolve.md"
        replacement.write_text(
            current.read_text(encoding="utf-8")
            + "\nFocused Evolution validates only the affected Harness owners.\n",
            encoding="utf-8",
        )
        delta = {
            "schema_version": "1.0",
            "mode": "evolution-focused",
            "decisions": [{
                "source": "registry:change/change-1",
                "action": "merge",
                "owner": "project Harness evolve workflow",
                "projection": "references/workflows/evolve.md",
                "validation": "workflow-contract",
            }],
            "artifacts": [{
                "path": "references/workflows/evolve.md",
                "action": "replace",
                "source": "artifacts/evolve.md",
                "owner": "project Harness evolve workflow",
                "validation": "workflow-contract",
                "evidence": ["registry:change/change-1"],
            }],
        }
        (bundle / "creation-delta.json").write_text(json.dumps(delta, indent=2), encoding="utf-8")
        return bundle

    def agent_knowledge_document(
        self,
        identifier: str,
        *,
        title: str,
        kind: str = "target",
        status: str = "accepted",
        owner: str = "project-architecture",
        evidence: tuple[str, ...] = ("user:accepted project direction",),
    ) -> str:
        evidence_lines = "\n".join(f"    - {item}" for item in evidence)
        return (
            "---\n"
            "ecl:\n"
            f"  id: {identifier}\n"
            "  layer: L2\n"
            f"  kind: {kind}\n"
            f"  status: {status}\n"
            f"  owner: {owner}\n"
            "  modules: [job-processing]\n"
            "  evidence:\n"
            f"{evidence_lines}\n"
            "  managed_by: agent\n"
            "---\n\n"
            f"# {title}\n\n"
            "This formal project document keeps its semantic state separate from current implementation facts.\n"
        )

    def prepare_integration(self, name: str) -> tuple[Path, Path, Path, str]:
        project = self.create_git_project(name)
        initialized = self.init_project(project, self.write_bundle(project, f"{name}-bundle"))
        baseline = self.commit_routes(project)
        lane = self.root / f"{name}-lane"
        self.git(project, "worktree", "add", "-b", f"{name}-lane", str(lane), baseline)
        self.run_connector(lane)
        completion = self.complete_git_change(lane, f"{name}-change", f"{name}.txt")
        self.cli(project, "integrate", "start", f"{name}-integration", f"{name}-change")
        return project, Path(initialized["skill_root"]), lane, completion

    def integration_candidate(self, skill_root: Path, integration_id: str) -> str:
        record = json.loads((
            skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        ).read_text(encoding="utf-8"))
        return self.git(skill_root / record["worktree"], "rev-parse", "HEAD")

    def write_integration_review(self, skill_root: Path, integration_id: str, commit: str) -> Path:
        path = self.root / "reviews" / f"{integration_id}-{commit[:8]}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": "1.0",
            "integration_id": integration_id,
            "reviewer_id": "independent-reviewer",
            "reviewed_commit": commit,
            "verdict": "approved",
            "validation_commands": ["fixture aggregate validation"],
            "findings": [],
            "created_at": "2026-01-01T00:00:00Z",
        }, indent=2), encoding="utf-8")
        return path

    def write_evolution_judge(
        self,
        skill_root: Path,
        proposal_id: str = "accepted-knowledge",
        *,
        verdict: str = "keep",
        score: int = 88,
        eval_mode: str = "independent_review",
        full_test_required: bool = False,
    ) -> Path:
        metadata = json.loads((
            skill_root / "state" / "evolution" / "staging" / proposal_id / "state" / "candidate.json"
        ).read_text(encoding="utf-8"))
        path = self.root / "judges" / f"{proposal_id}-{score}-{eval_mode}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": "1.0",
            "proposal_id": proposal_id,
            "reviewer_id": "independent-reviewer",
            "candidate_fingerprint": metadata["candidate_fingerprint"],
            "score": score,
            "hard_issues": [],
            "eval_mode": eval_mode,
            "validation": {
                "harness_passed": True,
                "project_passed": True,
                "full_test_required": full_test_required,
                "full_test_passed": True,
            },
            "verdict": verdict,
        }, indent=2), encoding="utf-8")
        return path

    def tree_hashes(self, root: Path) -> dict[str, str]:
        result = {}
        for path in root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def test_skill_capability_contract_is_routed_and_test_bound(self) -> None:
        baseline_capability_files = {
            "LICENSE",
            "README.md",
            "SKILL.md",
            "agents/analyzer.md",
            "agents/auditor.md",
            "agents/creator-config.md",
            "agents/creator-docs.md",
            "agents/creator-linters.md",
            "assets/readme/auto-evolve.png",
            "assets/readme/core-loop.png",
            "assets/readme/directory-map.png",
            "assets/readme/hero.png",
            "references/adapters/adapter-schema.md",
            "references/adapters/generic.md",
            "references/adapters/go.md",
            "references/adapters/java.md",
            "references/adapters/python.md",
            "references/adapters/rust.md",
            "references/adapters/typescript.md",
            "references/audit-rubric.json",
            "references/darwin-eval-prompts.md",
            "references/documentation-templates.md",
            "references/ecl-harness.md",
            "references/environment-config-guide.md",
            "references/environment-detection-guide.md",
            "references/greenfield-templates.md",
            "references/linter-templates.md",
        }
        missing = sorted(path for path in baseline_capability_files if not (ROOT / path).is_file())
        self.assertEqual(missing, [], f"Mature capability source files were removed: {missing}")

        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        direct_routes = {
            "agents/analyzer.md",
            "agents/auditor.md",
            "agents/creator-config.md",
            "agents/creator-docs.md",
            "agents/creator-linters.md",
            "references/ecl-harness.md",
            "references/darwin-eval-prompts.md",
        }
        for route in direct_routes:
            self.assertIn(route, skill)

        role_contracts = {
            "agents/analyzer.md": "<analysis-bundle>/project-profile.json",
            "agents/auditor.md": "<analysis-bundle>/audit.json",
            "agents/creator-config.md": "creation-delta.json",
            "agents/creator-docs.md": "creation-delta.json",
            "agents/creator-linters.md": "creation-delta.json",
        }
        for path, contract in role_contracts.items():
            self.assertIn(contract, (ROOT / path).read_text(encoding="utf-8"))

        cli_source = CLI.read_text(encoding="utf-8")
        semantic_install_callers = set()
        for implementation in (
            ROOT / "scripts" / "harness_runtime" / "project_commands.py",
            ROOT / "scripts" / "harness_runtime" / "evolution.py",
        ):
            tree = ast.parse(implementation.read_text(encoding="utf-8"))
            semantic_install_callers.update({
                node.name
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "install_analysis_bundle"
                    for child in ast.walk(node)
                )
            })
        self.assertEqual(semantic_install_callers, {"project_init", "project_migrate", "evolve_stage"})
        links_source = (ROOT / "scripts" / "harness_runtime" / "links.py").read_text(encoding="utf-8")
        self.assertNotIn("python_command = str(Path(sys.executable).resolve())", links_source)
        self.assertIn("ECL_HARNESS_PYTHON", links_source)

        facade_tree = ast.parse(cli_source)
        facade_functions = {
            node.name for node in facade_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(facade_functions, {"add_common", "build_parser", "dispatch", "main"})
        runtime_root = ROOT / "scripts" / "harness_runtime"
        module_names = {path.stem for path in runtime_root.glob("*.py") if path.name != "__init__.py"}
        dependencies: dict[str, set[str]] = {name: set() for name in module_names}
        for path in runtime_root.glob("*.py"):
            if path.name == "__init__.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                    dependency = node.module.split(".", 1)[0]
                    if dependency in module_names:
                        dependencies[path.stem].add(dependency)
                if isinstance(node, ast.Import):
                    self.assertTrue(all(alias.name != "harness_cli" for alias in node.names))
        temporary: set[str] = set()
        complete: set[str] = set()

        def visit(module: str) -> None:
            self.assertNotIn(module, temporary, f"Runtime dependency cycle includes {module}")
            if module in complete:
                return
            temporary.add(module)
            for dependency in dependencies[module]:
                visit(dependency)
            temporary.remove(module)
            complete.add(module)

        for module in dependencies:
            visit(module)

        auditor = (ROOT / "agents" / "auditor.md").read_text(encoding="utf-8")
        self.assertIn("audit-rubric.json", auditor)
        self.assertIn("machine formula owner", auditor)
        self.assertNotIn("advanced profile", auditor.lower())

        creator_config = (ROOT / "agents" / "creator-config.md").read_text(encoding="utf-8")
        creator_config_flat = " ".join(creator_config.split())
        self.assertIn("## Evidence And Command Status", creator_config)
        self.assertIn("Never present an adapter default as configured", creator_config_flat)
        self.assertIn("Ports, endpoints, patterns, and timeouts require", creator_config_flat)
        self.assertIn("Executable artifacts require explicit installation authorization", creator_config_flat)
        self.assertIn("Do not guess critical configuration", creator_config_flat)

        self.assertIn("`references/coordination-and-integration.md`", skill)
        self.assertIn("`references/evolution.md`", skill)

        capability_map = (ROOT / "references" / "maintainer-capability-contract.md").read_text(encoding="utf-8")
        for stale in (
            "references/knowledge/",
            "external local Skill",
            "routing pending",
            "forward test pending",
            "strengthening pending",
            "extension pending",
            "adaptation pending",
            "in progress",
            "proposal-only",
            "branch-local Change",
        ):
            self.assertNotIn(stale, capability_map)
        complete_rows = [
            line for line in capability_map.splitlines()
            if line.startswith("|") and line.rstrip().endswith("| Complete |")
        ]
        self.assertTrue(complete_rows)
        for row in complete_rows:
            columns = [column.strip() for column in row.strip().strip("|").split("|")]
            named_tests = re.findall(r"`(test_[A-Za-z0-9_]+)`", columns[-2])
            self.assertTrue(named_tests, f"Complete capability lacks a concrete semantic test: {row}")
            for test_name in named_tests:
                self.assertTrue(hasattr(self, test_name), f"Capability map names missing test: {test_name}")
        mapped_tests = set(re.findall(r"`(test_[A-Za-z0-9_]+)`", capability_map))
        for test_name in mapped_tests:
            self.assertTrue(hasattr(self, test_name), f"Capability map names missing test: {test_name}")

        prompts = json.loads((ROOT / "test-prompts.json").read_text(encoding="utf-8"))
        prompt_ids = {item["id"] for item in prompts}
        self.assertEqual(
            prompt_ids,
            {
                "greenfield-python-api",
                "independent-project-skill-git",
                "mature-polyglot",
                "parallel-integration-evolution",
                "reference-source-map",
            },
        )
        for item in prompts:
            self.assertTrue(item["prompt"].strip())
            self.assertTrue(item["expected"].strip())
        self.assertIn("Architecture Map", (ROOT / "README.md").read_text(encoding="utf-8"))
        migration = (ROOT / "references" / "migration.md").read_text(encoding="utf-8")
        for bundle_file in (
            "project-profile.json", "architecture.json", "audit.json", "creation-delta.json",
        ):
            self.assertIn(bundle_file, migration)

    def test_progressive_loading_routes_every_operational_reference(self) -> None:
        entry = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for reference in (ROOT / "references").glob("*.md"):
            self.assertIn(f"references/{reference.name}", entry, f"Unreachable reference: {reference.name}")
        for role in (ROOT / "agents").glob("*.md"):
            self.assertIn(f"agents/{role.name}", entry, f"Unreachable role: {role.name}")
        operational, maintainer = entry.split("## Maintaining ECL Harness Engineer", 1)
        self.assertNotIn("maintainer-capability-contract.md", operational)
        self.assertNotIn("darwin-eval-prompts.md", operational)
        self.assertIn("maintainer-capability-contract.md", maintainer)
        self.assertIn("darwin-eval-prompts.md", maintainer)

        scaffold = ROOT / "assets" / "project-skill"
        generated_entry = (scaffold / "SKILL.md.tpl").read_text(encoding="utf-8")
        for workflow in (scaffold / "references" / "workflows").glob("*.md"):
            self.assertIn(
                f"references/workflows/{workflow.name}", generated_entry,
                f"Unreachable generated workflow: {workflow.name}",
            )
        analysis_contract = scaffold / "references" / "analysis-contract.md"
        runtime_modules = scaffold / "references" / "runtime-modules.md"
        self.assertIn("references/analysis-contract.md", generated_entry)
        self.assertIn("references/bootstrap/project.md", generated_entry)
        self.assertIn("references/runtime-modules.md", generated_entry)
        self.assertIn("project_wiki/catalog.md", generated_entry)
        self.assertIn("target, decision, or guide documents", generated_entry)
        self.assertIn("Read the current workflow", generated_entry)
        self.assertRegex(generated_entry, r"reference-source\s+maps")
        self.assertIn("references/rules/by-stage/<stage>.md", generated_entry)
        self.assertTrue(analysis_contract.is_file())
        self.assertTrue(runtime_modules.is_file())
        self.assertNotEqual(
            runtime_modules.read_text(encoding="utf-8"),
            (ROOT / "references" / "runtime-modules.md").read_text(encoding="utf-8"),
        )
        generated_runtime_guide = runtime_modules.read_text(encoding="utf-8")
        self.assertNotIn("creator scaffold", generated_runtime_guide.lower())
        self.assertNotIn("mother", generated_runtime_guide.lower())
        self.assertIn("scripts/build_analysis_bundle.py", entry)
        self.assertIn("scripts/render_greenfield.py", entry)
        greenfield = (ROOT / "references" / "greenfield-templates.md").read_text(encoding="utf-8")
        self.assertIn("scripts/render_greenfield.py", greenfield)
        self.assertIn("approved Structured Change", greenfield)

    def test_operational_docs_use_current_product_vocabulary(self) -> None:
        docs = [ROOT / "SKILL.md", ROOT / "README.md"]
        docs.extend((ROOT / "agents").glob("*.md"))
        docs.extend(
            path for path in (ROOT / "references").glob("*.md")
            if path.name not in {"maintainer-capability-contract.md", "darwin-eval-prompts.md"}
        )
        docs.extend((ROOT / "assets" / "project-skill").rglob("*.md"))
        docs.append(ROOT / "assets" / "project-skill" / "SKILL.md.tpl")
        forbidden = (
            "母 skill", "mother skill", "project-skill checks", "<project-skill>",
            "generated skill", "generated project skill", "creator scaffold",
            "previous behavior", "preserve the mature",
        )
        for path in docs:
            content = path.read_text(encoding="utf-8")
            normalized = re.sub(r"\s+", " ", content).lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, normalized, f"Historical vocabulary in {path}: {phrase}")
        entry = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for jargon in (
            "evidence-proportionate", "capability-complete", "decision-complete",
            "bounded discovery funnel",
        ):
            self.assertNotIn(jargon, entry)

    def test_empty_non_git_bootstrap_is_honest_and_project_local(self) -> None:
        project = self.root / "empty-project"
        project.mkdir()
        initialized = self.init_project(project)
        self.assertEqual(initialized["status"], "bootstrapped")
        self.assertEqual(initialized["mode"], "single_lane")
        self.assertFalse(initialized["semantic_complete"])
        skill_root = Path(initialized["skill_root"])
        self.assertTrue(skill_root.is_relative_to(project / ".agents" / "skills"))
        self.assertFalse((project / ".git").exists())
        overview = (skill_root / "references" / "project_wiki" / "overview.md").read_text(encoding="utf-8")
        self.assertIn("Unknown", overview)
        self.assertEqual(list((skill_root / "references" / "project_wiki" / "modules").glob("*.md")), [])
        self.assertEqual(list((skill_root / "references" / "project_wiki" / "bridges").glob("*.md")), [])
        profile = json.loads((skill_root / "state" / "analysis" / "project-profile.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["commands"], [])
        agents_route = (project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("single-Lane mode", agents_route)
        self.assertNotIn("harness-skill-link", agents_route)
        self.assertTrue(self.cli(project, "project", "doctor")["healthy"])
        analysis_contract = (skill_root / "references" / "analysis-contract.md").read_text(encoding="utf-8")
        for contract in ("project-profile.json", "architecture.json", "audit.json", "creation-delta.json"):
            self.assertIn(contract, analysis_contract)
        generated_cli = skill_root / "scripts" / "harness_cli.py"
        help_result = self.run_process([sys.executable, str(generated_cli), "project", "--help"])
        self.assertIn("audit", help_result.stdout)
        self.assertIn("doctor", help_result.stdout)
        self.assertNotIn("init", help_result.stdout)
        self.assertNotIn("migrate", help_result.stdout)

    def test_mature_profile_generates_real_l1_l2_l3_without_directory_guessing(self) -> None:
        project = self.create_git_project("semantic-project")
        bundle = self.write_bundle(project, "semantic", artifact=True)
        initialized = self.init_project(project, bundle, allow_executable_artifacts=True)
        self.assertEqual(initialized["status"], "initialized")
        skill_root = Path(initialized["skill_root"])
        wiki = skill_root / "references" / "project_wiki"
        overview = (wiki / "overview.md").read_text(encoding="utf-8")
        self.assertIn("Accept jobs", overview)
        self.assertIn("Job Processing", overview)
        self.assertTrue((wiki / "modules" / "job-processing.md").is_file())
        self.assertFalse((wiki / "modules" / "misc-one.md").exists())
        self.assertFalse((wiki / "modules" / "misc-two.md").exists())
        bridge = (wiki / "bridges" / "terminology-to-code.md").read_text(encoding="utf-8")
        self.assertIn("submit a job", bridge)
        self.assertIn("src/jobs/service.py::submit_job", bridge)
        commands = (wiki / "systems" / "commands.md").read_text(encoding="utf-8")
        self.assertIn("configured", commands)
        architecture = (wiki / "systems" / "architecture.md").read_text(encoding="utf-8")
        self.assertIn("src/jobs", architecture)
        self.assertIn("```mermaid", architecture)
        self.assertIn("src/runtime/worker.py", architecture)
        self.assertIn("imports submit_job", architecture)
        self.assertIn("src/jobs/contracts.py::JobSubmitter", architecture)
        self.assertIn("src/jobs/service.py::JobService", architecture)
        module_map = (wiki / "modules" / "job-processing.md").read_text(encoding="utf-8")
        self.assertIn("## Local Architecture", module_map)
        self.assertIn("imports submit_job", module_map)
        critical_flow = (wiki / "bridges" / "critical-flow-submit-job.md").read_text(encoding="utf-8")
        self.assertIn("sequenceDiagram", critical_flow)
        self.assertIn("src/runtime/worker.py", critical_flow)
        self.assertTrue((skill_root / "scripts" / "checks" / "check_project.py").is_file())
        self.assertFalse((skill_root / "references" / "capabilities" / "greenfield.md").exists())
        for stage in ("intake", "locate", "plan", "implement", "verify", "close", "integrate", "evolve"):
            text = (skill_root / "references" / "workflows" / f"{stage}.md").read_text(encoding="utf-8")
            for heading in (
                "## Inputs",
                "## Agent Judgment",
                "## Deterministic Commands",
                "## Actions",
                "## Outputs",
                "## Exit",
                "## Stop And Escalate",
                "## Rules",
            ):
                self.assertIn(heading, text)
        templates = skill_root / "assets" / "templates"
        spec = (templates / "spec.md").read_text(encoding="utf-8")
        plan = (templates / "plan.md").read_text(encoding="utf-8")
        tasks = (templates / "tasks.md").read_text(encoding="utf-8")
        review = (templates / "review.md").read_text(encoding="utf-8")
        summary = (templates / "summary.md").read_text(encoding="utf-8")
        self.assertIn("requirement-first | plan-first | mixed", spec)
        self.assertIn("Questions asked this round", spec)
        self.assertIn("## Spec Gaps Found From Planning", plan)
        self.assertIn("## Plan Review", plan)
        self.assertIn("[AC-001]", tasks)
        self.assertIn("Failure attribution: introduced | pre-existing | environmental | blocked | none", review)
        self.assertIn("## Knowledge And Evolution Signals", review)
        self.assertIn("## Handoff", summary)
        self.assertTrue((skill_root / "references" / "rules" / "critical.md").is_file())
        intake = (skill_root / "references" / "workflows" / "intake.md").read_text(encoding="utf-8")
        rule_source = (skill_root / "references" / "rules" / "red_lines.yaml").read_text(encoding="utf-8")
        self.assertIn("at most three high-impact questions", intake)
        self.assertIn('"id":"HR-23"', rule_source)
        self.assertTrue(self.cli(project, "project", "audit")["rules"]["healthy"])
        wiki_index = json.loads((wiki / "index.json").read_text(encoding="utf-8"))
        overview_record = next(item for item in wiki_index["items"] if item["id"] == "overview")
        self.assertIn("src/runtime/worker.py", overview_record["sources"])
        self.assertIn("src/jobs/service.py", overview_record["source_fingerprints"])
        generated_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in skill_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".json", ".yaml", ".py", ".ps1", ".cmd", ".sh"}
        ).lower()
        for unsupported_fact in ("postgresql", "redis", "postgres:16", "localhost:5432", "get /healthz"):
            self.assertNotIn(unsupported_fact, generated_text)
        (project / "src" / "jobs" / "contracts.py").write_text(
            "from typing import Protocol\n\nclass ChangedContract(Protocol): ...\n",
            encoding="utf-8",
        )
        drift = self.cli(project, "knowledge", "check", expected=(1,))
        self.assertIn("knowledge_drift", {item["type"] for item in drift["findings"]})

    def test_l1_scales_with_project_complexity_without_content_caps(self) -> None:
        project = self.create_git_project("large-project-map")
        bundle = self.write_bundle(project, "large-project-map")
        profile_path = bundle / "project-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        module_template = profile["modules"][0]
        profile["modules"] = []
        for index in range(50):
            module = json.loads(json.dumps(module_template))
            module["id"] = f"domain-{index:02d}"
            module["name"] = f"Domain Capability {index:02d}"
            module["responsibility"] = (
                f"Own capability {index:02d}, its public contract, validation boundary, and operational handoff."
            )
            profile["modules"].append(module)
        profile["commands"] = [
            {
                "purpose": f"Run verification gate {index:02d}",
                "category": "test",
                "command": f"python -m pytest -k gate_{index:02d}",
                "working_directory": ".",
                "status": "configured",
                "last_result": "not executed",
                "evidence": ["pyproject.toml"],
            }
            for index in range(20)
        ]
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        initialized = self.init_project(project, bundle)
        skill_root = Path(initialized["skill_root"])
        wiki = skill_root / "references" / "project_wiki"
        overview = (wiki / "overview.md").read_text(encoding="utf-8")
        self.assertGreater(len(overview.encode("utf-8")), 6 * 1024)
        self.assertIn("Domain Capability 49", overview)
        self.assertIn("python -m pytest -k gate_19", overview)
        checked = self.cli(project, "knowledge", "check")
        self.assertTrue(checked["healthy"])
        self.assertNotIn("oversized_l1", {item["type"] for item in checked["findings"]})

        brief = wiki / "modules" / "brief.md"
        brief.write_text(
            "---\necl:\n  id: brief\n  layer: L2\n  kind: guide\n  status: accepted\n"
            "  owner: brief-owner\n  modules: [brief]\n  evidence: [user:accepted brief]\n"
            "  managed_by: agent\n---\n\n# Brief\n\nUseful.\n",
            encoding="utf-8",
        )
        self.runtime_knowledge.rebuild_project_wiki_index(
            skill_root, self.runtime_project.project_context(project),
        )
        checked = self.cli(project, "knowledge", "check")
        self.assertNotIn(
            str(brief),
            {item.get("path") for item in checked["findings"] if item["type"] == "empty_knowledge_entry"},
        )
        placeholder = wiki / "modules" / "placeholder.md"
        placeholder.write_text("   \n", encoding="utf-8")
        rejected = self.cli(project, "knowledge", "check", expected=(1,))
        self.assertIn(
            "modules/placeholder.md",
            {item.get("path") for item in rejected["findings"] if item["type"] == "empty_knowledge_entry"},
        )

    def test_rule_shaped_global_boundaries_render_completely_in_l1(self) -> None:
        project = self.create_git_project("rule-boundaries")
        bundle = self.write_bundle(project, "rule-boundaries")
        profile_path = bundle / "project-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        expected = [f"Global boundary rule {index}: use the public job service." for index in range(1, 8)]
        profile["global_boundaries"] = [
            {"rule": rule, "evidence": ["src/jobs/service.py"]}
            for rule in expected
        ]
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        initialized = self.init_project(project, bundle)
        overview = (
            Path(initialized["skill_root"])
            / "references" / "project_wiki" / "overview.md"
        ).read_text(encoding="utf-8")
        for rule in expected:
            self.assertIn(rule, overview)
        self.assertNotIn("No project-specific global boundary recorded.", overview)

        invalid_project = self.create_git_project("invalid-rule-boundary")
        invalid_bundle = self.write_bundle(invalid_project, "invalid-rule-boundary")
        invalid_profile_path = invalid_bundle / "project-profile.json"
        invalid_profile = json.loads(invalid_profile_path.read_text(encoding="utf-8"))
        invalid_profile["global_boundaries"] = [{"evidence": ["src/jobs/service.py"]}]
        invalid_profile_path.write_text(json.dumps(invalid_profile, indent=2), encoding="utf-8")
        rejected = self.cli(
            invalid_project,
            "project", "init", "--analysis-bundle", str(invalid_bundle),
            expected=(2,),
        )
        self.assertIn("global_boundaries", rejected["error"])
        self.assertIn("no displayable semantic text", rejected["error"])

    def test_other_semantic_projection_records_render_or_fail_validation(self) -> None:
        project = self.create_git_project("semantic-projections")
        workflow = project / ".github" / "workflows" / "verify.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: verify\n", encoding="utf-8")
        self.git(project, "add", ".github/workflows/verify.yml")
        self.git(project, "commit", "-m", "add verification workflow")
        bundle = self.write_bundle(project, "semantic-projections")
        profile_path = bundle / "project-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["environment"]["modes"] = [{
            "title": "Local development",
            "description": "Runs the project with local dependencies.",
            "evidence": [".env.example"],
        }]
        profile["environment"]["helpers"] = [{
            "name": "Readiness helper",
            "purpose": "Checks the configured local dependency.",
            "evidence": [".env.example"],
        }]
        profile["environment"]["startup_order"] = [{
            "service": "job service",
            "evidence": ["src/jobs/service.py"],
        }]
        profile["ci"] = [{
            "name": "Verification workflow",
            "path": ".github/workflows/verify.yml",
            "evidence": [".github/workflows/verify.yml"],
        }]
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        architecture_path = bundle / "architecture.json"
        architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
        architecture["components"] = [{
            "name": "Job API",
            "description": "Owns public job submission.",
            "evidence": ["src/jobs/service.py"],
        }]
        architecture["circular_dependencies"] = [{
            "pkg_a": "src.jobs",
            "pkg_b": "src.runtime",
            "suggested_fix": "Keep dependency direction through the public job service.",
            "evidence": ["src/jobs/service.py", "src/runtime/worker.py"],
        }]
        architecture_path.write_text(json.dumps(architecture, indent=2), encoding="utf-8")

        initialized = self.init_project(project, bundle)
        wiki = Path(initialized["skill_root"]) / "references" / "project_wiki"
        environment = (wiki / "systems" / "environment.md").read_text(encoding="utf-8")
        self.assertIn("Local development", environment)
        self.assertIn("Readiness helper", environment)
        self.assertIn("job service", environment)
        overview = (wiki / "overview.md").read_text(encoding="utf-8")
        self.assertNotIn("Canonical Documents", overview)
        verification = (wiki / "systems" / "verification.md").read_text(encoding="utf-8")
        self.assertIn("Verification workflow", verification)
        self.assertIn("`.github/workflows/verify.yml`", verification)
        architecture_map = (wiki / "systems" / "architecture.md").read_text(encoding="utf-8")
        self.assertIn("Job API", architecture_map)
        self.assertIn("`src.jobs` <-> `src.runtime`", architecture_map)
        self.assertNotIn("No dependency cycle recorded.", architecture_map)

        for case in ("primary-flow", "ci", "environment-mode", "startup-order", "component", "cycle"):
            with self.subTest(case=case):
                invalid_project = self.create_git_project(f"invalid-{case}")
                invalid_bundle = self.write_bundle(invalid_project, f"invalid-{case}")
                invalid_profile_path = invalid_bundle / "project-profile.json"
                invalid_profile = json.loads(invalid_profile_path.read_text(encoding="utf-8"))
                invalid_architecture_path = invalid_bundle / "architecture.json"
                invalid_architecture = json.loads(invalid_architecture_path.read_text(encoding="utf-8"))
                if case == "primary-flow":
                    invalid_profile["primary_flows"] = [{"evidence": ["README.md"]}]
                elif case == "ci":
                    invalid_profile["ci"] = [{"evidence": ["README.md"]}]
                elif case == "environment-mode":
                    invalid_profile["environment"]["modes"] = [{"evidence": ["README.md"]}]
                elif case == "startup-order":
                    invalid_profile["environment"]["startup_order"] = [{"evidence": ["README.md"]}]
                elif case == "component":
                    invalid_architecture["components"] = [{"evidence": ["README.md"]}]
                else:
                    invalid_architecture["circular_dependencies"] = [{
                        "pkg_a": "src.jobs",
                        "evidence": ["src/jobs/service.py"],
                    }]
                invalid_profile_path.write_text(json.dumps(invalid_profile, indent=2), encoding="utf-8")
                invalid_architecture_path.write_text(json.dumps(invalid_architecture, indent=2), encoding="utf-8")
                rejected = self.cli(
                    invalid_project,
                    "project", "init", "--analysis-bundle", str(invalid_bundle),
                    expected=(2,),
                )
                self.assertTrue(rejected["error"])

    def test_evolution_proposal_requires_only_non_empty_content(self) -> None:
        project, skill_root, bundle = self.prepare_evolution("short-evolution-proposal", stage=False)
        proposal = skill_root / "state" / "evolution" / "proposals" / "accepted-knowledge.md"
        proposal.write_text("   \n", encoding="utf-8")
        rejected = self.cli(
            project, "evolve", "stage", "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("must not be empty", rejected["error"])

        proposal.write_text("根据项目证据整理相关知识。\n", encoding="utf-8")
        staged = self.cli(
            project, "evolve", "stage", "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge", "--analysis-bundle", str(bundle),
        )
        self.assertEqual(staged["status"], "candidate_staged")

    def test_real_analyzer_auditor_creator_chain_builds_and_installs_bundle(self) -> None:
        project = self.create_git_project("real-analysis-chain")
        (project / ".github" / "workflows").mkdir(parents=True)
        (project / ".github" / "workflows" / "ci.yml").write_text(
            "steps:\n  - run: python -m pytest\n", encoding="utf-8",
        )
        self.git(project, "add", ".")
        self.git(project, "commit", "-m", "add ci evidence")
        bundle = self.root / "real-analysis-bundle"
        built = self.run_process([
            sys.executable, str(ROOT / "scripts" / "build_analysis_bundle.py"),
            "--project-root", str(project), "--output", str(bundle),
        ])
        build_result = json.loads(built.stdout)
        self.assertEqual(
            build_result["producer_chain"],
            ["deterministic-evidence-extractor"],
        )
        self.assertTrue(build_result["requires_agent_review"])
        audited = self.cli(
            project, "project", "audit", "--analysis-bundle", str(bundle),
        )
        self.assertFalse(audited["initialized"])
        self.assertEqual(audited["semantic"]["analysis_status"], "partial")
        self.agent_review_extracted_bundle(project, bundle, artifact=True)
        audited = self.cli(project, "project", "audit", "--analysis-bundle", str(bundle))
        self.assertEqual(audited["semantic"]["analysis_status"], "complete")
        initialized = self.init_project(project, bundle, allow_executable_artifacts=True)
        skill_root = Path(initialized["skill_root"])
        profile = json.loads((skill_root / "state" / "analysis" / "project-profile.json").read_text(encoding="utf-8"))
        self.assertIn("accept jobs", profile["purpose"]["summary"].lower())
        self.assertTrue(profile["primary_flows"])
        self.assertTrue(profile["modules"])
        self.assertTrue(profile["commands"])
        self.assertIn("APP_MODE", {item["name"] for item in profile["environment"]["variables"]})
        architecture = (skill_root / "references" / "project_wiki" / "systems" / "architecture.md").read_text(encoding="utf-8")
        self.assertIn("flowchart LR", architecture)
        self.assertIn("src/runtime/worker.py", architecture)
        self.assertTrue(list((skill_root / "references" / "project_wiki" / "bridges").glob("*.md")))
        check = skill_root / "scripts" / "checks" / "check_source_roots.py"
        self.assertTrue(check.is_file())
        self.run_process([sys.executable, str(check)])

    def test_analysis_source_discovery_prunes_ignored_trees_before_traversal(self) -> None:
        project = self.root / "pruned-analysis-source"
        (project / "src").mkdir(parents=True)
        (project / "src" / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
        (project / "src" / "z.ts").write_text("export const value = 1;\n", encoding="utf-8")
        (project / "src" / "notes.md").write_text("not source\n", encoding="utf-8")
        (project / "app.js").write_text("export const app = true;\n", encoding="utf-8")
        for index in range(200):
            dependency = project / "node_modules" / f"package-{index}" / "src"
            dependency.mkdir(parents=True)
            (dependency / "index.ts").write_text("export {};\n", encoding="utf-8")
        ignored_sources = [
            project / ".agents" / "reference-projects" / "sample" / "src" / "ignored.py",
            project / ".claude" / "skills" / "ignored.ts",
        ]
        for source in ignored_sources:
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("ignored = True\n", encoding="utf-8")

        spec = importlib.util.spec_from_file_location(
            f"analysis_builder_test_{id(self)}", ROOT / "scripts" / "build_analysis_bundle.py",
        )
        assert spec and spec.loader
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        real_scandir = os.scandir
        ignored = {"node_modules", ".agents", ".claude", "reference-projects"}

        def guarded_scandir(path: str | bytes | os.PathLike[str]) -> os.ScandirIterator:
            relative = Path(path).relative_to(project)
            self.assertFalse(ignored.intersection(relative.parts), f"visited ignored tree: {relative}")
            return real_scandir(path)

        with mock.patch("os.scandir", side_effect=guarded_scandir):
            discovered = builder.source_files(project)

        self.assertEqual(discovered, sorted([
            project / "app.js",
            project / "src" / "a.py",
            project / "src" / "z.ts",
        ]))

    def test_analysis_source_discovery_does_not_follow_directory_links(self) -> None:
        project = self.root / "linked-analysis-source"
        (project / "src").mkdir(parents=True)
        local_source = project / "src" / "local.py"
        local_source.write_text("LOCAL = True\n", encoding="utf-8")
        external = self.root / "external-analysis-source"
        external.mkdir()
        sentinel = external / "sentinel.py"
        sentinel.write_text("SENTINEL = 'unchanged'\n", encoding="utf-8")
        linked = project / "linked-source"
        self.runtime_links.create_directory_link(linked, external)

        spec = importlib.util.spec_from_file_location(
            f"linked_analysis_builder_test_{id(self)}", ROOT / "scripts" / "build_analysis_bundle.py",
        )
        assert spec and spec.loader
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        real_scandir = os.scandir
        external_root = external.resolve()

        def guarded_scandir(path: str | bytes | os.PathLike[str]) -> os.ScandirIterator:
            self.assertFalse(Path(path).resolve().is_relative_to(external_root), "visited linked target")
            return real_scandir(path)

        try:
            with mock.patch("os.scandir", side_effect=guarded_scandir):
                self.assertEqual(builder.source_files(project), [local_source])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "SENTINEL = 'unchanged'\n")
        finally:
            self.runtime_core.unlink_directory_link_node(linked)

    def test_real_polyglot_analysis_extracts_each_language_boundary(self) -> None:
        project = self.root / "real-polyglot"
        (project / "internal" / "jobs").mkdir(parents=True)
        (project / "cmd" / "worker").mkdir(parents=True)
        (project / "src" / "web").mkdir(parents=True)
        (project / "README.md").write_text(
            "# Polyglot Runtime\n\nAccept jobs in the web boundary and execute them in the Go worker.\n",
            encoding="utf-8",
        )
        (project / "go.mod").write_text("module example.test/polyglot\n\ngo 1.22\n", encoding="utf-8")
        (project / "package.json").write_text(
            json.dumps({"scripts": {"test": "node --test", "build": "tsc -p tsconfig.json"}}),
            encoding="utf-8",
        )
        (project / "internal" / "jobs" / "worker.go").write_text(
            "package jobs\n\ntype Runner interface { Run(string) string }\ntype Worker struct{}\nfunc (Worker) Run(v string) string { return v }\n",
            encoding="utf-8",
        )
        (project / "internal" / "jobs" / "worker_test.go").write_text(
            "package jobs\n\nimport \"testing\"\nfunc TestWorker(t *testing.T) { if (Worker{}).Run(\"ok\") != \"ok\" { t.Fatal(\"bad\") } }\n",
            encoding="utf-8",
        )
        (project / "cmd" / "worker" / "main.go").write_text(
            "package main\n\nimport \"example.test/polyglot/internal/jobs\"\nfunc main() { _ = (jobs.Worker{}).Run(\"accepted\") }\n",
            encoding="utf-8",
        )
        (project / "src" / "web" / "api.ts").write_text(
            "export interface JobApi { accept(value: string): string }\nexport class HttpApi implements JobApi { accept(value: string) { return value } }\n",
            encoding="utf-8",
        )
        (project / "src" / "web" / "index.ts").write_text(
            "import { HttpApi } from './api.js';\nexport const accepted = new HttpApi().accept('accepted');\n",
            encoding="utf-8",
        )
        (project / "src" / "web" / "api.test.ts").write_text(
            "import { HttpApi } from './api.js';\nif (new HttpApi().accept('ok') !== 'ok') throw new Error('bad');\n",
            encoding="utf-8",
        )
        bundle = self.root / "real-polyglot-bundle"
        built = self.run_process([
            sys.executable, str(ROOT / "scripts" / "build_analysis_bundle.py"),
            "--project-root", str(project), "--output", str(bundle),
        ])
        self.assertEqual(json.loads(built.stdout)["analysis_status"], "partial")
        profile = json.loads((bundle / "project-profile.json").read_text(encoding="utf-8"))
        architecture = json.loads((bundle / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual({"go", "typescript"}, {item["name"].lower() for item in profile["languages"]})
        self.assertGreaterEqual(len(profile["modules"]), 2)
        self.assertTrue(any(module["interfaces"] for module in profile["modules"]))
        self.assertEqual(profile["bridges"], [])
        self.assertIn("go test ./...", {item["command"] for item in profile["commands"]})
        self.assertIn("npm run test", {item["command"] for item in profile["commands"]})
        edges = {(item["from"], item["to"]) for item in architecture["dependencies"]}
        self.assertTrue(any(source.endswith(".go") and target.endswith(".go") for source, target in edges))
        self.assertTrue(any(source.endswith(".ts") and target.endswith(".ts") for source, target in edges))
        draft_audit = self.cli(project, "project", "audit", "--analysis-bundle", str(bundle))
        self.assertEqual(draft_audit["semantic"]["analysis_status"], "partial")
        self.agent_review_extracted_bundle(project, bundle)
        initialized = self.init_project(project, bundle, allow_executable_artifacts=True)
        self.assertEqual(initialized["status"], "initialized")
        generated_bridges = list(
            (Path(initialized["skill_root"]) / "references" / "project_wiki" / "bridges").glob("*.md")
        )
        self.assertEqual(generated_bridges, [])

    def test_evidence_extractor_cannot_complete_semantic_initialization(self) -> None:
        project = self.create_git_project("draft-analysis")
        bundle = self.root / "draft-analysis-bundle"
        built = self.run_process([
            sys.executable, str(ROOT / "scripts" / "build_analysis_bundle.py"),
            "--project-root", str(project), "--output", str(bundle),
        ])
        result = json.loads(built.stdout)
        self.assertEqual(result["analysis_status"], "partial")
        self.assertTrue(result["requires_agent_review"])
        profile = json.loads((bundle / "project-profile.json").read_text(encoding="utf-8"))
        audit = json.loads((bundle / "audit.json").read_text(encoding="utf-8"))
        delta = json.loads((bundle / "creation-delta.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["analysis_status"], "partial")
        self.assertEqual(audit["analysis_status"], "partial")
        self.assertNotIn("overall_score", audit)
        self.assertEqual(delta["artifacts"], [])
        initialized = self.init_project(project, bundle)
        self.assertEqual(initialized["status"], "bootstrapped")
        self.assertFalse(initialized["semantic_complete"])

    def test_reference_source_maps_are_isolated_and_linked_from_project_knowledge(self) -> None:
        project = self.create_git_project("reference-map")
        reference = project / ".agents" / "reference-projects" / "symphony"
        (reference / "src").mkdir(parents=True)
        (reference / "tests").mkdir()
        (reference / "README.md").write_text(
            "# Symphony Fixture\n\nA scheduler reconciles queued work into isolated workers.\n",
            encoding="utf-8",
        )
        (reference / "LICENSE").write_text("MIT fixture\n", encoding="utf-8")
        (reference / "src" / "scheduler.py").write_text(
            "class Scheduler:\n    def reconcile(self, queue): return list(queue)\n",
            encoding="utf-8",
        )
        (reference / "tests" / "test_scheduler.py").write_text(
            "from src.scheduler import Scheduler\n\ndef test_reconcile(): assert Scheduler().reconcile([1]) == [1]\n",
            encoding="utf-8",
        )

        extracted = self.root / "reference-target-extracted"
        self.run_process([
            sys.executable, str(ROOT / "scripts" / "build_analysis_bundle.py"),
            "--project-root", str(project), "--output", str(extracted),
        ])
        extracted_text = (extracted / "project-profile.json").read_text(encoding="utf-8")
        architecture_text = (extracted / "architecture.json").read_text(encoding="utf-8")
        self.assertNotIn("scheduler.py", extracted_text)
        self.assertNotIn("scheduler.py", architecture_text)

        bundle = self.write_bundle(project, "reference-map-bundle")
        profile_path = bundle / "project-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["reference_projects"] = [{
            "id": "symphony",
            "name": "Symphony",
            "source": "https://example.test/symphony.git",
            "checkout": ".agents/reference-projects/symphony",
            "inspected_commit": "0123456789abcdef",
            "purpose": "Study scheduler-owned worker reconciliation.",
            "global_relevance": "Orchestration lifecycle uses an adapted scheduler reconciliation model.",
            "license": "MIT (`LICENSE`)",
            "applicable_problems": ["queue dispatch", "worker reconciliation"],
            "inspected_files": [
                {"path": "src/scheduler.py", "reason": "Owns reconciliation behavior."},
                {"path": "tests/test_scheduler.py", "reason": "Proves queue-to-worker behavior."},
            ],
            "modules": [{
                "id": "scheduler",
                "name": "Scheduler",
                "responsibility": "Reconcile queued work into worker execution.",
                "roots": ["src"],
                "entrypoints": ["src/scheduler.py::Scheduler.reconcile"],
                "interfaces": ["Scheduler.reconcile(queue)"],
                "call_paths": ["queue -> Scheduler.reconcile -> workers"],
                "tests": ["tests/test_scheduler.py"],
                "evidence": ["src/scheduler.py", "tests/test_scheduler.py"],
            }],
            "unknowns": ["Production persistence behavior was not inspected."],
            "evidence": ["LICENSE", "src/scheduler.py", "tests/test_scheduler.py"],
        }]
        profile["modules"][0]["reference_sources"] = [{
            "reference_id": "symphony",
            "mechanism": "Scheduler-owned worker reconciliation.",
            "adaptation": "Keep project state in the Job Processing owner and reuse only the reconcile boundary.",
            "boundaries": ["Do not copy the reference authority model."],
            "validation": "Run the job-processing tests and contract review.",
            "target_evidence": ["src/jobs/service.py", "src/runtime/worker.py"],
            "reference_evidence": ["src/scheduler.py", "tests/test_scheduler.py"],
        }]
        profile["bridges"][0]["mappings"][0].update({
            "reference_id": "symphony",
            "reference_evidence": ["src/scheduler.py"],
        })
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        initialized = self.init_project(project, bundle)
        skill_root = Path(initialized["skill_root"])
        wiki = skill_root / "references" / "project_wiki"
        overview = (wiki / "overview.md").read_text(encoding="utf-8")
        module = (wiki / "modules" / "job-processing.md").read_text(encoding="utf-8")
        bridge = (wiki / "bridges" / "terminology-to-code.md").read_text(encoding="utf-8")
        reference_index = (wiki / "reference_projects" / "index.md").read_text(encoding="utf-8")
        reference_map = (wiki / "reference_projects" / "maps" / "symphony.md").read_text(encoding="utf-8")
        self.assertIn("reference_projects/maps/symphony.md", overview)
        self.assertIn("../reference_projects/maps/symphony.md", module)
        self.assertIn("../reference_projects/maps/symphony.md", bridge)
        self.assertIn("../modules/job-processing.md", reference_index)
        self.assertIn("../../modules/job-processing.md", reference_map)
        self.assertIn("src/scheduler.py", reference_map)
        self.assertIn("0123456789abcdef", reference_map)
        index = json.loads((wiki / "index.json").read_text(encoding="utf-8"))
        self.assertIn("reference-map", {item["kind"] for item in index["items"]})
        generated_entry = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        generated_cli = (skill_root / "scripts" / "harness_cli.py").read_text(encoding="utf-8")
        self.assertNotIn("harness-reference", generated_entry)
        self.assertNotIn("reference_ids", generated_entry)
        self.assertNotIn('add_parser("reference")', generated_cli)
        checked = self.cli(project, "knowledge", "check")
        self.assertEqual(checked["findings"], [])

        baseline = self.commit_routes(project)
        secondary = self.root / "reference-map-secondary"
        self.git(project, "worktree", "add", "-b", "reference-map-secondary", str(secondary), baseline)
        self.run_connector(secondary)
        secondary_checked = self.cli(secondary, "knowledge", "check")
        self.assertEqual(secondary_checked["findings"], [])
        self.assertTrue(self.cli(secondary, "knowledge", "scan")["healthy"])
        self.assertFalse((secondary / ".agents" / "reference-projects" / "symphony").exists())

        (reference / "src" / "scheduler.py").write_text(
            "class Scheduler:\n    def reconcile(self, queue): return tuple(queue)\n",
            encoding="utf-8",
        )
        drift = self.cli(secondary, "knowledge", "check", expected=(1,))
        self.assertIn("knowledge_drift", {item["type"] for item in drift["findings"]})
        scan_drift = self.cli(secondary, "knowledge", "scan", expected=(1,))
        self.assertEqual({item["source"] for item in scan_drift["findings"]}, {
            ".agents/reference-projects/symphony/src/scheduler.py",
        })

    def test_project_harness_rescans_audits_and_evolves_without_creator_files(self) -> None:
        project = self.root / "generated-independent"
        (project / "src" / "jobs").mkdir(parents=True)
        (project / "src" / "runtime").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / "README.md").write_text("# Independent\n\nAccept jobs and coordinate execution.\n", encoding="utf-8")
        (project / "pyproject.toml").write_text("[project]\nname='independent'\nversion='0.1'\n[tool.pytest.ini_options]\ntestpaths=['tests']\n", encoding="utf-8")
        (project / ".env.example").write_text("APP_MODE=development\n", encoding="utf-8")
        (project / "src" / "jobs" / "service.py").write_text("def submit_job(value): return value\n", encoding="utf-8")
        (project / "src" / "runtime" / "worker.py").write_text("from src.jobs.service import submit_job\n", encoding="utf-8")
        (project / "tests" / "test_jobs.py").write_text("def test_jobs(): assert True\n", encoding="utf-8")

        initial_bundle = self.root / "independent-initial-bundle"
        self.run_process([
            sys.executable, str(ROOT / "scripts" / "build_analysis_bundle.py"),
            "--project-root", str(project), "--output", str(initial_bundle),
        ])
        self.agent_review_extracted_bundle(project, initial_bundle)
        initialized = self.init_project(project, initial_bundle, allow_executable_artifacts=True)
        skill_root = Path(initialized["skill_root"])
        generated_cli = skill_root / "scripts" / "harness_cli.py"
        generated_builder = skill_root / "scripts" / "build_analysis_bundle.py"
        self.assertTrue(generated_builder.is_file())
        distribution_runtime = ROOT / "scripts" / "harness_runtime"
        generated_runtime = skill_root / "scripts" / "harness_runtime"
        self.assertEqual(
            {path.name for path in distribution_runtime.glob("*.py")},
            {path.name for path in generated_runtime.glob("*.py")},
        )
        generated_project_help = self.run_process([
            sys.executable, str(generated_cli), "project", "--help",
        ]).stdout
        self.assertIn("audit", generated_project_help)
        self.assertIn("doctor", generated_project_help)
        self.assertNotIn("init", generated_project_help)
        self.assertNotIn("migrate", generated_project_help)
        self.assertTrue((skill_root / "references" / "runtime-modules.md").is_file())
        for index in range(1, 6):
            self.complete_non_git_change(project, f"independent-{index}")
        self.cli(project, "evolve", "check", "--claim-owner", "independent-owner", "--e1-confirmed")
        proposal = skill_root / "state" / "evolution" / "proposals" / "independent-refresh.md"
        proposal.write_text("# Independent Refresh\n\nPromote changed canonical evidence and retain the proven module and command boundaries.\n", encoding="utf-8")
        (project / "README.md").write_text("# Independent\n\nAccept jobs, coordinate execution, and expose results.\n", encoding="utf-8")
        fresh_bundle = self.root / "independent-fresh-bundle"
        built = self.run_process([
            sys.executable, str(generated_builder), "--project-root", str(project),
            "--output", str(fresh_bundle),
        ])
        self.assertEqual(json.loads(built.stdout)["producer_chain"], ["deterministic-evidence-extractor"])
        draft_audited = self.run_process([
            sys.executable, str(generated_cli), "project", "audit", "--analysis-bundle", str(fresh_bundle),
            "--project-root", str(project),
        ])
        self.assertEqual(json.loads(draft_audited.stdout)["semantic"]["analysis_status"], "partial")
        self.agent_review_extracted_bundle(project, fresh_bundle, mode="migrate")
        audited = self.run_process([
            sys.executable, str(generated_cli), "project", "audit", "--analysis-bundle", str(fresh_bundle),
            "--project-root", str(project),
        ])
        self.assertEqual(json.loads(audited.stdout)["semantic"]["analysis_status"], "complete")
        preserved_changes = self.tree_hashes(skill_root / "state" / "changes")
        preserved_registry = {
            key: value for key, value in self.tree_hashes(skill_root / "state" / "registry").items()
            if not key.startswith("locks/")
        }
        staged = self.run_process([
            sys.executable, str(generated_cli), "evolve", "stage", "--proposal-id", "independent-refresh",
            "--owner", "independent-owner", "--analysis-bundle", str(fresh_bundle),
            "--allow-executable-artifacts", "--project-root", str(project),
        ])
        staged_payload = json.loads(staged.stdout)
        judge = self.write_evolution_judge(skill_root, "independent-refresh", score=90)
        completed = self.run_process([
            sys.executable, str(generated_cli), "evolve", "mark-complete",
            "--proposal-id", "independent-refresh", "--owner", "independent-owner",
            "--candidate-id", "independent-refresh", "--judge-report", str(judge),
            "--status", "keep", "--project-root", str(project),
        ])
        self.assertEqual(json.loads(completed.stdout)["status"], "keep")
        self.assertTrue(staged_payload["candidate_fingerprint"])
        self.assertEqual(preserved_changes, self.tree_hashes(skill_root / "state" / "changes"))
        self.assertEqual(
            preserved_registry,
            {
                key: value for key, value in self.tree_hashes(skill_root / "state" / "registry").items()
                if not key.startswith("locks/")
            },
        )

    def test_completed_change_requires_mature_semantic_evidence(self) -> None:
        project = self.root / "semantic-close"
        project.mkdir()
        self.init_project(project)
        self.cli(project, "change", "new", "semantic-close", "--scope", "semantic gate")
        rejected = self.cli(
            project,
            "change",
            "close",
            "semantic-close",
            "--status",
            "completed",
            "--validation",
            "fixture pass",
            "--validation-passed",
            expected=(2,),
        )
        self.assertIn("evidence is incomplete", rejected["error"])
        self.assertIn("clarification", rejected["error"])
        self.assertIn("approved plan review", rejected["error"])
        self.assertIn("unfinished task", rejected["error"])
        self.complete_change_documents(project, "semantic-close")
        closed = self.cli(
            project,
            "change",
            "close",
            "semantic-close",
            "--status",
            "completed",
            "--validation",
            "fixture pass",
            "--validation-passed",
        )
        self.assertTrue(closed["change"]["evidence_complete"])

    def test_doctor_detects_index_and_completed_evidence_tampering(self) -> None:
        project = self.root / "ecl-integrity"
        project.mkdir()
        initialized = self.init_project(project)
        skill_root = Path(initialized["skill_root"])
        self.cli(project, "change", "new", "indexed-change", "--scope", "Index metadata")
        self.complete_change_documents(project, "indexed-change")
        summary = skill_root / "state" / "changes" / "active" / "indexed-change" / "summary.md"
        text = summary.read_text(encoding="utf-8")
        text = text.replace(
            'status: "active"\n',
            'status: "active"\nmodules: [job-processing]\npaths: [src/jobs/service.py]\ntags: [runtime]\n',
        ).replace(
            "## Validation\n",
            "## Decisions\n\n- Keep the public job boundary stable.\n\n## Validation\n",
        )
        summary.write_text(text, encoding="utf-8")
        self.cli(
            project, "change", "close", "indexed-change", "--status", "completed",
            "--validation", "fixture passed", "--validation-passed",
        )
        index_path = skill_root / "state" / "changes" / "INDEX.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        entry = index["changes"][0]
        self.assertEqual(entry["modules"], ["job-processing"])
        self.assertEqual(entry["paths"], ["src/jobs/service.py"])
        self.assertEqual(entry["tags"], ["runtime"])
        self.assertIn("Keep the public job boundary stable.", entry["decisions"])

        index["changes"][0]["tags"] = ["tampered"]
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        audit_result = self.cli(project, "project", "audit")
        self.assertIn(
            "stale_or_tampered_change_index",
            {item["type"] for item in audit_result["ecl"]["findings"]},
        )

        self.cli(project, "change", "reindex")
        tasks = skill_root / "state" / "changes" / "archive" / "indexed-change" / "tasks.md"
        tasks.write_text(
            tasks.read_text(encoding="utf-8").replace(
                "validation: fixture validation", "validation: TBD",
            ),
            encoding="utf-8",
        )
        audit_result = self.cli(project, "project", "audit")
        self.assertIn(
            "tampered_change_evidence",
            {item["type"] for item in audit_result["ecl"]["findings"]},
        )

    def test_greenfield_capability_routes_through_structured_change(self) -> None:
        project = self.root / "greenfield-route"
        project.mkdir()
        initialized = self.init_project(project)
        skill_root = Path(initialized["skill_root"])
        entry = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        workflow = (
            skill_root / "references" / "workflows" / "bootstrap-project.md"
        ).read_text(encoding="utf-8")
        rules = (skill_root / "references" / "rules" / "red_lines.yaml").read_text(encoding="utf-8")
        self.assertIn("Bootstrap an empty business project", entry)
        for section in (
            "Inputs", "Agent Judgment", "Deterministic Commands", "Actions", "Outputs",
            "Exit", "Stop And Escalate", "Rules",
        ):
            self.assertIn(f"## {section}", workflow)
        for language in ("Go", "TypeScript", "Python"):
            self.assertIn(language, (ROOT / "references" / "greenfield-templates.md").read_text(encoding="utf-8"))
        self.assertIn("Structured Change", workflow)
        self.assertIn("Integration + I2", (ROOT / "references" / "greenfield-templates.md").read_text(encoding="utf-8"))
        self.assertIn('"id":"HR-24"', rules)
        capability = (
            skill_root / "references" / "bootstrap" / "project.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Decisions Required Before Projection", capability)
        self.assertNotIn("### Go CLI", capability)
        self.assertNotIn("### TypeScript CLI", capability)
        self.assertTrue(
            (skill_root / "references" / "rules" / "by-stage" / "bootstrap-project.md").is_file()
        )
        self.assertLess(workflow.index("change new"), workflow.index("change preflight"))
        renderer = skill_root / "scripts" / "render_greenfield.py"
        self.assertTrue(renderer.is_file())
        rendered_project = self.root / "generated-greenfield-render"
        self.run_process([
            sys.executable, str(renderer), "--variant", "python-cli",
            "--output-root", str(rendered_project), "--project-name", "Generated Greenfield",
        ])
        self.assertTrue((rendered_project / "pyproject.toml").is_file())
        self.assertFalse((project / "go.mod").exists())
        self.assertFalse((project / "package.json").exists())
        self.assertFalse((project / "pyproject.toml").exists())

    def test_greenfield_projects_only_the_selected_detailed_variant(self) -> None:
        project = self.create_git_project("selected-greenfield")
        bundle = self.write_bundle(project, "selected-greenfield")
        selected = bundle / "artifacts" / "selected-bootstrap.md"
        selected.write_text(
            "# Python CLI Bootstrap\n\n## Source\n\n`src/selected_greenfield/cli.py`\n\n"
            "## Commands\n\n`python -m pytest`\n\n## Change\n\nUse Structured Change and Integration/I2.\n",
            encoding="utf-8",
        )
        delta_path = bundle / "creation-delta.json"
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        delta["artifacts"] = [{
            "path": "references/bootstrap/project.md",
            "action": "replace",
            "source": "artifacts/selected-bootstrap.md",
            "owner": "creator-docs",
            "validation": "text-present",
            "evidence": ["pyproject.toml"],
        }]
        delta_path.write_text(json.dumps(delta, indent=2), encoding="utf-8")
        initialized = self.init_project(project, bundle)
        projected = (Path(initialized["skill_root"]) / "references" / "bootstrap" / "project.md").read_text(encoding="utf-8")
        self.assertIn("Python CLI Bootstrap", projected)
        self.assertNotIn("Go CLI Bootstrap", projected)
        self.assertNotIn("TypeScript CLI Bootstrap", projected)

    def test_greenfield_six_variants_generate_real_projects_and_run_available_gates(self) -> None:
        renderer = ROOT / "scripts" / "render_greenfield.py"
        variants = (
            "go-cli", "go-web", "typescript-cli", "typescript-web", "python-cli", "python-web",
        )
        runtime_results = {}
        for variant in variants:
            output = self.root / "greenfield-variants" / variant
            result = self.run_process([
                sys.executable, str(renderer), "--variant", variant,
                "--output-root", str(output), "--project-name", f"fixture-{variant}",
            ])
            rendered = json.loads(result.stdout)
            self.assertEqual(rendered["variant"], variant)
            self.assertTrue((output / "README.md").is_file())
            self.assertTrue((output / ".github" / "workflows" / "ci.yml").is_file())
            for command in ("build", "test", "lint", "start"):
                self.assertIn(command, rendered["commands"])

            language = variant.split("-", 1)[0]
            if language == "python":
                self.run_process([sys.executable, "-m", "compileall", "-q", "src", "tests"], cwd=output)
                self.run_process([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=output)
                if variant.endswith("cli"):
                    started = self.run_process([sys.executable, "main.py", "accepted"], cwd=output)
                    self.assertEqual(started.stdout.strip(), "accepted")
                runtime_results[variant] = "passed"
            elif language == "go":
                go = shutil.which("go")
                if not go:
                    runtime_results[variant] = "environmental: go unavailable"
                    continue
                for command in ([go, "test", "./..."], [go, "vet", "./..."], [go, "build", "./..."]):
                    self.run_process(command, cwd=output)
                if variant.endswith("cli"):
                    started = self.run_process([go, "run", f"./cmd/fixture-{variant}", "accepted"], cwd=output)
                    self.assertEqual(started.stdout.strip(), "accepted")
                runtime_results[variant] = "passed"
            else:
                tsc, node = shutil.which("tsc"), shutil.which("node")
                if not tsc or not node:
                    runtime_results[variant] = "environmental: tsc/node unavailable"
                    continue
                self.run_process([tsc, "-p", "tsconfig.json"], cwd=output)
                self.run_process([node, "dist/test/app.test.js"], cwd=output)
                if variant.endswith("web"):
                    self.run_process([node, "dist/test/http.test.js"], cwd=output)
                else:
                    started = self.run_process([node, "dist/src/cli.js", "accepted"], cwd=output)
                    self.assertEqual(started.stdout.strip(), "accepted")
                runtime_results[variant] = "passed"
        self.assertEqual(set(runtime_results), set(variants))
        self.assertTrue(all(value == "passed" or value.startswith("environmental:") for value in runtime_results.values()))

    def test_environment_projection_preserves_readiness_startup_and_rejects_secret_values(self) -> None:
        project = self.create_git_project("environment-contract")
        compose = project / "compose.yaml"
        compose.write_text("services:\n  database:\n    image: postgres:16\n", encoding="utf-8")
        bundle = self.write_bundle(project, "environment-contract")
        profile_path = bundle / "project-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["environment"] = {
            "services": [{
                "name": "database",
                "purpose": "Persist job state",
                "startup_order": 10,
                "readiness": {"type": "tcp", "target": "database service port from compose"},
                "migration_seed": "Run configured migration before application start",
                "cleanup": "Stop only the project-owned compose service",
                "evidence": ["compose.yaml"],
            }],
            "variables": [{
                "name": "DATABASE_URL", "required": True, "sensitive": True,
                "description": "Connection string supplied by the user environment",
                "evidence": [".env.example"],
            }],
            "modes": [],
            "startup_order": ["database", "migration", "application"],
            "helpers": [{
                "name": "database-readiness",
                "purpose": "Check the accepted database readiness contract",
                "evidence": ["compose.yaml"],
            }],
            "unknowns": ["Readiness port remains externally configured"],
            "evidence": ["compose.yaml", ".env.example"],
        }
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        helper = bundle / "artifacts" / "check_database.py"
        helper.write_text(
            "import argparse, tempfile\nfrom pathlib import Path\n"
            "p=argparse.ArgumentParser(); p.add_argument('action', choices=['start','ready','teardown','self-test']); "
            "p.add_argument('--state'); a=p.parse_args()\n"
            "def operate(action, state):\n"
            " marker=Path(state)\n"
            " if action=='start':\n  marker.write_text('owned-by-harness-helper', encoding='utf-8'); return\n"
            " if action=='ready':\n  if not marker.is_file(): raise SystemExit('database readiness failed: owned marker is absent'); return\n"
            " if action=='teardown':\n  if marker.is_file() and marker.read_text(encoding='utf-8')=='owned-by-harness-helper': marker.unlink(); return\n"
            "with tempfile.TemporaryDirectory() as d:\n"
            " marker=Path(d)/'database.ready'\n"
            " operate('start', marker); operate('ready', marker); operate('teardown', marker)\n"
            " if marker.exists(): raise SystemExit('teardown left owned state behind')\n"
            "print('database readiness helper ok')\n",
            encoding="utf-8",
        )
        delta_path = bundle / "creation-delta.json"
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        delta["artifacts"] = [{
            "path": "scripts/helpers/check_database.py",
            "action": "create",
            "source": "artifacts/check_database.py",
            "owner": "creator-config",
            "validation": "python scripts/helpers/check_database.py self-test",
            "evidence": ["compose.yaml"],
        }]
        delta_path.write_text(json.dumps(delta, indent=2), encoding="utf-8")
        initialized = self.init_project(project, bundle, allow_executable_artifacts=True)
        self.assertTrue(
            (Path(initialized["skill_root"]) / "scripts" / "helpers" / "check_database.py").is_file()
        )
        generated_helper = Path(initialized["skill_root"]) / "scripts" / "helpers" / "check_database.py"
        marker = self.root / "database.ready"
        for action in ("start", "ready", "teardown"):
            self.run_process([sys.executable, str(generated_helper), action, "--state", str(marker)])
        self.assertFalse(marker.exists())
        environment = (
            Path(initialized["skill_root"]) / "references" / "project_wiki" / "systems" / "environment.md"
        ).read_text(encoding="utf-8")
        self.assertIn("tcp: database service port from compose", environment)
        for step in ("- database", "- migration", "- application"):
            self.assertIn(step, environment)
        self.assertIn("Readiness port remains externally configured", environment)

        unsafe = self.write_bundle(project, "environment-secret")
        unsafe_profile_path = unsafe / "project-profile.json"
        unsafe_profile = json.loads(unsafe_profile_path.read_text(encoding="utf-8"))
        unsafe_profile["environment"]["variables"][0]["value"] = "actual-" + "secret"
        unsafe_profile_path.write_text(json.dumps(unsafe_profile, indent=2), encoding="utf-8")
        rejected = self.cli(
            project, "project", "migrate", "--analysis-bundle", str(unsafe), expected=(2,),
        )
        self.assertIn("Secret-bearing field", rejected["error"])

    def test_knowledge_check_does_not_infer_document_semantics_from_prose(self) -> None:
        project = self.create_git_project("knowledge-entropy")
        initialized = self.init_project(project, self.write_bundle(project, "knowledge-entropy"))
        skill_root = Path(initialized["skill_root"])
        repeated = "Current baseline is main at the accepted integration commit and next action is runtime verification."
        overview = skill_root / "references" / "project_wiki" / "overview.md"
        module = skill_root / "references" / "project_wiki" / "modules" / "job-processing.md"
        with overview.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## Current Status\n\n{repeated}\nLatest completed: changes/archive/old-change\n")
        with module.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n## Current Plan\n\n{repeated}\n"
                "[Evolve workflow](../../workflows/evolve.md)\n"
            )
        result = self.cli(project, "knowledge", "check")
        self.assertTrue(result["healthy"])
        self.assertEqual(result["warnings"], [])
        self.assertNotIn("external_knowledge_link", {item["type"] for item in result["findings"]})

        index_path = skill_root / "references" / "project_wiki" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        bridge = next(item for item in index["items"] if item["path"].startswith("bridges/"))
        bridge["sources"] = []
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        result = self.cli(project, "knowledge", "check")
        self.assertNotIn("uncited_l3_bridge", {item["type"] for item in result["findings"]})

    def test_evolution_accepts_project_language_proposal_without_entropy_keywords(self) -> None:
        project, skill_root, bundle = self.prepare_evolution("evolution-entropy", stage=False)
        repeated = "Current baseline is canonical and next action is to verify the runtime integration contract."
        overview = skill_root / "references" / "project_wiki" / "overview.md"
        module = skill_root / "references" / "project_wiki" / "modules" / "job-processing.md"
        with overview.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## Current Status\n\n{repeated}\nLatest completed: changes/archive/old\n")
        with module.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## Current Plan\n\n{repeated}\n")
        proposal = skill_root / "state/evolution/proposals/accepted-knowledge.md"
        proposal.write_text("演进提案：根据项目证据整理相关知识。\n", encoding="utf-8")
        staged = self.cli(
            project, "evolve", "stage", "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge", "--analysis-bundle", str(bundle),
        )
        self.assertEqual(staged["status"], "candidate_staged")

    def test_complete_bundle_rejects_weak_audit_or_missing_architecture(self) -> None:
        project = self.create_git_project("strict-analysis-contract")
        weak = self.write_bundle(project, "weak-audit")
        audit_path = weak / "audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["dimensions"].pop("evolution")
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(weak), expected=(2,),
        )
        self.assertIn("every core audit dimension", rejected["error"])

        missing = self.write_bundle(project, "missing-architecture")
        (missing / "architecture.json").unlink()
        rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(missing), expected=(2,),
        )
        self.assertIn("architecture.json", rejected["error"])

        partial_audit = self.write_bundle(project, "partial-audit")
        audit_path = partial_audit / "audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["analysis_status"] = "partial"
        audit["dimensions"] = {}
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(partial_audit), expected=(2,),
        )
        self.assertIn("requires a complete audit", rejected["error"])

        empty_architecture = self.write_bundle(project, "empty-architecture")
        architecture_path = empty_architecture / "architecture.json"
        architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
        for key in ("layers", "key_interfaces", "code_paths"):
            architecture[key] = []
        architecture["evidence"] = []
        architecture_path.write_text(json.dumps(architecture, indent=2), encoding="utf-8")
        rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(empty_architecture), expected=(2,),
        )
        self.assertIn("complete architecture requires project evidence", rejected["error"].lower())

        unsupported_architecture_status = self.write_bundle(project, "bootstrap-architecture")
        architecture_path = unsupported_architecture_status / "architecture.json"
        architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
        architecture["analysis_status"] = "bootstrap_only"
        architecture_path.write_text(json.dumps(architecture, indent=2), encoding="utf-8")
        rejected = self.cli(
            project,
            "project",
            "init",
            "--analysis-bundle",
            str(unsupported_architecture_status),
            expected=(2,),
        )
        self.assertIn("requires a complete architecture analysis", rejected["error"])

        unsupported_gap = self.write_bundle(project, "gap-without-evidence")
        audit_path = unsupported_gap / "audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["gaps"] = [{
            "priority": "P1",
            "dimension": "project_knowledge",
            "issue": "Module owner is unclear",
            "fix": "Trace imports and publish an evidenced owner",
        }]
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(unsupported_gap), expected=(2,),
        )
        self.assertIn("gap requires non-empty evidence", rejected["error"])

    def test_adapter_detector_uses_manifest_evidence_and_keeps_defaults_out(self) -> None:
        project = self.root / "adapter-detection"
        project.mkdir()
        (project / "go.mod").write_text("module example.test/go\ngo 1.22\n", encoding="utf-8")
        (project / "package.json").write_text(json.dumps({
            "scripts": {"test": "node --test", "build": "tsc"},
        }), encoding="utf-8")
        result = self.run_process([
            sys.executable,
            str(ROOT / "scripts" / "detect_adapters.py"),
            "--project-root",
            str(project),
        ])
        payload = json.loads(result.stdout)
        self.assertEqual({item["id"] for item in payload["adapters"]}, {"go", "typescript"})
        self.assertEqual(
            {item["command"] for item in payload["configured_commands"]},
            {"npm run test", "npm run build"},
        )
        self.assertNotIn("go test ./...", result.stdout)

    def test_obsolete_capability_profiles_are_rejected(self) -> None:
        project = self.create_git_project("obsolete-profile")
        bundle = self.write_bundle(project, "obsolete-profile")
        delta_path = bundle / "creation-delta.json"
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        delta["capability_profiles"] = ["eval"]
        delta_path.write_text(json.dumps(delta, indent=2), encoding="utf-8")
        rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("capability_profiles is obsolete", rejected["error"])

        del delta["capability_profiles"]
        artifact = bundle / "artifacts" / "helper.py"
        artifact.write_text("print('helper ok')\n", encoding="utf-8")
        delta["artifacts"] = [{
            "path": "scripts/helpers/helper.py",
            "action": "create",
            "source": "artifacts/helper.py",
            "owner": "creator-config",
            "validation": "python scripts/helpers/helper.py",
            "evidence": ["pyproject.toml"],
            "capability_profile": "eval",
        }]
        delta_path.write_text(json.dumps(delta, indent=2), encoding="utf-8")
        rejected = self.cli(
            project,
            "project",
            "init",
            "--analysis-bundle",
            str(bundle),
            "--allow-executable-artifacts",
            expected=(2,),
        )
        self.assertIn("obsolete capability_profile metadata", rejected["error"])

    def test_evidenced_mechanical_check_has_positive_negative_and_actionable_failure(self) -> None:
        project = self.create_git_project("mechanical-check")
        bundle = self.write_bundle(project, "mechanical-check")
        checker = bundle / "artifacts" / "check_boundary.py"
        checker.write_text(
            "import argparse\nfrom pathlib import Path\n"
            "p=argparse.ArgumentParser(); p.add_argument('--project-root', required=True); a=p.parse_args()\n"
            "target=Path(a.project_root)/'src/jobs/service.py'; text=target.read_text(encoding='utf-8')\n"
            "if 'forbidden-import' in text:\n"
            " print('CHECK-BOUNDARY src/jobs/service.py: remove forbidden-import and use the public runtime boundary')\n"
            " raise SystemExit(1)\n"
            "print('CHECK-BOUNDARY ok')\n",
            encoding="utf-8",
        )
        delta_path = bundle / "creation-delta.json"
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        delta["artifacts"] = [{
            "path": "scripts/checks/check_boundary.py",
            "action": "create",
            "source": "artifacts/check_boundary.py",
            "owner": "creator-linters",
            "validation": f"python scripts/checks/check_boundary.py --project-root {project}",
            "evidence": ["src/jobs/service.py"],
        }]
        delta_path.write_text(json.dumps(delta, indent=2), encoding="utf-8")
        initialized = self.init_project(project, bundle, allow_executable_artifacts=True)
        generated = Path(initialized["skill_root"]) / "scripts" / "checks" / "check_boundary.py"
        positive = self.run_process([
            sys.executable, str(generated), "--project-root", str(project),
        ])
        self.assertIn("CHECK-BOUNDARY ok", positive.stdout)
        with (project / "src" / "jobs" / "service.py").open("a", encoding="utf-8") as handle:
            handle.write("\n# forbidden-import\n")
        negative = self.run_process([
            sys.executable, str(generated), "--project-root", str(project),
        ], expected=(1,))
        self.assertIn("src/jobs/service.py", negative.stdout)
        self.assertIn("remove forbidden-import", negative.stdout)

    def test_knowledge_scan_and_check_are_read_only(self) -> None:
        project = self.create_git_project("read-only-knowledge")
        initialized = self.init_project(project, self.write_bundle(project, "read-only"))
        skill_root = Path(initialized["skill_root"])
        operation_locks = skill_root.parent / ".harness-operation-locks"
        audited = self.cli(project, "project", "audit")
        self.assertTrue(audited["initialized"])
        self.assertTrue(operation_locks.is_dir())
        before = self.tree_hashes(skill_root)
        (project / "README.md").write_text("# Changed\n\nCanonical evidence changed.\n", encoding="utf-8")
        changed_project = self.tree_hashes(project)
        scanned = self.cli(project, "knowledge", "scan")
        self.assertTrue(scanned["ok"])
        self.assertTrue(scanned["read_only"])
        self.assertTrue(scanned["healthy"])
        self.assertFalse(scanned["stale"])
        self.cli(project, "knowledge", "check")
        self.assertEqual(before, self.tree_hashes(skill_root))
        self.assertEqual(changed_project, self.tree_hashes(project))
        pending = self.runtime_transactions.content_transaction_store(skill_root) / "pending-read-only"
        pending.mkdir(parents=True)
        (pending / "sentinel.txt").write_text("keep\n", encoding="utf-8")
        transaction_before = self.tree_hashes(skill_root)
        for command in (("knowledge", "scan"), ("knowledge", "check")):
            rejected = self.cli(project, *command, expected=(2,))
            self.assertIn("incomplete content transaction", rejected["error"])
        wrapped = self.run_process([
            sys.executable, str(skill_root / "scripts" / "check_project_wiki_stale.py"),
            "--skill-root", str(skill_root), "--project-root", str(project),
        ], expected=(2,))
        self.assertIn("incomplete content transaction", json.loads(wrapped.stdout)["error"])
        self.assertEqual(transaction_before, self.tree_hashes(skill_root))
        self.assertTrue((pending / "sentinel.txt").is_file())

    def test_knowledge_fingerprints_have_one_generation_and_scan_contract(self) -> None:
        project = self.create_git_project("fingerprint-contract")
        package = project / "package.json"
        original = '{"name":"fingerprint-contract","scripts":{"test":"node --test"}}\n'
        package.write_text(original, encoding="utf-8")
        self.git(project, "add", "package.json")
        self.git(project, "commit", "-m", "add package evidence")
        bundle = self.write_bundle(
            project,
            "fingerprint-contract",
            command="npm test",
            command_evidence="package.json",
            language="TypeScript",
        )
        initialized = self.init_project(project, bundle)
        skill_root = Path(initialized["skill_root"])
        index_path = skill_root / "references" / "project_wiki" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        package_records = [
            item for item in index["items"]
            if "package.json" in item.get("source_fingerprints", {})
        ]
        self.assertTrue(package_records)
        expected = package_records[0]["source_fingerprints"]["package.json"]
        self.assertEqual(expected, self.runtime_knowledge.source_fingerprint(package, project))

        baseline = self.cli(project, "knowledge", "scan")
        self.assertTrue(baseline["healthy"])
        self.assertFalse(baseline["stale"])
        self.assertEqual(baseline["findings"], [])
        self.assertTrue(self.cli(project, "knowledge", "check")["healthy"])
        self.assertTrue(self.cli(project, "project", "doctor")["healthy"])
        wrapper = skill_root / "scripts" / "check_project_wiki_stale.py"
        wrapped = self.run_process([
            sys.executable, str(wrapper), "--skill-root", str(skill_root),
            "--project-root", str(project),
        ])
        self.assertTrue(json.loads(wrapped.stdout)["healthy"])

        package.write_text('{"name":"fingerprint-contract","scripts":{"test":"node --test test"}}\n', encoding="utf-8")
        changed = self.cli(project, "knowledge", "scan", expected=(1,))
        self.assertEqual({item["type"] for item in changed["findings"]}, {"changed"})
        self.assertEqual({item["source"] for item in changed["findings"]}, {"package.json"})
        wrapped = self.run_process([
            sys.executable, str(wrapper), "--skill-root", str(skill_root),
            "--project-root", str(project),
        ], expected=(1,))
        wrapped_payload = json.loads(wrapped.stdout)
        self.assertTrue(wrapped_payload["ok"])
        self.assertFalse(wrapped_payload["healthy"])
        self.assertEqual(
            {item["source"] for item in wrapped_payload["findings"]},
            {"package.json"},
        )
        package.write_text(original, encoding="utf-8")
        self.assertTrue(self.cli(project, "knowledge", "scan")["healthy"])

        package.unlink()
        missing = self.cli(project, "knowledge", "scan", expected=(1,))
        self.assertEqual({item["type"] for item in missing["findings"]}, {"missing"})
        package.write_text(original, encoding="utf-8")

        original_index = index_path.read_bytes()
        tampered = json.loads(original_index.decode("utf-8"))
        target = next(item for item in tampered["items"] if "package.json" in item.get("source_fingerprints", {}))
        target["source_fingerprints"]["package.json"] = "not-a-fingerprint"
        index_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
        invalid = self.cli(project, "knowledge", "scan", expected=(1,))
        self.assertIn("invalid_fingerprint", {item["type"] for item in invalid["findings"]})

        tampered = json.loads(original_index.decode("utf-8"))
        target = next(item for item in tampered["items"] if "package.json" in item.get("source_fingerprints", {}))
        fingerprint = target["source_fingerprints"].pop("package.json")
        target["source_fingerprints"]["../package.json"] = fingerprint
        index_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
        invalid = self.cli(project, "knowledge", "scan", expected=(1,))
        self.assertIn("invalid_source", {item["type"] for item in invalid["findings"]})
        index_path.write_bytes(original_index)

        outside = self.root / "outside-source.txt"
        outside.write_text("outside\n", encoding="utf-8")
        with mock.patch.object(
            self.runtime_knowledge,
            "knowledge_source_location",
            return_value=(outside, project),
        ):
            result = self.runtime_knowledge.knowledge_fingerprint_scan(
                skill_root,
                self.runtime_project.project_context(project),
            )
        self.assertIn("outside_project", {item["type"] for item in result["findings"]})

    def test_git_source_fingerprint_is_stable_across_line_endings(self) -> None:
        project = self.create_git_project("line-ending-fingerprint")
        (project / ".gitattributes").write_text("* text=auto\n", encoding="utf-8")
        self.git(project, "add", ".gitattributes")
        self.git(project, "commit", "-m", "normalize text")
        self.init_project(project, self.write_bundle(project, "line-ending-fingerprint"))
        source = project / "src" / "jobs" / "service.py"
        original = source.read_text(encoding="utf-8")
        before = self.runtime_knowledge.source_fingerprint(source, project)
        source.write_bytes(original.replace("\n", "\r\n").encode("utf-8"))
        after = self.runtime_knowledge.source_fingerprint(source, project)
        self.assertEqual(before, after)
        self.assertTrue(self.cli(project, "knowledge", "scan")["healthy"])

    def test_scoped_preflight_fingerprints_only_related_unique_sources(self) -> None:
        project = self.root / "scoped-fingerprints"
        project.mkdir()
        related = {
            "direct": "src/direct/change.py",
            "contract": "src/contract/affected.py",
            "module": "src/jobs/service.py",
        }
        for source in related.values():
            path = project / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {source}\n", encoding="utf-8")
        unrelated_sources = []
        for index in range(100):
            source = f"src/unrelated/source-{index}.py"
            unrelated_sources.append(source)
            path = project / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {source}\n", encoding="utf-8")

        skill_root = self.root / "scoped-skill"
        wiki = skill_root / "references" / "project_wiki"
        wiki.mkdir(parents=True)
        items = [
            {"id": "direct-item", "kind": "bridge", "source_fingerprints": {related["direct"]: "0" * 64}},
            {"id": "contract-item", "kind": "bridge", "source_fingerprints": {related["contract"]: "0" * 64}},
            {"id": "job-processing", "kind": "module", "source_fingerprints": {related["module"]: "0" * 64}},
        ]
        for index in range(597):
            source = unrelated_sources[index % len(unrelated_sources)]
            items.append({
                "id": f"unrelated-{index}",
                "kind": "bridge",
                "source_fingerprints": {source: "0" * 64},
            })
        (wiki / "index.json").write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
        context = self.runtime_project.project_context(project)
        current = {"paths": ["src/direct"]}
        contract = {"affected_paths": ["src/contract"], "owner_module": "job-processing"}

        with mock.patch.object(
            self.runtime_knowledge,
            "_content_fingerprint",
            wraps=self.runtime_knowledge._content_fingerprint,
        ) as fingerprint:
            impacts, scope = self.runtime_changes.knowledge_drift_impacts(
                skill_root, context, current, contract,
            )
        self.assertEqual(scope, {"candidate_items": 3, "checked_sources": 3})
        self.assertEqual(fingerprint.call_count, 3)
        self.assertEqual({item["knowledge_id"] for item in impacts}, {
            "direct-item", "contract-item", "job-processing",
        })

        with mock.patch.object(
            self.runtime_knowledge,
            "_content_fingerprint",
            wraps=self.runtime_knowledge._content_fingerprint,
        ) as fingerprint:
            full = self.runtime_knowledge.knowledge_fingerprint_scan(skill_root, context)
        self.assertEqual(full["checked"], 600)
        self.assertEqual(full["unique_sources"], 103)
        self.assertEqual(fingerprint.call_count, 103)

    def test_git_fingerprint_snapshot_batches_clean_sources_by_repository(self) -> None:
        project = self.create_git_project("batched-fingerprint-snapshot")
        sources = []
        for index in range(600):
            source = f"src/batch/source-{index}.py"
            path = project / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"VALUE = {index}\n", encoding="utf-8")
            sources.append(source)
        self.git(project, "add", ".")
        self.git(project, "commit", "-m", "add fingerprint sources")
        context = self.runtime_project.project_context(project)
        with mock.patch.object(
            self.runtime_knowledge,
            "git",
            wraps=self.runtime_knowledge.git,
        ) as git_call:
            snapshot = self.runtime_knowledge.SourceFingerprintSnapshot(context)
            snapshot.prime(sources)
        self.assertEqual(len(snapshot.local_sources()), 600)
        self.assertTrue(all(snapshot.result(source)[0] == "current" for source in sources))
        self.assertLessEqual(git_call.call_count, 25)

    def test_focused_evolution_stages_without_full_rescan_and_publishes(self) -> None:
        project, skill_root, _ = self.prepare_evolution("focused-evolution", stage=False)
        bundle = self.write_focused_evolution_bundle(skill_root, "focused-evolution")
        with mock.patch.object(
            self.runtime_evolution,
            "install_analysis_bundle",
            side_effect=AssertionError("focused Evolution must not render a full analysis bundle"),
        ), mock.patch.object(
            self.runtime_evolution,
            "knowledge_check_internal",
            side_effect=AssertionError("focused Evolution must not run a full knowledge check"),
        ):
            staged = self.dispatch(
                project,
                "evolve", "stage",
                "--proposal-id", "accepted-knowledge",
                "--owner", "independent-judge",
                "--analysis-bundle", str(bundle),
            )
        self.assertEqual(staged["mode"], "focused")
        self.assertEqual(staged["next_action"], "independent_judge")
        self.assertEqual(staged["changed_paths"], ["references/workflows/evolve.md"])
        candidate = Path(staged["candidate"])
        self.assertIn(
            "Focused Evolution validates only the affected Harness owners.",
            (candidate / "references" / "workflows" / "evolve.md").read_text(encoding="utf-8"),
        )
        judge = self.write_evolution_judge(skill_root)
        completed = self.cli(
            project,
            "evolve", "mark-complete",
            "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge",
            "--candidate-id", "accepted-knowledge",
            "--judge-report", str(judge),
            "--status", "keep",
        )
        self.assertEqual(completed["status"], "keep")
        self.assertIn(
            "Focused Evolution validates only the affected Harness owners.",
            (skill_root / "references" / "workflows" / "evolve.md").read_text(encoding="utf-8"),
        )

    def test_focused_evolution_can_retire_an_optional_semantic_artifact(self) -> None:
        project = self.root / "focused-retire"
        project.mkdir()
        initialized = self.init_project(project)
        skill_root = Path(initialized["skill_root"])
        target = skill_root / "scripts" / "checks" / "obsolete_check.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("print('obsolete')\n", encoding="utf-8")
        bundle = self.root / "focused-retire-bundle"
        bundle.mkdir()
        delta = {
            "schema_version": "1.0",
            "mode": "evolution-focused",
            "decisions": [],
            "artifacts": [{
                "path": "scripts/checks/obsolete_check.py",
                "action": "retire",
                "owner": "project checks",
                "validation": "retired",
                "evidence": ["registry:change/obsolete-check"],
            }],
        }
        result = self.runtime_rendering.apply_creation_delta(
            skill_root, bundle, delta, self.runtime_project.project_context(project), allow_retire=True,
        )
        self.assertEqual(result["applied"], ["scripts/checks/obsolete_check.py"])
        self.assertFalse(target.exists())

    def test_full_project_migrate_can_retire_an_optional_check(self) -> None:
        project = self.create_git_project("full-migrate-retire")
        initialized = self.init_project(
            project,
            self.write_bundle(project, "full-migrate-retire-base", artifact=True),
            allow_executable_artifacts=True,
        )
        skill_root = Path(initialized["skill_root"])
        target = skill_root / "scripts" / "checks" / "check_project.py"
        self.assertTrue(target.is_file())
        bundle = self.add_bundle_retirement(
            self.write_bundle(project, "full-migrate-retire-update"),
            "scripts/checks/check_project.py",
        )

        migrated = self.cli(project, "project", "migrate", "--analysis-bundle", str(bundle))

        self.assertEqual(
            migrated["applied"]["artifacts"]["applied"],
            ["scripts/checks/check_project.py"],
        )
        self.assertFalse(target.exists())

    def test_full_evolution_can_retire_an_optional_semantic_artifact(self) -> None:
        target_relative = "references/obsolete-project-guidance.md"
        project, skill_root, bundle = self.prepare_evolution(
            "full-evolution-retire",
            stage=False,
            optional_artifact=target_relative,
        )
        target = skill_root / target_relative
        self.assertTrue(target.is_file())
        self.add_bundle_retirement(bundle, target_relative, evidence="registry:change/change-1")

        staged = self.cli(
            project,
            "evolve", "stage",
            "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge",
            "--analysis-bundle", str(bundle),
        )

        self.assertEqual(staged["mode"], "full")
        self.assertTrue(target.is_file())
        self.assertFalse((Path(staged["candidate"]) / target_relative).exists())
        judge = self.write_evolution_judge(skill_root)
        completed = self.cli(
            project,
            "evolve", "mark-complete",
            "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge",
            "--candidate-id", "accepted-knowledge",
            "--judge-report", str(judge),
            "--status", "keep",
        )
        self.assertEqual(completed["status"], "keep")
        self.assertFalse(target.exists())

    def test_init_rejects_retirement_and_full_migrate_preserves_protected_owners(self) -> None:
        init_project = self.create_git_project("init-retire-rejected")
        init_bundle = self.add_bundle_retirement(
            self.write_bundle(init_project, "init-retire-rejected"),
            "scripts/checks/obsolete_check.py",
        )
        rejected = self.cli(
            init_project,
            "project", "init",
            "--analysis-bundle", str(init_bundle),
            expected=(2,),
        )
        self.assertIn("publication candidate", rejected["error"])
        self.assertEqual(list((init_project / ".agents" / "skills").glob("*")), [])

        project = self.create_git_project("full-migrate-retire-protected")
        initialized = self.init_project(
            project,
            self.write_bundle(project, "full-migrate-retire-protected-base"),
        )
        skill_root = Path(initialized["skill_root"])
        revision = json.loads(
            (skill_root / "state" / "manifest.json").read_text(encoding="utf-8")
        )["skill_revision"]
        protected = {
            "SKILL.md": "required project Harness owner",
            "references/rules/red_lines.yaml": "required project Harness owner",
            "references/workflows/intake.md": "required workflow",
            "scripts/harness_runtime/rendering.py": "protected or unsupported",
            "state/manifest.json": "protected or unsupported",
            "references/project_wiki/overview.md": "protected or unsupported",
        }
        for index, (target_relative, expected_error) in enumerate(protected.items()):
            with self.subTest(target=target_relative):
                bundle = self.add_bundle_retirement(
                    self.write_bundle(project, f"full-migrate-protected-{index}"),
                    target_relative,
                )
                result = self.cli(
                    project,
                    "project", "migrate",
                    "--analysis-bundle", str(bundle),
                    expected=(2,),
                )
                self.assertIn(expected_error, result["error"])
                self.assertTrue((skill_root / target_relative).exists())
                self.assertEqual(
                    json.loads(
                        (skill_root / "state" / "manifest.json").read_text(encoding="utf-8")
                    )["skill_revision"],
                    revision,
                )

    def test_full_migrate_retirement_rolls_back_content_and_dynamic_state(self) -> None:
        project = self.create_git_project("full-migrate-retire-rollback")
        initialized = self.init_project(
            project,
            self.write_bundle(project, "full-migrate-retire-rollback-base", artifact=True),
            allow_executable_artifacts=True,
        )
        skill_root = Path(initialized["skill_root"])
        target = skill_root / "scripts" / "checks" / "check_project.py"
        target_bytes = target.read_bytes()
        self.cli(
            project,
            "change", "new", "retirement-rollback",
            "--scope", "Prove retirement publication rollback",
        )
        change_record = skill_root / "state" / "registry" / "changes" / "retirement-rollback.json"
        legacy_record = json.loads(change_record.read_text(encoding="utf-8"))
        legacy_record["status"] = "closing"
        legacy_record["integration_status"] = "not_integrated"
        change_record.write_text(json.dumps(legacy_record, indent=2), encoding="utf-8")
        index_path = skill_root / "state" / "changes" / "INDEX.json"
        legacy_index = json.loads(index_path.read_text(encoding="utf-8"))
        legacy_index["rollback_sentinel"] = True
        index_path.write_text(json.dumps(legacy_index, indent=2), encoding="utf-8")
        before = self.tree_hashes(skill_root)
        before_state = self.tree_hashes(skill_root / "state")
        bundle = self.add_bundle_retirement(
            self.write_bundle(project, "full-migrate-retire-rollback-update"),
            "scripts/checks/check_project.py",
            evidence="registry:change/retirement-rollback",
        )
        observed_published_retirement = False
        original_atomic_write_json = self.runtime_project_commands.atomic_write_json

        def fail_after_dynamic_state_normalization(path: Path, value: dict) -> None:
            nonlocal observed_published_retirement
            if Path(path) == skill_root / "state" / "manifest.json" and value.get("skill_revision") == 2:
                self.assertFalse(target.exists())
                self.assertEqual(
                    json.loads(change_record.read_text(encoding="utf-8"))["integration_status"],
                    "not_requested",
                )
                self.assertNotIn(
                    "rollback_sentinel",
                    json.loads(index_path.read_text(encoding="utf-8")),
                )
                observed_published_retirement = True
                raise self.cli_module.HarnessError("injected post-normalization failure")
            original_atomic_write_json(path, value)

        with mock.patch.object(
            self.runtime_project_commands,
            "atomic_write_json",
            side_effect=fail_after_dynamic_state_normalization,
        ):
            with self.assertRaisesRegex(self.cli_module.HarnessError, "injected post-normalization failure"):
                self.dispatch(project, "project", "migrate", "--analysis-bundle", str(bundle))

        self.assertTrue(observed_published_retirement)
        self.assertEqual(target.read_bytes(), target_bytes)
        self.assertEqual(before_state, self.tree_hashes(skill_root / "state"))
        self.assertEqual(before, self.tree_hashes(skill_root))
        self.assertFalse(self.runtime_transactions.content_transaction_store(skill_root).exists())

    def test_open_agent_knowledge_is_indexed_and_preserved_by_full_refresh(self) -> None:
        project = self.create_git_project("open-agent-knowledge")
        initialized = self.init_project(project, self.write_bundle(project, "open-agent-knowledge"))
        skill_root = Path(initialized["skill_root"])
        bundle = self.root / "open-agent-knowledge-focused"
        artifacts = bundle / "artifacts"
        artifacts.mkdir(parents=True)
        target_source = artifacts / "office-v2.md"
        target_source.write_text(
            self.agent_knowledge_document("office-v2-target", title="Office V2 Target Architecture"),
            encoding="utf-8",
        )
        takeover_source = artifacts / "job-processing.md"
        takeover_source.write_text(
            self.agent_knowledge_document(
                "job-processing",
                title="Agent-Owned Job Processing",
                kind="current",
                status="implemented",
                owner="job-processing",
                evidence=("src/jobs/service.py",),
            ),
            encoding="utf-8",
        )
        delta = {
            "schema_version": "1.0",
            "mode": "migrate-focused",
            "decisions": [],
            "artifacts": [
                {
                    "path": "references/project_wiki/roadmaps/office/v2.md",
                    "action": "create",
                    "source": "artifacts/office-v2.md",
                    "owner": "project-architecture",
                    "validation": "text-present",
                    "evidence": ["user:accepted project direction"],
                },
                {
                    "path": "references/project_wiki/modules/job-processing.md",
                    "action": "replace",
                    "source": "artifacts/job-processing.md",
                    "owner": "job-processing",
                    "validation": "text-present",
                    "evidence": ["src/jobs/service.py"],
                },
            ],
        }
        (bundle / "creation-delta.json").write_text(json.dumps(delta, indent=2), encoding="utf-8")
        migrated = self.cli(project, "project", "migrate", "--analysis-bundle", str(bundle))
        self.assertEqual(migrated["applied"]["mode"], "focused")
        index = json.loads((skill_root / "references/project_wiki/index.json").read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in index["items"]}
        self.assertEqual(by_id["office-v2-target"]["path"], "roadmaps/office/v2.md")
        self.assertEqual(by_id["job-processing"]["managed_by"], "agent")
        catalog = (skill_root / "references/project_wiki/catalog.md").read_text(encoding="utf-8")
        self.assertIn("roadmaps/office/v2.md", catalog)
        self.assertIn("target", catalog)

        refresh = self.write_bundle(project, "open-agent-knowledge-refresh")
        with mock.patch.object(
            self.runtime_rendering,
            "rebuild_project_wiki_index",
            wraps=self.runtime_rendering.rebuild_project_wiki_index,
        ) as rebuild_index:
            self.dispatch(project, "project", "migrate", "--analysis-bundle", str(refresh))
        self.assertEqual(rebuild_index.call_count, 1)
        self.assertEqual(target_source.read_text(encoding="utf-8"), (
            skill_root / "references/project_wiki/roadmaps/office/v2.md"
        ).read_text(encoding="utf-8"))
        self.assertIn(
            "Agent-Owned Job Processing",
            (skill_root / "references/project_wiki/modules/job-processing.md").read_text(encoding="utf-8"),
        )

    def test_focused_migrate_updates_agent_knowledge_without_full_analysis(self) -> None:
        project = self.create_git_project("focused-document-migrate")
        initialized = self.init_project(project, self.write_bundle(project, "focused-document-migrate"))
        skill_root = Path(initialized["skill_root"])
        index_path = skill_root / "references/project_wiki/index.json"
        initial_index = json.loads(index_path.read_text(encoding="utf-8"))
        for number in range(600):
            initial_index["items"].append({
                "id": f"benchmark-{number}",
                "title": f"Benchmark {number}",
                "layer": "L2",
                "kind": "system",
                "status": "implemented",
                "owner": "benchmark",
                "modules": [],
                "path": f"benchmark/{number}.md",
                "sources": ["src/jobs/service.py"],
                "source_fingerprints": {},
                "managed_by": "renderer",
                "generated_by": "benchmark",
            })
        index_path.write_text(json.dumps(initial_index, indent=2), encoding="utf-8")
        bundle = self.root / "focused-document-migrate-bundle"
        artifacts = bundle / "artifacts"
        artifacts.mkdir(parents=True)
        source = artifacts / "decision.md"
        source.write_text(
            self.agent_knowledge_document(
                "queue-decision",
                title="Queue Decision",
                kind="decision",
                owner="job-processing",
                evidence=("src/jobs/service.py",),
            ),
            encoding="utf-8",
        )
        delta = {
            "schema_version": "1.0",
            "mode": "migrate-focused",
            "decisions": [],
            "artifacts": [{
                "path": "references/project_wiki/decisions/queue.md",
                "action": "create",
                "source": "artifacts/decision.md",
                "owner": "job-processing",
                "validation": "text-present",
                "evidence": ["src/jobs/service.py"],
            }],
        }
        (bundle / "creation-delta.json").write_text(json.dumps(delta, indent=2), encoding="utf-8")
        with mock.patch.object(
            self.runtime_project_commands,
            "install_analysis_bundle",
            side_effect=AssertionError("focused migrate must not install a full analysis bundle"),
        ), mock.patch.object(
            self.runtime_project_commands,
            "knowledge_check_internal",
            side_effect=AssertionError("focused migrate must not run a full knowledge check"),
        ), mock.patch.object(
            self.runtime_knowledge,
            "discover_agent_knowledge",
            side_effect=AssertionError("focused migrate must not discover all Wiki documents"),
        ), mock.patch.object(
            self.runtime_knowledge,
            "agent_knowledge_item",
            wraps=self.runtime_knowledge.agent_knowledge_item,
        ) as item_builder, mock.patch.object(
            self.runtime_knowledge,
            "context_source_fingerprints",
            wraps=self.runtime_knowledge.context_source_fingerprints,
        ) as fingerprints:
            result = self.dispatch(project, "project", "migrate", "--analysis-bundle", str(bundle))
        self.assertEqual(result["applied"]["mode"], "focused")
        self.assertTrue((skill_root / "references/project_wiki/decisions/queue.md").is_file())
        self.assertEqual(item_builder.call_count, 1)
        self.assertEqual(fingerprints.call_count, 1)
        updated_index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(len(updated_index["items"]), len(initial_index["items"]) + 1)
        catalog = (skill_root / "references/project_wiki/catalog.md").read_text(encoding="utf-8")
        self.assertIn("benchmark/599.md", catalog)
        self.assertIn("decisions/queue.md", catalog)

        retire_bundle = self.root / "focused-document-retire-bundle"
        retire_bundle.mkdir()
        retire_delta = {
            "schema_version": "1.0",
            "mode": "migrate-focused",
            "decisions": [],
            "artifacts": [{
                "path": "references/project_wiki/decisions/queue.md",
                "action": "retire",
                "owner": "job-processing",
                "validation": "retired",
                "evidence": ["user:accepted project direction"],
            }],
        }
        (retire_bundle / "creation-delta.json").write_text(
            json.dumps(retire_delta, indent=2), encoding="utf-8",
        )
        retired = self.cli(project, "project", "migrate", "--analysis-bundle", str(retire_bundle))
        self.assertEqual(retired["applied"]["mode"], "focused")
        self.assertFalse((skill_root / "references/project_wiki/decisions/queue.md").exists())
        retired_index = json.loads((skill_root / "references/project_wiki/index.json").read_text(encoding="utf-8"))
        self.assertNotIn("queue-decision", {item["id"] for item in retired_index["items"]})

    def test_open_knowledge_keeps_mechanical_guards_without_semantic_gates(self) -> None:
        project = self.create_git_project("open-knowledge-safety")
        initialized = self.init_project(project, self.write_bundle(project, "open-knowledge-safety"))
        skill_root = Path(initialized["skill_root"])
        self.assertFalse(self.runtime_rendering.allowed_artifact_target("references/project_wiki/index.json"))
        self.assertFalse(self.runtime_rendering.allowed_artifact_target("scripts/harness_runtime/core.py"))
        self.assertTrue(self.runtime_rendering.allowed_artifact_target("references/designs/target.yaml"))

        target_bundle = self.root / "target-classification"
        target_artifacts = target_bundle / "artifacts"
        target_artifacts.mkdir(parents=True)
        target_source = target_artifacts / "implemented-target.md"
        target_source.write_text(
            self.agent_knowledge_document(
                "implemented-target",
                title="Implemented Target",
                kind="target",
                status="implemented",
                evidence=("src/jobs/service.py",),
            ),
            encoding="utf-8",
        )
        target_delta = {
            "schema_version": "1.0",
            "mode": "migrate-focused",
            "decisions": [],
            "artifacts": [{
                "path": "references/project_wiki/targets/implemented.md",
                "action": "create",
                "source": "artifacts/implemented-target.md",
                "owner": "project-architecture",
                "validation": "text-present",
                "evidence": ["src/jobs/service.py"],
            }],
        }
        (target_bundle / "creation-delta.json").write_text(
            json.dumps(target_delta, indent=2), encoding="utf-8",
        )
        self.cli(project, "project", "migrate", "--analysis-bundle", str(target_bundle))

        target_source.write_text(
            self.agent_knowledge_document(
                "implemented-target",
                title="Implemented Target",
                kind="target",
                status="implemented",
                owner="next-architecture-owner",
                evidence=("src/jobs/service.py",),
            ),
            encoding="utf-8",
        )
        target_delta["artifacts"][0]["action"] = "replace"
        target_delta["artifacts"][0]["owner"] = "next-architecture-owner"
        (target_bundle / "creation-delta.json").write_text(
            json.dumps(target_delta, indent=2), encoding="utf-8",
        )
        self.cli(project, "project", "migrate", "--analysis-bundle", str(target_bundle))
        transferred_index = json.loads(
            (skill_root / "references/project_wiki/index.json").read_text(encoding="utf-8")
        )
        transferred = next(item for item in transferred_index["items"] if item["id"] == "implemented-target")
        self.assertEqual(transferred["owner"], "next-architecture-owner")

        target_path = skill_root / "references/project_wiki/targets/implemented.md"
        context = self.runtime_project.project_context(project)
        target_content = target_path.read_text(encoding="utf-8")
        target_path.write_text(target_content + "\n[Missing](missing.md)\n", encoding="utf-8")
        with self.assertRaisesRegex(self.runtime_core.HarnessError, "invalid local links"):
            self.runtime_knowledge.update_project_wiki_index(
                skill_root, context, {"targets/implemented.md"},
            )
        target_path.write_text(target_content, encoding="utf-8")

        empty = skill_root / "references/project_wiki/guides/empty.md"
        empty.parent.mkdir(parents=True)
        empty.write_text(
            "---\necl:\n  id: empty-agent-knowledge\n  layer: L2\n  kind: guide\n"
            "  status: accepted\n  owner: guide-owner\n  modules: []\n"
            "  evidence: [user:accepted empty guide]\n  managed_by: agent\n---\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(self.runtime_core.HarnessError, "non-empty body"):
            self.runtime_knowledge.update_project_wiki_index(skill_root, context, {"guides/empty.md"})
        empty.unlink()

        orphan = skill_root / "references/project_wiki/custom/orphan.md"
        orphan.parent.mkdir(parents=True)
        orphan.write_text("# Orphan\n\nUnindexed project knowledge.\n", encoding="utf-8")
        source = skill_root / "references/project_wiki/modules/job-processing.md"
        duplicate = skill_root / "references/project_wiki/custom/duplicate.md"
        duplicate.write_bytes(source.read_bytes())
        index_path = skill_root / "references/project_wiki/index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        duplicate_item = dict(next(item for item in index["items"] if item["id"] == "job-processing"))
        duplicate_item["id"] = "job-processing-copy"
        duplicate_item["path"] = "custom/duplicate.md"
        index["items"].append(duplicate_item)
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        checked = self.cli(project, "knowledge", "check", expected=(1,))
        types = {item["type"] for item in checked["findings"]}
        self.assertIn("orphan_knowledge_document", types)
        self.assertNotIn("duplicate_knowledge_content", types)

    def test_fingerprint_finding_types_share_canonical_audit_names(self) -> None:
        aliases = {
            "changed": "knowledge_drift",
            "missing": "missing_knowledge_source",
            "invalid_source": "invalid_knowledge_source",
            "outside_project": "external_knowledge_source",
            "invalid_fingerprint": "invalid_knowledge_fingerprint",
        }
        for raw, canonical in aliases.items():
            self.assertEqual(self.runtime_knowledge.canonical_knowledge_finding_type(raw), canonical)
            self.assertEqual(self.runtime_knowledge.canonical_knowledge_finding_type(canonical), canonical)

    def test_evolution_rejects_project_evidence_changed_after_staging(self) -> None:
        project, skill_root, _ = self.prepare_evolution("source-changed-after-stage")
        judge = self.write_evolution_judge(skill_root)
        metadata_path = (
            skill_root / "state" / "evolution" / "staging" / "accepted-knowledge" / "state" / "candidate.json"
        )
        original_metadata = metadata_path.read_bytes()
        metadata = json.loads(original_metadata)
        metadata["source_snapshot"] = {
            "sources": [],
            "digest": self.runtime_knowledge.SourceFingerprintSnapshot(
                self.runtime_project.project_context(project),
            ).digest([]),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        tampered = self.cli(
            project,
            "evolve", "mark-complete",
            "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge",
            "--candidate-id", "accepted-knowledge",
            "--judge-report", str(judge),
            "--status", "keep",
            expected=(2,),
        )
        self.assertIn("metadata was modified", tampered["error"].lower())
        metadata_path.write_bytes(original_metadata)
        source = project / "src" / "jobs" / "service.py"
        original_judge = self.runtime_evolution.evolution_judge_report

        def review_then_change_source(*args):
            report = original_judge(*args)
            source.write_text(source.read_text(encoding="utf-8") + "\n# changed after review\n", encoding="utf-8")
            return report

        with mock.patch.object(
            self.runtime_evolution,
            "evolution_judge_report",
            side_effect=review_then_change_source,
        ):
            with self.assertRaises(self.cli_module.HarnessError) as rejected:
                self.dispatch(
                    project,
                    "evolve", "mark-complete",
                    "--proposal-id", "accepted-knowledge",
                    "--owner", "independent-judge",
                    "--candidate-id", "accepted-knowledge",
                    "--judge-report", str(judge),
                    "--status", "keep",
                )
        self.assertIn("evidence changed", str(rejected.exception).lower())
        self.assertTrue((skill_root / "state" / "registry" / "locks" / "evolution-owner").exists())

    def test_read_only_knowledge_waits_for_content_publication(self) -> None:
        project = self.create_git_project("read-lock")
        initialized = self.init_project(project, self.write_bundle(project, "read-lock"))
        skill_root = Path(initialized["skill_root"])
        entered = threading.Event()
        release = threading.Event()
        completed = threading.Event()
        result: dict[str, object] = {}

        def hold_publication() -> None:
            with self.runtime_transactions.content_publication_guard(skill_root):
                entered.set()
                release.wait(5)

        def scan() -> None:
            try:
                result.update(self.dispatch(project, "knowledge", "scan"))
            finally:
                completed.set()

        holder = threading.Thread(target=hold_publication)
        reader = threading.Thread(target=scan)
        holder.start()
        self.assertTrue(entered.wait(2))
        reader.start()
        self.assertFalse(completed.wait(0.2))
        release.set()
        holder.join(10)
        reader.join(30)
        self.assertFalse(holder.is_alive())
        self.assertFalse(reader.is_alive())
        self.assertTrue(completed.is_set())
        self.assertTrue(result.get("healthy"))

    def test_runtime_copy_is_a_controlled_machine_owned_mirror(self) -> None:
        destination = self.root / "runtime-mirror"
        scripts = destination / "scripts"
        package = scripts / "harness_runtime"
        checks = scripts / "checks"
        helpers = scripts / "helpers"
        package.mkdir(parents=True)
        checks.mkdir()
        helpers.mkdir()
        (package / "obsolete.py").write_text("obsolete = True\n", encoding="utf-8")
        (package / "__pycache__").mkdir()
        (package / "__pycache__" / "obsolete.pyc").write_bytes(b"old")
        (scripts / "obsolete_runtime.py").write_text("obsolete = True\n", encoding="utf-8")
        (scripts / "harness-project.sh").write_text("old launcher\n", encoding="utf-8")
        (checks / "project_check.py").write_text("print('check')\n", encoding="utf-8")
        (helpers / "project_helper.py").write_text("print('helper')\n", encoding="utf-8")
        references = destination / "references"
        references.mkdir()
        (references / "analysis-contract.md").write_text("stale analysis contract\n", encoding="utf-8")
        (references / "runtime-modules.md").write_text("stale runtime map\n", encoding="utf-8")
        manifest = destination / "state" / "manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            "launchers": [
                "obsolete_runtime.py",
                "harness_runtime/obsolete.py",
                "harness-project.sh",
            ]
        }), encoding="utf-8")

        launchers = self.runtime_links.copy_runtime(destination)
        self.assertFalse((scripts / "obsolete_runtime.py").exists())
        self.assertFalse((package / "obsolete.py").exists())
        self.assertFalse((package / "__pycache__").exists())
        self.assertTrue((checks / "project_check.py").is_file())
        self.assertTrue((helpers / "project_helper.py").is_file())
        source_package = ROOT / "scripts" / "harness_runtime"
        self.assertEqual(
            {path.name: path.read_bytes() for path in source_package.glob("*.py")},
            {path.name: path.read_bytes() for path in package.glob("*.py")},
        )
        for name in (
            "harness_cli.py", "detect_adapters.py", "build_analysis_bundle.py",
            "render_greenfield.py", "generate_rule_docs.py",
            "check_project_wiki_stale.py", "check_stage_artifacts.py",
        ):
            self.assertEqual((ROOT / "scripts" / name).read_bytes(), (scripts / name).read_bytes())
        for name in ("analysis-contract.md", "runtime-modules.md", "git-collaboration.md"):
            self.assertEqual(
                (ROOT / "assets" / "project-skill" / "references" / name).read_bytes(),
                (references / name).read_bytes(),
            )
        for suffix in ("ps1", "cmd", "sh"):
            self.assertIn(f"harness-project.{suffix}", launchers)
            self.assertTrue((scripts / f"harness-project.{suffix}").is_file())

        stale_source = (ROOT / "scripts" / "check_project_wiki_stale.py").read_text(encoding="utf-8")
        stage_source = (ROOT / "scripts" / "check_stage_artifacts.py").read_text(encoding="utf-8")
        rule_source = (ROOT / "scripts" / "generate_rule_docs.py").read_text(encoding="utf-8")
        self.assertNotIn("hashlib", stale_source)
        self.assertNotIn("def sha256", stale_source)
        self.assertIn("knowledge_fingerprint_scan", stale_source)
        self.assertNotIn('manifest.get("project_root")', stale_source)
        self.assertIn('parser.add_argument("--project-root", type=Path, required=True)', stale_source)
        self.assertNotIn("def canonical_id", stage_source)
        self.assertNotIn("def atomic_write", rule_source)

    def test_runtime_copy_rejects_linked_machine_owned_package(self) -> None:
        destination = self.root / "linked-runtime-mirror"
        scripts = destination / "scripts"
        scripts.mkdir(parents=True)
        external = self.root / "external-runtime-package"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        package = scripts / "harness_runtime"
        self.runtime_links.create_directory_link(package, external)

        with self.assertRaisesRegex(self.cli_module.HarnessError, "physical directory"):
            self.runtime_links.copy_runtime(destination)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertTrue(os.path.samefile(package, external))

    def test_controlled_tree_removal_never_follows_nested_links(self) -> None:
        owner = self.root / "owned-cleanup"
        managed = owner / "candidate"
        managed.mkdir(parents=True)
        (managed / "owned.txt").write_text("owned\n", encoding="utf-8")
        external = self.root / "external-cleanup-target"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        self.runtime_links.create_directory_link(managed / "nested-link", external)

        with self.assertRaisesRegex(self.cli_module.HarnessError, "must not contain links"):
            self.runtime_core.remove_owned_tree(managed, owner, "fixture candidate")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertTrue((managed / "owned.txt").is_file())

    @unittest.skipUnless(os.name == "nt", "Windows reparse fallback is Windows-specific")
    def test_windows_reparse_fallback_does_not_require_os_path_isjunction(self) -> None:
        target = self.root / "junction-fallback-target"
        target.mkdir()
        junction = self.root / "junction-fallback-link"
        self.runtime_links.create_directory_link(junction, target)
        with mock.patch.object(os.path, "isjunction", None, create=True):
            self.assertTrue(self.runtime_core.windows_reparse_directory(junction))
            self.assertTrue(self.runtime_core.is_link_like(junction))
        self.runtime_core.unlink_directory_link_node(junction)
        self.assertTrue(target.is_dir())

    @unittest.skipUnless(os.name == "nt", "Windows Junction safety is Windows-specific")
    def test_rendered_python_connector_rejects_canonical_junction_without_isjunction(self) -> None:
        project = self.create_git_project("connector-old-python-junction")
        initialized = self.init_project(project, self.write_bundle(project, "connector-old-python-junction"))
        baseline = self.commit_routes(project)
        worktree = self.root / "connector-old-python-junction-worktree"
        self.git(project, "worktree", "add", "-b", "connector-old-python-junction", str(worktree), baseline)
        skill_root = Path(initialized["skill_root"])
        manifest = json.loads((skill_root / "state" / "manifest.json").read_text(encoding="utf-8"))
        connector = worktree / "scripts" / "old-python-link.py"
        connector.write_text(
            self.runtime_core.render(
                (ROOT / "assets" / "project-skill" / "assets" / "templates" / "harness-skill-link.py.tpl").read_text(encoding="utf-8"),
                {"SKILL_NAME": skill_root.name, "PROJECT_ID": manifest["project_id"]},
            ),
            encoding="utf-8",
        )
        physical = self.root / "moved-physical-harness"
        shutil.move(str(skill_root), str(physical))
        self.runtime_links.create_directory_link(skill_root, physical)
        try:
            wrapper = (
                "import os, runpy, sys; "
                "os.path.isjunction = None; "
                "sys.argv = [sys.argv[1]]; "
                "runpy.run_path(sys.argv[0], run_name='__main__')"
            )
            rejected = self.run_process(
                [sys.executable, "-c", wrapper, str(connector)],
                cwd=worktree,
                expected=(1,),
            )
            self.assertIn("must be physical", rejected.stderr)
            self.assertFalse(os.path.lexists(worktree / ".agents" / "skills" / skill_root.name))
            self.assertFalse(os.path.lexists(worktree / ".claude" / "skills" / skill_root.name))
        finally:
            self.runtime_core.unlink_directory_link_node(skill_root)
            shutil.move(str(physical), str(skill_root))

    def test_production_runtime_has_one_recursive_directory_deletion_owner(self) -> None:
        runtime = ROOT / "scripts" / "harness_runtime"
        offenders = []
        for path in runtime.glob("*.py"):
            if path.name == "core.py":
                continue
            if "shutil.rmtree" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_project_harness_routes_scripts_only_for_mechanical_state(self) -> None:
        entry = (ROOT / "assets" / "project-skill" / "SKILL.md.tpl").read_text(encoding="utf-8")
        intake = (ROOT / "assets" / "project-skill" / "references" / "workflows" / "intake.md").read_text(encoding="utf-8")
        locate = (ROOT / "assets" / "project-skill" / "references" / "workflows" / "locate.md").read_text(encoding="utf-8")
        implement = (ROOT / "assets" / "project-skill" / "references" / "workflows" / "implement.md").read_text(encoding="utf-8")
        runtime = (ROOT / "references" / "runtime-modules.md").read_text(encoding="utf-8")
        self.assertIn("explanation, navigation, or read-only source research", entry)
        self.assertIn("In single-Lane mode, Small Changes", entry)
        self.assertIn("publish scope", entry)
        self.assertIn("every repository mutation uses", entry)
        self.assertIn("Single-Lane Small work does not require", intake)
        self.assertNotIn("preflight before classification", intake)
        self.assertNotIn("preflight` before source search", locate)
        self.assertNotIn("preflight` at stage entry", implement)
        self.assertNotIn("300 lines", runtime)
        self.assertNotIn("1000 lines", runtime)

    def test_stage_checker_reads_skill_owned_change_evidence(self) -> None:
        project = self.create_git_project("stage-check")
        initialized = self.init_project(project, self.write_bundle(project, "stage-check"))
        self.commit_routes(project)
        self.cli(project, "change", "new", "stage-change", "--scope", "validate stage evidence")
        skill_root = Path(initialized["skill_root"])
        checker = skill_root / "scripts" / "check_stage_artifacts.py"
        result = self.run_process([
            sys.executable, str(checker), "--stage", "intake", "--change-id", "stage-change",
        ])
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertFalse((project / "harness" / "changes").exists())

    def test_linked_skill_ancestors_and_mismatched_manifest_are_rejected(self) -> None:
        linked_project = self.create_git_project("linked-ancestor")
        external = self.root / "external-agents"
        external.mkdir()
        self.runtime_links.create_directory_link(linked_project / ".agents", external)
        rejected = self.cli(
            linked_project,
            "project",
            "init",
            "--analysis-bundle",
            str(self.write_bundle(linked_project, "linked-ancestor")),
            expected=(2,),
        )
        self.assertIn("link or junction", rejected["error"])
        self.assertEqual(list(external.iterdir()), [])

        project = self.create_git_project("manifest-owner")
        initialized = self.init_project(project, self.write_bundle(project, "manifest-owner"))
        manifest_path = Path(initialized["skill_root"]) / "state" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["project_id"] = "wrong-project"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        mismatch = self.cli(project, "change", "status", expected=(2,))
        self.assertIn("Project id does not match", mismatch["error"])

    def test_new_worktree_connector_creates_project_level_codex_and_claude_links(self) -> None:
        project = self.create_git_project("connector-project")
        initialized = self.init_project(project, self.write_bundle(project, "connector"))
        baseline = self.commit_routes(project)
        worktree = self.root / "new-worktree"
        self.git(project, "worktree", "add", "-b", "new-worktree", str(worktree), baseline)
        skill_name = Path(initialized["skill_root"]).name
        codex_link = worktree / ".agents" / "skills" / skill_name
        claude_link = worktree / ".claude" / "skills" / skill_name
        self.assertFalse(codex_link.exists())
        common = Path(self.git(project, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = (project / common).resolve()
        exclude = common / "info" / "exclude"
        existing_excludes = exclude.read_text(encoding="utf-8").splitlines()
        existing_excludes = [line for line in existing_excludes if skill_name not in line]
        existing_excludes.append("/keep-existing-local-entry/")
        exclude.write_text("\n".join(existing_excludes) + "\n", encoding="utf-8")
        attached = self.run_connector(worktree)
        self.assertTrue(attached["ok"])
        self.assertTrue(os.path.samefile(codex_link, initialized["skill_root"]))
        self.assertTrue(os.path.samefile(claude_link, initialized["skill_root"]))
        repaired_excludes = exclude.read_text(encoding="utf-8").splitlines()
        self.assertIn(f"/.agents/skills/{skill_name}", repaired_excludes)
        self.assertIn(f"/.claude/skills/{skill_name}", repaired_excludes)
        self.assertIn("/keep-existing-local-entry/", repaired_excludes)
        route = (worktree / "AGENTS.md").read_text(encoding="utf-8")
        for connector_name in (
            "harness-skill-link.ps1",
            "harness-skill-link.mjs",
            "harness-skill-link.py",
        ):
            self.assertTrue((worktree / "scripts" / connector_name).is_file())
            self.assertIn(connector_name, route)
        generated_skill = (Path(initialized["skill_root"]) / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("python <project-skill-dir>", generated_skill)
        doctor = self.cli(worktree, "project", "doctor", "--repair-links")
        self.assertTrue(doctor["healthy"])
        skill_root = Path(initialized["skill_root"])
        manifest = json.loads((skill_root / "state" / "manifest.json").read_text(encoding="utf-8"))
        for machine_field in ("host_command", "project_root", "git_common_dir", "runtime_links"):
            self.assertNotIn(machine_field, manifest)
        if os.name == "nt":
            launcher = skill_root / "scripts" / "harness-project.ps1"
            launcher_content = launcher.read_text(encoding="utf-8")
            self.assertNotIn(str(Path(sys.executable).resolve()), launcher_content)
            self.assertIn("ECL_HARNESS_PYTHON", launcher_content)
            launcher_command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(launcher),
                "doctor",
                "--project-root",
                str(worktree),
            ]
        else:
            launcher = skill_root / "scripts" / "harness-project.sh"
            launcher_content = launcher.read_text(encoding="utf-8")
            self.assertNotIn(str(Path(sys.executable).resolve()), launcher_content)
            self.assertIn("ECL_HARNESS_PYTHON", launcher_content)
            launcher_command = [
                str(launcher),
                "doctor",
                "--project-root",
                str(worktree),
            ]
        launcher_result = self.run_process(launcher_command, cwd=worktree)
        self.assertTrue(json.loads(launcher_result.stdout)["healthy"])

    def test_worktree_connector_detaches_links_without_touching_shared_harness(self) -> None:
        project = self.create_git_project("connector-detach")
        initialized = self.init_project(project, self.write_bundle(project, "connector-detach"))
        baseline = self.commit_routes(project)
        worktree = self.root / "connector-detach-worktree"
        self.git(project, "worktree", "add", "-b", "connector-detach", str(worktree), baseline)
        skill_root = Path(initialized["skill_root"])
        skill_name = skill_root.name
        codex_link = worktree / ".agents" / "skills" / skill_name
        claude_link = worktree / ".claude" / "skills" / skill_name
        self.run_connector(worktree)
        before = self.tree_hashes(skill_root)

        detached = self.run_connector(worktree, detach=True)
        self.assertEqual(detached["action"], "detached")
        self.assertFalse(os.path.lexists(codex_link))
        self.assertFalse(os.path.lexists(claude_link))
        self.assertEqual(before, self.tree_hashes(skill_root))

        repeated = self.run_connector(worktree, detach=True)
        self.assertEqual(
            {item["status"] for item in repeated["links"].values()},
            {"missing"},
        )
        primary = self.run_process(
            self.connector_command(project, detach=True), cwd=project, expected=(1,),
        )
        self.assertIn("primary worktree", (primary.stderr + primary.stdout).lower())
        self.assertEqual(before, self.tree_hashes(skill_root))

    def test_worktree_connector_detach_prevalidates_all_links(self) -> None:
        project = self.create_git_project("connector-detach-collision")
        initialized = self.init_project(project, self.write_bundle(project, "connector-detach-collision"))
        baseline = self.commit_routes(project)
        worktree = self.root / "connector-detach-collision-worktree"
        self.git(project, "worktree", "add", "-b", "connector-detach-collision", str(worktree), baseline)
        skill_root = Path(initialized["skill_root"])
        codex_link = worktree / ".agents" / "skills" / skill_root.name
        claude_link = worktree / ".claude" / "skills" / skill_root.name
        self.run_connector(worktree)
        self.runtime_links.remove_directory_link(claude_link, skill_root)
        wrong_target = self.root / "wrong-harness-target"
        wrong_target.mkdir()
        (wrong_target / "sentinel.txt").write_text("keep\n", encoding="utf-8")
        self.runtime_links.create_directory_link(claude_link, wrong_target)

        rejected = self.run_process(
            self.connector_command(worktree, detach=True), cwd=worktree, expected=(1,),
        )
        self.assertIn("wrong target", (rejected.stderr + rejected.stdout).lower())
        self.assertTrue(os.path.samefile(codex_link, skill_root))
        self.assertTrue(os.path.samefile(claude_link, wrong_target))
        self.assertTrue((wrong_target / "sentinel.txt").is_file())

    def test_connector_hosts_share_attach_and_detach_contract(self) -> None:
        project = self.create_git_project("connector-host-parity")
        initialized = self.init_project(project, self.write_bundle(project, "connector-host-parity"))
        baseline = self.commit_routes(project)
        worktree = self.root / "connector-host-parity-worktree"
        self.git(project, "worktree", "add", "-b", "connector-host-parity", str(worktree), baseline)
        skill_root = Path(initialized["skill_root"])
        manifest = json.loads((skill_root / "state" / "manifest.json").read_text(encoding="utf-8"))
        replacements = {
            "SKILL_NAME": skill_root.name,
            "PROJECT_ID": manifest["project_id"],
        }
        templates = ROOT / "assets" / "project-skill" / "assets" / "templates"
        hosts = []
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell:
            hosts.append((
                "harness-skill-link.ps1.tpl",
                worktree / "scripts" / "parity-link.ps1",
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"],
                ["-Detach"],
            ))
        node = shutil.which("node")
        if node:
            hosts.append((
                "harness-skill-link.mjs.tpl",
                worktree / "scripts" / "parity-link.mjs",
                [node],
                ["--detach"],
            ))
        hosts.append((
            "harness-skill-link.py.tpl",
            worktree / "scripts" / "parity-link.py",
            [sys.executable],
            ["--detach"],
        ))

        for template_name, connector, prefix, detach_args in hosts:
            connector.write_text(
                self.runtime_core.render(
                    (templates / template_name).read_text(encoding="utf-8"), replacements,
                ),
                encoding="utf-8",
            )
            command = [*prefix, str(connector)]
            common = Path(self.git(project, "rev-parse", "--git-common-dir"))
            if not common.is_absolute():
                common = (project / common).resolve()
            exclude = common / "info" / "exclude"
            exclude.write_text(
                "\n".join(line for line in exclude.read_text(encoding="utf-8").splitlines() if skill_root.name not in line) + "\n",
                encoding="utf-8",
            )
            attached = json.loads(self.run_process(command, cwd=worktree).stdout)
            self.assertEqual(attached["action"], "attached", template_name)
            excludes = exclude.read_text(encoding="utf-8").splitlines()
            self.assertIn(f"/.agents/skills/{skill_root.name}", excludes, template_name)
            self.assertIn(f"/.claude/skills/{skill_root.name}", excludes, template_name)
            self.assertEqual(
                {item["status"] for item in attached["links"].values()}, {"attached"}, template_name,
            )
            existing = json.loads(self.run_process(command, cwd=worktree).stdout)
            self.assertEqual(
                {item["status"] for item in existing["links"].values()}, {"existing"}, template_name,
            )
            detached = json.loads(self.run_process([*command, *detach_args], cwd=worktree).stdout)
            self.assertEqual(detached["action"], "detached", template_name)
            self.assertEqual(
                {item["status"] for item in detached["links"].values()}, {"detached"}, template_name,
            )
            missing = json.loads(self.run_process([*command, *detach_args], cwd=worktree).stdout)
            self.assertEqual(
                {item["status"] for item in missing["links"].values()}, {"missing"}, template_name,
            )

    def test_runtime_detach_rolls_back_when_second_link_removal_fails(self) -> None:
        project = self.create_git_project("runtime-detach-rollback")
        initialized = self.init_project(project, self.write_bundle(project, "runtime-detach-rollback"))
        baseline = self.commit_routes(project)
        worktree = self.root / "runtime-detach-rollback-worktree"
        self.git(project, "worktree", "add", "-b", "runtime-detach-rollback", str(worktree), baseline)
        skill_root = Path(initialized["skill_root"])
        codex_link = worktree / ".agents" / "skills" / skill_root.name
        claude_link = worktree / ".claude" / "skills" / skill_root.name
        self.run_connector(worktree)
        original = self.runtime_links.unlink_directory_link_node
        calls = 0

        def fail_second(path: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected second unlink failure")
            original(path)

        with mock.patch.object(self.runtime_links, "unlink_directory_link_node", side_effect=fail_second):
            with self.assertRaisesRegex(self.cli_module.HarnessError, "Could not detach all"):
                self.runtime_links.detach_worktree_links(worktree, skill_root)
        self.assertTrue(os.path.samefile(codex_link, skill_root))
        self.assertTrue(os.path.samefile(claude_link, skill_root))
        self.run_connector(worktree, detach=True)

    def test_new_worktree_connector_rejects_linked_discovery_ancestors(self) -> None:
        project = self.create_git_project("connector-linked-ancestor")
        self.init_project(project, self.write_bundle(project, "connector-linked-ancestor"))
        baseline = self.commit_routes(project)
        worktree = self.root / "connector-linked-worktree"
        self.git(project, "worktree", "add", "-b", "connector-linked", str(worktree), baseline)
        external = self.root / "connector-external-agents"
        external.mkdir()
        self.runtime_links.create_directory_link(worktree / ".agents", external)

        rejected = self.run_process(
            self.connector_command(worktree), cwd=worktree, expected=(1,),
        )
        self.assertIn("link or junction", rejected.stderr)
        self.assertEqual(list(external.iterdir()), [])
        for template in (
            ROOT / "assets" / "project-skill" / "assets" / "templates" / "harness-skill-link.py.tpl",
            ROOT / "assets" / "project-skill" / "assets" / "templates" / "harness-skill-link.mjs.tpl",
            ROOT / "assets" / "project-skill" / "assets" / "templates" / "harness-skill-link.ps1.tpl",
        ):
            self.assertIn("link or junction", template.read_text(encoding="utf-8"))

    def test_new_worktree_connector_rolls_back_partial_links(self) -> None:
        project = self.create_git_project("connector-rollback")
        initialized = self.init_project(project, self.write_bundle(project, "connector-rollback"))
        baseline = self.commit_routes(project)
        worktree = self.root / "connector-rollback-worktree"
        self.git(project, "worktree", "add", "-b", "connector-rollback", str(worktree), baseline)
        skill_name = Path(initialized["skill_root"]).name
        codex_link = worktree / ".agents" / "skills" / skill_name
        claude_collision = worktree / ".claude" / "skills" / skill_name
        claude_collision.mkdir(parents=True)
        (claude_collision / "keep.txt").write_text("unmanaged collision\n", encoding="utf-8")

        rejected = self.run_process(
            self.connector_command(worktree), cwd=worktree, expected=(1,),
        )
        self.assertIn("collision", (rejected.stderr + rejected.stdout).lower())
        self.assertFalse(codex_link.exists())
        self.assertTrue((claude_collision / "keep.txt").is_file())
        templates = ROOT / "assets" / "project-skill" / "assets" / "templates"
        self.assertIn("reversed(created)", (templates / "harness-skill-link.py.tpl").read_text(encoding="utf-8"))
        self.assertIn("created.reverse()", (templates / "harness-skill-link.mjs.tpl").read_text(encoding="utf-8"))
        self.assertIn("$created.Count - 1", (templates / "harness-skill-link.ps1.tpl").read_text(encoding="utf-8"))

    def test_two_worktrees_share_registry_and_detect_contract_conflicts(self) -> None:
        project = self.create_git_project("parallel-project")
        initialized = self.init_project(project, self.write_bundle(project, "parallel"))
        baseline = self.commit_routes(project)
        lane_a = self.root / "lane-a"
        lane_b = self.root / "lane-b"
        self.git(project, "worktree", "add", "-b", "lane-a", str(lane_a), baseline)
        self.git(project, "worktree", "add", "-b", "lane-b", str(lane_b), baseline)
        self.run_connector(lane_a)
        self.run_connector(lane_b)
        self.cli(lane_a, "change", "new", "contract-a", "--scope", "Change API")
        self.cli(lane_b, "change", "new", "contract-b", "--scope", "Change API too")
        base_contract = {
            "kind": "api",
            "subject": "jobs.v1.submit",
            "operation": "change",
            "owner_module": "job-processing",
            "compatibility": "backward-compatible",
            "status": "proposed",
            "affected_paths": ["src/jobs/service.py"],
            "consumers": [],
            "depends_on": [],
        }
        paths = []
        for name in ("a", "b"):
            path = self.root / f"contract-{name}.json"
            path.write_text(json.dumps(base_contract), encoding="utf-8")
            paths.append(path)
        for lane, change, contract in ((lane_a, "contract-a", paths[0]), (lane_b, "contract-b", paths[1])):
            self.cli(
                lane,
                "change",
                "publish",
                change,
                "--status",
                "active",
                "--paths",
                "src/jobs/service.py",
                "--contract",
                str(contract),
            )
        preflight = self.cli(lane_b, "change", "preflight", "--change-id", "contract-b")
        self.assertEqual(preflight["action"], "replan")
        self.assertEqual({item["type"] for item in preflight["conflicts"]}, {"path", "contract"})
        lanes = list((Path(initialized["skill_root"]) / "state" / "registry" / "lanes").glob("*.json"))
        self.assertEqual(len(lanes), 2)
        change_root = Path(initialized["skill_root"]) / "state" / "changes"
        self.assertTrue((change_root / "active" / "contract-a" / "spec.md").is_file())
        self.assertTrue((change_root / "active" / "contract-b" / "spec.md").is_file())
        index = json.loads((change_root / "INDEX.json").read_text(encoding="utf-8"))
        self.assertEqual({item["change_id"] for item in index["changes"]}, {"contract-a", "contract-b"})
        self.assertFalse((project / "harness").exists())

    def test_completed_change_overlap_is_advisory(self) -> None:
        project = self.create_git_project("historical-overlap")
        initialized = self.init_project(project, self.write_bundle(project, "historical-overlap"))
        baseline = self.commit_routes(project)
        lane_a = self.root / "historical-overlap-a"
        lane_b = self.root / "historical-overlap-b"
        self.git(project, "worktree", "add", "-b", "historical-overlap-a", str(lane_a), baseline)
        self.git(project, "worktree", "add", "-b", "historical-overlap-b", str(lane_b), baseline)
        self.run_connector(lane_a)
        self.run_connector(lane_b)
        contract = {
            "kind": "api", "subject": "jobs.v1.submit", "operation": "change",
            "owner_module": "job-processing", "compatibility": "backward-compatible",
            "status": "proposed", "affected_paths": ["src/jobs/service.py"],
            "consumers": [], "depends_on": [],
        }
        contract_a = self.root / "historical-contract-a.json"
        contract_b = self.root / "historical-contract-b.json"
        contract_a.write_text(json.dumps(contract), encoding="utf-8")
        contract_b.write_text(json.dumps(contract), encoding="utf-8")

        self.cli(lane_a, "change", "new", "historical-a", "--scope", "first API change")
        self.cli(
            lane_a, "change", "publish", "historical-a", "--status", "active",
            "--paths", "src/jobs/service.py", "--contract", str(contract_a),
        )
        self.complete_change_documents(lane_a, "historical-a")
        self.cli(
            lane_a, "change", "close", "historical-a", "--status", "completed",
            "--validation", "fixture passed", "--validation-passed",
        )
        self.cli(lane_b, "change", "new", "historical-b", "--scope", "second API change")
        self.cli(
            lane_b, "change", "publish", "historical-b", "--status", "active",
            "--paths", "src/jobs/service.py", "--contract", str(contract_b),
        )
        preflight = self.cli(lane_b, "change", "preflight", "--change-id", "historical-b")
        self.assertEqual(preflight["action"], "continue")
        self.assertEqual(preflight["conflicts"], [])
        self.assertEqual({item["type"] for item in preflight["historical_overlaps"]}, {"path", "contract"})
        record = json.loads((
            Path(initialized["skill_root"]) / "state" / "registry" / "changes" / "historical-a.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(record["integration_status"], "not_requested")

    def test_integration_late_binds_completion_commit_without_rewriting_change(self) -> None:
        project = self.create_git_project("late-bound-integration")
        initialized = self.init_project(project, self.write_bundle(project, "late-bound-integration"))
        baseline = self.commit_routes(project)
        lane = self.root / "late-bound-integration-lane"
        self.git(project, "worktree", "add", "-b", "late-bound-integration", str(lane), baseline)
        self.run_connector(lane)
        self.cli(lane, "change", "new", "late-bound", "--scope", "late-bound delivery")
        self.complete_change_documents(lane, "late-bound")
        (lane / "late-bound.txt").write_text("late boundary\n", encoding="utf-8")
        closed = self.cli(
            lane, "change", "close", "late-bound", "--status", "completed",
            "--validation", "fixture passed", "--validation-passed",
        )
        self.assertEqual(closed["integration_boundary"], "not_recorded")
        missing = self.cli(
            project, "integrate", "start", "late-bound-missing", "late-bound", expected=(2,),
        )
        self.assertIn("no Integration commit boundary", missing["error"])

        self.git(lane, "add", "late-bound.txt")
        self.git(lane, "commit", "-m", "complete late-bound change")
        completion = self.git(lane, "rev-parse", "HEAD")
        started = self.cli(
            project, "integrate", "start", "late-bound-ready", "late-bound",
            "--completion-commit", f"late-bound={completion}",
        )
        self.assertEqual(started["completion_commits"], [completion])
        change = json.loads((
            Path(initialized["skill_root"]) / "state" / "registry" / "changes" / "late-bound.json"
        ).read_text(encoding="utf-8"))
        self.assertIsNone(change["completion_commit"])
        integration = json.loads((
            Path(initialized["skill_root"]) / "state" / "registry" / "integrations" / "late-bound-ready.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(integration["completion_commits"], [completion])
        self.cli(project, "integrate", "abort", "late-bound-ready")

    def test_integration_does_not_refresh_project_wiki(self) -> None:
        project = self.create_git_project("integration-project")
        initialized = self.init_project(project, self.write_bundle(project, "integration"))
        baseline = self.commit_routes(project)
        lane = self.root / "long-lane"
        self.git(project, "worktree", "add", "-b", "long-lane", str(lane), baseline)
        self.run_connector(lane)
        self.complete_git_change(lane, "change-a", "feature-a.txt")
        change_b_commit = self.complete_git_change(lane, "change-b", "feature-b.txt")
        wiki = Path(initialized["skill_root"]) / "references" / "project_wiki"
        before = self.tree_hashes(wiki)
        started = self.cli(project, "integrate", "start", "integration-b", "change-b")
        self.assertEqual(started["completion_commits"], [change_b_commit])
        integration_worktree = Path(started["worktree"])
        self.assertTrue((integration_worktree / "feature-b.txt").exists())
        self.assertFalse((integration_worktree / "feature-a.txt").exists())
        (integration_worktree / "integrator-compatibility.txt").write_text(
            "combined compatibility edit\n",
            encoding="utf-8",
        )
        self.git(integration_worktree, "add", "integrator-compatibility.txt")
        self.git(integration_worktree, "commit", "-m", "add integrator compatibility edit")
        reviewed_commit = self.git(integration_worktree, "rev-parse", "HEAD")
        review_report = self.write_integration_review(Path(initialized["skill_root"]), "integration-b", reviewed_commit)
        completed = self.cli(
            project,
            "integrate",
            "complete",
            "integration-b",
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(review_report),
        )
        self.assertEqual(completed["status"], "integrated")
        self.assertTrue((project / "integrator-compatibility.txt").is_file())
        self.assertIn("integrator-compatibility.txt", completed["record"]["integrator_edits"])
        self.assertEqual(before, self.tree_hashes(wiki))
        self.assertTrue(completed["record"]["evolution_signals"]["knowledge_refresh_deferred_to_evolution"])

    def test_fifth_change_evolution_stages_candidate_and_preserves_dynamic_registry(self) -> None:
        project = self.root / "evolution-project"
        (project / "src" / "jobs").mkdir(parents=True)
        (project / "src" / "runtime").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / "README.md").write_text("# Evolution\n\nAccept jobs and run them.\n", encoding="utf-8")
        (project / "pyproject.toml").write_text("[project]\nname='evolution'\nversion='0.1'\n", encoding="utf-8")
        (project / ".env.example").write_text("APP_MODE=development\n", encoding="utf-8")
        (project / "src" / "jobs" / "service.py").write_text("def submit_job(x): return x\n", encoding="utf-8")
        (project / "src" / "runtime" / "worker.py").write_text("def run(x): return x\n", encoding="utf-8")
        (project / "tests" / "test_jobs.py").write_text("def test_job(): assert True\n", encoding="utf-8")
        initialized = self.init_project(project, self.write_bundle(project, "evolution-base"))
        skill_root = Path(initialized["skill_root"])
        skill_git_head = self.initialize_skill_git_repository(skill_root)
        skill_repository_readme = (skill_root / "README.md").read_bytes()
        original_overview = (skill_root / "references" / "project_wiki" / "overview.md").read_text(encoding="utf-8")
        for index in range(1, 6):
            final = self.complete_non_git_change(project, f"change-{index}")
        self.assertTrue(final["evolution"]["due"])
        claimed = self.cli(
            project,
            "evolve",
            "check",
            "--claim-owner",
            "independent-judge",
            "--e1-confirmed",
        )
        self.assertEqual(len(claimed["eligible_unevaluated"]), 5)
        self.complete_non_git_change(project, "change-6")
        (project / "README.md").write_text(
            "# Evolution\n\nAccept jobs, coordinate runtime execution, and expose durable results.\n",
            encoding="utf-8",
        )
        proposal = skill_root / "state" / "evolution" / "proposals" / "accepted-knowledge.md"
        proposal.write_text(
            "# Evolution Proposal\n\nPromote the canonical runtime/result purpose and retain evidence-backed module ownership.\n",
            encoding="utf-8",
        )
        evolved_bundle = self.write_bundle(
            project,
            "evolution-updated",
            purpose="Accept jobs, coordinate runtime execution, and expose durable results.",
        )
        staged = self.cli(
            project,
            "evolve",
            "stage",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--analysis-bundle",
            str(evolved_bundle),
        )
        self.assertEqual(staged["status"], "candidate_staged")
        judge_report = self.write_evolution_judge(
            skill_root, score=86, eval_mode="full_test", full_test_required=True,
        )
        self.assertEqual(
            original_overview,
            (skill_root / "references" / "project_wiki" / "overview.md").read_text(encoding="utf-8"),
        )
        self.complete_non_git_change(project, "change-7")
        registry_before = self.tree_hashes(skill_root / "state" / "registry")
        changes_before = self.tree_hashes(skill_root / "state" / "changes")
        kept = self.cli(
            project,
            "evolve",
            "mark-complete",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--candidate-id",
            "accepted-knowledge",
            "--judge-report",
            str(judge_report),
            "--status",
            "keep",
        )
        self.assertEqual(kept["status"], "keep")
        updated_overview = (skill_root / "references" / "project_wiki" / "overview.md").read_text(encoding="utf-8")
        self.assertIn("durable results", updated_overview)
        self.assertNotEqual(original_overview, updated_overview)
        self.assertEqual(self.git(skill_root, "rev-parse", "HEAD"), skill_git_head)
        self.assertEqual((skill_root / "README.md").read_bytes(), skill_repository_readme)
        registry_after = self.tree_hashes(skill_root / "state" / "registry")
        changes_after = self.tree_hashes(skill_root / "state" / "changes")
        for path, digest in registry_before.items():
            if path.startswith("locks/"):
                continue
            self.assertEqual(digest, registry_after[path])
        self.assertEqual(changes_before, changes_after)
        change_six = skill_root / "state" / "registry" / "changes" / "change-6.json"
        change_seven = skill_root / "state" / "registry" / "changes" / "change-7.json"
        self.assertTrue(change_six.is_file())
        self.assertTrue(change_seven.is_file())
        self.assertEqual(
            kept["next_window"]["eligible_unevaluated"],
            ["change-6", "change-7"],
        )

    def test_project_skill_git_guidance_is_generated_without_initializing_git(self) -> None:
        project = self.create_git_project("git-guidance")
        initialized = self.init_project(project, self.write_bundle(project, "git-guidance"))
        skill_root = Path(initialized["skill_root"])

        guidance = skill_root / "references" / "git-collaboration.md"
        self.assertTrue(guidance.is_file())
        self.assertIn("Only proceed after the user explicitly asks", guidance.read_text(encoding="utf-8"))
        entry = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/git-collaboration.md", entry)
        self.assertFalse((skill_root / ".git").exists())
        self.assertFalse((skill_root / ".gitignore").exists())
        self.assertFalse((skill_root / "README.md").exists())
        self.assertFalse((skill_root / ".github").exists())

    def test_nested_skill_git_ignores_local_state_and_doctor_repairs_clone_state(self) -> None:
        project = self.create_git_project("nested-skill-git")
        initialized = self.init_project(project, self.write_bundle(project, "nested-skill-git"))
        skill_root = Path(initialized["skill_root"])
        self.commit_routes(project)
        self.initialize_skill_git_repository(skill_root)

        self.assertEqual(
            self.runtime_core.normalize_path(Path(self.git(skill_root, "rev-parse", "--show-toplevel"))),
            self.runtime_core.normalize_path(skill_root),
        )
        self.assertEqual(self.git(project, "status", "--porcelain"), "")
        manifest_path = skill_root / "state" / "manifest.json"
        manifest_before = manifest_path.read_bytes()
        for child in list((skill_root / "state").iterdir()):
            if child == manifest_path:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

        uninitialized = self.cli(project, "project", "doctor", expected=(1,))
        self.assertFalse(uninitialized["local_state"]["initialized"])
        self.assertIn("local_state_uninitialized", {item["type"] for item in uninitialized["findings"]})
        repaired = self.cli(project, "project", "doctor", "--repair-links")
        self.assertTrue(repaired["healthy"])
        self.assertTrue(repaired["local_state"]["initialized"])
        self.assertTrue(repaired["local_state"]["created"])
        self.assertEqual(manifest_before, manifest_path.read_bytes())
        self.assertTrue(repaired["git_sharing"]["enabled"])
        self.assertTrue(repaired["git_sharing"]["boundary_healthy"])

        common = Path(self.git(project, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = project / common
        exclude = common / "info" / "exclude"
        exclude.write_text(
            "\n".join(
                line for line in exclude.read_text(encoding="utf-8").splitlines()
                if skill_root.name not in line
            ) + "\n",
            encoding="utf-8",
        )
        (project / ".gitignore").write_text(
            f"/.agents/skills/{skill_root.name}\n/.claude/skills/{skill_root.name}\n",
            encoding="utf-8",
        )
        missing_exclude = self.cli(project, "project", "doctor", expected=(1,))
        self.assertIn(
            "outer_project_skill_not_ignored",
            {item["type"] for item in missing_exclude["findings"]},
        )
        repaired = self.cli(project, "project", "doctor", "--repair-links")
        self.assertTrue(repaired["git_sharing"]["boundary_healthy"])

        self.cli(project, "change", "new", "local-only", "--scope", "local ignored state")
        self.assertEqual(self.git(skill_root, "status", "--porcelain"), "")
        self.git(skill_root, "add", "-f", "state/changes/INDEX.json")
        boundary = self.cli(project, "project", "doctor", expected=(1,))
        self.assertIn("tracked_local_skill_state", {item["type"] for item in boundary["findings"]})

    def test_business_and_project_skill_repositories_clone_independently(self) -> None:
        project = self.create_git_project("independent-clone-source")
        initialized = self.init_project(project, self.write_bundle(project, "independent-clone"))
        skill_root = Path(initialized["skill_root"])
        skill_name = skill_root.name
        self.commit_routes(project)
        self.initialize_skill_git_repository(skill_root)

        cloned_project = self.root / "independent-clone-target"
        self.run_process(["git", "clone", str(project), str(cloned_project)])
        clone_parent = cloned_project / ".agents" / "skills"
        clone_parent.mkdir(parents=True)
        cloned_skill = clone_parent / skill_name
        self.run_process(["git", "clone", str(skill_root), str(cloned_skill)])

        self.assertNotEqual(cloned_project.resolve(), project.resolve())
        attached = self.run_connector(cloned_project)
        self.assertTrue(attached["ok"])
        repaired = self.cli(cloned_project, "project", "doctor", "--repair-links")
        self.assertTrue(repaired["healthy"])
        knowledge = self.cli(cloned_project, "knowledge", "check")
        self.assertTrue(knowledge["healthy"])
        self.cli(cloned_project, "change", "new", "clone-local", "--scope", "local clone state")
        self.assertEqual(self.git(cloned_project, "status", "--porcelain"), "")
        self.assertEqual(self.git(cloned_skill, "status", "--porcelain"), "")

    def test_skill_repository_sidecars_survive_migrate_and_do_not_affect_fingerprint(self) -> None:
        project = self.create_git_project("skill-sidecars")
        bundle = self.write_bundle(project, "skill-sidecars")
        initialized = self.init_project(project, bundle)
        skill_root = Path(initialized["skill_root"])
        self.commit_routes(project)
        head = self.initialize_skill_git_repository(skill_root)
        self.git(skill_root, "remote", "add", "origin", "https://example.invalid/project-skill.git")
        (skill_root / "LICENSE.custom").write_text("private fixture license\n", encoding="utf-8")
        self.git(skill_root, "add", "LICENSE.custom")
        self.git(skill_root, "commit", "-m", "add license")
        head = self.git(skill_root, "rev-parse", "HEAD")
        fingerprint = self.runtime_evolution.harness_content_fingerprint(skill_root)
        repository_files = {
            relative: (skill_root / relative).read_bytes()
            for relative in (".gitignore", "README.md", ".github/pull_request_template.md", "LICENSE.custom")
        }

        git_dir = Path(self.git(skill_root, "rev-parse", "--git-dir"))
        if not git_dir.is_absolute():
            git_dir = skill_root / git_dir
        index_lock = git_dir / "index.lock"
        index_lock.write_text("busy\n", encoding="utf-8")
        blocked = self.cli(
            project, "project", "migrate", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("skill_git_index_locked", blocked["error"])
        index_lock.unlink()

        self.cli(project, "project", "migrate", "--analysis-bundle", str(bundle))

        self.assertEqual(self.git(skill_root, "rev-parse", "HEAD"), head)
        self.assertEqual(
            self.git(skill_root, "config", "--get", "remote.origin.url"),
            "https://example.invalid/project-skill.git",
        )
        self.run_process(["git", "-C", str(skill_root), "fsck", "--no-dangling"])
        for relative, content in repository_files.items():
            self.assertEqual((skill_root / relative).read_bytes(), content)
        self.assertNotEqual(fingerprint, self.runtime_evolution.harness_content_fingerprint(skill_root))
        after_migrate = self.runtime_evolution.harness_content_fingerprint(skill_root)
        (skill_root / "README.md").write_text("repository-side change\n", encoding="utf-8")
        self.assertEqual(after_migrate, self.runtime_evolution.harness_content_fingerprint(skill_root))

    def test_skill_repository_sidecars_roll_back_after_partial_preservation_failure(self) -> None:
        project = self.create_git_project("skill-sidecar-rollback")
        bundle = self.write_bundle(project, "skill-sidecar-rollback")
        initialized = self.init_project(project, bundle)
        skill_root = Path(initialized["skill_root"])
        self.commit_routes(project)
        head = self.initialize_skill_git_repository(skill_root)
        manifest_before = (skill_root / "state" / "manifest.json").read_bytes()
        readme_before = (skill_root / "README.md").read_bytes()
        original_move = self.runtime_transactions.transaction_move
        failed_once = False

        def fail_after_git_sidecar(source: Path, target: Path) -> None:
            nonlocal failed_once
            if not failed_once and target.name == ".gitignore":
                failed_once = True
                raise OSError("injected repository-sidecar failure")
            original_move(source, target)

        arguments = ("project", "migrate", "--analysis-bundle", str(bundle))
        with mock.patch.object(self.runtime_transactions, "transaction_move", side_effect=fail_after_git_sidecar):
            with self.assertRaises(self.cli_module.HarnessError):
                self.dispatch(project, *arguments)

        self.assertTrue(failed_once)
        self.assertEqual(self.git(skill_root, "rev-parse", "HEAD"), head)
        self.assertEqual((skill_root / "state" / "manifest.json").read_bytes(), manifest_before)
        self.assertEqual((skill_root / "README.md").read_bytes(), readme_before)
        self.assertTrue((skill_root / ".gitignore").is_file())
        self.assertFalse(self.runtime_transactions.content_transaction_store(skill_root).exists())

    def test_init_and_migrate_never_create_repository_harness(self) -> None:
        project = self.create_git_project("single-output-project")
        initialized = self.init_project(project, self.write_bundle(project, "single-output"))
        self.assertEqual(initialized["status"], "initialized")
        self.commit_routes(project)
        self.cli(project, "change", "new", "preserved-change", "--scope", "preserve shared evidence")
        skill_root = Path(initialized["skill_root"])
        obsolete_package = skill_root / "scripts" / "harness_runtime" / "obsolete.py"
        obsolete_package.write_text("obsolete = True\n", encoding="utf-8")
        obsolete_runtime = skill_root / "scripts" / "obsolete_runtime.py"
        obsolete_runtime.write_text("obsolete = True\n", encoding="utf-8")
        helper = skill_root / "scripts" / "helpers" / "project_helper.py"
        helper.parent.mkdir(exist_ok=True)
        helper.write_text("print('helper')\n", encoding="utf-8")
        manifest_path = skill_root / "state" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["launchers"].extend(["obsolete_runtime.py", "harness_runtime/obsolete.py"])
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        changes_before = self.tree_hashes(skill_root / "state" / "changes")
        forbidden = (
            "docs/ECL.md", "docs/STATUS.md", "harness/config", "harness/changes",
            "harness/evolution",
        )
        for relative in forbidden:
            self.assertFalse((project / relative).exists(), relative)
        migrated = self.cli(
            project,
            "project",
            "migrate",
            "--analysis-bundle",
            str(self.write_bundle(project, "single-output-updated")),
        )
        self.assertEqual(migrated["status"], "migration_applied")
        for relative in forbidden:
            self.assertFalse((project / relative).exists(), relative)
        self.assertEqual(changes_before, self.tree_hashes(skill_root / "state" / "changes"))
        self.assertTrue((skill_root / "state" / "changes" / "INDEX.json").is_file())
        self.assertFalse(obsolete_package.exists())
        self.assertFalse(obsolete_runtime.exists())
        self.assertTrue(helper.is_file())
        source_runtime = ROOT / "scripts" / "harness_runtime"
        installed_runtime = skill_root / "scripts" / "harness_runtime"
        self.assertEqual(
            {path.name: path.read_bytes() for path in source_runtime.glob("*.py")},
            {path.name: path.read_bytes() for path in installed_runtime.glob("*.py")},
        )

    def test_multilanguage_profiles_preserve_evidence_backed_commands(self) -> None:
        fixtures = [
            ("go", "go.mod", "module example.test/fixture\ngo 1.22\n", "Go", "go test ./..."),
            ("java", "pom.xml", "<project></project>\n", "Java", "mvn test"),
            ("python", "pyproject.toml", "[project]\nname='fixture'\nversion='0.1'\n", "Python", "python -m pytest"),
            ("rust", "Cargo.toml", "[package]\nname='fixture'\nversion='0.1.0'\n", "Rust", "cargo test"),
            ("typescript", "package.json", '{"scripts":{"test":"node --test"}}\n', "TypeScript", "npm test"),
        ]
        for slug, manifest, manifest_text, language, command in fixtures:
            with self.subTest(language=language):
                project = self.root / f"lang-{slug}"
                (project / "src" / "jobs").mkdir(parents=True)
                (project / "src" / "runtime").mkdir(parents=True)
                (project / "tests").mkdir()
                (project / "README.md").write_text(f"# {language} fixture\n\nRuns jobs.\n", encoding="utf-8")
                (project / manifest).write_text(manifest_text, encoding="utf-8")
                (project / ".env.example").write_text("APP_MODE=development\n", encoding="utf-8")
                (project / "src" / "jobs" / "service.py").write_text("def submit_job(x): return x\n", encoding="utf-8")
                (project / "src" / "runtime" / "worker.py").write_text("def run(x): return x\n", encoding="utf-8")
                (project / "tests" / "test_jobs.py").write_text("def test_job(): assert True\n", encoding="utf-8")
                bundle = self.write_bundle(
                    project,
                    f"lang-{slug}",
                    command=command,
                    command_evidence=manifest,
                    language=language,
                )
                initialized = self.init_project(project, bundle)
                commands = (
                    Path(initialized["skill_root"])
                    / "references"
                    / "project_wiki"
                    / "systems"
                    / "commands.md"
                ).read_text(encoding="utf-8")
                self.assertIn(command, commands)
                self.assertIn(manifest, commands)
                self.assertEqual(initialized["mode"], "single_lane")

    def test_external_ids_cannot_traverse_registry_and_records_are_id_bound(self) -> None:
        project = self.create_git_project("id-safety")
        initialized = self.init_project(project, self.write_bundle(project, "id-safety"))
        self.commit_routes(project)
        self.cli(project, "change", "new", "safe-change", "--scope", "safe")
        skill_root = Path(initialized["skill_root"])
        baseline = skill_root / "state" / "registry" / "baseline.json"
        before = baseline.read_bytes()
        unsafe_calls = [
            ("change", "preflight", "--change-id", "../../baseline"),
            ("change", "publish", "..\\baseline"),
            ("change", "close", "../baseline", "--status", "blocked"),
            ("change", "status", "--change-id", "../../baseline"),
            ("integrate", "start", "../landing", "safe-change"),
            ("integrate", "status", "--integration-id", "../../landing"),
            ("integrate", "abort", "..\\landing"),
        ]
        for arguments in unsafe_calls:
            with self.subTest(arguments=arguments):
                result = self.cli(project, *arguments, expected=(2,))
                self.assertFalse(result["ok"])
        self.assertEqual(before, baseline.read_bytes())

        record_path = skill_root / "state" / "registry" / "changes" / "safe-change.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["change_id"] = "different-change"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        mismatch = self.cli(project, "change", "status", expected=(2,))
        self.assertIn("does not match", mismatch["error"])

    def test_generated_helpers_reject_path_traversal_and_linked_content(self) -> None:
        checker = ROOT / "scripts" / "check_stage_artifacts.py"
        for arguments in (
            ("--skill-root", str(ROOT), "--stage", "../../outside"),
            (
                "--skill-root", str(ROOT), "--stage", "plan",
                "--change-id", "../outside",
            ),
        ):
            with self.subTest(arguments=arguments):
                result = self.run_process([sys.executable, str(checker), *arguments], expected=(2,))
                payload = json.loads(result.stdout)
                self.assertFalse(payload["ok"])
                self.assertIn("traversal", payload["error"])

        rule_source = self.root / "unsafe-rules.yaml"
        rule_source.write_text(json.dumps({
            "schema_version": "1.0",
            "rules": [{
                "id": "HR-99", "severity": "critical", "stages": ["../../outside"],
                "title": "Unsafe", "rule": "Must not escape.", "on_violation": "Stop.",
            }],
        }), encoding="utf-8")
        output = self.root / "rule-output"
        generator = ROOT / "scripts" / "generate_rule_docs.py"
        rejected = self.run_process(
            [sys.executable, str(generator), "--source", str(rule_source), "--output-root", str(output)],
            expected=(2,),
        )
        self.assertFalse(json.loads(rejected.stdout)["ok"])
        self.assertFalse((self.root / "outside.md").exists())

        source = self.root / "linked-skill-source"
        (source / "references").mkdir(parents=True)
        external = self.root / "external-content"
        external.mkdir()
        link = source / "references" / "linked"
        self.runtime_links.create_directory_link(link, external)
        with self.assertRaisesRegex(self.cli_module.HarnessError, "must not contain links"):
            self.runtime_evolution.copy_non_state_skill(source, self.root / "linked-skill-copy")

        transaction_skill = self.root / "transaction-skill"
        candidate = transaction_skill / "state" / "candidate"
        (candidate / "references").mkdir(parents=True)
        (candidate / "SKILL.md").write_text("# Candidate\n", encoding="utf-8")
        self.runtime_links.create_directory_link(candidate / "references" / "linked", external)
        with self.assertRaisesRegex(self.cli_module.HarnessError, "must not contain links"):
            self.runtime_transactions.apply_content_transaction(
                transaction_skill,
                candidate,
                "evolution",
                "linked-candidate",
            )

    def test_rule_views_are_disjoint_and_cover_every_rule(self) -> None:
        source = self.root / "rules.yaml"
        source.write_text(json.dumps({
            "schema_version": "1.0",
            "rules": [
                {
                    "id": "HR-01", "severity": "critical", "stages": ["all"],
                    "title": "Global", "rule": "Load current facts.", "on_violation": "Reload.",
                },
                {
                    "id": "HR-02", "severity": "critical", "stages": ["plan"],
                    "title": "Plan Gate", "rule": "Approve the plan.", "on_violation": "Stop.",
                },
                {
                    "id": "HR-03", "severity": "standard", "stages": ["plan"],
                    "title": "Plan Detail", "rule": "Record detail.", "on_violation": "Revise.",
                },
                {
                    "id": "HR-04", "severity": "standard", "stages": ["all"],
                    "title": "Shared Detail", "rule": "Record evidence.", "on_violation": "Revise.",
                },
                {
                    "id": "HR-05", "severity": "standard", "stages": ["verify"],
                    "title": "Verify Detail", "rule": "Record results.", "on_violation": "Retry.",
                },
            ],
        }), encoding="utf-8")
        output = self.root / "rule-views"
        result = self.run_process([
            sys.executable,
            str(ROOT / "scripts" / "generate_rule_docs.py"),
            "--source", str(source),
            "--output-root", str(output),
        ])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["critical"], 2)
        self.assertEqual(payload["stage_rules"], 3)

        critical = set(re.findall(r"^## (HR-\d+):", (output / "critical.md").read_text(encoding="utf-8"), re.MULTILINE))
        stage_sets = {
            path.stem: set(re.findall(r"^## (HR-\d+):", path.read_text(encoding="utf-8"), re.MULTILINE))
            for path in (output / "by-stage").glob("*.md")
        }
        self.assertEqual(critical, {"HR-01", "HR-02"})
        self.assertEqual(stage_sets["plan"], {"HR-03", "HR-04"})
        self.assertEqual(stage_sets["verify"], {"HR-04", "HR-05"})
        self.assertTrue(all(critical.isdisjoint(stage_rules) for stage_rules in stage_sets.values()))
        self.assertEqual(critical | set().union(*stage_sets.values()), {f"HR-0{index}" for index in range(1, 6)})

    def test_audit_rubric_is_the_single_machine_formula_and_is_copied(self) -> None:
        rubric_path = ROOT / "references" / "audit-rubric.json"
        rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        self.assertEqual(sum(rubric["dimensions"].values()), 100)
        contracts_source = (ROOT / "scripts" / "harness_runtime" / "contracts.py").read_text(encoding="utf-8")
        self.assertNotIn("AUDIT_WEIGHTS", contracts_source)
        self.assertIn("load_audit_rubric", contracts_source)

        project = self.create_git_project("rubric-copy")
        initialized = self.init_project(project, self.write_bundle(project, "rubric-copy"))
        generated = Path(initialized["skill_root"]) / "references" / "audit-rubric.json"
        self.assertEqual(generated.read_bytes(), rubric_path.read_bytes())

    def test_evolution_rejects_a_candidate_that_rewrites_its_audit_gate(self) -> None:
        project, skill_root, _ = self.prepare_evolution("rubric-tamper")
        candidate = skill_root / "state" / "evolution" / "staging" / "accepted-knowledge"
        rubric_path = candidate / "references" / "audit-rubric.json"
        rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        rubric["evolution_gate"]["minimum_score"] = 0
        rubric_path.write_text(json.dumps(rubric, indent=2) + "\n", encoding="utf-8")
        metadata_path = candidate / "state" / "candidate.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        content_fingerprint = self.runtime_evolution.harness_content_fingerprint(candidate)
        metadata["candidate_content_fingerprint"] = content_fingerprint
        metadata["candidate_fingerprint"] = self.runtime_evolution.candidate_binding_fingerprint(
            content_fingerprint, metadata["source_snapshot"]["digest"],
        )
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        judge = self.write_evolution_judge(skill_root)
        rejected = self.cli(
            project,
            "evolve", "mark-complete",
            "--proposal-id", "accepted-knowledge",
            "--owner", "independent-judge",
            "--candidate-id", "accepted-knowledge",
            "--judge-report", str(judge),
            "--status", "keep",
            expected=(2,),
        )
        self.assertIn("cannot modify or replace", rejected["error"])

    def test_existing_routes_are_managed_idempotently_and_connector_collisions_fail(self) -> None:
        project = self.create_git_project("existing-routes")
        (project / "AGENTS.md").write_text("# Existing Agent Rules\n\nKeep this project-specific rule.\n", encoding="utf-8")
        (project / "CLAUDE.md").write_text("# Existing Claude Rules\n\nKeep this Claude rule.\n", encoding="utf-8")
        self.git(project, "add", "AGENTS.md", "CLAUDE.md")
        self.git(project, "commit", "-m", "add existing routes")
        self.init_project(project, self.write_bundle(project, "existing-routes"))
        first = {
            name: (project / name).read_text(encoding="utf-8")
            for name in ("AGENTS.md", "CLAUDE.md")
        }
        for name, content in first.items():
            self.assertIn("Existing", content)
            self.assertEqual(content.count("<!-- ECL-HARNESS:BEGIN -->"), 1)
            self.assertEqual(content.count("<!-- ECL-HARNESS:END -->"), 1)
        self.cli(project, "project", "doctor", "--repair-links", expected=(0, 1))
        self.cli(project, "project", "doctor", "--repair-links", expected=(0, 1))
        self.assertEqual(
            first,
            {name: (project / name).read_text(encoding="utf-8") for name in first},
        )

        collision = self.create_git_project("connector-collision")
        (collision / "scripts").mkdir()
        for name in (
            "harness-skill-link.ps1",
            "harness-skill-link.mjs",
            "harness-skill-link.py",
        ):
            (collision / "scripts" / name).write_text("unmanaged connector\n", encoding="utf-8")
        original_agents = "# Collision fixture\n"
        (collision / "AGENTS.md").write_text(original_agents, encoding="utf-8")
        failed = self.cli(
            collision,
            "project",
            "init",
            "--analysis-bundle",
            str(self.write_bundle(collision, "connector-collision")),
            expected=(2,),
        )
        self.assertIn("collision", failed["error"].lower())
        self.assertEqual(original_agents, (collision / "AGENTS.md").read_text(encoding="utf-8"))
        skill_dirs = list((collision / ".agents" / "skills").glob("*-harness")) if (collision / ".agents" / "skills").exists() else []
        self.assertEqual(skill_dirs, [])

    def test_partial_runtime_link_failure_removes_only_links_created_by_init(self) -> None:
        project = self.create_git_project("partial-links")
        extra = self.root / "partial-links-extra"
        self.git(project, "worktree", "add", "-b", "partial-links-extra", str(extra), "HEAD")
        bundle = self.write_bundle(project, "partial-links")
        original_create = self.runtime_links.create_directory_link
        created: list[Path] = []

        def fail_after_one_created_link(link: Path, target: Path) -> bool:
            if self.runtime_core.normalize_path(link) != self.runtime_core.normalize_path(target) and created:
                raise self.cli_module.HarnessError("injected runtime link failure")
            result = original_create(link, target)
            if result:
                created.append(link)
            return result

        with mock.patch.object(
            self.runtime_links,
            "create_directory_link",
            side_effect=fail_after_one_created_link,
        ):
            with self.assertRaises(self.cli_module.HarnessError):
                self.dispatch(
                    project,
                    "project",
                    "init",
                    "--analysis-bundle",
                    str(bundle),
                )
        self.assertTrue(created)
        self.assertTrue(all(not path.exists() for path in created))
        self.assertEqual(list((project / ".agents" / "skills").glob("*-harness")), [])

    def test_feature_branch_init_prefers_main_as_canonical(self) -> None:
        project = self.create_git_project("canonical-selection")
        main_commit = self.git(project, "rev-parse", "main")
        self.git(project, "switch", "-c", "feature/init-harness")
        initialized = self.init_project(project, self.write_bundle(project, "canonical-selection"))
        baseline = json.loads(
            (Path(initialized["skill_root"]) / "state" / "registry" / "baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(baseline["canonical_branch"], "main")
        self.assertEqual(baseline["canonical_commit"], main_commit)

    def test_baseline_relation_distinguishes_advancement_from_drift(self) -> None:
        project = self.create_git_project("baseline-relations")
        initial = self.git(project, "rev-parse", "HEAD")
        initialized = self.init_project(project, self.write_bundle(project, "baseline-relations"))
        advanced = self.commit_routes(project)
        doctor = self.cli(project, "project", "doctor")
        self.assertTrue(doctor["healthy"])
        self.assertEqual(doctor["baseline"]["relation"], "canonical_advanced")
        self.assertEqual(
            self.runtime_core.git_baseline_relation(project, initial, advanced),
            "canonical_advanced",
        )
        self.assertEqual(
            self.runtime_core.git_baseline_relation(project, advanced, initial),
            "worktree_behind",
        )
        self.assertEqual(
            self.runtime_core.git_baseline_relation(project, advanced, advanced),
            "equal",
        )
        self.assertEqual(
            self.runtime_core.git_baseline_relation(project, "missing-commit", advanced),
            "unavailable",
        )

        divergent_worktree = self.root / "baseline-divergent"
        self.git(project, "worktree", "add", "-b", "baseline-divergent", str(divergent_worktree), initial)
        (divergent_worktree / "divergent.txt").write_text("divergent\n", encoding="utf-8")
        self.git(divergent_worktree, "add", "divergent.txt")
        self.git(divergent_worktree, "commit", "-m", "create divergent baseline")
        divergent = self.git(divergent_worktree, "rev-parse", "HEAD")
        self.assertEqual(
            self.runtime_core.git_baseline_relation(project, divergent, advanced),
            "diverged",
        )

        baseline_path = Path(initialized["skill_root"]) / "state" / "registry" / "baseline.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline["canonical_commit"] = divergent
        baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        doctor = self.cli(project, "project", "doctor", expected=(1,))
        self.assertFalse(doctor["healthy"])
        self.assertEqual(doctor["baseline"]["relation"], "diverged")
        self.assertIn("canonical_baseline_diverged", {item["type"] for item in doctor["findings"]})

        baseline["canonical_commit"] = "missing-commit"
        baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        doctor = self.cli(project, "project", "doctor", expected=(1,))
        self.assertFalse(doctor["healthy"])
        self.assertEqual(doctor["baseline"]["relation"], "unavailable")
        self.assertIn("canonical_baseline_unavailable", {item["type"] for item in doctor["findings"]})

        non_git = self.root / "baseline-non-git"
        non_git.mkdir()
        self.init_project(non_git)
        self.assertEqual(
            self.runtime_core.git_baseline_relation(non_git, None, None),
            "not_applicable",
        )
        self.assertEqual(
            self.cli(non_git, "project", "doctor")["baseline"]["relation"],
            "not_applicable",
        )

    def test_same_change_id_has_one_global_winner_across_lanes(self) -> None:
        project = self.create_git_project("atomic-change")
        initialized = self.init_project(project, self.write_bundle(project, "atomic-change"))
        baseline = self.commit_routes(project)
        lanes = []
        for suffix in ("a", "b"):
            lane = self.root / f"atomic-lane-{suffix}"
            self.git(project, "worktree", "add", "-b", f"atomic-lane-{suffix}", str(lane), baseline)
            self.run_connector(lane)
            lanes.append(lane)
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(CLI),
                    "change",
                    "new",
                    "shared-id",
                    "--scope",
                    suffix,
                    "--project-root",
                    str(lane),
                ],
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for suffix, lane in zip(("lane-a", "lane-b"), lanes)
        ]
        results = [process.communicate(timeout=30) + (process.returncode,) for process in processes]
        self.assertEqual(sum(returncode == 0 for _, _, returncode in results), 1)
        skill_root = Path(initialized["skill_root"])
        records = list((skill_root / "state" / "registry" / "changes").glob("shared-id.json"))
        self.assertEqual(len(records), 1)
        shared_artifact = skill_root / "state" / "changes" / "active" / "shared-id"
        self.assertTrue(shared_artifact.is_dir())
        self.assertFalse(any((lane / "harness" / "changes").exists() for lane in lanes))

    def test_git_change_close_matches_mature_non_git_lifecycle(self) -> None:
        project = self.create_git_project("dirty-change")
        initialized = self.init_project(project, self.write_bundle(project, "dirty-change"))
        created = self.cli(project, "change", "new", "dirty", "--scope", "work with local edits")
        self.assertEqual(created["status"], "created")
        self.complete_change_documents(project, "dirty")
        (project / "unrelated.tmp").write_text("uncommitted work\n", encoding="utf-8")
        closed = self.cli(
            project, "change", "close", "dirty", "--status", "completed",
            "--validation", "fixture passed", "--validation-passed",
        )
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(closed["integration_boundary"], "not_recorded")
        record = json.loads((
            Path(initialized["skill_root"]) / "state" / "registry" / "changes" / "dirty.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(record["integration_status"], "not_requested")
        self.assertIsNone(record["completion_commit"])

        non_git = self.root / "terminal-change"
        non_git.mkdir()
        self.init_project(non_git)
        self.cli(non_git, "change", "new", "terminal", "--scope", "stop")
        self.cli(non_git, "change", "close", "terminal", "--status", "blocked")
        reopened = self.cli(
            non_git,
            "change",
            "publish",
            "terminal",
            "--status",
            "active",
            expected=(2,),
        )
        self.assertIn("terminal", reopened["error"].lower())

    def test_change_evidence_accepts_multiline_tasks_and_project_headings(self) -> None:
        project = self.root / "flexible-evidence"
        project.mkdir()
        initialized = self.init_project(project)
        skill_root = Path(initialized["skill_root"])
        self.cli(project, "change", "new", "flexible", "--scope", "validate flexible evidence")
        self.complete_change_documents(project, "flexible")
        evidence = skill_root / "state" / "changes" / "active" / "flexible"
        (evidence / "tasks.md").write_text(
            "# Tasks: flexible\n\n"
            "- [x] T001 [AC-001] Implement fixture behavior.\n"
            "  - owner: fixture team\n"
            "  - path: src/fixture.py\n"
            "  - validation: targeted fixture check\n",
            encoding="utf-8",
        )
        (evidence / "reviews" / "review.md").write_text(
            "# 复审\n\n## 计划结论\n\n- Approved: yes\n\n"
            "## 验证结果\n\n- 说明：历史示例可以提到 TBD，不表示当前字段未完成。\n",
            encoding="utf-8",
        )
        valid, issues = self.runtime_contracts.validate_change_evidence(evidence)
        self.assertTrue(valid, issues)
        closed = self.cli(
            project, "change", "close", "flexible", "--status", "completed",
            "--validation", "targeted fixture check passed", "--validation-passed",
        )
        self.assertEqual(closed["status"], "closed")

        self.cli(project, "change", "new", "invalid-fields", "--scope", "reject placeholders")
        self.complete_change_documents(project, "invalid-fields")
        invalid = skill_root / "state" / "changes" / "active" / "invalid-fields"
        (invalid / "tasks.md").write_text(
            "# Tasks: invalid-fields\n\n"
            "- [x] T001 [AC-001] Implement fixture behavior.\n"
            "  - owner: TBD\n"
            "  - path: src/fixture.py\n"
            "  - validation: command TBD\n",
            encoding="utf-8",
        )
        valid, issues = self.runtime_contracts.validate_change_evidence(invalid)
        self.assertFalse(valid)
        self.assertIn("task T001 has no valid owner/path mapping", issues)
        self.assertIn("task T001 has no valid validation mapping", issues)
        spec = invalid / "spec.md"
        spec.write_text(
            spec.read_text(encoding="utf-8").replace(
                "AC-001: fixture validation passes.", "AC-001: TBD",
            ),
            encoding="utf-8",
        )
        valid, issues = self.runtime_contracts.validate_change_evidence(invalid)
        self.assertFalse(valid)
        self.assertIn("acceptance criterion AC-001 has no completed value", issues)
        plan = invalid / "plan.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- Status: approved", "Historical text mentions Status: approved",
            ),
            encoding="utf-8",
        )
        review = invalid / "reviews" / "review.md"
        review.write_text(
            review.read_text(encoding="utf-8").replace(
                "- Approved: yes", "An example mentions Approved: yes",
            ),
            encoding="utf-8",
        )
        valid, issues = self.runtime_contracts.validate_change_evidence(invalid)
        self.assertFalse(valid)
        self.assertIn("plan.md does not record an approved plan review", issues)
        self.assertIn("reviews/review.md does not approve the plan", issues)
        spec.write_text(
            spec.read_text(encoding="utf-8") + "\n[NEEDS CLARIFICATION: ownership]\n",
            encoding="utf-8",
        )
        valid, issues = self.runtime_contracts.validate_change_evidence(invalid)
        self.assertFalse(valid)
        self.assertIn("spec.md contains unresolved high-impact clarification", issues)

    def test_dirty_git_lane_can_resume_a_parked_change(self) -> None:
        project = self.create_git_project("dirty-resume")
        self.init_project(project, self.write_bundle(project, "dirty-resume"))
        self.commit_routes(project)
        self.cli(project, "change", "new", "parked", "--scope", "resume safely")
        self.cli(project, "change", "park", "parked")
        dirty = project / "unrelated.tmp"
        dirty.write_text("unrelated work\n", encoding="utf-8")

        resumed = self.cli(project, "change", "resume", "parked")
        self.assertEqual(resumed["status"], "resumed")
        self.assertTrue(dirty.is_file())

    def test_optional_close_commit_is_linear_and_does_not_require_clean_head(self) -> None:
        project = self.create_git_project("optional-close-boundary")
        self.init_project(project, self.write_bundle(project, "optional-close-boundary"))
        baseline = self.commit_routes(project)
        self.cli(project, "change", "new", "optional-boundary", "--scope", "record optional boundary")
        self.complete_change_documents(project, "optional-boundary")
        empty = self.cli(
            project, "change", "close", "optional-boundary", "--status", "completed",
            "--completion-commit", baseline, "--validation", "fixture passed",
            "--validation-passed", expected=(2,),
        )
        self.assertIn("empty Change range", empty["error"])

        (project / "optional-boundary.txt").write_text("boundary\n", encoding="utf-8")
        self.git(project, "add", "optional-boundary.txt")
        self.git(project, "commit", "-m", "add optional boundary")
        completion = self.git(project, "rev-parse", "HEAD")
        (project / "unrelated.tmp").write_text("leave dirty\n", encoding="utf-8")
        closed = self.cli(
            project, "change", "close", "optional-boundary", "--status", "completed",
            "--completion-commit", completion, "--validation", "fixture passed",
            "--validation-passed",
        )
        self.assertEqual(closed["integration_boundary"], "recorded")
        self.assertEqual(closed["change"]["completion_commit"], completion)
        self.assertTrue((project / "unrelated.tmp").is_file())

    def test_change_lifecycle_and_index_live_only_in_project_skill(self) -> None:
        project = self.root / "skill-owned-changes"
        project.mkdir()
        initialized = self.init_project(project)
        skill_root = Path(initialized["skill_root"])
        created = self.cli(project, "change", "new", "lifecycle", "--scope", "Preserve mature flow")
        self.complete_change_documents(project, "lifecycle")
        self.assertTrue(Path(created["skill_path"]).is_relative_to(skill_root / "state" / "changes"))
        self.assertFalse((project / "harness").exists())

        parked = self.cli(project, "change", "park", "lifecycle")
        self.assertEqual(parked["status"], "parked")
        self.assertTrue((skill_root / "state" / "changes" / "parking" / "lifecycle").is_dir())
        resumed = self.cli(project, "change", "resume", "lifecycle")
        self.assertEqual(resumed["status"], "resumed")
        self.assertTrue((skill_root / "state" / "changes" / "active" / "lifecycle").is_dir())

        search = self.cli(project, "change", "search", "--query", "mature flow")
        self.assertEqual([item["change_id"] for item in search["changes"]], ["lifecycle"])
        summary_context = self.cli(project, "change", "context", "lifecycle")
        self.assertEqual(set(summary_context["documents"]), {"summary.md"})
        full_context = self.cli(project, "change", "context", "lifecycle", "--full")
        self.assertEqual(set(full_context["documents"]), set(self.runtime_core.REQUIRED_CHANGE_FILES))

        closed = self.cli(
            project,
            "change",
            "close",
            "lifecycle",
            "--status",
            "completed",
            "--validation",
            "fixture passed",
            "--validation-passed",
        )
        self.assertEqual(closed["status"], "closed")
        self.assertTrue((skill_root / "state" / "changes" / "archive" / "lifecycle").is_dir())
        reindexed = self.cli(project, "change", "reindex")
        self.assertEqual(reindexed["count"], 1)
        entry = reindexed["index"]["changes"][0]
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(entry["evidence_state"], "archive")

    def test_change_lifecycle_refuses_linked_evidence_without_moving_target(self) -> None:
        project = self.root / "linked-change-evidence"
        project.mkdir()
        initialized = self.init_project(project)
        skill_root = Path(initialized["skill_root"])
        self.cli(project, "change", "new", "linked-change", "--scope", "Protect evidence")
        active_root = skill_root / "state" / "changes" / "active"
        evidence = active_root / "linked-change"
        self.runtime_core.remove_owned_tree(evidence, active_root, "test Change evidence")
        external = self.root / "external-change-evidence"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        self.runtime_links.create_directory_link(evidence, external)
        try:
            rejected = self.cli(project, "change", "park", "linked-change", expected=(2,))
            self.assertIn("physical", rejected["error"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
            self.assertFalse((skill_root / "state" / "changes" / "parking" / "linked-change").exists())
        finally:
            self.runtime_core.unlink_directory_link_node(evidence)

    def test_empty_evidence_and_failed_artifact_validation_do_not_publish(self) -> None:
        empty_project = self.create_git_project("empty-evidence")
        empty_bundle = self.write_bundle(empty_project, "empty-evidence")
        profile_path = empty_bundle / "project-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["purpose"]["evidence"] = []
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        rejected = self.cli(
            empty_project,
            "project",
            "init",
            "--analysis-bundle",
            str(empty_bundle),
            expected=(2,),
        )
        self.assertIn("non-empty", rejected["error"])
        self.assertFalse((empty_project / ".agents" / "skills").exists())

        false_complete_project = self.create_git_project("false-complete-profile")
        false_complete_bundle = self.write_bundle(false_complete_project, "false-complete-profile")
        false_profile_path = false_complete_bundle / "project-profile.json"
        false_profile = json.loads(false_profile_path.read_text(encoding="utf-8"))
        false_profile["purpose"] = None
        false_profile["evidence"] = []
        for field in (
            "primary_flows", "languages", "frameworks", "package_managers", "source_roots",
            "entrypoints", "modules", "commands", "ci", "bridges", "global_boundaries",
        ):
            false_profile[field] = []
        false_profile_path.write_text(json.dumps(false_profile, indent=2), encoding="utf-8")
        false_complete = self.cli(
            false_complete_project,
            "project",
            "init",
            "--analysis-bundle",
            str(false_complete_bundle),
            expected=(2,),
        )
        self.assertIn("complete project profile requires", false_complete["error"].lower())
        self.assertFalse((false_complete_project / ".agents" / "skills").exists())

        shallow_project = self.create_git_project("shallow-complete-profile")
        shallow_bundle = self.write_bundle(shallow_project, "shallow-complete-profile")
        shallow_profile_path = shallow_bundle / "project-profile.json"
        shallow_profile = json.loads(shallow_profile_path.read_text(encoding="utf-8"))
        for field in (
            "primary_flows", "frameworks", "package_managers", "source_roots", "entrypoints",
            "modules", "commands", "ci", "bridges", "global_boundaries",
        ):
            shallow_profile[field] = []
        shallow_profile_path.write_text(json.dumps(shallow_profile, indent=2), encoding="utf-8")
        shallow = self.cli(
            shallow_project,
            "project",
            "init",
            "--analysis-bundle",
            str(shallow_bundle),
            expected=(2,),
        )
        self.assertIn("implementation structure", shallow["error"].lower())
        self.assertFalse((shallow_project / ".agents" / "skills").exists())

        untrusted_project = self.create_git_project("untrusted-executable-artifact")
        untrusted_bundle = self.write_bundle(
            untrusted_project,
            "untrusted-executable-artifact",
            artifact=True,
        )
        untrusted = self.cli(
            untrusted_project,
            "project",
            "init",
            "--analysis-bundle",
            str(untrusted_bundle),
            expected=(2,),
        )
        self.assertIn("explicit user authorization", untrusted["error"])
        self.assertEqual(list((untrusted_project / ".agents" / "skills").glob("*")), [])

        unsafe_project = self.create_git_project("unsafe-artifact-target")
        unsafe_bundle = self.write_bundle(unsafe_project, "unsafe-artifact-target", artifact=True)
        unsafe_delta_path = unsafe_bundle / "creation-delta.json"
        unsafe_delta = json.loads(unsafe_delta_path.read_text(encoding="utf-8"))
        unsafe_delta["artifacts"][0]["path"] = "references/rules/red_lines.yaml.evil"
        unsafe_delta_path.write_text(json.dumps(unsafe_delta, indent=2), encoding="utf-8")
        unsafe = self.cli(
            unsafe_project,
            "project",
            "init",
            "--analysis-bundle",
            str(unsafe_bundle),
            expected=(2,),
        )
        self.assertIn("protected or unsupported", unsafe["error"])

        project = self.create_git_project("migration-rollback")
        initialized = self.init_project(
            project,
            self.write_bundle(project, "migration-base", artifact=True),
            allow_executable_artifacts=True,
        )
        skill_root = Path(initialized["skill_root"])
        before = self.tree_hashes(skill_root)
        failing_bundle = self.write_bundle(project, "migration-failing", artifact=True)
        delta_path = failing_bundle / "creation-delta.json"
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        delta["artifacts"][0]["action"] = "merge"
        delta_path.write_text(json.dumps(delta, indent=2), encoding="utf-8")
        (failing_bundle / "artifacts" / "check_project.py").write_text(
            "#!/usr/bin/env python3\nraise SystemExit(7)\n",
            encoding="utf-8",
        )
        failed = self.cli(
            project,
            "project",
            "migrate",
            "--analysis-bundle",
            str(failing_bundle),
            "--allow-executable-artifacts",
            expected=(2,),
        )
        self.assertIn("validation failed", failed["error"].lower())
        self.assertEqual(before, self.tree_hashes(skill_root))

    def test_evolution_rejects_tampered_candidate_without_touching_current_skill(self) -> None:
        project, skill_root, _ = self.prepare_evolution("tampered-evolution")
        retry = self.cli(
            project,
            "evolve",
            "check",
            "--claim-owner",
            "independent-judge",
            "--e1-confirmed",
        )
        self.assertEqual(retry["owner"], "independent-judge")
        before = self.runtime_evolution.harness_content_fingerprint(skill_root)
        candidate = skill_root / "state" / "evolution" / "staging" / "accepted-knowledge"
        judge_report = self.write_evolution_judge(skill_root, score=90)
        with (candidate / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nTampered after judge validation.\n")
        rejected = self.cli(
            project,
            "evolve",
            "mark-complete",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--candidate-id",
            "accepted-knowledge",
            "--judge-report",
            str(judge_report),
            "--status",
            "keep",
            expected=(2,),
        )
        self.assertIn("modified after validation", rejected["error"])
        self.assertEqual(before, self.runtime_evolution.harness_content_fingerprint(skill_root))
        self.assertTrue((skill_root / "state" / "registry" / "locks" / "evolution-owner").exists())
        writer = json.loads(
            (skill_root / "state" / "registry" / "locks" / "shared-writer" / "owner.json").read_text(encoding="utf-8")
        )
        self.assertEqual(writer["kind"], "evolution")

    def test_evolution_publish_failure_rolls_back_content_and_state(self) -> None:
        project, skill_root, _ = self.prepare_evolution("failed-evolution")
        before_content = self.runtime_evolution.harness_content_fingerprint(skill_root)
        state_path = skill_root / "state" / "evolution" / "state.json"
        before_state = state_path.read_bytes()
        original_move = self.runtime_transactions.transaction_move
        failed_once = False
        judge_report = self.write_evolution_judge(skill_root)

        def fail_during_state_preservation(source: Path, target: Path) -> None:
            nonlocal failed_once
            if not failed_once and target.name == "state":
                failed_once = True
                raise OSError("injected state-preservation failure")
            original_move(source, target)

        arguments = (
            "evolve",
            "mark-complete",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--candidate-id",
            "accepted-knowledge",
            "--judge-report",
            str(judge_report),
            "--status",
            "keep",
        )
        with mock.patch.object(self.runtime_transactions, "transaction_move", side_effect=fail_during_state_preservation):
            with self.assertRaises(self.cli_module.HarnessError):
                self.dispatch(project, *arguments)
        self.assertTrue(failed_once)
        self.assertEqual(before_content, self.runtime_evolution.harness_content_fingerprint(skill_root))
        self.assertEqual(before_state, state_path.read_bytes())
        self.assertFalse(self.runtime_transactions.content_transaction_store(skill_root).exists())
        self.assertTrue((skill_root / "state" / "registry" / "locks" / "evolution-owner").exists())

        with mock.patch.object(
            self.runtime_evolution,
            "atomic_append_tsv",
            side_effect=self.cli_module.HarnessError("injected terminal-state failure"),
        ):
            with self.assertRaises(self.cli_module.HarnessError):
                self.dispatch(project, *arguments)
        self.assertEqual(before_content, self.runtime_evolution.harness_content_fingerprint(skill_root))
        self.assertEqual(before_state, state_path.read_bytes())
        self.assertFalse(self.runtime_transactions.content_transaction_store(skill_root).exists())

        completed = self.cli(project, *arguments)
        self.assertEqual(completed["status"], "keep")

    def test_unavailable_evolution_judge_records_noop_without_modification(self) -> None:
        project, skill_root, _ = self.prepare_evolution("noop-evolution")
        before = self.runtime_evolution.harness_content_fingerprint(skill_root)
        result = self.cli(
            project,
            "evolve",
            "mark-complete",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--status",
            "noop",
            "--judge-unavailable",
            "--note",
            "independent judge unavailable",
        )
        self.assertEqual(result["status"], "noop")
        self.assertEqual(before, self.runtime_evolution.harness_content_fingerprint(skill_root))
        self.assertFalse((skill_root / "state" / "registry" / "locks" / "evolution-owner").exists())
        state = json.loads((skill_root / "state" / "evolution" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["evaluated_change_ids"], [f"change-{index}" for index in range(1, 6)])

    def test_evolution_completion_serializes_change_close_without_losing_next_window(self) -> None:
        project, skill_root, _ = self.prepare_evolution("concurrent-evolution")
        self.cli(project, "change", "new", "change-6", "--scope", "queued during publication")
        self.complete_change_documents(project, "change-6")
        entered = threading.Event()
        release = threading.Event()
        original_move = self.runtime_transactions.transaction_move
        judge_report = self.write_evolution_judge(skill_root)

        def pause_before_publication(source: Path, target: Path) -> None:
            if target.name == "previous" and not entered.is_set():
                entered.set()
                self.assertTrue(release.wait(timeout=20))
            original_move(source, target)

        mark_arguments = (
            "evolve",
            "mark-complete",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--candidate-id",
            "accepted-knowledge",
            "--judge-report",
            str(judge_report),
            "--status",
            "keep",
        )
        thread_result: dict[str, object] = {}

        def run_mark() -> None:
            try:
                thread_result["value"] = self.dispatch(project, *mark_arguments)
            except Exception as exc:
                thread_result["error"] = exc

        with mock.patch.object(self.runtime_transactions, "transaction_move", side_effect=pause_before_publication):
            thread = threading.Thread(target=run_mark)
            thread.start()
            self.assertTrue(entered.wait(timeout=20))
            close = subprocess.Popen(
                [
                    sys.executable,
                    str(CLI),
                    "change",
                    "close",
                    "change-6",
                    "--status",
                    "completed",
                    "--validation",
                    "concurrent fixture pass",
                    "--validation-passed",
                    "--project-root",
                    str(project),
                ],
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.25)
            self.assertIsNone(close.poll())
            release.set()
            thread.join(timeout=30)
            stdout, stderr = close.communicate(timeout=30)
        self.assertNotIn("error", thread_result)
        self.assertEqual(close.returncode, 0, stderr or stdout)
        state = json.loads((skill_root / "state" / "evolution" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["evaluated_change_ids"], [f"change-{index}" for index in range(1, 6)])
        status = self.cli(project, "evolve", "check")
        self.assertEqual(status["eligible_unevaluated"], ["change-6"])
        self.assertFalse(status["pending"])

    def test_evolution_terminal_crash_retry_releases_writer(self) -> None:
        project, skill_root, _ = self.prepare_evolution("terminal-evolution")
        arguments = (
            "evolve",
            "mark-complete",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--status",
            "noop",
            "--judge-unavailable",
            "--note",
            "terminal crash fixture",
        )
        original_release = self.runtime_evolution.release_writer
        crashed = False

        def crash_before_writer_release(skill: Path, kind: str, owner: str) -> None:
            nonlocal crashed
            if kind == "evolution" and not crashed:
                crashed = True
                raise SystemExit("injected terminal evolution crash")
            original_release(skill, kind, owner)

        with mock.patch.object(self.runtime_evolution, "release_writer", side_effect=crash_before_writer_release):
            with self.assertRaises(SystemExit):
                self.dispatch(project, *arguments)
        self.assertTrue(crashed)
        self.assertTrue((skill_root / "state" / "registry" / "locks" / "shared-writer").exists())
        self.assertFalse((skill_root / "state" / "registry" / "locks" / "evolution-owner").exists())
        for index in range(6, 11):
            self.complete_non_git_change(project, f"change-{index}")

        recovered = self.cli(project, *arguments)
        self.assertEqual(recovered["status"], "already_completed")
        self.assertEqual(recovered["result_status"], "noop")
        self.assertTrue(recovered["next_window"]["pending"])
        self.assertEqual(
            recovered["next_window"]["eligible_unevaluated"],
            [f"change-{index}" for index in range(6, 11)],
        )
        self.assertFalse((skill_root / "state" / "registry" / "locks" / "shared-writer").exists())
        self.cli(
            project,
            "evolve",
            "check",
            "--claim-owner",
            "independent-judge",
            "--e1-confirmed",
        )
        reused_proposal = self.cli(project, *arguments)
        self.assertEqual(reused_proposal["status"], "noop")
        self.assertEqual(
            reused_proposal["evaluated_change_ids"],
            [f"change-{index}" for index in range(6, 11)],
        )

    def test_integration_pre_merge_failure_releases_writer_and_is_retryable(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("if-pre")
        integration_id = "if-pre-integration"
        before = self.git(project, "rev-parse", "HEAD")
        original_git = self.runtime_integration.git

        def fail_fast_forward(project_root: Path, *arguments: str, check: bool = True):
            if arguments and arguments[0] == "merge" and "--ff-only" in arguments:
                raise self.cli_module.HarnessError("injected ff-only failure")
            return original_git(project_root, *arguments, check=check)

        arguments = (
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(
                skill_root, integration_id, self.integration_candidate(skill_root, integration_id),
            )),
        )
        with mock.patch.object(self.runtime_integration, "git", side_effect=fail_fast_forward):
            with self.assertRaises(self.cli_module.HarnessError):
                self.dispatch(project, *arguments)
        self.assertEqual(before, self.git(project, "rev-parse", "HEAD"))
        record = json.loads(
            (skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["status"], "ready_for_review")
        self.assertEqual(record["landing_phase"], "pre_merge")
        self.assertFalse((skill_root / "state" / "registry" / "locks" / "shared-writer").exists())
        completed = self.cli(project, *arguments)
        self.assertEqual(completed["status"], "integrated")

    def test_integration_complete_detaches_shared_harness_before_worktree_removal(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("safe-complete")
        integration_id = "safe-complete-integration"
        record = json.loads((
            skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        ).read_text(encoding="utf-8"))
        worktree = skill_root / record["worktree"]
        attached = self.run_connector(worktree)
        self.assertEqual(attached["action"], "attached")
        sentinel = skill_root / "state" / "shared-harness-sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        stable_hashes = self.tree_hashes(skill_root / "references")
        candidate = self.integration_candidate(skill_root, integration_id)

        completed = self.cli(
            project,
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(skill_root, integration_id, candidate)),
        )
        self.assertEqual(completed["status"], "integrated")
        self.assertFalse(worktree.exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertEqual(stable_hashes, self.tree_hashes(skill_root / "references"))

    def test_integration_abort_detaches_shared_harness_before_worktree_removal(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("safe-abort")
        integration_id = "safe-abort-integration"
        record = json.loads((
            skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        ).read_text(encoding="utf-8"))
        worktree = skill_root / record["worktree"]
        self.run_connector(worktree)
        sentinel = skill_root / "state" / "abort-sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")

        aborted = self.cli(project, "integrate", "abort", integration_id)
        self.assertEqual(aborted["status"], "aborted")
        self.assertFalse(worktree.exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")

    def test_integration_cleanup_failure_resumes_without_relanding(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("safe-recovery")
        integration_id = "safe-recovery-integration"
        candidate = self.integration_candidate(skill_root, integration_id)
        arguments = (
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(skill_root, integration_id, candidate)),
        )
        with mock.patch.object(
            self.runtime_integration,
            "detach_worktree_links",
            side_effect=self.cli_module.HarnessError("injected detach failure"),
        ):
            with self.assertRaisesRegex(self.cli_module.HarnessError, "injected detach failure"):
                self.dispatch(project, *arguments)

        record_path = skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        failed = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(failed["status"], "landing_recovery_required")
        self.assertEqual(failed["landing_phase"], "registry_committed")
        landed = failed["landing_commit"]
        self.assertEqual(self.git(project, "rev-parse", "HEAD"), landed)
        self.assertTrue((skill_root / "state" / "registry" / "locks" / "shared-writer").is_dir())

        recovered = self.cli(project, "integrate", "complete", integration_id, "--confirm-i2")
        self.assertEqual(recovered["status"], "integrated")
        self.assertEqual(recovered["landing_commit"], landed)
        self.assertFalse((skill_root / "state" / "registry" / "locks" / "shared-writer").exists())

    def test_integration_git_worktree_remove_failure_is_retryable(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("safe-git-remove-recovery")
        integration_id = "safe-git-remove-recovery-integration"
        candidate = self.integration_candidate(skill_root, integration_id)
        arguments = (
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(skill_root, integration_id, candidate)),
        )
        original_git = self.runtime_integration.git

        def fail_worktree_remove(project_root: Path, *arguments: str, check: bool = True):
            if arguments[:2] == ("worktree", "remove"):
                return subprocess.CompletedProcess(
                    ["git", *arguments], 1, "", "injected worktree remove failure",
                )
            return original_git(project_root, *arguments, check=check)

        with mock.patch.object(self.runtime_integration, "git", side_effect=fail_worktree_remove):
            with self.assertRaisesRegex(self.cli_module.HarnessError, "injected worktree remove failure"):
                self.dispatch(project, *arguments)
        record_path = skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        failed = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(failed["landing_phase"], "registry_committed")
        self.assertEqual(failed["status"], "landing_recovery_required")
        landing = failed["landing_commit"]
        self.assertEqual(self.git(project, "rev-parse", "HEAD"), landing)

        recovered = self.cli(project, "integrate", "complete", integration_id, "--confirm-i2")
        self.assertEqual(recovered["landing_commit"], landing)
        self.assertEqual(recovered["record"]["landing_phase"], "cleanup_complete")

    def test_integration_abort_cleanup_failure_keeps_record_retryable(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("safe-abort-recovery")
        integration_id = "safe-abort-recovery-integration"
        record_path = skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        before = json.loads(record_path.read_text(encoding="utf-8"))
        worktree = skill_root / before["worktree"]
        with mock.patch.object(
            self.runtime_integration,
            "detach_worktree_links",
            side_effect=self.cli_module.HarnessError("injected abort detach failure"),
        ):
            with self.assertRaisesRegex(self.cli_module.HarnessError, "injected abort detach failure"):
                self.dispatch(project, "integrate", "abort", integration_id)
        failed = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(failed["status"], before["status"])
        self.assertIn("injected abort detach failure", failed["last_error"])
        self.assertTrue(worktree.is_dir())

        aborted = self.cli(project, "integrate", "abort", integration_id)
        self.assertEqual(aborted["status"], "aborted")
        self.assertFalse(worktree.exists())

    @unittest.skipUnless(os.name == "nt", "Windows Junction safety is Windows-specific")
    def test_integration_rejects_unknown_junction_before_git_worktree_removal(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("unknown-junction")
        integration_id = "unknown-junction-integration"
        record_path = skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        worktree = skill_root / record["worktree"]
        external = self.root / "external-junction-target"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        unknown = worktree / "unknown-junction"
        self.runtime_links.create_directory_link(unknown, external)

        rejected = self.cli(project, "integrate", "abort", integration_id, expected=(2,))
        self.assertIn("directory junctions", rejected["error"])
        self.assertTrue(worktree.is_dir())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.runtime_core.unlink_directory_link_node(unknown)
        self.cli(project, "integrate", "abort", integration_id)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")

    def test_i2_rejects_candidate_changed_after_review(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("review-binding")
        integration_id = "review-binding-integration"
        record = json.loads((
            skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        ).read_text(encoding="utf-8"))
        worktree = skill_root / record["worktree"]
        reviewed = self.git(worktree, "rev-parse", "HEAD")
        (worktree / "after-review.txt").write_text("not reviewed\n", encoding="utf-8")
        self.git(worktree, "add", "after-review.txt")
        self.git(worktree, "commit", "-m", "change candidate after review")
        changed = self.git(worktree, "rev-parse", "HEAD")
        before = self.git(project, "rev-parse", "HEAD")
        original_review = self.write_integration_review(skill_root, integration_id, reviewed)

        rejected = self.cli(
            project,
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(original_review),
            expected=(2,),
        )
        self.assertIn("does not bind", rejected["error"])
        self.assertEqual(before, self.git(project, "rev-parse", "HEAD"))
        self.assertFalse((project / "after-review.txt").exists())

        completed = self.cli(
            project,
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(skill_root, integration_id, changed)),
        )
        self.assertEqual(completed["record"]["reviewed_commit"], changed)
        self.assertTrue((project / "after-review.txt").is_file())

    def test_independent_review_identities_are_enforced(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("reviewer-identity")
        integration_id = "reviewer-identity-integration"
        record_path = skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        candidate = self.integration_candidate(skill_root, integration_id)
        report_path = self.write_integration_review(skill_root, integration_id, candidate)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["reviewer_id"] = record["integrator_id"]
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        rejected = self.cli(
            project,
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(report_path),
            expected=(2,),
        )
        self.assertIn("must differ", rejected["error"])

        evolution_project, evolution_skill, _ = self.prepare_evolution("judge-identity")
        judge_path = self.write_evolution_judge(evolution_skill)
        judge = json.loads(judge_path.read_text(encoding="utf-8"))
        judge["reviewer_id"] = "independent-judge"
        judge_path.write_text(json.dumps(judge, indent=2), encoding="utf-8")
        rejected = self.cli(
            evolution_project,
            "evolve",
            "mark-complete",
            "--proposal-id",
            "accepted-knowledge",
            "--owner",
            "independent-judge",
            "--candidate-id",
            "accepted-knowledge",
            "--judge-report",
            str(judge_path),
            "--status",
            "keep",
            expected=(2,),
        )
        self.assertIn("must differ", rejected["error"])

    def test_integration_terminal_crash_retry_releases_writer(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("terminal-integration")
        integration_id = "terminal-integration-integration"
        arguments = (
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(
                skill_root, integration_id, self.integration_candidate(skill_root, integration_id),
            )),
        )
        original_release = self.runtime_integration.release_writer
        crashed = False

        def crash_before_writer_release(skill: Path, kind: str, owner: str) -> None:
            nonlocal crashed
            if kind == "integration" and not crashed:
                crashed = True
                raise SystemExit("injected terminal integration crash")
            original_release(skill, kind, owner)

        with mock.patch.object(self.runtime_integration, "release_writer", side_effect=crash_before_writer_release):
            with self.assertRaises(SystemExit):
                self.dispatch(project, *arguments)
        self.assertTrue(crashed)
        writer = skill_root / "state" / "registry" / "locks" / "shared-writer"
        self.assertTrue(writer.exists())

        recovered = self.cli(project, "integrate", "complete", integration_id, "--confirm-i2")
        self.assertEqual(recovered["status"], "already_integrated")
        self.assertFalse(writer.exists())

    def test_integration_worktree_creation_failure_is_diagnostic_and_abortable(self) -> None:
        project = self.create_git_project("if-create")
        initialized = self.init_project(project, self.write_bundle(project, "if-create"))
        baseline = self.commit_routes(project)
        lane = self.root / "if-create-lane"
        self.git(project, "worktree", "add", "-b", "if-create-lane", str(lane), baseline)
        self.run_connector(lane)
        self.complete_git_change(lane, "if-create-change", "if-create.txt")
        original_git = self.runtime_integration.git

        def fail_worktree_add(project_root: Path, *arguments: str, check: bool = True):
            if arguments[:2] == ("worktree", "add"):
                raise self.cli_module.HarnessError("injected worktree creation failure")
            return original_git(project_root, *arguments, check=check)

        with mock.patch.object(self.runtime_integration, "git", side_effect=fail_worktree_add):
            with self.assertRaisesRegex(self.cli_module.HarnessError, "injected worktree"):
                self.dispatch(project, "integrate", "start", "if-create-integration", "if-create-change")
        skill_root = Path(initialized["skill_root"])
        record = json.loads((
            skill_root / "state" / "registry" / "integrations" / "if-create-integration.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "preparing_failed")
        self.assertIn("injected worktree", record["last_error"])
        aborted = self.cli(project, "integrate", "abort", "if-create-integration")
        self.assertEqual(aborted["status"], "aborted")

    def test_integration_post_merge_record_failure_retains_recovery_owner(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("if-post")
        integration_id = "if-post-integration"
        record_path = skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json"
        original_write = self.runtime_integration.atomic_write_json
        failed_once = False

        def fail_landed_record(path: Path, value: object) -> None:
            nonlocal failed_once
            if (
                not failed_once
                and Path(path) == record_path
                and isinstance(value, dict)
                and value.get("landing_phase") == "canonical_landed"
            ):
                failed_once = True
                raise OSError("injected post-merge record failure")
            original_write(path, value)

        arguments = (
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(
                skill_root, integration_id, self.integration_candidate(skill_root, integration_id),
            )),
        )
        with mock.patch.object(self.runtime_integration, "atomic_write_json", side_effect=fail_landed_record):
            with self.assertRaises(self.cli_module.HarnessError):
                self.dispatch(project, *arguments)
        self.assertTrue(failed_once)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(record["landing_phase"], "canonical_landed")
        self.assertEqual(self.git(project, "rev-parse", "HEAD"), record["landing_commit"])
        writer_path = skill_root / "state" / "registry" / "locks" / "shared-writer" / "owner.json"
        self.assertTrue(writer_path.is_file())
        writer = json.loads(writer_path.read_text(encoding="utf-8"))
        writer["claimed_at"] = "2000-01-01T00:00:00Z"
        writer_path.write_text(json.dumps(writer), encoding="utf-8")
        doctor = self.cli(project, "project", "doctor", expected=(1,))
        finding_types = {item["type"] for item in doctor["findings"]}
        self.assertIn("integration_recovery_required", finding_types)
        self.assertIn("stale_shared_writer", finding_types)
        completed = self.cli(project, "integrate", "complete", integration_id, "--confirm-i2")
        self.assertEqual(completed["status"], "integrated")
        self.assertFalse(writer_path.parent.exists())

    def test_integration_registry_failure_is_idempotent_and_event_is_not_duplicated(self) -> None:
        project, skill_root, _, _ = self.prepare_integration("if-reg")
        integration_id = "if-reg-integration"
        baseline_path = skill_root / "state" / "registry" / "baseline.json"
        before_baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["canonical_commit"]
        original_write = self.runtime_integration.atomic_write_json
        failed_once = False

        def fail_baseline_commit(path: Path, value: object) -> None:
            nonlocal failed_once
            if (
                not failed_once
                and Path(path) == baseline_path
                and isinstance(value, dict)
                and value.get("canonical_commit") != before_baseline
            ):
                failed_once = True
                raise OSError("injected Registry baseline failure")
            original_write(path, value)

        arguments = (
            "integrate",
            "complete",
            integration_id,
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(self.write_integration_review(
                skill_root, integration_id, self.integration_candidate(skill_root, integration_id),
            )),
        )
        with mock.patch.object(self.runtime_integration, "atomic_write_json", side_effect=fail_baseline_commit):
            with self.assertRaises(self.cli_module.HarnessError):
                self.dispatch(project, *arguments)
        self.assertTrue(failed_once)
        self.assertEqual(
            json.loads(baseline_path.read_text(encoding="utf-8"))["canonical_commit"],
            before_baseline,
        )
        events = list((skill_root / "state" / "registry" / "baseline-events").glob("*.json"))
        self.assertEqual(len(events), 1)
        recovery_record = json.loads(
            (skill_root / "state" / "registry" / "integrations" / f"{integration_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(recovery_record["landing_phase"], "canonical_landed")
        completed = self.cli(project, "integrate", "complete", integration_id, "--confirm-i2")
        self.assertEqual(completed["status"], "integrated")
        self.assertEqual(len(list((skill_root / "state" / "registry" / "baseline-events").glob("*.json"))), 1)

    def test_preflight_prioritizes_related_baseline_events_over_periodic_wiki(self) -> None:
        project = self.create_git_project("baseline-impact")
        initialized = self.init_project(project, self.write_bundle(project, "baseline-impact"))
        baseline = self.commit_routes(project)
        lanes = {}
        for suffix in ("producer", "related", "unrelated"):
            lane = self.root / f"baseline-{suffix}"
            self.git(project, "worktree", "add", "-b", f"baseline-{suffix}", str(lane), baseline)
            self.run_connector(lane)
            lanes[suffix] = lane

        producer = lanes["producer"]
        self.cli(producer, "change", "new", "api-change", "--scope", "change submit API")
        self.complete_change_documents(producer, "api-change")
        contract_path = self.root / "api-change-contract.json"
        contract_path.write_text(
            json.dumps({
                "kind": "api",
                "subject": "jobs.v1.submit",
                "operation": "change",
                "owner_module": "job-processing",
                "compatibility": "backward-compatible",
                "status": "proposed",
                "affected_paths": ["src/jobs/service.py"],
                "consumers": [],
                "depends_on": [],
                "depends_on_changes": [],
            }),
            encoding="utf-8",
        )
        self.cli(
            producer,
            "change",
            "publish",
            "api-change",
            "--status",
            "active",
            "--paths",
            "src/jobs/service.py",
            "--contract",
            str(contract_path),
        )
        published_change = json.loads((
            Path(initialized["skill_root"]) / "state" / "registry" / "changes" / "api-change.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(
            published_change["contract_path"],
            "state/registry/contracts/api-change.json",
        )
        with (producer / "src" / "jobs" / "service.py").open("a", encoding="utf-8") as handle:
            handle.write("\ndef submit_job_v2(payload): return submit_job(payload)\n")

        related = lanes["related"]
        self.cli(related, "change", "new", "related-work", "--scope", "consume submit API")
        self.cli(
            related,
            "change",
            "publish",
            "related-work",
            "--status",
            "active",
            "--paths",
            "src/jobs/service.py",
        )
        unrelated = lanes["unrelated"]
        self.cli(unrelated, "change", "new", "unrelated-work", "--scope", "edit note")
        self.cli(
            unrelated,
            "change",
            "publish",
            "unrelated-work",
            "--status",
            "active",
            "--paths",
            "misc-one/note.txt",
        )

        closed = self.cli(
            producer,
            "change",
            "close",
            "api-change",
            "--status",
            "completed",
            "--validation",
            "producer tests passed",
            "--validation-passed",
        )
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(closed["integration_boundary"], "not_recorded")
        self.git(producer, "add", ".")
        self.git(producer, "commit", "-m", "complete api change")
        completion = self.git(producer, "rev-parse", "HEAD")
        self.cli(
            project, "integrate", "start", "api-integration", "api-change",
            "--completion-commit", f"api-change={completion}",
        )
        api_candidate = self.integration_candidate(Path(initialized["skill_root"]), "api-integration")
        api_review = self.write_integration_review(
            Path(initialized["skill_root"]), "api-integration", api_candidate,
        )
        self.cli(
            project,
            "integrate",
            "complete",
            "api-integration",
            "--confirm-i2",
            "--validation",
            "aggregate pass",
            "--validation-passed",
            "--review-report",
            str(api_review),
        )

        related_preflight = self.cli(related, "change", "preflight", "--change-id", "related-work")
        self.assertEqual(related_preflight["action"], "replan")
        self.assertEqual(related_preflight["knowledge"]["status"], "refresh-needed")
        self.assertGreater(related_preflight["knowledge"]["candidate_items"], 0)
        self.assertGreater(related_preflight["knowledge"]["checked_sources"], 0)
        self.assertTrue(related_preflight["baseline_impacts"])
        self.assertEqual(
            related_preflight["knowledge"]["fact_priority"][0],
            "registry contracts and baseline events",
        )
        unrelated_preflight = self.cli(unrelated, "change", "preflight", "--change-id", "unrelated-work")
        self.assertEqual(unrelated_preflight["baseline_relation"], "canonical_advanced")
        self.assertEqual(unrelated_preflight["action"], "continue")
        self.assertEqual(unrelated_preflight["knowledge"]["status"], "current-for-change-scope")
        self.assertEqual(unrelated_preflight["knowledge"]["candidate_items"], 0)
        self.assertEqual(unrelated_preflight["knowledge"]["checked_sources"], 0)
        event = json.loads(next(
            (Path(initialized["skill_root"]) / "state" / "registry" / "baseline-events").glob("*.json")
        ).read_text(encoding="utf-8"))
        self.assertEqual(event["previous_canonical_commit"], baseline)
        self.assertEqual(event["contracts"][0]["subject"], "jobs.v1.submit")
        self.assertIn("src/jobs/service.py", event["affected_paths"])

    def test_single_lane_git_transition_preserves_identity_and_repairs_worktrees(self) -> None:
        project = self.root / "upgrade-project"
        (project / "src" / "jobs").mkdir(parents=True)
        (project / "src" / "runtime").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / "README.md").write_text("# Upgrade\n\nRuns jobs.\n", encoding="utf-8")
        (project / "pyproject.toml").write_text("[project]\nname='upgrade'\nversion='0.1'\n", encoding="utf-8")
        (project / ".env.example").write_text("APP_MODE=development\n", encoding="utf-8")
        (project / "src" / "jobs" / "service.py").write_text("def submit_job(x): return x\n", encoding="utf-8")
        (project / "src" / "runtime" / "worker.py").write_text("def run(x): return x\n", encoding="utf-8")
        (project / "tests" / "test_jobs.py").write_text("def test_job(): assert True\n", encoding="utf-8")
        initial = self.init_project(project, self.write_bundle(project, "upgrade-single"))
        old_skill_root = Path(initial["skill_root"])
        self.cli(project, "change", "new", "upgrade-history", "--scope", "preserve history bytes")
        summary = old_skill_root / "state" / "changes" / "active" / "upgrade-history" / "summary.md"
        with summary.open("a", encoding="utf-8") as handle:
            handle.write(f"\nLiteral identity evidence: {old_skill_root.name} {initial['project_id']}\n")
        results = old_skill_root / "state" / "evolution" / "results.tsv"
        with results.open("a", encoding="utf-8") as handle:
            handle.write(f"literal\t{initial['project_id']}\t-\t-\tnoop\tdry_run\tpreserve\n")
        preserved_active_change = self.tree_hashes(
            old_skill_root / "state" / "changes" / "active" / "upgrade-history"
        )
        preserved_results = results.read_bytes()

        self.run_process(["git", "init", "-b", "main", str(project)])
        self.git(project, "config", "user.email", "harness-tests@example.invalid")
        self.git(project, "config", "user.name", "Harness Tests")
        (project / ".gitignore").write_text(".agents/skills/\n.claude/skills/\n", encoding="utf-8")
        self.git(project, "add", ".")
        self.git(project, "commit", "-m", "initialize git after single-lane harness")
        baseline = self.git(project, "rev-parse", "HEAD")
        existing = []
        for suffix in ("one", "two"):
            worktree = self.root / f"upgrade-{suffix}"
            self.git(project, "worktree", "add", "-b", f"upgrade-{suffix}", str(worktree), baseline)
            existing.append(worktree)

        migrated = self.cli(project, "project", "migrate")
        self.assertIsNone(migrated["init"])
        self.assertTrue(migrated["applied"]["lane_rebound"])
        skill_root = old_skill_root
        self.assertTrue(skill_root.exists())
        self.assertEqual(initial["project_id"], json.loads(
            (skill_root / "state" / "manifest.json").read_text(encoding="utf-8")
        )["project_id"])
        self.assertEqual(
            preserved_active_change,
            self.tree_hashes(skill_root / "state" / "changes" / "active" / "upgrade-history"),
        )
        self.assertEqual(preserved_results, (skill_root / "state" / "evolution" / "results.tsv").read_bytes())
        rebound_change = json.loads((
            skill_root / "state" / "registry" / "changes" / "upgrade-history.json"
        ).read_text(encoding="utf-8"))
        rebound_baseline = json.loads((
            skill_root / "state" / "registry" / "baseline.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(rebound_change["base_commit"], baseline)
        self.assertEqual(rebound_baseline["canonical_branch"], "main")
        self.assertEqual(rebound_baseline["canonical_commit"], baseline)
        index = json.loads((skill_root / "state" / "changes" / "INDEX.json").read_text(encoding="utf-8"))
        index_change = next(item for item in index["changes"] if item["change_id"] == "upgrade-history")
        self.assertEqual(index_change["lane_id"], rebound_change["lane_id"])
        audit = self.cli(project, "project", "audit")
        self.assertTrue(audit["ecl"]["healthy"])
        for worktree in [project, *existing]:
            codex = worktree / ".agents" / "skills" / skill_root.name
            claude = worktree / ".claude" / "skills" / skill_root.name
            self.assertTrue(os.path.samefile(codex, skill_root))
            self.assertTrue(os.path.samefile(claude, skill_root))
        self.assertEqual((project / "AGENTS.md").read_text(encoding="utf-8").count("<!-- ECL-HARNESS:BEGIN -->"), 1)
        self.assertTrue(any((project / "scripts").glob("harness-skill-link.*")))
        for worktree in existing:
            self.assertIn("single-Lane mode", (worktree / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertFalse(any((worktree / "scripts").glob("harness-skill-link.*")))
        doctor = self.cli(project, "project", "doctor", expected=(1,))
        missing_worktrees = {
            item["worktree"] for item in doctor["findings"]
            if item["type"] in {"missing_worktree_route", "missing_worktree_connector"}
        }
        self.assertEqual(missing_worktrees, {str(path) for path in existing})

        committed = self.commit_routes(project)
        self.cli(project, "change", "park", "upgrade-history")
        resumed = self.cli(existing[0], "change", "resume", "upgrade-history")
        self.assertNotEqual(resumed["change"]["lane_id"], rebound_change["lane_id"])
        self.assertEqual(resumed["change"]["base_commit"], baseline)
        self.complete_change_documents(existing[0], "upgrade-history")
        (existing[0] / "upgrade-history.txt").write_text("portable change\n", encoding="utf-8")
        self.cli(
            existing[0], "change", "publish", "upgrade-history",
            "--paths", "upgrade-history.txt",
        )
        self.git(existing[0], "add", "upgrade-history.txt")
        self.git(existing[0], "commit", "-m", "complete portable upgrade change")
        completion = self.git(existing[0], "rev-parse", "HEAD")
        self.cli(
            existing[0], "change", "close", "upgrade-history",
            "--status", "completed", "--completion-commit", completion,
            "--validation", "transition validation passed", "--validation-passed",
        )
        integrated = self.cli(
            project, "integrate", "start", "upgrade-integration", "upgrade-history",
        )
        self.assertEqual(integrated["status"], "ready_for_review")
        self.cli(project, "integrate", "abort", "upgrade-integration")

        future = self.root / "upgrade-future"
        self.git(project, "worktree", "add", "-b", "upgrade-future", str(future), committed)
        self.assertFalse((future / ".agents" / "skills" / skill_root.name).exists())
        self.run_connector(future)
        self.assertTrue(os.path.samefile(future / ".agents" / "skills" / skill_root.name, skill_root))
        self.assertTrue(os.path.samefile(future / ".claude" / "skills" / skill_root.name, skill_root))

    def test_migrate_restores_legacy_closing_change_without_rewriting_evidence(self) -> None:
        project = self.create_git_project("closing-migration")
        bundle = self.write_bundle(project, "closing-migration")
        initialized = self.init_project(project, bundle)
        skill_root = Path(initialized["skill_root"])
        self.cli(project, "change", "new", "legacy-closing", "--scope", "resume after migration")
        self.complete_change_documents(project, "legacy-closing")
        evidence = skill_root / "state" / "changes" / "active" / "legacy-closing"
        before = self.tree_hashes(evidence)
        record_path = skill_root / "state" / "registry" / "changes" / "legacy-closing.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["status"] = "closing"
        record["integration_status"] = "not_integrated"
        record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        migrated = self.cli(
            project, "project", "migrate", "--analysis-bundle", str(bundle),
        )
        self.assertEqual(migrated["status"], "migration_applied")
        restored = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(restored["status"], "active")
        self.assertEqual(restored["integration_status"], "not_requested")
        self.assertEqual(before, self.tree_hashes(evidence))
        lane = json.loads(next(
            (skill_root / "state" / "registry" / "lanes").glob("*.json")
        ).read_text(encoding="utf-8"))
        self.assertEqual(lane["active_change_id"], "legacy-closing")
        self.assertTrue(self.cli(project, "project", "audit")["ecl"]["healthy"])

    def test_project_marker_rejects_mismatched_manifest_identity(self) -> None:
        project = self.root / "upgrade-invalid-owner"
        project.mkdir()
        initial = self.init_project(project)
        predecessor = Path(initial["skill_root"])
        manifest_path = predecessor / "state" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["project_id"] = ""
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        self.run_process(["git", "init", "-b", "main", str(project)])
        self.git(project, "config", "user.email", "harness-tests@example.invalid")
        self.git(project, "config", "user.name", "Harness Tests")
        (project / "README.md").write_text("# Invalid owner fixture\n", encoding="utf-8")
        (project / ".gitignore").write_text(".agents/skills/\n.claude/skills/\n", encoding="utf-8")
        self.git(project, "add", ".")
        self.git(project, "commit", "-m", "initialize git")

        rejected = self.cli(project, "project", "migrate", expected=(2,))
        self.assertIn("Project id does not match", rejected["error"])
        self.assertTrue(predecessor.is_dir())

    def test_project_identity_and_fingerprints_survive_directory_move(self) -> None:
        project = self.create_git_project("portable-move")
        initialized = self.init_project(project, self.write_bundle(project, "portable-move"))
        project_id = initialized["project_id"]
        before = self.cli(project, "knowledge", "scan")
        self.assertTrue(before["healthy"])

        moved = self.root / "moved" / "portable-move"
        moved.parent.mkdir()
        shutil.move(str(project), str(moved))
        context = self.runtime_project.project_context(moved)
        self.assertEqual(context["project_id"], project_id)
        after = self.cli(moved, "knowledge", "scan")
        self.assertTrue(after["healthy"])
        self.assertEqual(after["checked"], before["checked"])

    def test_persistent_state_contains_no_machine_absolute_paths(self) -> None:
        project = self.create_git_project("portable-state")
        initialized = self.init_project(project, self.write_bundle(project, "portable-state"))
        skill_root = Path(initialized["skill_root"])
        absolute = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
        prohibited_fields = {
            "project_root", "git_common_dir", "canonical_root", "host_command", "runtime_links",
        }

        def inspect(value: object, path: str = "") -> list[str]:
            findings: list[str] = []
            if isinstance(value, dict):
                for key, nested in value.items():
                    if key in prohibited_fields:
                        findings.append(f"{path}/{key}")
                    findings.extend(inspect(nested, f"{path}/{key}"))
            elif isinstance(value, list):
                for index, nested in enumerate(value):
                    findings.extend(inspect(nested, f"{path}/{index}"))
            elif isinstance(value, str) and absolute.match(value):
                findings.append(f"{path}={value}")
            return findings

        findings = []
        for path in sorted((skill_root / "state").rglob("*.json")):
            findings.extend(inspect(json.loads(path.read_text(encoding="utf-8")), path.name))
        self.assertEqual(findings, [])

    def test_complete_bundle_rejects_repository_prose_evidence(self) -> None:
        project = self.create_git_project("prose-evidence")
        bundle = self.write_bundle(project, "prose-evidence")
        profile_path = bundle / "project-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["purpose"]["evidence"] = ["README.md"]
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("repository prose-document references", rejected["error"])
        self.assertIn("README.md", rejected["error"])

        (project / "STATUS.md").write_text("# Current status\n", encoding="utf-8")
        profile["purpose"]["evidence"] = ["STATUS.md"]
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        status_rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("STATUS.md", status_rejected["error"])

        profile["purpose"]["evidence"] = ["src/jobs/service.py"]
        original_roots = profile["modules"][0]["roots"]
        profile["modules"][0]["roots"] = ["STATUS.md"]
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        structural_rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("STATUS.md", structural_rejected["error"])
        profile["modules"][0]["roots"] = original_roots
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        architecture_path = bundle / "architecture.json"
        architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
        original_flow = architecture["code_paths"][0]["flow"]
        architecture["code_paths"][0]["flow"] = ["STATUS.md"]
        architecture_path.write_text(json.dumps(architecture, indent=2), encoding="utf-8")
        architecture_rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("STATUS.md", architecture_rejected["error"])
        architecture["code_paths"][0]["flow"] = original_flow

        original_dependency = architecture["dependencies"][0]["from"]
        architecture["dependencies"][0]["from"] = "STATUS.md"
        architecture_path.write_text(json.dumps(architecture, indent=2), encoding="utf-8")
        dependency_rejected = self.cli(
            project, "project", "init", "--analysis-bundle", str(bundle), expected=(2,),
        )
        self.assertIn("STATUS.md", dependency_rejected["error"])
        architecture["dependencies"][0]["from"] = original_dependency
        architecture_path.write_text(json.dumps(architecture, indent=2), encoding="utf-8")

        source = project / "src" / "readme_parser.py"
        source.write_text("def parse_readme():\n    return 'source code'\n", encoding="utf-8")
        interface = project / "docs" / "openapi.yaml"
        interface.parent.mkdir()
        interface.write_text("openapi: 3.1.0\n", encoding="utf-8")
        self.assertFalse(self.runtime_analysis.is_repository_prose_path("src/readme_parser.py"))
        self.assertFalse(self.runtime_analysis.is_repository_prose_path("docs/openapi.yaml"))
        self.assertFalse(self.runtime_analysis.is_repository_prose_path("https://example.test/spec.md"))
        self.assertFalse(self.runtime_analysis.is_repository_prose_path("user: Generate README.md"))
        self.assertTrue(self.runtime_analysis.is_repository_prose_path("STATUS.md"))
        profile["purpose"]["summary"] = "Generate README.md output from source-backed behavior."
        profile["purpose"]["evidence"] = ["src/readme_parser.py", "user: Generate README.md"]
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        accepted = self.cli(
            project, "project", "init", "--analysis-bundle", str(bundle),
        )
        self.assertEqual(accepted["status"], "initialized")

    def test_detached_head_cannot_create_structured_change(self) -> None:
        project = self.create_git_project("detached-lane")
        self.init_project(project, self.write_bundle(project, "detached-lane"))
        self.commit_routes(project)
        self.git(project, "checkout", "--detach")
        rejected = self.cli(
            project, "change", "new", "detached-change", "--scope", "mutate project",
            expected=(2,),
        )
        self.assertIn("named Git branch", rejected["error"])

    def test_manifest_1_upgrade_is_portable_and_complete_requires_refresh(self) -> None:
        bootstrap = self.root / "portable-bootstrap"
        bootstrap.mkdir()
        initialized = self.init_project(bootstrap)
        manifest_path = Path(initialized["skill_root"]) / "state" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.cli(bootstrap, "change", "new", "portable-contract", "--scope", "portable contract")
        contract_input = self.root / "portable-contract.json"
        contract_input.write_text(json.dumps({
            "kind": "api", "subject": "portable.v1.sample", "operation": "change",
            "owner_module": "portable-contract", "compatibility": "backward-compatible",
            "status": "proposed", "affected_paths": ["src/api.py"], "consumers": [],
            "depends_on": [], "depends_on_changes": [],
        }), encoding="utf-8")
        published = self.cli(
            bootstrap, "change", "publish", "portable-contract", "--contract", str(contract_input),
        )
        change_path = manifest_path.parent / "registry" / "changes" / "portable-contract.json"
        change = json.loads(change_path.read_text(encoding="utf-8"))
        contract_record = Path(initialized["skill_root"]) / published["change"]["contract_path"]
        change["contract_path"] = str(contract_record.resolve())
        change_path.write_text(json.dumps(change, indent=2), encoding="utf-8")

        manifest.update({
            "schema_version": "1.0", "project_root": str(bootstrap),
            "git_common_dir": None, "host_command": str(Path(sys.executable).resolve()),
            "runtime_links": [{"runtime": "codex", "path": str(manifest_path.parent)}],
        })
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        migrated = self.cli(bootstrap, "project", "migrate")
        self.assertTrue(migrated["applied"]["portable_state_upgrade"])
        portable = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(portable["schema_version"], "2.0")
        for key in ("project_root", "git_common_dir", "host_command", "runtime_links"):
            self.assertNotIn(key, portable)
        migrated_change = json.loads(change_path.read_text(encoding="utf-8"))
        self.assertEqual(
            migrated_change["contract_path"],
            "state/registry/contracts/portable-contract.json",
        )

        project = self.create_git_project("semantic-refresh-required")
        complete = self.init_project(project, self.write_bundle(project, "semantic-refresh-required"))
        complete_manifest_path = Path(complete["skill_root"]) / "state" / "manifest.json"
        complete_manifest = json.loads(complete_manifest_path.read_text(encoding="utf-8"))
        complete_manifest["schema_version"] = "1.0"
        complete_manifest["project_root"] = str(project)
        complete_manifest_path.write_text(json.dumps(complete_manifest, indent=2), encoding="utf-8")
        rejected = self.cli(project, "project", "migrate", expected=(2,))
        self.assertIn("semantic_refresh_required", rejected["error"])
        self.assertEqual(
            json.loads(complete_manifest_path.read_text(encoding="utf-8"))["schema_version"], "1.0",
        )

    def test_complete_migrate_refreshes_runtime_owned_scaffold_references(self) -> None:
        project = self.create_git_project("refresh-runtime-references")
        bundle = self.write_bundle(project, "refresh-runtime-references")
        initialized = self.init_project(project, bundle)
        skill_root = Path(initialized["skill_root"])
        manifest_path = skill_root / "state" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = "1.0"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        references = skill_root / "references"
        (references / "analysis-contract.md").write_text(
            "Use canonical repository documents as durable citations.\n",
            encoding="utf-8",
        )
        (references / "runtime-modules.md").write_text("stale runtime map\n", encoding="utf-8")
        (references / "git-collaboration.md").unlink()
        entry_path = skill_root / "SKILL.md"
        entry_path.write_text(
            entry_path.read_text(encoding="utf-8").replace(
                "Read `references/git-collaboration.md` only when creating, sharing, cloning, updating, reviewing, or\n"
                "diagnosing an independent Git repository for this project Skill. Ordinary project work does not load\n"
                "or run that Git workflow.\n\n",
                "",
            ),
            encoding="utf-8",
        )

        self.cli(project, "project", "migrate", "--analysis-bundle", str(bundle))

        for name in ("analysis-contract.md", "runtime-modules.md", "git-collaboration.md"):
            self.assertEqual(
                (ROOT / "assets" / "project-skill" / "references" / name).read_bytes(),
                (references / name).read_bytes(),
            )
        self.assertIn("references/git-collaboration.md", entry_path.read_text(encoding="utf-8"))

    def test_fresh_migrate_reports_applied_analysis_bundle(self) -> None:
        project = self.create_git_project("fresh-migrate")
        bundle = self.write_bundle(project, "fresh-migrate")
        migrated = self.cli(
            project,
            "project",
            "migrate",
            "--analysis-bundle",
            str(bundle),
        )
        self.assertEqual(migrated["status"], "migration_applied")
        self.assertEqual(migrated["init"]["status"], "initialized")
        self.assertEqual(migrated["applied"]["via"], "project_init")
        self.assertTrue(migrated["applied"]["knowledge"]["modules"])

    def test_main_returns_structured_json_for_filesystem_errors(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(self.cli_module, "dispatch", side_effect=OSError("injected filesystem failure")):
            with contextlib.redirect_stderr(stderr):
                code = self.cli_module.main([
                    "project", "audit", "--project-root", str(self.root),
                ])
        self.assertEqual(code, 2)
        payload = json.loads(stderr.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("filesystem failure", payload["error"])

    def test_doctor_reports_incomplete_content_transaction_before_recovery(self) -> None:
        project = self.root / "transaction-doctor"
        project.mkdir()
        initialized = self.init_project(project)
        skill_root = Path(initialized["skill_root"])
        transaction_root = self.runtime_transactions.content_transaction_store(skill_root) / "evolution-stale-deadbeef"
        replacement = transaction_root / "next"
        replacement.mkdir(parents=True)
        journal = {
            "schema_version": "1.0",
            "operation": "evolution",
            "transaction_id": "stale",
            "skill_root": str(skill_root),
            "candidate": str(skill_root / "state" / "evolution" / "staging" / "stale"),
            "transaction_root": str(transaction_root),
            "replacement": str(replacement),
            "backup": str(transaction_root / "previous"),
            "original_analysis": str(transaction_root / "original-analysis"),
            "state_snapshots": {},
            "phase": "prepared",
        }
        (transaction_root / "journal.json").write_text(json.dumps(journal), encoding="utf-8")
        doctor = self.cli(project, "project", "doctor", expected=(1,))
        findings = [item for item in doctor["findings"] if item["type"] == "incomplete_content_transaction"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["phase"], "prepared")
        outside = self.root / "must-not-be-removed"
        outside.mkdir()
        (outside / "sentinel.txt").write_text("keep\n", encoding="utf-8")
        journal["replacement"] = str(outside)
        (transaction_root / "journal.json").write_text(json.dumps(journal), encoding="utf-8")
        rejected = self.cli(project, "change", "status", expected=(2,))
        self.assertIn("outside", rejected["error"])
        self.assertTrue((outside / "sentinel.txt").is_file())
        journal["replacement"] = str(replacement)
        (transaction_root / "journal.json").write_text(json.dumps(journal), encoding="utf-8")
        self.cli(project, "change", "status")
        self.assertFalse(self.runtime_transactions.content_transaction_store(skill_root).exists())

    @unittest.skipUnless(os.name == "nt", "Windows launcher fallback")
    def test_windows_host_launcher_falls_back_without_unstartable_powershell_route(self) -> None:
        destination = self.root / "runtime-fallback"
        destination.mkdir()
        with mock.patch.object(self.runtime_links.shutil, "which", return_value=None):
            routes = self.runtime_links.generated_command_routes()
            launchers = self.runtime_links.copy_runtime(destination)
            with self.assertRaises(self.cli_module.HarnessError):
                self.runtime_links.connector_route()
        self.assertTrue(all(value.endswith(".cmd") for value in routes.values()))
        self.assertIn("harness-project.cmd", launchers)
        launcher = destination / "scripts" / "harness-project.cmd"
        content = launcher.read_text(encoding="utf-8")
        self.assertNotIn(str(Path(sys.executable).resolve()), content)
        self.assertIn("ECL_HARNESS_PYTHON", content)
        self.assertIn("py -3", content)
        self.assertNotIn("powershell", content.lower())


if __name__ == "__main__":
    unittest.main()
