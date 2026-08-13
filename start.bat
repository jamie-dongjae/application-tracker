@echo off
rem Application Tracker - double-click launcher (Windows).
cd /d %~dp0
if not exist .venv (
  echo First run - setting things up...
  py -3 -m venv .venv
  .venv\Scripts\pip install --quiet -r requirements.txt
)
.venv\Scripts\python run.py
