#!/usr/bin/env node
// ECL-HARNESS-CONNECTOR
// Attach this worktree to its project-level shared Harness Skill without requiring Python.

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const skillName = "{{SKILL_NAME}}";
const projectId = "{{PROJECT_ID}}";

function git(cwd, ...args) {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim();
}

function sameTarget(link, target) {
  try {
    return fs.realpathSync.native(link) === fs.realpathSync.native(target);
  } catch {
    return false;
  }
}

function rejectLinkedAncestors(root, link) {
  const relative = path.relative(root, path.dirname(link));
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`Skill path escapes this worktree: ${link}`);
  }
  let current = root;
  for (const part of relative.split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) {
      throw new Error(`Skill path must not traverse a link or junction: ${current}`);
    }
  }
}

function addSkillLink(root, link, target) {
  if (path.resolve(link) === path.resolve(target)) return "physical";
  rejectLinkedAncestors(root, link);
  if (fs.existsSync(link)) {
    if (sameTarget(link, target)) return "existing";
    throw new Error(`Skill path collision: ${link}`);
  }
  fs.mkdirSync(path.dirname(link), { recursive: true });
  const type = process.platform === "win32" ? "junction" : "dir";
  const value = process.platform === "win32" ? target : path.relative(path.dirname(link), target);
  fs.symlinkSync(value, link, type);
  return "created";
}

const current = process.cwd();
const root = path.resolve(git(current, "rev-parse", "--show-toplevel"));
const commonRaw = git(root, "rev-parse", "--git-common-dir");
const common = path.resolve(root, commonRaw);
const worktreeLines = git(root, "worktree", "list", "--porcelain").split(/\r?\n/);
const firstWorktree = worktreeLines.find((line) => line.startsWith("worktree "));
const primary = path.basename(common) === ".git"
  ? path.dirname(common)
  : path.resolve(firstWorktree?.slice("worktree ".length).trim() ?? "");
if (!primary) throw new Error("could not resolve the primary worktree");
const canonical = path.join(primary, ".agents", "skills", skillName);
if (!fs.statSync(path.join(canonical, "SKILL.md"), { throwIfNoEntry: false })?.isFile()) {
  throw new Error(`canonical project Harness is missing: ${canonical}`);
}
if (fs.lstatSync(canonical).isSymbolicLink()) {
  throw new Error(`canonical project Harness must be physical: ${canonical}`);
}
const manifest = JSON.parse(fs.readFileSync(path.join(canonical, "state", "manifest.json"), "utf8"));
if (
  manifest.project_id !== projectId
  || manifest.mode !== "multi_lane"
  || path.resolve(manifest.project_root ?? "") !== primary
  || path.resolve(manifest.git_common_dir ?? "") !== common
) {
  throw new Error("canonical project Harness manifest does not match this Git project");
}

const links = {
  codex: path.join(root, ".agents", "skills", skillName),
  claude: path.join(root, ".claude", "skills", skillName),
};
const result = {};
const created = [];
try {
  for (const [name, link] of Object.entries(links)) {
    const status = addSkillLink(root, link, canonical);
    result[name] = { path: link, status };
    if (status === "created") created.push(link);
  }
} catch (error) {
  for (const link of created.reverse()) {
    try { fs.unlinkSync(link); } catch { /* Preserve the original connector error. */ }
  }
  throw error;
}
process.stdout.write(`${JSON.stringify({ ok: true, skill: canonical, links: result }, null, 2)}\n`);
