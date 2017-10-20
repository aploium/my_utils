#!/usr/bin/env python3
# coding=utf-8
import err_hunter

err_hunter.basicConfig("INFO", logfile="file.log", file_level="DEBUG",
                       maxBytes=1024 * 1024, backupCount=5,
                       )

logger = err_hunter.getLogger()

logger.error("err")
logger.warning("warning")
logger.info("info")
logger.debug("debug, only appears in file.log")

logger.info("please see `file.log` for filelog")

for i in range(50000):
    logger.info("info %s", i)
    logger.debug("debug %s", i)
