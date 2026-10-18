# Integration journey through NGINX: signup -> onboarding -> shortlist ->
# detail -> eligibility -> compare -> save -> finance -> admin review.
# Fails fast (exit 1) on any unexpected status; prints each step's result.
$ErrorActionPreference = 'Stop'
# NGINX host port: WEB_PORT env var, else WEB_PORT in .env, else 8080
$webPort = $env:WEB_PORT
if (-not $webPort -and (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) '.env'))) {
  $m = Select-String -Path (Join-Path (Split-Path $PSScriptRoot -Parent) '.env') -Pattern '^WEB_PORT=(.+)$'
  if ($m) { $webPort = $m.Matches[0].Groups[1].Value.Trim() }
}
if (-not $webPort) { $webPort = '8080' }
$base = "http://localhost:$webPort"
$api = "$base/api/v1"
$script:fail = 0

# Runs a scriptblock, returns a normalized object { StatusCode, Content } even
# when Invoke-WebRequest throws on 4xx/5xx (WebException in PS 5.1).
function Step($name, $expr, $expect = @(200)) {
  $resp = $null
  try {
    $resp = & $expr
  } catch {
    $e = $_.Exception
    $status = $null
    $body = ''
    # PS 5.1 wraps HTTP errors in WebException with an HttpWebResponse body
    if ($e.PSObject.Properties['Response'] -and $e.Response) {
      $status = [int]$e.Response.StatusCode
      try {
        $stream = $e.Response.GetResponseStream()
        if ($stream) {
          $stream.Position = 0
          $reader = New-Object System.IO.StreamReader($stream)
          $body = $reader.ReadToEnd()
          $reader.Close()
        }
      } catch { }
    }
    if ($null -ne $status) {
      $resp = [pscustomobject]@{ StatusCode = $status; Content = $body }
    } else {
      Write-Host "FAIL $name -> exception: $($e.Message)"
      $script:fail = 1
      $script:last = $null
      return
    }
  }
  if ($expect -contains $resp.StatusCode) {
    Write-Host "OK   $name -> $($resp.StatusCode)"
    $script:last = $resp
    return
  }
  Write-Host "FAIL $name -> $($resp.StatusCode) (expected $($expect -join '|'))"
  Write-Host ("     body: " + ($resp.Content.Substring(0, [Math]::Min(400, $resp.Content.Length))))
  $script:fail = 1
  $script:last = $resp
}

$script:s = New-Object Microsoft.PowerShell.Commands.WebRequestSession

function Get-Json($path) { Invoke-WebRequest -Uri "$api$path" -WebSession $script:s -UseBasicParsing }
function Post-Json($path, $body) {
  $h = @{'Content-Type' = 'application/json'}
  $payload = if ($null -ne $body) { $body | ConvertTo-Json -Depth 8 } else { '{}' }
  Invoke-WebRequest -Uri "$api$path" -Method Post -Headers $h -Body $payload -WebSession $script:s -UseBasicParsing
}

# --- 0. static SPA + health through NGINX -----------------------------------
Step 'GET / (SPA index)' { Invoke-WebRequest -Uri "$base/" -WebSession $script:s -UseBasicParsing }
Step 'GET /discover (SPA route)' { Invoke-WebRequest -Uri "$base/discover" -WebSession $script:s -UseBasicParsing }
Step 'health/ready' { Get-Json '/health/ready' }
Step 'meta' { Get-Json '/meta' }

# --- 1. register -------------------------------------------------------------
$email = "journey-$(Get-Random)@example.com"
$r = $null
Step 'register' { Post-Json '/auth/register' @{email = $email; password = 'Journey-Pass-1!'; display_name = 'Journey User'} } @(201)
$r = $script:last
if (-not $r -or $r.StatusCode -ne 201) { Write-Output 'JOURNEY: FAILED (register)'; exit 1 }

# --- 2. onboarding -----------------------------------------------------------
Step 'onboarding/complete' {
  Post-Json '/profile/onboarding/complete' @{
    intended_degree_level = 'masters'
    field = 'computer_science'
    country_preferences = @(@{country_code = 'DE'; preference_rank = 1; is_mandatory = $false},
                            @{country_code = 'NL'; preference_rank = 2; is_mandatory = $false})
    academic_degree = 'bachelors'
    institution_name = 'Journey University'
    grade_value = 8.2; grade_scale_min = 4; grade_scale_max = 10
    grade_system = 'cgpa'; graduation_status = 'completed'; graduation_year = 2025
    english_test_status = 'completed'; english_test_type = 'ielts'; english_test_overall = 7.5
    budget_amount = 30000; budget_currency = 'EUR'; budget_basis = 'full_degree_all_in'
    target_intake_year = 2027; target_intake_term = 'winter'
    risk_tolerance = 'balanced'
  }
} @(200, 201)
Step 'profile/completeness' { Get-Json '/profile/completeness' }

# --- 3. discover -------------------------------------------------------------
Step 'programs list' { Get-Json '/programs?page=1&page_size=5' }
$programs = $script:last
$pdata = $programs.Content | ConvertFrom-Json
$p1 = $pdata.items[0].id
$p2 = $pdata.items[1].id
Write-Host "     programs total=$($pdata.total_items) p1=$p1"

# --- 4. program detail + evidence tabs ---------------------------------------
Step 'program detail' { Get-Json "/programs/$p1" }
Step 'program requirements' { Get-Json "/programs/$p1/requirements" }
Step 'program fees' { Get-Json "/programs/$p1/fees" }
Step 'program evidence' { Get-Json "/programs/$p1/evidence" }
Step 'program outcomes' { Get-Json "/programs/$p1/outcomes" }

# --- 5. shortlist run --------------------------------------------------------
Step 'POST /recommendations' { Post-Json '/recommendations' @{filters = @{}; limit_per_tier = 5} } @(200, 201)
$run = $script:last
$runId = ($run.Content | ConvertFrom-Json).run_id
if (-not $runId) { Write-Host 'FAIL: no run_id in recommendation response'; $script:fail = 1 }
Step 'GET run' { Get-Json "/recommendations/$runId" }
Step 'GET run explanations' { Get-Json "/recommendations/$runId/explanations" }
Step 'list runs' { Get-Json '/recommendations' }

# --- 6. eligibility (explicit action) ----------------------------------------
Step 'POST eligibility' { Post-Json '/eligibility/evaluations' @{program_ids = @($p1, $p2)} } @(200, 201)

# --- 7. compare + save -------------------------------------------------------
Step 'POST programs/compare' { Post-Json '/programs/compare' @{program_ids = @($p1, $p2)} } @(200, 201)
Step 'POST saved-program' { Post-Json '/saved-programs' @{program_id = $p1} } @(200, 201)
Step 'GET saved-programs' { Get-Json '/saved-programs' }
Step 'POST comparison save' { Post-Json '/comparisons' @{name = 'Journey comparison'; program_ids = @($p1, $p2)} } @(200, 201)

# --- 8. finance + public catalogue -------------------------------------------
Step 'POST cost-estimate' { Post-Json '/cost-estimates' @{program_id = $p1; scenario = 'base'; currency = 'EUR'} } @(200, 201)
Step 'POST loan-scenario' {
  Post-Json '/loan-scenarios' @{name = 'Journey loan'; principal_amount = 20000; currency = 'EUR';
    annual_interest_rate = 6.5; tenure_months = 60; moratorium_months = 6;
    interest_during_moratorium = 'capitalize'; repayment_method = 'equal_emi'}
} @(200, 201)
Step 'POST roi-scenario' {
  Post-Json '/roi-scenarios' @{name = 'Journey ROI'; currency = 'EUR'; education_cost = 30000;
    expected_annual_income = 55000; employment_delay_months = 3; annual_expenses = 18000; discount_rate = 5}
} @(200, 201)
Step 'POST scholarships/matches' { Post-Json '/scholarships/matches' } @(200, 201)
Step 'GET destinations' { Get-Json '/destinations/countries' }
Step 'GET outcomes search' { Get-Json '/outcomes?field=computer_science&page_size=5' }

# --- 9. logout, demo admin login (auth rate limit 10/min; 4 auth calls total) -
Step 'logout (journey user)' { Invoke-WebRequest -Uri "$api/auth/logout" -Method Post -WebSession $script:s -UseBasicParsing } @(204)
Step 'admin login' { Post-Json '/auth/login' @{email = 'admin@example.com'; password = 'change_me_admin_pw'} } @(200)

# --- 10. admin review --------------------------------------------------------
Step 'admin review-queue' { Get-Json '/admin/review-queue?page_size=10' }
$q = $script:last
$qdata = $q.Content | ConvertFrom-Json
Write-Host "     queue total=$($qdata.total_items)"
$factId = $qdata.items[0].fact_id
Step 'admin fact detail' { Get-Json "/admin/facts/$factId" }
Step 'admin request-evidence' { Post-Json "/admin/facts/$factId/request-evidence" @{reason = 'Journey check: requesting stronger source'} } @(200, 409)
Step 'admin sources' { Get-Json '/admin/sources' }
Step 'admin jobs' { Get-Json '/admin/jobs' }
Step 'admin audit-events' { Get-Json '/admin/audit-events?page_size=10' }

# --- 11. protected route rejects after logout -------------------------------
Step 'logout (admin)' { Invoke-WebRequest -Uri "$api/auth/logout" -Method Post -WebSession $script:s -UseBasicParsing } @(204)
Step 'protected after logout' { Get-Json '/recommendations' } @(401)

if ($script:fail) { Write-Output 'JOURNEY: FAILED'; exit 1 }
Write-Output 'JOURNEY: ALL STEPS PASSED'
