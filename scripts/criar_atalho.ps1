# Cria LEB.lnk na área de trabalho, com o Faveicon.ico.
$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$desktop = [Environment]::GetFolderPath("Desktop")
$atalho = Join-Path $desktop "LEB.lnk"
$destino = Join-Path $raiz "scripts\iniciar_lextracaoboloes.bat"
$icone = Join-Path $raiz "static\img\Faveicon.ico"

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($atalho)
$lnk.TargetPath = $destino
$lnk.WorkingDirectory = $raiz
$lnk.WindowStyle = 7
$lnk.Description = "LEB - Extracao de Boloes"
if (Test-Path $icone) {
    $lnk.IconLocation = "$icone,0"
}
$lnk.Save()
Write-Host "Atalho criado: $atalho"
