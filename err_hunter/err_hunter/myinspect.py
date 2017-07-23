#!/usr/bin/env python3
# coding=utf-8
import inspect


def getblock(lines):
    """Extract the block of code at the top of the given list of lines."""
    blockfinder = inspect.BlockFinder()
    try:
        tokens = inspect.tokenize.generate_tokens(iter(lines).__next__)
        for _token in tokens:
            blockfinder.tokeneater(*_token)
    except (inspect.EndOfBlock, IndentationError):
        pass
    return lines  # different to builtin inspect is here


def getsourcelines(object):
    """Return a list of source lines and starting line number for an object.

    The argument may be a module, class, method, function, traceback, frame,
    or code object.  The source code is returned as a list of the lines
    corresponding to the object and the line number indicates where in the
    original source file the first line of code was found.  An OSError is
    raised if the source code cannot be retrieved."""
    object = inspect.unwrap(object)
    lines, lnum = inspect.findsource(object)
    
    if inspect.ismodule(object):
        return lines, 0
    else:
        return getblock(lines[lnum:]), lnum + 1
