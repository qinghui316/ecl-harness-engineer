# ECL-HARNESS-CONNECTOR
$ErrorActionPreference = "Stop"

$SkillName = "{{SKILL_NAME}}"
$ProjectId = "{{PROJECT_ID}}"

function Invoke-Git([string[]] $Arguments, [string] $WorkingDirectory) {
    $result = & git -C $WorkingDirectory @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed: git -C $WorkingDirectory $($Arguments -join ' ')"
    }
    return ($result | Out-String).Trim()
}

function Resolve-LinkTarget([string] $Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.LinkType -and $item.Target) {
        $target = @($item.Target)[0]
        if (-not [System.IO.Path]::IsPathRooted($target)) {
            $target = Join-Path $item.Parent.FullName $target
        }
        return [System.IO.Path]::GetFullPath($target).TrimEnd('\', '/')
    }
    return [System.IO.Path]::GetFullPath($item.FullName).TrimEnd('\', '/')
}

function Assert-PhysicalAncestors([string] $Root, [string] $Path) {
    $normalizedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $normalizedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $prefix = $normalizedRoot + [System.IO.Path]::DirectorySeparatorChar
    if (-not $normalizedPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Skill path escapes this worktree: $Path"
    }
    $current = Split-Path -Parent $normalizedPath
    while ($current -and $current -ine $normalizedRoot) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if ($item.LinkType) {
                throw "Skill path must not traverse a link or junction: $current"
            }
        }
        $parent = Split-Path -Parent $current
        if ($parent -eq $current) { throw "Skill path escapes this worktree: $Path" }
        $current = $parent
    }
}

function Add-SkillLink([string] $Root, [string] $Path, [string] $Target) {
    $normalizedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $normalizedTarget = [System.IO.Path]::GetFullPath($Target).TrimEnd('\', '/')
    if ($normalizedPath -ieq $normalizedTarget) {
        return "physical"
    }
    Assert-PhysicalAncestors $Root $Path
    if (Test-Path -LiteralPath $Path) {
        if ((Resolve-LinkTarget $Path) -ieq $normalizedTarget) {
            return "existing"
        }
        throw "Skill path collision: $Path"
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
    $output = & cmd /c mklink /J $Path $Target 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw (($output | Out-String).Trim())
    }
    return "created"
}

$current = (Get-Location).Path
$root = Invoke-Git @("rev-parse", "--show-toplevel") $current
$commonRaw = Invoke-Git @("rev-parse", "--git-common-dir") $root
$common = if ([System.IO.Path]::IsPathRooted($commonRaw)) {
    [System.IO.Path]::GetFullPath($commonRaw)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $root $commonRaw))
}
$primary = if ((Split-Path -Leaf $common) -eq ".git") {
    Split-Path -Parent $common
} else {
    $line = (Invoke-Git @("worktree", "list", "--porcelain") $root).Split("`n") |
        Where-Object { $_.StartsWith("worktree ") } |
        Select-Object -First 1
    if (-not $line) { throw "could not resolve the primary worktree" }
    $line.Substring("worktree ".Length).Trim()
}
$canonical = Join-Path $primary ".agents/skills/$SkillName"
if (-not (Test-Path -LiteralPath (Join-Path $canonical "SKILL.md") -PathType Leaf)) {
    throw "canonical project Harness is missing: $canonical"
}
$canonicalItem = Get-Item -LiteralPath $canonical -Force
if ($canonicalItem.LinkType) {
    throw "canonical project Harness must be physical: $canonical"
}
$manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $canonical "state/manifest.json") | ConvertFrom-Json
if ($manifest.project_id -ne $ProjectId -or $manifest.skill_name -ne $SkillName) {
    throw "canonical project Harness manifest does not match this Git project"
}

$links = [ordered]@{
    codex = Join-Path $root ".agents/skills/$SkillName"
    claude = Join-Path $root ".claude/skills/$SkillName"
}
$result = [ordered]@{}
$created = [System.Collections.Generic.List[string]]::new()
try {
    foreach ($entry in $links.GetEnumerator()) {
        $status = Add-SkillLink $root $entry.Value $canonical
        $result[$entry.Key] = [ordered]@{
            path = $entry.Value
            status = $status
        }
        if ($status -eq "created") {
            $created.Add($entry.Value)
        }
    }
} catch {
    for ($index = $created.Count - 1; $index -ge 0; $index--) {
        try {
            [System.IO.Directory]::Delete($created[$index])
        } catch {
            # Preserve the original connector error.
        }
    }
    throw
}

[ordered]@{ ok = $true; skill = $canonical; links = $result } |
    ConvertTo-Json -Depth 5
