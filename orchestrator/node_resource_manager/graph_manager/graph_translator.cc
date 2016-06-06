#include "graph_translator.h"

lowlevel::Graph GraphTranslator::lowerGraphToLSI0(highlevel::Graph *graph, LSI *tenantLSI, LSI *lsi0, map<string, unsigned int > &availableEndPoints, bool orchestrator_in_band, bool creating)
{
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Creating rules for LSI-0");

	map<string,unsigned int> ports_lsi0 = lsi0->getPhysicalPorts();

	vector<VLink> tenantVirtualLinks = tenantLSI->getVirtualLinks();//FIXME: a map <emulated port name, vlink> would be better

	map<string,vector<string> > eps = tenantLSI->getEndpointsPorts();

	lowlevel::Graph lsi0Graph;

	//if orchestrator in bound install the default rule on LSI-0 otherwise skip this code
	if(orchestrator_in_band)
	{
		unsigned int i = 0;
		for(map<string, vector<string> >::iterator it = eps.begin(); it != eps.end(); it++)
		{
			//Translate the match
			lowlevel::Match lsi0Match;
			map<string,unsigned int>::iterator translation = ports_lsi0.find(it->second[3]);

			lsi0Match.setGreKey((char *)it->second[0].c_str());
			lsi0Match.setInputPort(translation->second);

			lowlevel::Action lsi0Action(true);

			//Create the rule and add it to the graph
			//The rule ID is created as follows  highlevelGraphID_hlrID
			stringstream newRuleID;
			newRuleID << graph->getID() << "_" << i;
			lowlevel::Rule lsi0Rule(lsi0Match,lsi0Action,newRuleID.str(),HIGH_PRIORITY);
			lsi0Graph.addRule(lsi0Rule);

			i++;
		}
	}

	list<highlevel::Rule> highLevelRules = graph->getRules();
	logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "The high level graph contains %d rules",highLevelRules.size());
	for(list<highlevel::Rule>::iterator hlr = highLevelRules.begin(); hlr != highLevelRules.end(); hlr++)
	{
		logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "Considering a rule");

		highlevel::Match match = hlr->getMatch();
		highlevel::Action *action = hlr->getAction();
		uint64_t priority = hlr->getPriority();

		if( (match.matchOnNF()) && (action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION) )
		{
			//NF -> NF : rule not included in LSI-0
			logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches a NF, and the action is a NF. Not inserted in LSI-0");
			continue;
		}

		if( (match.matchOnNF()) && (action->getType() == highlevel::ACTION_ON_ENDPOINT) )
		{
			continue;
		}

		if(match.matchOnPort())
		{
			//The port name must be replaced with the port identifier

			string port = match.getPhysicalPort();
			if(ports_lsi0.count(port) == 0)
			{
				logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses a match on port \"%s\", which is not attached to LSI-0",port.c_str());
				throw GraphManagerException();
			}

			//Translate the match
			lowlevel::Match lsi0Match;
			lsi0Match.setAllCommonFields(match);
			map<string,unsigned int>::iterator translation = ports_lsi0.find(port);
			lsi0Match.setInputPort(translation->second);

			//Translate the action
			string action_info = action->getInfo();
			if(action->getType() == highlevel::ACTION_ON_PORT)
			{
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the port \"%s\", and the action is output to port %s",port.c_str(),action_info.c_str());

				//The port name must be replaced with the port identifier
				if(ports_lsi0.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action on port \"%s\", which is not attached to LSI-0",port.c_str());
					throw GraphManagerException();
				}

				map<string,unsigned int>::iterator translation = ports_lsi0.find(action_info);
				unsigned int portForAction = translation->second;

				lowlevel::Action lsi0Action(portForAction);
				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					lsi0Action.addGenericAction(*ga);

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule lsi0Rule(lsi0Match,lsi0Action,newRuleID.str(),priority);
				lsi0Graph.addRule(lsi0Rule);
			}
			else if(action->getType() == highlevel::ACTION_ON_ENDPOINT)
			{
				assert(action->getType() == highlevel::ACTION_ON_ENDPOINT);

				highlevel::ActionEndPoint *action_ep = (highlevel::ActionEndPoint*)action;

				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the port \"%s\", and the action is \"%s:%d\"",port.c_str(),action_info.c_str(),action_ep->getPort());

				//All the traffic for a endpoint is sent on the same virtual link

				stringstream action_port;
				action_port << action_ep->getPort();

				map<string, uint64_t> ep_vlinks = tenantLSI->getEndPointsVlinks();
				if(ep_vlinks.count(action_port.str()) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses a endpoint action \"%s:%d\" which has not been translated into a virtual link",action_info.c_str(),action_ep->getPort());
					logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tEndpoint translated to virtual links are the following:");
					for(map<string, uint64_t>::iterator vl = ep_vlinks.begin(); vl != ep_vlinks.end(); vl++)
						logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "\t\t%s",(vl->first).c_str());
					assert(0);
				}

				uint64_t vlink_id = ep_vlinks.find(action_port.str())->second;
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				lowlevel::Action lsi0Action(vlink->getRemoteID());

				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					lsi0Action.addGenericAction(*ga);

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule lsi0Rule(lsi0Match,lsi0Action,newRuleID.str(),priority);
				lsi0Graph.addRule(lsi0Rule);
			}
			else //XXX: for sure the action is a NF. Currently, other actions are not supported
			{
				assert(action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION);

				highlevel::ActionNetworkFunction *action_nf = (highlevel::ActionNetworkFunction*)action;

				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the port \"%s\", and the action is \"%s:%d\"",port.c_str(),action_info.c_str(),action_nf->getPort());

				//Al the traffic for a NF is sent on the same virtual link

				stringstream action_port;
				action_port << action_info << "_" << action_nf->getPort();

				map<string, uint64_t> nfs_vlinks = tenantLSI->getNFsVlinks();
				if(nfs_vlinks.count(action_port.str()) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses a NF action \"%s:%d\" which has not been translated into a virtual link",action_info.c_str(),action_nf->getPort());
					logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tNetwork functions ports translated to virtual links are the following:");
					for(map<string, uint64_t>::iterator vl = nfs_vlinks.begin(); vl != nfs_vlinks.end(); vl++)
						logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "\t\t%s",(vl->first).c_str());
					assert(0);
				}
				uint64_t vlink_id = nfs_vlinks.find(action_port.str())->second;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\t\tThe virtual link related to NF \"%s\" has ID: %x",action_port.str().c_str(),vlink_id);
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				lowlevel::Action lsi0Action(vlink->getRemoteID());

				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					lsi0Action.addGenericAction(*ga);

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule lsi0Rule(lsi0Match,lsi0Action,newRuleID.str(),priority);
				lsi0Graph.addRule(lsi0Rule);
			}

		 } //end of match.matchOnPort()
		 else if(match.matchOnEndPoint())
		 {
		 	assert(action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION || action->getType() == highlevel::ACTION_ON_PORT);

		 	stringstream ss;
		 	ss << match.getEndPoint();

			if(creating)
			{
				availableEndPoints[ss.str()]++;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "endpoint \"%s\" used %d times",ss.str().c_str(), availableEndPoints[ss.str()]);
			}
			else
			{
				availableEndPoints[ss.str()]--;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "endpoint \"%s\" still used %d times",ss.str().c_str(), availableEndPoints[ss.str()]);
			}

			//Translate the match
			lowlevel::Match lsi0Match;
			string action_info = action->getInfo();

			highlevel::ActionNetworkFunction *action_nf = (highlevel::ActionNetworkFunction*)action;

			map<string, uint64_t> ep_vlinks = tenantLSI->getEndPointsVlinks();
			if(ep_vlinks.count(ss.str()) == 0)
			{
				logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses a endpoint \"%s\" which has not been translated into a virtual link",ss.str().c_str());
			}
			else
			{
				uint64_t vlink_id = ep_vlinks.find(ss.str())->second;
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());

				//All the traffic for a endpoint is sent on the same virtual link
				stringstream action_port;
				action_port << action_info << "_" << action_nf->getPort();

				lsi0Match.setAllCommonFields(match);
				lsi0Match.setInputPort(vlink->getRemoteID());
			}

			if(action->getType() == highlevel::ACTION_ON_PORT)
			{
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the endpoint \"%s\", and the action is \"%s\"",ss.str().c_str(),action_info.c_str());

				//The port name must be replaced with the port identifier
				if(ports_lsi0.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action on port \"%s\", which is not attached to LSI-0",action_info.c_str());
					throw GraphManagerException();
				}

				map<string,unsigned int>::iterator translation = ports_lsi0.find(action_info);
				unsigned int portForAction = translation->second;

				lowlevel::Action lsi0Action(portForAction);
				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					lsi0Action.addGenericAction(*ga);

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule lsi0Rule(lsi0Match,lsi0Action,newRuleID.str(),priority);
				lsi0Graph.addRule(lsi0Rule);
			}
			continue;
		 } //end of match.matchOnEndPoint()
		 else
		 {
		 	assert(match.matchOnNF());
			if(action->getType() == highlevel::ACTION_ON_PORT)
			{
				//The entire match must be replaced with the virtual link associated with the port
				//expressed in the OUTPUT action.
				//The port in the OUTPUT action must be replaced with its port identifier

				string action_info = action->getInfo();
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "Match on NF \"%s\", action is on port \"%s\"",match.getNF().c_str(),action_info.c_str());
				if(ports_lsi0.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action on port \"%s\", which is not attached to LSI-0",action_info.c_str());
					throw GraphManagerException();
				}

				//Translate the match
				lowlevel::Match lsi0Match;

				map<string, uint64_t> ports_vlinks = tenantLSI->getPortsVlinks();
				if(ports_vlinks.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action on port \"%s\", which has not been translated into a virtual link",action_info.c_str());
				}
				uint64_t vlink_id = ports_vlinks.find(action_info)->second;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\t\tThe virtual link related to port \"%s\" has ID: %x",action_info.c_str(),vlink_id);
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				lsi0Match.setInputPort(vlink->getRemoteID());

				//Translate the action
				map<string,unsigned int>::iterator translation = ports_lsi0.find(action_info);
				unsigned int portForAction = translation->second;

				lowlevel::Action lsi0Action(portForAction);
				//XXX The generic actions will be added to the tenant lsi.

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule lsi0Rule(lsi0Match,lsi0Action,newRuleID.str(),priority);
				lsi0Graph.addRule(lsi0Rule);
			}
			else if(action->getType() == highlevel::ACTION_ON_ENDPOINT)
			{
				//The entire match must be replaced with LOCAL
				//The port in the OUTPUT action must be replaced with the port identifier related to physical port associated to endpoint

				string action_info = action->getInfo();
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "Match on NF \"%s\", action is on port \"%s\"",match.getNF().c_str(),action_info.c_str());
				if(ports_lsi0.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action on port \"%s\", which is not attached to LSI-0",action_info.c_str());
					throw GraphManagerException();
				}

				//Translate the match
				lowlevel::Match lsi0Match;

				map<string, uint64_t> ports_vlinks = tenantLSI->getPortsVlinks();
				if(ports_vlinks.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action on port \"%s\", which has not been translated into a virtual link",action_info.c_str());
				}
				uint64_t vlink_id = ports_vlinks.find(action_info)->second;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\t\tThe virtual link related to port \"%s\" has ID: %x",action_info.c_str(),vlink_id);
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				lsi0Match.setInputPort(vlink->getRemoteID());

				//Translate the action
				map<string,unsigned int>::iterator translation = ports_lsi0.find(action_info);
				unsigned int portForAction = translation->second;

				lowlevel::Action lsi0Action(portForAction);
				//XXX The generic actions will be added to the tenant lsi.

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule lsi0Rule(lsi0Match,lsi0Action,newRuleID.str(),priority);
				lsi0Graph.addRule(lsi0Rule);
			}
		 }//end of match.matchOnNF()
	}

	return lsi0Graph;
}

lowlevel::Graph GraphTranslator::lowerGraphToTenantLSI(highlevel::Graph *graph, LSI *tenantLSI, LSI *lsi0)
{
	logger(ORCH_DEBUG_INFO, MODULE_NAME, __FILE__, __LINE__, "Creating rules for the tenant LSI");

	map<string,unsigned int> ports_lsi0 = lsi0->getPhysicalPorts();

	vector<VLink> tenantVirtualLinks = tenantLSI->getVirtualLinks();//FIXME: a map <emulated port name, vlink> would be better
	set<string> tenantNetworkFunctions = tenantLSI->getNetworkFunctionsName();
	map<string, vector<string> > tenantEndpoints = tenantLSI->getEndpointsPorts();

	lowlevel::Graph tenantGraph;

	list<highlevel::Rule> highLevelRules = graph->getRules();

	for(list<highlevel::Rule>::iterator hlr = highLevelRules.begin(); hlr != highLevelRules.end(); hlr++)
	{
		logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "Considering a rule");

		highlevel::Match match = hlr->getMatch();
		highlevel::Action *action = hlr->getAction();
		uint64_t priority = hlr->getPriority();

		if( (match.matchOnPort()) && (action->getType() == highlevel::ACTION_ON_PORT) )
		{
			/**
			*	physical port -> physical port : rule not included in LSI-0
			*/
			logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches a port, and the action is OUTPUT to a port. Not inserted in the tenant LSI");
			continue;
		}

		if(match.matchOnPort())
		{
		 	assert(action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION || action->getType() == highlevel::ACTION_ON_ENDPOINT);

		 	/**
			*	The entire match must be replaced with the virtual link associated with the action.
			*	The action is translated into an action to the port identifier of the NF
			*	representing the action itself
			*/

			string action_info = action->getInfo();

			if(action->getType() == highlevel::ACTION_ON_ENDPOINT)
			{
				assert(action->getType() == highlevel::ACTION_ON_ENDPOINT);

				map<string,unsigned int> tenantEndpointsPorts = tenantLSI->getEndpointsPortsId();

				highlevel::ActionEndPoint *action_ep = (highlevel::ActionEndPoint*)action;
				stringstream ep_port;
				ep_port << action_ep->getPort();

				if(match.matchOnPort())
					logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "Match on port \"%s\", action is \"%s:%s\"",match.getPhysicalPort().c_str(),action_info.c_str(),ep_port.str().c_str());

				//Translate the match
				lowlevel::Match tenantMatch;

				map<string, uint64_t> ep_vlinks = tenantLSI->getEndPointsVlinks();
				if(ep_vlinks.count(ep_port.str()) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses the action \"%s:%d\", which has not been translated into a virtual link",action_info.c_str(),ep_port.str().c_str());
				}
				uint64_t vlink_id = ep_vlinks.find(ep_port.str())->second;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\t\tThe virtual link related to action \"%s\" has ID: %x",ep_port.str().c_str(),vlink_id);
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				tenantMatch.setInputPort(vlink->getLocalID());

				//Search endpoint id
				unsigned int e_id = 0;
				map<string, unsigned int > epp = tenantLSI->getEndpointsPortsId();
				for(map<string, unsigned int >::iterator ep = epp.begin(); ep != epp.end(); ep++){
					if(strcmp(ep->first.c_str(), action_ep->getInputEndpoint().c_str()) == 0)
						e_id = ep->second;
				}

				lowlevel::Action tenantAction(e_id);

				//Create the rule and add it to the graph
				lowlevel::Rule tenantRule(tenantMatch,tenantAction,hlr->getFlowID(),priority);
				tenantGraph.addRule(tenantRule);
			}
			else
			{
				assert(action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION);

				highlevel::ActionNetworkFunction *action_nf = (highlevel::ActionNetworkFunction*)action;
				unsigned int inputPort = action_nf->getPort();

				//Can be also an Endpoint
				if(tenantNetworkFunctions.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action \"%s\", which is not a NF attacched to the tenant LSI",action_info.c_str());
					throw GraphManagerException();
				}

				map<string,unsigned int> tenantNetworkFunctionsPorts = tenantLSI->getNetworkFunctionsPorts(action_info);

				stringstream nf_port;
				nf_port << action_info << "_" << inputPort;

				if(match.matchOnPort())
					logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "Match on port \"%s\", action is \"%s:%d\"",match.getPhysicalPort().c_str(),action_info.c_str(),inputPort);

				//Can be also an Endpoint
				if(tenantNetworkFunctionsPorts.count(nf_port.str()) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action \"%s:%d\", which is not a NF attacched to the tenant LSI",action_info.c_str(),inputPort);
					throw GraphManagerException();
				}

				//Translate the match
				lowlevel::Match tenantMatch;

				map<string, uint64_t> nfs_vlinks = tenantLSI->getNFsVlinks();
				if(nfs_vlinks.count(nf_port.str()) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses the action \"%s:%d\", which has not been translated into a virtual link",action_info.c_str(),inputPort);
				}
				uint64_t vlink_id = nfs_vlinks.find(nf_port.str())->second;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\t\tThe virtual link related to action \"%s\" has ID: %x",nf_port.str().c_str(),vlink_id);
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				tenantMatch.setInputPort(vlink->getLocalID());

				//Translate the action
				map<string,unsigned int>::iterator translation = tenantNetworkFunctionsPorts.find(nf_port.str());
				lowlevel::Action tenantAction(translation->second);

				//XXX The generic actions has been added to the lsi-0.

				//Create the rule and add it to the graph
				lowlevel::Rule tenantRule(tenantMatch,tenantAction,hlr->getFlowID(),priority);
				tenantGraph.addRule(tenantRule);
			}
		}//end match.matchOnPort
		else if(match.matchOnEndPoint())
		{
			assert(match.matchOnEndPoint());

			/**
			*	Each EndPoint is translated into its port ID on tenant-LSI.
			*	The other parameters expressed in the match are not
			*	changed.
			*/

			char input_endpoint[64];
			strcpy(input_endpoint, match.getInputEndpoint());

			assert(action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION || action->getType() == highlevel::ACTION_ON_PORT);

			string action_info = action->getInfo();

			//Search endpoint id
			unsigned int e_id = 0;
			map<string, unsigned int > epp = tenantLSI->getEndpointsPortsId();
			for(map<string, unsigned int >::iterator ep = epp.begin(); ep != epp.end(); ep++){
				if(strcmp(ep->first.c_str(), input_endpoint) == 0)
					e_id = ep->second;
			}

			//Translate the match
			lowlevel::Match tenantMatch;
			tenantMatch.setAllCommonFields(match);
			tenantMatch.setInputPort(e_id);

			if(action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION)
			{
				highlevel::ActionNetworkFunction *action_nf = (highlevel::ActionNetworkFunction*)action;

				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the endpoint \"%s\", and the action is \"%s:%d\"",input_endpoint,action_info.c_str(),action_nf->getPort());

				stringstream action_port;
				action_port << action_info << "_" << action_nf->getPort();

				map<string,unsigned int> tenantNetworkFunctionsPorts = tenantLSI->getNetworkFunctionsPorts(action_info);

				//Translate the action
				map<string,unsigned int>::iterator translation = tenantNetworkFunctionsPorts.find(action_port.str());

				lowlevel::Action tenantAction(/*vlink->getRemoteID()*/translation->second);

				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					tenantAction.addGenericAction(*ga);

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule tenantRule(tenantMatch,tenantAction,newRuleID.str(),priority);
				tenantGraph.addRule(tenantRule);
			}
			else
			{
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the endpoint \"%s\", and the action is \"%s\"",input_endpoint,action_info.c_str());

				//Translate the action
				map<string, uint64_t> p_vlinks = tenantLSI->getPortsVlinks();
				if(p_vlinks.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses a port action \"%s\" which has not been translated into a virtual link",action_info.c_str());
					assert(0);
				}
				uint64_t vlink_id = p_vlinks.find(action_info)->second;
				//logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\t\tThe virtual link related to NF \"%s\" has ID: %x",action_info.c_str(),vlink_id);
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				lowlevel::Action tenantAction(vlink->getLocalID());

				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					tenantAction.addGenericAction(*ga);

				//Create the rule and add it to the graph
				//The rule ID is created as follows  highlevelGraphID_hlrID
				stringstream newRuleID;
				newRuleID << graph->getID() << "_" << hlr->getFlowID();
				lowlevel::Rule tenantRule(tenantMatch,tenantAction,newRuleID.str(),priority);
				tenantGraph.addRule(tenantRule);
			}
			continue;
		}
		else //match.matchOnNF()
		{
			assert(match.matchOnNF());

			/**
			*	Each NF is translated into its port ID on tenant-LSI.
			*	The other parameters expressed in the match are not
			*	changed.
			*/

			string nf = match.getNF();
			int nfPort = match.getPortOfNF();

			if(tenantNetworkFunctions.count(nf) == 0)
			{
				logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses a match \"%s\", which is not a NF attacched to the tenant LSI",nf.c_str());
				throw GraphManagerException();
			}

			map<string,unsigned int> tenantNetworkFunctionsPorts = tenantLSI->getNetworkFunctionsPorts(nf);

			stringstream nf_output;
			nf_output << nf << "_" << nfPort;

			if(tenantNetworkFunctionsPorts.count(nf_output.str()) == 0)
			{
				logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses (at rule %s) a match on \"%s:%d\", which is not attached to the tenant LSI",(hlr->getFlowID()).c_str(),nf.c_str(),nfPort);
				throw GraphManagerException();
			}

			//Translate the match
			lowlevel::Match tenantMatch;
			tenantMatch.setAllCommonFields(match);

			map<string,unsigned int>::iterator translation = tenantNetworkFunctionsPorts.find(nf_output.str());
			tenantMatch.setInputPort(translation->second);

			//Translate the action
			string action_info = action->getInfo(); //e.g., "firewall"
			if(action->getType() == highlevel::ACTION_ON_NETWORK_FUNCTION)
			{
				highlevel::ActionNetworkFunction *action_nf = (highlevel::ActionNetworkFunction*)action;
				unsigned int inputPort = action_nf->getPort();//e.g., "1"
				stringstream nf_port;
				nf_port << action_info << "_" << inputPort;//e.g., "firewall_1"

				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the \"%s:%d\", and the action is \"%s:%d\"",nf.c_str(),nfPort,action_info.c_str(),inputPort);

				if(tenantNetworkFunctions.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses the  \"%s\", which is not a NF attacched to the tenant LSI",nf.c_str());
					throw GraphManagerException();
				}

				map<string,unsigned int> tenantNetworkFunctionsPortsAction = tenantLSI->getNetworkFunctionsPorts(action_info);

				//The NF must be replaced with the port identifier
				if(tenantNetworkFunctionsPortsAction.count(nf_port.str()) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an action (at rule %s) on NF \"%s:%d\", which is not attached to LSI-0",(hlr->getFlowID()).c_str(),action_info.c_str(),inputPort);
					throw GraphManagerException();
				}
				map<string,unsigned int>::iterator translation = tenantNetworkFunctionsPortsAction.find(nf_port.str());
				lowlevel::Action tenantAction(translation->second);

				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					tenantAction.addGenericAction(*ga);

				//Create the rule and add it to the graph
				lowlevel::Rule tenantRule(tenantMatch,tenantAction,hlr->getFlowID(),priority);
				tenantGraph.addRule(tenantRule);
			}
			else if(action->getType() == highlevel::ACTION_ON_PORT)
			{
				/**
				*	The phyPort is translated into the tenant side virtual link that
				*	"represents the phyPort" in the tenant LSI. The other parameters
				*	expressed in the match are not changed.
				*/

				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the \"%s:%d\", and the action is  OUTPUT to port \"%s\"",nf.c_str(),nfPort,action_info.c_str());

				//Al the traffic for a physical is sent on the same virtual link

				map<string, uint64_t> ports_vlinks = tenantLSI->getPortsVlinks();
				if(ports_vlinks.count(action_info) == 0)
				{
					logger(ORCH_WARNING, MODULE_NAME, __FILE__, __LINE__, "The tenant graph expresses an OUTPUT action on port \"%s\" which has not been translated into a virtual link",action_info.c_str());
				}
				uint64_t vlink_id = ports_vlinks.find(action_info)->second;
				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\t\tThe virtual link related to the physical port \"%s\" has ID: %x",action_info.c_str(),vlink_id);
				vector<VLink>::iterator vlink = tenantVirtualLinks.begin();
				for(;vlink != tenantVirtualLinks.end(); vlink++)
				{
					if(vlink->getID() == vlink_id)
						break;
				}
				assert(vlink != tenantVirtualLinks.end());
				lowlevel::Action tenantAction(vlink->getLocalID());

				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					tenantAction.addGenericAction(*ga);

				//Create the rule and add it to the graph
				lowlevel::Rule tenantRule(tenantMatch,tenantAction,hlr->getFlowID(),priority);
				tenantGraph.addRule(tenantRule);
			}
			else
			{
				assert(action->getType() == highlevel::ACTION_ON_ENDPOINT);

				/**
				*	the endpoint is translated into the tenant side virtual link that
				*	"represents the endpoint" in the tenant LSI. The other parameters
				*	expressed in the match are not changed.
				*/

				highlevel::ActionEndPoint *action_ep = (highlevel::ActionEndPoint*)action;
				stringstream ep_port;
				ep_port << action_ep->getPort();

				logger(ORCH_DEBUG, MODULE_NAME, __FILE__, __LINE__, "\tIt matches the \"%s:%d\", and the action is an output on endpoint \"%s\"",nf.c_str(),nfPort,ep_port.str().c_str());

				unsigned int e_id = 0;
				//Al the traffic for an endpoint is sent on the same virtual link
				map<string,unsigned int> tenantEndpointsPorts = tenantLSI->getEndpointsPortsId();
				for(map<string, unsigned int >::iterator ep = tenantEndpointsPorts.begin(); ep != tenantEndpointsPorts.end(); ep++){
					if(strcmp(ep->first.c_str(), action_ep->getInputEndpoint().c_str()) == 0)
						e_id = ep->second;
				}

				lowlevel::Action tenantAction(/*vlink->getLocalID()*/e_id);

				//XXX the generic actions must be inserted in this graph.
				list<GenericAction*> gas = action->getGenericActions();
				for(list<GenericAction*>::iterator ga = gas.begin(); ga != gas.end(); ga++)
					tenantAction.addGenericAction(*ga);

				//Create the rule and add it to the graph
				lowlevel::Rule tenantRule(tenantMatch,tenantAction,hlr->getFlowID(),priority);
				tenantGraph.addRule(tenantRule);
			}
		} //end match.matchOnNF

	}

	return tenantGraph;
}
