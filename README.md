# cpio-tools
cpio format reader/writer written in pure python

## installation
Just clone the repository and install the requirements
```
pip install -r ./requirements.txt
```
## usage
basic usage:
```
cpio-tools.py <archive-path> <command> <command-parameters> <options>
```

The script supports the following commands:
```
- unpack
    Extracts the contents of the archive.
    
    parameters:
        -o <directory> - (optional) directory to be used for the output.
        -f - overwrite directory contents if the output directory already exists
    examples:
        cpio-tools.py ./rootfs.cpio.gz unpack -o /tmp/rootfs
- pack
    Not implemented yet. Packs files into an archive.
- list
    Lists the contents of the archive.

    examples:
        cpio-tools.py ./rootfs.cpio.gz list
- add
    Adds new entry to the archive

    parameters:
        path - path to be used in the archive
        file - local file path to store in the archive
        -o <file> - (optional) file to be used for the output.   
    examples:
        cpio-tools.py ./rootfs.cpio.gz add tmp/test ./test
- delete
    Deletes an entry from the archive
    
    parameters:
        path - path of the file to be deleted
        -o <file> - (optional) file to be used for the output.
    examples:
        cpio-tools.py ./rootfs.cpio.gz delete tmp/test -o /tmp/modified.cpio.gz
 
- modify
    Changes a file inside the archive

    parameters:
        path - path of the file to be modified
        -u/--uid <int> - (optional) change uid to the selected value
        -g/--gid <int> - (optional) change uid to the selected value
        -m/--mode <octal> - (optional) change file access flags; uses octal value as an input (i.e. 755)
        -d/--data <file-path> - (optional) change file contents with the data from the selected file
        -o <directory> - (optional) file to be used for the output.
    examples:
        cpio-tools.py ./rootfs.cpio.gz modify bin/sh -m 04777 
```

It is possible to chain multiple commands in one script call.