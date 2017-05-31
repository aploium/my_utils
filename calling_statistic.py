#!/usr/bin/env python3
# coding=utf-8
"""
调用速率统计
支持py3与py2
"""
from __future__ import print_function, division
import time
import functools
import os

try:
    from collections import Callable
except:
    pass


def calling_static(period=1.0, printer=print, timer=None,
                   max_qps=None, qps_resolution=0.05):
    """

    :param period: 打印周期
    :type period: float
    :param printer: 打印函数
    :type printer: Callable
    :param timer: 计时器
    :type timer: Callable
    :param max_qps: 每秒最大调用次数, 用sleep限速
    :type max_qps: int
    :param qps_resolution: qps统计的解析间隔, 单位是秒
    :type qps_resolution: float
    """
    
    def dec(func):
        if timer is None:
            try:
                _timer = time.perf_counter
            except:
                _timer = time.time
        else:
            _timer = timer
        _record = {"checkpoint_spd": _timer(), "count_spd": 0, "total": 0}
        if max_qps:
            _record.update({"checkpoint_qps": _timer(), "count_qps": _timer()})
        start_time = _record["checkpoint_spd"]  # type: float
        
        @functools.wraps(func)
        def _func(*args, **kwargs):
            # -------
            result = func(*args, **kwargs)
            # -------
            
            now = _timer()  # type: float
            _record["count_spd"] += 1
            if max_qps:
                _record["count_qps"] += 1
            _record["total"] += 1
            if now - _record["checkpoint_spd"] > period:
                printer("Timer:func:%s T+%0.3fs Tot:%d Spd:%0.2f/s PID:%d" % (
                    func.__name__, now - start_time, _record["total"],
                    _record["count_spd"] / (now - _record["checkpoint_spd"]),
                    os.getpid()
                ))
                
                _record["checkpoint_spd"] = now
                _record["count_spd"] = 0
            
            if max_qps:
                if (now - _record["checkpoint_qps"]) * max_qps < _record["count_qps"]:
                    time.sleep(now + qps_resolution - _record["checkpoint_qps"])
                    _record["count_qps"] = 0
                    _record["checkpoint_qps"] = now
                
                if now - _record["checkpoint_qps"] > qps_resolution:
                    _record["checkpoint_qps"] = now
                    _record["count_qps"] = 0
            
            return result
        
        return _func
    
    return dec
