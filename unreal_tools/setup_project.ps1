# Creates the Unreal 5.8 Blueprint project for Shattered Lands from the Third Person template
# (character, camera and input already working), enables Python editor scripting, and imports the Blender export kit.
#   powershell -ExecutionPolicy Bypass -File unreal_tools\setup_project.ps1
$ErrorActionPreference = 'Stop'
$UE = 'C:\Program Files\Epic Games\UE_5.8'
$Root = Split-Path $PSScriptRoot -Parent
$Proj = Join-Path $Root 'Unreal\ShatteredLands'
$UProject = Join-Path $Proj 'ShatteredLands.uproject'

if (-not (Test-Path $UProject)) {
    New-Item -ItemType Directory -Force $Proj | Out-Null
    Copy-Item "$UE\Templates\TP_ThirdPersonBP\*" $Proj -Recurse -Force
    # shared content the template expects (mannequin character, input actions, level prototyping meshes/materials)
    foreach ($pack in 'Characters', 'Input', 'LevelPrototyping') {
        $src = "$UE\Templates\TemplateResources\High\$pack\Content"
        if (Test-Path $src) { Copy-Item "$src\*" (Join-Path $Proj 'Content') -Recurse -Force }
    }
    Get-ChildItem $Proj -Filter *.uproject | Rename-Item -NewName 'ShatteredLands.uproject'
    foreach ($d in 'Saved', 'Intermediate', 'Media') { $p = Join-Path $Proj $d; if (Test-Path $p) { Remove-Item $p -Recurse -Force } }
    # project file: keep the template's settings, add Python + editor scripting
    $j = Get-Content $UProject -Raw | ConvertFrom-Json
    $want = @('PythonScriptPlugin', 'EditorScriptingUtilities', 'Interchange', 'InterchangeEditor')
    $have = @(); if ($j.Plugins) { $have = $j.Plugins | ForEach-Object { $_.Name } } else { $j | Add-Member Plugins @() }
    foreach ($w in $want) { if ($have -notcontains $w) { $j.Plugins += [pscustomobject]@{ Name = $w; Enabled = $true } } }
    $j.Description = 'Shattered Lands - A Viking Saga'
    $j | ConvertTo-Json -Depth 10 | Set-Content $UProject -Encoding utf8
    # game name in config
    $ini = Join-Path $Proj 'Config\DefaultGame.ini'
    if (Test-Path $ini) { (Get-Content $ini -Raw) -replace 'ProjectName=.*', 'ProjectName=Shattered Lands' | Set-Content $ini -Encoding utf8 }
    "project created: $UProject"
}

# import the Blender export kit and build the test battlefield level
& "$UE\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" $UProject -run=pythonscript -script="$PSScriptRoot\import_assets.py" -unattended -nosplash -nullrhi -stdout -FullStdOutLogOutput 2>&1 |
    Select-String 'SL_|Error|error:|Traceback' | ForEach-Object { $_.Line }
