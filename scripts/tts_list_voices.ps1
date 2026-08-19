<#
Enumerates every speech voice installed on this Windows system through
WinRT (``Windows.Media.SpeechSynthesis.SpeechSynthesizer.AllVoices``),
the same voice catalog ``tts_windows_voice.ps1`` invokes against. Prints
a JSON array to stdout: ``[{"id", "display_name", "language"}, ...]``.

This is a read-only enumeration -- it never installs, downloads, or
modifies any voice. Used by the Local Windows Speech Provider /
Installed Voice Binding capability (M20 Release Contract § 2.3) to show
the user which voices they can bind, per language.
#>

$ErrorActionPreference = "Stop"

[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime] | Out-Null

$voices = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ForEach-Object {
    [PSCustomObject]@{
        id           = $_.Id
        display_name = $_.DisplayName
        language     = $_.Language
    }
}

if ($null -eq $voices) {
    Write-Output "[]"
} else {
    ConvertTo-Json -InputObject @($voices) -Compress
}
