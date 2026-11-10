param([Parameter(Mandatory=$true)][string]$JobsPath,[Parameter(Mandatory=$true)][string]$ReportPath)
$ErrorActionPreference='Stop'
$jobs=Get-Content -LiteralPath $JobsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$results=New-Object System.Collections.Generic.List[object]
$word=$null
try {
    if (@($jobs | Where-Object {$_.kind -eq 'word'}).Count -gt 0) {
        $word=New-Object -ComObject Word.Application
        $word.Visible=$false
        $word.DisplayAlerts=0
        $word.AutomationSecurity=3
    }
    foreach ($job in $jobs) {
        $doc=$null;$stream=$null;$bitmap=$null;$resetWord=$false
        try {
            if ($job.kind -eq 'word') {
                if ($null -eq $word) {
                    $word=New-Object -ComObject Word.Application
                    $word.Visible=$false;$word.DisplayAlerts=0;$word.AutomationSecurity=3
                }
                $doc=$word.Documents.OpenNoRepairDialog($job.original,$false,$true,$false)
                $doc.WebOptions.Encoding=65001
                $doc.SaveAs2($job.output,10)
                $doc.Close(0);$doc=$null
            } elseif ($job.kind -eq 'ocr') {
                Add-Type -AssemblyName System.Runtime.WindowsRuntime
                $null=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
                $null=[Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
                $null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
                $null=[Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
                $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'} | Select-Object -First 1
                function Await($operation,[Type]$type) {
                    $task=$method.MakeGenericMethod($type).Invoke($null,@($operation))
                    $task.Wait();return $task.Result
                }
                $file=Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($job.original)) ([Windows.Storage.StorageFile])
                $stream=Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
                $decoder=Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
                $bitmap=Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
                $engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language('pt-BR')))
                if ($null -eq $engine) {throw 'OCR pt-BR indisponível'}
                $text=(Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])).Text
                [System.IO.File]::WriteAllText($job.output,$text,(New-Object System.Text.UTF8Encoding($false)))
            } else {throw 'Tipo de extração desconhecido'}
            $results.Add([pscustomobject]@{id=$job.id;status='convertido';output=$job.output;kind=$job.kind})
        } catch {
            if ($job.kind -eq 'word') {$resetWord=$true}
            $results.Add([pscustomobject]@{id=$job.id;status='falha';output=$job.output;erro=$_.Exception.Message;kind=$job.kind})
        } finally {
            if ($null -ne $doc) {try {$doc.Close(0)} catch {}}
            if ($resetWord -and $null -ne $word) {
                try {$word.Quit()} catch {}
                [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
                $word=$null
            }
            if ($null -ne $bitmap) {$bitmap.Dispose()}
            if ($null -ne $stream) {$stream.Dispose()}
        }
        [System.IO.File]::WriteAllText($ReportPath,($results.ToArray() | ConvertTo-Json -Depth 8),(New-Object System.Text.UTF8Encoding($false)))
    }
} finally {
    if ($null -ne $word) {try {$word.Quit()} catch {};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null}
}
