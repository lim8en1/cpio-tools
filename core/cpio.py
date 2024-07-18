import gzip
import pathlib
import random
import string
from io import BytesIO
from typing import BinaryIO

from loguru import logger
from core.cpio_archive import CpioArchive


class Cpio:
    def __init__(self, path: pathlib.Path, use_gzip: bool = True, verbose: bool = False, save_to: pathlib.Path | None = None):
        self._path = path.absolute()
        self._use_gzip = use_gzip
        if not use_gzip:
            self._container = CpioArchive.open(path.absolute())
        else:
            data = gzip.decompress(path.read_bytes())
            self._container = CpioArchive.open(BytesIO(data))
        self._verbose = verbose
        self._changes_pending = False
        self._save_to = save_to

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._changes_pending:
            self.save_changes()

    @staticmethod
    def random_string(length: int = 16, charset: str = string.ascii_letters) -> str:
        return ''.join(random.choices(charset, k=length))

    def unpack(self, output_directory: pathlib.Path | None = None, force: bool = False):
        logger.info(f"Unpack {self._path}")

        if output_directory is None:
            output_directory = pathlib.Path(f'/tmp/{self.random_string()}')
        logger.info(f"Saving files to {output_directory}")

        if not output_directory.exists():
            logger.info(f"Creating directory {output_directory}")
            output_directory.mkdir(parents=True, exist_ok=True)

        if not output_directory.is_dir():
            logger.critical(f'{output_directory} is not a directory')
            return

        if len(tuple(output_directory.iterdir())):
            if force:
                logger.warning(
                    f'{output_directory} is not empty. Rewriting files at destination because of the --force flag')
            else:
                logger.critical(f'{output_directory} is not empty. --force flag is not enabled. Quitting...')
                return

        for entry in self._container.values():
            if self._verbose:
                logger.info(entry.name)
            file_path = output_directory / entry.name
            if entry.is_dir():
                file_path.mkdir(mode=entry.mode, parents=True, exist_ok=True)
            elif entry.is_file():
                if entry.size:
                    if file_path.exists():
                        file_path.unlink()
                    file_path.write_bytes(entry.data)
                else:
                    file_path.touch(exist_ok=True)
                file_path.chmod(entry.mode)
            elif entry.is_symlink():
                if file_path.is_symlink():
                    file_path.unlink(missing_ok=True)
                file_path.symlink_to(entry.data.decode())
            else:
                logger.warning(f"Failed to extract {entry.name}. File type: {entry.file_type}")

    def save_changes(self, output: pathlib.Path | None = None):
        output_stream = BytesIO()
        CpioArchive.write(output_stream, self._container)
        output_stream.seek(0)
        data = output_stream.read()
        output_stream.close()
        if self._use_gzip:
            data = gzip.compress(data, compresslevel=9)
        path = self._path
        if output:
            path = output.absolute()
        elif self._save_to:
            path = self._save_to.absolute()
        elif not self._changes_pending:
            logger.warning(f"No modifications done. Skipping file write")
            return

        logger.info(f"Saving changes to to {path}")
        path.write_bytes(data)
        self._changes_pending = False

    def add_entry(self, file: pathlib.Path, path: str):
        logger.info(f"Add entry {file} to {self._path} [{path}]")
        if not self._container.add_entry(file, path):
            exit(1)
        self._changes_pending = True

    def delete_entry(self, path: str):
        logger.info(f"Delete entry {path} to {self._path}")
        if not self._container.delete_entry(path):
            exit(1)
        self._changes_pending = True

    def modify_entry(self, path: str, uid: int | None = None, gid: int | None = None, mode: int | None = None, data: BinaryIO | None = None):
        logger.info(f"Modify entry {path} in {self._path}")
        if not self._container.modify_entry(
                archive_path=path,
                update_uid=uid,
                update_gid=gid,
                update_mode=mode,
                update_data=data
        ):
            exit(1)
        self._changes_pending = True

    def list_entries(self):
        logger.info(f"Listing entries in {self._path}")
        for entry in self._container.values():
            user = f"{entry.uid}:{entry.gid}"
            print(
                f"{oct(entry.mode).rjust(7)} {user.rjust(12)} {entry.size: 11} {entry.file_type.name.rjust(16)} {entry.name}")

    @staticmethod
    def pack(output: pathlib.Path, source_dir: pathlib.Path):
        logger.info(f"Packing {source_dir} to {output.absolute()}")
        raise NotImplementedError()
