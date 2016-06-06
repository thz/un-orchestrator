#include "high_level_graph_vnf.h"

namespace highlevel
{

#ifdef ENABLE_UNIFY_PORTS_CONFIGURATION
VNFs::VNFs(string id, string name, list<string> groups, string vnf_template, list<vector<string> > ports, list<pair<string, string> > control_ports, list<string> environment_variables) :
	id(id), name(name), groups(groups), vnf_template(vnf_template)
#else
VNFs::VNFs(string id, string name, list<string> groups, string vnf_template, list<vector<string> > ports) :
	id(id), name(name), groups(groups), vnf_template(vnf_template)
#endif
{
	for(list<vector<string> >::iterator p = ports.begin(); p != ports.end(); p++)
	{
		this->ports.push_back((*p));
	}

#ifdef ENABLE_UNIFY_PORTS_CONFIGURATION
	this->control_ports.insert(this->control_ports.end(),control_ports.begin(),control_ports.end());
	this->environment_variables.insert(this->environment_variables.end(),environment_variables.begin(),environment_variables.end());
#endif
}

VNFs::~VNFs()
{

}

bool VNFs::operator==(const VNFs &other) const
{
	if(id == other.id && name == other.name)
		return true;

	return false;
}

string VNFs::getId()
{
	return id;
}

string VNFs::getName()
{
	return name;
}

list<string> VNFs::getGroups()
{
	return groups;
}

string VNFs::getVnfTemplate()
{
	return vnf_template;
}

list <vector<string> > VNFs::getPorts()
{
	return ports;
}

void VNFs::print()
{
	if(LOGGING_LEVEL <= ORCH_DEBUG_INFO)
	{
		cout << "\t\tid:" << id << endl;
		cout << "\t\t\tname: " << name << endl;
		cout << "\t\t\tvnf_template: " << vnf_template << endl;
		cout << "\t\t\tgroups: " << endl << "\t\t{" << endl;
		for(list<string>::iterator it = groups.begin(); it != groups.end(); it++)
			cout << "\t\t\t" << *it << endl;
		cout << "\t\t}" << endl;
		cout << "\t\t\tports: " << endl << "\t\t{" << endl;
		for(list<vector<string> >::iterator p = ports.begin(); p != ports.end(); p++)
		{
			cout << "\t\t\tid: " << (*p)[0] << endl;
			cout << "\t\t\tname: " << (*p)[1] << endl;
			if(!(*p)[2].empty())
				cout << "\t\t\tmac: " << (*p)[2] << endl;
			if(!(*p)[3].empty())
				cout << "\t\t\tip: " << (*p)[3] << endl;
		}
		cout << "\t\t}" << endl;
#ifdef ENABLE_UNIFY_PORTS_CONFIGURATION
		cout << "\t\t\tunify-control: " << endl << "\t\t{" << endl;
		for(list<pair<string, string> >::iterator c = control_ports.begin(); c != control_ports.end(); c++)
		{
			cout << "\t\t\thost-tcp-port: " << (*c).first << endl;
			cout << "\t\t\tvnf-tcp-port: " << (*c).second << endl;
		}
		cout << "\t\t}" << endl;
#endif
	}
}

Object VNFs::toJSON()
{
	Object vnf;
	Array portS,groups_Array;
#ifdef ENABLE_UNIFY_PORTS_CONFIGURATION
	Array ctrl_ports;
	Array env_variables;
#endif

	vnf[_ID] = id.c_str();
	vnf[_NAME] = name.c_str();
	vnf[VNF_TEMPLATE] = vnf_template.c_str();
	for(list<string>::iterator it = groups.begin(); it != groups.end(); it++)
		groups_Array.push_back((*it).c_str());
	if(groups.size()!=0)
		vnf[VNF_GROUPS] = groups_Array;
	for(list<vector<string> >::iterator p = ports.begin(); p != ports.end(); p++)
	{
		Object pp;

		pp[_ID] = (*p)[0].c_str();
		pp[_NAME] = (*p)[1].c_str();
		pp[PORT_MAC] = (*p)[2].c_str();
		pp[PORT_IP] = (*p)[3].c_str();

		portS.push_back(pp);
	}
	vnf[VNF_PORTS] = portS;

#ifdef ENABLE_UNIFY_PORTS_CONFIGURATION
	for(list<pair<string, string> >::iterator c = control_ports.begin(); c != control_ports.end(); c++)
	{
		Object cc;

		cc[HOST_PORT] = atoi((*c).first.c_str());
		cc[VNF_PORT] = atoi((*c).second.c_str());

		ctrl_ports.push_back(cc);
	}
	vnf[UNIFY_CONTROL] = ctrl_ports;

	for(list<string>::iterator ev = environment_variables.begin(); ev != environment_variables.end(); ev++)
	{
		Object var;

		var[VARIABLE] = ev->c_str();
		env_variables.push_back(var);
	}
	vnf[UNIFY_ENV_VARIABLES] = env_variables;
#endif

	return vnf;
}

}
