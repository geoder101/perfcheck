$ErrorActionPreference = 'Stop'

function Stop-Adapter([string] $Message) {
    [Console]::Error.WriteLine($Message)
    exit 2
}

function ConvertTo-NativeArgument([string] $Value) {
    # Win32 argv quoting: double backslashes before quotes and the closing quote.
    $escaped = [regex]::Replace($Value, '(\\*)"', {
        param($match)
        ('\' * ($match.Groups[1].Length * 2 + 1)) + '"'
    })
    $escaped = [regex]::Replace($escaped, '(\\+)\z', '$1$1')
    return '"' + $escaped + '"'
}

$root = $env:PERFCHECK_CONTAINER_HOST_ROOT
if (-not $root) { Stop-Adapter 'Run through podman.just' }
$image = $env:PERFCHECK_CONTAINER_IMAGE
if (-not $image) { $image = 'localhost/perfcheck-dev:py314-uv0129-just1580' }
if ($image.StartsWith('-')) { Stop-Adapter 'Image must be a reference, not a Podman option' }
$action = $args[0]
$forward = @($args | Select-Object -Skip 1)
$native = @()
switch ($action) {
    'build' {
        $native = @('build', '--http-proxy=false', '--tag', $image, '--file', (Join-Path $root 'Containerfile'), $root)
    }
    { $_ -in 'run', 'preview' } {
        $port = $null
        if ($action -eq 'preview') {
            $port = '8000'
            if ($forward.Count -gt 0) { $port = [string]$forward[0] }
            if ($port -notmatch '\A[0-9]{1,5}\z' -or [int]$port -lt 1 -or [int]$port -gt 65535) {
                Stop-Adapter 'Preview port must be 1..65535'
            }
            $forward = @('docs-preview', '8000')
        } elseif ($forward.Count -eq 0) { $forward = @('--list') }

        $linux = [Environment]::OSVersion.Platform -eq [PlatformID]::Unix -and
            [System.IO.Directory]::Exists('/proc/sys/kernel')
        $source = $env:PERFCHECK_CONTAINER_SOURCE
        if (-not $source) {
            if (-not $linux) {
                Stop-Adapter 'Set PERFCHECK_CONTAINER_SOURCE to an engine-visible absolute Linux path; VM sharing and ownership must be configured externally'
            }
            $source = $root
        }
        if (-not $source.StartsWith('/') -or $source.Contains(':') -or $source.Contains('\')) {
            Stop-Adapter 'Source must be an absolute Linux path without mount delimiters'
        }
        $state = $env:PERFCHECK_CONTAINER_STATE_VOLUME
        if (-not $state) {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try { $hash = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($root)) }
            finally { $sha.Dispose() }
            $digest = ([BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant().Substring(0, 12)
            $state = "perfcheck-dev-$digest-py314-v1"
        }
        if ($state -notmatch '\A[a-zA-Z0-9][a-zA-Z0-9_.-]*\z') {
            Stop-Adapter 'State must be a named volume'
        }
        $native = @('run', '--rm', '--init', '--pull=never', '--http-proxy=false', '--workdir', '/workspace',
                    '--volume', "${state}:/container-state:U")
        if (Test-Path Env:PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX) {
            if ($env:PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX -cne '1') {
                Stop-Adapter 'PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX must be 1 when requested'
            }
            $native += @('--env', 'PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX=1')
        }
        if ($linux) {
            $native += @('--userns=keep-id', '--volume', "${source}:/workspace:z")
        } else {
            [Console]::Error.WriteLine('Remote/VM source sharing and writable ownership are caller-managed; native Linux keep-id/SELinux guarantees do not apply')
            $native += @('--volume', "${source}:/workspace")
        }
        if ($port) { $native += @('--publish', "127.0.0.1:${port}:8000") }
        $native += @($image) + $forward
    }
    default { Stop-Adapter "Unknown adapter action: $action" }
}

$start = New-Object System.Diagnostics.ProcessStartInfo
$start.FileName = 'podman'
$start.UseShellExecute = $false
$start.Arguments = ($native | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }) -join ' '
try { $process = [System.Diagnostics.Process]::Start($start) }
catch [System.ComponentModel.Win32Exception] {
    [Console]::Error.WriteLine("Unable to start podman: $($_.Exception.Message)")
    exit 127
}
try {
    $process.WaitForExit()
    $status = $process.ExitCode
} finally { $process.Dispose() }
exit $status
