import dataclasses
import enum
import pathlib
import time
from collections import OrderedDict
from typing import BinaryIO

from loguru import logger
from pybinary.binary_types import ArrayTypes
from pybinary.serializable import BinarySerializable


class CpioNewcHeader(BinarySerializable):
    c_magic = ArrayTypes.bytearray(6)
    c_ino = ArrayTypes.bytearray(8)
    c_mode = ArrayTypes.bytearray(8)
    c_uid = ArrayTypes.bytearray(8)
    c_gid = ArrayTypes.bytearray(8)
    c_nlink = ArrayTypes.bytearray(8)
    c_mtime = ArrayTypes.bytearray(8)
    c_filesize = ArrayTypes.bytearray(8)
    c_dev = ArrayTypes.bytearray(32)
    c_namesize = ArrayTypes.bytearray(8)
    c_check = ArrayTypes.bytearray(8)


class ModeMask:
    file_type = 0o170000
    permissions = 0o7777


class FileTypes(enum.Enum):
    directory = 0o40000
    named_pipe = 0o10000
    regular = 0o100000
    symlink = 0o120000
    block_device = 0o60000
    char_device = 0o20000
    socket = 0o140000


@dataclasses.dataclass
class CpioEntry:
    name: str = ''
    data: bytes = b''
    mode: int = 0
    file_type: FileTypes = FileTypes.regular
    uid: int = 0
    gid: int = 0
    number_of_links: int = 0
    modification_time: time.time = time.time()
    size: int = 0
    has_crc: bool = False
    inode: int = 0
    dev: bytes = b'0' * 32

    def is_dir(self) -> bool:
        return self.file_type == FileTypes.directory

    def is_file(self) -> bool:
        return self.file_type == FileTypes.regular

    def is_symlink(self) -> bool:
        return self.file_type == FileTypes.symlink


class CpioEntryContainer(OrderedDict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._inodes = set()
        self._inode_next = 0

    def add_entry(self, path: pathlib.Path, archive_path: str):
        if not path.exists():
            logger.critical(f"Failed to access file {path}. The file does not exist.")
            return False
        parent = pathlib.Path(archive_path).parent
        if str(parent) not in self:
            logger.critical(f"{parent} not in the archive. Failed to add {archive_path}")
            return False

        stat = path.stat(follow_symlinks=False)
        if archive_path in self:
            logger.warning(f"Overwriting {archive_path}")
            inode = self[archive_path].inode
            dev = self[archive_path].dev
        else:
            inode = self._inode_next
            dev = b'0' * 32
        entry = CpioEntry(
            name=archive_path,
            mode=stat.st_mode,
            uid=stat.st_uid,
            gid=stat.st_gid,
            number_of_links=stat.st_nlink,
            modification_time=stat.st_mtime,
            inode=inode,
            dev=dev
        )
        if path.is_file():
            entry.file_type = FileTypes.regular
            entry.data = path.read_bytes()
        elif path.is_symlink():
            entry.file_type = FileTypes.symlink
            entry.data = str(path.readlink()).encode()
        elif path.is_dir():
            entry.file_type = FileTypes.directory
        else:
            raise NotImplementedError()
        entry.size = len(entry.data)
        self[archive_path] = entry
        return True

    def __setitem__(self, key: str, value: CpioEntry):
        if not isinstance(value, CpioEntry):
            raise ValueError("CpioEntry expected")
        self._inode_next = max(self._inode_next, value.inode + 1)
        super().__setitem__(key, value)

    def delete_entry(self, archive_path: str):
        if archive_path in self:
            logger.info(f"Removing {archive_path} from the archive")
            self.pop(archive_path)
            return True
        else:
            logger.warning(f"{archive_path} not found in the archive")
            return False

    def modify_entry(self, archive_path: str, update_uid: None|int = None, update_gid: None|int = None, update_mode: None|int = None, update_data: None|BinaryIO = None):
        updated = False
        if archive_path in self:
            logger.info(f"Modifying {archive_path} in the archive")
            if update_data is not None:
                if self[archive_path].file_type == FileTypes.regular:
                    logger.info(f"{archive_path} : updated data")
                    self[archive_path].data = update_data.read()
                    self[archive_path].size = len(self[archive_path].data)
                    updated = True
                else:
                    logger.error(f"Failed to update data for {archive_path}. Reason: not a regular file.")
            if update_uid is not None:
                logger.info(f"{archive_path} : [uid] {self[archive_path].uid} => {update_uid}")
                self[archive_path].uid = update_uid
                updated = True
            if update_gid is not None:
                logger.info(f"{archive_path} : [gid] {self[archive_path].gid} => {update_gid}")
                self[archive_path].gid = update_gid
                updated = True
            if update_mode is not None:
                logger.info(f"{archive_path} : [mode] {oct(self[archive_path].mode)} => {oct(update_mode)}")
                self[archive_path].mode = update_mode
                updated = True
        else:
            logger.critical(f"{archive_path} not found in the archive")
        return updated


class CpioArchive:
    trailer_signature = 'TRAILER!!!'
    @classmethod
    def open(cls, file: pathlib.Path|BinaryIO|str) -> CpioEntryContainer:
        def __handle_padding(data_stream: BinaryIO, data_read: int) -> int:
            padding = (4 - (data_read % 4)) % 4
            data_stream.read(padding)
            return padding
        if  isinstance(file, pathlib.Path) or isinstance(file, str):
            if isinstance(file, str):
                file = pathlib.Path(file)
            with file.open('rb') as bytestream:
                return cls.open(bytestream)

        data_processed = 0
        entries = CpioEntryContainer()
        while True:
            header = CpioNewcHeader.deserialize(file)
            data_processed += CpioNewcHeader.size()

            if header.c_magic.startswith(b'070701'):
                has_crc = False
            elif header.c_magic.startswith(b'070702'):
                has_crc = True
            else:
                raise ValueError(f"Wrong magic: {header.c_magic}")

            data_size = int(header.c_filesize, 16)
            name_size = int(header.c_namesize, 16)
            mode_raw = int(header.c_mode, 16)
            inode = int(header.c_ino, 16)
            uid = int(header.c_uid, 16)
            gid = int(header.c_gid, 16)
            nlinks = int(header.c_nlink, 16)
            mtime = int(header.c_mtime, 16)
            name = file.read(name_size)[:-1].decode()
            if len(name) < name_size-1:
                logger.warning(f"{name} (expected: {name_size-1}, actual: {len(name)})")
            data_processed += name_size
            data_processed += __handle_padding(file, data_processed)
            if name == cls.trailer_signature:
                break
            entries[name] = CpioEntry(
                name=name,
                data=file.read(data_size),
                mode=mode_raw & ModeMask.permissions,
                file_type=FileTypes(mode_raw & ModeMask.file_type),
                uid=uid,
                gid=gid,
                number_of_links=nlinks,
                modification_time=mtime,
                size=data_size,
                has_crc=has_crc,
                inode=inode,
                dev=header.c_dev
            )
            if len(entries[name].data) < data_size:
                raise ValueError("Failed to read file data")
            data_processed += data_size
            data_processed += __handle_padding(file, data_processed)
        return entries

    @classmethod
    def write(cls, file: pathlib.Path|BinaryIO|str, entries: CpioEntryContainer):
        def __handle_padding(data_stream: BinaryIO, data_written: int) -> int:
            padding = (4 - (data_written % 4)) % 4
            data_stream.write(padding*b'\0')
            return padding

        if isinstance(file, pathlib.Path) or isinstance(file, str):
            if isinstance(file, str):
                file = pathlib.Path(file)
            with file.open('wb') as bytestream:
                return cls.write(bytestream, entries)

        bytes_written = 0
        for entry in entries.values():
            header = CpioNewcHeader()
            if entry.has_crc:
                header.c_magic = b'070702'
                header.c_check = f'{sum(x for x in entry.data) & 0xFFFFFFFF:08x}'.encode()
            else:
                header.c_magic = b'070701'
                header.c_check = b'00000000'
            header.c_filesize = f'{len(entry.data):08x}'.encode()
            name_encoded = entry.name.encode() + b'\0'
            header.c_namesize = f'{len(name_encoded):08x}'.encode()
            header.c_mode = f'{entry.mode | entry.file_type.value:08x}'.encode()
            header.c_uid = f'{entry.uid:08x}'.encode()
            header.c_gid = f'{entry.gid:08x}'.encode()
            header.c_nlink = f'{entry.number_of_links:08x}'.encode()
            header.c_mtime = f'{int(entry.modification_time):08x}'.encode()
            header.c_ino = f'{entry.inode:08x}'.encode()
            header.c_dev = entry.dev
            file.write(header.serialize())
            bytes_written += header.size()
            file.write(name_encoded)
            bytes_written += len(name_encoded)
            bytes_written += __handle_padding(file, bytes_written)
            file.write(entry.data)
            bytes_written += len(entry.data)
            bytes_written += __handle_padding(file, bytes_written)
        header = CpioNewcHeader()
        name_encoded = cls.trailer_signature.encode() + b'\0'
        header.c_namesize = f'{len(name_encoded):08x}'.encode()
        header.c_magic = b'070701'
        header.c_check = b'00000000'
        header.c_filesize = b'00000000'
        header.c_namesize = f'{len(name_encoded):08x}'.encode()
        header.c_mode = b'00000000'
        header.c_uid = b'00000000'
        header.c_gid = b'00000000'
        header.c_nlink = b'00000000'
        header.c_mtime = b'00000000'
        header.c_ino = b'00000000'
        header.c_dev = b'0' * 32
        file.write(header.serialize())
        bytes_written += header.size()
        file.write(name_encoded)
        bytes_written += len(name_encoded)
        bytes_written += __handle_padding(file, bytes_written)
