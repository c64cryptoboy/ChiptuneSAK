set gtdir=E:\GoatTracker\win32
set gtdir2=E:\GoatTracker\gtStereo\win32
set vicedir=E:\GTK3VICE-3.4-win64-r37296

rem Demo 1: Mercantile
python ..\examples\mercantile.py
start /wait %gtdir%\goattrk2.exe ..\examples\data\mercantile\mercantile.sng

rem Demo 2: LeChuck
python ..\examples\lechuck.py
start /wait %gtdir2%\gt2stereo.exe ..\examples\data\lechuck\lechuck.sng

rem Demo 3: SID import

rem Demo 4: C128
python ..\examples\c128basicExample.py
start /wait %vicedir%\x128.exe ..\examples\data\C128\BWV_799.prg

