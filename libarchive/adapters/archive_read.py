import contextlib
import ctypes
import logging

import libarchive.calls.archive_read
import libarchive.calls.archive_write
import libarchive.calls.archive_general
import libarchive.adapters.archive_entry
import libarchive.constants.archive

_logger = logging.getLogger(__name__)

def _archive_read_new():
    return libarchive.calls.archive_read.c_archive_read_new()

def _archive_read_support_filter_all(archive):
    return libarchive.calls.archive_read.c_archive_read_support_filter_all(
            archive)

def _archive_read_support_format_all(archive):
    return libarchive.calls.archive_read.c_archive_read_support_format_all(
            archive)

def _archive_read_support_format_7zip(archive):
    return libarchive.calls.archive_read.c_archive_read_support_format_7zip(
            archive)

def _archive_read_open_filename(archive, filepath, block_size_bytes):
    return libarchive.calls.archive_read.c_archive_read_open_filename(
            archive, 
            filepath, 
            block_size_bytes)

@contextlib.contextmanager
def _archive_read_next_header(archive):
    entry = ctypes.c_void_p()
    r = libarchive.calls.archive_read.c_archive_read_next_header(
            archive, 
            ctypes.byref(entry))

    if r == libarchive.constants.archive.ARCHIVE_OK:
        yield entry
    elif r == libarchive.constants.archive.ARCHIVE_EOF:
        yield None
    else:
        raise ValueError("Archive iteration returned error: %d" % (r))

def _archive_read_data_skip(entry):
    return libarchive.calls.archive_read.c_archive_read_data_skip(entry)

def _archive_read_free(archive):
    return libarchive.calls.archive_read.c_archive_read_free(archive)

def _archive_write_set_format_7zip(archive):
    return libarchive.calls.archive_read.c_archive_write_set_format_7zip(archive)

_READ_FILTER_MAP = {
        'all': _archive_read_support_filter_all,
    }

_READ_FORMAT_MAP = {
        'all': _archive_read_support_format_all,
        '7z': _archive_read_support_format_7zip,
    }

def _set_read_context(archive_res, filter_name, format_name):
    _filter = _READ_FILTER_MAP[filter_name]        
    r = _filter(archive_res)
    _logger.debug("Filter [%s] returned: %d", _filter, r)

    _format = _READ_FORMAT_MAP[format_name]
    r = _format(archive_res)
    _logger.debug("Format [%s] returned: %d", _format, r)

@contextlib.contextmanager
def reader(filepath, block_size=10240, filter_name='all', format_name='all'):
    """Get a generator with which to enumerate the entries."""

    _logger.info("Reading through archive: %s", filepath)

    archive_res = _archive_read_new()
    _logger.debug("Created archive resource (archive_read_new).")

    try:
        r = _set_read_context(archive_res, filter_name, format_name)

        r = _archive_read_open_filename(archive_res, filepath, block_size)
        _logger.debug("archive_read_open_filename: (%d) %s", r, filepath)

        def it():
            while 1:
                with _archive_read_next_header(archive_res) as entry_res:
                    if entry_res is None:
                        break

                    yield libarchive.adapters.archive_entry.ArchiveEntry(
                            archive_res, 
                            entry_res)

                    _archive_read_data_skip(archive_res)

        yield it()
    finally:
        _archive_read_free(archive_res)

def pour(filepath, 
         flags=0, 
         *args, 
         **kwargs):
    """Write the archive out to the current directory."""

    _logger.info("Pouring archive: %s", filepath)

    with reader(filepath, *args, **kwargs) as r:
        ext = libarchive.calls.archive_write.c_archive_write_disk_new()
        libarchive.calls.archive_write.c_archive_write_disk_set_options(
                ext,
                flags
            )

        for entry in r:
            r = libarchive.calls.archive_write.c_archive_write_header(
                    ext, 
                    entry.entry_res)

            buff = ctypes.c_void_p()
            size = ctypes.c_size_t()
            offset = ctypes.c_longlong()

            while 1:
                r = libarchive.calls.archive_read.\
                        c_archive_read_data_block(
                            entry.reader_res, 
                            ctypes.byref(buff), 
                            ctypes.byref(size), 
                            ctypes.byref(offset))

                if r == libarchive.constants.archive.ARCHIVE_EOF:
                    break
                elif r != libarchive.constants.archive.ARCHIVE_OK:
                    raise ValueError("Pour failed: %d" % (r))

                r = libarchive.calls.archive_write.\
                        c_archive_write_data_block(
                            ext, 
                            buff, 
                            size, 
                            offset)

            r = libarchive.calls.archive_write.\
                    c_archive_write_finish_entry(ext)

            yield entry

