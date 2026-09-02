#!/usr/bin/env python3
"""Render one approved Greenfield business-project variant into an empty output directory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


VARIANTS = {"go-cli", "go-web", "typescript-cli", "typescript-web", "python-cli", "python-web"}


def identifier(value: str, *, python: bool = False) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_" if python else "-", value).strip("_-").lower()
    if not normalized or (python and normalized[0].isdigit()):
        raise ValueError("Project/package name cannot form a valid identifier.")
    return normalized


def common_readme(name: str, variant: str, commands: dict[str, str]) -> str:
    command_lines = "\n".join(f"- `{command}` - {purpose}" for purpose, command in commands.items())
    return f"""# {name}

{variant} bootstrap created from an approved Structured Change.

## Commands

{command_lines}

## Architecture

Transport/CLI entrypoints depend on application behavior. Application behavior does not depend on
the transport. Replace the starter scenario only through the accepted Change and its tests.
"""


def go_files(name: str, module: str, web: bool) -> tuple[dict[str, str], dict[str, str]]:
    commands = {"build": "go build ./...", "test": "go test ./...", "lint": "go vet ./..."}
    files = {
        "go.mod": f"module {module}\n\ngo 1.22\n",
        "internal/app/app.go": "package app\n\nfunc Execute(input string) string { return input }\n",
        "internal/app/app_test.go": "package app\n\nimport \"testing\"\n\nfunc TestExecute(t *testing.T) { if Execute(\"accepted\") != \"accepted\" { t.Fatal(\"unexpected result\") } }\n",
    }
    if web:
        commands["start"] = "go run ./cmd/api"
        files.update({
            "internal/httpapi/handler.go": f'''package httpapi

import (
    "encoding/json"
    "net/http"
    "{module}/internal/app"
)

func Handler() http.Handler {{
    mux := http.NewServeMux()
    mux.HandleFunc("GET /accepted", func(w http.ResponseWriter, r *http.Request) {{
        w.Header().Set("Content-Type", "application/json")
        _ = json.NewEncoder(w).Encode(map[string]string{{"result": app.Execute("accepted")}})
    }})
    return mux
}}
''',
            "internal/httpapi/handler_test.go": '''package httpapi

import ("net/http"; "net/http/httptest"; "testing")
func TestAccepted(t *testing.T) { r := httptest.NewRequest("GET", "/accepted", nil); w := httptest.NewRecorder(); Handler().ServeHTTP(w, r); if w.Code != http.StatusOK { t.Fatalf("status %d", w.Code) } }
''',
            "cmd/api/main.go": f'''package main
import ("log"; "net/http"; "os"; "{module}/internal/httpapi")
func main() {{ address := os.Getenv("APP_ADDRESS"); if address == "" {{ log.Fatal("APP_ADDRESS is required") }}; log.Fatal(http.ListenAndServe(address, httpapi.Handler())) }}
''',
        })
    else:
        commands["start"] = f"go run ./cmd/{name} accepted"
        files["cmd/{name}/main.go"] = f'''package main
import ("fmt"; "os"; "{module}/internal/app")
func main() {{ if len(os.Args) != 2 {{ fmt.Fprintln(os.Stderr, "one argument is required"); os.Exit(2) }}; fmt.Println(app.Execute(os.Args[1])) }}
'''
    return files, commands


def typescript_files(name: str, web: bool) -> tuple[dict[str, str], dict[str, str]]:
    commands = {
        "build": "npm run build", "test": "npm test", "lint": "npm run typecheck",
        "typecheck": "npm run typecheck", "start": "npm start",
    }
    package = {
        "name": name, "private": True, "version": "0.1.0", "type": "module",
        "scripts": {
            "build": "tsc -p tsconfig.json", "typecheck": "tsc -p tsconfig.json --noEmit",
            "test": "npm run build && node dist/test/app.test.js" + (" && node dist/test/http.test.js" if web else ""),
            "start": "node dist/src/server.js" if web else "node dist/src/cli.js accepted",
        },
        "devDependencies": {"typescript": "^5.5.0"},
    }
    files = {
        "package.json": json.dumps(package, indent=2) + "\n",
        "tsconfig.json": json.dumps({
            "compilerOptions": {"target": "ES2022", "module": "NodeNext", "moduleResolution": "NodeNext", "strict": True, "outDir": "dist", "rootDir": "."},
            "include": ["src/**/*.ts", "test/**/*.ts"],
        }, indent=2) + "\n",
        "src/app.ts": "export function execute(input: string): string { return input; }\n",
        "test/app.test.ts": "import { execute } from '../src/app.js';\nif (execute('accepted') !== 'accepted') throw new Error('unexpected result');\n",
    }
    if web:
        files.update({
            "src/http.ts": "import { execute } from './app.js';\nexport function response(method: string, path: string) { return method === 'GET' && path === '/accepted' ? {status: 200, body: {result: execute('accepted')}} : {status: 404, body: {error: 'not_found'}}; }\n",
            "src/node-shims.d.ts": "declare const process: { env: Record<string, string | undefined> };\ndeclare module 'node:http' { export function createServer(handler: (request: any, response: any) => void): { listen(port: number, host: string): void }; }\n",
            "src/server.ts": "import { createServer } from 'node:http';\nimport { response } from './http.js';\nconst address = process.env.APP_ADDRESS; if (!address) throw new Error('APP_ADDRESS is required');\nconst [host, port] = address.split(':'); createServer((req, res) => { const value = response(req.method ?? '', req.url ?? ''); res.writeHead(value.status, {'content-type':'application/json'}); res.end(JSON.stringify(value.body)); }).listen(Number(port), host);\n",
            "test/http.test.ts": "import { response } from '../src/http.js';\nif (response('GET','/accepted').status !== 200) throw new Error('unexpected status');\n",
        })
    else:
        files["src/cli.ts"] = "declare const process: { argv: string[]; exitCode?: number };\nimport { execute } from './app.js';\nconst input = process.argv[2]; if (!input) { console.error('one argument is required'); process.exitCode = 2; } else console.log(execute(input));\n"
    return files, commands


def python_files(name: str, package: str, web: bool) -> tuple[dict[str, str], dict[str, str]]:
    commands = {
        "build": "python -m compileall -q src", "test": "python -m unittest discover -s tests -v",
        "lint": "python -m compileall -q src tests", "typecheck": "python -m compileall -q src tests",
        "start": "python main.py" if web else "python main.py accepted",
    }
    files = {
        "pyproject.toml": f'''[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.11"

[tool.unittest]
start-directory = "tests"
''',
        f"src/{package}/__init__.py": "",
        f"src/{package}/application.py": "def execute(value: str) -> str:\n    return value\n",
        "tests/test_application.py": f"import sys, unittest\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parents[1] / 'src'))\nfrom {package}.application import execute\n\nclass ApplicationTest(unittest.TestCase):\n    def test_execute(self): self.assertEqual(execute('accepted'), 'accepted')\n",
    }
    if web:
        files.update({
            "main.py": f"import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / 'src'))\nimport {package}.server\n",
            f"src/{package}/http_contract.py": "from .application import execute\ndef response(method: str, path: str):\n    return (200, {'result': execute('accepted')}) if (method, path) == ('GET', '/accepted') else (404, {'error': 'not_found'})\n",
            f"src/{package}/server.py": f"import json, os\nfrom http.server import BaseHTTPRequestHandler, HTTPServer\nfrom .http_contract import response\nclass Handler(BaseHTTPRequestHandler):\n    def do_GET(self):\n        status, body = response('GET', self.path); self.send_response(status); self.send_header('content-type','application/json'); self.end_headers(); self.wfile.write(json.dumps(body).encode())\naddress = os.environ.get('APP_ADDRESS');\nif not address: raise SystemExit('APP_ADDRESS is required')\nhost, port = address.rsplit(':', 1); HTTPServer((host, int(port)), Handler).serve_forever()\n",
            "tests/test_http.py": f"import sys, unittest\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parents[1] / 'src'))\nfrom {package}.http_contract import response\nclass HttpTest(unittest.TestCase):\n    def test_accepted(self): self.assertEqual(response('GET','/accepted')[0], 200)\n",
        })
    else:
        files["main.py"] = f"import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / 'src'))\nfrom {package}.application import execute\nif len(sys.argv) != 2: raise SystemExit('one argument is required')\nprint(execute(sys.argv[1]))\n"
        files[f"src/{package}/cli.py"] = "import sys\nfrom .application import execute\nif len(sys.argv) != 2: raise SystemExit('one argument is required')\nprint(execute(sys.argv[1]))\n"
    return files, commands


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--module", help="Required Go module path; defaults to example.invalid/<project>.")
    args = parser.parse_args()
    root = args.output_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise SystemExit("Output root must be empty; render only inside an approved bootstrap Change.")
    root.mkdir(parents=True, exist_ok=True)
    name = identifier(args.project_name)
    language, kind = args.variant.split("-", 1)
    if language == "go":
        files, commands = go_files(name, args.module or f"example.invalid/{name}", kind == "web")
    elif language == "typescript":
        files, commands = typescript_files(name, kind == "web")
    else:
        files, commands = python_files(name, identifier(name, python=True), kind == "web")
    files["README.md"] = common_readme(args.project_name, args.variant, commands)
    files[".github/workflows/ci.yml"] = "# Select and pin the accepted CI runtime, then run the README command matrix.\n"
    for relative, content in files.items():
        target = root / relative.format(name=name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(json.dumps({"variant": args.variant, "output_root": str(root), "files": sorted(files), "commands": commands}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
