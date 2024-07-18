#!/usr/bin/python3
import argparse
import enum
import pathlib
from loguru import logger
from core.custom_enum import CustomEnum
from core.cpio import Cpio


class Commands(CustomEnum):
    unpack = enum.auto()
    pack = enum.auto()
    list = enum.auto()
    add = enum.auto()
    delete = enum.auto()
    modify = enum.auto()


def parse(args: list) -> list:
    cmds = []
    cmd = None
    for arg in args:
        if Commands.has_value(arg):
            if cmd is not None:
                cmds.append(cmd)
            cmd = [arg]
        else:
            if cmd is not None:
                cmd.append(arg)
            else:
                logger.critical(f"Failed to parse argument {arg}")
                exit(1)
    cmds.append(cmd)
    return cmds

def custom_help() -> str:
    return """Usage: cpio-tools.py <archive-path> <command> <parameters>
    
Commands:
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
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.format_help = custom_help
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--no-gzip', '-G', action='store_false')
    parser.add_argument("archive", type=pathlib.Path)
    parser.add_argument("--output", "-o", type=pathlib.Path)
    command_parser = argparse.ArgumentParser()

    parsers = command_parser.add_subparsers(dest="command", required=True)

    unpack_parser = parsers.add_parser(Commands.unpack.name)
    unpack_parser.add_argument("--force", "-f", action="store_true")
    unpack_parser.format_usage = custom_help

    pack_parser = parsers.add_parser(Commands.pack.name)
    pack_parser.format_usage = custom_help

    list_parser = parsers.add_parser(Commands.list.name)
    list_parser.format_usage = custom_help

    add_parser = parsers.add_parser(Commands.add.name)
    add_parser.add_argument("path", type=str)
    add_parser.add_argument("file", type=pathlib.Path)
    add_parser.format_usage = custom_help

    delete_parser = parsers.add_parser(Commands.delete.name)
    delete_parser.add_argument("path", type=str)
    delete_parser.format_usage = custom_help

    modify_parser = parsers.add_parser(Commands.modify.name)
    modify_parser.add_argument("path", type=str)
    modify_parser.add_argument("-u", "--uid", type=int)
    modify_parser.add_argument("-g", "--gid", type=int)
    modify_parser.add_argument("-m", "--mode", type=lambda x: int(x, 8))
    modify_parser.add_argument("-d", "--data", type=argparse.FileType('rb'))
    modify_parser.format_usage = custom_help

    args, rest = parser.parse_known_args()

    command_line_tasks = parse(rest)
    with Cpio(args.archive, args.no_gzip, save_to=args.output) as cpio:
        for task in command_line_tasks:
            task_args = command_parser.parse_args(task)
            command = Commands(task_args.command)
            match command:
                case Commands.list:
                    cpio.list_entries()
                case Commands.pack:
                    cpio.pack(task_args.output, task_args.source_dir)
                case Commands.add:
                    cpio.add_entry(task_args.file, task_args.path)
                case Commands.delete:
                    cpio.delete_entry(task_args.path)
                case Commands.modify:
                    cpio.modify_entry(task_args.path, task_args.uid, task_args.gid, task_args.mode, task_args.data)
                case Commands.unpack:
                    cpio.unpack(args.output, task_args.force)
                case _:
                    raise ValueError("Unknown command")
