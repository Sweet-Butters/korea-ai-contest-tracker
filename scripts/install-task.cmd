@echo off
REM Register (or replace) the daily local sync at 07:30, after the 06:00 KST CI run.
REM Remove later:  schtasks /delete /tn "ai-contest-radar-local-sync" /f
schtasks /create /tn "ai-contest-radar-local-sync" /tr "\"%~dp0local-sync.cmd\"" /sc daily /st 07:30 /f
schtasks /query /tn "ai-contest-radar-local-sync" /fo list | findstr /i "TaskName Next"
