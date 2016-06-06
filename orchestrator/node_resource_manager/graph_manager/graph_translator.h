#ifndef GRAPH_TRANSLATOR_H_
#define GRAPH_TRANSLATOR_H_ 1

#pragma once

#include <sstream>

#include "graph_manager.h"
#include "../graph/high_level_graph/high_level_graph.h"

class GraphTranslator
{
friend class GraphManager;

	/**
	*	@Brief: this class applies some (complicated) rules to translate the highlevel description of
	*	the graph into lowlevel descriptions to be provided (as flowmod messages) respectively to the
	*	LSI-0 and to the tenant-LSI
	*/

protected:

	/**
	*	If the match is expressed on an endpoint, the action must be expressed on a NF
	*	If the action is expressed on an endpoint, the match must be expressed on a NF
	*/

	/**
	*	@brief: translate an high level graph into a rules to be sent to
	*		the LSI-0
	*
	*	@param: graph						High level graph to be translated
	*	@param: tenantLSI					Information related to the LSI of the tenant
	*	@param: lsi0						Information related to the LSI-0
	*	@param: availableEndPoints			Indicates the number of time each available endpoint is used
	*										by graphs not defining the endpoint itself
	*	@param: creating					Indicates if the translation is needed to create or to detroy
	*										a graph
	*
	*	@Translation rules:
	*		phyPort -> phyPort :
	*			Each phyPort is translated into its port ID on LSI-0.
	*			The other parameters expressed in the match are not
	*			changed.
	*		phyPort -> NF:
	*			PhyPort is translated into its port ID on LSI-0, while
	*			NF is translated into the LSI-0 side virtual link that
	*			"represents the NF" in LSI-0.
	*			The other parameters expressed in the match are not
	*			changed.
	*		NF -> phyPort:
	*			The entire match is replaced with a match on the LSI-0
	*			side of the virtual link that "represents the port" in the
	*			tenant LSI.
	*			phyPort is translated into it port ID on LSI-0.
	*		NF -> NF:
	*			This rule does not appear in LSI-0.
	*		NF -> endpoint:
	*			This rule does not appear in LSI-0
	*		endpoint -> NF:
	*			This rule does not appear in LSI-0
	*/
	static lowlevel::Graph lowerGraphToLSI0(highlevel::Graph *graph, LSI *tenantLSI, LSI *lsi0, map<string, unsigned int > &availableEndPoints, bool orchestrator_in_band = true, bool creating = true);

	/**
	*	@brief: translate an high level graph into a rules to be sent to
	*		the Tenant-LSI
	*
	*	@param: graph		High level graph to be translated
	*	@graph: tenantLSI	Information related to the LSI of the tenant
	*	@graph: lsi0		Information related to the LSI-0
	*
	*	@Translation rules:
	*		phyPort -> phyPort :
	*			This rule does not appear in the tenant LSI.
	*		phyPort -> NF :
	*			The entire match is replaced with a match on the tenant-LSI
	*			side of the virtual link that represents the NF on LSI-0.
	*			NF is translated into the port ID on tenant-LSI.
	*		endpoint -> NF:
	*			endpoint and NF is translated into the port ID on tenant-LSI.
	*		NF -> phyPort:
	*			NF is translated into the port ID on tenant-LSI, while phyPort
	*			is translated into the tenant side virtual link that "represents
	*			the phyPort" in the tenant LSI.
	*			The other parameters expressed in the match are not changed.
	*		NF -> NF:
	*			Each NF is translated into its port ID on tenant-LSI.
	*			The other parameters expressed in the match are not
	*			changed.
	*		NF -> endpoint:
	*			endpoint and NF is translated into the port ID on tenant-LSI.
	*/
	static lowlevel::Graph lowerGraphToTenantLSI(highlevel::Graph *graph, LSI *tenantLSI, LSI *lsi0);

	/**
	*	@Rules used to assign generic actions associated with an high level action to a low level action:
	*		phyPort -> phyPort:
	*			The generic actions are inserted in the LSI-0
	*		phyPort -> NF:
	*			The generic actions are inserted in the LSI-0
	*		NF -> NF:
	*			The generic actions are inserted in the tenant LSI
	*		NF -> phyPort:
	*			The generic actions are inserted in the tenant LSI
	*		NF -> endpoint:
	*			The generic actions are inserted in the tenant LSI
	*		endpoint -> NF:
	*			The generic actions are inserted in the tenant LSI
	*/
};

#endif //GRAPH_TRANSLATOR_H_
