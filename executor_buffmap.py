#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals, division
import sys
import time

if sys.version_info[0] == 2:
    import itertools
    
    izip = itertools.izip
else:
    izip = zip


def thread_buffmap(executor, fn, *iterables, **kwargs):
    common_kwargs = kwargs.pop("common_kwargs", {})
    buffsize = kwargs.pop("buffsize", executor._max_workers * 2 + 5)
    check_interval = kwargs.pop("check_interval", 2)
    
    if kwargs:
        raise ValueError("unknown kwargs: {}".format(kwargs))
    
    taskset = set()
    
    _iter = izip(*iterables)
    
    def _fill_taskq():
        while len(taskset) < buffsize:
            try:
                args = next(_iter)
            except StopIteration:
                return
            taskset.add(executor.submit(fn, *args, **common_kwargs))
    
    _fill_taskq()
    
    _sleep_interval = 0
    _done_tasks = []
    while taskset:
        
        for task in taskset:
            if task.done():
                _done_tasks.append(task)
        for task in _done_tasks:
            taskset.remove(task)
        
        _fill_taskq()
        
        for task in _done_tasks:
            yield task.result()
        
        if not _done_tasks:
            time.sleep(_sleep_interval)
            if _sleep_interval < check_interval:
                _sleep_interval += check_interval / 10.0
        else:
            _sleep_interval = 0
            _done_tasks = []
