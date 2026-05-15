param(
    [Parameter(Mandatory = $true)]
    [string]$VultrIp
)

$ErrorActionPreference = "Stop"

$remote = "root@$VultrIp"
$remotePath = "/opt/prometheus"

ssh $remote "mkdir -p $remotePath && rm -rf $remotePath/backend $remotePath/configs && mkdir -p $remotePath/data"

scp Dockerfile docker-compose.yml requirements.txt "$remote`:$remotePath/"
scp -r backend "$remote`:$remotePath/"
scp -r configs "$remote`:$remotePath/"

Write-Host "Backend deployment files copied to ${remote}:${remotePath}"
Write-Host "Create $remotePath/.env on the server before running docker compose up -d --build."
