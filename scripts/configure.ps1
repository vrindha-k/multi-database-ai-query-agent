$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path .env) { throw '.env exists; edit it manually to preserve existing credentials.' }
function New-Password {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [BitConverter]::ToString($bytes).Replace('-', '').ToLower()
}
$ecAdmin = New-Password
$ecReader = New-Password
$hrAdmin = New-Password
$hrReader = New-Password
$dbs = @(
    @{id='ecommerce'; description='Synthetic e-commerce analytics; 2025'; url="postgresql+psycopg://ecommerce_reader:${ecReader}@localhost:5541/ecommerce"; schemas=@('public')},
    @{id='hr'; description='Synthetic HR analytics; 2025'; url="postgresql+psycopg://hr_reader:${hrReader}@localhost:5542/hr"; schemas=@('public')}
) | ConvertTo-Json -Compress
$content = @"
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b-instruct
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
ECOMMERCE_ADMIN_PASSWORD=$ecAdmin
ECOMMERCE_READER_PASSWORD=$ecReader
HR_ADMIN_PASSWORD=$hrAdmin
HR_READER_PASSWORD=$hrReader
DATABASES_JSON='$dbs'
STATEMENT_TIMEOUT_MS=3000
MAX_ROWS=100
"@
[IO.File]::WriteAllText((Join-Path $PWD '.env'), $content, (New-Object Text.UTF8Encoding $false))
Write-Host 'Created private demo credentials. Ollama is the default AI provider; no API key required.'
