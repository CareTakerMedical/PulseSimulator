#! python

from git import Repo
import os, re, shutil
import tempfile as tf
import PyInstaller.__main__

cwd = os.getcwd()
# Make sure we're in a directory that makes sense
rem = re.search("PSApp$",cwd)
if not rem:
    raise SystemExit("Please run this script from the 'PSApp' directory.")

# Blow away the 'dist' directory; otherwise the next step will fail
try:
    shutil.rmtree("./dist/PulseSimulatorApp.exe/")
except:
    pass

# Make sure we're in a 'git' repository; it will be one level down from where we are
repo = Repo(search_parent_directories=True)

# Check to make sure that the code present in the repository has been committed
if repo.is_dirty():
    raise SystemExit("Please commit any changes or clean up the working directory before running this script.")

# Now get the version
version = repo.head.commit.hexsha[:8]

# Move 'PSAppVersion.py' off to the side somewhere for now.
temp_file = os.path.join(tf.gettempdir(),'PSAppVersion.py')
shutil.copy2('PSAppVersion.py',temp_file)

# Open up the version file
with open("PSAppVersion.py","w") as fh:
    print('def get_psapp_version():\n\treturn "{}"'.format(version),file=fh)

# Now run PyInstaller
try:
    PyInstaller.__main__.run([
        '__main__.py',
        '--onedir',
        '--windowed',
        '--add-data=res/*;res/',
        '--icon=./icons/PulseSimulatorApp.ico',
        '--name=PulseSimulatorApp.exe'
    ])
    # If this was successful, move the '.spec' file to the temp directory, and print
    # out the name, since I'd rather not have it in the working directory, but I may want to refer to it
    # if something is fishy with the executable.
    temp_spec = os.path.join(tf.gettempdir(),'PulseSimulatorApp.spec')
    shutil.move('PulseSimulatorApp.exe.spec',temp_spec)
except Exception as e:
    print("Exception encountered during creation of executable file:")
    if hasattr(e,'message'):
        print(e.message)
    else:
        print(e)
finally:
    shutil.copy2(temp_file,'PSAppVersion.py')
