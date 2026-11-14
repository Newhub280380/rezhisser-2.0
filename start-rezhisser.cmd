@echo off
rem Rezhisser 2.0: double-click to start and open http://127.0.0.1:7860/
rem   start-rezhisser.cmd -Stop   stops it. No autostart is installed.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-rezhisser.ps1" %*
if errorlevel 1 pause
