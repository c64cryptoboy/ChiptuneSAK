set gtdir=E:\GoatTracker\win32
set gtdir2=E:\GoatTracker\gtStereo\win32
set vicedir=E:\GTK3VICE-3.4-win64-r37296

rem Demo 1: Mercantile
python ..\examples\mercantile.py
echo Hit any key to load PDF
pause
start /wait ..\examples\data\mercantile\mercantile.pdf
echo Hit any key to load GoatTracker song
pause
start /wait %gtdir%\goattrk2.exe ..\examples\data\mercantile\mercantile.sng

rem Demo 2: LeChuck
python ..\examples\lechuck.py
echo Hit any key to load stereo GoatTracker song
pause
start /wait %gtdir2%\gt2stereo.exe ..\examples\data\lechuck\lechuck.sng

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
start /wait %vicedir%\x128.exe ..\examples\data\C128\BWV_799.prg

