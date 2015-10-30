#ifndef LIBVIRT_H_
#define LIBVIRT_H_ 1

#pragma once

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string>
#include <sstream>
#include <list>
#include <map>
#include <string.h>
#include <locale>
#include <libvirt/libvirt.h>
#include <libvirt/virterror.h>
#include "../../../utils/logger.h"
#include "../../../utils/constants.h"

#include "../../nfs_manager.h"
#include "../../startNF_in.h"

#ifdef ENABLE_KVM_DPDK_IVSHMEM
	#include "ivshmem_cmdline_generator.h"
#endif

#include <libxml/encoding.h>
#include <libxml/xmlwriter.h>
#include <libxml/xmlreader.h>

#include <libxml/tree.h>
#include <libxml/parser.h>
#include <libxml/xpath.h>
#include <libxml/xpathInternals.h>

using namespace std;

class Libvirt : public NFsManager
{
private:

#ifndef ENABLE_KVM_DPDK_IVSHMEM
	
	/**
	*	@bfief: Connection towards Libvirt
	*/
	static virConnectPtr connection;
#else

	/**
	*	@brief: TCP port to be assigned to the VM monitor to
	*		the next VM to be executed
	*/
	static unsigned int next_tcp_port;
#endif


#ifndef ENABLE_KVM_DPDK_IVSHMEM	
	/**
	*	@brief:	Open a connection with QEMU/KVM
	*/
	void connect();
	
	/**
	*	@brief: Disconnect from QEMU/KVM
	*/
	void disconnect();
	
	/**
	*	@brief: Custom error handler
	*/
	static void customErrorFunc(void *userdata, virErrorPtr err);
#endif

public:

	Libvirt();
	~Libvirt();
	
	bool isSupported();
	
	bool startNF(StartNFIn sni);
	bool stopNF(StopNFIn sni);
	
	bool interact(string name, string command);
};

#endif //LIBVIRT_H_
