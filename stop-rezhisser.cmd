@echo off
rem Stops the Rezhisser server started from this folder (other Python apps are not touched).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-rezhisser.ps1" -Stop %*
