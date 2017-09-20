#!/usr/bin/env python3
# coding=utf-8
import err_hunter

err_hunter.colorConfig("NOISE")

log = err_hunter.getLogger()

log.info("info")
log.verbose("verbose is lower than info but higher than debug")
log.debug("debug level")
log.trace("trace is lower than debug level")
log.noise("noise is more lower")
log.lowest("the lowest level, this will not be displayed here")
