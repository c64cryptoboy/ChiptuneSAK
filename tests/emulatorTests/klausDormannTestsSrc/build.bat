@echo off
ca65 -l ..\\klausDormannTestsBin\\6502_decimal_test.lst 6502_decimal_test.ca65
ld65 6502_decimal_test.o -o ..\\klausDormannTestsBin\\6502_decimal_test.bin -m ..\\klausDormannTestsBin\\6502_decimal_test.map -C config.cfg
REM TODO: I'm fighting the config.cfg, I don't think the FE_TO_1FF_PAD shouldn't be necessary to get code to start at $0200.


