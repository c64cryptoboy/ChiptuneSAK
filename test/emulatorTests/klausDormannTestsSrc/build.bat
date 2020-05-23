@echo off
ca65 -l 6502_decimal_test.lst 6502_decimal_test.ca65
ld65 6502_decimal_test.o -o 6502_decimal_test.bin -m 6502_decimal_test.map -C config.cfg
rem config.cfg from https://github.com/amb5l/6502_65C02_functional_tests/blob/master/ca65/example.cfg


