$ErrorActionPreference = 'Stop'

if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'Este instalador requiere Windows x64.'
}

$downloads = Join-Path ([System.IO.Path]::GetTempPath()) ("ufo-demo-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $downloads | Out-Null

function Get-SignedInstaller($url, $name) {
    $path = Join-Path $downloads $name
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $path
    if ((Get-AuthenticodeSignature -LiteralPath $path).Status -ne 'Valid') {
        throw "La firma del instalador $name no es valida."
    }
    return $path
}

function Invoke-Installer($file, $arguments) {
    $process = Start-Process -FilePath $file -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "El instalador $file termino con codigo $($process.ExitCode)."
    }
}

try {
    $pythonName = 'python-3.13.13-amd64.exe'
    $python = Get-SignedInstaller "https://www.python.org/ftp/python/3.13.13/$pythonName" $pythonName
    Invoke-Installer $python @('/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test=0')

    $nodeRelease = 'https://nodejs.org/download/release/latest-v22.x'
    $checksums = (Invoke-WebRequest -UseBasicParsing -Uri "$nodeRelease/SHASUMS256.txt").Content
    $entry = [regex]::Match($checksums, '(?m)^([0-9a-f]{64})\s+(node-v22\.\d+\.\d+-x64\.msi)\s*$')
    if (-not $entry.Success) { throw 'No se encontro el instalador x64 de Node.js 22.' }
    $nodeName = $entry.Groups[2].Value
    $node = Get-SignedInstaller "$nodeRelease/$nodeName" $nodeName
    if ((Get-FileHash -LiteralPath $node -Algorithm SHA256).Hash -ne $entry.Groups[1].Value) {
        throw 'El SHA-256 del instalador de Node.js no coincide.'
    }
    Invoke-Installer 'msiexec.exe' @('/i', ('"{0}"' -f $node), '/qn', '/norestart')
} finally {
    Get-ChildItem -LiteralPath $downloads -File | Remove-Item
    Remove-Item -LiteralPath $downloads
}

Write-Host 'Abre una nueva PowerShell y ejecuta python scripts/run_demo.py desde la raiz del repositorio.'
