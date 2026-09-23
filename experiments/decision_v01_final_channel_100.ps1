#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8080',
    [string]$Model = '',
    [string]$QuestionCsv = "$PSScriptRoot/results/decision_v01_final_channel_100.csv",
    [string]$OutputCsv = "$PSScriptRoot/results/decision_v01_final_channel_100_rerun_$(Get-Date -Format 'yyyyMMdd_HHmmss_fff').csv",
    [ValidateRange(1, 131072)][int]$MaxTokens = 4096
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Invoke-JsonPost($Path, $Body) {
    if ($Model) { $Body['model'] = $Model }
    $json = $Body | ConvertTo-Json -Depth 10 -Compress
    Invoke-RestMethod -Method Post -Uri ($BaseUrl.TrimEnd('/') + $Path) -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec 300
}

function Get-Median($Values) {
    $sorted = @($Values | Sort-Object)
    if ($sorted.Count -eq 0) { return $null }
    $middle = [int][Math]::Floor($sorted.Count / 2)
    if ($sorted.Count % 2) { return $sorted[$middle] }
    return ($sorted[$middle - 1] + $sorted[$middle]) / 2
}

if (Test-Path -LiteralPath $OutputCsv) { throw "Output already exists: $OutputCsv" }
if (-not (Test-Path -LiteralPath $QuestionCsv)) { throw "Missing original question CSV: $QuestionCsv" }
$questions = @(Import-Csv -LiteralPath $QuestionCsv)
if ($questions.Count -ne 100) { throw "Expected exactly 100 questions; found $($questions.Count)." }
$categories = @('facts', 'logic', 'negation', 'commonsense', 'technical')
foreach ($category in $categories) {
    $members = @($questions | Where-Object Category -eq $category)
    if ($members.Count -ne 20) { throw "Expected 20 questions in category '$category'." }
}
$ids = @($questions | Select-Object -ExpandProperty Index -Unique)
if ($ids.Count -ne 100) { throw 'Question indexes must be unique.' }
foreach ($q in $questions) {
    if ([string]::IsNullOrWhiteSpace($q.Question) -or $q.Truth -cnotin @('yes', 'no')) {
        throw "Invalid question or truth at index $($q.Index)."
    }
}

$results = @(foreach ($q in $questions) {
    Write-Host ("[{0}/100] {1}" -f $q.Index, $q.Question)
    $row = [ordered]@{
        Index = $q.Index; Category = $q.Category; Question = $q.Question; Truth = $q.Truth
        Decision = ''; DecisionCorrect = $false; YesProbability = $null; NoProbability = $null
        TemplateMs = $null; DecisionMs = $null; DecisionTotalMs = $null; DecisionTokens = 0
        Chat = ''; ChatCorrect = $false; ChatMs = $null; ChatTokens = $null
        ChatContent = ''; Agree = $null; DecisionError = ''; ChatError = ''
    }
    $messages = @(@{ role = 'user'; content = $q.Question })
    try {
        $total = [Diagnostics.Stopwatch]::StartNew()
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $template = Invoke-JsonPost '/apply-template' @{ messages = $messages }
        $timer.Stop()
        $row.TemplateMs = $timer.Elapsed.TotalMilliseconds
        if (-not ([string]$template.prompt).EndsWith('<|start|>assistant')) {
            throw 'Template must end exactly at <|start|>assistant; check the native GPT-OSS template.'
        }
        $prompt = $template.prompt + '<|channel|>final<|message|>'
        $timer.Restart()
        $decision = Invoke-JsonPost '/decision' @{ prompt = $prompt; choices = @('Yes', 'No') }
        $timer.Stop()
        $total.Stop()
        if (@($decision.choices).Count -ne 2 -or $decision.choices[0].text -cne 'Yes' -or $decision.choices[1].text -cne 'No') {
            throw 'Unexpected decision candidate response.'
        }
        $row.YesProbability = [double]$decision.choices[0].probability
        $row.NoProbability = [double]$decision.choices[1].probability
        $row.Decision = if ($row.YesProbability -ge $row.NoProbability) { 'yes' } else { 'no' }
        $row.DecisionCorrect = $row.Decision -eq $q.Truth
        $row.DecisionMs = $timer.Elapsed.TotalMilliseconds
        $row.DecisionTotalMs = $total.Elapsed.TotalMilliseconds
    } catch {
        $row.DecisionError = $_.Exception.Message
    }
    try {
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $chat = Invoke-JsonPost '/v1/chat/completions' @{ messages = $messages; temperature = 0; max_tokens = $MaxTokens; stream = $false }
        $timer.Stop()
        $row.ChatContent = [string]$chat.choices[0].message.content
        $row.ChatTokens = [int]$chat.usage.completion_tokens
        if ($chat.choices[0].finish_reason -ne 'stop') { throw "Chat did not finish normally: $($chat.choices[0].finish_reason)" }
        if ($row.ChatContent -notmatch '^\s*(?:\*\*)?(yes|no)\b') { throw 'Chat final content does not start with Yes or No.' }
        $row.Chat = $Matches[1].ToLowerInvariant()
        $row.ChatCorrect = $row.Chat -eq $q.Truth
        $row.ChatMs = $timer.Elapsed.TotalMilliseconds
    } catch {
        $row.ChatError = $_.Exception.Message
    }
    if (-not $row.DecisionError -and -not $row.ChatError) { $row.Agree = $row.Decision -eq $row.Chat }
    [pscustomobject]$row
})

if ($results.Count -ne 100) { throw "Expected exactly 100 results; found $($results.Count)." }
$outputDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($OutputCsv))
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$results | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8 -NoClobber

$summary = @(foreach ($category in @('all') + $categories) {
    $group = @($results | Where-Object { $category -eq 'all' -or $_.Category -eq $category })
    $directOk = @($group | Where-Object { -not $_.DecisionError })
    $chatOk = @($group | Where-Object { -not $_.ChatError })
    [pscustomobject]@{
        Category = $category; Questions = $group.Count
        DecisionCorrect = @($group | Where-Object DecisionCorrect).Count
        ChatCorrect = @($group | Where-Object ChatCorrect).Count
        DecisionAccuracyPct = 100 * @($group | Where-Object DecisionCorrect).Count / $group.Count
        ChatAccuracyPct = 100 * @($group | Where-Object ChatCorrect).Count / $group.Count
        DecisionMedianMs = Get-Median @($directOk | ForEach-Object { $_.DecisionTotalMs })
        ChatMedianMs = Get-Median @($chatOk | ForEach-Object { $_.ChatMs })
        DecisionErrors = $group.Count - $directOk.Count
        ChatErrors = $group.Count - $chatOk.Count
    }
})
$summary | Format-List | Out-Host
$disagreements = @($results | Where-Object { $_.Agree -eq $false })
Write-Host "Disagreements: $($disagreements.Count)"
$disagreements | Select-Object Index, Category, Question, Truth, Decision, Chat | Format-Table -AutoSize | Out-Host
$errors = @($results | Where-Object { $_.DecisionError -or $_.ChatError })
Write-Host "Rows with errors: $($errors.Count)"
$errors | Select-Object Index, DecisionError, ChatError | Format-List | Out-Host
$chatTokens = ($results | Measure-Object -Property ChatTokens -Sum).Sum
Write-Host "Completion tokens: direct = 0; chat = $chatTokens"
if ($summary[0].DecisionMedianMs -gt 0 -and $null -ne $summary[0].ChatMedianMs) {
    Write-Host ('Chat/direct median latency ratio: {0:N2}x' -f ($summary[0].ChatMedianMs / $summary[0].DecisionMedianMs))
}
Write-Host "Saved $($results.Count) results to $OutputCsv"
if ($errors.Count) { throw "Benchmark completed with errors in $($errors.Count) rows; see the saved CSV." }
