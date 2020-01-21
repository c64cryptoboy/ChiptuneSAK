from subprocess import run

output = run(['python', '-m', 'unittest', 'discover', '-p', '*Test.py', '-v'], capture_output=True)

print(output.stderr.decode('ascii', 'ignore'))