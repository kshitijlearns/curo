<#
.SYNOPSIS
  CURO common commands for Windows PowerShell (same targets as the Makefile).

.EXAMPLE
  ./dev.ps1 setup        # one-time: Python venv + web packages
  ./dev.ps1 local -seed  # API + worker + scheduler without Docker (embedded Postgres)
  ./dev.ps1 web          # the web app on http://localhost:3000
  ./dev.ps1 test
  ./dev.ps1 time advance 6h
#>
param(
  [Parameter(Position = 0)] [string] $Target = "help",
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)] [string[]] $Rest = @()
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

function Invoke-Step([scriptblock] $Block) {
  & $Block
  if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE)" }
}

function Ensure-Env {
  if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "created .env" }
}

function Up {
  Ensure-Env
  Invoke-Step { docker compose up -d --build }
  Invoke-Step { python tools/wait_for_api.py }
}

switch ($Target) {
  "help" {
    Write-Host @"
Targets:
  setup        install the Python venv (+ embedded test Postgres) and web packages
  dev          start the Docker stack, then the web app (http://localhost:3000)
  up           start db, redis, api, worker, scheduler and wait for /health
  web          the web app only (API already running), http://localhost:3000
  down         stop the stack (data kept)
  logs         follow api / worker / scheduler logs
  ps           container status
  migrate      apply database migrations
  seed         (re)load the demo creator @curo.demo: replays 14 days of mocked collection
  learning     what CURO has learned about an account, e.g.  ./dev.ps1 learning curo.demo
  api-types    regenerate the web app's typed API client from the FastAPI schema
  time ...     move the clock, e.g.  ./dev.ps1 time advance 6h
  test         all tests (API tests, web type-check)
  lint         lint + format checks
  format       auto-format
  extract      unpack the prototype into reference/prototype
  screenshots  screenshot every prototype screen into reference/screens
  compare      (legacy Expo app) screenshot it and write reference/compare.html
  clean-db     DESTRUCTIVE: stop the stack and delete the local database volume

Without Docker (embedded Postgres, one process; see tools/local_stack.py):
  local        run the API, worker and scheduler (add --seed to load the demo first)
  local-seed   (re)load the demo creator @curo.demo
  local-time   move the clock, e.g.  ./dev.ps1 local-time advance 6h
"@
  }
  "env" { Ensure-Env }
  "setup" {
    Ensure-Env
    Invoke-Step { python -m venv .venv }
    Invoke-Step { & $Py -m pip install --upgrade pip }
    Invoke-Step { & $Py -m pip install -c api/constraints.txt -e "api[dev,localdb,tools]" -e worker }
    Push-Location web; try { Invoke-Step { npm install } } finally { Pop-Location }
  }
  "up" { Up }
  "dev" { Up; Push-Location web; try { npm run dev } finally { Pop-Location } }
  "web" { Push-Location web; try { npm run dev } finally { Pop-Location } }
  "app" { Push-Location web; try { npm run dev } finally { Pop-Location } }
  "down" { Invoke-Step { docker compose down } }
  "logs" { docker compose logs -f api worker scheduler }
  "ps" { docker compose ps }
  "migrate" { Invoke-Step { docker compose exec api python -m curo.db.migrate } }
  "seed" { Invoke-Step { docker compose exec api python -m curo.seed demo --reset } }
  "learning" { Invoke-Step { docker compose exec api python -m curo.learned @Rest } }
  "api-types" {
    Invoke-Step { & $Py tools/gen_openapi.py }
    Push-Location web; try { Invoke-Step { npm run gen:api } } finally { Pop-Location }
  }
  "time" { Invoke-Step { docker compose exec api python /repo/tools/timetravel.py @Rest } }
  "test" { & $PSCommandPath test-api; & $PSCommandPath test-app }
  "test-api" { Push-Location api; try { Invoke-Step { & $Py -m pytest @Rest } } finally { Pop-Location } }
  "test-app" {
    Push-Location web
    try { Invoke-Step { npm run typecheck } }
    finally { Pop-Location }
  }
  "lint" {
    Invoke-Step { & $Py -m ruff check api worker tools }
    Invoke-Step { & $Py -m ruff format --check api worker tools }
    Push-Location web; try { Invoke-Step { npm run typecheck } } finally { Pop-Location }
  }
  "format" {
    Invoke-Step { & $Py -m ruff check --fix api worker tools }
    Invoke-Step { & $Py -m ruff format api worker tools }
  }
  "extract" { Invoke-Step { & $Py tools/extract_prototype.py } }
  "screenshots" { Invoke-Step { & $Py tools/screenshot_prototype.py } }
  "compare" { Invoke-Step { & $Py tools/screenshot_app.py } }
  "clean-db" { Invoke-Step { docker compose down -v } }
  "local" { Invoke-Step { & $Py tools/local_stack.py up @Rest } }
  "local-seed" { Invoke-Step { & $Py tools/local_stack.py seed } }
  "local-time" {
    $env:REDIS_URL = "redis://127.0.0.1:6390/0"
    Invoke-Step { & $Py tools/timetravel.py @Rest }
  }
  default { throw "Unknown target '$Target'. Run ./dev.ps1 help" }
}
