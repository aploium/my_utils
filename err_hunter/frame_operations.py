#!/usr/bin/env python3
# coding=utf-8
import sys
import inspect
from err_hunter.attr import attributes
from err_hunter import myinspect

PY2 = (sys.version_info[0] == 2)


def real_frame_extract(subframe, filepath, lineno):
    """
    :type subframe: inspect.FrameInfo
    :rtype: inspect.FrameInfo
    """
    frames = inspect.getouterframes(subframe)
    for frame in frames:
        if PY2:
            if frame[1] == filepath and frame[2] == lineno:
                return frame[0]  # type: inspect.FrameInfo
        elif frame.filename == filepath and frame.lineno == lineno:
            return frame.frame  # type: inspect.FrameInfo
    
    return None


def frame_format(frame, interested=None, linerange=5, frame_lineno=None):
    abs_path = frame.f_code.co_filename
    func_name = frame.f_code.co_name
    
    global_vars = attributes(frame.f_globals, from_dict=True, interested=interested)
    local_vars = attributes(frame.f_locals, from_dict=True, interested=interested)
    
    frame_lineno = frame_lineno or frame.f_lineno
    source_lines, first_lineno = myinspect.getsourcelines(frame.f_code)
    source_lines[frame_lineno - first_lineno] = "--->" \
                                                + source_lines[frame_lineno - first_lineno].rstrip("\r\n ") \
                                                + "  <---\n"
    source_lines = source_lines[
                   max(0, frame_lineno - first_lineno - linerange)
                   : frame_lineno - first_lineno + linerange
                   ]
    source_lines = "".join(("    " + x if not x.startswith("-") else x) for x in source_lines)
    
    text = """Frame {abs_path}, line {frame_lineno}, in {func_name}
{source_lines}
#----global_vars----#
{global_vars}
#----local_vars----#
{local_vars}
#------------------#""".format(
        abs_path=abs_path, frame_lineno=frame_lineno, func_name=func_name,
        source_lines=source_lines, global_vars=global_vars.rstrip(), local_vars=local_vars.rstrip()
    )
    return text
