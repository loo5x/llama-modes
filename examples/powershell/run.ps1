param(
    [ValidateSet('boolean', 'choice', 'scale', 'compare_direct_chat')][string]$Mode = 'boolean',
    [string]$Url = 'http://127.0.0.1:8080',
    [string]$Model = '',
    [int]$Timeout = 120
)
$ErrorActionPreference = 'Stop'
$name = if ($Mode -eq 'compare_direct_chat') { 'boolean' } else { $Mode }
$body = Get-Content -LiteralPath (Join-Path $PSScriptRoot "../requests/$name.json") -Raw | ConvertFrom-Json
if ($Model) { $body | Add-Member -NotePropertyName model -NotePropertyValue $Model }
function Invoke-Example($Endpoint, $Payload) {
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $data = [System.Text.Encoding]::UTF8.GetBytes(($Payload | ConvertTo-Json -Depth 20))
    $result = Invoke-RestMethod ($Url.TrimEnd('/') + $Endpoint) -Method Post -ContentType 'application/json' -Body $data -TimeoutSec $Timeout
    $timer.Stop()
    @{ endpoint = $Endpoint; latency_ms = $timer.Elapsed.TotalMilliseconds; response = $result } | ConvertTo-Json -Depth 30
}
$endpoint = if ($Mode -eq 'scale') { '/scale' } else { '/decision' }
Invoke-Example $endpoint $body
if ($Mode -eq 'compare_direct_chat') {
    Write-Host 'Interactive comparison: sequential. Direct generated tokens = 0 by design. Inspect chat final content, finish_reason, and usage.'
    $chat = @{ messages = $body.messages; temperature = 0; max_tokens = 1024; stream = $false }
    if ($Model) { $chat.model = $Model }
    Invoke-Example '/v1/chat/completions' $chat
}
