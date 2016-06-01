
from virtualizer5.virtualizer import *
from er_utils import *

import xml.etree.ElementTree as ET

import logging
nffg_log = logging.getLogger(__name__)
nffg_log.setLevel(logging.DEBUG)

def process_nffg(nffg_xml):

    nffg_log.debug("Reading dict: {0}".format(nffg_xml))

    try:
        tree = ET.fromstring(nffg_xml)
    except ET.ParseError as e:
        nffg_log.debug('ParseError: {0}'.format(e.message))
        return 0

    nffg_log.debug("File correctly read")

    nffg = Virtualizer.parse(root=tree)
    universal_nodes = nffg.nodes
    # take first node per default
    # alternatively, we can look for UUID11 (as done in UN virtualizer.py)
    for un in universal_nodes:
        un_id = un.id.get_value()
        nffg_log.debug("found UN: {0}".format(un_id))
        ovs_switches = find_ovs(un)
        return ovs_switches

def find_ovs(un):
    """
    find ER data paths (ovs containers) in the topology
    :param un: Universal Node object from the NFFG
    :return:
    """
    ovs_instances = {}
    nf_instances = un.NF_instances
    for nf in nf_instances:
        nf_name = nf.name.get_value()
        nf_type = nf.type.get_value()
        logging.debug("found NF: {0}".format(nf.name.get_value()))
        if 'ovs' in nf_type:
            ovsName = nf.name.get_value()
            ovsId = nf.id.get_value()
            new_DP = DP(ovsName, ovsId)
            ovs_instances[ovsName] = new_DP
            nffg_log.debug("found ovs NF: {0}".format(ovsName))

            for port in nf.ports:
                portName = port.name.get_value()

                # do not add control or public port of the DP
                if 'control' in portName or 'public' in portName: continue

                portId = port.id.get_value()
                new_port = DPPort(portName, portId, DP_parent=new_DP)
                new_DP.ports.append(new_port)

                logging.debug("found ovs port: {0} with ovs id: {1}".format(portName, ovsId))

    # first make all the ovs instances with all the ports,
    # then fill the linked ports
    # this function is only used to parse the first nffg, external ports only
    for ovs_name in ovs_instances:
        ovsId = ovs_instances[ovs_name].id
        for port in ovs_instances[ovs_name].ports:
            portId = port.id
            flowrules = getFlowRulesSendingTrafficFromPort(un, ovsId, portId)

            for flowrule in flowrules:
                # assume only one action
                port_linked = flowrule.out.get_target()
                portPath = flowrule.out.get_target().get_path()
                tokens = portPath.split('/')
                port_linked_type = tokens[4]
                port_linked_id = (port_linked.id.get_value())

                # check if external port
                if port_linked_type == 'ports':
                    SAP_name = port_linked.sap.get_value()
                    port.port_type = DPPort.External
                    linked_port = DPPort(SAP_name, port_linked_id, port_type=DPPort.SAP)
                # check if internal port
                elif port_linked_type == 'NF_instances':
                    vnf = port_linked.get_parent().get_parent()
                    vnf_name = vnf.name.get_value()
                    if not 'ovs' in vnf_name:
                        continue
                    port_linked_name = port_linked.name.get_value()
                    port.port_type = DPPort.Internal
                    for port2 in ovs_instances[vnf_name].ports:
                        if port2.ifname == port_linked_name:
                            linked_port = port2

                port.linked_port = linked_port
                linked_port.linked_port = port

    # after all internal/external ports are known in the NFFG,
    # set the forward_extport for all internal ports
    # choose a free one, when multiple  ext ports are on the same DP
    for ovs_name in ovs_instances:
        port_list = ovs_instances[ovs_name].ports
        external_ports = [port for port in port_list if port.port_type == DPPort.External]
        internal_ports = [port for port in port_list if port.port_type == DPPort.Internal]

        other_DPs = [ovs_name2 for ovs_name2 in ovs_instances if ovs_name != ovs_name2]
        for ext_port in external_ports:
            for ovs_name2 in other_DPs:
                for int_port in internal_ports:
                    # find first available free internal port to link to ext port
                    if int_port.linked_port.DP.name == ovs_name2 and int_port.forward_extport is None:
                        int_port.forward_extport = ext_port
                        break

    return ovs_instances



def getFlowRulesSendingTrafficFromPort(un, vnfId, portId):
    flow_rules = []

    for flowentry in un.flowtable:
        portPath = flowentry.port.get_target().get_path()
        port = flowentry.port.get_target()
        tokens = portPath.split('/')
        if tokens[4] == 'ports':
            # This is a port of the universal node, skip
            pass

        elif tokens[4] == 'NF_instances':
            # This is a port of the NF. I have to extract the port ID and the type of the NF.
            vnf = port.get_parent().get_parent()
            vnf_id = vnf.id.get_value()
            port_id = (port.id.get_value())
            if vnf_id == vnfId and port_id == portId:
                flow_rules.append(flowentry)

        else:
            nffg_log.error("Invalid port {0} defined in a flowentry".format(port))

        continue

    return flow_rules


if __name__ == "__main__":
    xml = open('test.xml').read()
    ovs_instances = process_nffg(xml)
    pass