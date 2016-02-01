#ifndef OVSDBManager_H_
#define OVSDBManager_H_ 1

#include "../../../../utils/logger.h"
#include "../../../../utils/constants.h"

#include "../../switch_manager.h"

#include "commands.h"

using namespace std;

class LSI;

class OVSDBManager : public SwitchManager
{
private:

public:
	OVSDBManager(bool of_controller_lsi0);

	~OVSDBManager();

	CreateLsiOut *createLsi(CreateLsiIn cli);

	AddNFportsOut *addNFPorts(AddNFportsIn anpi);

	AddEndpointOut *addEndpoint(AddEndpointIn aepi);

	AddVirtualLinkOut *addVirtualLink(AddVirtualLinkIn avli);

	void destroyLsi(uint64_t dpid);

	void destroyNFPorts(DestroyNFportsIn dnpi);

    void destroyEndpoint(DestroyEndpointIn depi);

	void destroyVirtualLink(DestroyVirtualLinkIn dvli);

	void checkPhysicalInterfaces(set<CheckPhysicalPortsIn> cppi);

};

class OVSDBManagerException: public SwitchManagerException
{
public:
	virtual const char* what() const throw()
	{
		return "OVSDBManagerException";
	}
};

#endif //OVSDBManager_H_
