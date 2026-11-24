$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'run_demo.py'

if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'Este instalador requiere Windows x64.'
}

$downloads = Join-Path ([System.IO.Path]::GetTempPath()) ("ufo-demo-" + [guid]::NewGuid())
$pythonDir = Join-Path $env:LocalAppData 'Programs\Python\Python313'
New-Item -ItemType Directory -Path $downloads | Out-Null

function Get-SignedInstaller($url, $name) {
    $path = Join-Path $downloads $name
    Write-Host "[Requisitos] Descargando $name..."
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $path
    Write-Host "[Requisitos] Verificando la firma de $name..."
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
    Write-Host '[Requisitos] Instalando Python 3.13. Esto puede tardar unos minutos...'
    Invoke-Installer $python @('/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test=0', ('TargetDir="{0}"' -f $pythonDir))

    $nodeRelease = 'https://nodejs.org/download/release/latest-v22.x'
    Write-Host '[Requisitos] Buscando la version de Node.js 22...'
    $checksums = (Invoke-WebRequest -UseBasicParsing -Uri "$nodeRelease/SHASUMS256.txt").Content
    $entry = [regex]::Match($checksums, '(?m)^([0-9a-f]{64})\s+(node-v22\.\d+\.\d+-x64\.msi)\s*$')
    if (-not $entry.Success) { throw 'No se encontro el instalador x64 de Node.js 22.' }
    $nodeName = $entry.Groups[2].Value
    $node = Get-SignedInstaller "$nodeRelease/$nodeName" $nodeName
    Write-Host '[Requisitos] Verificando el SHA-256 de Node.js...'
    if ((Get-FileHash -LiteralPath $node -Algorithm SHA256).Hash -ne $entry.Groups[1].Value) {
        throw 'El SHA-256 del instalador de Node.js no coincide.'
    }
    Write-Host '[Requisitos] Instalando Node.js 22 y npm. Esto puede tardar unos minutos...'
    Invoke-Installer 'msiexec.exe' @('/i', ('"{0}"' -f $node), '/qn', '/norestart')
} finally {
    Get-ChildItem -LiteralPath $downloads -File | Remove-Item
    Remove-Item -LiteralPath $downloads
}

$env:Path = (@($env:Path, [Environment]::GetEnvironmentVariable('Path', 'Machine'),
    [Environment]::GetEnvironmentVariable('Path', 'User')) -join ';')
$python = Join-Path $pythonDir 'python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'No se encontro el ejecutable de Python 3.13 instalado para este usuario.'
}
Write-Host '[Requisitos] Instalacion completa. Iniciando el lanzador de la muestra...'
& $python $launcher @args
exit $LASTEXITCODE
