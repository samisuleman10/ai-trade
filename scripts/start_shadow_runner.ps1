$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$env:PYTHONPATH = 'src'

# This process requests read-only market data and writes local shadow records.
# It does not contain broker order, account, or position operations.
python -m ai_trade.shadow_runner --serve --port 7496
