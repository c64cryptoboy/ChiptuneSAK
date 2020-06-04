import cbmcodecs

with open("consultant.sng", "rb") as f:
    input = bytearray(f.read())

# Demonstration of decoding as ascii vs decoding as petscii
print(input[0x24:0x2B].decode("petscii-c64en-lc"))
print(input[0x24:0x2B].decode("ascii"))

# Now demonstrate the repr() function:
import exportPRG

print()
print(repr(exportPRG.c64_tokens))
