#ifndef RESOURCE_MANAGER_H_
#define RESOURCE_MANAGER_H_ 1

#include "../pub_sub/pub_sub.h"
#include "../../utils/logger.h"
#include "../../utils/constants.h"
#include "domain_description/domain_description.h"
#include "../graph/high_level_graph/high_level_graph.h"
#include <string>
using namespace std;


/**
*	@brief: this class exports resources of the Universal Node, by means of the
**		DoubleDecker client
*/
class ResourceManager
{
	/**
	*	@breif: Object that represents the domain description
	*/
	static domainInformations::DomainDescription *domainDescription;
	/**
	*	@breif: Read the domain description from file to fill domainDescirption Object
	*/
	static bool readDescriptionFromFile(char *filename,string &fileContent);
	/**
	*	@breif: Publish the domain information
	*/
	static void publishDescription();
public:
	/**
	*	@breif: initialize domainDescription object reading domain information written in a specific file, finally call publishDescription()
	*
	*	@param	descr_file: file containing the description of the domain to
	*		be exported
	*/
	static bool init(char *descr_file);
	/**
	*	@breif: update the domain description and performs publish
	*
	*	@param	positiveGraph: contains informations that have to be added
	*	@param	negativeGraph: contains informations that have to be removed
	*/
	static void updateDescription(highlevel::Graph *positiveGraph, highlevel::Graph *negativeGraph);
};

#endif // RESOURCE_MANAGER_H_
