[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$Region = "us-central1",

    [string]$BucketName = "",

    [string]$BackendServiceAccountName = "local-seo-backend-sa",

    [string]$FrontendServiceAccountName = "local-seo-frontend-sa",

    [switch]$CreateBucket,

    [switch]$IncludeCloudSqlApis,

    [switch]$GrantCurrentUserAdminRoles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Gcloud {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    Write-Host ("gcloud " + ($Args -join " ")) -ForegroundColor DarkGray
    & gcloud @Args
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed: gcloud $($Args -join ' ')"
    }
}

function Invoke-GcloudCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    Write-Host ("gcloud " + ($Args -join " ")) -ForegroundColor DarkGray
    $output = & gcloud @Args
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed: gcloud $($Args -join ' ')"
    }
    return ($output | Out-String).Trim()
}

function Ensure-ServiceAccount {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectId,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$DisplayName
    )

    $email = "$Name@$ProjectId.iam.gserviceaccount.com"
    $existing = Invoke-GcloudCapture @(
        "iam", "service-accounts", "list",
        "--project", $ProjectId,
        "--filter", "email=$email",
        "--format", "value(email)"
    )

    if ([string]::IsNullOrWhiteSpace($existing)) {
        Write-Host "Creating service account: $email" -ForegroundColor Yellow
        Invoke-Gcloud @(
            "iam", "service-accounts", "create", $Name,
            "--project", $ProjectId,
            "--display-name", $DisplayName
        )
    }
    else {
        Write-Host "Service account already exists: $email" -ForegroundColor Green
    }

    return $email
}

function Ensure-ProjectRoleBinding {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectId,

        [Parameter(Mandatory = $true)]
        [string]$Member,

        [Parameter(Mandatory = $true)]
        [string]$Role
    )

    $existing = Invoke-GcloudCapture @(
        "projects", "get-iam-policy", $ProjectId,
        "--flatten", "bindings[].members",
        "--filter", "bindings.role=$Role AND bindings.members=$Member",
        "--format", "value(bindings.members)"
    )

    if ([string]::IsNullOrWhiteSpace($existing)) {
        Write-Host "Granting $Role to $Member" -ForegroundColor Yellow
        Invoke-Gcloud @(
            "projects", "add-iam-policy-binding", $ProjectId,
            "--member", $Member,
            "--role", $Role
        )
    }
    else {
        Write-Host "IAM binding already exists: $Member -> $Role" -ForegroundColor Green
    }
}

function Ensure-Bucket {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectId,

        [Parameter(Mandatory = $true)]
        [string]$BucketName,

        [Parameter(Mandatory = $true)]
        [string]$Region
    )

    $bucketUri = "gs://$BucketName"
    $null = & gcloud storage buckets describe $bucketUri --project $ProjectId 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Creating bucket: $bucketUri" -ForegroundColor Yellow
        Invoke-Gcloud @(
            "storage", "buckets", "create", $bucketUri,
            "--project", $ProjectId,
            "--location", $Region,
            "--uniform-bucket-level-access"
        )
    }
    else {
        Write-Host "Bucket already exists: $bucketUri" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "GCP bootstrap starting for project $ProjectId" -ForegroundColor Cyan
Write-Host ""

Invoke-Gcloud @("config", "set", "project", $ProjectId)

$apis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "containerregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com"
)

if ($IncludeCloudSqlApis) {
    $apis += @(
        "sqladmin.googleapis.com",
        "vpcaccess.googleapis.com",
        "servicenetworking.googleapis.com"
    )
}

Write-Host "Enabling required APIs..." -ForegroundColor Cyan
$enableArgs = @("services", "enable") + $apis + @("--project", $ProjectId)
Invoke-Gcloud -Args $enableArgs

$projectNumber = Invoke-GcloudCapture @(
    "projects", "describe", $ProjectId,
    "--format", "value(projectNumber)"
)

$cloudBuildSaEmail = "$projectNumber@cloudbuild.gserviceaccount.com"
$backendSaEmail = Ensure-ServiceAccount -ProjectId $ProjectId -Name $BackendServiceAccountName -DisplayName "Local SEO backend runtime"
$frontendSaEmail = Ensure-ServiceAccount -ProjectId $ProjectId -Name $FrontendServiceAccountName -DisplayName "Local SEO frontend runtime"

$cloudBuildMember = "serviceAccount:$cloudBuildSaEmail"
$backendMember = "serviceAccount:$backendSaEmail"
$frontendMember = "serviceAccount:$frontendSaEmail"

Write-Host "Granting Cloud Build deployment roles..." -ForegroundColor Cyan
$cloudBuildRoles = @(
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/secretmanager.secretAccessor",
    "roles/storage.admin",
    "roles/artifactregistry.writer"
)

if ($IncludeCloudSqlApis) {
    $cloudBuildRoles += "roles/cloudsql.client"
}

foreach ($role in $cloudBuildRoles) {
    Ensure-ProjectRoleBinding -ProjectId $ProjectId -Member $cloudBuildMember -Role $role
}

Write-Host "Granting backend runtime roles..." -ForegroundColor Cyan
$backendRoles = @(
    "roles/storage.objectAdmin",
    "roles/secretmanager.secretAccessor"
)

if ($IncludeCloudSqlApis) {
    $backendRoles += "roles/cloudsql.client"
}

foreach ($role in $backendRoles) {
    Ensure-ProjectRoleBinding -ProjectId $ProjectId -Member $backendMember -Role $role
}

Write-Host "Granting frontend runtime roles..." -ForegroundColor Cyan
$frontendRoles = @()
foreach ($role in $frontendRoles) {
    Ensure-ProjectRoleBinding -ProjectId $ProjectId -Member $frontendMember -Role $role
}

if ($GrantCurrentUserAdminRoles) {
    $currentAccount = Invoke-GcloudCapture @(
        "auth", "list",
        "--filter", "status:ACTIVE",
        "--format", "value(account)"
    )

    if ([string]::IsNullOrWhiteSpace($currentAccount)) {
        throw "Could not resolve active gcloud account."
    }

    $currentUserMember = "user:$currentAccount"
    Write-Host "Granting operator roles to active user $currentAccount" -ForegroundColor Cyan

    $operatorRoles = @(
        "roles/run.admin",
        "roles/cloudbuild.builds.editor",
        "roles/iam.serviceAccountUser",
        "roles/secretmanager.admin",
        "roles/serviceusage.serviceUsageAdmin",
        "roles/storage.admin",
        "roles/artifactregistry.admin"
    )

    if ($IncludeCloudSqlApis) {
        $operatorRoles += "roles/cloudsql.admin"
    }

    foreach ($role in $operatorRoles) {
        Ensure-ProjectRoleBinding -ProjectId $ProjectId -Member $currentUserMember -Role $role
    }
}

if ($CreateBucket) {
    if ([string]::IsNullOrWhiteSpace($BucketName)) {
        throw "BucketName is required when -CreateBucket is used."
    }
    Ensure-Bucket -ProjectId $ProjectId -BucketName $BucketName -Region $Region
}

Write-Host ""
Write-Host "Bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "Project summary" -ForegroundColor Cyan
Write-Host "  Project ID:            $ProjectId"
Write-Host "  Region:                $Region"
Write-Host "  Project number:        $projectNumber"
Write-Host "  Cloud Build SA:        $cloudBuildSaEmail"
Write-Host "  Backend runtime SA:    $backendSaEmail"
Write-Host "  Frontend runtime SA:   $frontendSaEmail"
if ($CreateBucket) {
    Write-Host "  GCS bucket:            gs://$BucketName"
}

Write-Host ""
Write-Host "Recommended next steps" -ForegroundColor Cyan
Write-Host "  1. Create Secret Manager entries:"
Write-Host "     - jwt-secret"
Write-Host "     - database-url"
Write-Host "     - openai-key or gemini-key"
Write-Host "     - stripe-secret / stripe-webhook-secret if billing is enabled"
Write-Host "     - twilio / sendgrid / oauth secrets if those features are enabled"
Write-Host "  2. Finalize APP_URL and NEXT_PUBLIC_API_URL policy."
Write-Host "  3. Review cloudbuild.yaml secret injection before first production deploy."
Write-Host "  4. Deploy backend first, then frontend, then run scripts/smoke_test_prod.ps1."
Write-Host ""
Write-Host "Example secret commands" -ForegroundColor Cyan
Write-Host "  gcloud secrets create jwt-secret --replication-policy=automatic"
Write-Host "  echo -n '<strong-secret>' | gcloud secrets versions add jwt-secret --data-file=-"
Write-Host "  gcloud secrets create database-url --replication-policy=automatic"
Write-Host "  echo -n '<postgres-url>' | gcloud secrets versions add database-url --data-file=-"
Write-Host ""
Write-Host "Example run" -ForegroundColor Cyan
Write-Host "  .\scripts\bootstrap-gcp.ps1 -ProjectId '$ProjectId' -Region '$Region' -CreateBucket -BucketName '<your-bucket>' -IncludeCloudSqlApis -GrantCurrentUserAdminRoles"
