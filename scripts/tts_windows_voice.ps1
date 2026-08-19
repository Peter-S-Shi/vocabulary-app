param(
    [string]$VoiceId,
    [string]$Text,
    [string]$ExpectedCodeUnits,
    [string]$OutputPath,
    [switch]$Preflight
)

<#
Local Windows Speech Provider / Installed Voice Binding (M20 Release
Contract § 2.3): invokes whatever Windows-installed speech voice the
caller names by ``-VoiceId`` -- never a fixed, hardcoded voice. This
generalizes the M15.1 Mandarin-only Yaoyao path (the prior art this
project already proved works) across every M20-supported language
(English, French, Mandarin): same WinRT mechanism
(``Windows.Media.SpeechSynthesis.SpeechSynthesizer``), same explicit
"voice must already be installed, never silently substituted" contract,
same Unicode-code-unit preflight safety check against command-line
text corruption -- previously justified as Mandarin-specific, but
equally applicable to accented French text, so it now runs for every
language rather than being special-cased to one.
#>

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

if ([string]::IsNullOrWhiteSpace($VoiceId)) {
    Write-Error "VoiceId is required."
    exit 1
}

[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Id -eq $VoiceId }
if (-not $voice) {
    Write-Error "The selected voice is unavailable: $VoiceId"
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
# PowerShell source-code literal is used for the input text.
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
