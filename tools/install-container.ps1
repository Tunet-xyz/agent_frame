[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version = '0.6.0',
    [string]$ArchiveDirectory
)

$ErrorActionPreference = 'Stop'
$env:GH_PROMPT_DISABLED = '1'
$platform = & docker version --format '{{.Server.Os}}/{{.Server.Arch}}'
if ($LASTEXITCODE -ne 0) { throw 'Start a Linux Docker engine before installing the image.' }
if ($platform -notin @('linux/amd64', 'linux/arm64')) { throw "Unsupported Docker platform: $platform" }
$architecture = $platform.Split('/')[1]
$imagePrefix = 'agent-frame-mcp'
if ([Version]$Version -lt [Version]'0.6.0') { $imagePrefix = 'tunet-agents-mcp' }
$asset = "${imagePrefix}_${Version}_linux_${architecture}.docker.tar.gz"
$ownedDownload = $false
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

try {
    if ($ArchiveDirectory) {
        $download = (Resolve-Path -LiteralPath $ArchiveDirectory).Path
    } else {
        $download = Join-Path $tempRoot ('agentframe-container-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $download | Out-Null
        $ownedDownload = $true
        & gh release download "v$Version" --repo Tunet-xyz/agent_frame --pattern $asset --pattern SHA256SUMS --dir $download
        if ($LASTEXITCODE -ne 0) { throw 'Release download failed. Existing non-interactive GitHub access to the private repository is required.' }
    }
    $checksums = @(Get-Content -LiteralPath (Join-Path $download 'SHA256SUMS') | ForEach-Object {
        $parts = $_ -split '\s+', 2
        if ($parts.Count -eq 2 -and $parts[1] -eq $asset -and $parts[0] -match '^[a-fA-F0-9]{64}$') { $parts[0] }
    })
    if ($checksums.Count -ne 1) { throw 'The release checksum manifest has no unique entry for this image.' }
    $archive = Join-Path $download $asset
    $stream = [IO.File]::OpenRead($archive)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $actualHash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '')
    } finally {
        $hasher.Dispose()
        $stream.Dispose()
    }
    if ($actualHash -ne $checksums[0]) { throw 'Image checksum verification failed.' }
    & docker load --input $archive
    if ($LASTEXITCODE -ne 0) { throw 'Docker could not load the verified image.' }
    & docker tag "${imagePrefix}:${Version}-linux-${architecture}" "agent-frame-mcp:$Version"
    if ($LASTEXITCODE -ne 0) { throw 'Docker could not create the local image alias.' }
    Write-Output "AgentFrame MCP image ready: agent-frame-mcp:$Version"
} finally {
    if ($ownedDownload) {
        $resolved = (Resolve-Path -LiteralPath $download).Path
        if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or $resolved -eq $tempRoot.TrimEnd([IO.Path]::DirectorySeparatorChar)) {
            throw 'Refusing cleanup outside the owned temporary download directory.'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
