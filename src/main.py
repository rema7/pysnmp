import threading
import time
import collections

from pysnmp.entity import engine, config
from pysnmp import debug
from pysnmp.entity.rfc3413 import cmdrsp, context, ntforg
from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.smi import builder

MibObject = collections.namedtuple('MibObject', ['mibName',
                                                 'objectType', 'valueFunc'])


def createVariable(SuperClass, getValue, *args):
    """This is going to create a instance variable that we can export.
    getValue is a function to call to retreive the value of the scalar
    """

    class Var(SuperClass):
        def readGet(self, name, *args):
            return name, self.syntax.clone(getValue())

    return Var(*args)


class Mib(object):
    """Stores the data we want to serve.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._test_count = 0

    def get_dce(self):
        return "My Description"


class SNMPAgent(object):
    def __init__(self, mibObjects):
        self._snmpEngine = engine.SnmpEngine()

        # open a UDP socket to listen for snmp requests
        config.addSocketTransport(self._snmpEngine, udp.domainName,
                                  udp.UdpTransport().openServerMode(('', 7757)))

        # add a v2 user with the community string public
        config.addV1System(self._snmpEngine, "agent", "public")
        # let anyone accessing 'public' read anything in the subtree below,
        # which is the enterprises subtree that we defined our MIB to be in
        config.addVacmUser(self._snmpEngine, 2, "agent", "noAuthNoPriv",
                           readSubTree=(1, 3, 6, 1, 4, 1))

        # each app has one or more contexts
        self._snmpContext = context.SnmpContext(self._snmpEngine)

        # the builder is used to load mibs. tell it to look in the
        # current directory for our new MIB. We'll also use it to
        # export our symbols later
        mibBuilder = self._snmpContext.getMibInstrum().getMibBuilder()
        mibSources = mibBuilder.getMibSources() + (builder.DirMibSource('.'),)
        mibBuilder.setMibSources(*mibSources)

        # our variables will subclass this since we only have scalar types
        # can't load this type directly, need to import it
        MibScalarInstance, = mibBuilder.importSymbols('SNMPv2-SMI',
                                                      'MibTable')

        mib = Mib()

        (
            nodeEntry,
            profileEntry,
            nodeIdxColumn,
            profileIdxColumn,
            dcdColumn,
            profileNameColumn
        ) = mibBuilder.importSymbols(
            'AKSION-CONTROL-MIB',
            'nodeEntry',
            'profileEntry',
            'nodeIdx',
            'profileIdx',
            'dcd',
            'profileName'
        )
        rowInstanceId = nodeEntry.getInstIdFromIndices(1)
        mibInstrumentation = self._snmpContext.getMibInstrum()
        mibInstrumentation.writeVars(
            (
                (dcdColumn.name + rowInstanceId, 'xx1'),
            )
        )

        rowProfileInstanceId = profileEntry.getInstIdFromIndices(1)
        mibInstrumentation = self._snmpContext.getMibInstrum()
        mibInstrumentation.writeVars(
            (
                (profileNameColumn.name + rowInstanceId + rowProfileInstanceId, 'ProfileNode1'),
            )
        )

        #
        rowInstanceId = nodeEntry.getInstIdFromIndices(2)
        mibInstrumentation = self._snmpContext.getMibInstrum()
        mibInstrumentation.writeVars(
            (
                (dcdColumn.name + rowInstanceId, 'xx 2'),
            )
        )

        rowProfileInstanceId = profileEntry.getInstIdFromIndices(2)
        mibInstrumentation = self._snmpContext.getMibInstrum()
        mibInstrumentation.writeVars(
            (
                (profileNameColumn.name + rowInstanceId + rowProfileInstanceId, 'ProfileNode2'),
            )
        )

        # tell pysnmp to respotd to get, getnext, and getbulk
        cmdrsp.GetCommandResponder(self._snmpEngine, self._snmpContext)
        cmdrsp.NextCommandResponder(self._snmpEngine, self._snmpContext)
        cmdrsp.BulkCommandResponder(self._snmpEngine, self._snmpContext)

    def serve_forever(self):
        print('Starting agent')
        self._snmpEngine.transportDispatcher.jobStarted(1)
        try:
            self._snmpEngine.transportDispatcher.runDispatcher()
        except:
            self._snmpEngine.transportDispatcher.closeDispatcher()
            raise


class Worker(threading.Thread):
    """Just to demonstrate updating the MIB
    and sending traps
    """

    def __init__(self, agent, mib):
        threading.Thread.__init__(self)
        self._agent = agent
        self._mib = mib
        self.setDaemon(True)

    def run(self):
        while True:
            time.sleep(3)
            # self._mib.setTestCount(mib.getTestCount()+1)
            # self._agent.sendTrap()


if __name__ == '__main__':
    mib = Mib()
    objects = [MibObject('AKSION-CONTROL-MIB', 'nodeTable', mib.get_dce)]
    agent = SNMPAgent(objects)
    # agent.setTrapReceiver('192.168.1.14', 'traps')
    Worker(agent, mib).start()
    try:
        agent.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down')
