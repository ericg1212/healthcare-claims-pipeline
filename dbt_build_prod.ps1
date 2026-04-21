$root = "C:\Users\ericg\projects\healthcare-claims-pipeline"
$dbt  = "C:\Users\ericg\AppData\Local\Programs\Python\Python313\Scripts\dbt.exe"

Get-Content "$root\.env" | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.+)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}

Set-Location "$root\dbt_project"
& $dbt build --profiles-dir profiles --target prod
