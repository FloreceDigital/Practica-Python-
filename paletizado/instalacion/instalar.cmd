@echo off
rem Doble clic para instalar o actualizar el Registro de tarimas.
rem Pide permiso de Administrador y corre instalar_windows.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File \"%~dp0instalar_windows.ps1\"'"
