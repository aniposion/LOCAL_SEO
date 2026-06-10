param(
    [string]$BackendBase = "http://127.0.0.1:8000",
    [string]$ApiBase = "",
    [string]$AccessToken = "",
    [string]$Email = "",
    [string]$Password = "",
    [string]$LocationId = "",
    [ValidateSet("custom", "daily", "full")]
    [string]$Profile = "custom",
    [ValidateSet("never", "failures", "warnings", "always")]
    [string]$AlertOn = "failures",
    [ValidateSet("generic-json", "slack-text")]
    [string]$AlertWebhookFormat = "generic-json",
    [switch]$CheckOAuth,
    [switch]$CheckUpload,
    [switch]$CheckTwilio,
    [switch]$CheckStripe,
    [switch]$CheckPublish,
    [switch]$CheckAdmin,
    [switch]$CheckSalesFunnel,
    [string]$ContactTestEmail = "",
    [string]$AlertWebhookUrl = "",
    [string]$AlertRunbookUrl = "",
    [string]$RunLabel = "",
    [string]$OutputDir = "",
    [string]$SummaryPath = "",
    [string]$MarkdownSummaryPath = "",
    [switch]$FailOnAlertDelivery,
    [switch]$FailOnWarnings
)

$ErrorActionPreference = "Stop"
$script:Failures = New-Object System.Collections.Generic.List[string]
$script:Warnings = New-Object System.Collections.Generic.List[string]
$script:CheckResults = New-Object System.Collections.Generic.List[object]
$script:WebSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$script:AccessToken = $AccessToken

if (-not $PSBoundParameters.ContainsKey("BackendBase")) {
    $envBackendBase = [Environment]::GetEnvironmentVariable("LSO_SMOKE_BACKEND_BASE")
    if ($envBackendBase) {
        $BackendBase = $envBackendBase
    }
}

if (-not $PSBoundParameters.ContainsKey("ApiBase")) {
    $envApiBase = [Environment]::GetEnvironmentVariable("LSO_SMOKE_API_BASE")
    if ($envApiBase) {
        $ApiBase = $envApiBase
    }
}

if (-not $PSBoundParameters.ContainsKey("AccessToken")) {
    $envAccessToken = [Environment]::GetEnvironmentVariable("LSO_SMOKE_ACCESS_TOKEN")
    if ($envAccessToken) {
        $AccessToken = $envAccessToken
        $script:AccessToken = $envAccessToken
    }
}

if (-not $PSBoundParameters.ContainsKey("Email")) {
    $envEmail = [Environment]::GetEnvironmentVariable("LSO_SMOKE_EMAIL")
    if ($envEmail) {
        $Email = $envEmail
    }
}

if (-not $PSBoundParameters.ContainsKey("Password")) {
    $envPassword = [Environment]::GetEnvironmentVariable("LSO_SMOKE_PASSWORD")
    if ($envPassword) {
        $Password = $envPassword
    }
}

if (-not $PSBoundParameters.ContainsKey("LocationId")) {
    $envLocationId = [Environment]::GetEnvironmentVariable("LSO_SMOKE_LOCATION_ID")
    if ($envLocationId) {
        $LocationId = $envLocationId
    }
}

if (-not $PSBoundParameters.ContainsKey("ContactTestEmail")) {
    $envContactTestEmail = [Environment]::GetEnvironmentVariable("LSO_SMOKE_CONTACT_TEST_EMAIL")
    if ($envContactTestEmail) {
        $ContactTestEmail = $envContactTestEmail
    }
}

if (-not $PSBoundParameters.ContainsKey("CheckSalesFunnel")) {
    $envCheckSalesFunnel = [Environment]::GetEnvironmentVariable("LSO_SMOKE_CHECK_SALES_FUNNEL")
    if ($envCheckSalesFunnel -and $envCheckSalesFunnel -match "^(1|true|yes)$") {
        $CheckSalesFunnel = $true
    }
}

if (-not $PSBoundParameters.ContainsKey("AlertWebhookUrl")) {
    $envAlertWebhookUrl = [Environment]::GetEnvironmentVariable("LSO_SMOKE_ALERT_WEBHOOK_URL")
    if ($envAlertWebhookUrl) {
        $AlertWebhookUrl = $envAlertWebhookUrl
    }
}

if (-not $PSBoundParameters.ContainsKey("AlertRunbookUrl")) {
    $envAlertRunbookUrl = [Environment]::GetEnvironmentVariable("LSO_SMOKE_ALERT_RUNBOOK_URL")
    if ($envAlertRunbookUrl) {
        $AlertRunbookUrl = $envAlertRunbookUrl
    }
}

if (-not $PSBoundParameters.ContainsKey("AlertOn")) {
    $envAlertOn = [Environment]::GetEnvironmentVariable("LSO_SMOKE_ALERT_ON")
    if ($envAlertOn -and $envAlertOn -in @("never", "failures", "warnings", "always")) {
        $AlertOn = $envAlertOn
    }
}

if (-not $PSBoundParameters.ContainsKey("AlertWebhookFormat")) {
    $envAlertWebhookFormat = [Environment]::GetEnvironmentVariable("LSO_SMOKE_ALERT_WEBHOOK_FORMAT")
    if ($envAlertWebhookFormat -and $envAlertWebhookFormat -in @("generic-json", "slack-text")) {
        $AlertWebhookFormat = $envAlertWebhookFormat
    }
}

switch ($Profile) {
    "daily" {
        $CheckOAuth = $true
        $CheckPublish = $true
        $CheckAdmin = $true
        $CheckSalesFunnel = $true
    }
    "full" {
        $CheckOAuth = $true
        $CheckUpload = $true
        $CheckTwilio = $true
        $CheckStripe = $true
        $CheckPublish = $true
        $CheckAdmin = $true
        $CheckSalesFunnel = $true
        $FailOnWarnings = $true
    }
}

$BackendBase = $BackendBase.TrimEnd("/")
if (-not $ApiBase) {
    $ApiBase = $BackendBase
}
$ApiBase = $ApiBase.TrimEnd("/")

if (-not $RunLabel) {
    $RunLabel = "{0}-{1}" -f $Profile, (Get-Date -Format "yyyyMMdd-HHmmss")
}

if (-not $OutputDir -and $Profile -ne "custom") {
    $OutputDir = Join-Path $PSScriptRoot "..\artifacts\smoke-reports"
}

if ($OutputDir) {
    $resolvedOutputDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputDir))
    [System.IO.Directory]::CreateDirectory($resolvedOutputDir) | Out-Null
    $OutputDir = $resolvedOutputDir

    if (-not $SummaryPath) {
        $SummaryPath = Join-Path $OutputDir "$RunLabel.json"
    }
    if (-not $MarkdownSummaryPath) {
        $MarkdownSummaryPath = Join-Path $OutputDir "$RunLabel.md"
    }
}

function Write-Step($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor Cyan
}

function Get-AuthMode() {
    if ($script:AccessToken) {
        return "access-token"
    }
    if ($Email -and $Password) {
        return "email-password session"
    }
    return "health-only"
}

function Mask-Secret([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value)) {
        return ""
    }
    if ($value.Length -le 6) {
        return ("*" * $value.Length)
    }
    return "{0}{1}" -f $value.Substring(0, 3), ("*" * ($value.Length - 3))
}

function Join-Url([string]$base, [string]$path) {
    if ($path.StartsWith("/")) {
        return "$base$path"
    }
    return "$base/$path"
}

function Get-ErrorMessage($errorRecord) {
    if ($errorRecord.ErrorDetails -and $errorRecord.ErrorDetails.Message) {
        return $errorRecord.ErrorDetails.Message
    }
    if ($errorRecord.Exception -and $errorRecord.Exception.Message) {
        return $errorRecord.Exception.Message
    }
    return [string]$errorRecord
}

function Get-StatusCode($errorRecord) {
    $response = $errorRecord.Exception.Response
    if (-not $response) {
        return $null
    }

    try {
        return [int]$response.StatusCode
    } catch {
        try {
            return [int]$response.StatusCode.value__
        } catch {
            return $null
        }
    }
}

function Test-IsUnauthorized($errorRecord) {
    $statusCode = Get-StatusCode $errorRecord
    if ($statusCode -eq 401) {
        return $true
    }
    return (Get-ErrorMessage $errorRecord) -like "HTTP 401*"
}

function Get-AuthHeaders() {
    $headers = @{}
    if ($script:AccessToken) {
        $headers["Authorization"] = "Bearer $($script:AccessToken)"
    }
    return $headers
}

function Invoke-JsonRequestInternal([string]$Method, [string]$Url, [object]$Body = $null) {
    $headers = Get-AuthHeaders

    if ($null -ne $Body) {
        $payload = if ($Body -is [string]) {
            $Body
        } else {
            $Body | ConvertTo-Json -Depth 10 -Compress
        }

        return Invoke-RestMethod `
            -Method $Method `
            -Uri $Url `
            -Headers $headers `
            -WebSession $script:WebSession `
            -ContentType "application/json" `
            -Body $payload
    }

    return Invoke-RestMethod `
        -Method $Method `
        -Uri $Url `
        -Headers $headers `
        -WebSession $script:WebSession
}

function Try-Refresh-AccessToken() {
    try {
        $response = Invoke-RestMethod `
            -Method Post `
            -Uri (Join-Url $ApiBase "/auth/refresh") `
            -WebSession $script:WebSession

        if ($response -and $response.access_token) {
            $script:AccessToken = [string]$response.access_token
            Write-Host "Session refresh succeeded." -ForegroundColor DarkGreen
            return $true
        }
    } catch {
        Write-Host "Session refresh failed: $(Get-ErrorMessage $_)" -ForegroundColor Yellow
    }

    return $false
}

function Invoke-JsonRequest([string]$Method, [string]$Url, [object]$Body = $null, [switch]$AllowRefresh) {
    try {
        return Invoke-JsonRequestInternal -Method $Method -Url $Url -Body $Body
    } catch {
        if ($AllowRefresh -and (Test-IsUnauthorized $_) -and (Try-Refresh-AccessToken)) {
            return Invoke-JsonRequestInternal -Method $Method -Url $Url -Body $Body
        }
        throw
    }
}

function Invoke-JsonGet([string]$Url, [switch]$AllowRefresh) {
    return Invoke-JsonRequest -Method Get -Url $Url -AllowRefresh:$AllowRefresh
}

function Invoke-JsonPost([string]$Url, [object]$Body = $null, [switch]$AllowRefresh) {
    return Invoke-JsonRequest -Method Post -Url $Url -Body $Body -AllowRefresh:$AllowRefresh
}

function Invoke-JsonDelete([string]$Url, [switch]$AllowRefresh) {
    return Invoke-JsonRequest -Method Delete -Url $Url -AllowRefresh:$AllowRefresh
}

function Invoke-FileUploadInternal(
    [string]$Url,
    [string]$FilePath,
    [string]$ContentType = "text/plain",
    [string]$FieldName = "file"
) {
    $handler = $null
    $client = $null
    $content = $null
    $fileContent = $null

    try {
        $handler = [System.Net.Http.HttpClientHandler]::new()
        $handler.CookieContainer = $script:WebSession.Cookies
        $client = [System.Net.Http.HttpClient]::new($handler)

        if ($script:AccessToken) {
            $client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new(
                "Bearer",
                $script:AccessToken
            )
        }

        $content = [System.Net.Http.MultipartFormDataContent]::new()
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        $fileContent = [System.Net.Http.ByteArrayContent]::new($bytes)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse($ContentType)
        $content.Add($fileContent, $FieldName, [System.IO.Path]::GetFileName($FilePath))

        $response = $client.PostAsync($Url, $content).GetAwaiter().GetResult()
        $payload = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()

        if (-not $response.IsSuccessStatusCode) {
            throw "HTTP $([int]$response.StatusCode) $($response.ReasonPhrase): $payload"
        }

        if ([string]::IsNullOrWhiteSpace($payload)) {
            return $null
        }

        return $payload | ConvertFrom-Json
    } finally {
        if ($null -ne $fileContent) {
            $fileContent.Dispose()
        }
        if ($null -ne $content) {
            $content.Dispose()
        }
        if ($null -ne $client) {
            $client.Dispose()
        }
        if ($null -ne $handler) {
            $handler.Dispose()
        }
    }
}

function Invoke-FileUpload(
    [string]$Url,
    [string]$FilePath,
    [string]$ContentType = "text/plain",
    [string]$FieldName = "file",
    [switch]$AllowRefresh
) {
    try {
        return Invoke-FileUploadInternal -Url $Url -FilePath $FilePath -ContentType $ContentType -FieldName $FieldName
    } catch {
        if ($AllowRefresh -and (Test-IsUnauthorized $_) -and (Try-Refresh-AccessToken)) {
            return Invoke-FileUploadInternal -Url $Url -FilePath $FilePath -ContentType $ContentType -FieldName $FieldName
        }
        throw
    }
}

function Login-WithPassword() {
    if (-not $Email -or -not $Password) {
        throw "Email and Password are required for session login."
    }

    $response = Invoke-JsonPost `
        -Url (Join-Url $ApiBase "/auth/login") `
        -Body @{ email = $Email; password = $Password }

    if (-not $response.access_token) {
        throw "Login succeeded but no access token was returned."
    }

    $script:AccessToken = [string]$response.access_token
    return $response
}

function Assert-CloudBackedUploadUrl([string]$Url) {
    $targetUri = [uri]$Url
    $backendUri = [uri]$BackendBase
    $apiUri = [uri]$ApiBase

    if (($targetUri.Host -eq $backendUri.Host -or $targetUri.Host -eq $apiUri.Host) -and $targetUri.AbsolutePath -like "/uploads/*") {
        throw "Upload URL still points to the backend local uploads path: $Url"
    }
}

function New-TempSmokeDocument() {
    $tempPath = [System.IO.Path]::Combine(
        [System.IO.Path]::GetTempPath(),
        ("lso-smoke-{0}.txt" -f [guid]::NewGuid().ToString("N"))
    )
    [System.IO.File]::WriteAllText(
        $tempPath,
        ("Local SEO Optimizer smoke test {0}" -f (Get-Date).ToString("s"))
    )
    return $tempPath
}

function Add-CheckResult(
    [string]$Label,
    [string]$Status,
    [string]$Detail = "",
    [bool]$Optional = $false
) {
    $script:CheckResults.Add(
        [pscustomobject]@{
            label = $Label
            status = $Status
            detail = $Detail
            optional = $Optional
            recorded_at = (Get-Date).ToString("o")
        }
    ) | Out-Null
}

function Get-OverallStatus() {
    if ($script:Failures.Count -gt 0) {
        return "failed"
    }
    if ($script:Warnings.Count -gt 0) {
        return "warning"
    }
    return "passed"
}

function Get-SmokeIssueText() {
    $parts = New-Object System.Collections.Generic.List[string]

    foreach ($failure in $script:Failures) {
        $parts.Add([string]$failure)
    }
    foreach ($warning in $script:Warnings) {
        $parts.Add([string]$warning)
    }
    foreach ($check in $script:CheckResults | Where-Object { $_.status -ne "passed" }) {
        if ($check.label) {
            $parts.Add([string]$check.label)
        }
        if ($check.detail) {
            $parts.Add([string]$check.detail)
        }
    }

    return ($parts -join "`n")
}

function Get-NextActions() {
    $actions = New-Object System.Collections.Generic.List[string]
    $issueText = Get-SmokeIssueText

    if ($MarkdownSummaryPath) {
        $actions.Add("Review markdown summary: $MarkdownSummaryPath")
    } elseif ($SummaryPath) {
        $actions.Add("Review JSON summary: $SummaryPath")
    }

    if ($issueText -match "(?i)readyz|billing|dunning|invoice|stripe") {
        $actions.Add("Check billing readiness, Stripe configuration, and dunning recovery state.")
    }

    if ($issueText -match "(?i)oauth|google|instagram|token") {
        $actions.Add("Verify OAuth tokens, redirect URIs, and provider connection health.")
    }

    if ($issueText -match "(?i)publish|operations-feed|notifications|review booster") {
        $actions.Add("Review /admin operations feed and /posts/publish-issues for actionable follow-up.")
    }

    if ($issueText -match "(?i)upload|storage|document") {
        $actions.Add("Verify cloud storage configuration and upload/delete permissions.")
    }

    if ($AlertRunbookUrl) {
        $actions.Add("Runbook: $AlertRunbookUrl")
    }

    return @($actions | Select-Object -Unique)
}

function New-SmokeSummary() {
    return [ordered]@{
        run_label = $RunLabel
        profile = $Profile
        overall_status = Get-OverallStatus
        backend_base = $BackendBase
        api_base = $ApiBase
        auth_mode = Get-AuthMode
        location_id = $LocationId
        checks_enabled = [ordered]@{
            oauth = $CheckOAuth.IsPresent
            upload = $CheckUpload.IsPresent
            twilio = $CheckTwilio.IsPresent
            stripe = $CheckStripe.IsPresent
            publish = $CheckPublish.IsPresent
            admin = $CheckAdmin.IsPresent
            sales_funnel = $CheckSalesFunnel.IsPresent
            fail_on_warnings = $FailOnWarnings.IsPresent
        }
        report_paths = [ordered]@{
            output_dir = $OutputDir
            json = $SummaryPath
            markdown = $MarkdownSummaryPath
        }
        alert = [ordered]@{
            webhook_configured = -not [string]::IsNullOrWhiteSpace($AlertWebhookUrl)
            alert_on = $AlertOn
            format = $AlertWebhookFormat
            runbook_url = $AlertRunbookUrl
            fail_on_delivery = $FailOnAlertDelivery.IsPresent
        }
        next_actions = @(Get-NextActions)
        checks = @($script:CheckResults)
        failures = @($script:Failures)
        warnings = @($script:Warnings)
        counts = [ordered]@{
            total_checks = $script:CheckResults.Count
            passed = @($script:CheckResults | Where-Object { $_.status -eq "passed" }).Count
            failed = @($script:CheckResults | Where-Object { $_.status -eq "failed" }).Count
            optional_failed = @($script:CheckResults | Where-Object { $_.status -eq "optional_failed" }).Count
            warnings = $script:Warnings.Count
        }
        completed_at = (Get-Date).ToString("o")
    }
}

function Write-SmokeArtifacts() {
    if (-not $SummaryPath -and -not $MarkdownSummaryPath) {
        return
    }

    $summary = New-SmokeSummary

    if ($SummaryPath) {
        $json = $summary | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($SummaryPath, $json, [System.Text.UTF8Encoding]::new($false))
        Write-Host "JSON summary: $SummaryPath" -ForegroundColor DarkCyan
    }

    if ($MarkdownSummaryPath) {
        $lines = New-Object System.Collections.Generic.List[string]
        $lines.Add("# Smoke Test Summary")
        $lines.Add("")
        $lines.Add("- Run label: ``$RunLabel``")
        $lines.Add("- Profile: ``$Profile``")
        $lines.Add("- Overall status: ``$($summary.overall_status)``")
        $lines.Add("- Backend base: ``$BackendBase``")
        $lines.Add("- API base: ``$ApiBase``")
        $lines.Add("- Location id: ``$(if ($LocationId) { $LocationId } else { 'not-set' })``")
        $lines.Add("- Completed at: ``$($summary.completed_at)``")
        $lines.Add("- Alert webhook configured: ``$($summary.alert.webhook_configured)``")
        $lines.Add("- Alert mode: ``$($summary.alert.alert_on)``")
        $lines.Add("- Alert format: ``$($summary.alert.format)``")
        $lines.Add("")
        $lines.Add("## Counts")
        $lines.Add("")
        $lines.Add("- Passed: $($summary.counts.passed)")
        $lines.Add("- Failed: $($summary.counts.failed)")
        $lines.Add("- Optional failed: $($summary.counts.optional_failed)")
        $lines.Add("- Warnings: $($summary.counts.warnings)")
        $lines.Add("")

        if ($summary.next_actions.Count -gt 0) {
            $lines.Add("## Next Actions")
            $lines.Add("")
            foreach ($action in $summary.next_actions) {
                $lines.Add("- $action")
            }
            $lines.Add("")
        }

        if ($script:Failures.Count -gt 0) {
            $lines.Add("## Failures")
            $lines.Add("")
            foreach ($failure in $script:Failures) {
                $lines.Add("- $failure")
            }
            $lines.Add("")
        }

        if ($script:Warnings.Count -gt 0) {
            $lines.Add("## Warnings")
            $lines.Add("")
            foreach ($warning in $script:Warnings) {
                $lines.Add("- $warning")
            }
            $lines.Add("")
        }

        $lines.Add("## Checks")
        $lines.Add("")
        foreach ($check in $script:CheckResults) {
            $line = "- [{0}] {1}" -f $check.status, $check.label
            if ($check.detail) {
                $line = "$line - $($check.detail)"
            }
            $lines.Add($line)
        }

        [System.IO.File]::WriteAllLines($MarkdownSummaryPath, $lines, [System.Text.UTF8Encoding]::new($false))
        Write-Host "Markdown summary: $MarkdownSummaryPath" -ForegroundColor DarkCyan
    }
}

function Test-ShouldSendAlert([string]$OverallStatus) {
    if ([string]::IsNullOrWhiteSpace($AlertWebhookUrl)) {
        return $false
    }

    switch ($AlertOn) {
        "never" { return $false }
        "failures" { return $OverallStatus -eq "failed" }
        "warnings" { return $OverallStatus -in @("failed", "warning") }
        "always" { return $true }
    }

    return $false
}

function New-SmokeAlertPayload([string]$OverallStatus) {
    $summary = New-SmokeSummary
    $headline = "[LSO smoke] {0} ({1})" -f $OverallStatus.ToUpperInvariant(), $RunLabel
    $nextActions = @($summary.next_actions)

    if ($AlertWebhookFormat -eq "slack-text") {
        $lines = New-Object System.Collections.Generic.List[string]
        $lines.Add($headline)
        $lines.Add("Profile: $Profile")
        $lines.Add("Backend: $BackendBase")
        $lines.Add(
            "Counts: passed=$($summary.counts.passed), failed=$($summary.counts.failed), optional_failed=$($summary.counts.optional_failed), warnings=$($summary.counts.warnings)"
        )
        if ($script:Failures.Count -gt 0) {
            $lines.Add("Failures: $(@($script:Failures) -join ', ')")
        }
        if ($script:Warnings.Count -gt 0) {
            $lines.Add("Warnings: $(@($script:Warnings) -join ', ')")
        }
        foreach ($action in $nextActions) {
            $lines.Add("Next: $action")
        }

        return [ordered]@{
            text = ($lines -join "`n")
        }
    }

    return [ordered]@{
        headline = $headline
        overall_status = $OverallStatus
        run_label = $RunLabel
        profile = $Profile
        backend_base = $BackendBase
        api_base = $ApiBase
        report_paths = $summary.report_paths
        counts = $summary.counts
        failures = @($script:Failures)
        warnings = @($script:Warnings)
        next_actions = $nextActions
    }
}

function Send-SmokeAlert() {
    $overallStatus = Get-OverallStatus
    if (-not (Test-ShouldSendAlert -OverallStatus $overallStatus)) {
        return
    }

    try {
        $payload = New-SmokeAlertPayload -OverallStatus $overallStatus | ConvertTo-Json -Depth 10
        Invoke-RestMethod `
            -Method Post `
            -Uri $AlertWebhookUrl `
            -ContentType "application/json" `
            -Body $payload | Out-Null

        Write-Host "Smoke alert sent." -ForegroundColor DarkGreen
        Add-CheckResult -Label "POST smoke alert webhook" -Status "passed" -Detail "$overallStatus -> $AlertWebhookFormat"
    } catch {
        $message = Get-ErrorMessage $_
        Write-Host "Smoke alert delivery failed: $message" -ForegroundColor Yellow

        if ($FailOnAlertDelivery) {
            $script:Failures.Add("smoke-alert-webhook") | Out-Null
            Add-CheckResult -Label "POST smoke alert webhook" -Status "failed" -Detail $message -Optional:$false
        } else {
            $script:Warnings.Add("smoke alert delivery failed: $message") | Out-Null
            Add-CheckResult -Label "POST smoke alert webhook" -Status "optional_failed" -Detail $message -Optional:$true
        }
    }
}

function Complete-SmokeRun([int]$ExitCode, [string]$SuccessMessage = "Smoke test finished successfully.") {
    Send-SmokeAlert

    $finalExitCode = if ($script:Failures.Count -gt 0) { 1 } else { $ExitCode }
    Write-Host ""

    if ($script:Failures.Count -gt 0) {
        Write-Host "Smoke test finished with failures:" -ForegroundColor Red
        foreach ($failure in $script:Failures) {
            Write-Host "- $failure" -ForegroundColor Red
        }

        if ($script:Warnings.Count -gt 0) {
            Write-Host ""
            Write-Host "Warnings observed:" -ForegroundColor Yellow
            foreach ($warning in $script:Warnings) {
                Write-Host "- $warning" -ForegroundColor Yellow
            }
        }
    } elseif ($script:Warnings.Count -gt 0) {
        Write-Host "Smoke test finished with warnings:" -ForegroundColor Yellow
        foreach ($warning in $script:Warnings) {
            Write-Host "- $warning" -ForegroundColor Yellow
        }
    } else {
        Write-Host $SuccessMessage -ForegroundColor Green
    }

    Write-SmokeArtifacts

    if ($script:CheckResults.Count -gt 0) {
        $summary = New-SmokeSummary
        Write-Host (
            "Check counts: passed={0}, failed={1}, optional_failed={2}, warnings={3}" -f
            $summary.counts.passed,
            $summary.counts.failed,
            $summary.counts.optional_failed,
            $summary.counts.warnings
        )
    }

    exit $finalExitCode
}

function Run-Check([string]$Label, [scriptblock]$Action, [switch]$Optional) {
    try {
        $result = & $Action
        Write-Host "$Label OK" -ForegroundColor Green
        Add-CheckResult -Label $Label -Status "passed" -Optional:$Optional.IsPresent
        return $result
    } catch {
        $message = Get-ErrorMessage $_

        if ($Optional) {
            Write-Host "$Label skipped/failed: $message" -ForegroundColor Yellow
            Add-CheckResult -Label $Label -Status "optional_failed" -Detail $message -Optional:$true
        } else {
            Write-Host "$Label failed: $message" -ForegroundColor Red
            $script:Failures.Add($Label) | Out-Null
            Add-CheckResult -Label $Label -Status "failed" -Detail $message -Optional:$false
        }
        return $null
    }
}

Write-Step "Configuration"
Write-Host "BackendBase: $BackendBase"
Write-Host "ApiBase:     $ApiBase"
Write-Host "Profile:     $Profile"
Write-Host "RunLabel:    $RunLabel"
Write-Host "AuthMode:    $(Get-AuthMode)"
Write-Host "Email:       $(if ($Email) { Mask-Secret $Email } else { 'not-set' })"
Write-Host "Token:       $(if ($script:AccessToken) { Mask-Secret $script:AccessToken } else { 'not-set' })"
Write-Host "OutputDir:   $(if ($OutputDir) { $OutputDir } else { 'disabled' })"
Write-Host "SummaryPath: $(if ($SummaryPath) { $SummaryPath } else { 'disabled' })"
Write-Host "Markdown:    $(if ($MarkdownSummaryPath) { $MarkdownSummaryPath } else { 'disabled' })"
Write-Host "Alert hook:  $(if ($AlertWebhookUrl) { Mask-Secret $AlertWebhookUrl } else { 'disabled' })"
Write-Host "Alert mode:  $AlertOn"
Write-Host "Alert fmt:   $AlertWebhookFormat"
Write-Host "Runbook:     $(if ($AlertRunbookUrl) { $AlertRunbookUrl } else { 'not-set' })"
Write-Host "OAuth check: $($CheckOAuth.IsPresent)"
Write-Host "Upload check:$($CheckUpload.IsPresent)"
Write-Host "Twilio check:$($CheckTwilio.IsPresent)"
Write-Host "Stripe check:$($CheckStripe.IsPresent)"
Write-Host "Publish check:$($CheckPublish.IsPresent)"
Write-Host "Admin check: $($CheckAdmin.IsPresent)"
Write-Host "Sales check: $($CheckSalesFunnel.IsPresent)"
Write-Host "Contact smoke email: $(if ($ContactTestEmail) { Mask-Secret $ContactTestEmail } else { 'not-set' })"
Write-Host "Fail warn:   $($FailOnWarnings.IsPresent)"
Write-Host "Fail alert:  $($FailOnAlertDelivery.IsPresent)"

Write-Step "Health checks"
$health = Run-Check "GET /healthz" {
    Invoke-RestMethod -Method Get -Uri (Join-Url $BackendBase "/healthz")
}
$ready = Run-Check "GET /readyz" {
    Invoke-RestMethod -Method Get -Uri (Join-Url $BackendBase "/readyz")
}

if ($ready -and $ready.status -ne "ready") {
    Write-Host "readyz returned non-ready status: $($ready.status)" -ForegroundColor Red
    $script:Failures.Add("readyz-status") | Out-Null
}

if ($ready -and $ready.warnings) {
    foreach ($warning in $ready.warnings) {
        $script:Warnings.Add([string]$warning) | Out-Null
        Write-Host "readyz warning: $warning" -ForegroundColor Yellow
    }
}

if ($FailOnWarnings -and $script:Warnings.Count -gt 0) {
    $script:Failures.Add("readyz-warnings") | Out-Null
}

if ($CheckSalesFunnel) {
    Write-Step "Public sales funnel checks"

    $null = Run-Check "GET /api/v1/healthz alias" {
        Invoke-RestMethod -Method Get -Uri (Join-Url $BackendBase "/api/v1/healthz")
    }

    $null = Run-Check "POST /contact/requests validation" {
        try {
            Invoke-RestMethod `
                -Method Post `
                -Uri (Join-Url $ApiBase "/contact/requests") `
                -ContentType "application/json" `
                -Body (@{
                    name = "LSO Smoke Validation"
                    email = "invalid@example.com"
                    message = "hey"
                    source = "smoke_validation"
                } | ConvertTo-Json -Compress) | Out-Null

            throw "Contact validation accepted a message that should be too short."
        } catch {
            $statusCode = Get-StatusCode $_
            if ($statusCode -eq 422) {
                return @{ validation = "passed" }
            }
            throw
        }
    }

    if ($ContactTestEmail) {
        $null = Run-Check "POST /contact/requests smoke lead" {
            try {
                $response = Invoke-RestMethod `
                    -Method Post `
                    -Uri (Join-Url $ApiBase "/contact/requests") `
                    -ContentType "application/json" `
                    -Body (@{
                        name = "LSO Smoke Test"
                        email = $ContactTestEmail
                        subject = "Managed pilot smoke test"
                        message = "Automated smoke test for the public managed-pilot contact path. This confirms the request is persisted and prioritized."
                        business_name = "LSO Smoke Test"
                        source = "smoke_test"
                        metadata = @{
                            run_label = $RunLabel
                            smoke_test = $true
                        }
                    } | ConvertTo-Json -Depth 10 -Compress)

                if ($null -eq $response.lead_score -or -not $response.recommended_package) {
                    throw "Contact smoke response did not include lead_score and recommended_package."
                }
                return $response
            } catch {
                $statusCode = Get-StatusCode $_
                if ($statusCode -eq 429) {
                    return @{ duplicate_window = "accepted" }
                }
                throw
            }
        }
    }
}

if (-not $script:AccessToken -and $Email -and $Password) {
    Write-Step "Authentication"
    $null = Run-Check "POST /auth/login" {
        Login-WithPassword
    }

    if ($script:AccessToken) {
        $null = Run-Check "POST /auth/refresh (session cookie)" {
            $response = Invoke-JsonPost -Url (Join-Url $ApiBase "/auth/refresh")
            if (-not $response.access_token) {
                throw "Refresh succeeded but no access token was returned."
            }
            $script:AccessToken = [string]$response.access_token
            return $response
        }
    }
}

if (-not $script:AccessToken) {
    Write-Host ""
    Write-Host "No AccessToken or login credentials provided. Stopping after unauthenticated checks." -ForegroundColor Yellow
    if ($script:Failures.Count -gt 0) {
        Complete-SmokeRun -ExitCode 1 -SuccessMessage "Smoke test finished after unauthenticated checks."
    }
    Complete-SmokeRun -ExitCode 0 -SuccessMessage "Smoke test finished after unauthenticated checks."
}

Write-Step "Authenticated smoke"
$null = Run-Check "GET /auth/me" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/auth/me") -AllowRefresh
}

$locationItems = Run-Check "GET /locations" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/locations") -AllowRefresh
}

if ($locationItems -and $locationItems.Count -gt 0 -and -not $LocationId) {
    $LocationId = [string]$locationItems[0].id
    Write-Host "Using first location from /locations: $LocationId"
}

$null = Run-Check "GET /billing/subscription" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/subscription") -AllowRefresh
}

$null = Run-Check "GET /billing/dunning-status" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/dunning-status") -AllowRefresh
}

$null = Run-Check "GET /billing/usage" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/usage") -AllowRefresh
}

$null = Run-Check "GET /billing/credits" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/credits") -AllowRefresh
}

if ($CheckStripe) {
    $null = Run-Check "GET /billing/invoices" {
        $response = Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/invoices?limit=5") -AllowRefresh
        if ($null -eq $response.total_count) {
            throw "Invoices response did not include total_count."
        }
        return $response
    }

    $null = Run-Check "GET /billing/payment-methods" {
        Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/payment-methods") -AllowRefresh
    }

    $null = Run-Check "GET /billing/audit" {
        $response = Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/audit?limit=5") -AllowRefresh
        if ($null -eq $response.total) {
            throw "Billing audit response did not include a total."
        }
        return $response
    }

    $null = Run-Check "GET /billing/webhook-events" {
        $response = Invoke-JsonGet -Url (Join-Url $ApiBase "/billing/webhook-events?limit=5") -AllowRefresh
        if ($null -eq $response.total) {
            throw "Billing webhook events response did not include a total."
        }
        return $response
    }
}

$null = Run-Check "GET /usage/summary" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/usage/summary") -AllowRefresh
}

$null = Run-Check "GET /usage/limits" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/usage/limits") -AllowRefresh
}

$null = Run-Check "GET /usage/credits" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/usage/credits") -AllowRefresh
}

$null = Run-Check "GET /notifications/preferences" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/notifications/preferences") -AllowRefresh
}

$null = Run-Check "GET /notifications/health-summary" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/notifications/health-summary") -AllowRefresh
}

$null = Run-Check "GET /oauth/status" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/oauth/status") -AllowRefresh
}

$null = Run-Check "GET /oauth/tokens" {
    Invoke-JsonGet -Url (Join-Url $ApiBase "/oauth/tokens") -AllowRefresh
}

if ($CheckAdmin) {
    $null = Run-Check "GET /admin/recovery-queue" {
        $response = Invoke-JsonGet -Url (Join-Url $ApiBase "/admin/recovery-queue?limit=5") -AllowRefresh
        if ($null -eq $response.action_required_total) {
            throw "Recovery queue response did not include action_required_total."
        }
        return $response
    }

    $null = Run-Check "GET /admin/operations-feed" {
        $response = Invoke-JsonGet -Url (Join-Url $ApiBase "/admin/operations-feed?limit=10") -AllowRefresh
        if ($null -eq $response.total) {
            throw "Operations feed response did not include a total."
        }
        return $response
    }

    if ($CheckSalesFunnel) {
        $null = Run-Check "GET /contact/requests admin sales queue" {
            $response = Invoke-JsonGet -Url (Join-Url $ApiBase "/contact/requests?status=new&limit=5") -AllowRefresh
            if ($null -eq $response.total -or $null -eq $response.requests) {
                throw "Contact requests response did not include total/requests."
            }
            return $response
        }
    }
}

if ($CheckPublish) {
    $publishIssuesUrl = Join-Url $ApiBase "/posts/publish-issues?limit=5"
    if ($LocationId) {
        $publishIssuesUrl = Join-Url $ApiBase "/posts/publish-issues?location_id=$([uri]::EscapeDataString($LocationId))&limit=5"
    }

    $null = Run-Check "GET /posts/publish-issues" {
        $response = Invoke-JsonGet -Url $publishIssuesUrl -AllowRefresh
        if ($null -eq $response.total) {
            throw "Publish issues response did not include a total."
        }
        if ($null -eq $response.failed -or $null -eq $response.retrying) {
            throw "Publish issues response did not include failed/retrying counters."
        }
        return $response
    }
}

if ($LocationId) {
    $encodedLocationId = [uri]::EscapeDataString($LocationId)

    $null = Run-Check "GET /metrics/dashboard?location_id=..." {
        Invoke-JsonGet -Url (Join-Url $ApiBase "/metrics/dashboard?location_id=$encodedLocationId") -AllowRefresh
    }

    $null = Run-Check "GET /locations/{id}/channels" {
        Invoke-JsonGet -Url (Join-Url $ApiBase "/locations/$LocationId/channels") -AllowRefresh
    }

    $null = Run-Check "GET /qa/{id}" {
        Invoke-JsonGet -Url (Join-Url $ApiBase "/qa/$LocationId") -AllowRefresh
    } -Optional

    if ($CheckTwilio) {
        $null = Run-Check "GET /calls/{id}/settings" {
            Invoke-JsonGet -Url (Join-Url $ApiBase "/calls/$LocationId/settings") -AllowRefresh
        }
    }

    if ($CheckOAuth) {
        $googleRedirectUri = [uri]::EscapeDataString((Join-Url $ApiBase "/oauth/google/callback"))
        $instagramRedirectUri = [uri]::EscapeDataString((Join-Url $ApiBase "/oauth/instagram/callback"))

        $null = Run-Check "GET /oauth/google/authorize" {
            $response = Invoke-JsonGet -Url (
                Join-Url $ApiBase "/oauth/google/authorize?location_id=$encodedLocationId&redirect_uri=$googleRedirectUri"
            ) -AllowRefresh
            if (-not $response.authorization_url) {
                throw "Google authorize endpoint returned no authorization_url."
            }
            return $response
        }

        $null = Run-Check "GET /oauth/instagram/authorize" {
            $response = Invoke-JsonGet -Url (
                Join-Url $ApiBase "/oauth/instagram/authorize?location_id=$encodedLocationId&redirect_uri=$instagramRedirectUri"
            ) -AllowRefresh
            if (-not $response.authorization_url) {
                throw "Instagram authorize endpoint returned no authorization_url."
            }
            return $response
        }
    }
} else {
    Write-Host "No location id available. Skipping location-scoped checks." -ForegroundColor Yellow
}

if ($CheckUpload) {
    $tempDocument = New-TempSmokeDocument
    $uploadedDocument = $null

    try {
        $uploadedDocument = Run-Check "POST /uploads/document" {
            $response = Invoke-FileUpload `
                -Url (Join-Url $ApiBase "/uploads/document") `
                -FilePath $tempDocument `
                -ContentType "text/plain" `
                -AllowRefresh

            if (-not $response.id -or -not $response.url) {
                throw "Upload response did not include an id/url."
            }

            Assert-CloudBackedUploadUrl $response.url
            return $response
        }

        if ($uploadedDocument -and $uploadedDocument.id) {
            $null = Run-Check "DELETE /uploads/{id}?file_type=document" {
                Invoke-JsonDelete -Url (
                    Join-Url $ApiBase "/uploads/$($uploadedDocument.id)?file_type=document"
                ) -AllowRefresh
            }
        }
    } finally {
        if (Test-Path $tempDocument) {
            Remove-Item -LiteralPath $tempDocument -Force
        }
    }
}

if ($Email -and $Password) {
    $null = Run-Check "POST /auth/logout" {
        $response = Invoke-JsonPost -Url (Join-Url $ApiBase "/auth/logout") -AllowRefresh
        $script:AccessToken = ""
        return $response
    }
}

if ($script:Failures.Count -gt 0) {
    Complete-SmokeRun -ExitCode 1
}

if ($script:Warnings.Count -gt 0) {
    Complete-SmokeRun -ExitCode 0
}

Complete-SmokeRun -ExitCode 0
