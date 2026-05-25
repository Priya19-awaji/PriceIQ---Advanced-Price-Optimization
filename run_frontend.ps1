$NodePath = "$PSScriptRoot\node-portable\node-v20.18.1-win-x64"
$env:PATH = "$NodePath;$env:PATH"
& "$NodePath\npm.cmd" run dev -- --port 3001 --host 0.0.0.0
