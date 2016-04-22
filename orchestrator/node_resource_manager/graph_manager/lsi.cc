#include "lsi.h"

#include <sstream>

static string nf_port_name(const string& nf_name, unsigned int port_id)
{
	stringstream ss;
	ss << nf_name << "_" << port_id;

	return ss.str();
}

LSI::LSI(string controllerAddress, string controllerPort, set<string> physical_ports, /*map<string, list<unsigned int> > nf_ports*/ list<highlevel::VNFs> network_functions,
	list<highlevel::EndPointGre> endpoints_ports, vector<VLink> virtual_links, map<string, map<unsigned int,PortType> > a_nfs_ports_type) :
		controllerAddress(controllerAddress), controllerPort(controllerPort),
		virtual_links(virtual_links.begin(),virtual_links.end())
{
	for(set<string>::iterator p = physical_ports.begin(); p != physical_ports.end(); p++)
		this->physical_ports[*p] = 0;

	//create NF ports (and give them names)
#if 0
	for(map<string, list< unsigned int> >::iterator nf = nf_ports.begin(); nf != nf_ports.end(); nf++)
#endif
	for(list<highlevel::VNFs>::iterator nf = network_functions.begin(); nf != network_functions.end(); nf++)
	{
		list<unsigned int> nf_ports = nf->getPortsId();
		addNF(nf->getName()/*first*/, /*nf->second*/nf_ports, a_nfs_ports_type[nf->/*first*/getName()]);
	}

	//fill the list of gre endpoints
	for(list<highlevel::EndPointGre>::iterator ep = endpoints_ports.begin(); ep != endpoints_ports.end(); ep++)
		this->endpoints_ports.push_back(*ep);
}

string LSI::getControllerAddress()
{
	return controllerAddress;
}

string LSI::getControllerPort()
{
	return controllerPort;
}

list<string> LSI::getPhysicalPortsName()
{
	list<string> names;

	map<string,unsigned int>::iterator p = physical_ports.begin();
	for(; p != physical_ports.end(); p++)
		names.push_back(p->first);

	return names;
}

set<string> LSI::getNetworkFunctionsName()
{
	set<string> names;

	for(map<string,struct nfData>::iterator nf = network_functions.begin(); nf != network_functions.end(); nf++)
		names.insert(nf->first);

	return names;
}

list<highlevel::EndPointGre> LSI::getEndpointsPorts()
{
	return endpoints_ports;
}

map<string,unsigned int > LSI::getEndpointsPortsId()
{
	return endpoints_ports_id;
}

list<string> LSI::getNetworkFunctionsPortNames(string nf)
{
	list<string> names;

	map<string, unsigned int> ports = network_functions[nf].ports_switch_id;

	for(map<string, unsigned int>::iterator p = ports.begin(); p != ports.end(); p++)
		names.push_back(p->first);

	return names;
}

PortType LSI::getNetworkFunctionPortType(string nf, string port_name)
{
	map<string, nfData>::iterator nf_it = network_functions.find(nf);
	if (nf_it == network_functions.end())
		return UNDEFINED_PORT;

	map<string, PortType>& ports = nf_it->second.ports_type;
	map< string, PortType >::iterator port_it = ports.find(port_name);
	if (port_it == ports.end())
		return UNDEFINED_PORT;

	return port_it->second;
}

map<string, list< struct nf_port_info> > LSI::getNetworkFunctionsPortsInfo()
{
	map<string, list<struct nf_port_info> > res;

	for (map<string,struct nfData>::iterator nf_it = network_functions.begin(); nf_it != network_functions.end(); ++nf_it) {
		const string& nf_name = nf_it->first;
		struct nfData& nf_data = nf_it->second;

		list<unsigned int>& ports = nf_data.nf_ports_id;
		list<struct nf_port_info> pi_list;
		for (list<unsigned int>::iterator port_it = ports.begin(); port_it != ports.end(); ++port_it) {
			string port_name = nf_port_name(nf_name, *port_it);

			struct nf_port_info pi;
			pi.port_name = port_name;
			pi.port_type = getNetworkFunctionPortType(nf_name, port_name);
			pi_list.push_back(pi); //each element contains the port name and the port type
		}
		res[nf_name] = pi_list;
	}

	return res;
}

map<unsigned int, string> LSI::getNetworkFunctionsPortsNameOnSwitchMap(string nf)
{
	map<unsigned int, string> res;

	map<string, nfData>::iterator nf_it = network_functions.find(nf);	//Retrieve the info associated with the required network function
	if (nf_it != network_functions.end()) {
		struct nfData& nf_data = nf_it->second;

		return nf_data.ports_name_on_switch;
	}

	return res;
}

list<uint64_t> LSI::getVirtualLinksRemoteLSI()
{
	list<uint64_t> dpids;

	vector<VLink>::iterator vl = virtual_links.begin();
	for(; vl != virtual_links.end(); vl++)
		dpids.push_back(vl->remote_dpid);

	return dpids;
}

void LSI::setDpid(uint64_t dpid)
{
	this->dpid = dpid;
}

bool LSI::setPhysicalPortID(string port, uint64_t id)
{
	if(physical_ports.count(port) == 0)
	{
		assert(0);
		return false;
	}

	physical_ports[port] = id;
	return true;
}

bool LSI::setNfSwitchPortsID(string nf, map<string, unsigned int> translation)
{
	//The network function must exist
	assert(network_functions.count(nf) != 0);
	if(network_functions.count(nf) == 0)
		return false;

	//Retrieve the data associated with this network function
	struct nfData& nf_data = network_functions[nf];

	for(map<string, unsigned int>::iterator t = translation.begin(); t != translation.end(); t++)
	{
		//The network function port must exist
		assert(nf_data.ports_switch_id.count(t->first) != 0);
		if(nf_data.ports_switch_id.count(t->first) == 0)
			return false;

		nf_data.ports_switch_id[t->first] = t->second;
	}

	return true;
}

bool LSI::setEndpointPortID(string ep, uint64_t id)
{
	bool found = false;

	for(list<highlevel::EndPointGre>::iterator endp = endpoints_ports.begin(); endp != endpoints_ports.end(); endp++)
		if(endp->getId().compare(ep) == 0)
			found = true;

	if(!found)
	{
		assert(0);
		return false;
	}

	endpoints_ports_id[ep] = id;
	return true;
}

/**
 * Warning: The 'names' is expected to holds names as a vector where the index
 * is the NF port id (as coming from the NF description).
 * TODO: Clarity and robustness would benefit from changing this to
 * e.g. map<unsigned int, string> (port_id -> port_name_on_switch). However it
 * only helps if the change is also done at the source of this data...
 *
 * This thing is fundamental to implement the hotplug, where the first port created for sure does not
 * have ID equal to 1.
 */
void LSI::setNetworkFunctionsPortsNameOnSwitch(string nf, list<string> names)
{
	if(network_functions.count(nf) == 0)
		return;  //TODO: ERROR

	struct nfData& nf_data = network_functions[nf];

	int id = 0;
	for (list<string>::iterator n_it = names.begin(); n_it != names.end(); ++n_it) {
		nf_data.ports_name_on_switch.insert(map<unsigned int, string>::value_type(++id, *n_it));
	}
}

void LSI::setVLinkIDs(unsigned int position, unsigned int localID, unsigned int remoteID)
{
	virtual_links[position].local_id = localID;
	virtual_links[position].remote_id = remoteID;
}

uint64_t LSI::getDpid()
{
	return dpid;
}

map<string,unsigned int> LSI::getPhysicalPorts()
{
	return physical_ports;
}

map<string,unsigned int> LSI::getNetworkFunctionsPorts(string nf)
{
	struct nfData& nf_data = network_functions[nf];

	return nf_data.ports_switch_id;
}

vector<VLink> LSI::getVirtualLinks()
{
	return virtual_links;
}

VLink LSI::getVirtualLink(uint64_t ID)
{
	vector<VLink>::iterator v = virtual_links.begin();
	for(; v != virtual_links.end(); v++)
	{
		if(v->getID() == ID)
			return *v;
	}

	//cannot be here!
	assert(0);
	return *v;
}


map<string, uint64_t> LSI::getNFsVlinks()
{
	return nfs_vlinks;
}

map<string, uint64_t> LSI::getPortsVlinks()
{
	return ports_vlinks;
}

map<string, uint64_t> LSI::getEndPointsVlinks()
{
	return endpoints_vlinks;
}

map<string, uint64_t> LSI::getEndPointsGreVlinks()
{
	return endpoints_gre_vlinks;
}

void LSI::setNFsVLinks(map<string, uint64_t> nfs_vlinks)
{
	for(map<string, uint64_t>::iterator it = nfs_vlinks.begin(); it != nfs_vlinks.end(); it++)
		this->nfs_vlinks.insert(*it);
}

void LSI::setPortsVLinks(map<string, uint64_t> ports_vlinks)
{
	for(map<string, uint64_t>::iterator it = ports_vlinks.begin(); it != ports_vlinks.end(); it++)
		this->ports_vlinks.insert(*it);
}

void LSI::setEndPointsVLinks(map<string, uint64_t> endpoints_vlinks)
{
	for(map<string, uint64_t>::iterator it = endpoints_vlinks.begin(); it != endpoints_vlinks.end(); it++)
		this->endpoints_vlinks.insert(*it);
}

void LSI::setEndPointsGreVLinks(map<string, uint64_t> endpoints_vlinks)
{
	for(map<string, uint64_t>::iterator it = endpoints_vlinks.begin(); it != endpoints_vlinks.end(); it++)
		this->endpoints_gre_vlinks.insert(*it);
}

void LSI::addNFvlink(string NF, uint64_t vlinkID)
{
	nfs_vlinks[NF] = vlinkID;
}

void LSI::addPortvlink(string port, uint64_t vlinkID)
{
	ports_vlinks[port] = vlinkID;
}

void LSI::addEndpointvlink(string endpoint, uint64_t vlinkID)
{
	endpoints_vlinks[endpoint] = vlinkID;
}

void LSI::addEndpointGrevlink(string endpoint, uint64_t vlinkID)
{
	endpoints_gre_vlinks[endpoint] = vlinkID;
}

void LSI::removeNFvlink(string nf_port)
{
	if(nfs_vlinks.count(nf_port) == 0)
	{
		assert(0);
		return;
	}

	map<string,uint64_t>::iterator it = nfs_vlinks.find(nf_port);
	nfs_vlinks.erase(it);
}

void LSI::removePortvlink(string port)
{
	if(ports_vlinks.count(port) == 0)
	{
		assert(0);
		return;
	}

	map<string,uint64_t>::iterator it = ports_vlinks.find(port);
	ports_vlinks.erase(it);
}

void LSI::removeEndPointvlink(string endpoint)
{
	if(endpoints_vlinks.count(endpoint) == 0)
	{
		assert(0);
		return;
	}

	map<string,uint64_t>::iterator it = endpoints_vlinks.find(endpoint);
	endpoints_vlinks.erase(it);
}

void LSI::removeEndPointGrevlink(string endpoint)
{
	if(endpoints_gre_vlinks.count(endpoint) == 0)
	{
		assert(0);
		return;
	}

	map<string,uint64_t>::iterator it = endpoints_vlinks.find(endpoint);
	endpoints_gre_vlinks.erase(it);
}

bool LSI::addNF(string nf_name, list< unsigned int> ports, const map<unsigned int, PortType>& a_nf_ports_type)
{
	//TODO: this assert will not be valid when we will introduce the hotplug.
	//In that case, this function should be modified so that the nfData (already existing) of the network
	//function is retrieved and updated. 
	assert(network_functions.count(nf_name) == 0);

	nfData nf_data;
	nf_data.nf_ports_id = ports;

	for (list< unsigned int>::iterator port_it = ports.begin(); port_it != ports.end(); ++port_it) {
		unsigned int port_id = (*port_it);  // This is the VNF port id from the NF-FG ("my_vnf:1" -> 1)

		string port_name = nf_port_name(nf_name, port_id);

		nf_data.ports_switch_id[port_name] = 0;	// Until the switch assigns an OpenFlow ID to the NF ports

		map<unsigned int, PortType>::const_iterator pt_it = a_nf_ports_type.find(port_id);
		if (pt_it == a_nf_ports_type.end())
			return false;
		nf_data.ports_type[port_name] = pt_it->second;
	}

	network_functions[nf_name] = nf_data;

	return true;
}

void LSI::addEndpoint(highlevel::EndPointGre ep)
{
	endpoints_ports.push_back(ep);
}

int LSI::addVlink(VLink vlink)
{
	//TODO: protect the next operation with a mutex
	int retVal = virtual_links.size();
	virtual_links.insert(virtual_links.end(),vlink);

	return retVal;
}

void LSI::removeVlink(uint64_t ID)
{
	for(vector<VLink>::iterator v = virtual_links.begin(); v != virtual_links.end(); v++)
	{
		if(v->getID() == ID)
		{
			virtual_links.erase(v);
			return;
		}
	}

	assert(0);
	return;
}

void LSI::removeNF(string nf)
{
	map<string, struct nfData>::iterator it =  network_functions.find(nf);
	if (it != network_functions.end()) {
		network_functions.erase(it);
	}
}

void LSI::removeEndpoint(string ep)
{
	for(list<highlevel::EndPointGre>::iterator endp = endpoints_ports.begin(); endp != endpoints_ports.end(); endp++)
		if(endp->getId().compare(ep) == 0)
			endpoints_ports.erase(endp);

	return;
}
