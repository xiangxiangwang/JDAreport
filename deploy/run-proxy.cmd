@echo off
cd /d "%~dp0.."
"proxy\caddy.exe" run --config "proxy\Caddyfile" >> "logs\proxy.log" 2>&1
