param([string]$Url = 'http://127.0.0.1:8080', [string]$Model = '', [int]$Timeout = 120)
& (Join-Path $PSScriptRoot 'run.ps1') -Mode 'compare_direct_chat' -Url $Url -Model $Model -Timeout $Timeout
