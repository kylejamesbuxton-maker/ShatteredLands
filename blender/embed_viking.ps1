# Embeds models/viking.json + viking.bin + vktex_* textures into index.html (vk-json, vk-bin, vk-tex-<key> tags).
#   powershell -File blender\embed_viking.ps1
$root = Split-Path $PSScriptRoot -Parent; $p = "$root\index.html"; $m = "$root\models"
$t = [IO.File]::ReadAllText($p)
$js = [IO.File]::ReadAllText("$m\viking.json"); $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$m\viking.bin"))
$t = ([regex]'(<script type="application/json" id="vk-json">)[\s\S]*?(</script>)').Replace($t, { param($x) $x.Groups[1].Value + $js + $x.Groups[2].Value }, 1)
$t = ([regex]'(<script type="text/plain" id="vk-bin">)[\s\S]*?(</script>)').Replace($t, { param($x) $x.Groups[1].Value + $b64 + $x.Groups[2].Value }, 1)
$t = ([regex]'\n<script type="text/plain" id="vk-tex-[a-z]+">[^<]*</script>').Replace($t, '')
$hdr = $js | ConvertFrom-Json; $tags = ""
foreach ($k in $hdr.tex.PSObject.Properties.Name) {
  $fn = $hdr.tex.$k.file; $mime = if ($fn.EndsWith('.png')) { 'image/png' } else { 'image/jpeg' }
  $tags += "`n<script type=`"text/plain`" id=`"vk-tex-$k`">data:$mime;base64," + [Convert]::ToBase64String([IO.File]::ReadAllBytes("$m\$fn")) + "</script>"
}
$i = $t.IndexOf('id="vk-bin"'); $j = $t.IndexOf('</script>', $i) + 9; $t = $t.Substring(0, $j) + $tags + $t.Substring($j)
[IO.File]::WriteAllText($p, $t); "embedded; index.html $($t.Length) chars"
