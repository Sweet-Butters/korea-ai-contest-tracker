@echo off
REM Collect the sources GitHub's runners cannot reach, from this PC, and push the result.
REM wevity answers 403 to data-centre IPs but serves normal machines, so it is collected here
REM instead of in CI. Register with scripts\install-task.cmd (daily 07:30).

cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
chcp 65001 >nul

echo [%date% %time%] local sync start
py -m collector.main wevity_only
if errorlevel 1 exit /b 1

git add data
git diff --cached --quiet && (echo no change & exit /b 0)
git -c user.name=sweetbutters -c user.email=pxh7yp@yonsei.ac.kr commit -q -m "data: local sync %date%"
git pull -q --rebase --autostash -X theirs origin main
git push -q origin HEAD:main
echo pushed
