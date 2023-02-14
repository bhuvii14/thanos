"""
Manage a apache_exporter instance.
"""
import os
import argparse
import logging
import atexit
import signal

from twisted.internet import defer, reactor

from ims.proxycontrol import process
from ims.util import pjoin, dryrun, spawn
from ims.monitoring import defaults
from ims.infrastructure import utils, common

log = logging.getLogger(__name__)

class ApacheExporterProcess(common.BaseProcess):
    """
    apache_exporter process protocol.
    """
    executable = defaults.APACHE_EXPORTER_EXE

    def __init__(self,
                 uid=defaults.APACHE_EXPORTER_UID,
                 gid=defaults.APACHE_EXPORTER_GID, **kwargs):
        super(ApacheExporterProcess, self).__init__(uid=uid, gid=gid, **kwargs)

def argparser(args=None, description=None):
    if description is None:
        description = """\
        Script for monitoring a apache_exporter instance.
        """
    parser = argparse.ArgumentParser(description=description, usage="%(prog)s [action]")
    common.addOptions(
            parser,
            lockdir=pjoin(defaults.APACHE_EXPORTER_LOCKDIR, parser.prog),
            logdir=pjoin(defaults.APACHE_EXPORTER_LOGDIR, parser.prog))
    return parser

@common.mainwrapper(argparser, minkernel=defaults.GO_MIN_KERNEL)
def main(parser, args):
    log = logging.getLogger(name="main")

    log.info("starting up")

    prog = parser.prog
    procmonitor = process.ProcessMonitor(persistent=True, log=log)
    procmonitor.setPidDir(args.lockdir)
    atexit.register(procmonitor.stop)

    def termchild(*args):
        for proc in list(procmonitor.childmap.values()):
            proc.kill(signal.SIGTERM)
        reactor.callLater(3, procmonitor.wakeup)

    reactor.callLater(1, signal.signal, signal.SIGHUP, termchild)

    oswrapper = dryrun.getOsWrapper()
    name = ApacheExporterProcess.executable

    childlog = utils.setupchildlogging(
            oswrapper, name + "_" + prog, args, name=name,
            formatter=logging.Formatter(fmt="%(message)s"))

    proc = ApacheExporterProcess(cmdargs=defaults.APACHE_EXPORTER_ARGS, log=log, respawn=True, childlog=childlog)
    procmonitor.queueProcess(proc)
    process.cleanupOrphans(args.lockdir, "*.pid", name)
    procmonitor.start()

    reactor.run()
    log.info("Shutting down")
    return 0

if __name__ == "__main__":
    main()

