#!/usr/bin/env python3
# coding=utf-8
import logging
import err_hunter

err_hunter.colorConfig()

logger = err_hunter.getLogger(__name__)
logger.info("some info")
logger.warning("some warning")

another_logger = logging.getLogger("yet_another_logger")
another_logger.info("this should be colored")
