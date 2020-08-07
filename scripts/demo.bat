
rem path to goattracker executable
set gtpath=E:\GoatTracker\win32\goattrk2.exe
rem path to stereo GT
set gtpath2=E:\GoatTracker\gtStereo\win32\gt2stereo.exe
rem path to Vice C128
set vicedir=E:\GTK3VICE-3.4-win64-r37296\x128.exe

rem Demo 1: Mercantile
python ..\examples\mercantile.py
echo Hit any key to load PDF
pause
start /wait ..\examples\data\mercantile\mercantile.pdf
echo Hit any key to load GoatTracker song
pause
start /wait %gtpath% ..\examples\data\mercantile\mercantile.sng

rem Demo 2: LeChuck
python ..\examples\lechuck.py
echo Hit any key to load stereo GoatTracker song
pause
start /wait %gtpath2% ..\examples\data\lechuck\lechuck.sng

rem Demo 3: Skyfox SID import
python ..\examples\tripletExample.py
echo Hit any key to see unmodulated PDF
pause
start /wait ..\examples\data\triplets\Skyfox.pdf
echo Hit any key to see modulated PDF
pause
start /wait ..\examples\data\triplets\skyfox_mod.pdf

rem Demo 4: C128
python ..\examples\c128basicExample.py
echo Hit any key to load Vice C128 program
pause
start /wait %viceath% ..\examples\data\C128\BWV_799.prg

