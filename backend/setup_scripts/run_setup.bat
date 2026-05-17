@echo off
echo ============================================================
echo QueryCraft Database Setup
echo ============================================================
echo.
echo Step 1: Creating database and roles...
psql -U postgres -f setup_db.sql
echo.
echo Step 2: Creating tables...
psql -U postgres -d querycraft_db -f create_tables.sql
echo.
echo ============================================================
echo Database setup complete!
echo ============================================================
echo.
echo Credentials:
echo   - nonstop_measure: nonstop123
echo   - querycraft_user: querycraft123
echo.
echo Next: Update backend/.env with:
echo   DB_USER=querycraft_user
echo   DB_PASSWORD=querycraft123
echo.
pause
