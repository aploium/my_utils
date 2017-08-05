#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals, division
import sys
import time
import functools
import logging

from concurrent.futures import TimeoutError

logger = logging.getLogger(__name__)

if sys.version_info[0] == 2:
    import itertools
    
    izip = itertools.izip
else:
    izip = zip


def _find_oldest_task(taskset):
    return min(x[1] for x in taskset)


def base_buffmap(executor, fn, *iterables, **kwargs):
    """
    增强版的 concurrent.futures.Executor.map()
     - 丢弃已完成的任务参数, 在长队列时显著节约内存(相对原版)
     - 半乱序执行
     - 一边运行一边展开 iterables
     - 支持传入全局的kv参数 common_kwargs
     - 避免子进程/线程意外挂掉后出现zombie进程导致主进程进入无限等待 (需要配合timeout)
     - 自动shutdown
    """
    common_kwargs = kwargs.pop("common_kwargs", {})
    buffsize = kwargs.pop("buffsize", executor._max_workers * 2 + 5)
    check_interval = kwargs.pop("check_interval", 2)
    timeout = kwargs.pop("timeout", None)
    
    if "chunksize" in kwargs:
        del kwargs["chunksize"]
    
    if kwargs:
        raise ValueError("unknown kwargs: {}".format(kwargs))
    
    taskset = set()
    
    _iter = izip(*iterables)
    _oldest_time = time.time()
    
    def _fill_taskset():
        while len(taskset) < buffsize:
            try:
                args = next(_iter)
            except StopIteration:
                return
            taskset.add((
                executor.submit(fn, *args, **common_kwargs),
                time.time() if timeout is not None else None,
            ))
    
    _fill_taskset()
    
    _sleep_interval = 0
    _done_tasks = []
    try:
        while taskset:
            for task in taskset:
                # 遍历检查任务是否已完成
                if task[0].done():
                    # 若完成则先记录, 之后再挨个挑出
                    _done_tasks.append(task)
            for task in _done_tasks:
                taskset.remove(task)
            
            if timeout is not None:
                if _oldest_time - time.time() > timeout:
                    # 找出最古老的任务
                    #   仅当上次记录的时间超时了才真正找出最老任务
                    #   可以减少计算量.
                    #   因为如果旧记录中最老的都没有超时, 后面新的就更加不会
                    _oldest_time = _find_oldest_task(taskset)
                    
                    if _oldest_time - time.time() > timeout:
                        # 超时就抛出错误
                        raise TimeoutError("timeout in running executor")
            
            _fill_taskset()  # 先填充再yield结果, 减少时间浪费
            
            for task in _done_tasks:
                yield task[0].result()
            
            if not _done_tasks:  # 没有结果就持续等待...
                time.sleep(_sleep_interval)
                if _sleep_interval < check_interval:
                    _sleep_interval += check_interval / 10.0
            else:
                _sleep_interval = 0
                _done_tasks = []
    finally:
        for task in taskset:
            task[0].cancel()
        for task in _done_tasks:
            task[0].cancel()
        
        executor.shutdown(wait=False)


thread_buffmap = base_buffmap


def _get_chunks(chunksize, *iterables):
    """ copy from python 3.6.1 `concurrent.futures.process._get_chunks` """
    it = izip(*iterables)
    while True:
        chunk = tuple(itertools.islice(it, chunksize))
        if not chunk:
            return
        yield chunk


def _process_chunk(fn, chunk):
    """copy from python 3.6.1 `concurrent.futures.process._process_chunk` """
    return [fn(*args) for args in chunk]


def process_buffmap(executor, fn, *iterables, **kwargs):
    """
    增强版的 concurrent.futures.process.ProcessPoolExecutor.map()
      - 在 py2 下支持 chunksize
      - 出错时自动杀死子进程
    """
    chunksize = kwargs.pop("chunksize", 1)
    if chunksize < 1:
        raise ValueError("chunksize must be >= 1.")
    
    results = base_buffmap(
        executor,
        functools.partial(_process_chunk, fn),
        _get_chunks(chunksize, *iterables),
        **kwargs
    )
    _processes = executor._processes
    try:
        return itertools.chain.from_iterable(results)
    except:
        for p in _processes:
            try:
                p.terminate()
            except:
                logger.warning("unable to shutdown subprocess {}".format(p), exc_info=True)
        
        raise


def process_executor_shutdown(executor, wait=True):
    import multiprocessing
    multiprocessing.Process.is_alive()
    for p in executor._processes:
        try:
            p.terminate()
        except:
            logger.warning("unable to shutdown subprocess {}".format(p), exc_info=True)
    executor.shutdown(wait=wait)
