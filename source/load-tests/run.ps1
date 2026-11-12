param(
    [string]$JMeterHome = $env:JMETER_HOME,
    [string]$JavaHome = $env:JAVA_HOME,
    [ValidateRange(1, 10000)][int]$Users = 100,
    [ValidateRange(0, 3600)][int]$Ramp = 30,
    [ValidateRange(1, 100000)][int]$Loops = 120,
    [ValidateRange(0, 60000)][int]$Think = 1000,
    [string]$TargetHost = '127.0.0.1',
    [ValidateRange(1, 65535)][int]$Port = 18080,
    [ValidateSet('http', 'https')][string]$Scheme = 'http',
    [string]$Ward = '00004',
    [string]$Province = '01'
)
$ErrorActionPreference = 'Stop'
if (!$JMeterHome -or !(Test-Path -LiteralPath "$JMeterHome/bin/jmeter.bat")) {
    throw 'Truyen -JMeterHome hoac dat JMETER_HOME toi thu muc Apache JMeter 5.6.3.'
}
if (!$JavaHome -or !(Test-Path -LiteralPath "$JavaHome/bin/java.exe")) {
    throw 'Truyen -JavaHome hoac dat JAVA_HOME toi JDK 17+ (WebSocket dung Java HttpClient).'
}
$env:JAVA_HOME = $JavaHome
$base = "${Scheme}://${TargetHost}:${Port}/api/v1"
foreach ($path in @('/health', '/provinces?page_size=100', "/wards?province_id=$Province&page_size=100", "/wards/$Ward/weather/current", "/wards/$Ward/weather/history?page_size=60")) {
    $response = Invoke-RestMethod -Uri "$base$path" -TimeoutSec 15
    if (!$response.success) { throw "Preflight that bai: $path" }
}
$current = Invoke-RestMethod -Uri "$base/wards/$Ward/weather/current" -TimeoutSec 15
if ($current.data.observation.source -ne 'simulator') {
    throw 'Bai test nay yeu cau WEATHER_SOURCE=simulator va publisher dang chay.'
}
$runId = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + "-u$Users"
$output = Join-Path $PSScriptRoot "results/$runId"
New-Item -ItemType Directory -Path $output -Force | Out-Null
@{
    started_at_utc = [DateTime]::UtcNow.ToString('o')
    users = $Users; ramp_seconds = $Ramp; loops = $Loops; think_ms = $Think
    target = "${Scheme}://${TargetHost}:${Port}"; ward = $Ward; province = $Province
    jmeter_home = $JMeterHome; java_home = $JavaHome
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $output 'run.json')
& "$JavaHome/bin/java.exe" -Xms256m -Xmx1g -jar "$JMeterHome/bin/ApacheJMeter.jar" `
    -n -t "$PSScriptRoot/dashboard.jmx" `
    -l "$output/samples.jtl" -j "$output/jmeter.log" -e -o "$output/html" `
    "-Jscripts=$PSScriptRoot" "-Jusers=$Users" "-Jramp=$Ramp" "-Jloops=$Loops" `
    "-Jthink=$Think" "-Jhost=$TargetHost" "-Jport=$Port" "-Jscheme=$Scheme" `
    "-Jward=$Ward" "-Jprovince=$Province" `
    '-Jjmeter.save.saveservice.output_format=csv' `
    '-Jjmeter.save.saveservice.assertion_results_failure_message=true' `
    '-Jjmeter.save.saveservice.response_message=true'
if ($LASTEXITCODE -ne 0) { throw "JMeter that bai. Xem $output/jmeter.log" }
python -X utf8 "$PSScriptRoot/summarize.py" "$output/samples.jtl" --users $Users --loops $Loops
if ($LASTEXITCODE -ne 0) { throw "Khong dat nguong hoac run khong day du. Xem $output/summary.md" }
Write-Host "Bao cao: $output/html/index.html"
