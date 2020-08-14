rem path to goattracker executable
IF "%COMPUTERNAME%"=="FIZZYMAGIC" (
   set gtpath=E:\GoatTracker\win32\goattrk2.exe
) ELSE (
   set gtpath=C:\Users\crypt\Desktop\sound\SIDwork\GoatTracker_2.74\win32\goattrk2.exe
)

rem path to stereo GT
IF "%COMPUTERNAME%"=="FIZZYMAGIC" (
   set gtpath2=E:\GoatTracker\gtStereo\win32\gt2stereo.exe
) ELSE (
   set gtpath2=C:\Users\crypt\Desktop\sound\SIDwork\GoatTracker_2.76_Stereo\trunk\win32\gt2stereo.exe
)

rem path to Vice C128
IF "%COMPUTERNAME%"=="FIZZYMAGIC" (
   set vicepath=E:\GTK3VICE-3.4-win64-r37296\x128.exe
) ELSE (
   set vicepath=C:\Users\crypt\Desktop\retro8-bit\c64\WinVICE-3.1-x86\x128.exe
)


rem Demo 1: Mercantile
python ..\examples\mercantile.py
echo Hit any key to load PDF
pause
start /wait ..\examples\data\mercantile\mercantile.pdf
echo Hit any key to load GoatTracker song
pause
start /wait %gtpath% -N ..\examples\data\mercantile\mercantile.sng

rem Demo 2: LeChuck
python ..\examples\lechuck.py
echo Hit any key to load stereo GoatTracker song
pause
start /wait %gtpath2% -P ..\examples\data\lechuck\lechuck.sng

rem Demo 3: Skyfox SID import
python ..\examples\tripletExample.py
echo Hit any key to listen to extracted MIDI
pause
start ..\examples\data\triplets\Skyfox.mid
echo Hit any key to see unmodulated PDF
pause
start /wait ..\examples\data\triplets\Skyfox.pdf
echo Hit any key to see modulated PDF
pause
start /wait ..\examples\data\triplets\skyfox_mod.pdf

rem Demo 4: C128
echo Hit any key to load buggy BWV_784
pause
start /wait %vicepath% -ntsc -basicload BWV_784_buggy.prg
python ..examples/c128_2_Voice_From_Manual.py
echo Hit any key to load Vice C128 program
pause
start /wait %vicepath% -ntsc -basicload ..\examples\data\C128\BWV_784.prg
python ..examples/c128_3_Voice_Example.py
echo Hit any key to load Vice C128 program
pause
start /wait %vicepath% -ntsc -basicload ..\examples\data\C128\BWV_799.prg

