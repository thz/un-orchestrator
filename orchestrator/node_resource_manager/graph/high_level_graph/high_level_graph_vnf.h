#ifndef HIGH_LEVEL_GRAPH_VNFS_H_
#define HIGH_LEVEL_GRAPH_VNFS_H_ 1

#include "../../../utils/logger.h"
#include "../../../utils/constants.h"

#include <iostream>
#include <sstream>

#include <string.h>
#include <list>

#include <json_spirit/json_spirit.h>
#include <json_spirit/value.h>
#include <json_spirit/writer.h>

using namespace json_spirit;
using namespace std;

namespace highlevel
{

class VNFs
{
private:
	/**
	*	@brief: the id of the VNF (e.g., 00000003)
	*/
	string id;

	/**
	*	@brief: the name of the VNF (e.g., example)
	*/
	string name;

	/**
	*	@brief: the groups of the VNF (e.g., example)
	*/
	list<string> groups;

	/**
	*	@brief: the vnf template of the VNF (e.g., example.json)
	*/
	string vnf_template;

	/**
	*	@brief: the list of ports configuration of the VNF
	*/
	list<vector<string> > ports;

#ifdef ENABLE_UNIFY_PORTS_CONFIGURATION
	/**
	*	@brief: the list of control ports configuration of the VNF
	*/
	list<pair<string, string> > control_ports;

	/**
	*	@brief: list of environment variables to be set to the VNF.
	*			Each element of the list is in the form "variable=value"
	*/
	list<string> environment_variables;
#endif

public:

#ifdef ENABLE_UNIFY_PORTS_CONFIGURATION
	VNFs(string id, string name, list<string> groups, string vnf_template, list<vector<string> > ports, list<pair<string, string> > control_ports, list<string> environment_variables);
#else
	VNFs(string id, string name, list<string> groups, string vnf_template, list<vector<string> > ports);
#endif

	string getId();
	string getName();
	list<string> getGroups();
	string getVnfTemplate();
	list<vector<string> > getPorts();

	~VNFs();

	bool operator==(const VNFs &other) const;

	void print();
	Object toJSON();
};

}

#endif //HIGH_LEVEL_GRAPH_VNFS_H_
