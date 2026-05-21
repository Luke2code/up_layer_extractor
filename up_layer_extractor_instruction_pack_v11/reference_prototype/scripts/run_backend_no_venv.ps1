$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location (Join-Path $Root "v18_backend_url_intake")
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ".\backend\requirements.txt"
python ".\backend\up_layer_extractor_service.py"
