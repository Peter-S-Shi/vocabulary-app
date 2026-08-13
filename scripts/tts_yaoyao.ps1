param(
    [string]$Text,
    [string]$ExpectedCodeUnits,
    [string]$OutputPath,
    [switch]$Preflight
)

$ErrorActionPreference = "Stop"

function Await-WinRT {
    param($WinRtTask, $ResultType)
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and $_.GetGenericArguments().Count -eq 1
    })[0]
    $asTaskSpecific = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTaskSpecific.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$voiceId = "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens\MSTTS_V110_zhCN_YaoyaoM"
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Id -eq $voiceId }
if (-not $voice) {
    Write-Error "The selected Yaoyao voice is unavailable."
    exit 2
}
if ($Preflight) {
    exit 0
}
if ([string]::IsNullOrWhiteSpace($Text) -or [string]::IsNullOrWhiteSpace($OutputPath)) {
    Write-Error "Text and OutputPath are required."
    exit 3
}

# Text arrives through the Unicode Windows process-command-line boundary. Verify
# the exact UTF-16 code units immediately before invoking WinRT; no file read or
# PowerShell source-code literal is used for Mandarin input.
$actualCodeUnits = ($Text.ToCharArray() | ForEach-Object { [int]$_ }) -join ","
if ([string]::IsNullOrWhiteSpace($ExpectedCodeUnits) -or $ExpectedCodeUnits -ne $actualCodeUnits) {
    Write-Error "Unicode preflight failed."
    exit 4
}

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$synth.Voice = $voice
$stream = Await-WinRT $synth.SynthesizeTextToStreamAsync($Text) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$inputStream = $stream.GetInputStreamAt(0)
$reader = New-Object Windows.Storage.Streams.DataReader($inputStream)
$size = [uint32]$stream.Size
Await-WinRT $reader.LoadAsync($size) ([uint32]) | Out-Null
$bytes = New-Object byte[] $size
$reader.ReadBytes($bytes)
[System.IO.File]::WriteAllBytes($OutputPath, $bytes)
exit 0
