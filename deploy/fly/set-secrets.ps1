# Menyalin rahasia dari backend\.env ke Fly (tanpa menampilkannya). Jalankan dari folder proyek.
$keys = 'SECRET_KEY','GEMINI_API_KEY','GEMINI_MODEL','GEMINI_FALLBACK_MODEL','GEMINI_MIN_INTERVAL',
        'SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM',
        'MIDTRANS_SERVER_KEY','MIDTRANS_CLIENT_KEY','MIDTRANS_IS_PRODUCTION','ROUTER_API_KEY','ROUTER_MODEL'
$pattern = '^(' + ($keys -join '|') + ')='
$noBom = New-Object System.Text.UTF8Encoding($false)
$lines = [System.IO.File]::ReadAllLines((Resolve-Path 'backend\.env'), $noBom) | Where-Object { $_ -match $pattern }
$tmp = Join-Path $env:TEMP 'narative-fly-secrets.env'
try {
    [System.IO.File]::WriteAllLines($tmp, $lines, $noBom)
    cmd /c "flyctl secrets import --stage -a narative-api-ipl26 < `"$tmp`""
} finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
}
