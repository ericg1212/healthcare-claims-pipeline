$root   = "C:\Users\ericg\projects\healthcare-claims-pipeline"
$python = "C:\Users\ericg\AppData\Local\Programs\Python\Python313\python.exe"

Get-Content "$root\.env" | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.+)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}

Set-Location $root
$env:PYTHONPATH = $root
& $python scripts/load_to_snowflake.py --fhir-dir output/fhir
