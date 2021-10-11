#! python

from git import Repo
import sys

# Don't try to get fancy here, just run from this directory and assume that it's the repo we want
repo = Repo(search_parent_directories=True)
dirty = repo.is_dirty()
version = repo.head.commit.hexsha[:8]

oso = sys.stdout
# Create the header file with the version information in it.
with open("ps_version.h","w") as fh:
    sys.stdout = fh
    print('#ifndef PS_VERSION_H_\n#define PS_VERSION_H_\n')
    print('#define DIRTY\t{}\n'.format(1 if dirty else 0))
    print("char fw_version[{}] = {{".format(8),end='')
    for i in range(7):
        print("'{}', ".format(version[i]),end='')
    print("'{}'}};".format(version[7]))
    print("#endif /* PS_VERSION_H_ */")
    sys.stdout = oso
