#
# Run the unit tests for the entire project.  They are python files in the test direcyory with names that end in 'test'
#

from subprocess import run

output = run(['python', '-m', 'unittest', 'discover', '-p', '*Test.py', '-v'], capture_output=True)

print(output.stderr.decode('ascii', 'ignore'))
