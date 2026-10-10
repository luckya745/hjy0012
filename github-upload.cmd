@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>nul
if errorlevel 1 goto missing
if not exist ".git" goto archive
git push -u origin main
if errorlevel 1 echo Upload failed. Complete GitHub sign-in and retry.
pause
exit /b
:archive
echo This is a source ZIP without Git history.
echo Upload the extracted files and folders to https://github.com/luckya745/hjy0012
pause
exit /b
:missing
echo Git for Windows is required for command-line upload.
pause
