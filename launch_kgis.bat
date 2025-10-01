@echo off
REM Se placer dans le dossier du projet
cd /d "%~dp0"

REM Activer l'environnement virtuel
call venv\Scripts\activate.bat

REM Lancer le script Python (avec console visible pour voir les erreurs)
python main.py

REM Garde la console ouverte après la fermeture du script
pause
