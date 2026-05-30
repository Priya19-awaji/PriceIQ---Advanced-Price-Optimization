$NodePath = "$PSScriptRoot\node-portable\node-v20.18.1-win-x64"
$env:PATH = "$NodePath;$env:PATH"
Write-Host "Starting Vite frontend server..."
cd frontend
..\node-portable\node-v20.18.1-win-x64\node.exe node_modules\vite\bin\vite.js --port 8080 --host
